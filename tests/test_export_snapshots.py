from __future__ import annotations

import json
from textwrap import dedent

from dietapp.formatters import plan_to_markdown
from dietapp.models import HouseholdPreferences, PersonProfile, PlanningRequest
from dietapp.planner import generate_fallback_plan, generate_fallback_wellness_strategy


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
        ),
        person_two=PersonProfile(
            name="Sara",
            dietary_style="Vegetariano",
            age=35,
            sex="Donna",
            height_cm=165,
            weight_kg=63.0,
            activity_summary="Yoga due volte a settimana, camminate regolari e lavoro d'ufficio.",
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


def test_markdown_export_snapshot() -> None:
    request = build_request()
    strategy = generate_fallback_wellness_strategy(request)
    plan = generate_fallback_plan(request, strategy)
    markdown = plan_to_markdown(plan, request, strategy)

    expected_excerpt = dedent(
        """
        # Piano settimanale guidato dalla strategia benessere

        Fonte: Planner locale
        Coppia: Fabrizio (Onnivoro) + Sara (Vegetariano)

        ## Strategia benessere
        Strategia benessere personalizzata per la coppia
        """
    ).strip()

    assert markdown.startswith(expected_excerpt)
    assert "## Lista della spesa" in markdown
    assert "## Controlli automatici" in markdown


def test_json_export_snapshot_contains_quantity_shapes() -> None:
    request = build_request()
    strategy = generate_fallback_wellness_strategy(request)
    plan = generate_fallback_plan(request, strategy)
    exported = json.loads(json.dumps(plan.to_dict(), ensure_ascii=False))

    snapshot = {
        "title": exported["title"],
        "model_source": exported["model_source"],
        "first_portion_label": exported["days"][0]["breakfast"]["person_one"]["portion_label"],
        "first_ingredient_keys": sorted(exported["days"][0]["breakfast"]["person_one"]["ingredient_details"][0].keys()),
        "shopping_detail_keys": sorted(exported["shopping_list_details"].keys()),
        "coherence_checks": exported["coherence_checks"],
    }

    assert snapshot == {
        "title": "Piano settimanale guidato dalla strategia benessere",
        "model_source": "Planner locale",
        "first_portion_label": "1 porzione colazione",
        "first_ingredient_keys": ["name", "quantity", "unit"],
        "shopping_detail_keys": snapshot["shopping_detail_keys"],
        "coherence_checks": snapshot["coherence_checks"],
    }
