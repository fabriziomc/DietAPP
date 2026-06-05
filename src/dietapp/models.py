from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _clean_string_list(values: Any) -> list[str]:
    if not values:
        return []
    if isinstance(values, str):
        return [values.strip()] if values.strip() else []
    if isinstance(values, list):
        cleaned: list[str] = []
        for item in values:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                cleaned.append(text)
        return cleaned
    return [str(values).strip()]


def _clean_mapping_of_string_lists(values: Any) -> dict[str, list[str]]:
    if not isinstance(values, dict):
        return {}

    cleaned: dict[str, list[str]] = {}
    for key, raw_items in values.items():
        label = str(key).strip()
        if not label:
            continue
        cleaned[label] = _clean_string_list(raw_items)
    return cleaned


def _clean_mapping_of_ingredient_portions(values: Any) -> dict[str, list["IngredientPortion"]]:
    if not isinstance(values, dict):
        return {}

    cleaned: dict[str, list[IngredientPortion]] = {}
    for key, raw_items in values.items():
        label = str(key).strip()
        if not label:
            continue
        cleaned[label] = _clean_ingredient_portion_list(raw_items)
    return cleaned


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "si", "on"}
    return bool(value)


def _coerce_measure_quantity(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_measure_quantity(value: float | None) -> str:
    if value is None:
        return ""
    rounded_value = round(value, 1)
    if float(rounded_value).is_integer():
        return str(int(rounded_value))
    return f"{rounded_value:.1f}"


def _normalize_day_source(value: Any, default: str = "Fallback") -> str:
    text = str(value or "").strip().lower()
    if text == "ai":
        return "AI"
    if text in {"fallback", "planner locale", "locale", "local", "salvato"}:
        return "Fallback"
    return "AI" if str(default or "").strip().lower() == "ai" else "Fallback"


def _default_day_source_for_plan(model_source: str) -> str:
    return "Fallback" if model_source.strip().lower() in {"", "planner locale", "salvato"} else "AI"


@dataclass(slots=True)
class IngredientPortion:
    name: str
    quantity: float | None = None
    unit: str = ""

    @classmethod
    def from_dict(cls, raw: Any, fallback_name: str = "Ingrediente") -> "IngredientPortion":
        if isinstance(raw, str):
            return cls(name=raw.strip() or fallback_name)
        if not isinstance(raw, dict):
            return cls(name=fallback_name)
        return cls(
            name=str(raw.get("name") or raw.get("ingredient") or fallback_name).strip() or fallback_name,
            quantity=_coerce_measure_quantity(raw.get("quantity")),
            unit=str(raw.get("unit") or "").strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "quantity": self.quantity,
            "unit": self.unit,
        }

    def display_label(self) -> str:
        quantity_label = _format_measure_quantity(self.quantity)
        if quantity_label and self.unit:
            return f"{quantity_label} {self.unit} {self.name}"
        if quantity_label:
            return f"{quantity_label} {self.name}"
        return self.name


def _clean_ingredient_portion_list(values: Any) -> list[IngredientPortion]:
    if not values:
        return []
    if isinstance(values, list):
        portions = [IngredientPortion.from_dict(item) for item in values]
        return [portion for portion in portions if portion.name.strip()]
    return [IngredientPortion.from_dict(values)]


@dataclass(slots=True)
class PersonProfile:
    name: str
    dietary_style: str
    age: int | None = None
    sex: str = ""
    height_cm: int | None = None
    weight_kg: float | None = None
    target_weight_kg: float | None = None
    allow_protein_powder: bool = False
    activity_summary: str = ""
    daily_kcal: int | None = None
    protein_target: int | None = None
    dislikes: list[str] = field(default_factory=list)
    allergies: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: Any) -> "PersonProfile":
        payload = raw if isinstance(raw, dict) else {}
        target_weight_raw = payload.get("target_weight_kg")
        if target_weight_raw in (None, ""):
            target_weight_raw = payload.get("weight_kg")
        return cls(
            name=str(payload.get("name") or "Persona").strip() or "Persona",
            dietary_style=str(payload.get("dietary_style") or "Onnivoro").strip() or "Onnivoro",
            age=_coerce_int(payload.get("age")),
            sex=str(payload.get("sex") or "").strip(),
            height_cm=_coerce_int(payload.get("height_cm")),
            weight_kg=_coerce_float(payload.get("weight_kg")),
            target_weight_kg=_coerce_float(target_weight_raw),
            allow_protein_powder=_coerce_bool(payload.get("allow_protein_powder")),
            activity_summary=str(payload.get("activity_summary") or "").strip(),
            daily_kcal=_coerce_int(payload.get("daily_kcal")),
            protein_target=_coerce_int(payload.get("protein_target")),
            dislikes=_clean_string_list(payload.get("dislikes")),
            allergies=_clean_string_list(payload.get("allergies")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HouseholdPreferences:
    goal: str
    budget: str
    max_prep_minutes: int
    leftover_lunches: int
    batch_days: list[str] = field(default_factory=list)
    favorite_cuisines: list[str] = field(default_factory=list)
    pantry_staples: list[str] = field(default_factory=list)
    excluded_ingredients: list[str] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def from_dict(cls, raw: Any) -> "HouseholdPreferences":
        payload = raw if isinstance(raw, dict) else {}
        return cls(
            goal=str(payload.get("goal") or "").strip(),
            budget=str(payload.get("budget") or "Bilanciato").strip() or "Bilanciato",
            max_prep_minutes=_coerce_int(payload.get("max_prep_minutes")) or 30,
            leftover_lunches=_coerce_int(payload.get("leftover_lunches")) or 0,
            batch_days=_clean_string_list(payload.get("batch_days")),
            favorite_cuisines=_clean_string_list(payload.get("favorite_cuisines")),
            pantry_staples=_clean_string_list(payload.get("pantry_staples")),
            excluded_ingredients=_clean_string_list(payload.get("excluded_ingredients")),
            notes=str(payload.get("notes") or "").strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PlanningRequest:
    person_one: PersonProfile
    person_two: PersonProfile
    preferences: HouseholdPreferences

    @classmethod
    def from_dict(cls, raw: Any) -> "PlanningRequest":
        payload = raw if isinstance(raw, dict) else {}
        return cls(
            person_one=PersonProfile.from_dict(payload.get("person_one")),
            person_two=PersonProfile.from_dict(payload.get("person_two")),
            preferences=HouseholdPreferences.from_dict(payload.get("preferences")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "person_one": self.person_one.to_dict(),
            "person_two": self.person_two.to_dict(),
            "preferences": self.preferences.to_dict(),
        }


@dataclass(slots=True)
class PersonWellnessStrategy:
    focus: str
    rationale: str
    daily_kcal_target: int | None = None
    protein_target_g: int | None = None
    movement_guidance: str = ""
    nutrition_guidance: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: Any) -> "PersonWellnessStrategy":
        payload = raw if isinstance(raw, dict) else {}
        return cls(
            focus=str(payload.get("focus") or "Equilibrio").strip() or "Equilibrio",
            rationale=str(payload.get("rationale") or "").strip(),
            daily_kcal_target=_coerce_int(payload.get("daily_kcal_target")),
            protein_target_g=_coerce_int(payload.get("protein_target_g")),
            movement_guidance=str(payload.get("movement_guidance") or "").strip(),
            nutrition_guidance=_clean_string_list(payload.get("nutrition_guidance")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WellnessStrategy:
    title: str
    couple_summary: str
    shared_principles: list[str]
    kitchen_principles: list[str]
    person_one: PersonWellnessStrategy
    person_two: PersonWellnessStrategy
    model_source: str

    @classmethod
    def from_dict(cls, raw: Any) -> "WellnessStrategy":
        payload = raw if isinstance(raw, dict) else {}
        return cls(
            title=str(payload.get("title") or "Strategia benessere").strip() or "Strategia benessere",
            couple_summary=str(payload.get("couple_summary") or "").strip(),
            shared_principles=_clean_string_list(payload.get("shared_principles")),
            kitchen_principles=_clean_string_list(payload.get("kitchen_principles")),
            person_one=PersonWellnessStrategy.from_dict(payload.get("person_one")),
            person_two=PersonWellnessStrategy.from_dict(payload.get("person_two")),
            model_source=str(payload.get("model_source") or "salvato").strip() or "salvato",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "couple_summary": self.couple_summary,
            "shared_principles": self.shared_principles,
            "kitchen_principles": self.kitchen_principles,
            "person_one": self.person_one.to_dict(),
            "person_two": self.person_two.to_dict(),
            "model_source": self.model_source,
        }


@dataclass(slots=True)
class MealVariant:
    title: str
    description: str
    ingredients: list[str] = field(default_factory=list)
    prep_notes: str = ""
    portion_label: str = ""
    ingredient_details: list[IngredientPortion] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: Any, fallback_title: str) -> "MealVariant":
        if isinstance(raw, str):
            ingredient_details = [IngredientPortion.from_dict(raw, raw)]
            return cls(
                title=fallback_title,
                description=raw,
                ingredients=[portion.name for portion in ingredient_details],
                ingredient_details=ingredient_details,
            )
        if not isinstance(raw, dict):
            return cls(title=fallback_title, description="Versione da rifinire")
        raw_ingredient_details = raw.get("ingredient_details")
        if raw_ingredient_details is None:
            raw_ingredient_details = raw.get("ingredients")
        ingredient_details = _clean_ingredient_portion_list(raw_ingredient_details)
        ingredients = _clean_string_list(raw.get("ingredients"))
        if ingredient_details:
            ingredients = [portion.name for portion in ingredient_details]
        return cls(
            title=str(raw.get("title") or fallback_title),
            description=str(raw.get("description") or "Versione da rifinire"),
            ingredients=ingredients,
            prep_notes=str(raw.get("prep_notes") or ""),
            portion_label=str(raw.get("portion_label") or "").strip(),
            ingredient_details=ingredient_details,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "ingredients": self.ingredients,
            "prep_notes": self.prep_notes,
            "portion_label": self.portion_label,
            "ingredient_details": [portion.to_dict() for portion in self.ingredient_details],
        }


@dataclass(slots=True)
class MealSlot:
    shared_base: str
    person_one: MealVariant
    person_two: MealVariant
    prep_minutes: int
    leftover_friendly: bool
    reuse_from_previous: str = ""
    kitchen_load: str = "Basso"

    @classmethod
    def from_dict(cls, raw: Any) -> "MealSlot":
        payload = raw if isinstance(raw, dict) else {}
        return cls(
            shared_base=str(payload.get("shared_base") or "Base condivisa").strip() or "Base condivisa",
            person_one=MealVariant.from_dict(payload.get("person_one"), "Versione persona 1"),
            person_two=MealVariant.from_dict(payload.get("person_two"), "Versione persona 2"),
            prep_minutes=_coerce_int(payload.get("prep_minutes")) or 0,
            leftover_friendly=_coerce_bool(payload.get("leftover_friendly")),
            reuse_from_previous=str(payload.get("reuse_from_previous") or "").strip(),
            kitchen_load=str(payload.get("kitchen_load") or "Basso").strip() or "Basso",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "shared_base": self.shared_base,
            "person_one": self.person_one.to_dict(),
            "person_two": self.person_two.to_dict(),
            "prep_minutes": self.prep_minutes,
            "leftover_friendly": self.leftover_friendly,
            "reuse_from_previous": self.reuse_from_previous,
            "kitchen_load": self.kitchen_load,
        }


@dataclass(slots=True)
class DayPlan:
    day: str
    breakfast: MealSlot
    lunch: MealSlot
    dinner: MealSlot
    source: str = "Fallback"

    @classmethod
    def from_dict(cls, raw: Any, default_source: str = "Fallback") -> "DayPlan":
        payload = raw if isinstance(raw, dict) else {}
        return cls(
            day=str(payload.get("day") or "Giorno").strip() or "Giorno",
            breakfast=MealSlot.from_dict(payload.get("breakfast")),
            lunch=MealSlot.from_dict(payload.get("lunch")),
            dinner=MealSlot.from_dict(payload.get("dinner")),
            source=_normalize_day_source(payload.get("source"), default_source),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "breakfast": self.breakfast.to_dict(),
            "lunch": self.lunch.to_dict(),
            "dinner": self.dinner.to_dict(),
            "source": self.source,
        }


@dataclass(slots=True)
class WeeklyPlan:
    title: str
    strategy: str
    prep_tasks: list[str]
    planning_notes: list[str]
    shopping_list: dict[str, list[str]]
    days: list[DayPlan]
    model_source: str
    shopping_list_details: dict[str, list[IngredientPortion]] = field(default_factory=dict)
    coherence_checks: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: Any) -> "WeeklyPlan":
        payload = raw if isinstance(raw, dict) else {}
        raw_days_value = payload.get("days")
        raw_days = raw_days_value if isinstance(raw_days_value, list) else []
        model_source = str(payload.get("model_source") or "salvato").strip() or "salvato"
        default_day_source = _default_day_source_for_plan(model_source)
        shopping_list_details = _clean_mapping_of_ingredient_portions(payload.get("shopping_list_details"))
        if not shopping_list_details:
            shopping_list_details = _clean_mapping_of_ingredient_portions(payload.get("shopping_list"))
        shopping_list = _clean_mapping_of_string_lists(payload.get("shopping_list"))
        if not shopping_list and shopping_list_details:
            shopping_list = {
                category: [item.name for item in items]
                for category, items in shopping_list_details.items()
            }
        return cls(
            title=str(payload.get("title") or "Piano settimanale").strip() or "Piano settimanale",
            strategy=str(payload.get("strategy") or "").strip(),
            prep_tasks=_clean_string_list(payload.get("prep_tasks")),
            planning_notes=_clean_string_list(payload.get("planning_notes")),
            shopping_list=shopping_list,
            shopping_list_details=shopping_list_details,
            days=[DayPlan.from_dict(day, default_day_source) for day in raw_days],
            coherence_checks=_clean_string_list(payload.get("coherence_checks")),
            model_source=model_source,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "strategy": self.strategy,
            "prep_tasks": self.prep_tasks,
            "planning_notes": self.planning_notes,
            "shopping_list": self.shopping_list,
            "shopping_list_details": {
                category: [item.to_dict() for item in items]
                for category, items in self.shopping_list_details.items()
            },
            "days": [day.to_dict() for day in self.days],
            "coherence_checks": self.coherence_checks,
            "model_source": self.model_source,
        }
