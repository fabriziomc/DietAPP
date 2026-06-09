from __future__ import annotations

from pathlib import Path

import dietapp.planner as planner_module
import pytest
from dietapp.config import AppConfig
from dietapp.defaults import DAYS
from dietapp.formatters import compute_plan_metrics, plan_to_markdown
from dietapp.models import HouseholdPreferences, PersonProfile, PlanningRequest
from dietapp.persistence import load_profile_form_values, save_profile_form_values
from dietapp.planner import (
    _normalize_ai_plan,
    build_plan_prompt_preview,
    build_strategy_prompt_preview,
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
            favorite_cuisines=["Italiana", "Mediterranea"],
            pantry_staples=["Riso", "Pasta", "Legumi in barattolo"],
            excluded_ingredients=["broccoli"],
            notes="Ridurre il numero di pentole usate.",
        ),
    )


def build_staged_plan_skeleton() -> dict[str, object]:
    return {
        "title": "Settimana AI scalare",
        "strategy": "Rotazione leggera con basi condivise e avanzi a pranzo.",
        "prep_tasks": [
            "Cuoci due basi cereali all'inizio settimana.",
            "Prepara un taglio verdure riutilizzabile per 2 cene.",
        ],
        "planning_notes": [
            "Alterna legumi, latticini freschi e carni bianche.",
            "Usa i pranzi come scarico degli avanzi quando indicato.",
        ],
        "days": [
            {
                "day": day_name,
                "theme": f"Rotazione {index + 1}",
                "variety_guardrail": f"Non ripetere il menu completo di {day_name} negli altri giorni.",
                "breakfast": {
                    "shared_base": f"Colazione {day_name}",
                    "direction": f"Base cremosa diversa per {day_name}",
                    "prep_minutes": 5,
                    "leftover_friendly": False,
                    "reuse_from_previous": "",
                    "kitchen_load": "Molto basso",
                },
                "lunch": {
                    "shared_base": f"Pranzo {day_name}",
                    "direction": f"Pranzo rapido diverso per {day_name}",
                    "prep_minutes": 10,
                    "leftover_friendly": True,
                    "reuse_from_previous": f"Recupera componenti da {day_name} se utile.",
                    "kitchen_load": "Basso",
                },
                "dinner": {
                    "shared_base": f"Cena {day_name}",
                    "direction": f"Cena principale diversa per {day_name}",
                    "prep_minutes": 25,
                    "leftover_friendly": True,
                    "reuse_from_previous": f"Lascia una porzione utile al pranzo successivo dopo {day_name}.",
                    "kitchen_load": "Medio",
                },
            }
            for index, day_name in enumerate(DAYS)
        ],
    }


def build_staged_ai_day(day_name: str, index: int) -> dict[str, object]:
    return {
        "day": day_name,
        "breakfast": {
            "shared_base": f"Colazione completa {day_name}",
            "person_one": {
                "title": f"Bowl proteica {day_name}",
                "description": "Colazione fresca con base cremosa e frutta.",
                "ingredients": ["yogurt greco", "avena", f"frutta {index + 1}"],
                "prep_notes": "Assembla tutto in una bowl fredda.",
            },
            "person_two": {
                "title": f"Bowl vegetariana {day_name}",
                "description": "Stessa base con topping leggermente diverso.",
                "ingredients": ["yogurt", "fiocchi d'avena", f"frutta {index + 2}"],
                "prep_notes": "Completa con semi o cannella al momento.",
            },
            "prep_minutes": 5,
            "leftover_friendly": False,
            "reuse_from_previous": "",
            "kitchen_load": "Molto basso",
        },
        "lunch": {
            "shared_base": f"Pranzo completo {day_name}",
            "person_one": {
                "title": f"Insalata di riso {day_name}",
                "description": "Pranzo rapido con cereale e proteina leggera.",
                "ingredients": ["riso", "zucchine", f"proteina {index + 1}"],
                "prep_notes": "Usa cereale gia cotto per tagliare i tempi.",
            },
            "person_two": {
                "title": f"Insalata mediterranea {day_name}",
                "description": "Stessa base con variante vegetariana.",
                "ingredients": ["riso", "pomodori", f"legume {index + 1}"],
                "prep_notes": "Condisci all'ultimo per mantenere freschezza.",
            },
            "prep_minutes": 10,
            "leftover_friendly": True,
            "reuse_from_previous": f"Recupera eventuali basi cotte dal giorno {index + 1}.",
            "kitchen_load": "Basso",
        },
        "dinner": {
            "shared_base": f"Cena completa {day_name}",
            "person_one": {
                "title": f"Piatto serale onnivoro {day_name}",
                "description": "Cena italiana con base condivisa e proteina dedicata.",
                "ingredients": ["patate", "verdure miste", f"proteina cena {index + 1}"],
                "prep_notes": "Cuoci tutto in una sola teglia quando possibile.",
            },
            "person_two": {
                "title": f"Piatto serale vegetariano {day_name}",
                "description": "Stessa base con variante vegetariana coerente.",
                "ingredients": ["patate", "verdure miste", f"legume cena {index + 1}"],
                "prep_notes": "Aggiungi la componente proteica negli ultimi minuti.",
            },
            "prep_minutes": 25,
            "leftover_friendly": True,
            "reuse_from_previous": f"Conserva una porzione per il pranzo successivo a {day_name}.",
            "kitchen_load": "Medio",
        },
    }


def test_fallback_plan_has_full_week() -> None:
    request = build_request()
    strategy = generate_fallback_wellness_strategy(request)
    plan = generate_fallback_plan(request, strategy)

    assert len(plan.days) == 7
    assert plan.shopping_list
    assert all(day.dinner.shared_base for day in plan.days)
    assert all(day.source == "Fallback" for day in plan.days)
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


def test_openrouter_config_exposes_base_url_model_and_headers() -> None:
    config = AppConfig(
        ai_provider="openrouter",
        openrouter_api_key="test-openrouter-key",
        openrouter_model="google/gemma-4-31b-it:free",
        openrouter_fallback_models=(
            "meta-llama/llama-3.3-70b-instruct:free",
            "qwen/qwen3-next-80b-a3b-instruct:free",
        ),
        openrouter_site_url="https://dietapp.example",
        openrouter_app_name="DietAPP",
    )

    assert config.get_provider_label() == "OpenRouter"
    assert config.get_api_key() == "test-openrouter-key"
    assert config.get_model() == "google/gemma-4-31b-it:free"
    assert config.get_base_url() == "https://openrouter.ai/api/v1"
    assert config.get_default_headers() == {
        "HTTP-Referer": "https://dietapp.example",
        "X-OpenRouter-Title": "DietAPP",
    }
    assert config.get_model_fallbacks() == (
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
    )


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


def test_config_can_fall_back_to_openrouter_when_available() -> None:
    config = AppConfig(
        ai_provider="openai",
        openai_api_key=None,
        groq_api_key=None,
        openrouter_api_key="test-openrouter-key",
        openrouter_model="google/gemma-4-31b-it:free",
    )

    assert config.normalize_provider() == "openrouter"
    assert config.get_provider_label() == "OpenRouter"
    assert config.get_model() == "google/gemma-4-31b-it:free"


def test_openrouter_attempt_order_uses_groq_before_local() -> None:
    config = AppConfig(
        ai_provider="openrouter",
        openrouter_api_key="test-openrouter-key",
        groq_api_key="test-groq-key",
    )

    assert config.get_provider_attempt_order() == ("openrouter", "groq")


def test_openrouter_fallback_models_skip_primary_and_duplicates() -> None:
    config = AppConfig(
        ai_provider="openrouter",
        openrouter_api_key="test-openrouter-key",
        openrouter_model="google/gemma-4-31b-it:free",
        openrouter_fallback_models=(
            "google/gemma-4-31b-it:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "qwen/qwen3-next-80b-a3b-instruct:free",
        ),
    )

    assert config.get_model_fallbacks() == (
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
    )


def test_openrouter_fallback_models_are_capped_to_api_limit() -> None:
    config = AppConfig(
        ai_provider="openrouter",
        openrouter_api_key="test-openrouter-key",
        openrouter_model="google/gemma-4-31b-it:free",
        openrouter_fallback_models=(
            "meta-llama/llama-3.3-70b-instruct:free",
            "qwen/qwen3-next-80b-a3b-instruct:free",
            "openai/gpt-oss-120b:free",
            "anthropic/claude-3.5-haiku",
        ),
    )

    assert config.get_model_fallbacks() == (
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "openai/gpt-oss-120b:free",
    )


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
            "person_one_target_weight_kg": 77.5,
            "person_one_allow_protein_powder": True,
            "person_one_activity": "Palestra 3 volte a settimana",
            "person_one_dislikes": "finocchi",
            "person_one_allergies": "",
            "person_two_name": "Sara",
            "person_two_style": "Vegetariano",
            "person_two_age": 35,
            "person_two_sex": "Donna",
            "person_two_height_cm": 165,
            "person_two_weight_kg": 63.0,
            "person_two_target_weight_kg": 66.0,
            "person_two_allow_protein_powder": False,
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
    assert loaded["person_one_target_weight_kg"] == 77.5
    assert loaded["person_two_target_weight_kg"] == 66.0
    assert loaded["person_one_allow_protein_powder"] is True
    assert loaded["person_two_allow_protein_powder"] is False
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


def test_local_wellness_strategy_uses_target_weight_goal() -> None:
    baseline_strategy = generate_fallback_wellness_strategy(build_request())
    request = build_request()
    request.person_one.target_weight_kg = 75.0
    request.person_two.target_weight_kg = 68.0

    strategy = generate_fallback_wellness_strategy(request)

    assert baseline_strategy.person_one.daily_kcal_target is not None
    assert baseline_strategy.person_two.daily_kcal_target is not None
    assert strategy.person_one.daily_kcal_target is not None
    assert strategy.person_two.daily_kcal_target is not None
    assert "dimagr" in strategy.person_one.focus.lower()
    assert strategy.person_one.daily_kcal_target < baseline_strategy.person_one.daily_kcal_target
    assert "75" in strategy.person_one.rationale
    assert (
        "aumento di peso" in strategy.person_two.focus.lower()
        or "recupero energetico" in strategy.person_two.focus.lower()
    )
    assert strategy.person_two.daily_kcal_target > baseline_strategy.person_two.daily_kcal_target
    assert "68" in strategy.person_two.rationale


def test_local_strategy_can_recommend_protein_powder_when_enabled() -> None:
    request = build_request()
    request.person_one.target_weight_kg = 88.0
    request.person_one.allow_protein_powder = True

    strategy = generate_fallback_wellness_strategy(request)

    rendered_guidance = " ".join(strategy.person_one.nutrition_guidance).lower()
    assert "polvere" in rendered_guidance
    assert "whey" in rendered_guidance or "proteine" in rendered_guidance


def test_fallback_plan_adds_protein_powder_to_notes_and_shopping() -> None:
    request = build_request()
    request.person_one.target_weight_kg = 88.0
    request.person_one.allow_protein_powder = True

    strategy = generate_fallback_wellness_strategy(request)
    plan = generate_fallback_plan(request, strategy)

    assert "Supplementi" in plan.shopping_list
    assert any("proteine" in item.lower() for item in plan.shopping_list["Supplementi"])
    assert any("polvere" in note.lower() for note in plan.planning_notes)


def test_strategy_prompt_preview_contains_system_and_payload() -> None:
    preview = build_strategy_prompt_preview(build_request())

    assert "=== SYSTEM PROMPT ===" in preview
    assert "=== USER PROMPT ===" in preview
    assert "Analizza il seguente profilo di coppia" in preview
    assert '"person_one"' in preview


def test_plan_prompt_preview_contains_strategy_payload() -> None:
    request = build_request()
    strategy = generate_fallback_wellness_strategy(request)

    preview = build_plan_prompt_preview(request, strategy)

    assert "FASE 1: SKELETON SETTIMANALE" in preview
    assert "FASE 2: DETTAGLIO GIORNALIERO" in preview
    assert "Costruisci prima lo skeleton settimanale" in preview
    assert "Espandi un solo giorno della settimana" in preview
    assert "Strategia benessere approvata:" in preview
    assert strategy.title in preview
    assert '"day": "Lunedi"' in preview
    assert '"variety_guardrail": "string"' in preview
    assert '"ingredients": ["string"]' in preview


def test_call_llm_json_passes_max_tokens(monkeypatch) -> None:
    captured: dict[str, object] = {}
    captured_client_kwargs: dict[str, object] = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)

            message = type("Message", (), {"content": '{"status": "ok"}'})()
            choice = type("Choice", (), {"message": message})()
            return type("Response", (), {"choices": [choice]})()

    class FakeClient:
        def __init__(self, **kwargs):
            captured_client_kwargs.update(kwargs)
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr(planner_module, "OpenAI", FakeClient)

    payload = planner_module._call_llm_json(
        AppConfig(ai_provider="groq", groq_api_key="test-key"),
        "system",
        "user",
        max_tokens=7000,
    )

    assert payload == {"status": "ok"}
    assert captured["max_tokens"] == 7000


def test_call_llm_json_caps_max_tokens_for_groq_when_prompt_is_large(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)

            message = type("Message", (), {"content": '{"status": "ok"}'})()
            choice = type("Choice", (), {"message": message})()
            return type("Response", (), {"choices": [choice]})()

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr(planner_module, "OpenAI", FakeClient)

    payload = planner_module._call_llm_json(
        AppConfig(ai_provider="groq", groq_api_key="test-key"),
        "system",
        "x" * 20000,
        max_tokens=7000,
    )

    assert payload == {"status": "ok"}
    assert isinstance(captured["max_tokens"], int)
    assert captured["max_tokens"] < 7000


def test_call_llm_json_sets_openrouter_headers(monkeypatch) -> None:
    captured_client_kwargs: dict[str, object] = {}
    captured_request_kwargs: dict[str, object] = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured_request_kwargs.update(kwargs)
            message = type("Message", (), {"content": '{"status": "ok"}'})()
            choice = type("Choice", (), {"message": message})()
            return type("Response", (), {"choices": [choice]})()

    class FakeClient:
        def __init__(self, **kwargs):
            captured_client_kwargs.update(kwargs)
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr(planner_module, "OpenAI", FakeClient)

    payload = planner_module._call_llm_json(
        AppConfig(
            ai_provider="openrouter",
            openrouter_api_key="test-openrouter-key",
            openrouter_model="google/gemma-4-31b-it:free",
            openrouter_fallback_models=(
                "meta-llama/llama-3.3-70b-instruct:free",
                "qwen/qwen3-next-80b-a3b-instruct:free",
                "openai/gpt-oss-120b:free",
                "anthropic/claude-3.5-haiku",
            ),
            openrouter_site_url="https://dietapp.example",
            openrouter_app_name="DietAPP",
        ),
        "system",
        "user",
        max_tokens=2000,
    )

    assert payload == {"status": "ok"}
    assert captured_client_kwargs["api_key"] == "test-openrouter-key"
    assert captured_client_kwargs["base_url"] == "https://openrouter.ai/api/v1"
    assert captured_client_kwargs["default_headers"] == {
        "HTTP-Referer": "https://dietapp.example",
        "X-OpenRouter-Title": "DietAPP",
    }
    assert captured_request_kwargs["extra_body"] == {
        "models": [
            "meta-llama/llama-3.3-70b-instruct:free",
            "qwen/qwen3-next-80b-a3b-instruct:free",
            "openai/gpt-oss-120b:free",
        ],
        "route": "fallback",
    }


def test_generate_ai_plan_uses_staged_pipeline(monkeypatch) -> None:
    request = build_request()
    strategy = generate_fallback_wellness_strategy(request)
    responses = iter([build_staged_plan_skeleton(), *(build_staged_ai_day(day_name, index) for index, day_name in enumerate(DAYS))])
    prompts: list[tuple[str, str, int | None, str | None]] = []

    def fake_call(_config, system_prompt, user_prompt, max_tokens=None, provider=None):
        prompts.append((system_prompt, user_prompt, max_tokens, provider))
        return next(responses)

    monkeypatch.setattr(planner_module, "_call_llm_json", fake_call)

    plan = planner_module._generate_ai_plan(
        request,
        strategy,
        AppConfig(ai_provider="groq", groq_api_key="test-key"),
        provider="groq",
    )

    assert len(prompts) == 8
    assert all(day.source == "AI" for day in plan.days)
    assert len({day.breakfast.shared_base for day in plan.days}) == 7
    assert len({day.dinner.shared_base for day in plan.days}) == 7
    assert plan.shopping_list


def test_generate_ai_plan_recovers_fallback_days_on_second_pass(monkeypatch) -> None:
    request = build_request()
    strategy = generate_fallback_wellness_strategy(request)
    responses = iter(
        [
            build_staged_plan_skeleton(),
            build_staged_ai_day("Lunedi", 0),
            build_staged_ai_day("Martedi", 1),
            build_staged_ai_day("Mercoledi", 2),
            {},
            {},
            {},
            {},
            build_staged_ai_day("Sabato", 5),
            {},
            {},
            build_staged_ai_day("Giovedi", 3),
            build_staged_ai_day("Venerdi", 4),
            build_staged_ai_day("Domenica", 6),
        ]
    )

    def fake_call(_config, system_prompt, user_prompt, max_tokens=None, provider=None):
        return next(responses)

    monkeypatch.setattr(planner_module, "_call_llm_json", fake_call)

    plan = planner_module._generate_ai_plan(
        request,
        strategy,
        AppConfig(ai_provider="groq", groq_api_key="test-key"),
        provider="groq",
    )

    assert all(day.source == "AI" for day in plan.days)
    assert plan.days[3].day == "Giovedi"
    assert plan.days[4].day == "Venerdi"
    assert plan.days[6].day == "Domenica"


def test_generate_ai_plan_rejects_weak_staged_provider_output(monkeypatch) -> None:
    request = build_request()
    strategy = generate_fallback_wellness_strategy(request)
    responses = iter(
        [build_staged_plan_skeleton(), build_staged_ai_day("Lunedi", 0), *([{}] * 30)]
    )

    def fake_call(_config, system_prompt, user_prompt, max_tokens=None, provider=None):
        return next(responses)

    monkeypatch.setattr(planner_module, "_call_llm_json", fake_call)

    with pytest.raises(RuntimeError, match="giorni validi su 7"):
        planner_module._generate_ai_plan(
            request,
            strategy,
            AppConfig(ai_provider="groq", groq_api_key="test-key"),
            provider="groq",
        )


def test_generate_diet_from_strategy_warns_when_one_day_is_completed_locally(monkeypatch) -> None:
    request = build_request()
    strategy = generate_fallback_wellness_strategy(request)
    staged_days = [build_staged_ai_day(day_name, index) for index, day_name in enumerate(DAYS)]
    staged_days[-1] = {}
    responses = iter([build_staged_plan_skeleton(), *staged_days, {}, {}, {}])

    def fake_call(_config, system_prompt, user_prompt, max_tokens=None, provider=None):
        return next(responses)

    monkeypatch.setattr(planner_module, "_call_llm_json", fake_call)

    result = generate_diet_from_strategy(
        request,
        strategy,
        AppConfig(ai_provider="groq", groq_api_key="test-key"),
    )

    assert result.source_label == "Groq | llama-3.3-70b-versatile"
    assert result.warning is not None
    assert "6 giorni su 7" in result.warning
    assert "planner locale" in result.warning
    assert result.plan.days[-1].source == "Fallback"


def test_strategy_uses_groq_when_openrouter_provider_fails(monkeypatch) -> None:
    request = build_request()
    strategy = generate_fallback_wellness_strategy(request)
    attempted_providers: list[str | None] = []

    def fake_generate(_request, _config, provider=None):
        attempted_providers.append(provider)
        if provider == "openrouter":
            raise RuntimeError("temporarily rate-limited upstream")
        if provider == "groq":
            return strategy
        raise AssertionError("provider inatteso")

    monkeypatch.setattr(planner_module, "_generate_ai_wellness_strategy", fake_generate)

    result = generate_wellness_strategy(
        request,
        AppConfig(
            ai_provider="openrouter",
            openrouter_api_key="test-openrouter-key",
            groq_api_key="test-groq-key",
            groq_model="llama-3.3-70b-versatile",
        ),
    )

    assert attempted_providers == ["openrouter", "groq"]
    assert result.source_label == "Groq | llama-3.3-70b-versatile"
    assert result.warning is not None
    assert "OpenRouter | google/gemma-4-31b-it:free" in result.warning
    assert "Ho usato Groq | llama-3.3-70b-versatile come fallback." in result.warning


def test_diet_uses_groq_when_openrouter_provider_fails(monkeypatch) -> None:
    request = build_request()
    strategy = generate_fallback_wellness_strategy(request)
    plan = generate_fallback_plan(request, strategy)
    attempted_providers: list[str | None] = []

    def fake_generate(_request, _strategy, _config, provider=None):
        attempted_providers.append(provider)
        if provider == "openrouter":
            raise RuntimeError("temporarily rate-limited upstream")
        if provider == "groq":
            return plan
        raise AssertionError("provider inatteso")

    monkeypatch.setattr(planner_module, "_generate_ai_plan", fake_generate)

    result = generate_diet_from_strategy(
        request,
        strategy,
        AppConfig(
            ai_provider="openrouter",
            openrouter_api_key="test-openrouter-key",
            groq_api_key="test-groq-key",
            groq_model="llama-3.3-70b-versatile",
        ),
    )

    assert attempted_providers == ["openrouter", "groq"]
    assert result.source_label == "Groq | llama-3.3-70b-versatile"
    assert result.warning is not None
    assert "OpenRouter | google/gemma-4-31b-it:free" in result.warning
    assert "Ho usato Groq | llama-3.3-70b-versatile come fallback." in result.warning


def test_format_provider_exception_clarifies_openrouter_rate_limit() -> None:
    message = planner_module._format_provider_exception(
        RuntimeError(
            "Error code: 429 - {'error': {'message': 'Provider returned error', 'metadata': {'raw': 'google/gemma-4-31b-it:free is temporarily rate-limited upstream. Please retry shortly'}}}"
        ),
        AppConfig(
            ai_provider="openrouter",
            openrouter_api_key="test-openrouter-key",
            openrouter_model="google/gemma-4-31b-it:free",
            openrouter_fallback_models=("meta-llama/llama-3.3-70b-instruct:free",),
        ),
    )

    assert "temporaneamente limitato" in message
    assert "OPENROUTER_FALLBACK_MODELS" in message


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
    assert plan.days[0].source == "AI"
    sunday = plan.days[-1]
    assert sunday.day == "Domenica"
    assert sunday.source == "Fallback"
    assert sunday.breakfast.person_one.description != "Versione da rifinire"
    assert sunday.lunch.person_one.ingredients
    assert sunday.dinner.person_two.prep_notes


def test_ai_plan_normalization_replaces_duplicate_full_days_with_fallback() -> None:
    request = build_request()
    strategy = generate_fallback_wellness_strategy(request)
    repeated_day = {
        "day": "Lunedi",
        "breakfast": {
            "shared_base": "Colazione ripetuta",
            "person_one": {
                "title": "Toast uno",
                "description": "Sempre uguale",
                "ingredients": ["pane", "uova"],
                "prep_notes": "5 min",
            },
            "person_two": {
                "title": "Toast due",
                "description": "Sempre uguale",
                "ingredients": ["pane", "ricotta"],
                "prep_notes": "5 min",
            },
            "prep_minutes": 5,
            "leftover_friendly": False,
            "reuse_from_previous": "",
            "kitchen_load": "Molto basso",
        },
        "lunch": {
            "shared_base": "Pranzo ripetuto",
            "person_one": {
                "title": "Bowl uno",
                "description": "Sempre uguale",
                "ingredients": ["riso", "pollo"],
                "prep_notes": "10 min",
            },
            "person_two": {
                "title": "Bowl due",
                "description": "Sempre uguale",
                "ingredients": ["riso", "ceci"],
                "prep_notes": "10 min",
            },
            "prep_minutes": 10,
            "leftover_friendly": False,
            "reuse_from_previous": "",
            "kitchen_load": "Basso",
        },
        "dinner": {
            "shared_base": "Cena ripetuta",
            "person_one": {
                "title": "Cena uno",
                "description": "Sempre uguale",
                "ingredients": ["pasta", "pollo"],
                "prep_notes": "20 min",
            },
            "person_two": {
                "title": "Cena due",
                "description": "Sempre uguale",
                "ingredients": ["pasta", "mozzarella"],
                "prep_notes": "20 min",
            },
            "prep_minutes": 20,
            "leftover_friendly": True,
            "reuse_from_previous": "",
            "kitchen_load": "Medio",
        },
    }
    raw_plan = {
        "title": "Piano AI ripetitivo",
        "strategy": "Strategia AI",
        "days": [repeated_day.copy() for _ in range(7)],
    }

    plan = _normalize_ai_plan(raw_plan, request, strategy, "Groq | test")

    assert plan.days[0].breakfast.shared_base == "Colazione ripetuta"
    assert plan.days[0].source == "AI"
    assert plan.days[1].breakfast.shared_base != "Colazione ripetuta"
    assert plan.days[1].lunch.shared_base != "Pranzo ripetuto"
    assert plan.days[1].dinner.shared_base != "Cena ripetuta"
    assert plan.days[1].source == "Fallback"


def test_fallback_plan_excludes_blocked_ingredient_aliases() -> None:
    request = build_request()
    request.person_two.allergies = ["frutta secca"]
    request.preferences.excluded_ingredients = ["spinaci"]

    plan = generate_fallback_plan(request)
    rendered_meals = "\n".join(
        " ".join(
            [
                slot.shared_base,
                slot.person_one.title,
                slot.person_one.description,
                " ".join(slot.person_one.ingredients),
                slot.person_two.title,
                slot.person_two.description,
                " ".join(slot.person_two.ingredients),
            ]
        )
        for day in plan.days
        for slot in (day.breakfast, day.lunch, day.dinner)
    ).lower()

    assert "mandorle" not in rendered_meals
    assert "noci" not in rendered_meals
    assert "nocciole" not in rendered_meals
    assert "spinaci" not in rendered_meals


def test_fallback_plan_changes_first_dinner_with_budget() -> None:
    essential_request = build_request()
    essential_request.preferences.budget = "Essenziale"
    essential_request.preferences.favorite_cuisines = ["Tradizione regionale"]

    premium_request = build_request()
    premium_request.preferences.budget = "Premium"
    premium_request.preferences.favorite_cuisines = ["Tradizione regionale"]

    essential_plan = generate_fallback_plan(essential_request)
    premium_plan = generate_fallback_plan(premium_request)

    assert "Pasta e lenticchie" in essential_plan.days[0].dinner.shared_base
    assert "Orzotto" in premium_plan.days[0].dinner.shared_base


def test_fallback_plan_changes_first_dinner_with_cuisine_preference() -> None:
    bowl_request = build_request()
    bowl_request.preferences.favorite_cuisines = ["Bowl proteiche"]

    regional_request = build_request()
    regional_request.preferences.favorite_cuisines = ["Tradizione regionale"]

    bowl_plan = generate_fallback_plan(bowl_request)
    regional_plan = generate_fallback_plan(regional_request)

    assert "Teglia" in bowl_plan.days[0].dinner.shared_base
    assert "Pasta al forno" in regional_plan.days[0].dinner.shared_base


def test_fallback_plan_rewrites_breakfasts_when_constraints_are_too_strict() -> None:
    request = build_request()
    request.preferences.excluded_ingredients = [
        "pane integrale",
        "ricotta",
        "yogurt greco",
        "fette biscottate integrali",
        "frutta secca",
    ]

    plan = generate_fallback_plan(request)
    rendered_breakfasts = "\n".join(
        " ".join(
            [
                day.breakfast.shared_base,
                day.breakfast.person_one.title,
                day.breakfast.person_one.description,
                " ".join(day.breakfast.person_one.ingredients),
                day.breakfast.person_two.title,
                day.breakfast.person_two.description,
                " ".join(day.breakfast.person_two.ingredients),
            ]
        )
        for day in plan.days
    ).lower()

    assert "pane integrale" not in rendered_breakfasts
    assert "ricotta" not in rendered_breakfasts
    assert "yogurt greco" not in rendered_breakfasts
    assert "fette biscottate integrali" not in rendered_breakfasts
    assert "mandorle" not in rendered_breakfasts
    assert "noci" not in rendered_breakfasts
    assert "nocciole" not in rendered_breakfasts
    assert any(token in rendered_breakfasts for token in ["gallette di riso", "yogurt di soia", "semi di zucca"])
    assert any("Sostituzioni automatiche attivate" in note for note in plan.planning_notes)
