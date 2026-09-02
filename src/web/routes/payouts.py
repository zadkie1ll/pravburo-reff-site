from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, Response
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import RewardType
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.payout_pdf import build_payouts_pdf
from src.services.payouts import (
    REWARD_TYPE_LABELS,
    STATUS_LABELS,
    PayoutFilters,
    get_payout_rows,
)
from src.web.dependencies import CurrentAgent
from src.web.routes.pages import templates

router = APIRouter(tags=["payouts"])
Session = Annotated[AsyncSession, Depends(get_session)]


def _filters_label(filters: PayoutFilters) -> str:
    parts = []
    if filters.month:
        parts.append(f"месяц: {filters.month}")
    if filters.reward_type:
        parts.append(
            f"тип: {REWARD_TYPE_LABELS.get(RewardType(filters.reward_type), filters.reward_type)}"
        )
    if filters.status:
        parts.append(f"статус: {STATUS_LABELS.get(filters.status, filters.status)}")
    return ", ".join(parts)


@router.get("/payouts", response_class=HTMLResponse)
async def payouts_page(
    request: Request,
    agent: CurrentAgent,
    session: Session,
    month: Annotated[str, Query()] = "",
    reward_type: Annotated[str, Query()] = "",
    status: Annotated[str, Query()] = "",
) -> HTMLResponse:
    filters = PayoutFilters(month=month, reward_type=reward_type, status=status)
    rows = await get_payout_rows(session, agent.id, filters)
    return templates.TemplateResponse(
        request=request,
        name="payouts.html",
        context={
            "agent": agent,
            "rows": rows,
            "filters": filters,
            "reward_types": REWARD_TYPE_LABELS,
            "statuses": STATUS_LABELS,
        },
    )


@router.get("/payouts/export.pdf")
async def payouts_export_pdf(
    agent: CurrentAgent,
    session: Session,
    month: Annotated[str, Query()] = "",
    reward_type: Annotated[str, Query()] = "",
    status: Annotated[str, Query()] = "",
) -> Response:
    filters = PayoutFilters(month=month, reward_type=reward_type, status=status)
    rows = await get_payout_rows(session, agent.id, filters)
    agent_label = agent.display_name or agent.email or f"Партнёр #{agent.id}"
    pdf_bytes = build_payouts_pdf(agent_label, _filters_label(filters), rows)
    return Response(
        pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="payouts.pdf"'},
    )
