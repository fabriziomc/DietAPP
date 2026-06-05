from __future__ import annotations

from pathlib import Path
from typing import cast

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


def test_cloud_end_to_end_flow_reloads_generated_state(monkeypatch) -> None:
    auth_session = AuthSession(
        access_token="access",
        refresh_token="refresh",
        user_id="user-1",
        email="user@example.com",
    )
    request_payload = build_request_payload(cast(FormValues, dict(DEFAULT_PROFILE_VALUES)))
    strategy_result = StrategyResult(
        strategy=generate_fallback_wellness_strategy(request_payload),
        source_label="Planner locale",
        warning=None,
    )
    diet_result = DietResult(
        plan=generate_fallback_plan(request_payload, strategy_result.strategy),
        source_label="Planner locale",
        warning=None,
    )
    config = AppConfig(
        ai_provider="openai",
        openai_api_key=None,
        supabase_url="https://example.supabase.co",
        supabase_anon_key="anon-key",
    )

    profile_store: dict[str, object] = dict(DEFAULT_PROFILE_VALUES)
    planning_store: dict[str, StoredPlanningState | None] = {"state": None}

    monkeypatch.setattr(webapp.AppConfig, "from_env", lambda: config)
    monkeypatch.setattr(webapp, "render_auth_gate", lambda _config: (object(), auth_session))
    monkeypatch.setattr(webapp, "load_profile_form_values", lambda: dict(DEFAULT_PROFILE_VALUES))
    monkeypatch.setattr(
        webapp,
        "load_profile_form_values_from_supabase",
        lambda client, user_id, table_name: dict(profile_store),
    )
    monkeypatch.setattr(
        webapp,
        "save_profile_form_values_to_supabase",
        lambda values, client, user_id, table_name: profile_store.update(dict(values)),
    )
    monkeypatch.setattr(
        webapp,
        "load_planning_state_from_supabase",
        lambda client, user_id, table_name: planning_store["state"],
    )
    monkeypatch.setattr(webapp, "generate_wellness_strategy", lambda request, runtime_config: strategy_result)
    monkeypatch.setattr(webapp, "generate_diet_from_strategy", lambda request, strategy, runtime_config: diet_result)

    def persist_state(base_config, auth_client, current_auth_session, request_payload, current_strategy_result, current_diet_result):
        planning_store["state"] = StoredPlanningState(
            request_payload=request_payload,
            strategy_result=current_strategy_result,
            diet_result=current_diet_result,
        )

    monkeypatch.setattr(webapp, "persist_planning_state", persist_state)

    app = _build_app()
    app.run()

    app = _button_by_label(app, "Genera o aggiorna strategia").click().run()
    assert app.session_state["strategy_result"] is not None

    app = _button_by_label(app, "Genera dieta da questa strategia").click().run()
    assert app.session_state["diet_result"] is not None
    assert planning_store["state"] is not None

    reloaded_app = _build_app()
    reloaded_app.run()

    assert reloaded_app.session_state["diet_result"] is not None
    assert any(
        "Ho ricaricato l'ultima strategia e il piano salvati per questo account." in alert.value
        for alert in reloaded_app.info
    )
