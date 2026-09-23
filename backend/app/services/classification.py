from ..models.academic import AcademicModule

FIRST_THRESHOLD = 70.0
UPPER_SECOND_THRESHOLD = 60.0
LOWER_SECOND_THRESHOLD = 50.0
THIRD_THRESHOLD = 40.0

METHODOLOGY_NOTE = (
    "Weighted-mean estimate only (Level 1 excluded, Level 3 credits carry double "
    "the weight of Level 2 credits, First threshold 70%). Sheffield also runs a "
    "secondary check on the distribution of your weighted module grades, so one "
    "low module can't be fully offset by strong ones elsewhere — that check is "
    "not replicated here. Treat this number as directional, not a confirmed "
    "classification."
)


def _module_mark(module: AcademicModule) -> tuple[float | None, bool]:
    graded = [a for a in module.assessments if a.mark_pct is not None]
    if not graded:
        return None, False
    total_weight = sum(a.weight_pct for a in graded)
    if total_weight <= 0:
        return None, False
    mark = sum(a.mark_pct * a.weight_pct for a in graded) / total_weight
    fully_graded = len(graded) == len(module.assessments)
    return mark, fully_graded


def _band(overall: float | None) -> str | None:
    if overall is None:
        return None
    if overall >= FIRST_THRESHOLD:
        return "First"
    if overall >= UPPER_SECOND_THRESHOLD:
        return "Upper Second (2:1)"
    if overall >= LOWER_SECOND_THRESHOLD:
        return "Lower Second (2:2)"
    if overall >= THIRD_THRESHOLD:
        return "Third"
    return "Fail"


def classify(modules: list[AcademicModule]) -> dict:
    weighted_sum = 0.0
    weight_total = 0.0
    breakdown = []

    for module in modules:
        if module.fheq_level == 1:
            continue

        mark, fully_graded = _module_mark(module)
        # A module whose level or credit value isn't confirmed yet can't be
        # weighted without guessing - list it (flagged), but keep it out of
        # the average rather than inventing a weight.
        needs_level_credits = module.fheq_level is None or module.credits is None
        breakdown.append(
            {
                "module_id": module.id,
                "name": module.name,
                "fheq_level": module.fheq_level,
                "credits": module.credits,
                "mark_pct": mark,
                "fully_graded": fully_graded,
                "needs_level_credits": needs_level_credits,
            }
        )
        if mark is not None and not needs_level_credits:
            credit_weight = module.credits * (2 if module.fheq_level == 3 else 1)
            weighted_sum += mark * credit_weight
            weight_total += credit_weight

    overall = weighted_sum / weight_total if weight_total > 0 else None

    return {
        "weighted_average_pct": overall,
        "classification_estimate": _band(overall),
        "modules": breakdown,
        "methodology_note": METHODOLOGY_NOTE,
    }
