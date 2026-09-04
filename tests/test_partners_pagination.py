import uuid

import pytest
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent
from sqlalchemy import delete

from src.services.partners import PAGE_SIZE, list_partners


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


async def test_list_partners_paginates_beyond_page_size() -> None:
    marker = uuid.uuid4().hex[:8]
    total = PAGE_SIZE + 5
    agent_ids: list[int] = []
    async with session_factory() as session:
        for i in range(total):
            agent = Agent(
                email=f"{uuid.uuid4()}@example.test", display_name=f"Пагинация{marker}-{i:03d}"
            )
            session.add(agent)
            await session.flush()
            agent_ids.append(agent.id)
        await session.commit()

    try:
        async with session_factory() as session:
            page1 = await list_partners(session, f"Пагинация{marker}", page=1)
            page2 = await list_partners(session, f"Пагинация{marker}", page=2)

            assert page1.total_count == total
            assert page1.total_pages == 2
            assert len(page1.rows) == PAGE_SIZE
            assert len(page2.rows) == total - PAGE_SIZE

            page1_ids = {row.agent.id for row in page1.rows}
            page2_ids = {row.agent.id for row in page2.rows}
            assert page1_ids.isdisjoint(page2_ids)
            assert page1_ids | page2_ids == set(agent_ids)

            # page beyond the end clamps to the last page instead of erroring
            page_far = await list_partners(session, f"Пагинация{marker}", page=999)
            assert page_far.page == 2
    finally:
        async with session_factory() as session:
            await session.execute(delete(Agent).where(Agent.id.in_(agent_ids)))
            await session.commit()
