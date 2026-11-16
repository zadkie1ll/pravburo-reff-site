from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.services.client_workflow import WorkflowInput, stage_plan, workday_after


def example(**changes):
    return WorkflowInput.model_validate(
        {
            "contract_date": "2026-10-10",
            "first_payment": "8000",
            "advance_amount": "3000",
            "main_amount": "10000",
            **changes,
        }
    )


@pytest.mark.parametrize(
    ("start", "days", "expected"),
    [
        (date(2026, 10, 10), 5, date(2026, 10, 16)),
        (date(2026, 11, 12), 15, date(2026, 12, 3)),
        (date(2026, 11, 13), 1, date(2026, 11, 16)),
    ],
)
def test_video_deadlines_skip_weekends(start, days, expected):
    assert workday_after(start, days) == expected


def test_payment_threshold_and_full_payment_bonus_are_independent():
    below = stage_plan(example(first_payment="7999.99"), None)
    assert below["advance"]["eligible"] is False
    assert stage_plan(example(), None)["advance"]["eligible"] is True
    plan = stage_plan(example(deposit_paid_on="2026-11-12", paid_in_full=True), 123)
    assert plan["main"]["due"] == date(2026, 12, 3)
    assert plan["bonus"]["amount"] == Decimal("3000")
    assert plan["curator"]["eligible"] is True
    assert plan["main"]["amount"] == Decimal("10000")


@pytest.mark.parametrize(
    "changes",
    [
        {"first_payment": "0", "advance_paid_on": "2026-10-16"},
        {"first_payment": "7999", "deposit_paid_on": "2026-11-12"},
        {"main_paid_on": "2026-11-12"},
        {"contract_date": "2199-01-01"},
        {"first_payment": "NaN"},
    ],
)
def test_inconsistent_history_and_nonfinite_money_are_rejected(changes):
    with pytest.raises(ValidationError):
        example(**changes)


def test_manual_due_date_does_not_shift_with_default_calculation():
    plan = stage_plan(
        example(
            advance_due_on="2026-11-11", main_due_on="2026-12-10", deposit_paid_on="2026-11-12"
        ),
        None,
    )
    assert plan["advance"]["due"] == date(2026, 11, 11)
    assert plan["main"]["due"] == date(2026, 12, 10)


@pytest.mark.parametrize("status", ["not_signed", "date_unknown"])
def test_contract_without_date_never_creates_payable_stages(status):
    body = WorkflowInput(contract_status=status, first_payment="8000")
    assert body.contract_date is None
    for stage in stage_plan(body, 123).values():
        assert stage["eligible"] is False
        assert stage["due"] is None


def test_signed_unknown_date_keeps_payment_facts_without_accruing():
    body = example(
        contract_status="date_unknown",
        contract_date=None,
        deposit_paid_on="2026-11-12",
        paid_in_full=True,
    )
    assert body.deposit_paid_on == date(2026, 11, 12)
    assert all(not stage["eligible"] for stage in stage_plan(body, 123).values())


@pytest.mark.parametrize(
    "changes",
    [
        {"contract_status": "signed", "contract_date": None},
        {"contract_status": "not_signed"},
        {"contract_status": "date_unknown"},
        {"contract_status": "not_signed", "contract_date": None, "paid_in_full": True},
    ],
)
def test_contract_state_and_dates_cannot_contradict_each_other(changes):
    with pytest.raises(ValidationError):
        example(**changes)


def test_saved_workflows_without_contract_status_keep_signed_contract():
    assert example().contract_status == "signed"
