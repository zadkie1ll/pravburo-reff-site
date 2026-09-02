from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import RewardStatus, RewardType

from src.core.payout_pdf import build_payouts_pdf
from src.main import app
from src.services.payouts import PayoutRow, format_amount, payout_status_slug


def _reward(**overrides) -> SimpleNamespace:
    defaults = dict(status=RewardStatus.PENDING, paid_at=None)
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


def test_payouts_page_requires_login(client) -> None:
    response = client.get("/payouts", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_payouts_export_requires_login(client) -> None:
    response = client.get("/payouts/export.pdf", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


class _FakeExecuteResult:
    def __init__(self, rows) -> None:
        self._rows = rows

    def all(self):
        return self._rows


class _FakePayoutsSession:
    def __init__(self, rows) -> None:
        self._rows = rows

    async def execute(self, *args, **kwargs):
        return _FakeExecuteResult(self._rows)


def _override_agent_and_rewards(agent, rows):
    from src.web.dependencies import require_agent

    app.dependency_overrides[require_agent] = lambda: agent

    async def _get_session():
        yield _FakePayoutsSession(rows)

    app.dependency_overrides[get_session] = _get_session


def test_payouts_page_renders_rows(client) -> None:
    from src.web.dependencies import require_agent

    agent = SimpleNamespace(id=1)
    reward = _reward(
        reward_type=RewardType.ADVANCE,
        status=RewardStatus.APPROVED,
        paid_at=None,
        amount=Decimal("3000"),
    )
    _override_agent_and_rewards(agent, [(reward, "Иван Иванов")])

    try:
        response = client.get("/payouts")
    finally:
        app.dependency_overrides.pop(require_agent, None)
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert "Иван Иванов" in response.text
    assert "Аванс" in response.text
    assert "Запланировано" in response.text
    assert "3 000" in response.text


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
