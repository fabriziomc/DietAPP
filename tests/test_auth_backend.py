from __future__ import annotations

from typing import Any

import dietapp.auth as auth_module
from dietapp.auth import AuthSession
from dietapp.config import AppConfig


class FakeUser:
    def __init__(self, user_id: str = "user-1", email: str = "user@example.com") -> None:
        self.id = user_id
        self.email = email


class FakeSession:
    def __init__(self, access_token: str = "access", refresh_token: str = "refresh") -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.user = FakeUser()


class FakeAuthResponse:
    def __init__(self) -> None:
        self.session = FakeSession()
        self.user = FakeUser()


class FakeAuthApi:
    def __init__(self) -> None:
        self.sign_in_payload: dict[str, Any] | None = None
        self.reset_payload: tuple[str, dict[str, str]] | None = None
        self.set_session_payload: tuple[str, str] | None = None
        self.update_payload: dict[str, str] | None = None
        self.verify_payload: dict[str, str] | None = None
        self.signed_out = False

    def sign_in_with_password(self, payload: dict[str, Any]) -> FakeAuthResponse:
        self.sign_in_payload = payload
        return FakeAuthResponse()

    def reset_password_for_email(self, email: str, payload: dict[str, str]) -> None:
        self.reset_payload = (email, payload)

    def set_session(self, access_token: str, refresh_token: str) -> FakeAuthResponse:
        self.set_session_payload = (access_token, refresh_token)
        return FakeAuthResponse()

    def update_user(self, payload: dict[str, str]) -> None:
        self.update_payload = payload

    def verify_otp(self, payload: dict[str, str]) -> FakeAuthResponse:
        self.verify_payload = payload
        return FakeAuthResponse()

    def sign_out(self) -> None:
        self.signed_out = True


class FakeClient:
    def __init__(self) -> None:
        self.auth = FakeAuthApi()


def _build_supabase_config() -> AppConfig:
    return AppConfig(
        ai_provider="openai",
        supabase_url="https://example.supabase.co",
        supabase_anon_key="anon-key",
        supabase_auth_redirect_url="https://app.example",
    )


def test_sign_in_user_calls_supabase_password_login(monkeypatch) -> None:
    fake_client = FakeClient()

    monkeypatch.setattr(auth_module, "ClientOptions", lambda **kwargs: kwargs)
    monkeypatch.setattr(auth_module, "create_client", lambda url, key, options=None: fake_client)

    client, session = auth_module.sign_in_user(_build_supabase_config(), " user@example.com ", "secret")

    assert client is fake_client
    assert session.user_id == "user-1"
    assert fake_client.auth.sign_in_payload == {"email": "user@example.com", "password": "secret"}


def test_request_password_reset_uses_redirect_url(monkeypatch) -> None:
    fake_client = FakeClient()

    monkeypatch.setattr(auth_module, "ClientOptions", lambda **kwargs: kwargs)
    monkeypatch.setattr(auth_module, "create_client", lambda url, key, options=None: fake_client)

    auth_module.request_password_reset(_build_supabase_config(), " user@example.com ")

    assert fake_client.auth.reset_payload == (
        "user@example.com",
        {"redirect_to": "https://app.example"},
    )


def test_restore_session_update_password_and_sign_out(monkeypatch) -> None:
    fake_client = FakeClient()

    monkeypatch.setattr(auth_module, "ClientOptions", lambda **kwargs: kwargs)
    monkeypatch.setattr(auth_module, "create_client", lambda url, key, options=None: fake_client)

    raw_session = AuthSession(
        access_token="access",
        refresh_token="refresh",
        user_id="user-1",
        email="user@example.com",
    ).to_dict()

    client, restored_session = auth_module.restore_user_session(_build_supabase_config(), raw_session)
    auth_module.update_user_password(_build_supabase_config(), raw_session, "  new-password  ")
    auth_module.sign_out_user(_build_supabase_config(), raw_session)

    assert client is fake_client
    assert restored_session is not None
    assert fake_client.auth.set_session_payload == ("access", "refresh")
    assert fake_client.auth.update_payload == {"password": "new-password"}
    assert fake_client.auth.signed_out is True


def test_verify_auth_link_uses_token_hash_and_type(monkeypatch) -> None:
    fake_client = FakeClient()

    monkeypatch.setattr(auth_module, "ClientOptions", lambda **kwargs: kwargs)
    monkeypatch.setattr(auth_module, "create_client", lambda url, key, options=None: fake_client)

    client, session = auth_module.verify_auth_link(_build_supabase_config(), " token-hash ", " recovery ")

    assert client is fake_client
    assert session.user_id == "user-1"
    assert fake_client.auth.verify_payload == {"token_hash": "token-hash", "type": "recovery"}
