from __future__ import annotations

from collections import defaultdict

from dietapp.models import DayPlan, IngredientPortion
from dietapp.planning.common import KEYWORD_BUCKETS, _normalize_text_token


def build_portion_label(meal_type: str) -> str:
    labels = {
        "breakfast": "1 porzione colazione",
        "lunch": "1 porzione pranzo",
        "dinner": "1 porzione cena",
    }
    return labels.get(meal_type, "1 porzione")


def build_ingredient_details(
    ingredient_names: list[str],
    meal_type: str,
    fallback_details: list[IngredientPortion] | None = None,
) -> list[IngredientPortion]:
    if ingredient_names:
        return [_hydrate_ingredient_detail(IngredientPortion(name=name), meal_type) for name in ingredient_names]

    fallback_details = fallback_details or []
    return [_hydrate_ingredient_detail(detail, meal_type) for detail in fallback_details]


def merge_ingredient_details(
    raw_details: list[IngredientPortion],
    meal_type: str,
    fallback_details: list[IngredientPortion] | None = None,
) -> list[IngredientPortion]:
    if not raw_details:
        return build_ingredient_details([], meal_type, fallback_details)

    fallback_by_name = {
        _normalize_text_token(detail.name): detail for detail in (fallback_details or []) if detail.name.strip()
    }
    merged_details: list[IngredientPortion] = []
    for raw_detail in raw_details:
        fallback_detail = fallback_by_name.get(_normalize_text_token(raw_detail.name))
        merged_detail = IngredientPortion(
            name=raw_detail.name,
            quantity=raw_detail.quantity,
            unit=raw_detail.unit,
        )
        if merged_detail.quantity is None and fallback_detail is not None:
            merged_detail.quantity = fallback_detail.quantity
        if not merged_detail.unit and fallback_detail is not None:
            merged_detail.unit = fallback_detail.unit
        merged_details.append(_hydrate_ingredient_detail(merged_detail, meal_type))
    return merged_details


def aggregate_shopping_details(days: list[DayPlan]) -> dict[str, list[IngredientPortion]]:
    aggregated: dict[tuple[str, str, str], float | None] = {}
    display_names: dict[tuple[str, str, str], str] = {}

    for day in days:
        for meal in (day.breakfast, day.lunch, day.dinner):
            for variant in (meal.person_one, meal.person_two):
                for detail in variant.ingredient_details:
                    category = bucket_ingredient(detail.name)
                    normalized_name = _normalize_text_token(detail.name)
                    key = (category, normalized_name, detail.unit)
                    display_names[key] = detail.name
                    current_quantity = aggregated.get(key)
                    if detail.quantity is None:
                        aggregated[key] = None
                    elif current_quantity is None:
                        aggregated[key] = detail.quantity
                    else:
                        aggregated[key] = round(current_quantity + detail.quantity, 1)

    grouped: dict[str, list[IngredientPortion]] = defaultdict(list)
    for (category, _normalized_name, unit), quantity in aggregated.items():
        grouped[category].append(
            IngredientPortion(
                name=display_names[(category, _normalized_name, unit)],
                quantity=quantity,
                unit=unit,
            )
        )

    return {
        category: sorted(items, key=lambda item: _normalize_text_token(item.name))
        for category, items in grouped.items()
    }


def shopping_details_to_legacy_lists(
    shopping_details: dict[str, list[IngredientPortion]],
) -> dict[str, list[str]]:
    return {
        category: [item.name for item in items]
        for category, items in shopping_details.items()
    }


def build_coherence_checks(days: list[DayPlan], max_prep_minutes: int) -> list[str]:
    checks: list[str] = []
    if len(days) != 7:
        checks.append("Il piano non contiene ancora 7 giorni completi.")

    if any(day.dinner.prep_minutes > max_prep_minutes for day in days):
        checks.append(
            f"Una o piu cene superano il target di {max_prep_minutes} minuti dichiarato nel profilo."
        )

    if any(
        not variant.ingredient_details
        for day in days
        for meal in (day.breakfast, day.lunch, day.dinner)
        for variant in (meal.person_one, meal.person_two)
    ):
        checks.append("Alcuni pasti non hanno ancora un dettaglio quantitativo completo sugli ingredienti.")

    if not checks:
        checks.append(
            "Controllo automatico: settimana completa, dettagli quantitativi presenti e piano coerente con il vincolo di prep principale."
        )

    return checks


def bucket_ingredient(ingredient: str) -> str:
    lowered = ingredient.lower()
    for category, keywords in KEYWORD_BUCKETS.items():
        if any(keyword in lowered for keyword in keywords):
            return category
    return "Extra"


def _hydrate_ingredient_detail(detail: IngredientPortion, meal_type: str) -> IngredientPortion:
    quantity = detail.quantity
    unit = detail.unit
    if quantity is None or not unit:
        inferred_quantity, inferred_unit = _infer_measure(detail.name, meal_type)
        quantity = quantity if quantity is not None else inferred_quantity
        unit = unit or inferred_unit
    return IngredientPortion(name=detail.name, quantity=quantity, unit=unit)


def _infer_measure(ingredient_name: str, meal_type: str) -> tuple[float | None, str]:
    token = _normalize_text_token(ingredient_name)

    if any(keyword in token for keyword in ("olio",)):
        return (5.0 if meal_type == "breakfast" else 10.0, "ml")
    if any(keyword in token for keyword in ("miele", "confettura", "tahina")):
        return 15.0, "g"
    if any(keyword in token for keyword in ("cannella", "paprika", "cumino", "origano", "cacao")):
        return 3.0, "g"
    if any(keyword in token for keyword in ("basilico", "prezzemolo", "rosmarino")):
        return 5.0, "g"
    if any(keyword in token for keyword in ("uova", "uovo")):
        return 2.0, "pz"
    if any(keyword in token for keyword in ("banana", "pera", "mela", "kiwi", "albicocche", "albicocca")):
        return 1.0, "pz"
    if any(keyword in token for keyword in ("limone", "lime")):
        return 0.5, "pz"
    if any(keyword in token for keyword in ("fragole", "fragola")):
        return 120.0, "g"
    if any(keyword in token for keyword in ("yogurt",)):
        return 170.0, "g"
    if any(keyword in token for keyword in ("ricotta", "mozzarella", "primo sale", "robiola", "parmigiano")):
        return (80.0 if meal_type == "breakfast" else 120.0, "g")
    if any(keyword in token for keyword in ("ceci", "lenticchie", "cannellini", "fagioli")):
        return 120.0, "g"
    if any(keyword in token for keyword in ("pollo", "tacchino", "tofu", "tonno", "halloumi", "feta")):
        return (120.0 if meal_type == "lunch" else 150.0, "g")
    if any(keyword in token for keyword in ("pasta", "riso", "farro", "orzo")):
        return (60.0 if meal_type == "breakfast" else 80.0, "g")
    if "gnocchi" in token:
        return 200.0, "g"
    if any(keyword in token for keyword in ("pane",)):
        return (80.0 if meal_type == "breakfast" else 100.0, "g")
    if "piadina" in token:
        return 1.0, "pz"
    if "gallette" in token:
        return 4.0, "pz"
    if "fette biscottate" in token:
        return 4.0, "pz"
    if any(keyword in token for keyword in ("mandorle", "noci", "nocciole", "semi")):
        return 15.0, "g"
    if any(keyword in token for keyword in ("zucchine", "patate", "carote", "bieta", "spinaci", "melanzane", "funghi", "insalata", "pomodor", "cipolla", "sedano", "piselli")):
        return 150.0, "g"
    if any(keyword in token for keyword in ("passata", "pelati", "pomodori")):
        return 200.0, "ml"

    return (100.0, "g")