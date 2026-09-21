from src.services.deal_stages import (
    DEFAULT_STAGE_LABEL,
    STAGE_LABELS,
    application_status_label,
    is_funnel_2_stage,
    stage_label,
)


def test_stage_label_returns_none_for_no_code() -> None:
    assert stage_label(None) is None


def test_stage_label_returns_none_for_untracked_stage() -> None:
    # "Сбор документов" в воронке "Сопровождение" - в ТЗ такого этапа нет.
    assert stage_label("C2:UC_M5ONI8") is None
    assert stage_label("C10:PREPARATION") is None


def test_stage_label_maps_funnel_stages_to_tz_stages() -> None:
    assert stage_label("C2:NEW") == "Договор подписан"
    assert stage_label("C2:UC_0Y0VBU") == "Заявление подано в суд"
    assert stage_label("C2:UC_7TR7XT") == "Процедура завершена"


def test_only_funnel_2_stages_are_tracked() -> None:
    assert all(code.startswith("C2:") for code in STAGE_LABELS)
    assert DEFAULT_STAGE_LABEL == "Заявка получена"


def test_is_funnel_2_stage() -> None:
    assert is_funnel_2_stage("C2:NEW")
    assert not is_funnel_2_stage("UC_1BEALQ")


def test_application_status_label_uses_agent_friendly_wording() -> None:
    assert application_status_label(None) == "Заявка получена"
    assert application_status_label("UC_Q6ZN5G") == "Думает"  # "Думает"
    assert application_status_label("UC_NPZOBZ") == "Пытаемся связаться"
    assert application_status_label("UC_K0Z3P6") == "Не подходит"  # "Мусор" не показываем
    assert application_status_label("UC_O7XFI5") == "Выбрал другую компанию"
    assert application_status_label("UC_1BEALQ") == "Не выходит на связь"
    assert application_status_label("WON") == "Договор заключён"
    # Этап процедуры (воронка "Сопровождение") важнее продажи.
    assert application_status_label("C2:UC_0Y0VBU") == "Заявление подано в суд"
    # Незнакомая стадия воронки продаж не должна ломать список.
    assert application_status_label("UC_SOMETHING_NEW") == "В обработке"


def test_every_sales_status_is_agent_facing_not_a_raw_bitrix_name() -> None:
    from src.services.deal_stages import SALES_STAGE_LABELS

    raw_names = {"Мусор", "Брак", "Недозвон", "Неудобно говорить", "Возражение"}
    assert raw_names.isdisjoint(set(SALES_STAGE_LABELS.values()))
