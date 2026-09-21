from datetime import UTC, datetime
from decimal import Decimal

from pravburo_ref_common.models import Reward, RewardStatus, RewardType

from src.services.referrals import _reward_totals


def _reward(amount, status=RewardStatus.APPROVED, paid=False, reward_type=RewardType.ADVANCE):
    return Reward(
        deal_id="1",
        application_id=1,
        agent_id=1,
        reward_type=reward_type,
        amount=None if amount is None else Decimal(amount),
        status=status,
        paid_at=datetime.now(UTC) if paid else None,
    )


def test_totals_without_rewards_is_dash() -> None:
    assert _reward_totals([]) == "—"


def test_totals_split_paid_and_expected() -> None:
    rewards = [
        _reward(3000, paid=True),
        _reward(10000, reward_type=RewardType.MAIN),  # одобрено, ещё не выплачено
    ]
    assert _reward_totals(rewards) == "Выплачено: 3 000 ₽ · Ожидается: 10 000 ₽"


def test_totals_pending_decision_counts_as_expected() -> None:
    assert (
        _reward_totals([_reward(3000, status=RewardStatus.PENDING)])
        == "Выплачено: 0 ₽ · Ожидается: 3 000 ₽"
    )


def test_totals_ignore_rejected_and_amountless_rewards() -> None:
    rewards = [_reward(3000, status=RewardStatus.REJECTED), _reward(None)]
    assert _reward_totals(rewards) == "—"
