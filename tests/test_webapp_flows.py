from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from streamlit.testing.v1 import AppTest

import dietapp.webapp as webapp
from dietapp.auth import AuthSession
from dietapp.config import AppConfig
from dietapp.persistence import DEFAULT_PROFILE_VALUES, StoredPlanningState
from dietapp.planner import (
    DietResult,
    StrategyResult,
    generate_fallback_plan,
    generate_fallback_wellness_strategy,
)
from dietapp.ui.helpers import FormValues, build_request_payload

ROOT_DIR = Path(__file__).resolve().parents[1]


def _build_app() -> AppTest:
    return AppTest.from_file(str(ROOT_DIR / "app.py"))


def _button_by_label(app: AppTest, label: str):
    return next(button for button in app.button if button.label == label)


def _base_local_config() -> AppConfig:
    return AppConfig(ai_provider="openai", openai_api_key=None, supabase_url=None, supabase_anon_key=None)


def _request_from_defaults() -> Any:
    return build_request_payload(cast(FormValues, dict(DEFAULT_PROFILE_VALUES)))


def _strategy_result_for_defaults() -> StrategyResult:
    request_payload = _request_from_defaults()
    return StrategyResult(
        strategy=generate_fallback_wellness_strategy(request_payload),
        source_label="Planner locale",
        warning=None,
    )


def _diet_result_for_defaults(strategy_result: StrategyResult) -> DietResult:
    request_payload = _request_from_defaults()
    return DietResult(
        plan=generate_fallback_plan(request_payload, strategy_result.strategy),
        source_label="Planner locale",
        warning=None,
    )


def test_local_profile_save_flow_persists_values(monkeypatch) -> None:
    saved_payloads: list[dict[str, Any]] = []

    monkeypatch.setattr(webapp.AppConfig, "from_env", lambda: _base_local_config())
    monkeypatch.setattr(webapp, "load_profile_form_values", lambda: dict(DEFAULT_PROFILE_VALUES))
    monkeypatch.setattr(webapp, "save_profile_form_values", lambda values: saved_payloads.append(dict(values)))

    app = _build_app()
    app.run()

    assert len(app.exception) == 0

    app = _button_by_label(app, "Salva profilo coppia").click().run()

    assert len(app.exception) == 0
    assert len(saved_payloads) == 1
    assert saved_payloads[0]["person_one_name"] == DEFAULT_PROFILE_VALUES["person_one_name"]
    assert any("Profilo coppia salvato" in alert.value for alert in app.success)


def test_local_strategy_and_diet_flow_updates_session_state(monkeypatch) -> None:
    strategy_result = _strategy_result_for_defaults()
    diet_result = _diet_result_for_defaults(strategy_result)

    monkeypatch.setattr(webapp.AppConfig, "from_env", lambda: _base_local_config())
    monkeypatch.setattr(webapp, "load_profile_form_values", lambda: dict(DEFAULT_PROFILE_VALUES))
    monkeypatch.setattr(webapp, "save_profile_form_values", lambda values: None)
    monkeypatch.setattr(webapp, "generate_wellness_strategy", lambda request, config: strategy_result)
    monkeypatch.setattr(
        webapp,
        "generate_diet_from_strategy",
        lambda request, strategy, config: diet_result,
    )

    app = _build_app()
    app.run()

    app = _button_by_label(app, "Genera o aggiorna strategia").click().run()

    assert len(app.exception) == 0
    assert app.session_state["strategy_result"] is not None
    assert any(button.label == "Genera dieta da questa strategia" for button in app.button)
    assert any("Strategia generata." in alert.value for alert in app.success)

    app = _button_by_label(app, "Genera dieta da questa strategia").click().run()

    assert len(app.exception) == 0
    assert app.session_state["diet_result"] is not None
    assert any(tab.label == "Settimana" for tab in app.tabs)


def test_cloud_reload_flow_restores_matching_saved_state(monkeypatch) -> None:
    auth_session = AuthSession(
        access_token="access",
        refresh_token="refresh",
        user_id="user-1",
        email="user@example.com",
    )
    request_payload = _request_from_defaults()
    strategy_result = _strategy_result_for_defaults()
    diet_result = _diet_result_for_defaults(strategy_result)
    stored_state = StoredPlanningState(
        request_payload=request_payload,
        strategy_result=strategy_result,
        diet_result=diet_result,
    )
    config = AppConfig(
        ai_provider="openai",
        openai_api_key=None,
        supabase_url="https://example.supabase.co",
        supabase_anon_key="anon-key",
    )

    monkeypatch.setattr(webapp.AppConfig, "from_env", lambda: config)
    monkeypatch.setattr(webapp, "render_auth_gate", lambda _config: (object(), auth_session))
    monkeypatch.setattr(webapp, "load_profile_form_values", lambda: dict(DEFAULT_PROFILE_VALUES))
    monkeypatch.setattr(
        webapp,
        "load_profile_form_values_from_supabase",
        lambda client, user_id, table_name: dict(DEFAULT_PROFILE_VALUES),
    )
    monkeypatch.setattr(
        webapp,
        "load_planning_state_from_supabase",
        lambda client, user_id, table_name: stored_state,
    )

    app = _build_app()
    app.run()

    assert len(app.exception) == 0
    assert app.session_state["request_payload"] is not None
    assert app.session_state["strategy_result"] is not None
    assert app.session_state["diet_result"] is not None
    assert any(
        "Ho ricaricato l'ultima strategia e il piano salvati per questo account." in alert.value
        for alert in app.info
    )
