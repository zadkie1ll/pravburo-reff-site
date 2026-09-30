import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import (
    Agent,
    AgentRole,
    EmploymentFormat,
    PayoutSettings,
    ReferralApplication,
    Reward,
    RewardStatus,
    RewardType,
)
from sqlalchemy import delete

from src.main import app
from src.services.admin_payouts import DEFAULT_OVERDUE_DAYS
from src.web.api_dependencies import CSRF_HEADER
from src.web.dependencies import optional_agent
from src.web.routes import api_admin_payouts

URL = "/api/v1/site/admin/payouts"
ADMIN = Agent(id=1, email="a@example.test", role=AgentRole.ADMIN, is_active=True)
NOW = datetime.now(UTC)


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


@dataclass
class World:
    client: AsyncClient
    rewards: dict[str, int]
    partner_name: str

    async def post(self, path: str, body: dict | None = None):
        me = (await self.client.get("/api/v1/site/me")).json()
        return await self.client.post(
            path, json=body or {}, headers={CSRF_HEADER: me["csrf_token"]}
        )

    async def reward(self, name: str) -> Reward:
        async with session_factory() as session:
            return await session.get(Reward, self.rewards[name])


def _reward(agent_id, application_id, **fields) -> Reward:
    return Reward(
        deal_id=str(uuid.uuid4()),
        application_id=application_id,
        agent_id=agent_id,
        reward_type=RewardType.ADVANCE,
        amount=Decimal(3000),
        **fields,
    )


@pytest.fixture
async def world(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[World]:
    """One partner with a reward in every state, and the partner notices captured."""
    marker = uuid.uuid4().hex[:8]
    notices = SimpleNamespace(email=AsyncMock(), push=AsyncMock(), partner=AsyncMock())
    monkeypatch.setattr(api_admin_payouts, "send_payout_paid_notice", notices.email)
    monkeypatch.setattr(api_admin_payouts, "send_push_notice", notices.push)
    monkeypatch.setattr(api_admin_payouts, "send_partner_notice", notices.partner)

    async with session_factory() as session:
        settings = await session.get(PayoutSettings, 1)
        original_days = settings.overdue_days if settings else None
        partner = Agent(
            email=f"{uuid.uuid4()}@example.test",
            display_name=f"Партнёр{marker}",
            employment_format=EmploymentFormat.SELF_EMPLOYED,
        )
        session.add(partner)
        await session.flush()
        application = ReferralApplication(
            agent_id=partner.id,
            full_name=f"Клиент{marker}",
            phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
        )
        session.add(application)
        await session.flush()
        rewards = {
            "scheduled": _reward(
                partner.id,
                application.id,
                status=RewardStatus.APPROVED,
                decided_at=NOW - timedelta(days=1),
            ),
            "overdue": _reward(
                partner.id,
                application.id,
                status=RewardStatus.APPROVED,
                decided_at=NOW - timedelta(days=40),
            ),
            "paid": _reward(
                partner.id,
                application.id,
                status=RewardStatus.APPROVED,
                decided_at=NOW - timedelta(days=5),
                paid_at=NOW,
            ),
            "pending": _reward(partner.id, application.id, status=RewardStatus.PENDING),
            "rejected": _reward(partner.id, application.id, status=RewardStatus.REJECTED),
        }
        session.add_all(rewards.values())
        await session.commit()
        ids = {name: reward.id for name, reward in rewards.items()}
        partner_id, application_id = partner.id, application.id

    app.dependency_overrides[optional_agent] = lambda: ADMIN
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        world = World(client=client, rewards=ids, partner_name=f"Партнёр{marker}")
        world.notices = notices  # type: ignore[attr-defined]
        yield world
    app.dependency_overrides.pop(optional_agent, None)
    async with session_factory() as session:
        await session.execute(delete(Reward).where(Reward.id.in_(ids.values())))
        await session.execute(
            delete(ReferralApplication).where(ReferralApplication.id == application_id)
        )
        await session.execute(delete(Agent).where(Agent.id == partner_id))
        settings = await session.get(PayoutSettings, 1)
        if original_days is None:
            if settings:
                await session.delete(settings)
        elif settings:
            settings.overdue_days = original_days
        await session.commit()


def _entries(body: dict) -> dict[int, dict]:
    return {
        entry["reward_id"]: entry
        for week in body["weeks"]
        for day in week
        if day["in_month"]
        for entry in day["entries"]
    }


def _month_of(moment: datetime) -> dict:
    return {"year": moment.year, "month": moment.month}


async def test_guest_and_partner_are_refused(world: World) -> None:
    app.dependency_overrides[optional_agent] = lambda: None
    assert (await world.client.get(URL)).status_code == 401
    partner = Agent(
        id=2,
        email="p@example.test",
        role=AgentRole.AGENT,
        is_active=True,
        employment_format=EmploymentFormat.SELF_EMPLOYED,
    )
    app.dependency_overrides[optional_agent] = lambda: partner

    assert (await world.client.get(URL)).status_code == 403


async def test_without_parameters_it_shows_the_current_month(world: World) -> None:
    response = await world.client.get(URL)

    assert response.status_code == 200
    body = response.json()
    assert (body["year"], body["month"]) == (NOW.year, NOW.month)
    assert body["overdue_days"] >= 1
    assert body["status"] == ""


async def test_paid_reward_sits_on_its_payment_day_this_month(world: World) -> None:
    body = (await world.client.get(URL, params=_month_of(NOW))).json()

    entry = _entries(body)[world.rewards["paid"]]
    assert entry["status_slug"] == "paid"
    assert entry["can_mark_paid"] is False
    assert body["month"] == NOW.month
    assert len(body["weeks"][0]) == 7


async def test_overdue_reward_is_listed_and_placed_on_its_planned_date(world: World) -> None:
    planned = NOW - timedelta(days=40) + timedelta(days=DEFAULT_OVERDUE_DAYS)

    body = (await world.client.get(URL, params=_month_of(planned))).json()

    overdue_ids = {row["reward_id"] for row in body["overdue_rows"]}
    assert world.rewards["overdue"] in overdue_ids
    row = next(r for r in body["overdue_rows"] if r["reward_id"] == world.rewards["overdue"])
    assert row["agent_name"] == world.partner_name
    assert row["target_date_label"] == planned.strftime("%d.%m.%Y")
    assert _entries(body)[world.rewards["overdue"]]["can_mark_paid"] is True


async def test_pending_and_rejected_rewards_are_not_on_the_calendar(world: World) -> None:
    body = (await world.client.get(URL, params=_month_of(NOW))).json()

    placed = _entries(body)
    assert world.rewards["pending"] not in placed
    assert world.rewards["rejected"] not in placed


async def test_status_filter_narrows_the_calendar(world: World) -> None:
    body = (await world.client.get(URL, params={**_month_of(NOW), "status": "paid"})).json()

    assert body["status"] == "paid"
    assert set(_entries(body)) >= {world.rewards["paid"]}
    assert world.rewards["scheduled"] not in _entries(body)
    assert {o["value"] for o in body["statuses"]} == {
        "pending",
        "scheduled",
        "overdue",
        "paid",
        "rejected",
    }


@pytest.mark.parametrize(
    "params",
    [{"month": 13}, {"month": -1}, {"year": 1}, {"status": "nonsense"}],
)
async def test_bad_month_year_or_status_is_a_validation_error(world: World, params) -> None:
    response = await world.client.get(URL, params=params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize(
    ("year", "month", "previous", "following"),
    [
        (2026, 1, (2025, 12), (2026, 2)),
        (2026, 12, (2026, 11), (2027, 1)),
        (2026, 6, (2026, 5), (2026, 7)),
    ],
)
async def test_neighbouring_months_wrap_around_the_year(
    world: World, year, month, previous, following
) -> None:
    body = (await world.client.get(URL, params={"year": year, "month": month})).json()

    assert (body["previous"]["year"], body["previous"]["month"]) == previous
    assert (body["next"]["year"], body["next"]["month"]) == following
    assert body["month_label"].endswith(str(year))


async def test_overdue_days_setting_is_saved_and_moves_the_planned_date(world: World) -> None:
    saved = await world.post(f"{URL}/settings", {"overdue_days": 30})

    assert saved.status_code == 200
    body = (await world.client.get(URL, params=_month_of(NOW))).json()
    assert body["overdue_days"] == 30
    # 40 days ago + 30 days: still overdue, but the planned date moved from +14 to +30.
    planned = NOW - timedelta(days=40) + timedelta(days=30)
    row = next(r for r in body["overdue_rows"] if r["reward_id"] == world.rewards["overdue"])
    assert row["target_date_label"] == planned.strftime("%d.%m.%Y")


@pytest.mark.parametrize("days", [0, -3, 366, "abc"])
async def test_bad_overdue_days_are_refused(world: World, days) -> None:
    response = await world.post(f"{URL}/settings", {"overdue_days": days})

    assert response.status_code == 422
    assert (await world.client.get(URL)).json()["overdue_days"] != days


async def test_marking_paid_records_it_and_tells_the_partner_everywhere(world: World) -> None:
    response = await world.post(f"{URL}/{world.rewards['scheduled']}/mark-paid")

    assert response.status_code == 200
    assert (await world.reward("scheduled")).paid_at is not None
    world.notices.email.assert_awaited_once()  # type: ignore[attr-defined]
    world.notices.push.assert_awaited_once()  # type: ignore[attr-defined]
    world.notices.partner.assert_awaited_once()  # type: ignore[attr-defined]


async def test_marking_an_overdue_reward_paid_works_too(world: World) -> None:
    response = await world.post(f"{URL}/{world.rewards['overdue']}/mark-paid")

    assert response.status_code == 200
    assert (await world.reward("overdue")).paid_at is not None


async def test_a_second_click_changes_nothing_and_notifies_nobody_again(world: World) -> None:
    first = await world.post(f"{URL}/{world.rewards['scheduled']}/mark-paid")
    paid_at = (await world.reward("scheduled")).paid_at
    second = await world.post(f"{URL}/{world.rewards['scheduled']}/mark-paid")

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "not_payable"
    assert (await world.reward("scheduled")).paid_at == paid_at
    assert world.notices.email.await_count == 1  # type: ignore[attr-defined]


@pytest.mark.parametrize("name", ["pending", "rejected", "paid"])
async def test_only_an_approved_unpaid_reward_can_be_marked(world: World, name) -> None:
    before = (await world.reward(name)).paid_at

    response = await world.post(f"{URL}/{world.rewards[name]}/mark-paid")

    assert response.status_code == 409
    assert (await world.reward(name)).paid_at == before
    world.notices.email.assert_not_awaited()  # type: ignore[attr-defined]


async def test_unknown_reward_is_a_404(world: World) -> None:
    response = await world.post(f"{URL}/999999999/mark-paid")

    assert response.status_code == 404


async def test_one_failing_notice_does_not_undo_the_payment(world: World) -> None:
    world.notices.push.side_effect = RuntimeError("push down")  # type: ignore[attr-defined]

    response = await world.post(f"{URL}/{world.rewards['scheduled']}/mark-paid")

    assert response.status_code == 200
    assert (await world.reward("scheduled")).paid_at is not None
    world.notices.partner.assert_awaited_once()  # type: ignore[attr-defined]


async def test_changes_require_csrf(world: World) -> None:
    response = await world.client.post(f"{URL}/{world.rewards['scheduled']}/mark-paid")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"
    assert (await world.reward("scheduled")).paid_at is None
