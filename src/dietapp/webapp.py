from __future__ import annotations

import json
from typing import Any

import streamlit as st

from dietapp.config import AppConfig
from dietapp.formatters import compute_plan_metrics, plan_to_markdown
from dietapp.persistence import (
    DEFAULT_PROFILE_VALUES,
    clear_planning_state_from_supabase,
    load_planning_state_from_supabase,
    load_profile_form_values,
    load_profile_form_values_from_supabase,
    save_profile_form_values,
    save_profile_form_values_to_supabase,
)
from dietapp.planner import (
    DietResult,
    StrategyResult,
    build_plan_prompt_preview,
    build_strategy_prompt_preview,
    generate_diet_from_strategy,
    generate_wellness_strategy,
)
from dietapp.ui.auth_flow import render_auth_gate
from dietapp.ui.forms import render_planner_form
from dietapp.ui.helpers import build_request_payload, build_source_label, same_request_payload
from dietapp.ui.rendering import (
    render_day,
    render_metric,
    render_prep,
    render_prompt_preview_toggle,
    render_provider_recovery_note,
    render_shopping_list,
    render_wellness_strategy,
)
from dietapp.ui.state import clear_planning_state, ensure_session_defaults, persist_planning_state
from dietapp.ui.styles import inject_styles, render_hero


def run_app() -> None:
    st.set_page_config(
        page_title="DietAPP | Planner settimanale",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    inject_styles()
    ensure_session_defaults()
    render_hero()

    base_config = AppConfig.from_env()
    auth_client: Any = None
    auth_session = None

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

    st.markdown("<div class='section-label'>Motore e memoria</div>", unsafe_allow_html=True)
    if base_config.get_api_key():
        st.success(
            f"Motore AI attivo da .env: {base_config.get_provider_label()} | {base_config.get_model()}"
        )
    else:
        st.info("Nessuna chiave AI valida trovata nel file .env: usero il planner locale.")
    st.caption(
        f"Il profilo della coppia si salva in {profile_storage_label}. Eta, sesso, altezza, peso, obiettivo peso, attivita e l'eventuale uso di proteine in polvere guidano prima la strategia benessere e poi il piano alimentare; con Supabase attivo vengono ricaricati anche strategia e piano compatibili con il profilo corrente."
    )

    if not base_config.has_supabase():
        st.warning(
            "Supabase non e configurato: questa istanza resta pubblica e il profilo si salva solo sul filesystem locale."
        )

    planner_form = render_planner_form(form_defaults)
    form_values = planner_form.form_values
    save_profile_clicked = planner_form.save_profile_clicked
    generate_strategy_clicked = planner_form.generate_strategy_clicked

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

        st.success(
            "Strategia generata. Se la approvi, puoi creare o rigenerare la dieta settimanale con il pulsante dedicato."
        )

    strategy_result: StrategyResult | None = st.session_state.strategy_result
    diet_result: DietResult | None = st.session_state.diet_result
    request_payload = st.session_state.request_payload

    if strategy_result and request_payload:
        if strategy_result.warning:
            st.warning(strategy_result.warning)
        render_provider_recovery_note(strategy_result.source_label, strategy_result.warning)

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
            render_metric(
                "Fonte strategia",
                strategy_result.source_label,
                "motore usato per la strategia benessere",
            )

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
            render_provider_recovery_note(diet_result.source_label, diet_result.warning)

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
                render_metric(
                    "Giorni attivi",
                    str(metrics["active_cooking_days"]),
                    "cene che richiedono vera preparazione",
                )
            with metric_cols[2]:
                render_metric(
                    "Tempo medio cena",
                    f"{metrics['average_dinner_minutes']} min",
                    "ottimizzato sul vincolo selezionato",
                )
            with metric_cols[3]:
                render_metric(
                    "Pasti con avanzi",
                    str(metrics["leftover_slots"]),
                    "riusi espliciti durante la settimana",
                )

            week_tab, shopping_tab, prep_tab = st.tabs(["Settimana", "Spesa", "Prep e download"])

            with week_tab:
                for day_plan in diet_result.plan.days:
                    render_day(day_plan, request_payload.person_one.name, request_payload.person_two.name)

            with shopping_tab:
                render_shopping_list(diet_result.plan)

            with prep_tab:
                render_prep(diet_result.plan)
                markdown_export = plan_to_markdown(
                    diet_result.plan,
                    request_payload,
                    strategy_result.strategy,
                )
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
            st.info(
                "La strategia e pronta. Quando vuoi, clicca il pulsante sopra per generare la dieta settimanale."
            )
    else:
        st.info(
            "Compila i profili fisiologici, descrivi l'attivita motoria e genera la strategia benessere. La dieta verra creata dopo, con un pulsante dedicato."
        )
