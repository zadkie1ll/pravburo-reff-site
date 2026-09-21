import uuid

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

from src.services.referrals import get_link_stats


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


def _application(agent_id: int, name: str) -> ReferralApplication:
    return ReferralApplication(
        agent_id=agent_id,
        full_name=name,
        phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
    )


def _reward(application_id: int, agent_id: int, reward_type: RewardType, status: RewardStatus):
    return Reward(
        deal_id=str(uuid.uuid4()),
        application_id=application_id,
        agent_id=agent_id,
        reward_type=reward_type,
        amount=3000,
        status=status,
    )


async def test_link_stats_count_contracts_by_non_rejected_advance() -> None:
    async with session_factory() as session:
        agent = Agent(email=f"{uuid.uuid4()}@example.test", display_name="Партнёр")
        session.add(agent)
        await session.flush()
        signed = _application(agent.id, "Договор + основная")
        pending = _application(agent.id, "Аванс ждёт решения")
        rejected = _application(agent.id, "Аванс отклонён")
        no_contract = _application(agent.id, "Без договора")
        session.add_all([signed, pending, rejected, no_contract])
        await session.flush()
        session.add_all(
            [
                _reward(signed.id, agent.id, RewardType.ADVANCE, RewardStatus.APPROVED),
                _reward(signed.id, agent.id, RewardType.MAIN, RewardStatus.APPROVED),
                _reward(pending.id, agent.id, RewardType.ADVANCE, RewardStatus.PENDING),
                _reward(rejected.id, agent.id, RewardType.ADVANCE, RewardStatus.REJECTED),
            ]
        )
        await session.commit()
        agent_id = agent.id
        application_ids = [signed.id, pending.id, rejected.id, no_contract.id]

    try:
        async with session_factory() as session:
            stats = await get_link_stats(session, agent_id)
    finally:
        async with session_factory() as session:
            await session.execute(delete(Reward).where(Reward.agent_id == agent_id))
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id.in_(application_ids))
            )
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()

    assert stats.applications == 4
    assert stats.contracts == 2  # подписанный и ждущий решения; отклонённый и без договора - нет
