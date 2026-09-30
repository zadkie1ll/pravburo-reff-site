"""Admin: payout calendar, overdue payouts, marking a payout as paid."""

import logging
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Agent, Reward
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.email import send_payout_paid_notice
from src.core.push import send_push_notice
from src.core.telegram import send_partner_notice
from src.services.admin_payouts import (
    STATUS_LABELS,
    PayoutRow,
    build_calendar,
    get_overdue_days,
    list_payout_rows,
    mark_paid,
    month_label,
    set_overdue_days,
)
from src.services.payouts import format_amount
from src.web.api_dependencies import ApiAdmin, CsrfProtected
from src.web.api_errors import ApiError
from src.web.api_schemas import OkResponse, OptionOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/site/admin/payouts", tags=["site admin api"])
Session = Annotated[AsyncSession, Depends(get_session)]

StatusFilter = Literal["pending", "scheduled", "overdue", "paid", "rejected"]
MAX_OVERDUE_DAYS = 365


class MonthRef(BaseModel):
    year: int
    month: int


class CalendarEntry(BaseModel):
    reward_id: int
    client_name: str
    amount_label: str
    status_slug: str
    can_mark_paid: bool


class CalendarDayOut(BaseModel):
    day: int
    in_month: bool
    is_today: bool
    entries: list[CalendarEntry]


class OverdueRow(BaseModel):
    reward_id: int
    agent_name: str
    client_name: str
    type_label: str
    amount_label: str
    target_date_label: str


class PayoutsCalendar(BaseModel):
    year: int
    month: int
    month_label: str
    status: str
    statuses: list[OptionOut]
    overdue_days: int
    previous: MonthRef
    next: MonthRef
    weeks: list[list[CalendarDayOut]]
    overdue_rows: list[OverdueRow]


class SettingsRequest(BaseModel):
    overdue_days: int = Field(ge=1, le=MAX_OVERDUE_DAYS)


def _entry(row: PayoutRow) -> CalendarEntry:
    return CalendarEntry(
        reward_id=row.reward.id,
        client_name=row.client_name,
        amount_label=row.amount_label,
        status_slug=row.status_slug,
        can_mark_paid=row.status_slug in ("scheduled", "overdue"),
    )


def _overdue(row: PayoutRow) -> OverdueRow:
    return OverdueRow(
        reward_id=row.reward.id,
        agent_name=row.agent_name,
        client_name=row.client_name,
        type_label=row.type_label,
        amount_label=row.amount_label,
        target_date_label=row.target_date.strftime("%d.%m.%Y") if row.target_date else "—",
    )


def _neighbour(year: int, month: int, step: int) -> MonthRef:
    index = year * 12 + (month - 1) + step
    return MonthRef(year=index // 12, month=index % 12 + 1)


@router.get("", response_model=PayoutsCalendar)
async def calendar_page(
    _: ApiAdmin,
    session: Session,
    year: Annotated[int | None, Query(ge=2000, le=2200)] = None,
    month: Annotated[int | None, Query(ge=1, le=12)] = None,
    status: Annotated[StatusFilter | None, Query()] = None,
) -> PayoutsCalendar:
    today = datetime.now(UTC).date()
    year = year or today.year
    month = month or today.month
    overdue_days = await get_overdue_days(session)
    rows = await list_payout_rows(session, status or "", overdue_days)
    weeks = build_calendar(rows, year, month, today)
    overdue_rows = (
        rows if status == "overdue" else await list_payout_rows(session, "overdue", overdue_days)
    )
    return PayoutsCalendar(
        year=year,
        month=month,
        month_label=month_label(year, month),
        status=status or "",
        statuses=[OptionOut(value=slug, label=label) for slug, label in STATUS_LABELS.items()],
        overdue_days=overdue_days,
        previous=_neighbour(year, month, -1),
        next=_neighbour(year, month, 1),
        weeks=[
            [
                CalendarDayOut(
                    day=day.date.day,
                    in_month=day.in_month,
                    is_today=day.is_today,
                    entries=[_entry(row) for row in day.rows],
                )
                for day in week
            ]
            for week in weeks
        ],
        overdue_rows=[_overdue(row) for row in overdue_rows],
    )


@router.post("/settings", response_model=OkResponse, dependencies=[CsrfProtected])
async def save_settings(_: ApiAdmin, session: Session, body: SettingsRequest) -> OkResponse:
    await set_overdue_days(session, body.overdue_days)
    return OkResponse()


async def _tell_partner(session: AsyncSession, reward: Reward) -> None:
    """E-mail, push and Telegram are best effort: the payout is already recorded."""
    agent = await session.get(Agent, reward.agent_id)
    if agent is None:
        return
    amount = format_amount(reward.amount)
    text = f"Ваша выплата на сумму {amount} произведена."
    channels = []
    if agent.email:
        channels.append(send_payout_paid_notice(agent.email, amount))
    channels.append(send_push_notice(session, agent.id, "Выплата произведена", text))
    channels.append(send_partner_notice(session, agent.id, text))
    for channel in channels:
        try:
            await channel
        except Exception:
            logger.warning("Failed to notify about a paid reward: reward_id=%s", reward.id)


@router.post("/{reward_id}/mark-paid", response_model=OkResponse, dependencies=[CsrfProtected])
async def mark_reward_paid(_: ApiAdmin, session: Session, reward_id: int) -> OkResponse:
    if await session.get(Reward, reward_id) is None:
        raise ApiError(404, "not_found", "Выплата не найдена")
    reward = await mark_paid(session, reward_id)
    if reward is None:
        # Not approved yet, or already paid (e.g. a double click): nothing was changed.
        raise ApiError(
            409,
            "not_payable",
            "Эту выплату нельзя отметить выплаченной: она не одобрена или уже выплачена",
        )
    await _tell_partner(session, reward)
    return OkResponse()
