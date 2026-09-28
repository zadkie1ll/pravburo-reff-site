import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import (
    Agent,
    PartnerLevel,
    PartnerLevelMonth,
    ReferralApplication,
    Reward,
    RewardStageRate,
    RewardStatus,
    RewardType,
)
from sqlalchemy import delete

import src.services.partner_levels as partner_levels_module
from src.services.partner_levels import (
    MOSCOW_TZ,
    build_level_progress,
    contracts_word,
    get_current_month_progress,
    level_for_contracts,
    previous_month,
    run_monthly_level_close,
)


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (0, PartnerLevel.START),
        (1, PartnerLevel.START),
        (2, PartnerLevel.ACTIVE),
        (3, PartnerLevel.ACTIVE),
        (4, PartnerLevel.PRO),
        (5, PartnerLevel.PRO),
        (6, PartnerLevel.EXPERT),
        (100, PartnerLevel.EXPERT),
    ],
)
def test_level_for_contracts_thresholds(count, expected) -> None:
    assert level_for_contracts(count) == expected


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (datetime(2026, 7, 1, tzinfo=MOSCOW_TZ), (2026, 6)),
        (datetime(2026, 1, 1, tzinfo=MOSCOW_TZ), (2025, 12)),
    ],
)
def test_previous_month(today, expected) -> None:
    assert previous_month(today) == expected


async def _make_agent(session, marker: str) -> tuple[int, int]:
    agent = Agent(email=f"{marker}@example.test", display_name=f"Партнёр{marker}")
    session.add(agent)
    await session.flush()
    application = ReferralApplication(
        agent_id=agent.id,
        full_name=f"Клиент{marker}",
        phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
    )
    session.add(application)
    await session.flush()
    return agent.id, application.id


async def _make_advance(
    session,
    agent_id: int,
    application_id: int,
    *,
    created_at: datetime,
    status=RewardStatus.APPROVED,
    marker: str,
) -> int:
    reward = Reward(
        deal_id=f"deal-{marker}-{uuid.uuid4().hex[:8]}",
        application_id=application_id,
        agent_id=agent_id,
        reward_type=RewardType.ADVANCE,
        amount=Decimal("3000.00"),
        status=status,
        created_at=created_at,
    )
    session.add(reward)
    await session.flush()
    return reward.id


async def _cleanup(agent_ids: list[int]) -> None:
    async with session_factory() as session:
        await session.execute(delete(Reward).where(Reward.agent_id.in_(agent_ids)))
        await session.execute(
            delete(PartnerLevelMonth).where(PartnerLevelMonth.agent_id.in_(agent_ids))
        )
        await session.execute(
            delete(ReferralApplication).where(ReferralApplication.agent_id.in_(agent_ids))
        )
        await session.execute(delete(Agent).where(Agent.id.in_(agent_ids)))
        await session.commit()


async def test_close_month_sets_level_from_non_rejected_contracts_only() -> None:
    marker = uuid.uuid4().hex[:8]
    month_start = datetime(2026, 6, 15, tzinfo=MOSCOW_TZ)
    async with session_factory() as session:
        agent_id, application_id = await _make_agent(session, marker)
        await _make_advance(
            session, agent_id, application_id, created_at=month_start, marker=marker
        )
        await _make_advance(
            session, agent_id, application_id, created_at=month_start, marker=marker
        )
        await _make_advance(
            session, agent_id, application_id, created_at=month_start, marker=marker
        )
        await _make_advance(
            session,
            agent_id,
            application_id,
            created_at=month_start,
            status=RewardStatus.REJECTED,
            marker=marker,
        )
        # Outside the closed month - must not count.
        await _make_advance(
            session,
            agent_id,
            application_id,
            created_at=datetime(2026, 7, 2, tzinfo=MOSCOW_TZ),
            marker=marker,
        )
        await session.commit()

    try:
        async with session_factory() as session:
            await partner_levels_module._close_month(session, 2026, 6)

        async with session_factory() as session:
            row = await session.scalar(select_level_month(agent_id, 2026, 6))
            assert row is not None
            assert row.contracts_count == 3
            assert row.level == PartnerLevel.ACTIVE
            assert row.is_manual is False
    finally:
        await _cleanup([agent_id])


def select_level_month(agent_id: int, year: int, month: int):
    from sqlalchemy import select

    return select(PartnerLevelMonth).where(
        PartnerLevelMonth.agent_id == agent_id,
        PartnerLevelMonth.year == year,
        PartnerLevelMonth.month == month,
    )


async def test_close_month_does_not_overwrite_manual_row() -> None:
    marker = uuid.uuid4().hex[:8]
    month_start = datetime(2026, 6, 15, tzinfo=MOSCOW_TZ)
    async with session_factory() as session:
        agent_id, application_id = await _make_agent(session, marker)
        for _ in range(6):
            await _make_advance(
                session, agent_id, application_id, created_at=month_start, marker=marker
            )
        session.add(
            PartnerLevelMonth(
                agent_id=agent_id,
                year=2026,
                month=6,
                contracts_count=1,
                level=PartnerLevel.START,
                is_manual=True,
            )
        )
        await session.commit()

    try:
        async with session_factory() as session:
            await partner_levels_module._close_month(session, 2026, 6)

        async with session_factory() as session:
            row = await session.scalar(select_level_month(agent_id, 2026, 6))
            assert row.level == PartnerLevel.START
            assert row.contracts_count == 1
    finally:
        await _cleanup([agent_id])


async def test_backfill_main_rewards_uses_origin_month_level() -> None:
    marker = uuid.uuid4().hex[:8]
    deal_id = f"deal-{marker}"
    signed_at = datetime(2026, 6, 20, tzinfo=MOSCOW_TZ)
    async with session_factory() as session:
        agent_id, application_id = await _make_agent(session, marker)
        session.add(
            Reward(
                deal_id=deal_id,
                application_id=application_id,
                agent_id=agent_id,
                reward_type=RewardType.ADVANCE,
                amount=Decimal("3000.00"),
                created_at=signed_at,
            )
        )
        main_reward = Reward(
            deal_id=deal_id,
            application_id=application_id,
            agent_id=agent_id,
            reward_type=RewardType.MAIN,
            amount=None,
        )
        session.add(main_reward)
        session.add(
            PartnerLevelMonth(
                agent_id=agent_id,
                year=2026,
                month=6,
                contracts_count=2,
                level=PartnerLevel.ACTIVE,
            )
        )
        await session.commit()
        main_reward_id = main_reward.id

    try:
        async with session_factory() as session:
            await partner_levels_module._backfill_main_rewards(session, 2026, 6)

        async with session_factory() as session:
            reward = await session.get(Reward, main_reward_id)
            rate = await session.get(RewardStageRate, (RewardType.MAIN, PartnerLevel.ACTIVE))
            assert reward.amount == rate.amount
    finally:
        await _cleanup([agent_id])


async def test_close_quarter_creates_bonus_once_over_threshold() -> None:
    marker = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        agent_id, application_id = await _make_agent(session, marker)
        for month in (4, 5, 6):
            for _ in range(5):
                await _make_advance(
                    session,
                    agent_id,
                    application_id,
                    created_at=datetime(2026, month, 10, tzinfo=MOSCOW_TZ),
                    marker=marker,
                )
        await session.commit()

    try:
        async with session_factory() as session:
            await partner_levels_module._close_quarter_if_due(session, 2026, 6)
            # Re-running for the same closed quarter must not duplicate the bonus.
            await partner_levels_module._close_quarter_if_due(session, 2026, 6)

        async with session_factory() as session:
            from sqlalchemy import select

            rewards = (
                await session.scalars(
                    select(Reward).where(
                        Reward.agent_id == agent_id,
                        Reward.reward_type == RewardType.QUARTERLY_BONUS,
                    )
                )
            ).all()
            assert len(rewards) == 1
            assert rewards[0].amount == Decimal("15000.00")
            assert rewards[0].application_id is None
    finally:
        await _cleanup([agent_id])


async def test_run_monthly_level_close_notifies_admin_on_failure(monkeypatch) -> None:
    failure_notices: list[str] = []

    async def broken_close_month(*args, **kwargs):
        raise RuntimeError("boom")

    async def fake_notice(period):
        failure_notices.append(period)

    monkeypatch.setattr(partner_levels_module, "_close_month", broken_close_month)
    monkeypatch.setattr(
        partner_levels_module, "send_partner_level_close_failed_notice", fake_notice
    )

    await run_monthly_level_close()

    assert len(failure_notices) == 1


@pytest.mark.parametrize(
    ("count", "expected_level", "expected_fills", "next_level", "contracts_to_next"),
    [
        (0, PartnerLevel.START, [0, 0, 0], PartnerLevel.ACTIVE, 2),
        (1, PartnerLevel.START, [50, 0, 0], PartnerLevel.ACTIVE, 1),
        (2, PartnerLevel.ACTIVE, [100, 0, 0], PartnerLevel.PRO, 2),
        (3, PartnerLevel.ACTIVE, [100, 50, 0], PartnerLevel.PRO, 1),
        (4, PartnerLevel.PRO, [100, 100, 0], PartnerLevel.EXPERT, 2),
        (5, PartnerLevel.PRO, [100, 100, 50], PartnerLevel.EXPERT, 1),
        (6, PartnerLevel.EXPERT, [100, 100, 100], None, None),
        (20, PartnerLevel.EXPERT, [100, 100, 100], None, None),
    ],
)
def test_build_level_progress(
    count, expected_level, expected_fills, next_level, contracts_to_next
) -> None:
    progress = build_level_progress(count)
    assert progress.level == expected_level
    assert [segment.fill_percent for segment in progress.segments] == expected_fills
    assert progress.next_level == next_level
    assert progress.contracts_to_next == contracts_to_next


async def test_get_current_month_progress_counts_only_current_month() -> None:
    marker = uuid.uuid4().hex[:8]
    now = datetime.now(MOSCOW_TZ)
    async with session_factory() as session:
        agent = Agent(email=f"{marker}@example.test", display_name=f"Партнёр{marker}")
        session.add(agent)
        await session.flush()
        application = ReferralApplication(
            agent_id=agent.id,
            full_name=f"Клиент{marker}",
            phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
        )
        session.add(application)
        await session.flush()
        for _ in range(3):
            session.add(
                Reward(
                    deal_id=f"deal-{marker}-{uuid.uuid4().hex[:8]}",
                    application_id=application.id,
                    agent_id=agent.id,
                    reward_type=RewardType.ADVANCE,
                    amount=Decimal("3000.00"),
                    created_at=now,
                )
            )
        # A contract from last month must not count toward this month's progress.
        session.add(
            Reward(
                deal_id=f"deal-{marker}-old",
                application_id=application.id,
                agent_id=agent.id,
                reward_type=RewardType.ADVANCE,
                amount=Decimal("3000.00"),
                created_at=now - timedelta(days=400),
            )
        )
        await session.commit()
        agent_id = agent.id

    try:
        async with session_factory() as session:
            progress = await get_current_month_progress(session, agent_id)
        assert progress.contracts_count == 3
        assert progress.level == PartnerLevel.ACTIVE
    finally:
        async with session_factory() as session:
            await session.execute(delete(Reward).where(Reward.agent_id == agent_id))
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.agent_id == agent_id)
            )
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()


@pytest.mark.parametrize(
    ("count", "expected_word"),
    [
        (0, "договоров"),
        (1, "договор"),
        (2, "договора"),
        (3, "договора"),
        (4, "договора"),
        (5, "договоров"),
        (11, "договоров"),
        (12, "договоров"),
        (21, "договор"),
        (22, "договора"),
        (25, "договоров"),
    ],
)
def test_contracts_word(count, expected_word) -> None:
    assert contracts_word(count) == expected_word
