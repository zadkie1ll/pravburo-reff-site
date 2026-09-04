from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Agent, NetworkOverrideRate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import csrf_token, valid_csrf
from src.services.network import get_descendant_tree, search_agents
from src.web.dependencies import CurrentAdmin
from src.web.routes.pages import templates

router = APIRouter(prefix="/admin/network", tags=["admin network"])
Session = Annotated[AsyncSession, Depends(get_session)]

LEVEL_LABELS = {
    1: "1 уровень (прямой пригласивший)",
    2: "2 уровень (пригласивший пригласившего)",
    3: "3 уровень (только для цепочки из партнёров)",
}


async def _rates_context(request: Request, session: AsyncSession, *, error: str = "") -> dict:
    rows = (
        await session.scalars(select(NetworkOverrideRate).order_by(NetworkOverrideRate.level))
    ).all()
    return {
        "csrf_token": csrf_token(request.session),
        "rates": [
            {
                "level": row.level,
                "label": LEVEL_LABELS.get(row.level, f"{row.level} уровень"),
                "amount": row.amount,
            }
            for row in rows
        ],
        "error": error,
    }


@router.get("/rates", response_class=HTMLResponse)
async def rates_page(request: Request, _admin: CurrentAdmin, session: Session) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="admin_network_rates.html",
        context=await _rates_context(request, session),
    )


@router.post("/rates")
async def rates_submit(
    request: Request,
    _admin: CurrentAdmin,
    session: Session,
    amount_1: Annotated[str, Form()],
    amount_2: Annotated[str, Form()],
    amount_3: Annotated[str, Form()],
    csrf: Annotated[str, Form()] = "",
):
    if not valid_csrf(request.session, csrf):
        return templates.TemplateResponse(
            request=request,
            name="admin_network_rates.html",
            context=await _rates_context(request, session, error="Обновите страницу"),
            status_code=400,
        )
    try:
        new_values = {1: Decimal(amount_1), 2: Decimal(amount_2), 3: Decimal(amount_3)}
    except InvalidOperation:
        return templates.TemplateResponse(
            request=request,
            name="admin_network_rates.html",
            context=await _rates_context(request, session, error="Укажите корректную сумму"),
            status_code=400,
        )
    if any(value < 0 for value in new_values.values()):
        return templates.TemplateResponse(
            request=request,
            name="admin_network_rates.html",
            context=await _rates_context(
                request, session, error="Сумма не может быть отрицательной"
            ),
            status_code=400,
        )
    rows = (await session.scalars(select(NetworkOverrideRate))).all()
    for row in rows:
        if row.level in new_values:
            row.amount = new_values[row.level]
    await session.commit()
    return RedirectResponse("/admin/network/rates", status_code=303)


@router.get("/tree", response_class=HTMLResponse)
async def tree_page(
    request: Request,
    _admin: CurrentAdmin,
    session: Session,
    q: str = "",
    root: int | None = None,
):
    matches = await search_agents(session, q) if q else []
    root_agent = await session.get(Agent, root) if root else None
    tree = await get_descendant_tree(session, root) if root_agent else []
    return templates.TemplateResponse(
        request=request,
        name="admin_network_tree.html",
        context={
            "q": q,
            "matches": matches,
            "root_agent": root_agent,
            "tree": tree,
        },
    )
