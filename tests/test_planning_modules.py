from __future__ import annotations

from dietapp.models import HouseholdPreferences, PersonProfile, PlanningRequest
from dietapp.planning.ai import build_plan_prompt_preview, build_strategy_prompt_preview
from dietapp.planning.fallback_plan import generate_fallback_plan
from dietapp.planning.strategy import generate_fallback_wellness_strategy


def build_request() -> PlanningRequest:
    return PlanningRequest(
        person_one=PersonProfile(
            name="Fabrizio",
            dietary_style="Onnivoro",
            age=39,
            sex="Uomo",
            height_cm=178,
            weight_kg=82.0,
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
            activity_summary="Yoga due volte a settimana, camminate regolari e lavoro d'ufficio.",
            dislikes=["olive"],
            allergies=[],
        ),
        preferences=HouseholdPreferences(
            goal="",
            budget="Bilanciato",
            max_prep_minutes=30,
            leftover_lunches=3,
            batch_days=["Domenica", "Mercoledi"],
            favorite_cuisines=["Italiana", "Mediterranea"],
            pantry_staples=["Riso", "Pasta", "Legumi in barattolo"],
            excluded_ingredients=["broccoli"],
            notes="Ridurre il numero di pentole usate.",
        ),
    )


def test_strategy_module_generates_targets() -> None:
    strategy = generate_fallback_wellness_strategy(build_request())

    assert strategy.person_one.daily_kcal_target is not None
    assert strategy.person_two.protein_target_g is not None
    assert strategy.model_source == "Planner locale"


def test_fallback_plan_module_generates_week() -> None:
    request = build_request()
    strategy = generate_fallback_wellness_strategy(request)
    plan = generate_fallback_plan(request, strategy)

    assert len(plan.days) == 7
    assert plan.model_source == "Planner locale"
    assert plan.shopping_list


def test_ai_prompt_module_builds_preview_sections() -> None:
    request = build_request()
    strategy = generate_fallback_wellness_strategy(request)

    strategy_preview = build_strategy_prompt_preview(request)
    plan_preview = build_plan_prompt_preview(request, strategy)

    assert "=== SYSTEM PROMPT ===" in strategy_preview
    assert "=== USER PROMPT ===" in strategy_preview
    assert "=== SYSTEM PROMPT ===" in plan_preview
    assert "=== USER PROMPT ===" in plan_preview
