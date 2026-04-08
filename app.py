from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path
from textwrap import dedent

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

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
from dietapp.defaults import CUISINE_OPTIONS, DAYS, PANTRY_OPTIONS
from dietapp.formatters import compute_plan_metrics, plan_to_markdown
from dietapp.models import HouseholdPreferences, PersonProfile, PlanningRequest, WeeklyPlan, WellnessStrategy
from dietapp.persistence import (
    DEFAULT_PROFILE_VALUES,
    clear_planning_state_from_supabase,
    load_planning_state_from_supabase,
    load_profile_form_values,
    load_profile_form_values_from_supabase,
    save_planning_state_to_supabase,
    save_profile_form_values,
    save_profile_form_values_to_supabase,
)
import dietapp.planner as planner_module


DietResult = planner_module.DietResult
StrategyResult = planner_module.StrategyResult
generate_diet_from_strategy = planner_module.generate_diet_from_strategy
generate_wellness_strategy = planner_module.generate_wellness_strategy


def build_strategy_prompt_preview(request: PlanningRequest) -> str:
    prompt_builder = getattr(planner_module, "build_strategy_prompt_preview", None)
    if callable(prompt_builder):
        return prompt_builder(request)
    return _format_prompt_preview(
        planner_module.STRATEGY_SYSTEM_PROMPT,
        planner_module._build_strategy_ai_prompt(request),
    )


def build_plan_prompt_preview(request: PlanningRequest, strategy: WellnessStrategy) -> str:
    prompt_builder = getattr(planner_module, "build_plan_prompt_preview", None)
    if callable(prompt_builder):
        return prompt_builder(request, strategy)
    return _format_prompt_preview(
        planner_module.PLAN_SYSTEM_PROMPT,
        planner_module._build_plan_ai_prompt(request, strategy),
    )


def _format_prompt_preview(system_prompt: str, user_prompt: str) -> str:
    return "\n\n".join(
        [
            "=== SYSTEM PROMPT ===",
            system_prompt,
            "=== USER PROMPT ===",
            user_prompt,
        ]
    )


st.set_page_config(
    page_title="DietAPP | Planner settimanale",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def inject_styles() -> None:
    st.markdown(
        dedent(
            """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Cormorant+Garamond:wght@500;700&display=swap');

        :root {
            --paper: #f7f2e8;
            --card: rgba(255, 250, 243, 0.82);
            --ink: #15251b;
            --muted: #5c6d5d;
            --green: #2c6e49;
            --green-soft: #dfeadf;
            --sand: #efe2cb;
            --terracotta: #c06549;
            --border: rgba(21, 37, 27, 0.08);
            --shadow: 0 16px 40px rgba(21, 37, 27, 0.09);
        }

        html, body, [class*="css"]  {
            font-family: 'Space Grotesk', sans-serif;
            color: var(--ink);
        }

        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at top left, rgba(192, 101, 73, 0.18), transparent 32%),
                radial-gradient(circle at top right, rgba(44, 110, 73, 0.16), transparent 34%),
                linear-gradient(180deg, #faf6ee 0%, #f2ebdf 100%);
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #173923 0%, #29593b 100%);
        }

        [data-testid="stSidebar"],
        [data-testid="collapsedControl"] {
            display: none;
        }

        [data-testid="stSidebar"] * {
            color: #f8f6f1;
        }

        .hero {
            background: linear-gradient(135deg, rgba(255,255,255,0.82), rgba(239,226,203,0.86));
            border: 1px solid var(--border);
            border-radius: 28px;
            padding: 2.2rem 2rem 1.8rem;
            box-shadow: var(--shadow);
            margin-bottom: 1.2rem;
            position: relative;
            overflow: hidden;
        }

        .hero:before {
            content: "";
            position: absolute;
            inset: auto -40px -60px auto;
            width: 220px;
            height: 220px;
            border-radius: 999px;
            background: radial-gradient(circle, rgba(192,101,73,0.22) 0%, rgba(192,101,73,0) 72%);
        }

        .hero-kicker {
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            color: var(--green);
            font-weight: 700;
            margin-bottom: 0.6rem;
        }

        .hero h1 {
            font-family: 'Cormorant Garamond', serif;
            font-size: clamp(2.2rem, 3vw, 3.5rem);
            line-height: 0.95;
            margin: 0 0 0.9rem;
        }

        .hero p {
            max-width: 860px;
            color: var(--muted);
            margin: 0;
            font-size: 1.02rem;
        }

        .section-label {
            font-size: 0.8rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            color: var(--green);
            margin: 1.6rem 0 0.65rem;
        }

        .metric-card,
        .day-shell,
        .meal-card,
        .shopping-card,
        .prep-card {
            background: var(--card);
            backdrop-filter: blur(8px);
            border: 1px solid var(--border);
            box-shadow: var(--shadow);
            border-radius: 24px;
        }

        .metric-card {
            padding: 1.1rem 1.15rem;
            min-height: 128px;
        }

        .metric-label {
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-weight: 700;
            color: var(--muted);
        }

        .metric-value {
            font-size: 2rem;
            font-weight: 700;
            margin: 0.35rem 0 0.2rem;
            color: var(--ink);
        }

        .metric-caption {
            color: var(--muted);
            font-size: 0.9rem;
            line-height: 1.35;
        }

        .day-shell {
            padding: 1.2rem;
            margin-bottom: 1rem;
        }

        .day-title {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            gap: 1rem;
            margin-bottom: 0.85rem;
        }

        .day-title h3 {
            font-family: 'Cormorant Garamond', serif;
            font-size: 2rem;
            margin: 0;
        }

        .meal-card {
            padding: 1rem;
            height: 100%;
        }

        .meal-label {
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-weight: 700;
            color: var(--terracotta);
        }

        .meal-base {
            font-weight: 700;
            margin: 0.4rem 0 0.75rem;
            line-height: 1.35;
        }

        .meal-variant {
            margin-bottom: 0.75rem;
            padding-top: 0.7rem;
            border-top: 1px dashed rgba(21,37,27,0.12);
        }

        .meal-variant:first-of-type {
            border-top: 0;
            padding-top: 0;
        }

        .meal-person {
            font-size: 0.83rem;
            text-transform: uppercase;
            letter-spacing: 0.11em;
            color: var(--green);
            font-weight: 700;
        }

        .meal-name {
            font-weight: 700;
            margin: 0.2rem 0;
        }

        .meal-text,
        .meal-meta,
        .shopping-card li,
        .prep-card li {
            color: var(--muted);
            line-height: 1.45;
        }

        .meal-meta {
            margin-top: 0.7rem;
            font-size: 0.9rem;
        }

        .tag {
            display: inline-flex;
            align-items: center;
            padding: 0.2rem 0.55rem;
            margin-right: 0.35rem;
            border-radius: 999px;
            background: var(--green-soft);
            color: var(--green);
            font-size: 0.78rem;
            font-weight: 700;
        }

        .shopping-card,
        .prep-card {
            padding: 1rem 1.1rem;
        }

        .shopping-card h4,
        .prep-card h4 {
            margin-top: 0;
        }

        .download-shell {
            padding-top: 0.8rem;
        }
        </style>
        """
        ).strip(),
        unsafe_allow_html=True,
    )


def csv_to_list(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def format_weight(value: float | None) -> str:
    if value is None:
        return "n.d."
    if float(value).is_integer():
        return f"{int(value)} kg"
    return f"{value:.1f} kg"


def safe_index(options: list[str], value: str, fallback: int = 0) -> int:
    try:
        return options.index(value)
    except ValueError:
        return fallback


def filter_selected_options(values: list[str], allowed_options: list[str]) -> list[str]:
    return [value for value in values if value in allowed_options]


def describe_person_profile(person: PersonProfile) -> str:
    parts = []
    if person.age is not None:
        parts.append(f"{person.age} anni")
    if person.sex:
        parts.append(person.sex)
    if person.height_cm is not None:
        parts.append(f"{person.height_cm} cm")
    if person.weight_kg is not None:
        parts.append(format_weight(person.weight_kg))
    if person.target_weight_kg is not None and person.weight_kg is not None:
        weight_delta = person.target_weight_kg - person.weight_kg
        if abs(weight_delta) >= 0.5:
            direction_label = "dimagrimento" if weight_delta < 0 else "aumento"
            parts.append(f"target {format_weight(person.target_weight_kg)} ({direction_label})")
    return " | ".join(parts) if parts else "Profilo non completo"


def build_weight_goal_summary(*people: PersonProfile) -> str:
    goals: list[str] = []
    for person in people:
        if person.target_weight_kg is None or person.weight_kg is None:
            continue
        weight_delta = person.target_weight_kg - person.weight_kg
        if abs(weight_delta) < 0.5:
            goals.append(f"{person.name}: mantenimento del peso")
        elif weight_delta < 0:
            goals.append(f"{person.name}: dimagrimento verso {format_weight(person.target_weight_kg)}")
        else:
            goals.append(f"{person.name}: aumento di peso verso {format_weight(person.target_weight_kg)}")
    return "; ".join(goals)


def build_request_payload(form_values: dict[str, object]) -> PlanningRequest:
    person_one = PersonProfile(
        name=str(form_values["person_one_name"]).strip() or "Persona 1",
        dietary_style=str(form_values["person_one_style"]),
        age=int(form_values["person_one_age"]),
        sex=str(form_values["person_one_sex"]),
        height_cm=int(form_values["person_one_height_cm"]),
        weight_kg=float(form_values["person_one_weight_kg"]),
        target_weight_kg=float(form_values["person_one_target_weight_kg"]),
        activity_summary=str(form_values["person_one_activity"]).strip(),
        dislikes=csv_to_list(str(form_values["person_one_dislikes"])),
        allergies=csv_to_list(str(form_values["person_one_allergies"])),
    )
    person_two = PersonProfile(
        name=str(form_values["person_two_name"]).strip() or "Persona 2",
        dietary_style=str(form_values["person_two_style"]),
        age=int(form_values["person_two_age"]),
        sex=str(form_values["person_two_sex"]),
        height_cm=int(form_values["person_two_height_cm"]),
        weight_kg=float(form_values["person_two_weight_kg"]),
        target_weight_kg=float(form_values["person_two_target_weight_kg"]),
        activity_summary=str(form_values["person_two_activity"]).strip(),
        dislikes=csv_to_list(str(form_values["person_two_dislikes"])),
        allergies=csv_to_list(str(form_values["person_two_allergies"])),
    )
    return PlanningRequest(
        person_one=person_one,
        person_two=person_two,
        preferences=HouseholdPreferences(
            goal=build_weight_goal_summary(person_one, person_two),
            budget=str(form_values["budget"]),
            max_prep_minutes=int(form_values["max_prep_minutes"]),
            leftover_lunches=int(form_values["leftover_lunches"]),
            batch_days=list(form_values["batch_days"]),
            favorite_cuisines=list(form_values["cuisines"]),
            pantry_staples=list(form_values["pantry_staples"]),
            excluded_ingredients=csv_to_list(str(form_values["excluded_ingredients"])),
            notes=str(form_values["notes"]).strip(),
        ),
    )


def build_source_label(strategy_source: str, diet_source: str) -> str:
    if strategy_source == diet_source:
        return strategy_source
    return f"Strategia {strategy_source} | Dieta {diet_source}"


def same_request_payload(left: PlanningRequest | None, right: PlanningRequest) -> bool:
    return left is not None and left.to_dict() == right.to_dict()


def render_metric(label: str, value: str, caption: str) -> None:
    st.markdown(
        dedent(
            f"""
        <div class="metric-card">
            <div class="metric-label">{escape(label)}</div>
            <div class="metric-value">{escape(value)}</div>
            <div class="metric-caption">{escape(caption)}</div>
        </div>
        """
        ).strip(),
        unsafe_allow_html=True,
    )


def render_wellness_strategy(strategy: WellnessStrategy, request: PlanningRequest) -> None:
    shared_principles = "".join(f"<li>{escape(item)}</li>" for item in strategy.shared_principles)
    kitchen_principles = "".join(f"<li>{escape(item)}</li>" for item in strategy.kitchen_principles)
    st.markdown(
        dedent(
            f"""
        <div class="prep-card">
            <h4>{escape(strategy.title)}</h4>
            <p>{escape(strategy.couple_summary)}</p>
            <h4>Principi condivisi</h4>
            <ul>{shared_principles}</ul>
            <h4>Principi di cucina</h4>
            <ul>{kitchen_principles}</ul>
        </div>
        """
        ).strip(),
        unsafe_allow_html=True,
    )

    columns = st.columns(2)
    people = [
        (request.person_one, strategy.person_one),
        (request.person_two, strategy.person_two),
    ]
    for column, (person, person_strategy) in zip(columns, people, strict=False):
        guidance_markup = "".join(
            f"<li>{escape(item)}</li>" for item in person_strategy.nutrition_guidance
        )
        tags = "".join(
            [
                f'<span class="tag">{escape(person_strategy.focus)}</span>',
                f'<span class="tag">{escape(str(person_strategy.daily_kcal_target or "n.d."))} kcal</span>',
                f'<span class="tag">{escape(str(person_strategy.protein_target_g or "n.d."))} g proteine</span>',
            ]
        )
        with column:
            st.markdown(
                dedent(
                    f"""
                <div class="prep-card">
                    <h4>{escape(person.name)}</h4>
                    <p>{escape(describe_person_profile(person))}</p>
                    <div class="meal-meta">{tags}</div>
                    <p>{escape(person_strategy.rationale)}</p>
                    <p><strong>Movimento:</strong> {escape(person_strategy.movement_guidance)}</p>
                    <ul>{guidance_markup}</ul>
                </div>
                """
                ).strip(),
                unsafe_allow_html=True,
            )


def render_meal_card(slot_label: str, meal, person_one_name: str, person_two_name: str) -> None:
    tags = []
    tags.append(f"{meal.prep_minutes} min")
    tags.append(meal.kitchen_load)
    if meal.leftover_friendly:
        tags.append("avanzi")

    tag_markup = "".join(f'<span class="tag">{escape(tag)}</span>' for tag in tags)
    shared_base = escape(meal.shared_base)

    person_one_block = dedent(
        f"""
        <div class="meal-variant">
            <div class="meal-person">{escape(person_one_name)}</div>
            <div class="meal-name">{escape(meal.person_one.title)}</div>
            <div class="meal-text">{escape(meal.person_one.description)}</div>
            <div class="meal-text">Ingredienti: {escape(', '.join(meal.person_one.ingredients))}</div>
            <div class="meal-text">Prep: {escape(meal.person_one.prep_notes)}</div>
        </div>
        """
    ).strip()

    person_two_block = dedent(
        f"""
        <div class="meal-variant">
            <div class="meal-person">{escape(person_two_name)}</div>
            <div class="meal-name">{escape(meal.person_two.title)}</div>
            <div class="meal-text">{escape(meal.person_two.description)}</div>
            <div class="meal-text">Ingredienti: {escape(', '.join(meal.person_two.ingredients))}</div>
            <div class="meal-text">Prep: {escape(meal.person_two.prep_notes)}</div>
        </div>
        """
    ).strip()

    reuse_copy = escape(meal.reuse_from_previous or "Nuova preparazione, ma con dispensa condivisa.")
    st.markdown(
        dedent(
            f"""
        <div class="meal-card">
            <div class="meal-label">{escape(slot_label)}</div>
            <div class="meal-base">Base comune: {shared_base}</div>
            {person_one_block}
            {person_two_block}
            <div class="meal-meta">{tag_markup}</div>
            <div class="meal-meta">Riutilizzo: {reuse_copy}</div>
        </div>
        """
        ).strip(),
        unsafe_allow_html=True,
    )


def render_day(day_plan, person_one_name: str, person_two_name: str) -> None:
    st.markdown(
        dedent(
            f"""
        <div class="day-shell">
            <div class="day-title">
                <h3>{escape(day_plan.day)}</h3>
                <div class="tag">Strategia: {escape(day_plan.dinner.reuse_from_previous or 'rotazione smart')}</div>
            </div>
        </div>
        """
        ).strip(),
        unsafe_allow_html=True,
    )
    breakfast_col, lunch_col, dinner_col = st.columns(3)
    with breakfast_col:
        render_meal_card("Colazione", day_plan.breakfast, person_one_name, person_two_name)
    with lunch_col:
        render_meal_card("Pranzo", day_plan.lunch, person_one_name, person_two_name)
    with dinner_col:
        render_meal_card("Cena", day_plan.dinner, person_one_name, person_two_name)


def render_shopping_list(plan: WeeklyPlan) -> None:
    categories = list(plan.shopping_list.items())
    if not categories:
        st.info("La lista della spesa verra popolata quando generi un piano.")
        return

    columns = st.columns(2)
    for index, (category, items) in enumerate(categories):
        with columns[index % 2]:
            item_markup = "".join(f"<li>{escape(item)}</li>" for item in items)
            st.markdown(
                dedent(
                    f"""
                <div class="shopping-card">
                    <h4>{escape(category)}</h4>
                    <ul>{item_markup}</ul>
                </div>
                """
                ).strip(),
                unsafe_allow_html=True,
            )


def render_prep(plan: WeeklyPlan) -> None:
    prep_markup = "".join(f"<li>{escape(task)}</li>" for task in plan.prep_tasks)
    notes_markup = "".join(f"<li>{escape(note)}</li>" for note in plan.planning_notes)
    st.markdown(
        dedent(
            f"""
        <div class="prep-card">
            <h4>Strategia settimanale</h4>
            <p>{escape(plan.strategy)}</p>
            <h4>Prep consigliato</h4>
            <ul>{prep_markup}</ul>
            <h4>Note operative</h4>
            <ul>{notes_markup}</ul>
        </div>
        """
        ).strip(),
        unsafe_allow_html=True,
    )


def render_prompt_preview_toggle(
    button_label: str,
    session_key: str,
    prompt_text: str,
    source_label: str,
    warning: str | None,
    local_only_message: str,
) -> None:
    if st.button(button_label, key=f"{session_key}-toggle", use_container_width=True):
        st.session_state[session_key] = not st.session_state.get(session_key, False)

    if not st.session_state.get(session_key, False):
        return

    if source_label == "Planner locale":
        if warning:
            st.info(
                "Il planner locale e intervenuto dopo un tentativo AI non riuscito. Qui sotto trovi il prompt costruito per quella richiesta."
            )
        else:
            st.info(local_only_message)

    st.code(prompt_text)


def clear_planning_state() -> None:
    for session_key in ("strategy_result", "diet_result", "request_payload"):
        st.session_state[session_key] = None
    for session_key in ("show_strategy_prompt", "show_diet_prompt"):
        st.session_state[session_key] = False


def persist_planning_state(
    config: AppConfig,
    auth_client,
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


def render_auth_gate(config: AppConfig):
    consume_auth_link(config)

    current_auth_session: AuthSession | None = None
    current_auth_client = None

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


inject_styles()

if "auth_session" not in st.session_state:
    st.session_state.auth_session = None

if "strategy_result" not in st.session_state:
    st.session_state.strategy_result = None

if "diet_result" not in st.session_state:
    st.session_state.diet_result = None

if "request_payload" not in st.session_state:
    st.session_state.request_payload = None

if "password_reset_pending" not in st.session_state:
    st.session_state.password_reset_pending = False

if "planning_state_user_id" not in st.session_state:
    st.session_state.planning_state_user_id = None

if "auth_feedback" not in st.session_state:
    st.session_state.auth_feedback = None

st.markdown(
    dedent(
        """
    <div class="hero">
        <div class="hero-kicker">Meal planning per due</div>
        <h1>Una settimana sola, una cucina sola, due diete diverse.</h1>
        <p>
            DietAPP genera un piano alimentare condiviso per una coppia con versioni onnivora e vegetariana,
            usando basi comuni, avanzi utili e meno passaggi possibile ai fornelli.
        </p>
    </div>
    """
    ).strip(),
    unsafe_allow_html=True,
)

base_config = AppConfig.from_env()
auth_client = None
auth_session: AuthSession | None = None

if base_config.has_supabase():
    auth_client, auth_session = render_auth_gate(base_config)

form_defaults = load_profile_form_values()
profile_storage_label = "locale"
if auth_session is not None and auth_client is not None:
    try:
        form_defaults = load_profile_form_values_from_supabase(
            auth_client,
            auth_session.user_id,
            base_config.supabase_profile_table,
        )
        profile_storage_label = "cloud personale"
    except Exception:
        form_defaults = dict(DEFAULT_PROFILE_VALUES)
        st.warning(
            "Non riesco a leggere il profilo salvato su Supabase. Controlla tabella, policy RLS e secrets."
        )
style_options = ["Onnivoro", "Vegetariano"]
sex_options = ["Uomo", "Donna", "Altro / Non specificato"]
budget_options = ["Essenziale", "Bilanciato", "Premium"]
batch_day_options = [DAYS[-1], *DAYS[:-1]]

st.markdown("<div class='section-label'>Motore e memoria</div>", unsafe_allow_html=True)
if base_config.get_api_key():
    st.success(
        f"Motore AI attivo da .env: {base_config.get_provider_label()} | {base_config.get_model()}"
    )
else:
    st.info("Nessuna chiave AI valida trovata nel file .env: usero il planner locale.")
st.caption(
    f"Il profilo della coppia si salva in {profile_storage_label}. Eta, sesso, altezza, peso, obiettivo peso e attivita guidano prima la strategia benessere e poi il piano alimentare; con Supabase attivo vengono ricaricati anche strategia e piano compatibili con il profilo corrente."
)

if not base_config.has_supabase():
    st.warning(
        "Supabase non e configurato: questa istanza resta pubblica e il profilo si salva solo sul filesystem locale."
    )

st.markdown("<div class='section-label'>Profili e vincoli</div>", unsafe_allow_html=True)

with st.form("planner-form", clear_on_submit=False):
    left_col, right_col = st.columns(2)

    with left_col:
        person_one_name = st.text_input("Nome persona 1", value=form_defaults["person_one_name"])
        person_one_style = st.selectbox(
            "Regime persona 1",
            options=style_options,
            index=safe_index(style_options, form_defaults["person_one_style"]),
        )
        person_one_age = st.number_input(
            "Eta persona 1",
            min_value=14,
            max_value=100,
            value=form_defaults["person_one_age"],
            step=1,
        )
        person_one_sex = st.selectbox(
            "Sesso persona 1",
            options=sex_options,
            index=safe_index(sex_options, form_defaults["person_one_sex"]),
        )
        person_one_height_cm = st.number_input(
            "Altezza persona 1 (cm)",
            min_value=120,
            max_value=230,
            value=form_defaults["person_one_height_cm"],
            step=1,
        )
        person_one_weight_kg = st.number_input(
            "Peso persona 1 (kg)",
            min_value=35.0,
            max_value=250.0,
            value=float(form_defaults["person_one_weight_kg"]),
            step=0.5,
            format="%.1f",
        )
        person_one_target_weight_kg = st.number_input(
            "Obiettivo peso persona 1 (kg)",
            min_value=35.0,
            max_value=250.0,
            value=float(form_defaults["person_one_target_weight_kg"]),
            step=0.5,
            format="%.1f",
            help="Se uguale al peso attuale indica mantenimento; se piu basso o piu alto segnala dimagrimento o aumento di peso.",
        )
        person_one_activity = st.text_area(
            "Attivita motoria persona 1",
            value=form_defaults["person_one_activity"],
            help="Descrivi in modo libero allenamenti, lavoro attivo/sedentario, camminate e frequenza.",
        )
        person_one_dislikes = st.text_area(
            "Ingredienti da evitare persona 1",
            value=form_defaults["person_one_dislikes"],
            help="Separati da virgola.",
        )
        person_one_allergies = st.text_area(
            "Allergie/intolleranze persona 1",
            value=form_defaults["person_one_allergies"],
            help="Separati da virgola.",
        )

    with right_col:
        person_two_name = st.text_input("Nome persona 2", value=form_defaults["person_two_name"])
        person_two_style = st.selectbox(
            "Regime persona 2",
            options=style_options,
            index=safe_index(style_options, form_defaults["person_two_style"], fallback=1),
        )
        person_two_age = st.number_input(
            "Eta persona 2",
            min_value=14,
            max_value=100,
            value=form_defaults["person_two_age"],
            step=1,
        )
        person_two_sex = st.selectbox(
            "Sesso persona 2",
            options=sex_options,
            index=safe_index(sex_options, form_defaults["person_two_sex"], fallback=1),
        )
        person_two_height_cm = st.number_input(
            "Altezza persona 2 (cm)",
            min_value=120,
            max_value=230,
            value=form_defaults["person_two_height_cm"],
            step=1,
        )
        person_two_weight_kg = st.number_input(
            "Peso persona 2 (kg)",
            min_value=35.0,
            max_value=250.0,
            value=float(form_defaults["person_two_weight_kg"]),
            step=0.5,
            format="%.1f",
        )
        person_two_target_weight_kg = st.number_input(
            "Obiettivo peso persona 2 (kg)",
            min_value=35.0,
            max_value=250.0,
            value=float(form_defaults["person_two_target_weight_kg"]),
            step=0.5,
            format="%.1f",
            help="Se uguale al peso attuale indica mantenimento; se piu basso o piu alto segnala dimagrimento o aumento di peso.",
        )
        person_two_activity = st.text_area(
            "Attivita motoria persona 2",
            value=form_defaults["person_two_activity"],
            help="Descrivi in modo libero allenamenti, camminate, lavoro attivo o sedentarieta.",
        )
        person_two_dislikes = st.text_area(
            "Ingredienti da evitare persona 2",
            value=form_defaults["person_two_dislikes"],
            help="Separati da virgola.",
        )
        person_two_allergies = st.text_area(
            "Allergie/intolleranze persona 2",
            value=form_defaults["person_two_allergies"],
            help="Separati da virgola.",
        )

    pref_col, pantry_col = st.columns(2)

    with pref_col:
        budget = st.select_slider(
            "Budget",
            options=budget_options,
            value=form_defaults["budget"],
        )
        max_prep_minutes = st.slider(
            "Tempo massimo per singolo pasto",
            min_value=10,
            max_value=60,
            value=form_defaults["max_prep_minutes"],
            step=5,
        )
        leftover_lunches = st.slider(
            "Pranzi con avanzi a settimana",
            min_value=0,
            max_value=5,
            value=form_defaults["leftover_lunches"],
        )
        batch_days = st.multiselect(
            "Giorni di batch cooking",
            options=batch_day_options,
            default=filter_selected_options(form_defaults["batch_days"], batch_day_options),
        )
        cuisines = st.multiselect(
            "Cucine preferite",
            options=CUISINE_OPTIONS,
            default=filter_selected_options(form_defaults["cuisines"], CUISINE_OPTIONS),
        )

    with pantry_col:
        pantry_staples = st.multiselect(
            "Dispensa sempre presente",
            options=PANTRY_OPTIONS,
            default=filter_selected_options(form_defaults["pantry_staples"], PANTRY_OPTIONS),
        )
        excluded_ingredients = st.text_area(
            "Ingredienti esclusi in casa",
            value=form_defaults["excluded_ingredients"],
            help="Separati da virgola.",
        )
        notes = st.text_area(
            "Note per il planner",
            value=form_defaults["notes"],
            height=180,
        )

    action_col, submit_col = st.columns([1, 1.4])
    with action_col:
        save_profile_clicked = st.form_submit_button(
            "Salva profilo coppia",
            use_container_width=True,
        )
    with submit_col:
        generate_strategy_clicked = st.form_submit_button(
            "Genera o aggiorna strategia",
            type="primary",
            use_container_width=True,
        )

form_values = {
    "person_one_name": person_one_name,
    "person_one_style": person_one_style,
    "person_one_age": person_one_age,
    "person_one_sex": person_one_sex,
    "person_one_height_cm": person_one_height_cm,
    "person_one_weight_kg": person_one_weight_kg,
    "person_one_target_weight_kg": person_one_target_weight_kg,
    "person_one_activity": person_one_activity,
    "person_one_dislikes": person_one_dislikes,
    "person_one_allergies": person_one_allergies,
    "person_two_name": person_two_name,
    "person_two_style": person_two_style,
    "person_two_age": person_two_age,
    "person_two_sex": person_two_sex,
    "person_two_height_cm": person_two_height_cm,
    "person_two_weight_kg": person_two_weight_kg,
    "person_two_target_weight_kg": person_two_target_weight_kg,
    "person_two_activity": person_two_activity,
    "person_two_dislikes": person_two_dislikes,
    "person_two_allergies": person_two_allergies,
    "budget": budget,
    "max_prep_minutes": max_prep_minutes,
    "leftover_lunches": leftover_lunches,
    "batch_days": batch_days,
    "cuisines": cuisines,
    "pantry_staples": pantry_staples,
    "excluded_ingredients": excluded_ingredients,
    "notes": notes,
}

current_request_payload = build_request_payload(form_values)

if auth_session is not None and auth_client is not None:
    if st.session_state.planning_state_user_id != auth_session.user_id:
        clear_planning_state()
        st.session_state.planning_state_user_id = auth_session.user_id

    if st.session_state.request_payload is None and st.session_state.strategy_result is None:
        try:
            stored_planning_state = load_planning_state_from_supabase(
                auth_client,
                auth_session.user_id,
                base_config.supabase_profile_table,
            )
        except Exception:
            st.warning(
                "Non riesco a leggere strategia e piano salvati su Supabase. Controlla tabella, colonne aggiuntive e policy RLS."
            )
        else:
            if (
                stored_planning_state is not None
                and stored_planning_state.request_payload.to_dict() == current_request_payload.to_dict()
            ):
                st.session_state.request_payload = stored_planning_state.request_payload
                st.session_state.strategy_result = stored_planning_state.strategy_result
                st.session_state.diet_result = stored_planning_state.diet_result
                st.info("Ho ricaricato l'ultima strategia e il piano salvati per questo account.")

if save_profile_clicked or generate_strategy_clicked:
    try:
        if auth_session is not None and auth_client is not None:
            save_profile_form_values_to_supabase(
                form_values,
                auth_client,
                auth_session.user_id,
                base_config.supabase_profile_table,
            )
        else:
            save_profile_form_values(form_values)
    except Exception:
        st.warning(
            "Il piano continua, ma il profilo non e stato salvato. Controlla configurazione Supabase e policy della tabella profili."
        )

if save_profile_clicked and not generate_strategy_clicked:
    if not same_request_payload(st.session_state.request_payload, current_request_payload):
        clear_planning_state()
        if auth_session is not None and auth_client is not None:
            try:
                clear_planning_state_from_supabase(
                    auth_client,
                    auth_session.user_id,
                    base_config.supabase_profile_table,
                )
            except Exception:
                st.warning(
                    "Profilo aggiornato, ma non sono riuscito a rimuovere strategia e piano precedenti dal cloud."
                )
        st.info(
            "Profilo aggiornato: ho rimosso strategia e piano precedenti per evitare incoerenze con i nuovi dati."
        )

if save_profile_clicked and not generate_strategy_clicked:
    if auth_session is not None:
        st.success("Profilo coppia salvato nel cloud per questo account.")
    else:
        st.success("Profilo coppia salvato. Al prossimo refresh i campi verranno ripopolati automaticamente.")

if generate_strategy_clicked:
    request_payload = current_request_payload
    runtime_config = AppConfig.from_env()

    with st.spinner("Sto costruendo la strategia benessere personalizzata..."):
        st.session_state.strategy_result = generate_wellness_strategy(request_payload, runtime_config)
        st.session_state.diet_result = None
        st.session_state.request_payload = request_payload

    if auth_session is not None and auth_client is not None:
        try:
            persist_planning_state(
                base_config,
                auth_client,
                auth_session,
                request_payload,
                st.session_state.strategy_result,
                None,
            )
        except Exception:
            st.warning(
                "Strategia generata, ma non sono riuscito a salvarla su Supabase. Controlla schema e policy della tabella profili."
            )

    st.success("Strategia generata. Se la approvi, puoi creare o rigenerare la dieta settimanale con il pulsante dedicato.")

strategy_result: StrategyResult | None = st.session_state.strategy_result
diet_result: DietResult | None = st.session_state.diet_result
request_payload: PlanningRequest | None = st.session_state.request_payload

if strategy_result and request_payload:
    if strategy_result.warning:
        st.warning(strategy_result.warning)

    st.markdown("<div class='section-label'>Strategia benessere</div>", unsafe_allow_html=True)
    render_wellness_strategy(strategy_result.strategy, request_payload)
    strategy_prompt_preview = build_strategy_prompt_preview(request_payload)
    render_prompt_preview_toggle(
        "Mostra prompt completo strategia AI",
        "show_strategy_prompt",
        strategy_prompt_preview,
        strategy_result.source_label,
        strategy_result.warning,
        "In questa esecuzione non e stata fatta una chiamata AI per la strategia. Qui sotto trovi comunque il prompt che l'app costruirebbe con questi dati.",
    )

    st.markdown("<div class='section-label'>Passo successivo</div>", unsafe_allow_html=True)
    strategy_action_col, source_col = st.columns([1.2, 1])
    with strategy_action_col:
        generate_diet_clicked = st.button(
            "Rigenera dieta da questa strategia" if diet_result else "Genera dieta da questa strategia",
            type="primary",
            use_container_width=True,
        )
    with source_col:
        render_metric("Fonte strategia", strategy_result.source_label, "motore usato per la strategia benessere")

    st.caption("Se modifichi i dati del profilo, rigenera prima la strategia e poi la dieta.")

    if generate_diet_clicked:
        runtime_config = AppConfig.from_env()
        with st.spinner("Sto generando la dieta settimanale a partire dalla strategia approvata..."):
            st.session_state.diet_result = generate_diet_from_strategy(
                request_payload,
                strategy_result.strategy,
                runtime_config,
            )
        diet_result = st.session_state.diet_result

        if auth_session is not None and auth_client is not None:
            try:
                persist_planning_state(
                    base_config,
                    auth_client,
                    auth_session,
                    request_payload,
                    strategy_result,
                    diet_result,
                )
            except Exception:
                st.warning(
                    "Dieta generata, ma non sono riuscito a salvarla su Supabase. Controlla schema e policy della tabella profili."
                )

    if diet_result:
        if diet_result.warning:
            st.warning(diet_result.warning)

        st.markdown("<div class='section-label'>Dieta settimanale</div>", unsafe_allow_html=True)
        diet_prompt_preview = build_plan_prompt_preview(request_payload, strategy_result.strategy)
        render_prompt_preview_toggle(
            "Mostra prompt completo dieta AI",
            "show_diet_prompt",
            diet_prompt_preview,
            diet_result.source_label,
            diet_result.warning,
            "In questa esecuzione non e stata fatta una chiamata AI per la dieta. Qui sotto trovi comunque il prompt che l'app costruirebbe con questi dati e con la strategia approvata.",
        )
        metrics = compute_plan_metrics(diet_result.plan)
        combined_source = build_source_label(strategy_result.source_label, diet_result.source_label)
        metric_cols = st.columns(4)
        with metric_cols[0]:
            render_metric("Fonte", combined_source, "motori usati per strategia e dieta")
        with metric_cols[1]:
            render_metric("Giorni attivi", str(metrics["active_cooking_days"]), "cene che richiedono vera preparazione")
        with metric_cols[2]:
            render_metric("Tempo medio cena", f"{metrics['average_dinner_minutes']} min", "ottimizzato sul vincolo selezionato")
        with metric_cols[3]:
            render_metric("Pasti con avanzi", str(metrics["leftover_slots"]), "riusi espliciti durante la settimana")

        week_tab, shopping_tab, prep_tab = st.tabs(["Settimana", "Spesa", "Prep e download"])

        with week_tab:
            for day_plan in diet_result.plan.days:
                render_day(day_plan, request_payload.person_one.name, request_payload.person_two.name)

        with shopping_tab:
            render_shopping_list(diet_result.plan)

        with prep_tab:
            render_prep(diet_result.plan)
            markdown_export = plan_to_markdown(diet_result.plan, request_payload, strategy_result.strategy)
            json_export = json.dumps(
                {
                    "strategy": strategy_result.strategy.to_dict(),
                    "plan": diet_result.plan.to_dict(),
                },
                indent=2,
                ensure_ascii=False,
            )

            st.markdown("<div class='download-shell'></div>", unsafe_allow_html=True)
            download_left, download_right = st.columns(2)
            with download_left:
                st.download_button(
                    label="Scarica piano in Markdown",
                    data=markdown_export,
                    file_name="dietapp-piano-settimanale.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            with download_right:
                st.download_button(
                    label="Scarica piano in JSON",
                    data=json_export,
                    file_name="dietapp-piano-settimanale.json",
                    mime="application/json",
                    use_container_width=True,
                )
    else:
        st.info("La strategia e pronta. Quando vuoi, clicca il pulsante sopra per generare la dieta settimanale.")
else:
    st.info(
        "Compila i profili fisiologici, descrivi l'attivita motoria e genera la strategia benessere. La dieta verra creata dopo, con un pulsante dedicato."
    )
