import uuid

import pytest
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent
from sqlalchemy import delete

from src.services.network import get_descendant_tree, search_agents


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


async def test_tree_includes_root_and_all_descendants_ordered_by_depth() -> None:
    marker = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        olya = Agent(email=f"{uuid.uuid4()}@example.test", display_name=f"Оля {marker}")
        session.add(olya)
        await session.flush()
        vasya = Agent(
            email=f"{uuid.uuid4()}@example.test",
            display_name=f"Вася {marker}",
            invited_by_agent_id=olya.id,
        )
        session.add(vasya)
        await session.flush()
        oleg = Agent(
            email=f"{uuid.uuid4()}@example.test",
            display_name=f"Олег {marker}",
            invited_by_agent_id=vasya.id,
        )
        session.add(oleg)
        # A sibling of Вася, also under Оля - shouldn't affect Вася's subtree
        petya = Agent(
            email=f"{uuid.uuid4()}@example.test",
            display_name=f"Петя {marker}",
            invited_by_agent_id=olya.id,
        )
        session.add(petya)
        await session.commit()
        olya_id, vasya_id, oleg_id, petya_id = olya.id, vasya.id, oleg.id, petya.id

    try:
        async with session_factory() as session:
            tree = await get_descendant_tree(session, olya_id)
            ids = [node.id for node in tree]
            assert ids[0] == olya_id
            assert set(ids) == {olya_id, vasya_id, oleg_id, petya_id}
            by_id = {node.id: node for node in tree}
            assert by_id[olya_id].depth == 0
            assert by_id[vasya_id].depth == 1
            assert by_id[petya_id].depth == 1
            assert by_id[oleg_id].depth == 2

            vasya_subtree = await get_descendant_tree(session, vasya_id)
            assert {node.id for node in vasya_subtree} == {vasya_id, oleg_id}
    finally:
        async with session_factory() as session:
            for agent_id in (oleg_id, petya_id, vasya_id, olya_id):
                await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()


async def test_search_agents_matches_display_name_and_email() -> None:
    marker = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        agent = Agent(
            email=f"findme-{marker}@example.test", display_name=f"Уникальное Имя {marker}"
        )
        session.add(agent)
        await session.commit()
        agent_id = agent.id

    try:
        async with session_factory() as session:
            by_name = await search_agents(session, f"Уникальное Имя {marker}")
            assert [a.id for a in by_name] == [agent_id]

            by_email = await search_agents(session, f"findme-{marker}")
            assert [a.id for a in by_email] == [agent_id]

            assert await search_agents(session, "") == []
    finally:
        async with session_factory() as session:
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()
