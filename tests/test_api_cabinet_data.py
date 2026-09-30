"""What the cabinet API says about a partner's clients, visits and applications.

These are the business rules the old HTML cabinet tests checked through page text; here they are
checked on the JSON the React cabinet receives.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import (
    Agent,
    EmploymentFormat,
    ReferralApplication,
    ReferralLinkVisit,
    Reward,
    RewardStatus,
    RewardType,
)
from sqlalchemy import delete, update

from src.main import app
from src.web.dependencies import optional_agent

CABINET = "/api/v1/site/cabinet"


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


def _phone() -> str:
    return f"+7999{uuid.uuid4().int % 10**7:07d}"


def _agent(name: str, **fields) -> Agent:
    return Agent(
        email=f"{uuid.uuid4()}@example.test",
        display_name=name,
        employment_format=EmploymentFormat.SELF_EMPLOYED,
        **fields,
    )


async def _wipe(*agent_ids: int) -> None:
    async with session_factory() as session:
        await session.execute(delete(Reward).where(Reward.agent_id.in_(agent_ids)))
        await session.execute(
            delete(ReferralApplication).where(ReferralApplication.agent_id.in_(agent_ids))
        )
        await session.execute(
            delete(ReferralLinkVisit).where(ReferralLinkVisit.agent_id.in_(agent_ids))
        )
        await session.execute(
            update(Agent).where(Agent.id.in_(agent_ids)).values(invited_by_agent_id=None)
        )
        await session.execute(delete(Agent).where(Agent.id.in_(agent_ids)))
        await session.commit()


async def _get(agent_id: int, path: str):
    async with session_factory() as session:
        agent = await session.get(Agent, agent_id)
    app.dependency_overrides[optional_agent] = lambda: agent
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.get(path)
    finally:
        app.dependency_overrides.pop(optional_agent, None)


def _client(body: dict, name: str) -> dict:
    return next(row for row in body["clients"] if row["client_name"] == name)


async def test_each_client_shows_where_their_reward_stands() -> None:
    async with session_factory() as session:
        agent = _agent("Партнёр")
        session.add(agent)
        await session.flush()
        with_reward = ReferralApplication(
            agent_id=agent.id, full_name="Оплативший клиент", phone_normalized=_phone()
        )
        without = ReferralApplication(
            agent_id=agent.id, full_name="Клиент без оплаты", phone_normalized=_phone()
        )
        session.add_all([with_reward, without])
        await session.flush()
        session.add(
            Reward(deal_id=str(uuid.uuid4()), application_id=with_reward.id, agent_id=agent.id)
        )
        await session.commit()
        agent_id = agent.id

    try:
        response = await _get(agent_id, CABINET)
    finally:
        await _wipe(agent_id)

    body = response.json()
    assert (
        "Основная выплата: Ожидает решения" in _client(body, "Оплативший клиент")["reward_summary"]
    )
    assert "Договор не заключен" in _client(body, "Клиент без оплаты")["reward_summary"]


async def test_client_row_has_stage_created_date_and_paid_and_expected_totals() -> None:
    async with session_factory() as session:
        agent = _agent("Партнёр")
        session.add(agent)
        await session.flush()
        staged = ReferralApplication(
            agent_id=agent.id,
            full_name="Клиент на этапе",
            phone_normalized=_phone(),
            deal_stage_code="C2:UC_0Y0VBU",
        )
        fresh = ReferralApplication(
            agent_id=agent.id, full_name="Свежая заявка", phone_normalized=_phone()
        )
        session.add_all([staged, fresh])
        await session.flush()
        session.add_all(
            [
                Reward(
                    deal_id=str(uuid.uuid4()),
                    application_id=staged.id,
                    agent_id=agent.id,
                    reward_type=RewardType.ADVANCE,
                    amount=3000,
                    status=RewardStatus.APPROVED,
                    paid_at=datetime.now(UTC),
                ),
                Reward(
                    deal_id=str(uuid.uuid4()),
                    application_id=staged.id,
                    agent_id=agent.id,
                    reward_type=RewardType.MAIN,
                    amount=10000,
                    status=RewardStatus.APPROVED,
                ),
            ]
        )
        await session.commit()
        agent_id = agent.id
        created_label = staged.created_at.strftime("%d.%m.%Y")

    try:
        body = (await _get(agent_id, CABINET)).json()
    finally:
        await _wipe(agent_id)

    staged_row = _client(body, "Клиент на этапе")
    assert staged_row["stage"] == "Заявление подано в суд"
    assert staged_row["created_at_label"] == created_label
    # The label may wrap only between "paid" and "expected": every other space is non-breaking.
    nbsp = lambda text: text.replace(" ", "\u00a0")  # noqa: E731
    assert staged_row["reward_totals"] == (
        f"{nbsp('Выплачено: 3 000 ₽')} · {nbsp('Ожидается: 10 000 ₽')}"
    )
    assert _client(body, "Свежая заявка")["stage"] == "Заявка получена"


async def test_a_partner_sees_the_network_bonus_earned_from_an_invitees_client() -> None:
    async with session_factory() as session:
        agent = _agent("Оля")
        session.add(agent)
        await session.flush()
        invitee = _agent("Вася", invited_by_agent_id=agent.id)
        session.add(invitee)
        await session.flush()
        application = ReferralApplication(
            agent_id=invitee.id, full_name="Клиент Васи", phone_normalized=_phone()
        )
        session.add(application)
        await session.flush()
        main_a = Reward(
            deal_id=str(uuid.uuid4()), application_id=application.id, agent_id=invitee.id
        )
        main_b = Reward(
            deal_id=str(uuid.uuid4()), application_id=application.id, agent_id=invitee.id
        )
        session.add_all([main_a, main_b])
        await session.flush()
        session.add_all(
            [
                Reward(
                    deal_id=main_a.deal_id,
                    application_id=application.id,
                    agent_id=agent.id,
                    reward_type=RewardType.OVERRIDE,
                    amount=Decimal("300.00"),
                    network_level=1,
                    source_reward_id=main_a.id,
                    paid_at=datetime.now(UTC),
                ),
                Reward(
                    deal_id=main_b.deal_id,
                    application_id=application.id,
                    agent_id=agent.id,
                    reward_type=RewardType.OVERRIDE,
                    amount=Decimal("150.00"),
                    network_level=1,
                    source_reward_id=main_b.id,
                ),
            ]
        )
        await session.commit()
        agent_id, invitee_id = agent.id, invitee.id

    try:
        body = (await _get(agent_id, CABINET)).json()
    finally:
        await _wipe(agent_id, invitee_id)

    row = _client(body, "Клиент Васи")
    assert "Бонус за сеть" in row["reward_summary"]
    assert "300" in row["reward_summary"] + row["reward_totals"]
    assert "150" in row["reward_summary"] + row["reward_totals"]


async def test_visits_are_counted_per_moscow_day_newest_first_with_a_total() -> None:
    async with session_factory() as session:
        agent = _agent("Партнёр")
        session.add(agent)
        await session.flush()
        session.add_all(
            ReferralLinkVisit(agent_id=agent.id, created_at=moment)
            for moment in (
                datetime(2026, 9, 20, 10, 0, tzinfo=UTC),
                datetime(2026, 9, 20, 11, 0, tzinfo=UTC),
                # 22:30 UTC is already the next day in Moscow (UTC+3).
                datetime(2026, 9, 20, 22, 30, tzinfo=UTC),
                datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
            )
        )
        await session.commit()
        agent_id = agent.id

    try:
        body = (await _get(agent_id, f"{CABINET}/visits")).json()
    finally:
        await _wipe(agent_id)

    assert [(day["day_label"], day["count"]) for day in body["days"]] == [
        ("21.09.2026", 1),
        ("20.09.2026", 2),
        ("19.09.2026", 1),
    ]
    assert body["total"] == 4


async def test_applications_show_friendly_statuses_for_the_partners_own_clients_only() -> None:
    async with session_factory() as session:
        agent = _agent("Партнёр")
        other = _agent("Чужой")
        session.add_all([agent, other])
        await session.flush()
        session.add_all(
            [
                ReferralApplication(
                    agent_id=owner.id,
                    full_name=name,
                    phone_normalized=_phone(),
                    deal_stage_code=stage,
                )
                for owner, name, stage in (
                    (agent, "Клиент без сделки", None),
                    (agent, "Клиент думает", "UC_Q6ZN5G"),
                    (agent, "Клиент мусор", "UC_K0Z3P6"),
                    (agent, "Клиент в суде", "C2:UC_0Y0VBU"),
                    (other, "Чужой клиент", "UC_Q6ZN5G"),
                )
            ]
        )
        await session.commit()
        agent_id, other_id = agent.id, other.id

    try:
        body = (await _get(agent_id, f"{CABINET}/applications")).json()
    finally:
        await _wipe(agent_id, other_id)

    assert {row["client_name"]: row["status"] for row in body["rows"]} == {
        "Клиент без сделки": "Заявка получена",
        "Клиент думает": "Думает",
        "Клиент мусор": "Не подходит",
        "Клиент в суде": "Заявление подано в суд",
    }
    assert all("***" in row["masked_phone"] for row in body["rows"])
