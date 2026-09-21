import uuid
from datetime import UTC, datetime

import pytest
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import (
    Agent,
    ReferralApplication,
    Reward,
    RewardStatus,
    RewardType,
)
from sqlalchemy import delete

from src.services.payouts import PayoutFilters, get_payout_rows


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


def _application(agent_id: int, name: str, stage_code: str | None = None):
    return ReferralApplication(
        agent_id=agent_id,
        full_name=name,
        phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
        deal_stage_code=stage_code,
    )


async def test_payout_rows_combine_rewards_and_clients_without_reward() -> None:
    async with session_factory() as session:
        agent = Agent(email=f"{uuid.uuid4()}@example.test", display_name="Партнёр")
        session.add(agent)
        await session.flush()
        paid = _application(agent.id, "Клиент с выплатой")
        rejected = _application(agent.id, "Клиент с отказом")
        analysis = _application(agent.id, "Клиент в работе")
        deposit = _application(agent.id, "Клиент платит депозит", "UC_4FX5NE")
        ignored = _application(agent.id, "Клиент пропал", "UC_1BEALQ")
        session.add_all([paid, rejected, analysis, deposit, ignored])
        await session.flush()
        session.add_all(
            [
                Reward(
                    deal_id=str(uuid.uuid4()),
                    application_id=paid.id,
                    agent_id=agent.id,
                    reward_type=RewardType.ADVANCE,
                    amount=3000,
                    status=RewardStatus.APPROVED,
                    paid_at=datetime.now(UTC),
                ),
                Reward(
                    deal_id=str(uuid.uuid4()),
                    application_id=rejected.id,
                    agent_id=agent.id,
                    reward_type=RewardType.ADVANCE,
                    amount=3000,
                    status=RewardStatus.REJECTED,
                    rejection_reason="Клиент отказался от услуг",
                ),
            ]
        )
        await session.commit()
        agent_id = agent.id
        application_ids = [a.id for a in (paid, rejected, analysis, deposit, ignored)]

    try:
        async with session_factory() as session:
            rows = await get_payout_rows(session, agent_id, PayoutFilters())
            ignored_only = await get_payout_rows(session, agent_id, PayoutFilters(status="ignored"))
            by_month = await get_payout_rows(
                session, agent_id, PayoutFilters(month=datetime.now(UTC).strftime("%Y-%m"))
            )
    finally:
        async with session_factory() as session:
            await session.execute(delete(Reward).where(Reward.agent_id == agent_id))
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id.in_(application_ids))
            )
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()

    statuses = {row.client_name: row.status_label for row in rows}
    assert statuses == {
        "Клиент с выплатой": "Выплачено",
        "Клиент с отказом": "Отклонено",
        "Клиент в работе": "Анализ ситуации",
        "Клиент платит депозит": "Оплата депозита",
        "Клиент пропал": "Ушел в игнор",
    }
    rejected_row = next(row for row in rows if row.client_name == "Клиент с отказом")
    assert rejected_row.rejection_reason == "Клиент отказался от услуг"
    assert [row.client_name for row in ignored_only] == ["Клиент пропал"]
    # Фильтр по месяцу выплаты: остаются только строки с выплатой, без клиентов "в работе".
    assert {row.client_name for row in by_month} == {"Клиент с выплатой"}
