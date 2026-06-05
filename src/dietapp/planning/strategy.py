from __future__ import annotations

from dietapp.models import PersonProfile, PersonWellnessStrategy, PlanningRequest, WellnessStrategy
from dietapp.planning.common import (
    HIGH_ACTIVITY_KEYWORDS,
    LIGHT_ACTIVITY_KEYWORDS,
    MODERATE_ACTIVITY_KEYWORDS,
    SEDENTARY_KEYWORDS,
    WEIGHT_GOAL_TOLERANCE_KG,
    _round_to_step,
)


def generate_fallback_wellness_strategy(request: PlanningRequest) -> WellnessStrategy:
    person_one_strategy = _build_local_person_strategy(request.person_one)
    person_two_strategy = _build_local_person_strategy(request.person_two)
    batch_days = ", ".join(request.preferences.batch_days) or "nessun giorno fisso"

    shared_principles = [
        "Ogni pasto principale deve avere una fonte proteica chiara e una quota abbondante di fibre.",
        "La sazieta viene costruita con verdure, legumi, cereali gestibili e proteine distribuite nella giornata.",
        "Le colazioni restano semplici e ripetibili per ridurre attrito decisionale durante la settimana.",
    ]
    kitchen_principles = [
        f"Cene entro {request.preferences.max_prep_minutes} minuti quando possibile.",
        f"Batch cooking concentrato su: {batch_days}.",
        f"Riutilizzo degli avanzi per circa {request.preferences.leftover_lunches} pranzi settimanali.",
    ]
    couple_summary = (
        f"Strategia costruita per sostenere {request.person_one.name} con un focus su {person_one_strategy.focus.lower()} "
        f"e {request.person_two.name} con un focus su {person_two_strategy.focus.lower()}, mantenendo una cucina unica, "
        "ingredienti ricorrenti e varianti proteiche separate solo dove serve."
    )
    return WellnessStrategy(
        title="Strategia benessere personalizzata per la coppia",
        couple_summary=couple_summary,
        shared_principles=shared_principles,
        kitchen_principles=kitchen_principles,
        person_one=person_one_strategy,
        person_two=person_two_strategy,
        model_source="Planner locale",
    )


def _build_local_person_strategy(person: PersonProfile) -> PersonWellnessStrategy:
    activity_factor, activity_label = _estimate_activity_factor(person.activity_summary)
    bmi = _estimate_bmi(person.weight_kg, person.height_cm)
    tdee = _estimate_tdee(person, activity_factor)
    focus, calorie_adjustment = _infer_focus_and_adjustment(person, bmi, activity_factor)
    daily_kcal_target = _round_to_step(max(_minimum_calories(person.sex), tdee + calorie_adjustment), 50)
    protein_multiplier = _protein_multiplier_for_focus(focus, person.dietary_style)
    reference_weight = person.weight_kg if person.weight_kg is not None else 70.0
    protein_target = _round_to_step(reference_weight * protein_multiplier, 5)

    bmi_copy = f"BMI stimato {bmi:.1f}" if bmi is not None else "composizione corporea stimata"
    rationale_parts = []
    weight_goal_rationale = _build_weight_goal_rationale(person)
    if weight_goal_rationale:
        rationale_parts.append(weight_goal_rationale)
    rationale_parts.append(
        f"Eta, {bmi_copy} e attivita {activity_label} suggeriscono di puntare a {focus.lower()}, "
        "usando un approccio sostenibile e pasti facili da ripetere durante la settimana."
    )
    rationale = " ".join(rationale_parts)
    return PersonWellnessStrategy(
        focus=focus,
        rationale=rationale,
        daily_kcal_target=int(daily_kcal_target),
        protein_target_g=int(protein_target),
        movement_guidance=_build_movement_guidance(person.activity_summary, focus),
        nutrition_guidance=_build_nutrition_guidance(person, focus),
    )


def _estimate_activity_factor(activity_summary: str) -> tuple[float, str]:
    summary = activity_summary.lower()
    if any(keyword in summary for keyword in HIGH_ACTIVITY_KEYWORDS):
        return 1.75, "alta"
    if any(keyword in summary for keyword in MODERATE_ACTIVITY_KEYWORDS):
        return 1.55, "moderata"
    if any(keyword in summary for keyword in LIGHT_ACTIVITY_KEYWORDS):
        return 1.375, "leggera"
    if any(keyword in summary for keyword in SEDENTARY_KEYWORDS):
        return 1.2, "bassa"
    if summary.strip():
        return 1.4, "intermedia"
    return 1.3, "non specificata"


def _estimate_bmi(weight_kg: float | None, height_cm: int | None) -> float | None:
    if not weight_kg or not height_cm:
        return None
    if height_cm <= 0:
        return None
    height_m = height_cm / 100
    return weight_kg / (height_m * height_m)


def _estimate_tdee(person: PersonProfile, activity_factor: float) -> float:
    weight_kg = person.weight_kg if person.weight_kg is not None else 70.0
    height_cm = person.height_cm if person.height_cm is not None else 170
    age = person.age if person.age is not None else 35

    sex_value = person.sex.strip().lower()
    if sex_value == "uomo":
        sex_offset = 5
    elif sex_value == "donna":
        sex_offset = -161
    else:
        sex_offset = -78

    bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + sex_offset
    return bmr * activity_factor


def _weight_goal_delta(person: PersonProfile) -> float | None:
    if person.weight_kg is None or person.target_weight_kg is None:
        return None
    return person.target_weight_kg - person.weight_kg


def _weight_goal_direction(person: PersonProfile) -> str:
    delta = _weight_goal_delta(person)
    if delta is None or abs(delta) < WEIGHT_GOAL_TOLERANCE_KG:
        return "maintain"
    return "gain" if delta > 0 else "lose"


def _format_weight_label(value: float | None) -> str:
    if value is None:
        return "n.d."
    rounded_value = round(value, 1)
    if float(rounded_value).is_integer():
        return f"{int(rounded_value)} kg"
    return f"{rounded_value:.1f} kg"


def _build_weight_goal_rationale(person: PersonProfile) -> str:
    delta = _weight_goal_delta(person)
    if delta is None or abs(delta) < WEIGHT_GOAL_TOLERANCE_KG:
        return ""
    if delta < 0:
        return (
            f"L'obiettivo peso dichiarato e scendere da {_format_weight_label(person.weight_kg)} "
            f"a {_format_weight_label(person.target_weight_kg)}."
        )
    return (
        f"L'obiettivo peso dichiarato e salire da {_format_weight_label(person.weight_kg)} "
        f"a {_format_weight_label(person.target_weight_kg)}."
    )


def _infer_focus_and_adjustment(person: PersonProfile, bmi: float | None, activity_factor: float) -> tuple[str, int]:
    goal_direction = _weight_goal_direction(person)
    goal_delta = _weight_goal_delta(person) or 0.0

    if goal_direction == "lose":
        if goal_delta <= -8:
            return "Dimagrimento graduale e alta sazieta", -450 if activity_factor < 1.5 else -350
        if goal_delta <= -3:
            return "Dimagrimento graduale e ricomposizione", -350 if activity_factor < 1.55 else -250
        return "Ricomposizione e lieve dimagrimento", -200

    if goal_direction == "gain":
        if goal_delta >= 8:
            focus = "Aumento di peso graduale e costruzione muscolare"
            calorie_adjustment = 300 if activity_factor >= 1.4 else 250
        elif goal_delta >= 3:
            focus = "Aumento di peso controllato e supporto muscolare"
            calorie_adjustment = 250 if activity_factor >= 1.5 else 200
        else:
            focus = "Recupero energetico e lieve aumento di peso"
            calorie_adjustment = 150

        if bmi is not None and bmi < 20.5:
            calorie_adjustment = max(calorie_adjustment, 250)
        return focus, calorie_adjustment

    if bmi is not None and bmi >= 30:
        return "Dimagrimento graduale e alta sazieta", -400
    if bmi is not None and bmi >= 25:
        if activity_factor >= 1.55:
            return "Ricomposizione corporea e tono muscolare", -200
        return "Dimagrimento leggero e ricomposizione", -300
    if bmi is not None and bmi < 21 and activity_factor >= 1.5:
        return "Energia e costruzione muscolare leggera", 200
    if activity_factor >= 1.6:
        return "Supporto a performance e tono muscolare", 100
    return "Mantenimento e tono muscolare", 0


def _protein_multiplier_for_focus(focus: str, dietary_style: str) -> float:
    lowered_focus = focus.lower()
    multiplier = 1.5
    if "dimagrimento" in lowered_focus:
        multiplier = 1.8
    elif "ricomposizione" in lowered_focus or "tono" in lowered_focus:
        multiplier = 1.7
    elif "muscolare" in lowered_focus or "performance" in lowered_focus:
        multiplier = 1.8
    elif "aumento di peso" in lowered_focus or "recupero energetico" in lowered_focus:
        multiplier = 1.6

    if dietary_style.strip().lower() == "vegetariano":
        multiplier += 0.1
    return multiplier


def _protein_powder_product(person: PersonProfile) -> str:
    lowered_allergies = " ".join(person.allergies).lower()
    if person.dietary_style.strip().lower() == "vegetariano" or any(
        term in lowered_allergies for term in ("lattosio", "latte", "whey")
    ):
        return "proteine vegetali in polvere"
    return "proteine whey in polvere"


def _should_recommend_protein_powder(
    person: PersonProfile,
    person_strategy: PersonWellnessStrategy,
) -> bool:
    if not person.allow_protein_powder:
        return False

    lowered_focus = person_strategy.focus.lower()
    reference_weight = person.weight_kg if person.weight_kg is not None else 70.0
    protein_target = person_strategy.protein_target_g or 0

    if any(
        term in lowered_focus
        for term in ("aumento di peso", "recupero energetico", "muscolare", "performance", "ricomposizione")
    ):
        return True
    if protein_target >= reference_weight * 1.8:
        return True
    if person.dietary_style.strip().lower() == "vegetariano" and protein_target >= reference_weight * 1.6:
        return True
    return False


def _build_protein_powder_guidance(person: PersonProfile, focus: str) -> str | None:
    if not person.allow_protein_powder:
        return None

    powder_label = _protein_powder_product(person)
    lowered_focus = focus.lower()
    if any(
        term in lowered_focus
        for term in ("aumento di peso", "recupero energetico", "muscolare", "performance", "ricomposizione")
    ):
        return (
            f"Se con i soli pasti fai fatica a raggiungere il target, puoi usare {powder_label} "
            "in modo pratico, preferibilmente a colazione o nel post-allenamento, senza superare una porzione al giorno."
        )
    return (
        f"Le {powder_label} restano opzionali: usale solo quando una giornata resta troppo bassa in proteine, "
        "senza sostituire i pasti principali."
    )


def _minimum_calories(sex: str) -> int:
    normalized = sex.strip().lower()
    if normalized == "uomo":
        return 1600
    if normalized == "donna":
        return 1300
    return 1450


def _build_movement_guidance(activity_summary: str, focus: str) -> str:
    lowered_activity = activity_summary.lower()
    lowered_focus = focus.lower()

    if "dimagrimento" in lowered_focus and any(keyword in lowered_activity for keyword in SEDENTARY_KEYWORDS):
        return "Mantieni i pasti sazianti e prova ad aggiungere camminate quotidiane o 2-3 sessioni leggere di forza."
    if "aumento di peso" in lowered_focus or "recupero energetico" in lowered_focus:
        return "Accompagna il surplus con 2-4 sessioni di forza e cura recupero, sonno e regolarita dei pasti."
    if "performance" in lowered_focus or "muscolare" in lowered_focus:
        return "Distribuisci bene i pasti nei giorni di allenamento e cura recupero, sonno e idratazione."
    if any(keyword in lowered_activity for keyword in LIGHT_ACTIVITY_KEYWORDS):
        return "L'attivita descritta e gia utile: costruisci regolarita nei pasti e una buona routine di recupero."
    return "Tieni una routine motoria regolare e usa il piano alimentare per sostenere energia, recupero e continuita."


def _build_nutrition_guidance(person: PersonProfile, focus: str) -> list[str]:
    guidance = [
        "Mantieni una fonte proteica in colazione, pranzo e cena per dare struttura alla giornata.",
        "Concentra fibre e verdure soprattutto a pranzo e cena per migliorare sazieta e qualita complessiva.",
    ]

    lowered_focus = focus.lower()
    if "dimagrimento" in lowered_focus:
        guidance.append("Usa pasti voluminosi, condimenti misurati e snack facili da controllare, evitando deficit estremi.")
    elif "aumento di peso" in lowered_focus or "recupero energetico" in lowered_focus:
        guidance.append(
            "Aumenta l'energia con porzioni progressivamente piu ricche, carboidrati gestibili e uno snack strategico, senza ricorrere a pasti enormi."
        )
    elif "muscolare" in lowered_focus or "performance" in lowered_focus:
        guidance.append("Inserisci carboidrati gestibili intorno agli allenamenti e una quota proteica stabile nel post-workout.")
    else:
        guidance.append("Lavora su regolarita, porzioni coerenti e rotazione semplice delle stesse basi durante la settimana.")

    if person.dietary_style.strip().lower() == "vegetariano":
        guidance.append("Distribuisci bene legumi, tofu, uova e latticini per mantenere costante la quota proteica vegetariana.")
    else:
        guidance.append("Alterna carni magre, uova, latticini e legumi per non dipendere sempre dalla stessa fonte proteica.")

    protein_powder_guidance = _build_protein_powder_guidance(person, focus)
    if protein_powder_guidance:
        guidance.append(protein_powder_guidance)

    return guidance
