import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, ReferralApplication
from sqlalchemy import delete

from src.core.config import get_settings
from src.main import app
from src.web.routes import internal as internal_route


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


async def _make_application(session) -> tuple[int, int]:
    agent = Agent(email=f"{uuid.uuid4()}@example.test", display_name="Партнёр")
    session.add(agent)
    await session.flush()
    application = ReferralApplication(
        agent_id=agent.id,
        full_name="Клиент",
        phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
    )
    session.add(application)
    await session.commit()
    return agent.id, application.id


async def test_update_deal_stage_requires_internal_token() -> None:
    async with session_factory() as session:
        agent_id, application_id = await _make_application(session)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/internal/applications/{application_id}/stage",
                json={
                    "application_id": application_id,
                    "deal_id": "555",
                    "stage_code": "C2:PREPARATION",
                },
            )
        assert response.status_code == 401
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id == application_id)
            )
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()


async def test_update_deal_stage_stores_stage_code(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "internal_service_token", "test-token")

    async with session_factory() as session:
        agent_id, application_id = await _make_application(session)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/internal/applications/{application_id}/stage",
                headers={"X-Internal-Token": "test-token"},
                json={
                    "application_id": application_id,
                    "deal_id": "555",
                    "stage_code": "C2:PREPARATION",
                },
            )
        assert response.status_code == 200

        async with session_factory() as session:
            updated = await session.get(ReferralApplication, application_id)
            assert updated.bitrix_deal_id == "555"
            assert updated.deal_stage_code == "C2:PREPARATION"
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id == application_id)
            )
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()


async def test_update_deal_stage_pushes_only_on_actual_change(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "internal_service_token", "test-token")

    pushed: list[tuple] = []

    async def fake_push(session, agent_id, title, body):
        pushed.append((agent_id, title, body))

    monkeypatch.setattr(internal_route, "send_push_notice", fake_push)

    async with session_factory() as session:
        agent_id, application_id = await _make_application(session)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first = await client.post(
                f"/internal/applications/{application_id}/stage",
                headers={"X-Internal-Token": "test-token"},
                json={
                    "application_id": application_id,
                    "deal_id": "555",
                    "stage_code": "C2:NEW",
                },
            )
            assert first.status_code == 200
            assert len(pushed) == 1
            assert pushed[0][0] == agent_id

            # Same stage repeated (e.g. an unrelated field changed on the deal) - no push.
            repeated = await client.post(
                f"/internal/applications/{application_id}/stage",
                headers={"X-Internal-Token": "test-token"},
                json={
                    "application_id": application_id,
                    "deal_id": "555",
                    "stage_code": "C2:NEW",
                },
            )
            assert repeated.status_code == 200
            assert len(pushed) == 1

            # Real transition to a new stage - pushes again.
            second = await client.post(
                f"/internal/applications/{application_id}/stage",
                headers={"X-Internal-Token": "test-token"},
                json={
                    "application_id": application_id,
                    "deal_id": "555",
                    "stage_code": "C2:UC_0Y0VBU",
                },
            )
            assert second.status_code == 200
            assert len(pushed) == 2
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id == application_id)
            )
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()


async def test_update_deal_stage_sends_telegram_notice(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "internal_service_token", "test-token")

    notified: list[tuple] = []

    async def fake_partner_notice(session, agent_id, message):
        notified.append((agent_id, message))

    monkeypatch.setattr(internal_route, "send_partner_notice", fake_partner_notice)

    async with session_factory() as session:
        agent_id, application_id = await _make_application(session)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/internal/applications/{application_id}/stage",
                headers={"X-Internal-Token": "test-token"},
                json={
                    "application_id": application_id,
                    "deal_id": "555",
                    "stage_code": "C2:UC_7TR7XT",
                },
            )
            assert response.status_code == 200
            assert len(notified) == 1
            assert notified[0][0] == agent_id
            assert "Процедура завершена" in notified[0][1]
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id == application_id)
            )
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()


async def test_update_deal_stage_ignores_untracked_stage(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "internal_service_token", "test-token")

    pushed: list[tuple] = []
    notified: list[tuple] = []

    async def fake_push(session, agent_id, title, body):
        pushed.append((agent_id, title, body))

    async def fake_partner_notice(session, agent_id, message):
        notified.append((agent_id, message))

    monkeypatch.setattr(internal_route, "send_push_notice", fake_push)
    monkeypatch.setattr(internal_route, "send_partner_notice", fake_partner_notice)

    async with session_factory() as session:
        agent_id, application_id = await _make_application(session)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            tracked = await client.post(
                f"/internal/applications/{application_id}/stage",
                headers={"X-Internal-Token": "test-token"},
                json={"application_id": application_id, "deal_id": "555", "stage_code": "C2:NEW"},
            )
            assert tracked.status_code == 200
            assert len(pushed) == 1

            # "Сбор документов" не входит в этапы ТЗ: этап не меняется, push не идёт.
            untracked = await client.post(
                f"/internal/applications/{application_id}/stage",
                headers={"X-Internal-Token": "test-token"},
                json={
                    "application_id": application_id,
                    "deal_id": "555",
                    "stage_code": "C2:UC_M5ONI8",
                },
            )
            assert untracked.status_code == 200
            assert untracked.json() == {"status": "ignored"}
            assert len(pushed) == 1
            assert len(notified) == 1

        async with session_factory() as session:
            updated = await session.get(ReferralApplication, application_id)
            assert updated.deal_stage_code == "C2:NEW"
            assert updated.bitrix_deal_id == "555"
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id == application_id)
            )
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()


async def test_update_deal_stage_remembers_sales_stages_and_ignores_untracked_funnel_2(
    monkeypatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "internal_service_token", "test-token")

    pushed: list[tuple] = []

    async def fake_push(session, agent_id, title, body):
        pushed.append((agent_id, title, body))

    monkeypatch.setattr(internal_route, "send_push_notice", fake_push)

    async with session_factory() as session:
        agent_id, application_id = await _make_application(session)

    async def post(client, stage_code):
        return await client.post(
            f"/internal/applications/{application_id}/stage",
            headers={"X-Internal-Token": "test-token"},
            json={"application_id": application_id, "deal_id": "555", "stage_code": stage_code},
        )

    async def stored_stage():
        async with session_factory() as session:
            return (await session.get(ReferralApplication, application_id)).deal_stage_code

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await post(client, "UC_Q6ZN5G")  # "Думает"
            assert await stored_stage() == "UC_Q6ZN5G"

            await post(client, "UC_1BEALQ")  # "Ушли в игнор"
            assert await stored_stage() == "UC_1BEALQ"

            await post(client, "UC_6IE5TH")  # "Возврат на первую линию": просто новая стадия
            assert await stored_stage() == "UC_6IE5TH"

            await post(client, "UC_4FX5NE")  # "Договор составлен, ждём оплату"
            assert await stored_stage() == "UC_4FX5NE"

            # Стадия воронки "Сопровождение" вне ТЗ не стирает то, что уже запомнено.
            await post(client, "C2:UC_M5ONI8")
            assert await stored_stage() == "UC_4FX5NE"

        assert pushed == []  # по стадиям продаж push не шлём
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id == application_id)
            )
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()
