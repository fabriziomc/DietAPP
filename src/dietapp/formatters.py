from __future__ import annotations

from dietapp.models import PlanningRequest, WeeklyPlan, WellnessStrategy


def compute_plan_metrics(plan: WeeklyPlan) -> dict[str, int]:
    dinner_minutes = [day.dinner.prep_minutes for day in plan.days]
    average_dinner_minutes = round(sum(dinner_minutes) / max(len(dinner_minutes), 1))
    active_cooking_days = sum(1 for minutes in dinner_minutes if minutes >= 20)
    leftover_slots = sum(
        1
        for day in plan.days
        for slot in (day.breakfast, day.lunch, day.dinner)
        if slot.leftover_friendly or slot.reuse_from_previous
    )
    return {
        "average_dinner_minutes": average_dinner_minutes,
        "active_cooking_days": active_cooking_days,
        "leftover_slots": leftover_slots,
    }


def plan_to_markdown(
    plan: WeeklyPlan,
    request: PlanningRequest,
    strategy: WellnessStrategy | None = None,
) -> str:
    lines = [
        f"# {plan.title}",
        "",
        f"Fonte: {plan.model_source}",
        f"Coppia: {request.person_one.name} ({request.person_one.dietary_style}) + {request.person_two.name} ({request.person_two.dietary_style})",
        "",
    ]

    if strategy:
        lines.extend([
            "## Strategia benessere",
            strategy.title,
            "",
            strategy.couple_summary,
            "",
            f"- {request.person_one.name}: {strategy.person_one.focus} | target ~{strategy.person_one.daily_kcal_target or 'n.d.'} kcal | {strategy.person_one.protein_target_g or 'n.d.'} g proteine",
            f"- {request.person_two.name}: {strategy.person_two.focus} | target ~{strategy.person_two.daily_kcal_target or 'n.d.'} kcal | {strategy.person_two.protein_target_g or 'n.d.'} g proteine",
            "",
            "## Principi condivisi",
        ])
        for principle in strategy.shared_principles:
            lines.append(f"- {principle}")
        if strategy.kitchen_principles:
            lines.extend(["", "## Principi di cucina"])
            for principle in strategy.kitchen_principles:
                lines.append(f"- {principle}")
        lines.extend(["", "## Strategia del piano", plan.strategy, "", "## Prep"])
    else:
        lines.extend(["## Strategia", plan.strategy, "", "## Prep"])

    for task in plan.prep_tasks:
        lines.append(f"- {task}")

    lines.extend(["", "## Piano giornaliero"])

    for day in plan.days:
        lines.extend([
            "",
            f"### {day.day}",
            f"- Colazione: {day.breakfast.shared_base}",
            f"  - {request.person_one.name}: {day.breakfast.person_one.title}",
            f"  - {request.person_two.name}: {day.breakfast.person_two.title}",
            f"- Pranzo: {day.lunch.shared_base}",
            f"  - {request.person_one.name}: {day.lunch.person_one.title}",
            f"  - {request.person_two.name}: {day.lunch.person_two.title}",
            f"- Cena: {day.dinner.shared_base}",
            f"  - {request.person_one.name}: {day.dinner.person_one.title}",
            f"  - {request.person_two.name}: {day.dinner.person_two.title}",
        ])

    lines.extend(["", "## Lista della spesa"])
    for category, items in plan.shopping_list.items():
        lines.append(f"- {category}: {', '.join(items)}")

    if plan.planning_notes:
        lines.extend(["", "## Note operative"])
        for note in plan.planning_notes:
            lines.append(f"- {note}")

    return "\n".join(lines)
