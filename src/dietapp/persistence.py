from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dietapp.models import PlanningRequest, WeeklyPlan, WellnessStrategy
from dietapp.planner import DietResult, StrategyResult


APP_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = APP_ROOT / "data" / "household_profile.json"

DEFAULT_PROFILE_VALUES: dict[str, Any] = {
    "person_one_name": "Io",
    "person_one_style": "Onnivoro",
    "person_one_age": 38,
    "person_one_sex": "Uomo",
    "person_one_height_cm": 178,
    "person_one_weight_kg": 82.0,
    "person_one_target_weight_kg": 82.0,
    "person_one_activity": "Lavoro d'ufficio, 3 allenamenti a settimana e camminate nei giorni restanti.",
    "person_one_dislikes": "",
    "person_one_allergies": "",
    "person_two_name": "Mia moglie",
    "person_two_style": "Vegetariano",
    "person_two_age": 35,
    "person_two_sex": "Donna",
    "person_two_height_cm": 165,
    "person_two_weight_kg": 63.0,
    "person_two_target_weight_kg": 63.0,
    "person_two_activity": "Attivita moderata, yoga e camminate regolari durante la settimana.",
    "person_two_dislikes": "",
    "person_two_allergies": "",
    "budget": "Bilanciato",
    "max_prep_minutes": 30,
    "leftover_lunches": 3,
    "batch_days": ["Domenica", "Mercoledi"],
    "cuisines": ["Italiana", "Mediterranea", "Comfort food leggera"],
    "pantry_staples": ["Riso", "Pasta", "Farro", "Legumi in barattolo", "Uova", "Pane integrale"],
    "excluded_ingredients": "",
    "notes": "Preferiamo ricette italiane semplici, con cene rapide e basi comuni da personalizzare.",
}


@dataclass(slots=True)
class StoredPlanningState:
    request_payload: PlanningRequest
    strategy_result: StrategyResult
    diet_result: DietResult | None = None


def load_profile_form_values(path: Path | None = None) -> dict[str, Any]:
    profile_path = path or PROFILE_PATH
    if not profile_path.exists():
        return dict(DEFAULT_PROFILE_VALUES)

    try:
        raw_data = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_PROFILE_VALUES)

    return _sanitize_profile_values(raw_data)


def save_profile_form_values(values: dict[str, Any], path: Path | None = None) -> None:
    profile_path = path or PROFILE_PATH
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    clean_values = _sanitize_profile_values(values)
    profile_path.write_text(
        json.dumps(clean_values, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_profile_form_values_from_supabase(
    client: Any,
    user_id: str,
    table_name: str = "user_profiles",
) -> dict[str, Any]:
    response = (
        client.table(table_name)
        .select("form_values")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    if not rows:
        return dict(DEFAULT_PROFILE_VALUES)

    row = rows[0] if isinstance(rows, list) else rows
    return _sanitize_profile_values(row.get("form_values"))


def save_profile_form_values_to_supabase(
    values: dict[str, Any],
    client: Any,
    user_id: str,
    table_name: str = "user_profiles",
) -> None:
    clean_values = _sanitize_profile_values(values)
    (
        client.table(table_name)
        .upsert(
            {
                "user_id": user_id,
                "form_values": clean_values,
            },
            on_conflict="user_id",
        )
        .execute()
    )


def load_planning_state_from_supabase(
    client: Any,
    user_id: str,
    table_name: str = "user_profiles",
) -> StoredPlanningState | None:
    response = (
        client.table(table_name)
        .select(
            "request_payload,strategy_payload,strategy_source_label,strategy_warning,plan_payload,diet_source_label,diet_warning"
        )
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    if not rows:
        return None

    row = rows[0] if isinstance(rows, list) else rows
    request_payload_raw = row.get("request_payload")
    strategy_payload_raw = row.get("strategy_payload")
    if not request_payload_raw or not strategy_payload_raw:
        return None

    request_payload = PlanningRequest.from_dict(request_payload_raw)
    strategy = WellnessStrategy.from_dict(strategy_payload_raw)
    strategy_result = StrategyResult(
        strategy=strategy,
        source_label=str(row.get("strategy_source_label") or strategy.model_source or "salvato").strip()
        or "salvato",
        warning=_nullable_text(row.get("strategy_warning")),
    )

    diet_result = None
    if row.get("plan_payload"):
        plan = WeeklyPlan.from_dict(row.get("plan_payload"))
        diet_result = DietResult(
            plan=plan,
            source_label=str(row.get("diet_source_label") or plan.model_source or "salvato").strip()
            or "salvato",
            warning=_nullable_text(row.get("diet_warning")),
        )

    return StoredPlanningState(
        request_payload=request_payload,
        strategy_result=strategy_result,
        diet_result=diet_result,
    )


def save_planning_state_to_supabase(
    request_payload: PlanningRequest,
    strategy_result: StrategyResult,
    diet_result: DietResult | None,
    client: Any,
    user_id: str,
    table_name: str = "user_profiles",
) -> None:
    payload = {
        "user_id": user_id,
        "request_payload": request_payload.to_dict(),
        "strategy_payload": strategy_result.strategy.to_dict(),
        "strategy_source_label": strategy_result.source_label,
        "strategy_warning": strategy_result.warning,
        "plan_payload": diet_result.plan.to_dict() if diet_result is not None else None,
        "diet_source_label": diet_result.source_label if diet_result is not None else None,
        "diet_warning": diet_result.warning if diet_result is not None else None,
    }
    client.table(table_name).upsert(payload, on_conflict="user_id").execute()


def clear_planning_state_from_supabase(
    client: Any,
    user_id: str,
    table_name: str = "user_profiles",
) -> None:
    client.table(table_name).upsert(
        {
            "user_id": user_id,
            "request_payload": None,
            "strategy_payload": None,
            "strategy_source_label": None,
            "strategy_warning": None,
            "plan_payload": None,
            "diet_source_label": None,
            "diet_warning": None,
        },
        on_conflict="user_id",
    ).execute()


def _sanitize_profile_values(raw_values: Any) -> dict[str, Any]:
    clean_values = dict(DEFAULT_PROFILE_VALUES)
    if not isinstance(raw_values, dict):
        return clean_values

    for field_name, default_value in DEFAULT_PROFILE_VALUES.items():
        has_candidate_value = field_name in raw_values
        candidate_value = raw_values.get(field_name, default_value)
        if isinstance(default_value, list):
            if isinstance(candidate_value, list):
                clean_values[field_name] = [
                    str(item).strip() for item in candidate_value if str(item).strip()
                ]
            else:
                clean_values[field_name] = list(default_value)
            continue

        if isinstance(default_value, int):
            try:
                clean_values[field_name] = int(candidate_value)
            except (TypeError, ValueError):
                clean_values[field_name] = default_value
            continue

        if isinstance(default_value, float):
            if field_name.endswith("_target_weight_kg") and not has_candidate_value:
                weight_field_name = field_name.replace("_target_weight_kg", "_weight_kg")
                clean_values[field_name] = float(clean_values.get(weight_field_name, default_value))
                continue
            try:
                clean_values[field_name] = float(candidate_value)
            except (TypeError, ValueError):
                if field_name.endswith("_target_weight_kg"):
                    weight_field_name = field_name.replace("_target_weight_kg", "_weight_kg")
                    clean_values[field_name] = float(clean_values.get(weight_field_name, default_value))
                else:
                    clean_values[field_name] = default_value
            continue

        clean_values[field_name] = "" if candidate_value is None else str(candidate_value).strip()

    return clean_values


def _nullable_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None