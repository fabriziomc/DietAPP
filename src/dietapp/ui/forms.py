from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st

from dietapp.defaults import CUISINE_OPTIONS, DAYS, PANTRY_OPTIONS
from dietapp.ui.helpers import FormValues, filter_selected_options, safe_index

STYLE_OPTIONS = ["Onnivoro", "Vegetariano"]
SEX_OPTIONS = ["Uomo", "Donna", "Altro / Non specificato"]
BUDGET_OPTIONS = ["Essenziale", "Bilanciato", "Premium"]


@dataclass(slots=True)
class PlannerFormResult:
    form_values: FormValues
    save_profile_clicked: bool
    generate_strategy_clicked: bool


def render_planner_form(form_defaults: dict[str, Any]) -> PlannerFormResult:
    batch_day_options = [DAYS[-1], *DAYS[:-1]]

    st.markdown("<div class='section-label'>Profili e vincoli</div>", unsafe_allow_html=True)

    with st.form("planner-form", clear_on_submit=False):
        left_col, right_col = st.columns(2)

        with left_col:
            person_one_name = st.text_input("Nome persona 1", value=form_defaults["person_one_name"])
            person_one_style = st.selectbox(
                "Regime persona 1",
                options=STYLE_OPTIONS,
                index=safe_index(STYLE_OPTIONS, form_defaults["person_one_style"]),
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
                options=SEX_OPTIONS,
                index=safe_index(SEX_OPTIONS, form_defaults["person_one_sex"]),
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
            person_one_allow_protein_powder = st.checkbox(
                "Consenti proteine in polvere persona 1",
                value=bool(form_defaults["person_one_allow_protein_powder"]),
                help="Il planner potra suggerirle solo se davvero utili per praticita o target proteico, soprattutto nei focus muscolari.",
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
                options=STYLE_OPTIONS,
                index=safe_index(STYLE_OPTIONS, form_defaults["person_two_style"], fallback=1),
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
                options=SEX_OPTIONS,
                index=safe_index(SEX_OPTIONS, form_defaults["person_two_sex"], fallback=1),
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
            person_two_allow_protein_powder = st.checkbox(
                "Consenti proteine in polvere persona 2",
                value=bool(form_defaults["person_two_allow_protein_powder"]),
                help="Il planner potra suggerirle solo se davvero utili per praticita o target proteico, soprattutto nei focus muscolari.",
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
                options=BUDGET_OPTIONS,
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

    return PlannerFormResult(
        form_values={
            "person_one_name": person_one_name,
            "person_one_style": person_one_style,
            "person_one_age": person_one_age,
            "person_one_sex": person_one_sex,
            "person_one_height_cm": person_one_height_cm,
            "person_one_weight_kg": person_one_weight_kg,
            "person_one_target_weight_kg": person_one_target_weight_kg,
            "person_one_allow_protein_powder": person_one_allow_protein_powder,
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
            "person_two_allow_protein_powder": person_two_allow_protein_powder,
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
        },
        save_profile_clicked=save_profile_clicked,
        generate_strategy_clicked=generate_strategy_clicked,
    )
