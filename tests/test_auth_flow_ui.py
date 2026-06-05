from __future__ import annotations

from streamlit.testing.v1 import AppTest

import dietapp.ui.auth_flow as auth_flow
from dietapp.auth import AuthSession


def _build_auth_gate_app() -> AppTest:
    script = """
from dietapp.ui.auth_flow import render_auth_gate
from dietapp.config import AppConfig
render_auth_gate(AppConfig(ai_provider='openai', supabase_url='https://example.supabase.co', supabase_anon_key='anon-key', supabase_auth_redirect_url='https://app.example'))
"""
    return AppTest.from_string(script)


def test_auth_gate_login_flow_sets_session_and_shows_private_state(monkeypatch) -> None:
    authenticated_session = AuthSession(
        access_token="access",
        refresh_token="refresh",
        user_id="user-1",
        email="user@example.com",
    )

    monkeypatch.setattr(
        auth_flow,
        "restore_user_session",
        lambda config, raw_session: (object(), AuthSession.from_dict(raw_session)) if raw_session else (None, None),
    )
    monkeypatch.setattr(
        auth_flow,
        "sign_in_user",
        lambda config, email, password: (object(), authenticated_session),
    )

    app = _build_auth_gate_app()
    app.run()

    app.text_input[0].input("user@example.com")
    app.text_input[1].input("strong-password")
    app = app.button[0].click().run()

    assert len(app.exception) == 0
    assert app.session_state["auth_session"]["user_id"] == "user-1"
    assert any(button.label == "Esci" for button in app.button)


def test_auth_gate_recovery_flow_requests_reset_email(monkeypatch) -> None:
    requested_emails: list[str] = []

    monkeypatch.setattr(auth_flow, "restore_user_session", lambda config, raw_session: (None, None))
    monkeypatch.setattr(
        auth_flow,
        "request_password_reset",
        lambda config, email: requested_emails.append(email),
    )

    app = _build_auth_gate_app()
    app.run()

    app.text_input[2].input("recover@example.com")
    app = app.button[1].click().run()

    assert len(app.exception) == 0
    assert requested_emails == ["recover@example.com"]
    assert any("Email di reset inviata" in alert.value for alert in app.success)
