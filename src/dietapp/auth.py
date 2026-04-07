from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from dietapp.config import AppConfig

try:
    from supabase import ClientOptions, create_client
except ImportError:
    ClientOptions = None
    create_client = None


@dataclass(slots=True)
class AuthSession:
    access_token: str
    refresh_token: str
    user_id: str
    email: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw_value: Any) -> "AuthSession | None":
        if not isinstance(raw_value, dict):
            return None

        access_token = str(raw_value.get("access_token") or "").strip()
        refresh_token = str(raw_value.get("refresh_token") or "").strip()
        user_id = str(raw_value.get("user_id") or "").strip()
        email = str(raw_value.get("email") or "").strip()
        if not access_token or not refresh_token or not user_id:
            return None
        return cls(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=user_id,
            email=email,
        )


def _require_supabase(config: AppConfig) -> None:
    if not config.has_supabase():
        raise RuntimeError("Supabase non configurato. Imposta SUPABASE_URL e SUPABASE_ANON_KEY.")
    if create_client is None or ClientOptions is None:
        raise RuntimeError(
            "Dipendenza Supabase non installata. Esegui pip install -r requirements.txt."
        )


def _build_client(config: AppConfig):
    _require_supabase(config)
    return create_client(
        config.supabase_url or "",
        config.supabase_anon_key or "",
        ClientOptions(
            auto_refresh_token=False,
            persist_session=False,
        ),
    )


def _session_from_auth_response(auth_response: Any) -> AuthSession:
    session = getattr(auth_response, "session", None)
    user = getattr(auth_response, "user", None) or getattr(session, "user", None)
    access_token = str(getattr(session, "access_token", "") or "").strip()
    refresh_token = str(getattr(session, "refresh_token", "") or "").strip()
    user_id = str(getattr(user, "id", "") or "").strip()
    email = str(getattr(user, "email", "") or "").strip()

    if not access_token or not refresh_token or not user_id:
        raise RuntimeError("La sessione Supabase non contiene i dati minimi richiesti.")

    return AuthSession(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user_id,
        email=email,
    )


def sign_in_user(config: AppConfig, email: str, password: str):
    client = _build_client(config)
    auth_response = client.auth.sign_in_with_password(
        {
            "email": email.strip(),
            "password": password,
        }
    )
    return client, _session_from_auth_response(auth_response)


def request_password_reset(config: AppConfig, email: str) -> None:
    if not config.supabase_auth_redirect_url:
        raise RuntimeError(
            "Imposta SUPABASE_AUTH_REDIRECT_URL con l'URL pubblico dell'app per abilitare il reset password."
        )

    client = _build_client(config)
    client.auth.reset_password_for_email(
        email.strip(),
        {
            "redirect_to": config.supabase_auth_redirect_url,
        },
    )


def verify_auth_link(config: AppConfig, token_hash: str, auth_type: str):
    client = _build_client(config)
    auth_response = client.auth.verify_otp(
        {
            "token_hash": token_hash.strip(),
            "type": auth_type.strip(),
        }
    )
    return client, _session_from_auth_response(auth_response)


def restore_user_session(config: AppConfig, raw_session: dict[str, Any] | None):
    session_data = AuthSession.from_dict(raw_session)
    if session_data is None:
        return None, None

    client = _build_client(config)
    auth_response = client.auth.set_session(
        session_data.access_token,
        session_data.refresh_token,
    )
    return client, _session_from_auth_response(auth_response)


def update_user_password(config: AppConfig, raw_session: dict[str, Any] | None, new_password: str) -> None:
    client, _ = restore_user_session(config, raw_session)
    if client is None:
        raise RuntimeError("Sessione non valida per aggiornare la password.")
    client.auth.update_user({"password": new_password.strip()})


def sign_out_user(config: AppConfig, raw_session: dict[str, Any] | None) -> None:
    client, _ = restore_user_session(config, raw_session)
    if client is None:
        return
    client.auth.sign_out()