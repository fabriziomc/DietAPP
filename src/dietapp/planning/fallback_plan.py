from __future__ import annotations

import copy
import re
from typing import Any

from dietapp.defaults import BREAKFAST_TEMPLATES, DAYS, DINNER_BLUEPRINTS, LUNCH_BLUEPRINTS
from dietapp.models import (
    DayPlan,
    IngredientPortion,
    MealSlot,
    MealVariant,
    PlanningRequest,
    WeeklyPlan,
    WellnessStrategy,
)
from dietapp.planning.common import (
    BLOCKED_INGREDIENT_ALIASES,
    BUDGET_LEVELS,
    INGREDIENT_BUDGET_HINTS,
    INGREDIENT_SUBSTITUTIONS,
    KEYWORD_BUCKETS,
    _coerce_int,
    _normalize_budget_label,
    _normalize_text_token,
    _to_string_list,
)
from dietapp.planning.quantities import (
    aggregate_shopping_details,
    build_coherence_checks,
    build_ingredient_details,
    build_portion_label,
)
from dietapp.planning.strategy import (
    _protein_powder_product,
    _should_recommend_protein_powder,
    generate_fallback_wellness_strategy,
)


def generate_fallback_plan(
    request: PlanningRequest,
    strategy: WellnessStrategy | None = None,
) -> WeeklyPlan:
    resolved_strategy = strategy or generate_fallback_wellness_strategy(request)
    shopping_map: dict[str, set[str]] = {}
    days: list[DayPlan] = []
    prep_tasks = _build_prep_tasks(request, resolved_strategy)
    planning_notes = _build_planning_notes(request, resolved_strategy)
    substitution_notes: list[str] = []
    blocked_terms = _collect_blocked_terms(request)
    cuisine_preferences = _effective_cuisine_preferences(request)
    budget_label = _normalize_budget_label(request.preferences.budget)

    breakfast_templates = _prioritize_templates(
        BREAKFAST_TEMPLATES,
        request,
        blocked_terms,
        cuisine_preferences,
        budget_label,
    )
    lunch_blueprints = _prioritize_templates(
        LUNCH_BLUEPRINTS,
        request,
        blocked_terms,
        cuisine_preferences,
        budget_label,
    )
    dinner_templates = _prioritize_templates(
        DINNER_BLUEPRINTS,
        request,
        blocked_terms,
        cuisine_preferences,
        budget_label,
    )

    leftover_indexes = {1, 3, 4, 6}
    leftover_indexes = set(sorted(leftover_indexes)[: request.preferences.leftover_lunches])

    for index, day_name in enumerate(DAYS):
        breakfast_template = breakfast_templates[index % len(breakfast_templates)]
        dinner_template = dinner_templates[index % len(dinner_templates)]
        leftover_template = dinner_templates[(index - 1) % len(dinner_templates)]
        lunch_blueprint = lunch_blueprints[index % len(lunch_blueprints)]

        breakfast = _make_breakfast_slot(breakfast_template, request)
        lunch = _make_lunch_slot(
            index,
            request,
            leftover_template,
            lunch_blueprint,
            blocked_terms,
            index in leftover_indexes,
        )
        dinner = _make_dinner_slot(dinner_template, request)

        _collect_template_substitution_note(substitution_notes, breakfast_template)
        _collect_template_substitution_note(substitution_notes, lunch_blueprint)
        _collect_template_substitution_note(substitution_notes, dinner_template)

        _merge_shopping(shopping_map, breakfast_template.get("shopping", {}))
        _merge_shopping(shopping_map, dinner_template.get("shopping", {}))
        _merge_shopping(shopping_map, _shopping_from_lunch(lunch))

        days.append(
            DayPlan(
                day=day_name,
                breakfast=breakfast,
                lunch=lunch,
                dinner=dinner,
                source="Fallback",
            )
        )

    shopping_list = {category: sorted(items) for category, items in shopping_map.items()}
    shopping_list_details = aggregate_shopping_details(days)
    _apply_protein_powder_support(request, resolved_strategy, shopping_list, prep_tasks, planning_notes)
    _sync_shopping_details_with_legacy_list(shopping_list_details, shopping_list)
    strategy_text = _build_plan_strategy(request, resolved_strategy)
    coherence_checks = build_coherence_checks(days, request.preferences.max_prep_minutes)
    if substitution_notes:
        planning_notes.append(
            "Sostituzioni automatiche attivate per rispettare i vincoli piu stretti: "
            + "; ".join(substitution_notes[:4])
            + "."
        )
    return WeeklyPlan(
        title="Piano settimanale guidato dalla strategia benessere",
        strategy=strategy_text,
        prep_tasks=prep_tasks,
        planning_notes=planning_notes,
        shopping_list=shopping_list,
        days=days,
        model_source="Planner locale",
        shopping_list_details=shopping_list_details,
        coherence_checks=coherence_checks,
    )


def _make_breakfast_slot(template: dict[str, Any], request: PlanningRequest) -> MealSlot:
    person_one_title = _variant_title_for_style(template, request.person_one.dietary_style)
    person_two_title = _variant_title_for_style(template, request.person_two.dietary_style)

    return MealSlot(
        shared_base=template["shared_base"],
        person_one=_build_meal_variant(
            person_one_title,
            template["description"],
            list(template["ingredients"]),
            template["prep_notes"],
            "breakfast",
        ),
        person_two=_build_meal_variant(
            person_two_title,
            template["description"],
            list(template["ingredients"]),
            template["prep_notes"],
            "breakfast",
        ),
        prep_minutes=int(template.get("prep_minutes", 8)),
        leftover_friendly=False,
        reuse_from_previous="Ruota 2-3 basi per evitare decision fatigue la mattina.",
        kitchen_load="Molto basso",
    )


def _make_lunch_slot(
    index: int,
    request: PlanningRequest,
    leftover_template: dict[str, Any],
    lunch_blueprint: dict[str, Any],
    blocked_terms: set[str],
    use_leftovers: bool,
) -> MealSlot:
    if use_leftovers:
        person_one_leftover = _variant_for_person(leftover_template, request.person_one.dietary_style)
        person_two_leftover = _variant_for_person(leftover_template, request.person_two.dietary_style)
        return MealSlot(
            shared_base=f"Lunch box con base avanzata da {leftover_template['name'].lower()}",
            person_one=_build_meal_variant(
                f"Lunch box da {person_one_leftover['title']}",
                "Pranzo costruito sugli avanzi della cena per abbattere tempi e sprechi.",
                list(person_one_leftover["ingredients"]),
                "Porziona la sera stessa in contenitore ermetico.",
                "lunch",
                "1 lunch box",
            ),
            person_two=_build_meal_variant(
                f"Lunch box da {person_two_leftover['title']}",
                "Stessa base con variante proteica gia pronta dal giorno prima.",
                list(person_two_leftover["ingredients"]),
                "Aggiungi foglie fresche o yogurt solo al momento.",
                "lunch",
                "1 lunch box",
            ),
            prep_minutes=6,
            leftover_friendly=True,
            reuse_from_previous=leftover_template["reuse_from_previous"],
            kitchen_load="Molto basso",
        )

    grain = _select_lunch_grain(lunch_blueprint, request, blocked_terms, index)
    person_one_protein = _select_lunch_protein(
        lunch_blueprint,
        request.person_one.dietary_style,
        request.preferences.budget,
        blocked_terms,
        index,
    )
    person_two_protein = _select_lunch_protein(
        lunch_blueprint,
        request.person_two.dietary_style,
        request.preferences.budget,
        blocked_terms,
        index + 1,
    )

    person_one_title = _render_lunch_text(lunch_blueprint["title_template"], grain, person_one_protein)
    person_two_title = _render_lunch_text(lunch_blueprint["title_template"], grain, person_two_protein)
    shared_base = _render_lunch_text(lunch_blueprint["shared_base"], grain, person_one_protein)

    person_one_ingredients = _build_lunch_ingredients(lunch_blueprint, grain, person_one_protein)
    person_two_ingredients = _build_lunch_ingredients(lunch_blueprint, grain, person_two_protein)

    return MealSlot(
        shared_base=shared_base,
        person_one=_build_meal_variant(
            person_one_title,
            _lunch_description_for_style(lunch_blueprint, request.person_one.dietary_style),
            person_one_ingredients,
            str(lunch_blueprint["prep_notes"]),
            "lunch",
        ),
        person_two=_build_meal_variant(
            person_two_title,
            _lunch_description_for_style(lunch_blueprint, request.person_two.dietary_style),
            person_two_ingredients,
            str(lunch_blueprint["prep_notes"]),
            "lunch",
        ),
        prep_minutes=int(lunch_blueprint.get("prep_minutes", 10)),
        leftover_friendly=False,
        reuse_from_previous="Usa cereali, verdure e condimenti preparati nei giorni di batch cooking.",
        kitchen_load="Basso",
    )


def _make_dinner_slot(template: dict[str, Any], request: PlanningRequest) -> MealSlot:
    return MealSlot(
        shared_base=template["shared_base"],
        person_one=_meal_variant_from_template(
            _variant_for_person(template, request.person_one.dietary_style),
            "dinner",
        ),
        person_two=_meal_variant_from_template(
            _variant_for_person(template, request.person_two.dietary_style),
            "dinner",
        ),
        prep_minutes=min(int(template["prep_minutes"]), request.preferences.max_prep_minutes),
        leftover_friendly=bool(template["leftover_friendly"]),
        reuse_from_previous=str(template["reuse_from_previous"]),
        kitchen_load=str(template["kitchen_load"]),
    )


def _meal_variant_from_template(raw: dict[str, Any], meal_type: str) -> MealVariant:
    return _build_meal_variant(
        raw["title"],
        raw["description"],
        list(raw["ingredients"]),
        raw["prep_notes"],
        meal_type,
    )


def _build_meal_variant(
    title: str,
    description: str,
    ingredients: list[str],
    prep_notes: str,
    meal_type: str,
    portion_label: str | None = None,
) -> MealVariant:
    ingredient_details = build_ingredient_details(ingredients, meal_type)
    return MealVariant(
        title=title,
        description=description,
        ingredients=ingredients,
        prep_notes=prep_notes,
        portion_label=portion_label or build_portion_label(meal_type),
        ingredient_details=ingredient_details,
    )


def _variant_for_person(template: dict[str, Any], dietary_style: str) -> dict[str, Any]:
    if dietary_style.strip().lower() == "vegetariano":
        return template["vegetarian"]
    return template["omnivore"]


def _variant_title_for_style(template: dict[str, Any], dietary_style: str) -> str:
    if dietary_style.strip().lower() == "vegetariano":
        return template["vegetarian_title"]
    return template["omnivore_title"]


def _merge_shopping(shopping_map: dict[str, set[str]], raw_shopping: dict[str, list[str]]) -> None:
    for category, items in raw_shopping.items():
        shopping_map.setdefault(category, set()).update(items)


def _shopping_from_lunch(lunch: MealSlot) -> dict[str, list[str]]:
    shopping: dict[str, list[str]] = {}
    for ingredient in lunch.person_one.ingredients + lunch.person_two.ingredients:
        category = _bucket_ingredient(ingredient)
        shopping.setdefault(category, []).append(ingredient)
    return shopping


def _bucket_ingredient(ingredient: str) -> str:
    lowered = ingredient.lower()
    for category, keywords in KEYWORD_BUCKETS.items():
        if any(keyword in lowered for keyword in keywords):
            return category
    return "Extra"


def _build_shopping_list_from_days(days: list[DayPlan]) -> dict[str, list[str]]:
    shopping_map: dict[str, set[str]] = {}
    for day in days:
        for slot in (day.breakfast, day.lunch, day.dinner):
            ingredients = slot.person_one.ingredients + slot.person_two.ingredients
            for ingredient in ingredients:
                category = _bucket_ingredient(ingredient)
                shopping_map.setdefault(category, set()).add(ingredient)
    return {category: sorted(items) for category, items in shopping_map.items()}


def _normalize_shopping_list(raw: Any) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        return {}
    cleaned: dict[str, list[str]] = {}
    for category, items in raw.items():
        if isinstance(items, list):
            cleaned_items = []
            for item in items:
                if isinstance(item, dict):
                    name = str(item.get("name") or item.get("ingredient") or "").strip()
                    if name:
                        cleaned_items.append(name)
                else:
                    text = str(item).strip()
                    if text:
                        cleaned_items.append(text)
        else:
            cleaned_items = _to_string_list(items)
        if cleaned_items:
            cleaned[str(category)] = cleaned_items
    return cleaned


def _sync_shopping_details_with_legacy_list(
    shopping_list_details: dict[str, list[IngredientPortion]],
    shopping_list: dict[str, list[str]],
) -> None:
    for category, items in shopping_list.items():
        details = shopping_list_details.setdefault(category, [])
        known_names = {_normalize_text_token(detail.name) for detail in details}
        for item in items:
            if _normalize_text_token(item) in known_names:
                continue
            details.append(IngredientPortion(name=item))


def _build_plan_strategy(request: PlanningRequest, strategy: WellnessStrategy) -> str:
    batch_days = ", ".join(request.preferences.batch_days) or "nessun giorno fisso"
    favorite_cuisines = ", ".join(_effective_cuisine_preferences(request)) or "stile bilanciato"
    return (
        f"{strategy.couple_summary} In cucina la settimana privilegia basi condivise, due momenti di prep ({batch_days}), "
        f"cene entro {request.preferences.max_prep_minutes} minuti e ricette italiane orientate verso {favorite_cuisines}."
    )


def _build_prep_tasks(request: PlanningRequest, strategy: WellnessStrategy) -> list[str]:
    prep_days = ", ".join(request.preferences.batch_days) or "Domenica"
    return [
        f"Sul blocco di prep ({prep_days}) cuoci una teglia grande di verdure miste e una base di cereali.",
        f"Prepara componenti proteici coerenti con i focus: {request.person_one.name} -> {strategy.person_one.focus.lower()}, {request.person_two.name} -> {strategy.person_two.focus.lower()}.",
        "Lava e porziona verdure crude, frutta e topping per le colazioni e i lunch box.",
        "Tieni pronta almeno una salsa fresca e un dressing stabile per velocizzare i pasti principali.",
        "Porziona subito gli avanzi della cena nei contenitori destinati ai pranzi del giorno dopo.",
    ]


def _build_planning_notes(request: PlanningRequest, strategy: WellnessStrategy) -> list[str]:
    notes = [
        f"{request.person_one.name}: {strategy.person_one.focus} | target stimato {strategy.person_one.daily_kcal_target} kcal e {strategy.person_one.protein_target_g} g proteine.",
        f"{request.person_two.name}: {strategy.person_two.focus} | target stimato {strategy.person_two.daily_kcal_target} kcal e {strategy.person_two.protein_target_g} g proteine.",
        f"Budget impostato: {request.preferences.budget}.",
        "Il planner locale usa ricette italiane domestiche e adatta le scelte in base a budget e cucine preferite.",
        "Le cene sono costruite per condividere contorni, dressing e basi amidacee senza duplicare il lavoro.",
    ]
    if request.preferences.excluded_ingredients:
        notes.append(
            "Ingredienti esclusi monitorati: " + ", ".join(request.preferences.excluded_ingredients) + "."
        )
    if request.preferences.notes:
        notes.append(f"Nota famiglia: {request.preferences.notes}")
    return notes


def _apply_protein_powder_support(
    request: PlanningRequest,
    strategy: WellnessStrategy,
    shopping_list: dict[str, list[str]],
    prep_tasks: list[str],
    planning_notes: list[str],
) -> None:
    supplement_items: set[str] = set()
    supported_people: list[str] = []
    people = [
        (request.person_one, strategy.person_one),
        (request.person_two, strategy.person_two),
    ]

    for person, person_strategy in people:
        if not _should_recommend_protein_powder(person, person_strategy):
            continue

        powder_label = _protein_powder_product(person)
        supplement_items.add(powder_label)
        supported_people.append(person.name)
        planning_notes.append(
            f"{person.name}: proteine in polvere abilitate. Usa 1 porzione di {powder_label} solo nei giorni di allenamento o quando colazione e post-workout non bastano a coprire il target proteico."
        )

    if not supplement_items:
        return

    existing_items = set(shopping_list.get("Supplementi", []))
    shopping_list["Supplementi"] = sorted(existing_items | supplement_items)
    prep_tasks.append(
        "Tieni gia porzionate le proteine in polvere per "
        + ", ".join(supported_people)
        + " e usale solo come supporto pratico, non come sostituto del pasto."
    )


def _effective_cuisine_preferences(request: PlanningRequest) -> list[str]:
    preferences = ["Italiana"]
    preferences.extend(request.preferences.favorite_cuisines)
    unique_preferences: list[str] = []
    seen: set[str] = set()
    for cuisine in preferences:
        cleaned = str(cuisine).strip()
        if not cleaned:
            continue
        token = _normalize_text_token(cleaned)
        if token in seen:
            continue
        seen.add(token)
        unique_preferences.append(cleaned)
    return unique_preferences


def _collect_blocked_terms(request: PlanningRequest) -> set[str]:
    raw_terms = list(request.preferences.excluded_ingredients)
    for person in (request.person_one, request.person_two):
        raw_terms.extend(person.dislikes)
        raw_terms.extend(person.allergies)

    blocked_terms: set[str] = set()
    for term in raw_terms:
        cleaned = _normalize_text_token(term)
        if not cleaned:
            continue
        blocked_terms.add(cleaned)
        for alias in BLOCKED_INGREDIENT_ALIASES.get(cleaned, []):
            blocked_terms.add(_normalize_text_token(alias))
    return blocked_terms


def _template_conflicts_with_terms(template: dict[str, Any], blocked_terms: set[str]) -> bool:
    if not blocked_terms:
        return False
    for text in _iter_template_texts(template):
        lowered_text = _normalize_text_token(text)
        if any(term in lowered_text for term in blocked_terms):
            return True
    return False


def _iter_template_texts(template: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for key, value in template.items():
        if str(key).startswith("_"):
            continue
        texts.extend(_flatten_text_values(value))
    return texts


def _flatten_text_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    flattened_texts: list[str] = []
    if isinstance(value, list):
        for item in value:
            flattened_texts.extend(_flatten_text_values(item))
        return flattened_texts
    if isinstance(value, dict):
        for nested_value in value.values():
            flattened_texts.extend(_flatten_text_values(nested_value))
        return flattened_texts
    return [str(value)]


def _prioritize_templates(
    templates: list[dict[str, Any]],
    request: PlanningRequest,
    blocked_terms: set[str],
    cuisine_preferences: list[str],
    budget_label: str,
) -> list[dict[str, Any]]:
    compatible_templates = [
        template for template in templates if not _template_conflicts_with_terms(template, blocked_terms)
    ]
    if not compatible_templates and blocked_terms:
        compatible_templates = _adapt_templates_for_blocked_terms(templates, blocked_terms)
    if not compatible_templates:
        compatible_templates = list(templates)

    pantry_tokens = {_normalize_text_token(item) for item in request.preferences.pantry_staples}
    return sorted(
        compatible_templates,
        key=lambda template: (
            -_template_priority_score(template, request, cuisine_preferences, budget_label, pantry_tokens),
            str(template.get("name") or template.get("shared_base") or ""),
        ),
    )


def _template_priority_score(
    template: dict[str, Any],
    request: PlanningRequest,
    cuisine_preferences: list[str],
    budget_label: str,
    pantry_tokens: set[str],
) -> int:
    score = 0
    template_budget = _normalize_budget_label(str(template.get("budget_tier") or budget_label))
    score += max(0, 5 - (abs(BUDGET_LEVELS[template_budget] - BUDGET_LEVELS[budget_label]) * 2))

    template_cuisines = {
        _normalize_text_token(cuisine) for cuisine in _to_string_list(template.get("cuisines"))
    }
    for index, cuisine in enumerate(cuisine_preferences):
        if _normalize_text_token(cuisine) in template_cuisines:
            score += max(5 - index, 1) * 2
    if "italiana" in template_cuisines:
        score += 4

    prep_minutes = _coerce_int(template.get("prep_minutes"), request.preferences.max_prep_minutes)
    if prep_minutes <= request.preferences.max_prep_minutes:
        score += 3
    else:
        score -= max(1, prep_minutes - request.preferences.max_prep_minutes)

    if template.get("leftover_friendly") and request.preferences.leftover_lunches:
        score += 2

    template_tokens = {_normalize_text_token(token) for token in _iter_template_texts(template)}
    if pantry_tokens and any(token in joined_template_token for token in pantry_tokens for joined_template_token in template_tokens):
        score += 2

    if template.get("_is_substituted"):
        score -= 2

    return score


def _select_lunch_grain(
    lunch_blueprint: dict[str, Any],
    request: PlanningRequest,
    blocked_terms: set[str],
    rotation_index: int,
) -> str:
    grain_options = _to_string_list(lunch_blueprint.get("grain_options"))
    if not grain_options:
        return ""

    pantry_tokens = {_normalize_text_token(item) for item in request.preferences.pantry_staples}
    compatible_options = [
        option for option in grain_options if _normalize_text_token(option) not in blocked_terms
    ]
    if not compatible_options:
        compatible_options = list(grain_options)

    ranked_options = sorted(
        compatible_options,
        key=lambda option: (
            0 if _normalize_text_token(option) in pantry_tokens else 1,
            option,
        ),
    )
    return ranked_options[rotation_index % len(ranked_options)]


def _select_lunch_protein(
    lunch_blueprint: dict[str, Any],
    dietary_style: str,
    budget_label: str,
    blocked_terms: set[str],
    rotation_index: int,
) -> str:
    option_key = "vegetarian_options" if dietary_style.strip().lower() == "vegetariano" else "omnivore_options"
    protein_options = _to_string_list(lunch_blueprint.get(option_key))
    compatible_options = [
        option for option in protein_options if _normalize_text_token(option) not in blocked_terms
    ]
    if not compatible_options:
        compatible_options = list(protein_options)

    resolved_budget = _normalize_budget_label(budget_label)
    ranked_options = sorted(
        compatible_options,
        key=lambda option: (
            abs(
                BUDGET_LEVELS[_normalize_budget_label(INGREDIENT_BUDGET_HINTS.get(option, resolved_budget))]
                - BUDGET_LEVELS[resolved_budget]
            ),
            option,
        ),
    )
    return ranked_options[rotation_index % len(ranked_options)]


def _render_lunch_text(template_text: str, grain: str, protein: str) -> str:
    return template_text.format(grain=grain, protein=protein).replace("  ", " ").strip()


def _build_lunch_ingredients(
    lunch_blueprint: dict[str, Any],
    grain: str,
    protein: str,
) -> list[str]:
    ingredients = []
    if grain:
        ingredients.append(grain)
    ingredients.extend(_to_string_list(lunch_blueprint.get("base_ingredients")))
    if protein:
        ingredients.append(protein)
    return ingredients


def _lunch_description_for_style(lunch_blueprint: dict[str, Any], dietary_style: str) -> str:
    if dietary_style.strip().lower() == "vegetariano":
        return str(lunch_blueprint.get("vegetarian_description") or lunch_blueprint.get("omnivore_description") or "")
    return str(lunch_blueprint.get("omnivore_description") or lunch_blueprint.get("vegetarian_description") or "")


def _collect_template_substitution_note(substitution_notes: list[str], template: dict[str, Any]) -> None:
    note = str(template.get("_substitution_summary") or "").strip()
    if note and note not in substitution_notes:
        substitution_notes.append(note)


def _adapt_templates_for_blocked_terms(
    templates: list[dict[str, Any]],
    blocked_terms: set[str],
) -> list[dict[str, Any]]:
    adapted_templates: list[dict[str, Any]] = []
    for template in templates:
        adapted_template = _adapt_template_for_blocked_terms(template, blocked_terms)
        if adapted_template is not None:
            adapted_templates.append(adapted_template)
    return adapted_templates


def _adapt_template_for_blocked_terms(
    template: dict[str, Any],
    blocked_terms: set[str],
) -> dict[str, Any] | None:
    adapted_template = copy.deepcopy(template)
    applied_replacements: list[tuple[str, str]] = []
    adapted_template = _adapt_template_value(adapted_template, blocked_terms, applied_replacements)
    if _template_conflicts_with_terms(adapted_template, blocked_terms):
        return None
    if not applied_replacements:
        return None

    unique_replacements: list[tuple[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for source, target in applied_replacements:
        pair = (_normalize_text_token(source), _normalize_text_token(target))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        unique_replacements.append((source, target))

    adapted_template["_is_substituted"] = True
    adapted_template["_substitution_summary"] = ", ".join(
        f"{source} -> {target}" for source, target in unique_replacements[:3]
    )
    return adapted_template


def _adapt_template_value(
    value: Any,
    blocked_terms: set[str],
    applied_replacements: list[tuple[str, str]],
) -> Any:
    if isinstance(value, str):
        return _adapt_template_text(value, blocked_terms, applied_replacements)
    if isinstance(value, list):
        return [_adapt_template_value(item, blocked_terms, applied_replacements) for item in value]
    if isinstance(value, dict):
        adapted_mapping: dict[str, Any] = {}
        for key, nested_value in value.items():
            adapted_mapping[key] = _adapt_template_value(nested_value, blocked_terms, applied_replacements)
        return adapted_mapping
    return value


def _adapt_template_text(
    text: str,
    blocked_terms: set[str],
    applied_replacements: list[tuple[str, str]],
) -> str:
    adapted_text = text
    for source_token in sorted(INGREDIENT_SUBSTITUTIONS, key=len, reverse=True):
        if not _source_token_is_blocked(source_token, blocked_terms):
            continue
        if _normalize_text_token(source_token) not in _normalize_text_token(adapted_text):
            continue
        replacement = _choose_replacement_for_token(source_token, blocked_terms)
        if not replacement:
            continue
        updated_text = _replace_case_insensitive(adapted_text, source_token, replacement)
        if updated_text != adapted_text:
            adapted_text = updated_text
            applied_replacements.append((source_token, replacement))
    return adapted_text


def _source_token_is_blocked(source_token: str, blocked_terms: set[str]) -> bool:
    normalized_source = _normalize_text_token(source_token)
    return any(
        blocked_term == normalized_source
        or blocked_term in normalized_source
        or normalized_source in blocked_term
        for blocked_term in blocked_terms
    )


def _choose_replacement_for_token(source_token: str, blocked_terms: set[str]) -> str | None:
    for replacement in INGREDIENT_SUBSTITUTIONS.get(source_token, []):
        if not _string_conflicts_with_terms(replacement, blocked_terms):
            return replacement
    return None


def _string_conflicts_with_terms(text: str, blocked_terms: set[str]) -> bool:
    normalized_text = _normalize_text_token(text)
    return any(blocked_term in normalized_text for blocked_term in blocked_terms)


def _replace_case_insensitive(text: str, source_token: str, replacement: str) -> str:
    pattern = re.compile(re.escape(source_token), re.IGNORECASE)

    def replace_match(match: re.Match[str]) -> str:
        matched_text = match.group(0)
        if matched_text[:1].isupper():
            return replacement[:1].upper() + replacement[1:]
        return replacement

    return pattern.sub(replace_match, text)
