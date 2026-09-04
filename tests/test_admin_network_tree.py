import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, AgentRole
from sqlalchemy import delete

from src.main import app
from src.web.dependencies import require_admin

FAKE_ADMIN = Agent(id=1, email="admin@example.com", role=AgentRole.ADMIN)


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


async def test_tree_page_without_query_shows_empty_state() -> None:
    app.dependency_overrides[require_admin] = lambda: FAKE_ADMIN
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/admin/network/tree")
    finally:
        app.dependency_overrides.pop(require_admin, None)

    assert response.status_code == 200
    assert "Дерево:" not in response.text


async def test_tree_page_search_and_render() -> None:
    marker = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        olya = Agent(email=f"{uuid.uuid4()}@example.test", display_name=f"ОляТест{marker}")
        session.add(olya)
        await session.flush()
        vasya = Agent(
            email=f"{uuid.uuid4()}@example.test",
            display_name=f"ВасяТест{marker}",
            invited_by_agent_id=olya.id,
        )
        session.add(vasya)
        await session.commit()
        olya_id, vasya_id = olya.id, vasya.id

    app.dependency_overrides[require_admin] = lambda: FAKE_ADMIN
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            search_response = await client.get(f"/admin/network/tree?q=ОляТест{marker}")
            assert search_response.status_code == 200
            assert f"root={olya_id}" in search_response.text

            tree_response = await client.get(f"/admin/network/tree?root={olya_id}")
            assert tree_response.status_code == 200
            assert f"ОляТест{marker}" in tree_response.text
            assert f"ВасяТест{marker}" in tree_response.text
    finally:
        app.dependency_overrides.pop(require_admin, None)
        async with session_factory() as session:
            await session.execute(delete(Agent).where(Agent.id == vasya_id))
            await session.execute(delete(Agent).where(Agent.id == olya_id))
            await session.commit()
