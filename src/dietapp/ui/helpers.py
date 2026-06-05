from __future__ import annotations

from typing import TypedDict

from dietapp.models import HouseholdPreferences, PersonProfile, PlanningRequest


class FormValues(TypedDict):
    person_one_name: str
    person_one_style: str
    person_one_age: int
    person_one_sex: str
    person_one_height_cm: int
    person_one_weight_kg: float
    person_one_target_weight_kg: float
    person_one_allow_protein_powder: bool
    person_one_activity: str
    person_one_dislikes: str
    person_one_allergies: str
    person_two_name: str
    person_two_style: str
    person_two_age: int
    person_two_sex: str
    person_two_height_cm: int
    person_two_weight_kg: float
    person_two_target_weight_kg: float
    person_two_allow_protein_powder: bool
    person_two_activity: str
    person_two_dislikes: str
    person_two_allergies: str
    budget: str
    max_prep_minutes: int
    leftover_lunches: int
    batch_days: list[str]
    cuisines: list[str]
    pantry_staples: list[str]
    excluded_ingredients: str
    notes: str


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
    if person.allow_protein_powder:
        parts.append("proteine in polvere ok")
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


def build_request_payload(form_values: FormValues) -> PlanningRequest:
    person_one = PersonProfile(
        name=str(form_values["person_one_name"]).strip() or "Persona 1",
        dietary_style=str(form_values["person_one_style"]),
        age=int(form_values["person_one_age"]),
        sex=str(form_values["person_one_sex"]),
        height_cm=int(form_values["person_one_height_cm"]),
        weight_kg=float(form_values["person_one_weight_kg"]),
        target_weight_kg=float(form_values["person_one_target_weight_kg"]),
        allow_protein_powder=bool(form_values["person_one_allow_protein_powder"]),
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
        allow_protein_powder=bool(form_values["person_two_allow_protein_powder"]),
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
