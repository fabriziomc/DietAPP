from __future__ import annotations

import json
from typing import Any

from dietapp.config import AppConfig
from dietapp.defaults import DAYS
from dietapp.models import (
    DayPlan,
    HouseholdPreferences,
    IngredientPortion,
    MealSlot,
    MealVariant,
    PersonProfile,
    PersonWellnessStrategy,
    PlanningRequest,
    WeeklyPlan,
    WellnessStrategy,
)
from dietapp.planning.common import (
    PLAN_SYSTEM_PROMPT,
    STRATEGY_SYSTEM_PROMPT,
    ProviderFailure,
    _coerce_bool,
    _coerce_int,
    _coerce_optional_int,
    _to_string_list,
)
from dietapp.planning.fallback_plan import _normalize_shopping_list, generate_fallback_plan
from dietapp.planning.quantities import (
    aggregate_shopping_details,
    build_coherence_checks,
    build_ingredient_details,
    build_portion_label,
    merge_ingredient_details,
    shopping_details_to_legacy_lists,
)
from dietapp.planning.strategy import generate_fallback_wellness_strategy


def _call_llm_json(
    openai_client_factory: Any,
    config: AppConfig,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    if openai_client_factory is None:
        raise RuntimeError("pacchetto openai non installato")

    client_kwargs: dict[str, Any] = {"api_key": config.get_api_key(provider)}
    base_url = config.get_base_url(provider)
    if base_url:
        client_kwargs["base_url"] = base_url
    default_headers = config.get_default_headers(provider)
    if default_headers:
        client_kwargs["default_headers"] = default_headers

    client = openai_client_factory(**client_kwargs)
    request_kwargs: dict[str, Any] = {
        "model": config.get_model(provider),
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if max_tokens is not None:
        request_kwargs["max_tokens"] = max_tokens
    model_fallbacks = config.get_model_fallbacks(provider)
    if model_fallbacks:
        request_kwargs["extra_body"] = {
            "models": list(model_fallbacks),
            "route": "fallback",
        }

    response = client.chat.completions.create(**request_kwargs)
    content = response.choices[0].message.content or "{}"
    return json.loads(content)


def _build_provider_source_label(config: AppConfig, provider: str | None = None) -> str:
    return f"{config.get_provider_label(provider)} | {config.get_model(provider)}"


def _build_provider_failure(exc: Exception, config: AppConfig, provider: str) -> ProviderFailure:
    return ProviderFailure(
        source_label=_build_provider_source_label(config, provider),
        message=_format_provider_exception(exc, config, provider),
    )


def _summarize_provider_failures(failures: list[ProviderFailure]) -> str:
    return " ".join(
        f"{failure.source_label} non ha risposto correttamente ({failure.message})."
        for failure in failures
    )


def _build_provider_recovery_warning(
    subject: str,
    failures: list[ProviderFailure],
    success_source_label: str,
) -> str | None:
    if not failures:
        return None
    return (
        f"{subject}: {_summarize_provider_failures(failures)} "
        f"Ho usato {success_source_label} come fallback."
    )


def _build_local_provider_warning(
    subject: str,
    failures: list[ProviderFailure],
    local_resolution: str,
) -> str | None:
    if not failures:
        return None
    return f"{subject}: {_summarize_provider_failures(failures)} {local_resolution}"


def _format_provider_exception(exc: Exception, config: AppConfig, provider: str | None = None) -> str:
    message = str(exc).strip() or "errore sconosciuto"
    selected_provider = provider or config.normalize_provider()
    if selected_provider != "openrouter":
        return message

    lowered = message.lower()
    if "temporarily rate-limited upstream" in lowered or "rate limit" in lowered:
        fallback_models = config.get_model_fallbacks()
        fallback_hint = ""
        if fallback_models:
            fallback_hint = (
                " Ho configurato fallback automatici su altri modelli OpenRouter; se anche quelli sono saturi, "
                "puoi cambiare OPENROUTER_MODEL oppure personalizzare OPENROUTER_FALLBACK_MODELS."
            )
        return (
            "il modello OpenRouter scelto e temporaneamente limitato sul provider upstream gratuito. "
            "Riprova tra poco, usa un altro modello gratuito oppure collega una integrazione BYOK nel tuo account OpenRouter."
            + fallback_hint
        )

    return message


def build_strategy_prompt_preview(request: PlanningRequest) -> str:
    return _format_prompt_preview(STRATEGY_SYSTEM_PROMPT, _build_strategy_ai_prompt(request))


def build_plan_prompt_preview(request: PlanningRequest, strategy: WellnessStrategy) -> str:
    return _format_prompt_preview(PLAN_SYSTEM_PROMPT, _build_plan_ai_prompt(request, strategy))


def _format_prompt_preview(system_prompt: str, user_prompt: str) -> str:
    return "\n\n".join(
        [
            "=== SYSTEM PROMPT ===",
            system_prompt,
            "=== USER PROMPT ===",
            user_prompt,
        ]
    )


def _build_strategy_ai_prompt(request: PlanningRequest) -> str:
    payload = request.to_dict()
    return f"""
Analizza il seguente profilo di coppia e proponi in italiano una strategia benessere realistica.

Payload:
{json.dumps(payload, indent=2, ensure_ascii=False)}

Regole:
- Usa soprattutto eta, sesso, altezza, peso e descrizione dell'attivita fisica.
- Se target_weight_kg e inferiore o superiore al peso attuale, interpretalo come obiettivo esplicito di dimagrimento o aumento di peso.
- Se allow_protein_powder=true per una persona, puoi considerare proteine in polvere solo come supporto pratico al target proteico, non come base del piano.
- Se allow_protein_powder=false, non proporre proteine in polvere per quella persona.
- Calorie e proteine devono essere output derivati, non la base del ragionamento.
- Non fare diagnosi mediche e non proporre tagli calorici aggressivi.
- Tieni conto del diverso regime alimentare della coppia.
- La strategia deve essere pratica da trasformare in un piano settimanale con cucina condivisa.

Restituisci JSON con questo schema esatto:
{{
  "title": "string",
  "couple_summary": "string",
  "shared_principles": ["string"],
  "kitchen_principles": ["string"],
  "person_one": {{
    "focus": "string",
    "rationale": "string",
    "daily_kcal_target": 2200,
    "protein_target_g": 140,
    "movement_guidance": "string",
    "nutrition_guidance": ["string"]
  }},
  "person_two": {{
    "focus": "string",
    "rationale": "string",
    "daily_kcal_target": 1800,
    "protein_target_g": 95,
    "movement_guidance": "string",
    "nutrition_guidance": ["string"]
  }}
}}
""".strip()


def _build_plan_day_schema_prompt(day_name: str) -> str:
    return f"""
        {{
            "day": "{day_name}",
            "breakfast": {{
                "shared_base": "string",
                    "person_one": {{"title": "string", "description": "string", "portion_label": "string", "ingredients": [{{"name": "string", "quantity": 120, "unit": "g"}}], "prep_notes": "string"}},
                    "person_two": {{"title": "string", "description": "string", "portion_label": "string", "ingredients": [{{"name": "string", "quantity": 120, "unit": "g"}}], "prep_notes": "string"}},
                "prep_minutes": 10,
                "leftover_friendly": false,
                "reuse_from_previous": "string",
                "kitchen_load": "Basso"
            }},
            "lunch": {{
                "shared_base": "string",
                    "person_one": {{"title": "string", "description": "string", "portion_label": "string", "ingredients": [{{"name": "string", "quantity": 120, "unit": "g"}}], "prep_notes": "string"}},
                    "person_two": {{"title": "string", "description": "string", "portion_label": "string", "ingredients": [{{"name": "string", "quantity": 120, "unit": "g"}}], "prep_notes": "string"}},
                "prep_minutes": 10,
                "leftover_friendly": true,
                "reuse_from_previous": "string",
                "kitchen_load": "Basso"
            }},
            "dinner": {{
                "shared_base": "string",
                    "person_one": {{"title": "string", "description": "string", "portion_label": "string", "ingredients": [{{"name": "string", "quantity": 150, "unit": "g"}}], "prep_notes": "string"}},
                    "person_two": {{"title": "string", "description": "string", "portion_label": "string", "ingredients": [{{"name": "string", "quantity": 150, "unit": "g"}}], "prep_notes": "string"}},
                "prep_minutes": 25,
                "leftover_friendly": true,
                "reuse_from_previous": "string",
                "kitchen_load": "Medio"
            }}
        }}
        """.strip()


def _build_plan_days_schema_prompt() -> str:
    return ",\n".join(_build_plan_day_schema_prompt(day_name) for day_name in DAYS)


def _build_plan_ai_prompt(request: PlanningRequest, strategy: WellnessStrategy) -> str:
    payload = request.to_dict()
    strategy_payload = strategy.to_dict()
    return f"""
Costruisci un piano alimentare settimanale in italiano per una coppia usando questa strategia benessere come fonte principale.

Payload coppia:
{json.dumps(payload, indent=2, ensure_ascii=False)}

Strategia benessere approvata:
{json.dumps(strategy_payload, indent=2, ensure_ascii=False)}

Regole:
- La strategia sopra e il punto di partenza: i pasti devono rispettare focus, target derivati e linee guida di ciascuna persona.
- Genera sempre 7 giorni, da Lunedi a Domenica.
- Il JSON e valido solo se contiene esattamente 7 oggetti in "days", ciascuno con breakfast, lunch e dinner valorizzati; non fermarti a 5 o 6 giorni e non usare null nei pasti.
- L'ultimo oggetto di "days" deve essere Domenica.
- Evita di ripetere la stessa combinazione completa di colazione, pranzo e cena in giorni diversi: la settimana deve avere una rotazione credibile.
- Le ricette devono essere concrete e riconoscibili come cucina italiana domestica o tradizione regionale italiana alleggerita.
- Minimizza il lavoro in cucina con basi comuni, batch cooking, ingredienti ripetuti e avanzi intelligenti.
- Usa gli stessi nomi presenti nel payload per person_one e person_two.
- Se allow_protein_powder=true, puoi usare proteine in polvere solo in modo sobrio, massimo una porzione al giorno e solo quando aiutano davvero il target proteico.
- Se allow_protein_powder=false, evita di inserirle nel piano per quella persona.
- Mantieni shared_base, description e prep_notes brevi e operativi; ogni ingredients deve avere al massimo 6 elementi davvero usati nel piatto.
- Ogni elemento di ingredients deve essere un oggetto con name, quantity e unit; usa quantita realistiche per una persona.
- Mantieni le cene entro il tempo massimo richiesto quando possibile.
- Evita ingredienti esclusi, allergie e cibi non graditi.
- Usa budget e cucine preferite per orientare la scelta degli ingredienti, ma resta in un perimetro di ricette italiane.
- La lista della spesa deve essere aggregata per categoria.

Restituisci JSON con questo schema esatto:
{{
  "title": "string",
  "strategy": "string",
  "prep_tasks": ["string"],
  "planning_notes": ["string"],
  "shopping_list": {{
    "Verdure": ["string"],
    "Proteine": ["string"],
    "Supplementi": ["string"],
    "Dispensa": ["string"],
    "Frigo": ["string"]
  }},
  "days": [
{_build_plan_days_schema_prompt()}
  ]
}}
""".strip()


def _normalize_wellness_strategy(
    raw_strategy: Any,
    request: PlanningRequest,
    model_source: str,
) -> WellnessStrategy:
    fallback = generate_fallback_wellness_strategy(request)
    raw_strategy = raw_strategy if isinstance(raw_strategy, dict) else {}

    return WellnessStrategy(
        title=str(raw_strategy.get("title") or fallback.title),
        couple_summary=str(raw_strategy.get("couple_summary") or fallback.couple_summary),
        shared_principles=_to_string_list(raw_strategy.get("shared_principles")) or fallback.shared_principles,
        kitchen_principles=_to_string_list(raw_strategy.get("kitchen_principles")) or fallback.kitchen_principles,
        person_one=_normalize_person_wellness_strategy(raw_strategy.get("person_one"), fallback.person_one),
        person_two=_normalize_person_wellness_strategy(raw_strategy.get("person_two"), fallback.person_two),
        model_source=model_source,
    )


def _normalize_person_wellness_strategy(
    raw_person_strategy: Any,
    fallback: PersonWellnessStrategy,
) -> PersonWellnessStrategy:
    raw_person_strategy = raw_person_strategy if isinstance(raw_person_strategy, dict) else {}
    return PersonWellnessStrategy(
        focus=str(raw_person_strategy.get("focus") or fallback.focus),
        rationale=str(raw_person_strategy.get("rationale") or fallback.rationale),
        daily_kcal_target=_coerce_optional_int(
            raw_person_strategy.get("daily_kcal_target"),
            fallback.daily_kcal_target,
        ),
        protein_target_g=_coerce_optional_int(
            raw_person_strategy.get("protein_target_g"),
            fallback.protein_target_g,
        ),
        movement_guidance=str(raw_person_strategy.get("movement_guidance") or fallback.movement_guidance),
        nutrition_guidance=(
            _to_string_list(raw_person_strategy.get("nutrition_guidance"))
            or fallback.nutrition_guidance
        ),
    )


def _normalize_ai_plan(
    raw_plan: dict[str, Any],
    request: PlanningRequest,
    strategy: WellnessStrategy,
    model_source: str,
) -> WeeklyPlan:
    fallback_plan = generate_fallback_plan(request, strategy)
    days_raw = raw_plan.get("days") if isinstance(raw_plan, dict) else []
    days: list[DayPlan] = []

    if not isinstance(days_raw, list):
        days_raw = []

    for index, day_name in enumerate(DAYS):
        fallback_day = fallback_plan.days[index]
        raw_day = days_raw[index] if index < len(days_raw) and isinstance(days_raw[index], dict) else {}
        has_ai_content = _day_payload_has_ai_content(raw_day)
        days.append(
            DayPlan(
                day=str(raw_day.get("day") or fallback_day.day or day_name),
                breakfast=_normalize_meal_slot(raw_day.get("breakfast"), request, fallback_day.breakfast, "breakfast"),
                lunch=_normalize_meal_slot(raw_day.get("lunch"), request, fallback_day.lunch, "lunch"),
                dinner=_normalize_meal_slot(raw_day.get("dinner"), request, fallback_day.dinner, "dinner"),
                source="AI" if has_ai_content else "Fallback",
            )
        )

    days = _replace_duplicate_ai_days(days, fallback_plan.days)

    shopping_list = _normalize_shopping_list(raw_plan.get("shopping_list"))
    shopping_list_details = _normalize_shopping_list_details(raw_plan.get("shopping_list"))
    if not shopping_list_details:
        shopping_list_details = aggregate_shopping_details(days)
    if not shopping_list:
        shopping_list = shopping_details_to_legacy_lists(shopping_list_details) or fallback_plan.shopping_list

    prep_tasks = _to_string_list(raw_plan.get("prep_tasks")) or fallback_plan.prep_tasks
    planning_notes = _to_string_list(raw_plan.get("planning_notes")) or fallback_plan.planning_notes
    coherence_checks = build_coherence_checks(days, request.preferences.max_prep_minutes)

    return WeeklyPlan(
        title=str(raw_plan.get("title") or fallback_plan.title),
        strategy=str(raw_plan.get("strategy") or fallback_plan.strategy),
        prep_tasks=prep_tasks,
        planning_notes=planning_notes,
        shopping_list=shopping_list,
        days=days,
        model_source=model_source,
        shopping_list_details=shopping_list_details,
        coherence_checks=coherence_checks,
    )


def _normalize_meal_slot(raw: Any, request: PlanningRequest, fallback_slot: MealSlot, meal_type: str) -> MealSlot:
    raw = raw if isinstance(raw, dict) else {}
    shared_base = str(raw.get("shared_base") or fallback_slot.shared_base)
    person_one_variant = _normalize_meal_variant(
        raw.get("person_one") or raw.get(request.person_one.name),
        fallback_slot.person_one,
        meal_type,
    )
    person_two_variant = _normalize_meal_variant(
        raw.get("person_two") or raw.get(request.person_two.name),
        fallback_slot.person_two,
        meal_type,
    )

    return MealSlot(
        shared_base=shared_base,
        person_one=person_one_variant,
        person_two=person_two_variant,
        prep_minutes=_coerce_int(raw.get("prep_minutes"), fallback_slot.prep_minutes),
        leftover_friendly=_coerce_bool(raw.get("leftover_friendly"), fallback_slot.leftover_friendly),
        reuse_from_previous=str(raw.get("reuse_from_previous") or fallback_slot.reuse_from_previous),
        kitchen_load=str(raw.get("kitchen_load") or fallback_slot.kitchen_load),
    )


def _normalize_meal_variant(raw: Any, fallback_variant: MealVariant, meal_type: str) -> MealVariant:
    if isinstance(raw, str):
        description = raw.strip() or fallback_variant.description
        return MealVariant(
            title=fallback_variant.title,
            description=description,
            ingredients=list(fallback_variant.ingredients),
            prep_notes=fallback_variant.prep_notes,
            portion_label=fallback_variant.portion_label,
            ingredient_details=list(fallback_variant.ingredient_details),
        )

    if not isinstance(raw, dict):
        return MealVariant(
            title=fallback_variant.title,
            description=fallback_variant.description,
            ingredients=list(fallback_variant.ingredients),
            prep_notes=fallback_variant.prep_notes,
            portion_label=fallback_variant.portion_label,
            ingredient_details=list(fallback_variant.ingredient_details),
        )

    ingredient_details = _normalize_ingredient_details(
        raw.get("ingredient_details") or raw.get("ingredients"),
        meal_type,
        fallback_variant.ingredient_details,
        fallback_variant.ingredients,
    )
    ingredients = [detail.name for detail in ingredient_details] or list(fallback_variant.ingredients)

    return MealVariant(
        title=str(raw.get("title") or fallback_variant.title),
        description=str(raw.get("description") or fallback_variant.description),
        ingredients=ingredients,
        prep_notes=str(raw.get("prep_notes") or fallback_variant.prep_notes),
        portion_label=str(raw.get("portion_label") or fallback_variant.portion_label or build_portion_label(meal_type)).strip(),
        ingredient_details=ingredient_details,
    )


def _normalize_ingredient_details(
    raw: Any,
    meal_type: str,
    fallback_details: list[IngredientPortion],
    fallback_names: list[str],
) -> list[IngredientPortion]:
    if isinstance(raw, list):
        raw_details = [IngredientPortion.from_dict(item) for item in raw]
        raw_details = [detail for detail in raw_details if detail.name.strip()]
        if raw_details:
            return merge_ingredient_details(raw_details, meal_type, fallback_details)

    raw_names = _to_string_list(raw)
    if raw_names:
        return build_ingredient_details(raw_names, meal_type, fallback_details)
    if fallback_details:
        return merge_ingredient_details(list(fallback_details), meal_type, fallback_details)
    return build_ingredient_details(fallback_names, meal_type)


def _normalize_shopping_list_details(raw: Any) -> dict[str, list[IngredientPortion]]:
    if not isinstance(raw, dict):
        return {}

    normalized: dict[str, list[IngredientPortion]] = {}
    for category, items in raw.items():
        if not isinstance(items, list):
            continue
        details = [IngredientPortion.from_dict(item) for item in items]
        details = [detail for detail in details if detail.name.strip()]
        if details:
            normalized[str(category)] = details
    return normalized


def _replace_duplicate_ai_days(days: list[DayPlan], fallback_days: list[DayPlan]) -> list[DayPlan]:
    resolved_days: list[DayPlan] = []
    seen_signatures: set[tuple[Any, ...]] = set()

    for index, day in enumerate(days):
        day_signature = _day_menu_signature(day)
        if day_signature in seen_signatures and index < len(fallback_days):
            fallback_day = fallback_days[index]
            fallback_signature = _day_menu_signature(fallback_day)
            if fallback_signature not in seen_signatures:
                resolved_days.append(fallback_day)
                seen_signatures.add(fallback_signature)
                continue

        resolved_days.append(day)
        seen_signatures.add(day_signature)

    return resolved_days


def _day_payload_has_ai_content(raw_day: dict[str, Any]) -> bool:
    if not isinstance(raw_day, dict):
        return False

    for meal_key in ("breakfast", "lunch", "dinner"):
        meal_payload = raw_day.get(meal_key)
        if isinstance(meal_payload, dict) and any(
            value not in (None, "", [], {}) for value in meal_payload.values()
        ):
            return True

    return False


def _day_menu_signature(day: DayPlan) -> tuple[Any, ...]:
    return (
        _meal_menu_signature(day.breakfast),
        _meal_menu_signature(day.lunch),
        _meal_menu_signature(day.dinner),
    )


def _meal_menu_signature(meal: MealSlot) -> tuple[Any, ...]:
    return (
        meal.shared_base.strip().lower(),
        meal.person_one.title.strip().lower(),
        tuple(sorted(item.strip().lower() for item in meal.person_one.ingredients)),
        meal.person_two.title.strip().lower(),
        tuple(sorted(item.strip().lower() for item in meal.person_two.ingredients)),
    )


def _apply_strategy_targets(request: PlanningRequest, strategy: WellnessStrategy) -> PlanningRequest:
    return PlanningRequest(
        person_one=_copy_person_with_targets(request.person_one, strategy.person_one),
        person_two=_copy_person_with_targets(request.person_two, strategy.person_two),
        preferences=_copy_preferences_with_goal(request.preferences, _summarize_goal(strategy)),
    )


def _copy_person_with_targets(
    person: PersonProfile,
    person_strategy: PersonWellnessStrategy,
) -> PersonProfile:
    return PersonProfile(
        name=person.name,
        dietary_style=person.dietary_style,
        age=person.age,
        sex=person.sex,
        height_cm=person.height_cm,
        weight_kg=person.weight_kg,
        target_weight_kg=person.target_weight_kg,
        allow_protein_powder=person.allow_protein_powder,
        activity_summary=person.activity_summary,
        daily_kcal=person_strategy.daily_kcal_target,
        protein_target=person_strategy.protein_target_g,
        dislikes=list(person.dislikes),
        allergies=list(person.allergies),
    )


def _copy_preferences_with_goal(preferences: HouseholdPreferences, goal: str) -> HouseholdPreferences:
    return HouseholdPreferences(
        goal=goal,
        budget=preferences.budget,
        max_prep_minutes=preferences.max_prep_minutes,
        leftover_lunches=preferences.leftover_lunches,
        batch_days=list(preferences.batch_days),
        favorite_cuisines=list(preferences.favorite_cuisines),
        pantry_staples=list(preferences.pantry_staples),
        excluded_ingredients=list(preferences.excluded_ingredients),
        notes=preferences.notes,
    )


def _summarize_goal(strategy: WellnessStrategy) -> str:
    return (
        f"{strategy.person_one.focus} per la prima persona; "
        f"{strategy.person_two.focus} per la seconda persona"
    )
