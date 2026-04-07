from __future__ import annotations

from pathlib import Path

from dietapp.config import AppConfig
from dietapp.formatters import compute_plan_metrics, plan_to_markdown
from dietapp.models import HouseholdPreferences, PersonProfile, PlanningRequest
from dietapp.persistence import load_profile_form_values, save_profile_form_values
from dietapp.planner import (
    _normalize_ai_plan,
    generate_diet_from_strategy,
    generate_fallback_plan,
    generate_fallback_wellness_strategy,
    generate_weekly_plan,
    generate_wellness_strategy,
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
            favorite_cuisines=["Mediterranea", "Tex-Mex"],
            pantry_staples=["Riso", "Pasta", "Legumi in barattolo"],
            excluded_ingredients=["broccoli"],
            notes="Ridurre il numero di pentole usate.",
        ),
    )


def test_fallback_plan_has_full_week() -> None:
    request = build_request()
    strategy = generate_fallback_wellness_strategy(request)
    plan = generate_fallback_plan(request, strategy)

    assert len(plan.days) == 7
    assert plan.shopping_list
    assert all(day.dinner.shared_base for day in plan.days)
    assert strategy.person_one.daily_kcal_target is not None
    assert strategy.person_two.protein_target_g is not None


def test_generate_weekly_plan_uses_local_planner_without_key() -> None:
    openai_result = generate_weekly_plan(
        build_request(),
        AppConfig(ai_provider="openai", openai_api_key=None),
    )
    groq_result = generate_weekly_plan(
        build_request(),
        AppConfig(ai_provider="groq", groq_api_key=None),
    )

    assert openai_result.source_label == "Planner locale"
    assert openai_result.plan.model_source == "Planner locale"
    assert groq_result.source_label == "Planner locale"
    assert groq_result.plan.model_source == "Planner locale"


def test_strategy_and_diet_can_be_generated_in_two_steps() -> None:
    request = build_request()
    config = AppConfig(ai_provider="groq", groq_api_key=None)

    strategy_result = generate_wellness_strategy(request, config)
    diet_result = generate_diet_from_strategy(request, strategy_result.strategy, config)

    assert strategy_result.strategy.title
    assert strategy_result.source_label == "Planner locale"
    assert len(diet_result.plan.days) == 7
    assert diet_result.source_label == "Planner locale"


def test_groq_config_exposes_base_url_and_model() -> None:
    config = AppConfig(
        ai_provider="groq",
        groq_api_key="test-groq-key",
        groq_model="llama-3.3-70b-versatile",
    )

    assert config.get_provider_label() == "Groq"
    assert config.get_api_key() == "test-groq-key"
    assert config.get_model() == "llama-3.3-70b-versatile"
    assert config.get_base_url() == "https://api.groq.com/openai/v1"


def test_config_falls_back_to_available_provider_key() -> None:
    config = AppConfig(
        ai_provider="openai",
        openai_api_key=None,
        groq_api_key="test-groq-key",
        groq_model="llama-3.3-70b-versatile",
    )

    assert config.normalize_provider() == "groq"
    assert config.get_provider_label() == "Groq"
    assert config.get_model() == "llama-3.3-70b-versatile"


def test_profile_values_are_persisted_locally(tmp_path: Path) -> None:
    profile_path = tmp_path / "household_profile.json"
    save_profile_form_values(
        {
            "person_one_name": "Fabrizio",
            "person_one_style": "Onnivoro",
            "person_one_age": 39,
            "person_one_sex": "Uomo",
            "person_one_height_cm": 178,
            "person_one_weight_kg": 82.0,
            "person_one_activity": "Palestra 3 volte a settimana",
            "person_one_dislikes": "finocchi",
            "person_one_allergies": "",
            "person_two_name": "Sara",
            "person_two_style": "Vegetariano",
            "person_two_age": 35,
            "person_two_sex": "Donna",
            "person_two_height_cm": 165,
            "person_two_weight_kg": 63.0,
            "person_two_activity": "Yoga e camminate",
            "person_two_dislikes": "olive",
            "person_two_allergies": "",
            "budget": "Bilanciato",
            "max_prep_minutes": 25,
            "leftover_lunches": 4,
            "batch_days": ["Domenica"],
            "cuisines": ["Mediterranea"],
            "pantry_staples": ["Riso", "Uova"],
            "excluded_ingredients": "broccoli",
            "notes": "Batch cooking la domenica.",
        },
        profile_path,
    )

    loaded = load_profile_form_values(profile_path)

    assert loaded["person_one_name"] == "Fabrizio"
    assert loaded["person_two_name"] == "Sara"
    assert loaded["person_one_age"] == 39
    assert loaded["person_two_weight_kg"] == 63.0
    assert loaded["leftover_lunches"] == 4
    assert loaded["batch_days"] == ["Domenica"]


def test_local_wellness_strategy_derives_focus_and_targets() -> None:
    strategy = generate_fallback_wellness_strategy(build_request())

    assert strategy.title
    assert strategy.person_one.focus
    assert strategy.person_one.daily_kcal_target is not None
    assert strategy.person_one.protein_target_g is not None
    assert strategy.person_two.focus
    assert strategy.shared_principles


def test_markdown_and_metrics_are_populated() -> None:
    request = build_request()
    strategy = generate_fallback_wellness_strategy(request)
    plan = generate_fallback_plan(request, strategy)
    markdown = plan_to_markdown(plan, request, strategy)
    metrics = compute_plan_metrics(plan)

    assert "# Piano settimanale guidato dalla strategia benessere" in markdown
    assert "## Strategia benessere" in markdown
    assert metrics["average_dinner_minutes"] > 0
    assert metrics["leftover_slots"] >= 1


def test_ai_plan_normalization_fills_missing_last_day_from_fallback() -> None:
    request = build_request()
    strategy = generate_fallback_wellness_strategy(request)
    raw_plan = {
        "title": "Piano AI incompleto",
        "strategy": "Strategia AI",
        "days": [
            {
                "day": "Lunedi",
                "breakfast": {
                    "shared_base": "Base colazione",
                    "person_one": {
                        "title": "Colazione uno",
                        "description": "Descrizione uno",
                        "ingredients": ["avena"],
                        "prep_notes": "Monta tutto",
                    },
                    "person_two": {
                        "title": "Colazione due",
                        "description": "Descrizione due",
                        "ingredients": ["yogurt"],
                        "prep_notes": "Monta tutto",
                    },
                    "prep_minutes": 5,
                    "leftover_friendly": False,
                    "reuse_from_previous": "",
                    "kitchen_load": "Molto basso",
                },
                "lunch": {},
                "dinner": {},
            }
        ]
    }

    plan = _normalize_ai_plan(raw_plan, request, strategy, "Groq | test")

    assert len(plan.days) == 7
    sunday = plan.days[-1]
    assert sunday.day == "Domenica"
    assert sunday.breakfast.person_one.description != "Versione da rifinire"
    assert sunday.lunch.person_one.ingredients
    assert sunday.dinner.person_two.prep_notes
