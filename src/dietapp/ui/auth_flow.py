from __future__ import annotations

from typing import Any

import streamlit as st

from dietapp.auth import (
    AuthSession,
    request_password_reset,
    restore_user_session,
    sign_in_user,
    sign_out_user,
    update_user_password,
    verify_auth_link,
)
from dietapp.config import AppConfig
from dietapp.ui.state import clear_planning_state


def consume_auth_link(config: AppConfig) -> None:
    token_hash = str(st.query_params.get("token_hash") or "").strip()
    auth_type = str(st.query_params.get("type") or "").strip()
    if not token_hash or not auth_type:
        return

    try:
        _, recovered_session = verify_auth_link(config, token_hash, auth_type)
    except Exception as exc:
        st.session_state.auth_feedback = (
            "error",
            f"Link di accesso o recupero non valido: {exc}",
        )
    else:
        st.session_state.auth_session = recovered_session.to_dict()
        st.session_state.password_reset_pending = auth_type == "recovery"
        st.session_state.planning_state_user_id = None
        clear_planning_state()
        if auth_type == "recovery":
            st.session_state.auth_feedback = (
                "success",
                "Link di recupero verificato. Imposta ora una nuova password.",
            )

    st.query_params.clear()
    st.rerun()


def render_auth_gate(config: AppConfig) -> tuple[Any, AuthSession | None]:
    consume_auth_link(config)

    current_auth_session: AuthSession | None = None
    current_auth_client: Any = None

    feedback = st.session_state.pop("auth_feedback", None)
    if isinstance(feedback, tuple) and len(feedback) == 2:
        level, message = feedback
        getattr(st, level, st.info)(message)

    if st.session_state.get("auth_session"):
        try:
            current_auth_client, current_auth_session = restore_user_session(
                config,
                st.session_state.auth_session,
            )
        except Exception:
            st.session_state.auth_session = None
            st.session_state.planning_state_user_id = None
            st.session_state.password_reset_pending = False
            clear_planning_state()
            st.warning("La sessione e scaduta oppure non e piu valida. Effettua di nuovo il login.")

    st.markdown("<div class='section-label'>Accesso riservato</div>", unsafe_allow_html=True)

    if current_auth_session is not None:
        identity_col, action_col = st.columns([1.8, 1])
        with identity_col:
            st.success(
                f"Accesso attivo come {current_auth_session.email or current_auth_session.user_id}. Profilo, strategia e piano vengono salvati nel cloud per questo account."
            )
        with action_col:
            if st.button("Esci", use_container_width=True):
                try:
                    sign_out_user(config, st.session_state.auth_session)
                except Exception:
                    pass
                st.session_state.auth_session = None
                st.session_state.planning_state_user_id = None
                st.session_state.password_reset_pending = False
                clear_planning_state()
                st.rerun()

        if st.session_state.get("password_reset_pending"):
            st.warning(
                "Recupero password in corso: scegli una nuova password per completare il reset del tuo account."
            )
            with st.form("password-recovery-form", clear_on_submit=True):
                new_password = st.text_input("Nuova password", type="password")
                confirm_password = st.text_input("Conferma nuova password", type="password")
                update_password_clicked = st.form_submit_button(
                    "Aggiorna password",
                    type="primary",
                    use_container_width=True,
                )

            if update_password_clicked:
                if len(new_password.strip()) < 8:
                    st.error("La nuova password deve avere almeno 8 caratteri.")
                elif new_password != confirm_password:
                    st.error("Le due password non coincidono.")
                else:
                    try:
                        update_user_password(config, st.session_state.auth_session, new_password)
                    except Exception as exc:
                        st.error(f"Aggiornamento password non riuscito: {exc}")
                    else:
                        st.session_state.password_reset_pending = False
                        st.session_state.auth_feedback = (
                            "success",
                            "Password aggiornata correttamente.",
                        )
                        st.rerun()

        return current_auth_client, current_auth_session

    st.info(
        "Questa istanza usa Supabase Auth. Mantieni l'app privata creando gli utenti manualmente nel dashboard Supabase, senza signup pubblico."
    )
    with st.form("login-form", clear_on_submit=False):
        login_email = st.text_input("Email", placeholder="nome@esempio.com")
        login_password = st.text_input("Password", type="password")
        login_clicked = st.form_submit_button(
            "Entra",
            type="primary",
            use_container_width=True,
        )

    if login_clicked:
        try:
            _, authenticated_session = sign_in_user(config, login_email, login_password)
        except Exception as exc:
            st.error(
                f"Accesso non riuscito: {exc}. Verifica credenziali, utente attivato in Supabase e secrets configurati."
            )
        else:
            st.session_state.auth_session = authenticated_session.to_dict()
            st.session_state.planning_state_user_id = None
            st.session_state.password_reset_pending = False
            clear_planning_state()
            st.rerun()

    with st.form("forgot-password-form", clear_on_submit=False):
        recovery_email = st.text_input(
            "Email per recupero password",
            placeholder="nome@esempio.com",
        )
        recovery_clicked = st.form_submit_button(
            "Invia email di reset",
            use_container_width=True,
        )

    if recovery_clicked:
        try:
            request_password_reset(config, recovery_email)
        except Exception as exc:
            st.error(f"Invio email di reset non riuscito: {exc}")
        else:
            st.success(
                "Email di reset inviata. Apri il link ricevuto e poi imposta la nuova password direttamente nell'app."
            )

    st.caption(
        "La registrazione pubblica non e esposta nell'app. Crea gli utenti da Supabase Auth > Users, configura il recovery template e poi usa qui email e password."
    )
    st.stop()