from __future__ import annotations

import json

from dietapp.formatters import plan_to_markdown
from dietapp.models import HouseholdPreferences, PersonProfile, PlanningRequest, WeeklyPlan
from dietapp.planner import (
    _normalize_ai_plan,
    generate_fallback_plan,
    generate_fallback_wellness_strategy,
)


def build_request() -> PlanningRequest:
    return PlanningRequest(
        person_one=PersonProfile(
            name="Fabrizio",
            dietary_style="Onnivoro",
            age=39,
            sex="Uomo",
            height_cm=178,
            weight_kg=82.0,
            target_weight_kg=78.0,
            activity_summary="Lavoro sedentario, 3 allenamenti in palestra a settimana e camminate.",
            dislikes=["finocchi"],
            allergies=[],
        ),
        person_two=PersonProfile(
            name="Sara",
            dietary_style="Vegetariano",
            age=35,
            sex="Donna",
            height_cm=165,
            weight_kg=63.0,
            target_weight_kg=66.0,
            activity_summary="Yoga due volte a settimana, camminate regolari e lavoro d'ufficio.",
            dislikes=["olive"],
            allergies=["frutta secca"],
        ),
        preferences=HouseholdPreferences(
            goal="",
            budget="Bilanciato",
            max_prep_minutes=30,
            leftover_lunches=3,
            batch_days=["Domenica", "Mercoledi"],
            favorite_cuisines=["Italiana", "Mediterranea"],
            pantry_staples=["Riso", "Pasta", "Legumi in barattolo"],
            excluded_ingredients=["spinaci"],
            notes="Ridurre il numero di pentole usate.",
        ),
    )


def test_fallback_plan_generates_quantified_details_and_shopping_totals() -> None:
    request = build_request()
    strategy = generate_fallback_wellness_strategy(request)
    plan = generate_fallback_plan(request, strategy)

    breakfast_variant = plan.days[0].breakfast.person_one

    assert breakfast_variant.portion_label
    assert breakfast_variant.ingredient_details
    assert all(detail.quantity is not None for detail in breakfast_variant.ingredient_details)
    assert plan.shopping_list_details
    assert any(item.quantity is not None for items in plan.shopping_list_details.values() for item in items)
    assert plan.coherence_checks


def test_ai_normalization_accepts_structured_ingredients_and_infers_missing_quantities() -> None:
    request = build_request()
    strategy = generate_fallback_wellness_strategy(request)
    raw_plan = {
        "title": "Piano AI con quantita",
        "strategy": "Strategia AI",
        "shopping_list": {
            "Proteine": [{"name": "pollo", "quantity": 300, "unit": "g"}],
        },
        "days": [
            {
                "day": "Lunedi",
                "breakfast": {
                    "shared_base": "Toast proteico",
                    "person_one": {
                        "title": "Toast",
                        "description": "Descrizione",
                        "portion_label": "1 toast",
                        "ingredients": [
                            {"name": "pane integrale", "quantity": 80, "unit": "g"},
                            {"name": "ricotta", "unit": "g"},
                        ],
                        "prep_notes": "Tosta e servi",
                    },
                    "person_two": {
                        "title": "Toast veg",
                        "description": "Descrizione",
                        "ingredients": ["pane integrale", "yogurt di soia"],
                        "prep_notes": "Tosta e servi",
                    },
                    "prep_minutes": 5,
                    "leftover_friendly": False,
                    "reuse_from_previous": "",
                    "kitchen_load": "Molto basso",
                },
                "lunch": {},
                "dinner": {},
            }
        ],
    }

    plan = _normalize_ai_plan(raw_plan, request, strategy, "Groq | test")

    first_breakfast = plan.days[0].breakfast.person_one
    assert first_breakfast.ingredient_details[0].quantity == 80
    assert first_breakfast.ingredient_details[1].quantity is not None
    assert plan.shopping_list_details["Proteine"][0].name == "pollo"
    assert plan.shopping_list_details["Proteine"][0].quantity == 300


def test_markdown_export_includes_quantities_and_checks() -> None:
    request = build_request()
    strategy = generate_fallback_wellness_strategy(request)
    plan = generate_fallback_plan(request, strategy)

    markdown = plan_to_markdown(plan, request, strategy)

    assert "## Controlli automatici" in markdown
    assert "Ingredienti Fabrizio:" in markdown
    assert "g" in markdown or "ml" in markdown or "pz" in markdown


def test_weekly_plan_roundtrips_quantity_fields() -> None:
    request = build_request()
    strategy = generate_fallback_wellness_strategy(request)
    plan = generate_fallback_plan(request, strategy)

    restored = WeeklyPlan.from_dict(json.loads(json.dumps(plan.to_dict(), ensure_ascii=False)))

    assert restored.shopping_list_details
    assert restored.days[0].breakfast.person_one.ingredient_details
    assert restored.days[0].breakfast.person_one.ingredient_details[0].name


def test_combined_edge_case_with_constraints_and_weight_goals_remains_operational() -> None:
    request = build_request()
    request.person_one.target_weight_kg = 74.0
    request.person_two.target_weight_kg = 68.0
    request.person_one.allergies = ["glutine"]
    request.preferences.excluded_ingredients.extend(["pane integrale", "ricotta"])

    strategy = generate_fallback_wellness_strategy(request)
    plan = generate_fallback_plan(request, strategy)
    rendered_meals = "\n".join(
        " ".join(
            [
                meal.shared_base,
                meal.person_one.title,
                meal.person_one.description,
                " ".join(meal.person_one.ingredients),
                meal.person_two.title,
                meal.person_two.description,
                " ".join(meal.person_two.ingredients),
            ]
        )
        for day in plan.days
        for meal in (day.breakfast, day.lunch, day.dinner)
    ).lower()

    assert "pane integrale" not in rendered_meals
    assert "ricotta" not in rendered_meals
    assert len(plan.days) == 7
    assert plan.coherence_checks
