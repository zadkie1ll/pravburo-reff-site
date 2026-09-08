import logging
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Agent
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.email import send_payout_paid_notice
from src.core.push import send_push_notice
from src.core.security import csrf_token, valid_csrf
from src.services.admin_payouts import (
    STATUS_LABELS,
    build_calendar,
    get_overdue_days,
    list_payout_rows,
    mark_paid,
    month_label,
    set_overdue_days,
)
from src.services.payouts import format_amount
from src.web.dependencies import CurrentAdmin
from src.web.routes.pages import templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/payouts", tags=["admin payouts"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_class=HTMLResponse)
async def payouts_page(
    request: Request,
    _admin: CurrentAdmin,
    session: Session,
    year: int = 0,
    month: int = 0,
    status: str = "",
):
    today = datetime.now(UTC).date()
    year = year or today.year
    month = month or today.month
    overdue_days = await get_overdue_days(session)
    rows = await list_payout_rows(session, status, overdue_days)
    weeks = build_calendar(rows, year, month, today)
    overdue_rows = (
        rows
        if status == "overdue"
        else await list_payout_rows(session, "overdue", overdue_days)
    )

    prev_month, prev_year = (12, year - 1) if month == 1 else (month - 1, year)
    next_month, next_year = (1, year + 1) if month == 12 else (month + 1, year)

    return templates.TemplateResponse(
        request=request,
        name="admin_payouts.html",
        context={
            "year": year,
            "month": month,
            "month_label": month_label(year, month),
            "status": status,
            "status_options": STATUS_LABELS,
            "weeks": weeks,
            "overdue_rows": overdue_rows,
            "overdue_days": overdue_days,
            "prev_year": prev_year,
            "prev_month": prev_month,
            "next_year": next_year,
            "next_month": next_month,
            "csrf_token": csrf_token(request.session),
        },
    )


@router.post("/settings")
async def payouts_settings(
    request: Request,
    _admin: CurrentAdmin,
    session: Session,
    overdue_days: Annotated[int, Form()],
    csrf: Annotated[str, Form()] = "",
):
    if valid_csrf(request.session, csrf) and overdue_days > 0:
        await set_overdue_days(session, overdue_days)
    return RedirectResponse("/admin/payouts", status_code=303)


@router.post("/{reward_id}/mark-paid")
async def payouts_mark_paid(
    request: Request,
    _admin: CurrentAdmin,
    session: Session,
    reward_id: int,
    year: Annotated[int, Form()] = 0,
    month: Annotated[int, Form()] = 0,
    status: Annotated[str, Form()] = "",
    csrf: Annotated[str, Form()] = "",
):
    if valid_csrf(request.session, csrf):
        reward = await mark_paid(session, reward_id)
        if reward is not None:
            agent = await session.get(Agent, reward.agent_id)
            if agent is not None and agent.email:
                try:
                    await send_payout_paid_notice(agent.email, format_amount(reward.amount))
                except Exception:
                    logger.warning(
                        "Failed to notify agent about paid reward: reward_id=%s", reward.id
                    )
            if agent is not None:
                try:
                    await send_push_notice(
                        session,
                        agent.id,
                        "Выплата произведена",
                        f"Ваша выплата на сумму {format_amount(reward.amount)} произведена.",
                    )
                except Exception:
                    logger.warning(
                        "Failed to send push about paid reward: reward_id=%s", reward.id
                    )
    return RedirectResponse(
        f"/admin/payouts?{urlencode({'year': year, 'month': month, 'status': status})}",
        status_code=303,
    )
