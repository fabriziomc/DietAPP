from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from dietapp.config import AppConfig
from dietapp.defaults import BREAKFAST_TEMPLATES, DAYS, DINNER_BLUEPRINTS
from dietapp.models import (
    DayPlan,
    HouseholdPreferences,
    MealSlot,
    MealVariant,
    PersonProfile,
    PersonWellnessStrategy,
    PlanningRequest,
    WeeklyPlan,
    WellnessStrategy,
)

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


STRATEGY_SYSTEM_PROMPT = """
You are a nutrition and wellbeing planning assistant for a couple.
Return JSON only.
Use age, sex, height, weight, activity description, dietary style and constraints to infer a realistic wellbeing strategy.
Calories and protein are derived estimates, not the primary objective.
Avoid medical diagnoses, extreme calorie deficits or unrealistic prescriptions.
Do not include markdown fences.
""".strip()


PLAN_SYSTEM_PROMPT = """
You are a meal planning assistant for a couple.
Return JSON only.
Design one weekly plan with breakfast, lunch and dinner for 7 days.
The plan must follow the supplied wellbeing strategy, minimize kitchen work by reusing ingredients, batch cooking and leftovers,
and keep a shared base meal whenever possible before splitting into omnivore and vegetarian variants.
Do not include markdown fences.
""".strip()


KEYWORD_BUCKETS = {
    "Proteine": [
        "pollo",
        "tacchino",
        "tofu",
        "ceci",
        "fagioli",
        "lenticchie",
        "uova",
        "halloumi",
        "feta",
        "mozzarella",
        "scamorza",
        "parmigiano",
        "yogurt",
        "ricotta",
    ],
    "Verdure": [
        "zucchine",
        "peperoni",
        "cipolla",
        "patate",
        "spinaci",
        "carote",
        "piselli",
        "lattuga",
        "pomodor",
        "sedano",
        "lime",
        "limone",
        "mela",
        "banana",
        "pera",
        "frutti",
    ],
    "Dispensa": [
        "riso",
        "pasta",
        "tortillas",
        "avena",
        "granola",
        "pelati",
        "passata",
        "tahina",
        "latte di cocco",
        "pane",
        "cumino",
        "paprika",
        "olio",
        "origano",
        "cannella",
        "semi",
        "miele",
    ],
}


LIGHT_ACTIVITY_KEYWORDS = (
    "cammin",
    "passegg",
    "yoga",
    "pilates",
    "mobilita",
    "stretch",
)

MODERATE_ACTIVITY_KEYWORDS = (
    "corsa",
    "running",
    "palestra",
    "allen",
    "bici",
    "bicicletta",
    "nuoto",
    "padel",
    "tennis",
    "trek",
)

HIGH_ACTIVITY_KEYWORDS = (
    "crossfit",
    "maratona",
    "manuale",
    "ogni giorno",
    "intens",
    "doppia sessione",
    "calcio",
    "rugby",
)

SEDENTARY_KEYWORDS = (
    "sedent",
    "ufficio",
    "scrivania",
    "poco movimento",
    "auto",
)


@dataclass(slots=True)
class PlanResult:
    plan: WeeklyPlan
    strategy: WellnessStrategy
    source_label: str
    warning: str | None = None


@dataclass(slots=True)
class StrategyResult:
    strategy: WellnessStrategy
    source_label: str
    warning: str | None = None


@dataclass(slots=True)
class DietResult:
    plan: WeeklyPlan
    source_label: str
    warning: str | None = None


def generate_weekly_plan(request: PlanningRequest, config: AppConfig) -> PlanResult:
    strategy_result = generate_wellness_strategy(request, config)
    diet_result = generate_diet_from_strategy(request, strategy_result.strategy, config)
    source_label = _build_bundle_source_label(strategy_result.source_label, diet_result.source_label)
    warnings = [warning for warning in (strategy_result.warning, diet_result.warning) if warning]
    return PlanResult(
        plan=diet_result.plan,
        strategy=strategy_result.strategy,
        source_label=source_label,
        warning="\n\n".join(warnings) if warnings else None,
    )


def generate_wellness_strategy(request: PlanningRequest, config: AppConfig) -> StrategyResult:
    provider_name = config.get_provider_label()
    model_name = config.get_model()
    api_key = config.get_api_key()

    if api_key:
        try:
            strategy = _generate_ai_wellness_strategy(request, config)
            return StrategyResult(strategy=strategy, source_label=f"{provider_name} | {model_name}")
        except Exception as exc:
            fallback_strategy = generate_fallback_wellness_strategy(request)
            message = str(exc).strip() or "errore sconosciuto"
            return StrategyResult(
                strategy=fallback_strategy,
                source_label="Planner locale",
                warning=(
                    f"La strategia benessere tramite {provider_name} non ha risposto correttamente "
                    f"({message}). Ho usato il motore locale."
                ),
            )

    fallback_strategy = generate_fallback_wellness_strategy(request)
    return StrategyResult(strategy=fallback_strategy, source_label="Planner locale")


def generate_diet_from_strategy(
    request: PlanningRequest,
    strategy: WellnessStrategy,
    config: AppConfig,
) -> DietResult:
    provider_name = config.get_provider_label()
    model_name = config.get_model()
    api_key = config.get_api_key()
    enriched_request = _apply_strategy_targets(request, strategy)

    if api_key:
        try:
            plan = _generate_ai_plan(enriched_request, strategy, config)
            return DietResult(plan=plan, source_label=f"{provider_name} | {model_name}")
        except Exception as exc:
            fallback_plan = generate_fallback_plan(enriched_request, strategy)
            message = str(exc).strip() or "errore sconosciuto"
            return DietResult(
                plan=fallback_plan,
                source_label="Planner locale",
                warning=(
                    f"La dieta settimanale tramite {provider_name} non ha risposto correttamente "
                    f"({message}). Ho creato il piano con il motore locale."
                ),
            )

    fallback_plan = generate_fallback_plan(enriched_request, strategy)
    return DietResult(plan=fallback_plan, source_label="Planner locale")


def generate_fallback_wellness_strategy(request: PlanningRequest) -> WellnessStrategy:
    person_one_strategy = _build_local_person_strategy(request.person_one)
    person_two_strategy = _build_local_person_strategy(request.person_two)
    batch_days = ", ".join(request.preferences.batch_days) or "nessun giorno fisso"

    shared_principles = [
        "Ogni pasto principale deve avere una fonte proteica chiara e una quota abbondante di fibre.",
        "La sazieta viene costruita con verdure, legumi, cereali gestibili e proteine distribuite nella giornata.",
        "Le colazioni restano semplici e ripetibili per ridurre attrito decisionale durante la settimana.",
    ]
    kitchen_principles = [
        f"Cene entro {request.preferences.max_prep_minutes} minuti quando possibile.",
        f"Batch cooking concentrato su: {batch_days}.",
        f"Riutilizzo degli avanzi per circa {request.preferences.leftover_lunches} pranzi settimanali.",
    ]
    couple_summary = (
        f"Strategia costruita per sostenere {request.person_one.name} con un focus su {person_one_strategy.focus.lower()} "
        f"e {request.person_two.name} con un focus su {person_two_strategy.focus.lower()}, mantenendo una cucina unica, "
        f"ingredienti ricorrenti e varianti proteiche separate solo dove serve."
    )
    return WellnessStrategy(
        title="Strategia benessere personalizzata per la coppia",
        couple_summary=couple_summary,
        shared_principles=shared_principles,
        kitchen_principles=kitchen_principles,
        person_one=person_one_strategy,
        person_two=person_two_strategy,
        model_source="Planner locale",
    )


def generate_fallback_plan(
    request: PlanningRequest,
    strategy: WellnessStrategy | None = None,
) -> WeeklyPlan:
    resolved_strategy = strategy or generate_fallback_wellness_strategy(request)
    shopping_map: dict[str, set[str]] = {}
    days: list[DayPlan] = []
    prep_tasks = _build_prep_tasks(request, resolved_strategy)
    planning_notes = _build_planning_notes(request, resolved_strategy)

    leftover_indexes = {1, 3, 4, 6}
    leftover_indexes = set(sorted(leftover_indexes)[: request.preferences.leftover_lunches])

    for index, day_name in enumerate(DAYS):
        breakfast_template = BREAKFAST_TEMPLATES[index % len(BREAKFAST_TEMPLATES)]
        dinner_template = DINNER_BLUEPRINTS[index % len(DINNER_BLUEPRINTS)]

        breakfast = _make_breakfast_slot(breakfast_template, request)
        lunch = _make_lunch_slot(index, request, dinner_template, index in leftover_indexes)
        dinner = _make_dinner_slot(dinner_template, request)

        _merge_shopping(shopping_map, breakfast_template.get("shopping", {}))
        _merge_shopping(shopping_map, dinner_template.get("shopping", {}))
        _merge_shopping(shopping_map, _shopping_from_lunch(lunch))

        days.append(
            DayPlan(
                day=day_name,
                breakfast=breakfast,
                lunch=lunch,
                dinner=dinner,
            )
        )

    shopping_list = {category: sorted(items) for category, items in shopping_map.items()}
    strategy_text = _build_plan_strategy(request, resolved_strategy)
    return WeeklyPlan(
        title="Piano settimanale guidato dalla strategia benessere",
        strategy=strategy_text,
        prep_tasks=prep_tasks,
        planning_notes=planning_notes,
        shopping_list=shopping_list,
        days=days,
        model_source="Planner locale",
    )


def _generate_ai_wellness_strategy(request: PlanningRequest, config: AppConfig) -> WellnessStrategy:
    raw_strategy = _call_llm_json(config, STRATEGY_SYSTEM_PROMPT, _build_strategy_ai_prompt(request))
    return _normalize_wellness_strategy(
        raw_strategy,
        request,
        f"{config.get_provider_label()} | {config.get_model()}",
    )


def _generate_ai_plan(
    request: PlanningRequest,
    strategy: WellnessStrategy,
    config: AppConfig,
) -> WeeklyPlan:
    raw_plan = _call_llm_json(config, PLAN_SYSTEM_PROMPT, _build_plan_ai_prompt(request, strategy))
    return _normalize_ai_plan(
        raw_plan,
        request,
        strategy,
        f"{config.get_provider_label()} | {config.get_model()}",
    )


def _call_llm_json(config: AppConfig, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    if OpenAI is None:
        raise RuntimeError("pacchetto openai non installato")

    client_kwargs: dict[str, Any] = {"api_key": config.get_api_key()}
    base_url = config.get_base_url()
    if base_url:
        client_kwargs["base_url"] = base_url

    client = OpenAI(**client_kwargs)
    response = client.chat.completions.create(
        model=config.get_model(),
        temperature=0.4,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)


def _build_strategy_ai_prompt(request: PlanningRequest) -> str:
    payload = request.to_dict()
    return f"""
Analizza il seguente profilo di coppia e proponi in italiano una strategia benessere realistica.

Payload:
{json.dumps(payload, indent=2, ensure_ascii=False)}

Regole:
- Usa soprattutto eta, sesso, altezza, peso e descrizione dell'attivita fisica.
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
- Minimizza il lavoro in cucina con basi comuni, batch cooking, ingredienti ripetuti e avanzi intelligenti.
- Usa gli stessi nomi presenti nel payload per person_one e person_two.
- Mantieni le cene entro il tempo massimo richiesto quando possibile.
- Evita ingredienti esclusi, allergie e cibi non graditi.
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
    "Dispensa": ["string"],
    "Frigo": ["string"]
  }},
  "days": [
    {{
      "day": "Lunedi",
      "breakfast": {{
        "shared_base": "string",
        "person_one": {{"title": "string", "description": "string", "ingredients": ["string"], "prep_notes": "string"}},
        "person_two": {{"title": "string", "description": "string", "ingredients": ["string"], "prep_notes": "string"}},
        "prep_minutes": 10,
        "leftover_friendly": false,
        "reuse_from_previous": "string",
        "kitchen_load": "Basso"
      }},
      "lunch": {{
        "shared_base": "string",
        "person_one": {{"title": "string", "description": "string", "ingredients": ["string"], "prep_notes": "string"}},
        "person_two": {{"title": "string", "description": "string", "ingredients": ["string"], "prep_notes": "string"}},
        "prep_minutes": 10,
        "leftover_friendly": true,
        "reuse_from_previous": "string",
        "kitchen_load": "Basso"
      }},
      "dinner": {{
        "shared_base": "string",
        "person_one": {{"title": "string", "description": "string", "ingredients": ["string"], "prep_notes": "string"}},
        "person_two": {{"title": "string", "description": "string", "ingredients": ["string"], "prep_notes": "string"}},
        "prep_minutes": 25,
        "leftover_friendly": true,
        "reuse_from_previous": "string",
        "kitchen_load": "Medio"
      }}
    }}
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
    days_raw = raw_plan.get("days") if isinstance(raw_plan, dict) else []
    days: list[DayPlan] = []

    if not isinstance(days_raw, list):
        days_raw = []

    for index, day_name in enumerate(DAYS):
        raw_day = days_raw[index] if index < len(days_raw) and isinstance(days_raw[index], dict) else {}
        days.append(
            DayPlan(
                day=str(raw_day.get("day") or day_name),
                breakfast=_normalize_meal_slot(raw_day.get("breakfast"), request, "Colazione condivisa"),
                lunch=_normalize_meal_slot(raw_day.get("lunch"), request, "Pranzo condiviso"),
                dinner=_normalize_meal_slot(raw_day.get("dinner"), request, "Cena condivisa"),
            )
        )

    shopping_list = _normalize_shopping_list(raw_plan.get("shopping_list"))
    if not shopping_list:
        shopping_list = _build_shopping_list_from_days(days)

    prep_tasks = _to_string_list(raw_plan.get("prep_tasks")) or _build_prep_tasks(request, strategy)
    planning_notes = _to_string_list(raw_plan.get("planning_notes")) or _build_planning_notes(request, strategy)

    return WeeklyPlan(
        title=str(raw_plan.get("title") or "Piano settimanale generato con AI"),
        strategy=str(raw_plan.get("strategy") or _build_plan_strategy(request, strategy)),
        prep_tasks=prep_tasks,
        planning_notes=planning_notes,
        shopping_list=shopping_list,
        days=days,
        model_source=model_source,
    )


def _normalize_meal_slot(raw: Any, request: PlanningRequest, fallback_base: str) -> MealSlot:
    raw = raw if isinstance(raw, dict) else {}
    shared_base = str(raw.get("shared_base") or fallback_base)
    person_one_variant = MealVariant.from_dict(
        raw.get("person_one") or raw.get(request.person_one.name),
        fallback_title=f"Versione {request.person_one.name}",
    )
    person_two_variant = MealVariant.from_dict(
        raw.get("person_two") or raw.get(request.person_two.name),
        fallback_title=f"Versione {request.person_two.name}",
    )

    return MealSlot(
        shared_base=shared_base,
        person_one=person_one_variant,
        person_two=person_two_variant,
        prep_minutes=_coerce_int(raw.get("prep_minutes"), 15),
        leftover_friendly=bool(raw.get("leftover_friendly")),
        reuse_from_previous=str(raw.get("reuse_from_previous") or ""),
        kitchen_load=str(raw.get("kitchen_load") or "Basso"),
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


def _build_local_person_strategy(person: PersonProfile) -> PersonWellnessStrategy:
    activity_factor, activity_label = _estimate_activity_factor(person.activity_summary)
    bmi = _estimate_bmi(person.weight_kg, person.height_cm)
    tdee = _estimate_tdee(person, activity_factor)
    focus, calorie_adjustment = _infer_focus_and_adjustment(bmi, activity_factor)
    daily_kcal_target = _round_to_step(max(_minimum_calories(person.sex), tdee + calorie_adjustment), 50)
    protein_multiplier = _protein_multiplier_for_focus(focus, person.dietary_style)
    reference_weight = person.weight_kg if person.weight_kg is not None else 70.0
    protein_target = _round_to_step(reference_weight * protein_multiplier, 5)

    bmi_copy = f"BMI stimato {bmi:.1f}" if bmi is not None else "composizione corporea stimata"
    rationale = (
        f"Eta, {bmi_copy} e attivita {activity_label} suggeriscono di puntare a {focus.lower()}, "
        f"usando un approccio sostenibile e pasti facili da ripetere durante la settimana."
    )
    return PersonWellnessStrategy(
        focus=focus,
        rationale=rationale,
        daily_kcal_target=int(daily_kcal_target),
        protein_target_g=int(protein_target),
        movement_guidance=_build_movement_guidance(person.activity_summary, focus),
        nutrition_guidance=_build_nutrition_guidance(person, focus),
    )


def _estimate_activity_factor(activity_summary: str) -> tuple[float, str]:
    summary = activity_summary.lower()
    if any(keyword in summary for keyword in HIGH_ACTIVITY_KEYWORDS):
        return 1.75, "alta"
    if any(keyword in summary for keyword in MODERATE_ACTIVITY_KEYWORDS):
        return 1.55, "moderata"
    if any(keyword in summary for keyword in LIGHT_ACTIVITY_KEYWORDS):
        return 1.375, "leggera"
    if any(keyword in summary for keyword in SEDENTARY_KEYWORDS):
        return 1.2, "bassa"
    if summary.strip():
        return 1.4, "intermedia"
    return 1.3, "non specificata"


def _estimate_bmi(weight_kg: float | None, height_cm: int | None) -> float | None:
    if not weight_kg or not height_cm:
        return None
    if height_cm <= 0:
        return None
    height_m = height_cm / 100
    return weight_kg / (height_m * height_m)


def _estimate_tdee(person: PersonProfile, activity_factor: float) -> float:
    weight_kg = person.weight_kg if person.weight_kg is not None else 70.0
    height_cm = person.height_cm if person.height_cm is not None else 170
    age = person.age if person.age is not None else 35

    sex_value = person.sex.strip().lower()
    if sex_value == "uomo":
        sex_offset = 5
    elif sex_value == "donna":
        sex_offset = -161
    else:
        sex_offset = -78

    bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + sex_offset
    return bmr * activity_factor


def _infer_focus_and_adjustment(bmi: float | None, activity_factor: float) -> tuple[str, int]:
    if bmi is not None and bmi >= 30:
        return "Dimagrimento graduale e alta sazieta", -400
    if bmi is not None and bmi >= 25:
        if activity_factor >= 1.55:
            return "Ricomposizione corporea e tono muscolare", -200
        return "Dimagrimento leggero e ricomposizione", -300
    if bmi is not None and bmi < 21 and activity_factor >= 1.5:
        return "Energia e costruzione muscolare leggera", 200
    if activity_factor >= 1.6:
        return "Supporto a performance e tono muscolare", 100
    return "Mantenimento e tono muscolare", 0


def _protein_multiplier_for_focus(focus: str, dietary_style: str) -> float:
    lowered_focus = focus.lower()
    multiplier = 1.5
    if "dimagrimento" in lowered_focus:
        multiplier = 1.8
    elif "ricomposizione" in lowered_focus or "tono" in lowered_focus:
        multiplier = 1.7
    elif "muscolare" in lowered_focus or "performance" in lowered_focus:
        multiplier = 1.8

    if dietary_style.strip().lower() == "vegetariano":
        multiplier += 0.1
    return multiplier


def _minimum_calories(sex: str) -> int:
    normalized = sex.strip().lower()
    if normalized == "uomo":
        return 1600
    if normalized == "donna":
        return 1300
    return 1450


def _build_movement_guidance(activity_summary: str, focus: str) -> str:
    lowered_activity = activity_summary.lower()
    lowered_focus = focus.lower()

    if "dimagrimento" in lowered_focus and any(keyword in lowered_activity for keyword in SEDENTARY_KEYWORDS):
        return "Mantieni i pasti sazianti e prova ad aggiungere camminate quotidiane o 2-3 sessioni leggere di forza."
    if "performance" in lowered_focus or "muscolare" in lowered_focus:
        return "Distribuisci bene i pasti nei giorni di allenamento e cura recupero, sonno e idratazione."
    if any(keyword in lowered_activity for keyword in LIGHT_ACTIVITY_KEYWORDS):
        return "L'attivita descritta e gia utile: costruisci regolarita nei pasti e una buona routine di recupero."
    return "Tieni una routine motoria regolare e usa il piano alimentare per sostenere energia, recupero e continuita."


def _build_nutrition_guidance(person: PersonProfile, focus: str) -> list[str]:
    guidance = [
        "Mantieni una fonte proteica in colazione, pranzo e cena per dare struttura alla giornata.",
        "Concentra fibre e verdure soprattutto a pranzo e cena per migliorare sazieta e qualita complessiva.",
    ]

    lowered_focus = focus.lower()
    if "dimagrimento" in lowered_focus:
        guidance.append("Usa pasti voluminosi, condimenti misurati e snack facili da controllare, evitando deficit estremi.")
    elif "muscolare" in lowered_focus or "performance" in lowered_focus:
        guidance.append("Inserisci carboidrati gestibili intorno agli allenamenti e una quota proteica stabile nel post-workout.")
    else:
        guidance.append("Lavora su regolarita, porzioni coerenti e rotazione semplice delle stesse basi durante la settimana.")

    if person.dietary_style.strip().lower() == "vegetariano":
        guidance.append("Distribuisci bene legumi, tofu, uova e latticini per mantenere costante la quota proteica vegetariana.")
    else:
        guidance.append("Alterna carni magre, uova, latticini e legumi per non dipendere sempre dalla stessa fonte proteica.")

    return guidance


def _make_breakfast_slot(template: dict[str, Any], request: PlanningRequest) -> MealSlot:
    person_one_title = _variant_title_for_style(template, request.person_one.dietary_style)
    person_two_title = _variant_title_for_style(template, request.person_two.dietary_style)

    return MealSlot(
        shared_base=template["shared_base"],
        person_one=MealVariant(
            title=person_one_title,
            description=template["description"],
            ingredients=list(template["ingredients"]),
            prep_notes=template["prep_notes"],
        ),
        person_two=MealVariant(
            title=person_two_title,
            description=template["description"],
            ingredients=list(template["ingredients"]),
            prep_notes=template["prep_notes"],
        ),
        prep_minutes=8,
        leftover_friendly=False,
        reuse_from_previous="Ruota 2-3 basi per evitare decision fatigue la mattina.",
        kitchen_load="Molto basso",
    )


def _make_lunch_slot(
    index: int,
    request: PlanningRequest,
    dinner_template: dict[str, Any],
    use_leftovers: bool,
) -> MealSlot:
    if use_leftovers:
        return MealSlot(
            shared_base=f"Lunch box con base avanzata da {dinner_template['name'].lower()}",
            person_one=MealVariant(
                title=f"Leftover box {request.person_one.dietary_style.lower()}",
                description="Pranzo costruito sugli avanzi della cena per abbattere tempi e sprechi.",
                ingredients=_variant_for_person(dinner_template, request.person_one.dietary_style)["ingredients"],
                prep_notes="Porziona la sera stessa in contenitore ermetico.",
            ),
            person_two=MealVariant(
                title=f"Leftover box {request.person_two.dietary_style.lower()}",
                description="Stessa base con variante proteica gia pronta dal giorno prima.",
                ingredients=_variant_for_person(dinner_template, request.person_two.dietary_style)["ingredients"],
                prep_notes="Aggiungi foglie fresche o yogurt solo al momento.",
            ),
            prep_minutes=6,
            leftover_friendly=True,
            reuse_from_previous=dinner_template["reuse_from_previous"],
            kitchen_load="Molto basso",
        )

    lunch_shared_base = "Bowl fredda ad alta sazieta con cereale, ortaggi croccanti e dressing rapido"
    pantry_seed = request.preferences.pantry_staples[:3] or ["riso", "farro", "legumi"]
    person_one_title = "Bowl proteica con uova e dressing allo yogurt"
    person_two_title = "Bowl proteica con ceci e feta"
    if index % 2 == 1:
        lunch_shared_base = "Piadina ripiena con verdure, salsa cremosa e frutta di fianco"
        person_one_title = "Wrap con hummus, uova e insalata"
        person_two_title = "Wrap con hummus, feta e insalata"

    ingredients = pantry_seed + ["verdure crude", "salsa yogurt", "frutta"]
    return MealSlot(
        shared_base=lunch_shared_base,
        person_one=MealVariant(
            title=person_one_title,
            description="Pranzo rapido da assemblare in meno di 10 minuti.",
            ingredients=ingredients + ["uova sode"],
            prep_notes="Usa componenti gia porzionati in frigo.",
        ),
        person_two=MealVariant(
            title=person_two_title,
            description="Versione vegetariana con stesso assetto e stessi contorni.",
            ingredients=ingredients + ["ceci", "feta"],
            prep_notes="Prepara 2 lunch box in parallelo quando fai batch cooking.",
        ),
        prep_minutes=10,
        leftover_friendly=False,
        reuse_from_previous="Slot flessibile per smaltire verdure crude, salse e cereali della settimana.",
        kitchen_load="Basso",
    )


def _make_dinner_slot(template: dict[str, Any], request: PlanningRequest) -> MealSlot:
    return MealSlot(
        shared_base=template["shared_base"],
        person_one=_meal_variant_from_template(_variant_for_person(template, request.person_one.dietary_style)),
        person_two=_meal_variant_from_template(_variant_for_person(template, request.person_two.dietary_style)),
        prep_minutes=min(int(template["prep_minutes"]), request.preferences.max_prep_minutes),
        leftover_friendly=bool(template["leftover_friendly"]),
        reuse_from_previous=str(template["reuse_from_previous"]),
        kitchen_load=str(template["kitchen_load"]),
    )


def _meal_variant_from_template(raw: dict[str, Any]) -> MealVariant:
    return MealVariant(
        title=raw["title"],
        description=raw["description"],
        ingredients=list(raw["ingredients"]),
        prep_notes=raw["prep_notes"],
    )


def _variant_for_person(template: dict[str, Any], dietary_style: str) -> dict[str, Any]:
    if dietary_style.strip().lower() == "vegetariano":
        return template["vegetarian"]
    return template["omnivore"]


def _variant_title_for_style(template: dict[str, Any], dietary_style: str) -> str:
    if dietary_style.strip().lower() == "vegetariano":
        return template["vegetarian_title"]
    return template["omnivore_title"]


def _merge_shopping(shopping_map: dict[str, set[str]], raw_shopping: dict[str, list[str]]) -> None:
    for category, items in raw_shopping.items():
        shopping_map.setdefault(category, set()).update(items)


def _shopping_from_lunch(lunch: MealSlot) -> dict[str, list[str]]:
    shopping: dict[str, list[str]] = {}
    for ingredient in lunch.person_one.ingredients + lunch.person_two.ingredients:
        category = _bucket_ingredient(ingredient)
        shopping.setdefault(category, []).append(ingredient)
    return shopping


def _bucket_ingredient(ingredient: str) -> str:
    lowered = ingredient.lower()
    for category, keywords in KEYWORD_BUCKETS.items():
        if any(keyword in lowered for keyword in keywords):
            return category
    return "Extra"


def _build_shopping_list_from_days(days: list[DayPlan]) -> dict[str, list[str]]:
    shopping_map: dict[str, set[str]] = {}
    for day in days:
        for slot in (day.breakfast, day.lunch, day.dinner):
            ingredients = slot.person_one.ingredients + slot.person_two.ingredients
            for ingredient in ingredients:
                category = _bucket_ingredient(ingredient)
                shopping_map.setdefault(category, set()).add(ingredient)
    return {category: sorted(items) for category, items in shopping_map.items()}


def _normalize_shopping_list(raw: Any) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        return {}
    cleaned: dict[str, list[str]] = {}
    for category, items in raw.items():
        cleaned_items = _to_string_list(items)
        if cleaned_items:
            cleaned[str(category)] = cleaned_items
    return cleaned


def _build_plan_strategy(request: PlanningRequest, strategy: WellnessStrategy) -> str:
    batch_days = ", ".join(request.preferences.batch_days) or "nessun giorno fisso"
    favorite_cuisines = ", ".join(request.preferences.favorite_cuisines) or "stile bilanciato"
    return (
        f"{strategy.couple_summary} In cucina la settimana privilegia basi condivise, due momenti di prep ({batch_days}), "
        f"cene entro {request.preferences.max_prep_minutes} minuti e sapori ispirati a {favorite_cuisines}."
    )


def _build_prep_tasks(request: PlanningRequest, strategy: WellnessStrategy) -> list[str]:
    prep_days = ", ".join(request.preferences.batch_days) or "Domenica"
    return [
        f"Sul blocco di prep ({prep_days}) cuoci una teglia grande di verdure miste e una base di cereali.",
        f"Prepara componenti proteici coerenti con i focus: {request.person_one.name} -> {strategy.person_one.focus.lower()}, {request.person_two.name} -> {strategy.person_two.focus.lower()}.",
        "Lava e porziona verdure crude, frutta e topping per le colazioni e i lunch box.",
        "Tieni pronta almeno una salsa fresca e un dressing stabile per velocizzare i pasti principali.",
        "Porziona subito gli avanzi della cena nei contenitori destinati ai pranzi del giorno dopo.",
    ]


def _build_planning_notes(request: PlanningRequest, strategy: WellnessStrategy) -> list[str]:
    notes = [
        f"{request.person_one.name}: {strategy.person_one.focus} | target stimato {strategy.person_one.daily_kcal_target} kcal e {strategy.person_one.protein_target_g} g proteine.",
        f"{request.person_two.name}: {strategy.person_two.focus} | target stimato {strategy.person_two.daily_kcal_target} kcal e {strategy.person_two.protein_target_g} g proteine.",
        f"Budget impostato: {request.preferences.budget}.",
        "Le cene sono costruite per condividere contorni, dressing e basi amidacee senza duplicare il lavoro.",
    ]
    if request.preferences.excluded_ingredients:
        notes.append(
            "Ingredienti esclusi monitorati: " + ", ".join(request.preferences.excluded_ingredients) + "."
        )
    if request.preferences.notes:
        notes.append(f"Nota famiglia: {request.preferences.notes}")
    return notes


def _build_bundle_source_label(strategy_source: str, plan_source: str) -> str:
    if strategy_source == plan_source:
        return strategy_source
    return f"Strategia {strategy_source} | Piano {plan_source}"


def _to_string_list(raw: Any) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return [str(raw).strip()]


def _coerce_int(raw: Any, default: int) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _coerce_optional_int(raw: Any, default: int | None) -> int | None:
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _round_to_step(value: float, step: int) -> int:
    return int(step * round(float(value) / step))