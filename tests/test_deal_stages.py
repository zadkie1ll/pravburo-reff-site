from src.services.deal_stages import stage_label


def test_stage_label_returns_none_for_no_code() -> None:
    assert stage_label(None) is None


def test_stage_label_falls_back_to_raw_code_when_unmapped() -> None:
    assert stage_label("C2:UNKNOWN_STAGE") == "C2:UNKNOWN_STAGE"
