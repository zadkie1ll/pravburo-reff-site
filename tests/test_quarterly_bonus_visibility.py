import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, Reward, RewardStatus, RewardType
from sqlalchemy import delete, select

import src.services.payout_reminders as reminders_module
from src.services.admin_payouts import list_payout_rows
from src.services.payouts import PayoutFilters, get_payout_rows
from src.services.referrals import get_network_client_rows


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


async def _make_agent_with_quarterly_bonus(*, status=RewardStatus.PENDING) -> tuple[int, str]:
    deal_id = f"quarterly:{uuid.uuid4().hex[:8]}:2026Q3"
    async with session_factory() as session:
        agent = Agent(email=f"{uuid.uuid4()}@example.test", display_name="Партнёр")
        session.add(agent)
        await session.flush()
        session.add(
            Reward(
                deal_id=deal_id,
                application_id=None,
                agent_id=agent.id,
                reward_type=RewardType.QUARTERLY_BONUS,
                amount=Decimal("15000.00"),
                status=status,
            )
        )
        await session.commit()
        return agent.id, deal_id


async def _cleanup(agent_id: int) -> None:
    async with session_factory() as session:
        await session.execute(delete(Reward).where(Reward.agent_id == agent_id))
        await session.execute(delete(Agent).where(Agent.id == agent_id))
        await session.commit()


async def test_partner_payouts_list_shows_quarterly_bonus() -> None:
    agent_id, _ = await _make_agent_with_quarterly_bonus()
    try:
        async with session_factory() as session:
            rows = await get_payout_rows(session, agent_id, PayoutFilters())
        assert [row.type_label for row in rows] == ["Квартальный бонус"]
        assert rows[0].client_name == "—"
        assert "15" in rows[0].amount_label
    finally:
        await _cleanup(agent_id)


async def test_admin_payouts_list_shows_quarterly_bonus() -> None:
    agent_id, _ = await _make_agent_with_quarterly_bonus()
    try:
        async with session_factory() as session:
            rows = await list_payout_rows(session)
        mine = [row for row in rows if row.reward.agent_id == agent_id]
        assert len(mine) == 1
        assert mine[0].type_label == "Квартальный бонус"
        assert mine[0].client_name == "—"
    finally:
        await _cleanup(agent_id)


async def test_network_client_rows_ignore_quarterly_bonus() -> None:
    agent_id, _ = await _make_agent_with_quarterly_bonus()
    try:
        async with session_factory() as session:
            rows = await get_network_client_rows(session, agent_id)
        assert rows == []
    finally:
        await _cleanup(agent_id)


async def test_payout_reminders_include_approved_quarterly_bonus(monkeypatch) -> None:
    agent_id, deal_id = await _make_agent_with_quarterly_bonus(status=RewardStatus.APPROVED)
    async with session_factory() as session:
        reward = await session.scalar(select(Reward).where(Reward.deal_id == deal_id))
        reward.decided_at = datetime.now(UTC) - timedelta(days=60)
        await session.commit()

    notices: list[tuple] = []

    async def fake_due(reward, agent, client_name, target_date):
        notices.append((reward.deal_id, client_name))

    async def fake_overdue(reward, agent, client_name, target_date, days_overdue):
        notices.append((reward.deal_id, client_name))

    monkeypatch.setattr(reminders_module, "send_payout_due_notice", fake_due)
    monkeypatch.setattr(reminders_module, "send_payout_overdue_notice", fake_overdue)

    try:
        await reminders_module.check_payout_reminders()
        assert (deal_id, "—") in notices
    finally:
        await _cleanup(agent_id)
