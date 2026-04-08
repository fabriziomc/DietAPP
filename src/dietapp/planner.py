from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from typing import Any

from dietapp.config import AppConfig
from dietapp.defaults import BREAKFAST_TEMPLATES, DAYS, DINNER_BLUEPRINTS, LUNCH_BLUEPRINTS
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
Use recognizable Italian home-style recipes and Italian ingredient combinations unless an explicit constraint prevents it.
The plan must follow the supplied wellbeing strategy, minimize kitchen work by reusing ingredients, batch cooking and leftovers,
and keep a shared base meal whenever possible before splitting into omnivore and vegetarian variants.
Do not include markdown fences.
""".strip()


AI_STRATEGY_MAX_TOKENS = 2500
AI_PLAN_MAX_TOKENS = 7000


KEYWORD_BUCKETS = {
    "Proteine": [
        "pollo",
        "tacchino",
        "tofu",
        "ceci",
        "fagioli",
        "lenticchie",
        "cannellini",
        "tonno",
        "uova",
        "halloumi",
        "feta",
        "mozzarella",
        "scamorza",
        "parmigiano",
        "yogurt",
        "ricotta",
        "robiola",
        "primo sale",
    ],
    "Supplementi": [
        "proteine in polvere",
        "proteine whey",
        "whey",
        "proteine vegetali",
    ],
    "Verdure": [
        "zucchine",
        "peperoni",
        "cipolla",
        "patate",
        "spinaci",
        "bieta",
        "carote",
        "piselli",
        "lattuga",
        "pomodor",
        "sedano",
        "lime",
        "limone",
        "melanzane",
        "funghi",
        "basilico",
        "prezzemolo",
        "mela",
        "banana",
        "pera",
        "kiwi",
        "albicoc",
        "fragol",
        "frutti",
    ],
    "Dispensa": [
        "riso",
        "pasta",
        "tortillas",
        "avena",
        "granola",
        "farro",
        "orzo",
        "gnocchi",
        "pelati",
        "passata",
        "tahina",
        "latte di cocco",
        "pane",
        "piadina",
        "fette biscottate",
        "cumino",
        "paprika",
        "olio",
        "origano",
        "cannella",
        "semi",
        "miele",
        "cacao",
        "confettura",
    ],
}


BUDGET_LEVELS = {"Essenziale": 0, "Bilanciato": 1, "Premium": 2}

BLOCKED_INGREDIENT_ALIASES = {
    "frutta secca": ["mandorle", "noci", "nocciole"],
    "frutta a guscio": ["mandorle", "noci", "nocciole"],
    "latticini": ["ricotta", "mozzarella", "parmigiano", "yogurt", "robiola", "primo sale"],
    "latte": ["ricotta", "mozzarella", "parmigiano", "yogurt", "robiola", "primo sale"],
    "lattosio": ["ricotta", "mozzarella", "parmigiano", "yogurt", "robiola", "primo sale"],
    "legumi": ["ceci", "lenticchie", "cannellini", "fagioli"],
    "uova": ["uova", "frittata", "tortino"],
    "glutine": ["pasta", "pane", "farro", "orzo", "piadina", "gnocchi", "fette biscottate"],
    "carne": ["pollo", "tacchino", "ragu di tacchino"],
    "pesce": ["tonno"],
}

INGREDIENT_BUDGET_HINTS = {
    "uova sode": "Essenziale",
    "uova": "Essenziale",
    "ceci": "Essenziale",
    "cannellini": "Essenziale",
    "tonno al naturale": "Bilanciato",
    "ricotta": "Bilanciato",
    "primo sale": "Bilanciato",
    "tacchino arrosto": "Bilanciato",
    "pollo arrosto": "Bilanciato",
    "mozzarella": "Premium",
    "robiola": "Premium",
    "ricotta salata": "Premium",
    "pollo alla piastra": "Premium",
}

INGREDIENT_SUBSTITUTIONS = {
    "petto di pollo": ["uova", "ceci", "cannellini"],
    "pollo alla piastra": ["uova sode", "ceci", "cannellini"],
    "pollo arrosto": ["uova sode", "ceci", "cannellini"],
    "pollo": ["uova", "ceci", "cannellini"],
    "macinato di tacchino": ["lenticchie", "cannellini", "uova"],
    "tacchino arrosto": ["uova sode", "ceci", "cannellini"],
    "tacchino": ["uova", "lenticchie", "cannellini"],
    "ragu di tacchino": ["ragu di lenticchie", "cannellini al pomodoro"],
    "tonno al naturale": ["uova sode", "ceci", "cannellini"],
    "uova sode": ["ceci", "cannellini", "primo sale"],
    "uova": ["ceci", "cannellini", "primo sale"],
    "ricotta salata": ["primo sale", "ceci al basilico", "crema di semi di girasole"],
    "ricotta": ["yogurt di soia", "crema di semi di girasole", "cannellini al limone"],
    "yogurt greco": ["yogurt di soia", "crema di semi di girasole"],
    "mozzarella": ["primo sale", "ceci al basilico", "cannellini al basilico"],
    "parmigiano": ["pangrattato alle erbe", "semi di zucca"],
    "primo sale": ["ricotta", "ceci al basilico", "crema di semi di girasole"],
    "robiola": ["ricotta", "crema di semi di girasole", "cannellini al limone"],
    "mandorle": ["semi di zucca", "semi di girasole"],
    "noci": ["semi di zucca", "semi di girasole"],
    "nocciole": ["semi di zucca", "semi di girasole"],
    "spinaci": ["bieta", "zucchine grigliate"],
    "bieta": ["zucchine grigliate", "carote"],
    "melanzane grigliate": ["zucchine grigliate", "funghi"],
    "funghi": ["zucchine grigliate", "carote"],
    "ceci": ["cannellini", "uova sode", "primo sale"],
    "cannellini": ["ceci", "uova sode", "primo sale"],
    "lenticchie": ["cannellini", "uova", "primo sale"],
    "pane integrale": ["gallette di riso", "polenta grigliata"],
    "pane casereccio": ["gallette di riso", "polenta grigliata"],
    "fette biscottate integrali": ["gallette di riso", "yogurt di soia con frutta"],
    "piadina integrale": ["gallette di riso salate", "riso"],
    "pasta corta": ["riso", "patate al forno"],
    "pasta": ["riso", "patate al forno"],
    "gnocchi": ["riso", "patate al forno"],
    "farro": ["riso", "patate lesse"],
    "orzo": ["riso", "patate lesse"],
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

WEIGHT_GOAL_TOLERANCE_KG = 0.5


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


@dataclass(slots=True)
class ProviderFailure:
    source_label: str
    message: str


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
    failures: list[ProviderFailure] = []
    for provider in config.get_provider_attempt_order():
        try:
            strategy = _generate_ai_wellness_strategy(request, config, provider)
            source_label = _build_provider_source_label(config, provider)
            return StrategyResult(
                strategy=strategy,
                source_label=source_label,
                warning=_build_provider_recovery_warning(
                    "Strategia benessere",
                    failures,
                    source_label,
                ),
            )
        except Exception as exc:
            failures.append(_build_provider_failure(exc, config, provider))

    fallback_strategy = generate_fallback_wellness_strategy(request)
    return StrategyResult(
        strategy=fallback_strategy,
        source_label="Planner locale",
        warning=_build_local_provider_warning(
            "Strategia benessere",
            failures,
            "Ho usato il motore locale.",
        ),
    )


def generate_diet_from_strategy(
    request: PlanningRequest,
    strategy: WellnessStrategy,
    config: AppConfig,
) -> DietResult:
    enriched_request = _apply_strategy_targets(request, strategy)
    failures: list[ProviderFailure] = []
    for provider in config.get_provider_attempt_order():
        try:
            plan = _generate_ai_plan(enriched_request, strategy, config, provider)
            source_label = _build_provider_source_label(config, provider)
            return DietResult(
                plan=plan,
                source_label=source_label,
                warning=_build_provider_recovery_warning(
                    "Dieta settimanale",
                    failures,
                    source_label,
                ),
            )
        except Exception as exc:
            failures.append(_build_provider_failure(exc, config, provider))

    fallback_plan = generate_fallback_plan(enriched_request, strategy)
    return DietResult(
        plan=fallback_plan,
        source_label="Planner locale",
        warning=_build_local_provider_warning(
            "Dieta settimanale",
            failures,
            "Ho creato il piano con il motore locale.",
        ),
    )


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
    substitution_notes: list[str] = []
    blocked_terms = _collect_blocked_terms(request)
    cuisine_preferences = _effective_cuisine_preferences(request)
    budget_label = _normalize_budget_label(request.preferences.budget)

    breakfast_templates = _prioritize_templates(
        BREAKFAST_TEMPLATES,
        request,
        blocked_terms,
        cuisine_preferences,
        budget_label,
    )
    lunch_blueprints = _prioritize_templates(
        LUNCH_BLUEPRINTS,
        request,
        blocked_terms,
        cuisine_preferences,
        budget_label,
    )
    dinner_templates = _prioritize_templates(
        DINNER_BLUEPRINTS,
        request,
        blocked_terms,
        cuisine_preferences,
        budget_label,
    )

    leftover_indexes = {1, 3, 4, 6}
    leftover_indexes = set(sorted(leftover_indexes)[: request.preferences.leftover_lunches])

    for index, day_name in enumerate(DAYS):
        breakfast_template = breakfast_templates[index % len(breakfast_templates)]
        dinner_template = dinner_templates[index % len(dinner_templates)]
        leftover_template = dinner_templates[(index - 1) % len(dinner_templates)]
        lunch_blueprint = lunch_blueprints[index % len(lunch_blueprints)]

        breakfast = _make_breakfast_slot(breakfast_template, request)
        lunch = _make_lunch_slot(
            index,
            request,
            leftover_template,
            lunch_blueprint,
            blocked_terms,
            index in leftover_indexes,
        )
        dinner = _make_dinner_slot(dinner_template, request)

        _collect_template_substitution_note(substitution_notes, breakfast_template)
        _collect_template_substitution_note(substitution_notes, lunch_blueprint)
        _collect_template_substitution_note(substitution_notes, dinner_template)

        _merge_shopping(shopping_map, breakfast_template.get("shopping", {}))
        _merge_shopping(shopping_map, dinner_template.get("shopping", {}))
        _merge_shopping(shopping_map, _shopping_from_lunch(lunch))

        days.append(
            DayPlan(
                day=day_name,
                breakfast=breakfast,
                lunch=lunch,
                dinner=dinner,
                source="Fallback",
            )
        )

    shopping_list = {category: sorted(items) for category, items in shopping_map.items()}
    _apply_protein_powder_support(request, resolved_strategy, shopping_list, prep_tasks, planning_notes)
    strategy_text = _build_plan_strategy(request, resolved_strategy)
    if substitution_notes:
        planning_notes.append(
            "Sostituzioni automatiche attivate per rispettare i vincoli piu stretti: "
            + "; ".join(substitution_notes[:4])
            + "."
        )
    return WeeklyPlan(
        title="Piano settimanale guidato dalla strategia benessere",
        strategy=strategy_text,
        prep_tasks=prep_tasks,
        planning_notes=planning_notes,
        shopping_list=shopping_list,
        days=days,
        model_source="Planner locale",
    )


def _generate_ai_wellness_strategy(
    request: PlanningRequest,
    config: AppConfig,
    provider: str | None = None,
) -> WellnessStrategy:
    raw_strategy = _call_llm_json(
        config,
        STRATEGY_SYSTEM_PROMPT,
        _build_strategy_ai_prompt(request),
        max_tokens=AI_STRATEGY_MAX_TOKENS,
        provider=provider,
    )
    return _normalize_wellness_strategy(
        raw_strategy,
        request,
        _build_provider_source_label(config, provider),
    )


def _generate_ai_plan(
    request: PlanningRequest,
    strategy: WellnessStrategy,
    config: AppConfig,
    provider: str | None = None,
) -> WeeklyPlan:
    raw_plan = _call_llm_json(
        config,
        PLAN_SYSTEM_PROMPT,
        _build_plan_ai_prompt(request, strategy),
        max_tokens=AI_PLAN_MAX_TOKENS,
        provider=provider,
    )
    return _normalize_ai_plan(
        raw_plan,
        request,
        strategy,
        _build_provider_source_label(config, provider),
    )


def _call_llm_json(
    config: AppConfig,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    if OpenAI is None:
        raise RuntimeError("pacchetto openai non installato")

    client_kwargs: dict[str, Any] = {"api_key": config.get_api_key(provider)}
    base_url = config.get_base_url(provider)
    if base_url:
        client_kwargs["base_url"] = base_url
    default_headers = config.get_default_headers(provider)
    if default_headers:
        client_kwargs["default_headers"] = default_headers

    client = OpenAI(**client_kwargs)
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
        request_kwargs["models"] = list(model_fallbacks)
        request_kwargs["route"] = "fallback"

    response = client.chat.completions.create(
        **request_kwargs,
    )
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
                breakfast=_normalize_meal_slot(raw_day.get("breakfast"), request, fallback_day.breakfast),
                lunch=_normalize_meal_slot(raw_day.get("lunch"), request, fallback_day.lunch),
                dinner=_normalize_meal_slot(raw_day.get("dinner"), request, fallback_day.dinner),
                source="AI" if has_ai_content else "Fallback",
            )
        )

    days = _replace_duplicate_ai_days(days, fallback_plan.days)

    shopping_list = _normalize_shopping_list(raw_plan.get("shopping_list"))
    if not shopping_list:
        shopping_list = fallback_plan.shopping_list

    prep_tasks = _to_string_list(raw_plan.get("prep_tasks")) or fallback_plan.prep_tasks
    planning_notes = _to_string_list(raw_plan.get("planning_notes")) or fallback_plan.planning_notes

    return WeeklyPlan(
        title=str(raw_plan.get("title") or fallback_plan.title),
        strategy=str(raw_plan.get("strategy") or fallback_plan.strategy),
        prep_tasks=prep_tasks,
        planning_notes=planning_notes,
        shopping_list=shopping_list,
        days=days,
        model_source=model_source,
    )


def _normalize_meal_slot(raw: Any, request: PlanningRequest, fallback_slot: MealSlot) -> MealSlot:
    raw = raw if isinstance(raw, dict) else {}
    shared_base = str(raw.get("shared_base") or fallback_slot.shared_base)
    person_one_variant = _normalize_meal_variant(
        raw.get("person_one") or raw.get(request.person_one.name),
        fallback_slot.person_one,
    )
    person_two_variant = _normalize_meal_variant(
        raw.get("person_two") or raw.get(request.person_two.name),
        fallback_slot.person_two,
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


def _normalize_meal_variant(raw: Any, fallback_variant: MealVariant) -> MealVariant:
    if isinstance(raw, str):
        description = raw.strip() or fallback_variant.description
        return MealVariant(
            title=fallback_variant.title,
            description=description,
            ingredients=list(fallback_variant.ingredients),
            prep_notes=fallback_variant.prep_notes,
        )

    if not isinstance(raw, dict):
        return MealVariant(
            title=fallback_variant.title,
            description=fallback_variant.description,
            ingredients=list(fallback_variant.ingredients),
            prep_notes=fallback_variant.prep_notes,
        )

    return MealVariant(
        title=str(raw.get("title") or fallback_variant.title),
        description=str(raw.get("description") or fallback_variant.description),
        ingredients=_to_string_list(raw.get("ingredients")) or list(fallback_variant.ingredients),
        prep_notes=str(raw.get("prep_notes") or fallback_variant.prep_notes),
    )


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


def _build_local_person_strategy(person: PersonProfile) -> PersonWellnessStrategy:
    activity_factor, activity_label = _estimate_activity_factor(person.activity_summary)
    bmi = _estimate_bmi(person.weight_kg, person.height_cm)
    tdee = _estimate_tdee(person, activity_factor)
    focus, calorie_adjustment = _infer_focus_and_adjustment(person, bmi, activity_factor)
    daily_kcal_target = _round_to_step(max(_minimum_calories(person.sex), tdee + calorie_adjustment), 50)
    protein_multiplier = _protein_multiplier_for_focus(focus, person.dietary_style)
    reference_weight = person.weight_kg if person.weight_kg is not None else 70.0
    protein_target = _round_to_step(reference_weight * protein_multiplier, 5)

    bmi_copy = f"BMI stimato {bmi:.1f}" if bmi is not None else "composizione corporea stimata"
    rationale_parts = []
    weight_goal_rationale = _build_weight_goal_rationale(person)
    if weight_goal_rationale:
        rationale_parts.append(weight_goal_rationale)
    rationale_parts.append(
        f"Eta, {bmi_copy} e attivita {activity_label} suggeriscono di puntare a {focus.lower()}, "
        f"usando un approccio sostenibile e pasti facili da ripetere durante la settimana."
    )
    rationale = " ".join(rationale_parts)
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


def _weight_goal_delta(person: PersonProfile) -> float | None:
    if person.weight_kg is None or person.target_weight_kg is None:
        return None
    return person.target_weight_kg - person.weight_kg


def _weight_goal_direction(person: PersonProfile) -> str:
    delta = _weight_goal_delta(person)
    if delta is None or abs(delta) < WEIGHT_GOAL_TOLERANCE_KG:
        return "maintain"
    return "gain" if delta > 0 else "lose"


def _format_weight_label(value: float | None) -> str:
    if value is None:
        return "n.d."
    rounded_value = round(value, 1)
    if float(rounded_value).is_integer():
        return f"{int(rounded_value)} kg"
    return f"{rounded_value:.1f} kg"


def _build_weight_goal_rationale(person: PersonProfile) -> str:
    delta = _weight_goal_delta(person)
    if delta is None or abs(delta) < WEIGHT_GOAL_TOLERANCE_KG:
        return ""
    if delta < 0:
        return (
            f"L'obiettivo peso dichiarato e scendere da {_format_weight_label(person.weight_kg)} "
            f"a {_format_weight_label(person.target_weight_kg)}."
        )
    return (
        f"L'obiettivo peso dichiarato e salire da {_format_weight_label(person.weight_kg)} "
        f"a {_format_weight_label(person.target_weight_kg)}."
    )


def _infer_focus_and_adjustment(person: PersonProfile, bmi: float | None, activity_factor: float) -> tuple[str, int]:
    goal_direction = _weight_goal_direction(person)
    goal_delta = _weight_goal_delta(person) or 0.0

    if goal_direction == "lose":
        if goal_delta <= -8:
            return "Dimagrimento graduale e alta sazieta", -450 if activity_factor < 1.5 else -350
        if goal_delta <= -3:
            return "Dimagrimento graduale e ricomposizione", -350 if activity_factor < 1.55 else -250
        return "Ricomposizione e lieve dimagrimento", -200

    if goal_direction == "gain":
        if goal_delta >= 8:
            focus = "Aumento di peso graduale e costruzione muscolare"
            calorie_adjustment = 300 if activity_factor >= 1.4 else 250
        elif goal_delta >= 3:
            focus = "Aumento di peso controllato e supporto muscolare"
            calorie_adjustment = 250 if activity_factor >= 1.5 else 200
        else:
            focus = "Recupero energetico e lieve aumento di peso"
            calorie_adjustment = 150

        if bmi is not None and bmi < 20.5:
            calorie_adjustment = max(calorie_adjustment, 250)
        return focus, calorie_adjustment

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
    elif "aumento di peso" in lowered_focus or "recupero energetico" in lowered_focus:
        multiplier = 1.6

    if dietary_style.strip().lower() == "vegetariano":
        multiplier += 0.1
    return multiplier


def _protein_powder_product(person: PersonProfile) -> str:
    lowered_allergies = " ".join(person.allergies).lower()
    if person.dietary_style.strip().lower() == "vegetariano" or any(
        term in lowered_allergies for term in ("lattosio", "latte", "whey")
    ):
        return "proteine vegetali in polvere"
    return "proteine whey in polvere"


def _should_recommend_protein_powder(
    person: PersonProfile,
    person_strategy: PersonWellnessStrategy,
) -> bool:
    if not person.allow_protein_powder:
        return False

    lowered_focus = person_strategy.focus.lower()
    reference_weight = person.weight_kg if person.weight_kg is not None else 70.0
    protein_target = person_strategy.protein_target_g or 0

    if any(
        term in lowered_focus
        for term in ("aumento di peso", "recupero energetico", "muscolare", "performance", "ricomposizione")
    ):
        return True
    if protein_target >= reference_weight * 1.8:
        return True
    if person.dietary_style.strip().lower() == "vegetariano" and protein_target >= reference_weight * 1.6:
        return True
    return False


def _build_protein_powder_guidance(person: PersonProfile, focus: str) -> str | None:
    if not person.allow_protein_powder:
        return None

    powder_label = _protein_powder_product(person)
    lowered_focus = focus.lower()
    if any(
        term in lowered_focus
        for term in ("aumento di peso", "recupero energetico", "muscolare", "performance", "ricomposizione")
    ):
        return (
            f"Se con i soli pasti fai fatica a raggiungere il target, puoi usare {powder_label} "
            "in modo pratico, preferibilmente a colazione o nel post-allenamento, senza superare una porzione al giorno."
        )
    return (
        f"Le {powder_label} restano opzionali: usale solo quando una giornata resta troppo bassa in proteine, "
        "senza sostituire i pasti principali."
    )


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
    if "aumento di peso" in lowered_focus or "recupero energetico" in lowered_focus:
        return "Accompagna il surplus con 2-4 sessioni di forza e cura recupero, sonno e regolarita dei pasti."
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
    elif "aumento di peso" in lowered_focus or "recupero energetico" in lowered_focus:
        guidance.append(
            "Aumenta l'energia con porzioni progressivamente piu ricche, carboidrati gestibili e uno snack strategico, senza ricorrere a pasti enormi."
        )
    elif "muscolare" in lowered_focus or "performance" in lowered_focus:
        guidance.append("Inserisci carboidrati gestibili intorno agli allenamenti e una quota proteica stabile nel post-workout.")
    else:
        guidance.append("Lavora su regolarita, porzioni coerenti e rotazione semplice delle stesse basi durante la settimana.")

    if person.dietary_style.strip().lower() == "vegetariano":
        guidance.append("Distribuisci bene legumi, tofu, uova e latticini per mantenere costante la quota proteica vegetariana.")
    else:
        guidance.append("Alterna carni magre, uova, latticini e legumi per non dipendere sempre dalla stessa fonte proteica.")

    protein_powder_guidance = _build_protein_powder_guidance(person, focus)
    if protein_powder_guidance:
        guidance.append(protein_powder_guidance)

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
        prep_minutes=int(template.get("prep_minutes", 8)),
        leftover_friendly=False,
        reuse_from_previous="Ruota 2-3 basi per evitare decision fatigue la mattina.",
        kitchen_load="Molto basso",
    )


def _make_lunch_slot(
    index: int,
    request: PlanningRequest,
    leftover_template: dict[str, Any],
    lunch_blueprint: dict[str, Any],
    blocked_terms: set[str],
    use_leftovers: bool,
) -> MealSlot:
    if use_leftovers:
        person_one_leftover = _variant_for_person(leftover_template, request.person_one.dietary_style)
        person_two_leftover = _variant_for_person(leftover_template, request.person_two.dietary_style)
        return MealSlot(
            shared_base=f"Lunch box con base avanzata da {leftover_template['name'].lower()}",
            person_one=MealVariant(
                title=f"Lunch box da {person_one_leftover['title']}",
                description="Pranzo costruito sugli avanzi della cena per abbattere tempi e sprechi.",
                ingredients=list(person_one_leftover["ingredients"]),
                prep_notes="Porziona la sera stessa in contenitore ermetico.",
            ),
            person_two=MealVariant(
                title=f"Lunch box da {person_two_leftover['title']}",
                description="Stessa base con variante proteica gia pronta dal giorno prima.",
                ingredients=list(person_two_leftover["ingredients"]),
                prep_notes="Aggiungi foglie fresche o yogurt solo al momento.",
            ),
            prep_minutes=6,
            leftover_friendly=True,
            reuse_from_previous=leftover_template["reuse_from_previous"],
            kitchen_load="Molto basso",
        )

    grain = _select_lunch_grain(lunch_blueprint, request, blocked_terms, index)
    person_one_protein = _select_lunch_protein(
        lunch_blueprint,
        request.person_one.dietary_style,
        request.preferences.budget,
        blocked_terms,
        index,
    )
    person_two_protein = _select_lunch_protein(
        lunch_blueprint,
        request.person_two.dietary_style,
        request.preferences.budget,
        blocked_terms,
        index + 1,
    )

    person_one_title = _render_lunch_text(lunch_blueprint["title_template"], grain, person_one_protein)
    person_two_title = _render_lunch_text(lunch_blueprint["title_template"], grain, person_two_protein)
    shared_base = _render_lunch_text(lunch_blueprint["shared_base"], grain, person_one_protein)

    person_one_ingredients = _build_lunch_ingredients(lunch_blueprint, grain, person_one_protein)
    person_two_ingredients = _build_lunch_ingredients(lunch_blueprint, grain, person_two_protein)

    return MealSlot(
        shared_base=shared_base,
        person_one=MealVariant(
            title=person_one_title,
            description=_lunch_description_for_style(lunch_blueprint, request.person_one.dietary_style),
            ingredients=person_one_ingredients,
            prep_notes=str(lunch_blueprint["prep_notes"]),
        ),
        person_two=MealVariant(
            title=person_two_title,
            description=_lunch_description_for_style(lunch_blueprint, request.person_two.dietary_style),
            ingredients=person_two_ingredients,
            prep_notes=str(lunch_blueprint["prep_notes"]),
        ),
        prep_minutes=int(lunch_blueprint.get("prep_minutes", 10)),
        leftover_friendly=False,
        reuse_from_previous="Usa cereali, verdure e condimenti preparati nei giorni di batch cooking.",
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
    favorite_cuisines = ", ".join(_effective_cuisine_preferences(request)) or "stile bilanciato"
    return (
        f"{strategy.couple_summary} In cucina la settimana privilegia basi condivise, due momenti di prep ({batch_days}), "
        f"cene entro {request.preferences.max_prep_minutes} minuti e ricette italiane orientate verso {favorite_cuisines}."
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
        "Il planner locale usa ricette italiane domestiche e adatta le scelte in base a budget e cucine preferite.",
        "Le cene sono costruite per condividere contorni, dressing e basi amidacee senza duplicare il lavoro.",
    ]
    if request.preferences.excluded_ingredients:
        notes.append(
            "Ingredienti esclusi monitorati: " + ", ".join(request.preferences.excluded_ingredients) + "."
        )
    if request.preferences.notes:
        notes.append(f"Nota famiglia: {request.preferences.notes}")
    return notes


def _apply_protein_powder_support(
    request: PlanningRequest,
    strategy: WellnessStrategy,
    shopping_list: dict[str, list[str]],
    prep_tasks: list[str],
    planning_notes: list[str],
) -> None:
    supplement_items: set[str] = set()
    supported_people: list[str] = []
    people = [
        (request.person_one, strategy.person_one),
        (request.person_two, strategy.person_two),
    ]

    for person, person_strategy in people:
        if not _should_recommend_protein_powder(person, person_strategy):
            continue

        powder_label = _protein_powder_product(person)
        supplement_items.add(powder_label)
        supported_people.append(person.name)
        planning_notes.append(
            f"{person.name}: proteine in polvere abilitate. Usa 1 porzione di {powder_label} solo nei giorni di allenamento o quando colazione e post-workout non bastano a coprire il target proteico."
        )

    if not supplement_items:
        return

    existing_items = set(shopping_list.get("Supplementi", []))
    shopping_list["Supplementi"] = sorted(existing_items | supplement_items)
    prep_tasks.append(
        "Tieni gia porzionate le proteine in polvere per "
        + ", ".join(supported_people)
        + " e usale solo come supporto pratico, non come sostituto del pasto."
    )


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


def _coerce_bool(raw: Any, default: bool) -> bool:
    if raw in (None, ""):
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "si", "on"}
    return bool(raw)


def _coerce_optional_int(raw: Any, default: int | None) -> int | None:
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _round_to_step(value: float, step: int) -> int:
    return int(step * round(float(value) / step))


def _normalize_text_token(value: str) -> str:
    return " ".join(str(value).strip().lower().replace("/", " ").replace(",", " ").split())


def _normalize_budget_label(raw_budget: str) -> str:
    normalized = str(raw_budget).strip().capitalize()
    if normalized in BUDGET_LEVELS:
        return normalized
    return "Bilanciato"


def _effective_cuisine_preferences(request: PlanningRequest) -> list[str]:
    preferences = ["Italiana"]
    preferences.extend(request.preferences.favorite_cuisines)
    unique_preferences: list[str] = []
    seen: set[str] = set()
    for cuisine in preferences:
        cleaned = str(cuisine).strip()
        if not cleaned:
            continue
        token = _normalize_text_token(cleaned)
        if token in seen:
            continue
        seen.add(token)
        unique_preferences.append(cleaned)
    return unique_preferences


def _collect_blocked_terms(request: PlanningRequest) -> set[str]:
    raw_terms = list(request.preferences.excluded_ingredients)
    for person in (request.person_one, request.person_two):
        raw_terms.extend(person.dislikes)
        raw_terms.extend(person.allergies)

    blocked_terms: set[str] = set()
    for term in raw_terms:
        cleaned = _normalize_text_token(term)
        if not cleaned:
            continue
        blocked_terms.add(cleaned)
        for alias in BLOCKED_INGREDIENT_ALIASES.get(cleaned, []):
            blocked_terms.add(_normalize_text_token(alias))
    return blocked_terms


def _template_conflicts_with_terms(template: dict[str, Any], blocked_terms: set[str]) -> bool:
    if not blocked_terms:
        return False
    for text in _iter_template_texts(template):
        lowered_text = _normalize_text_token(text)
        if any(term in lowered_text for term in blocked_terms):
            return True
    return False


def _iter_template_texts(template: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for key, value in template.items():
        if str(key).startswith("_"):
            continue
        texts.extend(_flatten_text_values(value))
    return texts


def _flatten_text_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        texts: list[str] = []
        for item in value:
            texts.extend(_flatten_text_values(item))
        return texts
    if isinstance(value, dict):
        texts: list[str] = []
        for nested_value in value.values():
            texts.extend(_flatten_text_values(nested_value))
        return texts
    return [str(value)]


def _prioritize_templates(
    templates: list[dict[str, Any]],
    request: PlanningRequest,
    blocked_terms: set[str],
    cuisine_preferences: list[str],
    budget_label: str,
) -> list[dict[str, Any]]:
    compatible_templates = [
        template for template in templates if not _template_conflicts_with_terms(template, blocked_terms)
    ]
    if not compatible_templates and blocked_terms:
        compatible_templates = _adapt_templates_for_blocked_terms(templates, blocked_terms)
    if not compatible_templates:
        compatible_templates = list(templates)

    pantry_tokens = {_normalize_text_token(item) for item in request.preferences.pantry_staples}
    return sorted(
        compatible_templates,
        key=lambda template: (
            -_template_priority_score(template, request, cuisine_preferences, budget_label, pantry_tokens),
            str(template.get("name") or template.get("shared_base") or ""),
        ),
    )


def _template_priority_score(
    template: dict[str, Any],
    request: PlanningRequest,
    cuisine_preferences: list[str],
    budget_label: str,
    pantry_tokens: set[str],
) -> int:
    score = 0
    template_budget = _normalize_budget_label(str(template.get("budget_tier") or budget_label))
    score += max(0, 5 - (abs(BUDGET_LEVELS[template_budget] - BUDGET_LEVELS[budget_label]) * 2))

    template_cuisines = {
        _normalize_text_token(cuisine) for cuisine in _to_string_list(template.get("cuisines"))
    }
    for index, cuisine in enumerate(cuisine_preferences):
        if _normalize_text_token(cuisine) in template_cuisines:
            score += max(5 - index, 1) * 2
    if "italiana" in template_cuisines:
        score += 4

    prep_minutes = _coerce_int(template.get("prep_minutes"), request.preferences.max_prep_minutes)
    if prep_minutes <= request.preferences.max_prep_minutes:
        score += 3
    else:
        score -= max(1, prep_minutes - request.preferences.max_prep_minutes)

    if template.get("leftover_friendly") and request.preferences.leftover_lunches:
        score += 2

    template_tokens = {_normalize_text_token(token) for token in _iter_template_texts(template)}
    if pantry_tokens and any(token in joined_template_token for token in pantry_tokens for joined_template_token in template_tokens):
        score += 2

    if template.get("_is_substituted"):
        score -= 2

    return score


def _select_lunch_grain(
    lunch_blueprint: dict[str, Any],
    request: PlanningRequest,
    blocked_terms: set[str],
    rotation_index: int,
) -> str:
    grain_options = _to_string_list(lunch_blueprint.get("grain_options"))
    if not grain_options:
        return ""

    pantry_tokens = {_normalize_text_token(item) for item in request.preferences.pantry_staples}
    compatible_options = [
        option for option in grain_options if _normalize_text_token(option) not in blocked_terms
    ]
    if not compatible_options:
        compatible_options = list(grain_options)

    ranked_options = sorted(
        compatible_options,
        key=lambda option: (
            0 if _normalize_text_token(option) in pantry_tokens else 1,
            option,
        ),
    )
    return ranked_options[rotation_index % len(ranked_options)]


def _select_lunch_protein(
    lunch_blueprint: dict[str, Any],
    dietary_style: str,
    budget_label: str,
    blocked_terms: set[str],
    rotation_index: int,
) -> str:
    option_key = "vegetarian_options" if dietary_style.strip().lower() == "vegetariano" else "omnivore_options"
    protein_options = _to_string_list(lunch_blueprint.get(option_key))
    compatible_options = [
        option for option in protein_options if _normalize_text_token(option) not in blocked_terms
    ]
    if not compatible_options:
        compatible_options = list(protein_options)

    resolved_budget = _normalize_budget_label(budget_label)
    ranked_options = sorted(
        compatible_options,
        key=lambda option: (
            abs(
                BUDGET_LEVELS[_normalize_budget_label(INGREDIENT_BUDGET_HINTS.get(option, resolved_budget))]
                - BUDGET_LEVELS[resolved_budget]
            ),
            option,
        ),
    )
    return ranked_options[rotation_index % len(ranked_options)]


def _render_lunch_text(template_text: str, grain: str, protein: str) -> str:
    return template_text.format(grain=grain, protein=protein).replace("  ", " ").strip()


def _build_lunch_ingredients(
    lunch_blueprint: dict[str, Any],
    grain: str,
    protein: str,
) -> list[str]:
    ingredients = []
    if grain:
        ingredients.append(grain)
    ingredients.extend(_to_string_list(lunch_blueprint.get("base_ingredients")))
    if protein:
        ingredients.append(protein)
    return ingredients


def _lunch_description_for_style(lunch_blueprint: dict[str, Any], dietary_style: str) -> str:
    if dietary_style.strip().lower() == "vegetariano":
        return str(lunch_blueprint.get("vegetarian_description") or lunch_blueprint.get("omnivore_description") or "")
    return str(lunch_blueprint.get("omnivore_description") or lunch_blueprint.get("vegetarian_description") or "")


def _collect_template_substitution_note(substitution_notes: list[str], template: dict[str, Any]) -> None:
    note = str(template.get("_substitution_summary") or "").strip()
    if note and note not in substitution_notes:
        substitution_notes.append(note)


def _adapt_templates_for_blocked_terms(
    templates: list[dict[str, Any]],
    blocked_terms: set[str],
) -> list[dict[str, Any]]:
    adapted_templates: list[dict[str, Any]] = []
    for template in templates:
        adapted_template = _adapt_template_for_blocked_terms(template, blocked_terms)
        if adapted_template is not None:
            adapted_templates.append(adapted_template)
    return adapted_templates


def _adapt_template_for_blocked_terms(
    template: dict[str, Any],
    blocked_terms: set[str],
) -> dict[str, Any] | None:
    adapted_template = copy.deepcopy(template)
    applied_replacements: list[tuple[str, str]] = []
    adapted_template = _adapt_template_value(adapted_template, blocked_terms, applied_replacements)
    if _template_conflicts_with_terms(adapted_template, blocked_terms):
        return None
    if not applied_replacements:
        return None

    unique_replacements: list[tuple[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for source, target in applied_replacements:
        pair = (_normalize_text_token(source), _normalize_text_token(target))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        unique_replacements.append((source, target))

    adapted_template["_is_substituted"] = True
    adapted_template["_substitution_summary"] = ", ".join(
        f"{source} -> {target}" for source, target in unique_replacements[:3]
    )
    return adapted_template


def _adapt_template_value(
    value: Any,
    blocked_terms: set[str],
    applied_replacements: list[tuple[str, str]],
) -> Any:
    if isinstance(value, str):
        return _adapt_template_text(value, blocked_terms, applied_replacements)
    if isinstance(value, list):
        return [
            _adapt_template_value(item, blocked_terms, applied_replacements)
            for item in value
        ]
    if isinstance(value, dict):
        adapted_mapping: dict[str, Any] = {}
        for key, nested_value in value.items():
            adapted_mapping[key] = _adapt_template_value(nested_value, blocked_terms, applied_replacements)
        return adapted_mapping
    return value


def _adapt_template_text(
    text: str,
    blocked_terms: set[str],
    applied_replacements: list[tuple[str, str]],
) -> str:
    adapted_text = text
    for source_token in sorted(INGREDIENT_SUBSTITUTIONS, key=len, reverse=True):
        if not _source_token_is_blocked(source_token, blocked_terms):
            continue
        if _normalize_text_token(source_token) not in _normalize_text_token(adapted_text):
            continue
        replacement = _choose_replacement_for_token(source_token, blocked_terms)
        if not replacement:
            continue
        updated_text = _replace_case_insensitive(adapted_text, source_token, replacement)
        if updated_text != adapted_text:
            adapted_text = updated_text
            applied_replacements.append((source_token, replacement))
    return adapted_text


def _source_token_is_blocked(source_token: str, blocked_terms: set[str]) -> bool:
    normalized_source = _normalize_text_token(source_token)
    return any(
        blocked_term == normalized_source
        or blocked_term in normalized_source
        or normalized_source in blocked_term
        for blocked_term in blocked_terms
    )


def _choose_replacement_for_token(source_token: str, blocked_terms: set[str]) -> str | None:
    for replacement in INGREDIENT_SUBSTITUTIONS.get(source_token, []):
        if not _string_conflicts_with_terms(replacement, blocked_terms):
            return replacement
    return None


def _string_conflicts_with_terms(text: str, blocked_terms: set[str]) -> bool:
    normalized_text = _normalize_text_token(text)
    return any(blocked_term in normalized_text for blocked_term in blocked_terms)


def _replace_case_insensitive(text: str, source_token: str, replacement: str) -> str:
    pattern = re.compile(re.escape(source_token), re.IGNORECASE)

    def replace_match(match: re.Match[str]) -> str:
        matched_text = match.group(0)
        if matched_text[:1].isupper():
            return replacement[:1].upper() + replacement[1:]
        return replacement

    return pattern.sub(replace_match, text)