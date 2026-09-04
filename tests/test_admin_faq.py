import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, AgentRole, FaqItem
from sqlalchemy import delete

from src.main import app
from src.web.dependencies import require_admin

FAKE_ADMIN = Agent(id=1, email="admin@example.com", role=AgentRole.ADMIN)


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


def _csrf_from(html: str) -> str:
    return html.split('name="csrf" value="')[1].split('"')[0]


async def test_create_faq_item_shows_on_admin_and_public_page() -> None:
    marker = uuid.uuid4().hex[:8]
    app.dependency_overrides[require_admin] = lambda: FAKE_ADMIN
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            page = await client.get("/admin/faq")
            csrf = _csrf_from(page.text)
            response = await client.post(
                "/admin/faq/create",
                data={"question": f"Вопрос{marker}", "answer": f"Ответ{marker}", "csrf": csrf},
                follow_redirects=False,
            )
            assert response.status_code == 303

            admin_page = await client.get("/admin/faq")
            assert f"Вопрос{marker}" in admin_page.text

            public_page = await client.get("/faq")
            assert f"Вопрос{marker}" in public_page.text
    finally:
        app.dependency_overrides.pop(require_admin, None)
        async with session_factory() as session:
            await session.execute(delete(FaqItem).where(FaqItem.question == f"Вопрос{marker}"))
            await session.commit()


async def test_update_and_delete_faq_item() -> None:
    marker = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        item = FaqItem(question=f"Старый{marker}", answer="Ответ", position=999)
        session.add(item)
        await session.commit()
        item_id = item.id

    app.dependency_overrides[require_admin] = lambda: FAKE_ADMIN
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            page = await client.get("/admin/faq")
            csrf = _csrf_from(page.text)
            await client.post(
                f"/admin/faq/{item_id}/update",
                data={"question": f"Новый{marker}", "answer": "Обновлённый ответ", "csrf": csrf},
                follow_redirects=False,
            )

            async with session_factory() as session:
                updated = await session.get(FaqItem, item_id)
                assert updated.question == f"Новый{marker}"

            page2 = await client.get("/admin/faq")
            csrf2 = _csrf_from(page2.text)
            delete_response = await client.post(
                f"/admin/faq/{item_id}/delete",
                data={"csrf": csrf2},
                follow_redirects=False,
            )
            assert delete_response.status_code == 303

            async with session_factory() as session:
                gone = await session.get(FaqItem, item_id)
                assert gone is None
    finally:
        app.dependency_overrides.pop(require_admin, None)
        async with session_factory() as session:
            await session.execute(delete(FaqItem).where(FaqItem.id == item_id))
            await session.commit()


async def test_move_faq_item_swaps_position() -> None:
    marker = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        first = FaqItem(question=f"Первый{marker}", answer="A", position=1000)
        second = FaqItem(question=f"Второй{marker}", answer="B", position=1001)
        session.add_all([first, second])
        await session.commit()
        first_id, second_id = first.id, second.id

    app.dependency_overrides[require_admin] = lambda: FAKE_ADMIN
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            page = await client.get("/admin/faq")
            csrf = _csrf_from(page.text)
            response = await client.post(
                f"/admin/faq/{second_id}/move",
                data={"direction": "up", "csrf": csrf},
                follow_redirects=False,
            )
            assert response.status_code == 303

        async with session_factory() as session:
            first_after = await session.get(FaqItem, first_id)
            second_after = await session.get(FaqItem, second_id)
            assert second_after.position < first_after.position
    finally:
        app.dependency_overrides.pop(require_admin, None)
        async with session_factory() as session:
            await session.execute(delete(FaqItem).where(FaqItem.id.in_([first_id, second_id])))
            await session.commit()
