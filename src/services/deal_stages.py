"""Bitrix deal stage codes (воронка "Агенты", category_id=10) mapped to a
partner-facing label. An unmapped code is shown as-is rather than failing.
"""

STAGE_LABELS: dict[str, str] = {
    "C10:NEW": "Заявление ещё не подано",
    "C10:PREPARATION": "Заявление подано",
    "C10:PREPAYMENT_INVOIC": "Дело признано судом",
    "C10:EXECUTING": "Дело завершено",
    "C10:FINAL_INVOICE": "Дело завершено (более года)",
    "C10:UC_MWJRTR": "Клиент отказался от услуг",
    "C10:WON": "Клиент успешно прошёл процедуру",
    "C10:LOSE": "К сожалению, довести дело до конца не получилось",
    "C10:APOLOGY": "Уточняем детали по этому делу",
}


def stage_label(stage_code: str | None) -> str | None:
    if not stage_code:
        return None
    return STAGE_LABELS.get(stage_code, stage_code)
