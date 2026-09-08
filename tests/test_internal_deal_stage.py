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
                    "stage_code": "C10:PREPARATION",
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
                    "stage_code": "C10:PREPARATION",
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
                    "stage_code": "C10:EXECUTING",
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
