import uuid
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, AgentRole, EmploymentFormat, NetworkOverrideRate
from sqlalchemy import delete, select, update

from src.main import app
from src.web.api_dependencies import CSRF_HEADER
from src.web.dependencies import optional_agent

RATES = "/api/v1/site/admin/network/rates"
ADMIN = Agent(id=1, email="a@example.test", role=AgentRole.ADMIN, is_active=True)


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


async def _saved_amounts() -> dict[int, Decimal]:
    async with session_factory() as session:
        rows = (await session.scalars(select(NetworkOverrideRate))).all()
        return {row.level: row.amount for row in rows}


@pytest.fixture
async def admin_client() -> AsyncIterator[AsyncClient]:
    """An admin client that puts the real rates back afterwards."""
    original = await _saved_amounts()
    app.dependency_overrides[optional_agent] = lambda: ADMIN
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(optional_agent, None)
    async with session_factory() as session:
        for level, amount in original.items():
            await session.execute(
                update(NetworkOverrideRate)
                .where(NetworkOverrideRate.level == level)
                .values(amount=amount)
            )
        await session.commit()


async def _post(client: AsyncClient, body: dict):
    me = (await client.get("/api/v1/site/me")).json()
    return await client.post(RATES, json=body, headers={CSRF_HEADER: me["csrf_token"]})


def _amounts(one, two, three) -> dict:
    return {"amount_1": one, "amount_2": two, "amount_3": three}


async def test_guest_and_partner_are_refused(admin_client: AsyncClient) -> None:
    app.dependency_overrides[optional_agent] = lambda: None
    assert (await admin_client.get(RATES)).status_code == 401
    partner = Agent(
        id=2,
        email="p@example.test",
        role=AgentRole.AGENT,
        is_active=True,
        employment_format=EmploymentFormat.SELF_EMPLOYED,
    )
    app.dependency_overrides[optional_agent] = lambda: partner

    assert (await admin_client.get(RATES)).status_code == 403


async def test_rates_are_listed_by_level_with_labels(admin_client: AsyncClient) -> None:
    body = (await admin_client.get(RATES)).json()

    assert [rate["level"] for rate in body["rates"]] == [1, 2, 3]
    assert "1 уровень" in body["rates"][0]["label"]
    assert all(Decimal(rate["amount"]) >= 0 for rate in body["rates"])


async def test_rates_are_saved_and_returned(admin_client: AsyncClient) -> None:
    response = await _post(admin_client, _amounts("600.50", "225.25", " 50 "))

    assert response.status_code == 200
    saved = await _saved_amounts()
    assert saved == {1: Decimal("600.50"), 2: Decimal("225.25"), 3: Decimal("50")}
    assert [Decimal(r["amount"]) for r in response.json()["rates"]] == [
        Decimal("600.50"),
        Decimal("225.25"),
        Decimal("50"),
    ]


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        ("-1", "Сумма не может быть отрицательной"),
        ("abc", "Укажите корректную сумму"),
        ("", "Укажите корректную сумму"),
        ("NaN", "Укажите корректную сумму"),
        ("Infinity", "Укажите корректную сумму"),
    ],
)
async def test_bad_amounts_are_refused_and_nothing_is_saved(
    admin_client: AsyncClient, bad: str, message: str
) -> None:
    before = await _saved_amounts()

    response = await _post(admin_client, _amounts("10", bad, "10"))

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["message"] == message
    assert "amount_2" in error["fields"]
    assert await _saved_amounts() == before


async def test_saving_requires_csrf(admin_client: AsyncClient) -> None:
    response = await admin_client.post(RATES, json=_amounts("1", "1", "1"))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


# --- network tree -----------------------------------------------------------------------

TREE = "/api/v1/site/admin/network/tree"


@pytest.fixture
async def chain() -> AsyncIterator[dict]:
    """root -> child -> grandchild (the child is blocked), and an unrelated partner."""
    marker = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        root = Agent(email=f"{uuid.uuid4()}@example.test", display_name=f"Корень{marker}")
        session.add(root)
        await session.flush()
        child = Agent(
            email=f"{uuid.uuid4()}@example.test",
            display_name=f"Ребёнок{marker}",
            invited_by_agent_id=root.id,
            is_active=False,
        )
        session.add(child)
        await session.flush()
        grandchild = Agent(
            email=f"{uuid.uuid4()}@example.test",
            display_name="",
            invited_by_agent_id=child.id,
        )
        other = Agent(email=f"{uuid.uuid4()}@example.test", display_name=f"Чужой{marker}")
        session.add_all([grandchild, other])
        await session.commit()
        ids = {
            "root": root.id,
            "child": child.id,
            "grandchild": grandchild.id,
            "other": other.id,
            "marker": marker,
            "grandchild_email": grandchild.email,
        }
    yield ids
    async with session_factory() as session:
        await session.execute(delete(Agent).where(Agent.id.in_([ids["grandchild"], ids["child"]])))
        await session.execute(delete(Agent).where(Agent.id.in_([ids["root"], ids["other"]])))
        await session.commit()


async def test_tree_search_finds_partners_by_name(admin_client: AsyncClient, chain: dict) -> None:
    body = (await admin_client.get(TREE, params={"q": f"Корень{chain['marker']}"})).json()

    assert [match["id"] for match in body["matches"]] == [chain["root"]]
    assert body["root"] is None
    assert body["tree"] is None


async def test_tree_without_query_or_root_is_empty(admin_client: AsyncClient) -> None:
    body = (await admin_client.get(TREE)).json()

    assert body == {"matches": [], "root": None, "tree": None}


async def test_tree_lists_the_whole_downline(admin_client: AsyncClient, chain: dict) -> None:
    body = (await admin_client.get(TREE, params={"root": chain["root"]})).json()

    assert body["root"]["id"] == chain["root"]
    tree = body["tree"]
    assert tree["id"] == chain["root"]
    assert [child["id"] for child in tree["children"]] == [chain["child"]]
    child = tree["children"][0]
    assert child["is_active"] is False
    grandchild = child["children"][0]
    assert grandchild["id"] == chain["grandchild"]
    # A partner without a name is shown by e-mail.
    assert grandchild["name"] == chain["grandchild_email"]
    assert grandchild["children"] == []
    assert chain["other"] not in {tree["id"], child["id"], grandchild["id"]}


async def test_tree_of_a_partner_without_downline_is_a_single_node(
    admin_client: AsyncClient, chain: dict
) -> None:
    tree = (await admin_client.get(TREE, params={"root": chain["other"]})).json()["tree"]

    assert tree["id"] == chain["other"]
    assert tree["children"] == []


async def test_unknown_root_shows_nothing(admin_client: AsyncClient) -> None:
    body = (await admin_client.get(TREE, params={"root": 999999999})).json()

    assert body["root"] is None
    assert body["tree"] is None


async def test_tree_is_for_admins_only(admin_client: AsyncClient) -> None:
    app.dependency_overrides[optional_agent] = lambda: None

    assert (await admin_client.get(TREE)).status_code == 401
