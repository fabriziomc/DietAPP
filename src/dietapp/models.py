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


@dataclass(slots=True)
class PersonProfile:
    name: str
    dietary_style: str
    age: int | None = None
    sex: str = ""
    height_cm: int | None = None
    weight_kg: float | None = None
    activity_summary: str = ""
    daily_kcal: int | None = None
    protein_target: int | None = None
    dislikes: list[str] = field(default_factory=list)
    allergies: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: Any) -> "PersonProfile":
        payload = raw if isinstance(raw, dict) else {}
        return cls(
            name=str(payload.get("name") or "Persona").strip() or "Persona",
            dietary_style=str(payload.get("dietary_style") or "Onnivoro").strip() or "Onnivoro",
            age=_coerce_int(payload.get("age")),
            sex=str(payload.get("sex") or "").strip(),
            height_cm=_coerce_int(payload.get("height_cm")),
            weight_kg=_coerce_float(payload.get("weight_kg")),
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

    @classmethod
    def from_dict(cls, raw: Any, fallback_title: str) -> "MealVariant":
        if isinstance(raw, str):
            return cls(title=fallback_title, description=raw)
        if not isinstance(raw, dict):
            return cls(title=fallback_title, description="Versione da rifinire")
        return cls(
            title=str(raw.get("title") or fallback_title),
            description=str(raw.get("description") or "Versione da rifinire"),
            ingredients=_clean_string_list(raw.get("ingredients")),
            prep_notes=str(raw.get("prep_notes") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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

    @classmethod
    def from_dict(cls, raw: Any) -> "DayPlan":
        payload = raw if isinstance(raw, dict) else {}
        return cls(
            day=str(payload.get("day") or "Giorno").strip() or "Giorno",
            breakfast=MealSlot.from_dict(payload.get("breakfast")),
            lunch=MealSlot.from_dict(payload.get("lunch")),
            dinner=MealSlot.from_dict(payload.get("dinner")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "breakfast": self.breakfast.to_dict(),
            "lunch": self.lunch.to_dict(),
            "dinner": self.dinner.to_dict(),
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

    @classmethod
    def from_dict(cls, raw: Any) -> "WeeklyPlan":
        payload = raw if isinstance(raw, dict) else {}
        raw_days = payload.get("days") if isinstance(payload.get("days"), list) else []
        return cls(
            title=str(payload.get("title") or "Piano settimanale").strip() or "Piano settimanale",
            strategy=str(payload.get("strategy") or "").strip(),
            prep_tasks=_clean_string_list(payload.get("prep_tasks")),
            planning_notes=_clean_string_list(payload.get("planning_notes")),
            shopping_list=_clean_mapping_of_string_lists(payload.get("shopping_list")),
            days=[DayPlan.from_dict(day) for day in raw_days],
            model_source=str(payload.get("model_source") or "salvato").strip() or "salvato",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "strategy": self.strategy,
            "prep_tasks": self.prep_tasks,
            "planning_notes": self.planning_notes,
            "shopping_list": self.shopping_list,
            "days": [day.to_dict() for day in self.days],
            "model_source": self.model_source,
        }
