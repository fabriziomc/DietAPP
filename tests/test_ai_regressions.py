from __future__ import annotations

from dietapp.models import HouseholdPreferences, PersonProfile, PlanningRequest
from dietapp.planner import _normalize_ai_plan, generate_fallback_wellness_strategy


def build_request() -> PlanningRequest:
    return PlanningRequest(
        person_one=PersonProfile(name="Fabrizio", dietary_style="Onnivoro", age=39, sex="Uomo", height_cm=178, weight_kg=82.0, activity_summary="Palestra e camminate"),
        person_two=PersonProfile(name="Sara", dietary_style="Vegetariano", age=35, sex="Donna", height_cm=165, weight_kg=63.0, activity_summary="Yoga e camminate"),
        preferences=HouseholdPreferences(
            goal="",
            budget="Bilanciato",
            max_prep_minutes=30,
            leftover_lunches=2,
            batch_days=["Domenica"],
            favorite_cuisines=["Italiana"],
            pantry_staples=["Riso"],
            excluded_ingredients=[],
            notes="",
        ),
    )


def test_ai_normalization_recovers_from_malformed_ingredient_payloads() -> None:
    request = build_request()
    strategy = generate_fallback_wellness_strategy(request)
    raw_plan = {
        "title": "Piano malformato",
        "strategy": "Strategia",
        "shopping_list": {"Proteine": [{"ingredient": "pollo"}, None, "uova"]},
        "days": [
            {
                "day": "Lunedi",
                "breakfast": {
                    "shared_base": "Colazione",
                    "person_one": {
                        "title": "Bowl",
                        "description": "Descrizione",
                        "ingredients": [{"ingredient": "yogurt greco"}, None, "avena"],
                        "prep_notes": "Mescola",
                    },
                    "person_two": {
                        "title": "Bowl due",
                        "description": "Descrizione",
                        "ingredients": [None, {"name": "banana"}],
                        "prep_notes": "Mescola",
                    },
                    "prep_minutes": 5,
                    "leftover_friendly": False,
                    "reuse_from_previous": "",
                    "kitchen_load": "Basso",
                },
                "lunch": {},
                "dinner": {},
            }
        ],
    }

    plan = _normalize_ai_plan(raw_plan, request, strategy, "Groq | test")

    assert plan.days[0].breakfast.person_one.ingredient_details
    assert all(detail.name for detail in plan.days[0].breakfast.person_one.ingredient_details)
    assert plan.shopping_list_details
    assert all(item.name for items in plan.shopping_list_details.values() for item in items)
