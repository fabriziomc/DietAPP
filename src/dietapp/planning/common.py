from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dietapp.models import WeeklyPlan, WellnessStrategy

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
