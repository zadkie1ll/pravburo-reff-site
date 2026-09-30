import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, AgentRole, EmploymentFormat, FaqItem
from sqlalchemy import delete, select

from src.main import app
from src.web.api_dependencies import CSRF_HEADER
from src.web.dependencies import optional_agent

URL = "/api/v1/site/admin/faq"
ADMIN = Agent(id=1, email="a@example.test", role=AgentRole.ADMIN, is_active=True)


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


@pytest.fixture
async def faq_client() -> AsyncIterator[tuple[AsyncClient, str]]:
    """Admin client; every FAQ row this test creates (marked) is removed afterwards."""
    marker = uuid.uuid4().hex[:8]
    app.dependency_overrides[optional_agent] = lambda: ADMIN
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, marker
    app.dependency_overrides.pop(optional_agent, None)
    async with session_factory() as session:
        await session.execute(delete(FaqItem).where(FaqItem.question.like(f"%{marker}%")))
        await session.commit()


async def _send(client: AsyncClient, method: str, path: str, body: dict | None = None):
    me = (await client.get("/api/v1/site/me")).json()
    return await client.request(method, path, json=body, headers={CSRF_HEADER: me["csrf_token"]})


async def _mine(client: AsyncClient, marker: str) -> list[dict]:
    items = (await client.get(URL)).json()["items"]
    return [item for item in items if marker in item["question"]]


async def test_guest_and_partner_are_refused(faq_client) -> None:
    client, _ = faq_client
    app.dependency_overrides[optional_agent] = lambda: None
    assert (await client.get(URL)).status_code == 401
    partner = Agent(
        id=2,
        email="p@example.test",
        role=AgentRole.AGENT,
        is_active=True,
        employment_format=EmploymentFormat.SELF_EMPLOYED,
    )
    app.dependency_overrides[optional_agent] = lambda: partner

    assert (await client.get(URL)).status_code == 403


async def test_a_created_question_is_listed_and_public(faq_client) -> None:
    client, marker = faq_client

    created = await _send(
        client, "POST", URL, {"question": f"  Вопрос{marker}  ", "answer": " Ответ "}
    )

    assert created.status_code == 200
    (item,) = await _mine(client, marker)
    assert item["question"] == f"Вопрос{marker}"  # trimmed
    assert item["answer"] == "Ответ"
    public = (await client.get("/api/v1/site/faq")).json()["items"]
    assert any(entry["question"] == f"Вопрос{marker}" for entry in public)


@pytest.mark.parametrize(
    ("question", "answer", "field"),
    [("   ", "Ответ", "question"), ("Вопрос", "   ", "answer")],
)
async def test_blank_parts_are_refused(faq_client, question, answer, field) -> None:
    client, marker = faq_client
    before = len((await client.get(URL)).json()["items"])

    response = await _send(client, "POST", URL, {"question": question, "answer": answer})

    assert response.status_code == 400
    assert field in response.json()["error"]["fields"]
    assert len((await client.get(URL)).json()["items"]) == before


async def test_a_too_long_question_is_a_validation_error_not_a_crash(faq_client) -> None:
    client, _ = faq_client

    response = await _send(client, "POST", URL, {"question": "я" * 301, "answer": "Ответ"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_a_question_is_edited(faq_client) -> None:
    client, marker = faq_client
    await _send(client, "POST", URL, {"question": f"Вопрос{marker}", "answer": "Старый"})
    (item,) = await _mine(client, marker)

    response = await _send(
        client, "PUT", f"{URL}/{item['id']}", {"question": f"Вопрос{marker}", "answer": "Новый"}
    )

    assert response.status_code == 200
    assert (await _mine(client, marker))[0]["answer"] == "Новый"


async def test_editing_refuses_blanks_and_unknown_ids(faq_client) -> None:
    client, marker = faq_client
    await _send(client, "POST", URL, {"question": f"Вопрос{marker}", "answer": "Ответ"})
    (item,) = await _mine(client, marker)

    blank = await _send(client, "PUT", f"{URL}/{item['id']}", {"question": " ", "answer": "x"})
    missing = await _send(client, "PUT", f"{URL}/999999999", {"question": "q", "answer": "a"})

    assert blank.status_code == 400
    assert missing.status_code == 404
    assert (await _mine(client, marker))[0]["question"] == f"Вопрос{marker}"


async def test_a_question_is_deleted(faq_client) -> None:
    client, marker = faq_client
    await _send(client, "POST", URL, {"question": f"Вопрос{marker}", "answer": "Ответ"})
    (item,) = await _mine(client, marker)

    response = await _send(client, "DELETE", f"{URL}/{item['id']}")

    assert response.status_code == 200
    assert await _mine(client, marker) == []
    assert (await _send(client, "DELETE", f"{URL}/{item['id']}")).status_code == 404


async def test_questions_can_be_moved_up_and_down(faq_client) -> None:
    client, marker = faq_client
    for name in ("A", "B", "C"):
        await _send(client, "POST", URL, {"question": f"{name}{marker}", "answer": "x"})
    order = lambda items: [i["question"][0] for i in items]  # noqa: E731
    first, second, third = await _mine(client, marker)

    await _send(client, "POST", f"{URL}/{third['id']}/move", {"direction": "up"})
    assert order(await _mine(client, marker)) == ["A", "C", "B"]

    await _send(client, "POST", f"{URL}/{first['id']}/move", {"direction": "down"})
    assert order(await _mine(client, marker)) == ["C", "A", "B"]

    # Already first / last: nothing changes, no error.
    top = (await _mine(client, marker))[0]
    assert (
        await _send(client, "POST", f"{URL}/{top['id']}/move", {"direction": "up"})
    ).status_code == 200
    assert order(await _mine(client, marker)) == ["C", "A", "B"]
    assert second["id"] in {i["id"] for i in await _mine(client, marker)}


async def test_move_rejects_a_bad_direction_and_unknown_ids(faq_client) -> None:
    client, marker = faq_client
    await _send(client, "POST", URL, {"question": f"Вопрос{marker}", "answer": "Ответ"})
    (item,) = await _mine(client, marker)

    bad = await _send(client, "POST", f"{URL}/{item['id']}/move", {"direction": "sideways"})
    missing = await _send(client, "POST", f"{URL}/999999999/move", {"direction": "up"})

    assert bad.status_code == 422
    assert missing.status_code == 404


async def test_changes_require_csrf(faq_client) -> None:
    client, marker = faq_client

    response = await client.post(URL, json={"question": f"Вопрос{marker}", "answer": "x"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"
    assert await _mine(client, marker) == []
    async with session_factory() as session:
        assert (
            await session.scalar(select(FaqItem.id).where(FaqItem.question.like(f"%{marker}%")))
            is None
        )
