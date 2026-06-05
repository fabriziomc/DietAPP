from __future__ import annotations

from pathlib import Path
from typing import cast

from streamlit.testing.v1 import AppTest

import dietapp.webapp as webapp
from dietapp.auth import AuthSession
from dietapp.config import AppConfig
from dietapp.persistence import DEFAULT_PROFILE_VALUES
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


def _auth_session() -> AuthSession:
    return AuthSession(
        access_token="access",
        refresh_token="refresh",
        user_id="user-1",
        email="user@example.com",
    )


def _cloud_config() -> AppConfig:
    return AppConfig(
        ai_provider="openai",
        openai_api_key=None,
        supabase_url="https://example.supabase.co",
        supabase_anon_key="anon-key",
    )


def _request_payload():
    return build_request_payload(cast(FormValues, dict(DEFAULT_PROFILE_VALUES)))


def _strategy_result() -> StrategyResult:
    request_payload = _request_payload()
    return StrategyResult(
        strategy=generate_fallback_wellness_strategy(request_payload),
        source_label="Planner locale",
        warning=None,
    )


def _diet_result(strategy_result: StrategyResult) -> DietResult:
    request_payload = _request_payload()
    return DietResult(
        plan=generate_fallback_plan(request_payload, strategy_result.strategy),
        source_label="Planner locale",
        warning=None,
    )


def _patch_cloud_bootstrap(monkeypatch) -> None:
    monkeypatch.setattr(webapp.AppConfig, "from_env", lambda: _cloud_config())
    monkeypatch.setattr(webapp, "render_auth_gate", lambda _config: (object(), _auth_session()))
    monkeypatch.setattr(webapp, "load_profile_form_values", lambda: dict(DEFAULT_PROFILE_VALUES))


def test_profile_cloud_load_warning_is_shown(monkeypatch) -> None:
    _patch_cloud_bootstrap(monkeypatch)
    monkeypatch.setattr(
        webapp,
        "load_profile_form_values_from_supabase",
        lambda client, user_id, table_name: (_ for _ in ()).throw(RuntimeError("rls")),
    )
    monkeypatch.setattr(webapp, "load_planning_state_from_supabase", lambda client, user_id, table_name: None)

    app = _build_app()
    app.run()

    assert any("Non riesco a leggere il profilo salvato su Supabase" in alert.value for alert in app.warning)


def test_planning_state_cloud_load_warning_is_shown(monkeypatch) -> None:
    _patch_cloud_bootstrap(monkeypatch)
    monkeypatch.setattr(
        webapp,
        "load_profile_form_values_from_supabase",
        lambda client, user_id, table_name: dict(DEFAULT_PROFILE_VALUES),
    )
    monkeypatch.setattr(
        webapp,
        "load_planning_state_from_supabase",
        lambda client, user_id, table_name: (_ for _ in ()).throw(RuntimeError("rls")),
    )

    app = _build_app()
    app.run()

    assert any("Non riesco a leggere strategia e piano salvati su Supabase" in alert.value for alert in app.warning)


def test_profile_cloud_save_warning_is_shown(monkeypatch) -> None:
    _patch_cloud_bootstrap(monkeypatch)
    monkeypatch.setattr(
        webapp,
        "load_profile_form_values_from_supabase",
        lambda client, user_id, table_name: dict(DEFAULT_PROFILE_VALUES),
    )
    monkeypatch.setattr(webapp, "load_planning_state_from_supabase", lambda client, user_id, table_name: None)
    monkeypatch.setattr(
        webapp,
        "save_profile_form_values_to_supabase",
        lambda values, client, user_id, table_name: (_ for _ in ()).throw(RuntimeError("rls")),
    )

    app = _build_app()
    app.run()
    app = _button_by_label(app, "Salva profilo coppia").click().run()

    assert any("Il piano continua, ma il profilo non e stato salvato" in alert.value for alert in app.warning)


def test_strategy_cloud_persist_warning_is_shown(monkeypatch) -> None:
    _patch_cloud_bootstrap(monkeypatch)
    strategy_result = _strategy_result()
    monkeypatch.setattr(
        webapp,
        "load_profile_form_values_from_supabase",
        lambda client, user_id, table_name: dict(DEFAULT_PROFILE_VALUES),
    )
    monkeypatch.setattr(webapp, "load_planning_state_from_supabase", lambda client, user_id, table_name: None)
    monkeypatch.setattr(webapp, "save_profile_form_values_to_supabase", lambda values, client, user_id, table_name: None)
    monkeypatch.setattr(webapp, "generate_wellness_strategy", lambda request, config: strategy_result)
    monkeypatch.setattr(
        webapp,
        "persist_planning_state",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("rls")),
    )

    app = _build_app()
    app.run()
    app = _button_by_label(app, "Genera o aggiorna strategia").click().run()

    assert any("Strategia generata, ma non sono riuscito a salvarla su Supabase" in alert.value for alert in app.warning)


def test_diet_cloud_persist_warning_is_shown(monkeypatch) -> None:
    _patch_cloud_bootstrap(monkeypatch)
    strategy_result = _strategy_result()
    diet_result = _diet_result(strategy_result)
    monkeypatch.setattr(
        webapp,
        "load_profile_form_values_from_supabase",
        lambda client, user_id, table_name: dict(DEFAULT_PROFILE_VALUES),
    )
    monkeypatch.setattr(webapp, "load_planning_state_from_supabase", lambda client, user_id, table_name: None)
    monkeypatch.setattr(webapp, "save_profile_form_values_to_supabase", lambda values, client, user_id, table_name: None)
    monkeypatch.setattr(webapp, "generate_wellness_strategy", lambda request, config: strategy_result)
    monkeypatch.setattr(webapp, "generate_diet_from_strategy", lambda request, strategy, config: diet_result)

    def fake_persist(*args, **kwargs):
        if args[-1] is not None:
            raise RuntimeError("rls")

    monkeypatch.setattr(webapp, "persist_planning_state", fake_persist)

    app = _build_app()
    app.run()
    app = _button_by_label(app, "Genera o aggiorna strategia").click().run()
    app = _button_by_label(app, "Genera dieta da questa strategia").click().run()

    assert any("Dieta generata, ma non sono riuscito a salvarla su Supabase" in alert.value for alert in app.warning)