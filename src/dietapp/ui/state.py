from __future__ import annotations

from typing import Any

import streamlit as st

from dietapp.auth import AuthSession
from dietapp.config import AppConfig
from dietapp.models import PlanningRequest
from dietapp.persistence import save_planning_state_to_supabase
from dietapp.planner import DietResult, StrategyResult

SESSION_DEFAULTS: dict[str, object] = {
    "auth_session": None,
    "strategy_result": None,
    "diet_result": None,
    "request_payload": None,
    "password_reset_pending": False,
    "planning_state_user_id": None,
    "auth_feedback": None,
}


def ensure_session_defaults() -> None:
    for key, value in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_planning_state() -> None:
    for session_key in ("strategy_result", "diet_result", "request_payload"):
        st.session_state[session_key] = None
    for session_key in ("show_strategy_prompt", "show_diet_prompt"):
        st.session_state[session_key] = False


def persist_planning_state(
    config: AppConfig,
    auth_client: Any,
    auth_session: AuthSession | None,
    request_payload: PlanningRequest | None,
    strategy_result: StrategyResult | None,
    diet_result: DietResult | None,
) -> None:
    if auth_session is None or auth_client is None or request_payload is None or strategy_result is None:
        return

    save_planning_state_to_supabase(
        request_payload,
        strategy_result,
        diet_result,
        auth_client,
        auth_session.user_id,
        config.supabase_profile_table,
    )
