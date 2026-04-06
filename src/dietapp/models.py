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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PlanningRequest:
    person_one: PersonProfile
    person_two: PersonProfile
    preferences: HouseholdPreferences

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
