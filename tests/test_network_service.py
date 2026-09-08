import uuid

import pytest
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent
from sqlalchemy import delete

from src.services.network import (
    NetworkNode,
    build_network_tree,
    get_descendant_tree,
    network_tree_to_dict,
    search_agents,
)


def _node(id, parent_id, depth, name="Партнёр", is_active=True) -> NetworkNode:
    return NetworkNode(
        id=id,
        display_name=name,
        email=f"agent{id}@example.test",
        phone_normalized=None,
        is_active=is_active,
        depth=depth,
        parent_id=parent_id,
    )


def test_build_network_tree_nests_children_under_correct_parent() -> None:
    nodes = [
        _node(1, None, 0, "Оля"),
        _node(2, 1, 1, "Вася"),
        _node(3, 1, 1, "Петя"),
        _node(4, 2, 2, "Олег"),
    ]

    tree = build_network_tree(nodes)

    assert tree is not None
    assert tree.node.id == 1
    assert {child.node.id for child in tree.children} == {2, 3}
    vasya = next(c for c in tree.children if c.node.id == 2)
    assert [c.node.id for c in vasya.children] == [4]
    petya = next(c for c in tree.children if c.node.id == 3)
    assert petya.children == []


def test_build_network_tree_empty_list_returns_none() -> None:
    assert build_network_tree([]) is None


def test_network_tree_to_dict_serializes_nested_structure() -> None:
    tree = build_network_tree(
        [_node(1, None, 0, "Оля"), _node(2, 1, 1, "Вася", is_active=False)]
    )

    data = network_tree_to_dict(tree)

    assert data == {
        "id": 1,
        "name": "Оля",
        "email": "agent1@example.test",
        "phone": None,
        "is_active": True,
        "children": [
            {
                "id": 2,
                "name": "Вася",
                "email": "agent2@example.test",
                "phone": None,
                "is_active": False,
                "children": [],
            }
        ],
    }


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
