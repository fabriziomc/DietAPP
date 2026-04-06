from __future__ import annotations

import json
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = APP_ROOT / "data" / "household_profile.json"

DEFAULT_PROFILE_VALUES: dict[str, Any] = {
    "person_one_name": "Io",
    "person_one_style": "Onnivoro",
    "person_one_age": 38,
    "person_one_sex": "Uomo",
    "person_one_height_cm": 178,
    "person_one_weight_kg": 82.0,
    "person_one_activity": "Lavoro d'ufficio, 3 allenamenti a settimana e camminate nei giorni restanti.",
    "person_one_dislikes": "",
    "person_one_allergies": "",
    "person_two_name": "Mia moglie",
    "person_two_style": "Vegetariano",
    "person_two_age": 35,
    "person_two_sex": "Donna",
    "person_two_height_cm": 165,
    "person_two_weight_kg": 63.0,
    "person_two_activity": "Attivita moderata, yoga e camminate regolari durante la settimana.",
    "person_two_dislikes": "",
    "person_two_allergies": "",
    "budget": "Bilanciato",
    "max_prep_minutes": 30,
    "leftover_lunches": 3,
    "batch_days": ["Domenica", "Mercoledi"],
    "cuisines": ["Mediterranea", "Medio Oriente", "Tex-Mex"],
    "pantry_staples": ["Avena", "Riso", "Pasta", "Legumi in barattolo", "Uova", "Yogurt greco"],
    "excluded_ingredients": "",
    "notes": "Preferiamo cene rapide e basi comuni da personalizzare in padella o al forno.",
}


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


def _sanitize_profile_values(raw_values: Any) -> dict[str, Any]:
    clean_values = dict(DEFAULT_PROFILE_VALUES)
    if not isinstance(raw_values, dict):
        return clean_values

    for field_name, default_value in DEFAULT_PROFILE_VALUES.items():
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
            try:
                clean_values[field_name] = float(candidate_value)
            except (TypeError, ValueError):
                clean_values[field_name] = default_value
            continue

        clean_values[field_name] = "" if candidate_value is None else str(candidate_value).strip()

    return clean_values