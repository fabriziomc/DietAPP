from __future__ import annotations

from html import escape
from textwrap import dedent

import streamlit as st

from dietapp.models import (
    DayPlan,
    IngredientPortion,
    MealSlot,
    PlanningRequest,
    WeeklyPlan,
    WellnessStrategy,
)
from dietapp.ui.helpers import describe_person_profile


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


def build_provider_recovery_note(source_label: str, warning: str | None) -> tuple[str, str] | None:
    if not warning or source_label == "Planner locale" or "come fallback" not in warning:
        return None

    if source_label.startswith("Groq |") and "OpenRouter |" in warning:
        return (
            "Fallback OpenRouter -> Groq",
            "OpenRouter non ha risposto correttamente; questa risposta arriva da Groq invece che dal planner locale.",
        )

    return (
        "Provider di recupero attivo",
        f"Questa risposta arriva da {source_label} dopo un errore del provider tentato in precedenza.",
    )


def render_provider_recovery_note(source_label: str, warning: str | None) -> None:
    note = build_provider_recovery_note(source_label, warning)
    if note is None:
        return

    label, description = note
    st.markdown(
        dedent(
            f"""
        <div class="provider-recovery-note">
            <span class="tag tag-provider-recovery">{escape(label)}</span>
            <div class="provider-recovery-text">{escape(description)}</div>
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


def render_meal_card(slot_label: str, meal: MealSlot, person_one_name: str, person_two_name: str) -> None:
    tags = [f"{meal.prep_minutes} min", meal.kitchen_load]
    if meal.leftover_friendly:
        tags.append("avanzi")

    tag_markup = "".join(f'<span class="tag">{escape(tag)}</span>' for tag in tags)
    shared_base = escape(meal.shared_base)

    person_one_ingredients = _format_ingredient_list(meal.person_one.ingredient_details, meal.person_one.ingredients)
    person_two_ingredients = _format_ingredient_list(meal.person_two.ingredient_details, meal.person_two.ingredients)
    person_one_portion = escape(meal.person_one.portion_label or "1 porzione")
    person_two_portion = escape(meal.person_two.portion_label or "1 porzione")

    person_one_block = dedent(
        f"""
        <div class="meal-variant">
            <div class="meal-person">{escape(person_one_name)}</div>
            <div class="meal-name">{escape(meal.person_one.title)}</div>
            <div class="meal-text">{escape(meal.person_one.description)}</div>
            <div class="meal-text">Porzione: {person_one_portion}</div>
            <div class="meal-text">Ingredienti: {escape(person_one_ingredients)}</div>
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
            <div class="meal-text">Porzione: {person_two_portion}</div>
            <div class="meal-text">Ingredienti: {escape(person_two_ingredients)}</div>
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


def build_day_reuse_badge(day_plan: DayPlan) -> str:
    if day_plan.lunch.reuse_from_previous:
        return day_plan.lunch.reuse_from_previous
    if day_plan.breakfast.reuse_from_previous:
        return day_plan.breakfast.reuse_from_previous
    return "rotazione smart"


def get_day_source_badge(day_plan: DayPlan) -> tuple[str, str]:
    source = str(getattr(day_plan, "source", "") or "").strip().lower()
    if source == "ai":
        return "AI", "tag-source-ai"
    return "Fallback", "tag-source-fallback"


def render_day(day_plan: DayPlan, person_one_name: str, person_two_name: str) -> None:
    source_label, source_class = get_day_source_badge(day_plan)
    st.markdown(
        dedent(
            f"""
        <div class="day-shell">
            <div class="day-title">
                <div class="day-heading">
                    <h3>{escape(day_plan.day)}</h3>
                    <span class="tag {escape(source_class)}">{escape(source_label)}</span>
                </div>
                <div class="tag">Riutilizzo: {escape(build_day_reuse_badge(day_plan))}</div>
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
    shopping_details = plan.shopping_list_details or {
        category: [IngredientPortion(name=item) for item in items]
        for category, items in plan.shopping_list.items()
    }
    categories = list(shopping_details.items())
    if not categories:
        st.info("La lista della spesa verra popolata quando generi un piano.")
        return

    columns = st.columns(2)
    for index, (category, items) in enumerate(categories):
        with columns[index % 2]:
            item_markup = "".join(f"<li>{escape(item.display_label())}</li>" for item in items)
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
    checks_markup = "".join(f"<li>{escape(check)}</li>" for check in plan.coherence_checks)
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
            <h4>Controlli automatici</h4>
            <ul>{checks_markup}</ul>
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


def _format_ingredient_list(
    ingredient_details: list[IngredientPortion],
    fallback_ingredients: list[str],
) -> str:
    if ingredient_details:
        return ", ".join(detail.display_label() for detail in ingredient_details)
    return ", ".join(fallback_ingredients)