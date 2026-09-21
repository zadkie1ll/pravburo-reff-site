from src.services.deal_stages import DEFAULT_STAGE_LABEL, STAGE_LABELS, stage_label


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
