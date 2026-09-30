from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Agent, AgentRole, EmploymentFormat, RewardStatus, RewardType

from src.core.payout_pdf import build_payouts_pdf
from src.main import app
from src.services.payouts import (
    PayoutRow,
    build_finance_summary,
    format_amount,
    payout_status_slug,
)


def _reward(**overrides) -> SimpleNamespace:
    defaults = dict(status=RewardStatus.PENDING, paid_at=None, amount=None)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_payout_status_slug_rejected_takes_priority() -> None:
    assert payout_status_slug(_reward(status=RewardStatus.REJECTED, paid_at=None)) == "rejected"


def test_payout_status_slug_pending() -> None:
    assert payout_status_slug(_reward(status=RewardStatus.PENDING)) == "pending"


def test_payout_status_slug_approved_unpaid_is_scheduled() -> None:
    assert payout_status_slug(_reward(status=RewardStatus.APPROVED, paid_at=None)) == "scheduled"


def test_payout_status_slug_approved_paid_is_paid() -> None:
    reward = _reward(status=RewardStatus.APPROVED, paid_at=datetime(2026, 1, 1, tzinfo=UTC))
    assert payout_status_slug(reward) == "paid"


def test_finance_summary_sums_paid_and_pending_by_status() -> None:
    summary = build_finance_summary(
        [
            _reward(
                status=RewardStatus.APPROVED,
                paid_at=datetime.now(UTC),
                amount=Decimal("5000.00"),
            ),
            _reward(status=RewardStatus.PENDING, amount=Decimal("3000.00")),
            _reward(status=RewardStatus.APPROVED, paid_at=None, amount=Decimal("10000.00")),
            _reward(status=RewardStatus.REJECTED, amount=Decimal("1000.00")),
        ]
    )
    assert summary.total_paid_label == "5 000 ₽"
    assert summary.this_month_label == "5 000 ₽"
    assert summary.pending_total_label == "13 000 ₽"
    assert {g.label: g.amount_label for g in summary.pending_groups} == {
        "Ожидает подтверждения": "3 000 ₽",
        "Ждём выплаты": "10 000 ₽",
    }


def test_finance_summary_ignores_rewards_without_amount() -> None:
    summary = build_finance_summary([_reward(status=RewardStatus.PENDING, amount=None)])
    assert summary.total_paid_label == "0 ₽"
    assert summary.pending_total_label == "0 ₽"
    assert summary.pending_groups == []


def test_format_amount_none() -> None:
    assert format_amount(None) == "—"


def test_format_amount_formats_with_spaces() -> None:
    assert format_amount(Decimal("45000")) == "45 000 ₽"


def test_build_payouts_pdf_contains_cyrillic_content() -> None:
    row = PayoutRow(
        reward=_reward(),
        client_name="Иван Иванов",
        type_label="Аванс",
        status_label="Выплачено",
        status_slug="paid",
        amount_label="3 000 ₽",
        payout_date_label="15.03.2026",
    )
    pdf_bytes = build_payouts_pdf("Светлана Иванова", "", [row])
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000


def test_build_payouts_pdf_handles_empty_rows() -> None:
    pdf_bytes = build_payouts_pdf("Светлана Иванова", "", [])
    assert pdf_bytes.startswith(b"%PDF")


def test_payouts_export_requires_login(client) -> None:
    response = client.get("/payouts/export.pdf", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


class _FakeExecuteResult:
    def __init__(self, rows) -> None:
        self._rows = rows

    def all(self):
        return self._rows


class _FakeScalarResult:
    def __init__(self, items) -> None:
        self._items = items

    def all(self):
        return self._items


class _FakePayoutsSession:
    def __init__(self, rows, applications=()) -> None:
        self._rows = rows
        self._applications = list(applications)

    async def execute(self, *args, **kwargs):
        return _FakeExecuteResult(self._rows)

    async def scalars(self, *args, **kwargs):
        return _FakeScalarResult(self._applications)


def _override_agent_and_rewards(agent, rows, applications=()):
    from src.web.dependencies import require_agent

    app.dependency_overrides[require_agent] = lambda: agent

    async def _get_session():
        yield _FakePayoutsSession(rows, applications)

    app.dependency_overrides[get_session] = _get_session


def test_payouts_export_pdf_returns_pdf(client) -> None:
    from src.web.dependencies import require_agent

    agent = SimpleNamespace(id=1, display_name="Светлана Иванова", email="agent@example.com")
    reward = _reward(
        reward_type=RewardType.MAIN,
        status=RewardStatus.APPROVED,
        paid_at=datetime(2026, 2, 12, tzinfo=UTC),
        amount=Decimal("45000"),
    )
    _override_agent_and_rewards(agent, [(reward, "Алексей Смирнов")])

    try:
        response = client.get("/payouts/export.pdf")
    finally:
        app.dependency_overrides.pop(require_agent, None)
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def _get_page(client, agent, rows, applications=(), url="/payouts"):
    from src.web.dependencies import require_agent

    _override_agent_and_rewards(agent, rows, applications)
    try:
        return client.get(url)
    finally:
        app.dependency_overrides.pop(require_agent, None)
        app.dependency_overrides.pop(get_session, None)


def _application(name, stage_code=None) -> SimpleNamespace:
    return SimpleNamespace(full_name=name, deal_stage_code=stage_code)


# --- the payouts list as the React page receives it (JSON) -------------------------------


def _partner() -> Agent:
    return Agent(
        id=1,
        email="agent@example.com",
        role=AgentRole.AGENT,
        is_active=True,
        employment_format=EmploymentFormat.SELF_EMPLOYED,
    )


def _get_api(client, rows, applications=(), query=""):
    """GET the payouts JSON for a partner whose rewards/applications are the given fakes."""
    from src.web.dependencies import optional_agent

    partner = _partner()
    app.dependency_overrides[optional_agent] = lambda: partner

    async def _get_session():
        yield _FakePayoutsSession(rows, applications)

    app.dependency_overrides[get_session] = _get_session
    try:
        return client.get(f"/api/v1/site/payouts{query}")
    finally:
        app.dependency_overrides.pop(optional_agent, None)
        app.dependency_overrides.pop(get_session, None)


def _rows(response) -> dict[str, dict]:
    return {row["client_name"]: row for row in response.json()["rows"]}


def test_payouts_list_shows_a_reward_with_its_type_status_and_amount(client) -> None:
    reward = _reward(
        reward_type=RewardType.ADVANCE,
        status=RewardStatus.APPROVED,
        paid_at=None,
        amount=Decimal("3000"),
    )

    response = _get_api(client, [(reward, "Иван Иванов")])

    assert response.status_code == 200
    row = _rows(response)["Иван Иванов"]
    assert row["type_label"] == "Аванс"
    assert row["status_label"] == "Запланировано"
    assert "3" in row["amount_label"] and "000" in row["amount_label"]


def test_payouts_list_shows_a_reason_only_for_rejected_rewards(client) -> None:
    rejected = _reward(
        reward_type=RewardType.ADVANCE,
        status=RewardStatus.REJECTED,
        amount=Decimal("3000"),
        rejection_reason="Не удалось связаться с клиентом",
    )
    pending = _reward(
        reward_type=RewardType.MAIN,
        status=RewardStatus.PENDING,
        amount=Decimal("10000"),
        rejection_reason="Причина, которую агенту показывать нельзя",
    )

    response = _get_api(client, [(rejected, "Иван Иванов"), (pending, "Пётр Петров")])

    rows = _rows(response)
    assert rows["Иван Иванов"]["status_label"] == "Отклонено"
    assert rows["Иван Иванов"]["rejection_reason"] == "Не удалось связаться с клиентом"
    assert rows["Пётр Петров"]["rejection_reason"] == ""
    assert "показывать нельзя" not in response.text


def test_payouts_list_shows_pre_contract_statuses_for_clients_without_reward(client) -> None:
    applications = [
        _application("Клиент Анализов"),
        _application("Клиент Депозитов", "UC_4FX5NE"),
        _application("Клиент Игнорин", "UC_1BEALQ"),
    ]

    rows = _rows(_get_api(client, [], applications))

    assert rows["Клиент Анализов"]["status_slug"] == "analysis"
    assert rows["Клиент Депозитов"]["status_slug"] == "deposit"
    assert rows["Клиент Игнорин"]["status_slug"] == "ignored"
    assert all(row["amount_label"] == "—" for row in rows.values())


def test_payouts_list_shows_a_pending_reward_as_scheduled_not_as_awaiting_decision(client) -> None:
    reward = _reward(
        reward_type=RewardType.ADVANCE, status=RewardStatus.PENDING, amount=Decimal("3000")
    )

    response = _get_api(client, [(reward, "Иван Иванов")])

    assert _rows(response)["Иван Иванов"]["status_label"] == "Запланировано"
    assert "Ожидает решения" not in [row["status_label"] for row in response.json()["rows"]]


def test_payouts_status_filter_applies_to_clients_without_reward(client) -> None:
    applications = [_application("Клиент Анализов"), _application("Клиент Игнорин", "UC_1BEALQ")]

    rows = _rows(_get_api(client, [], applications, "?status=ignored"))

    assert list(rows) == ["Клиент Игнорин"]


def test_payouts_month_filter_hides_clients_without_reward(client) -> None:
    rows = _rows(_get_api(client, [], [_application("Клиент Анализов")], "?month=2026-02"))

    assert rows == {}


def test_payouts_pdf_contains_only_rows_with_reward(client, monkeypatch) -> None:
    from src.web.routes import payouts as payouts_route

    captured: list = []

    def fake_build(agent_label, filters_label, rows):
        captured.extend(rows)
        return b"%PDF-fake"

    monkeypatch.setattr(payouts_route, "build_payouts_pdf", fake_build)
    reward = _reward(
        reward_type=RewardType.MAIN,
        status=RewardStatus.APPROVED,
        paid_at=datetime(2026, 2, 12, tzinfo=UTC),
        amount=Decimal("10000"),
    )
    agent = SimpleNamespace(id=1, display_name="Партнёр", email="a@example.com")
    response = _get_page(
        client,
        agent,
        [(reward, "Алексей Смирнов")],
        [_application("Клиент Анализов")],
        url="/payouts/export.pdf",
    )

    assert response.status_code == 200
    assert [row.client_name for row in captured] == ["Алексей Смирнов"]
