from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Agent, AgentRole
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import csrf_token, valid_csrf
from src.services.partners import list_partners
from src.web.dependencies import CurrentAdmin
from src.web.routes.pages import templates

router = APIRouter(prefix="/admin/partners", tags=["admin partners"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_class=HTMLResponse)
async def partners_page(
    request: Request, _admin: CurrentAdmin, session: Session, q: str = "", page: int = 1
):
    result = await list_partners(session, q, page)
    return templates.TemplateResponse(
        request=request,
        name="admin_partners.html",
        context={
            "q": q,
            "page_result": result,
            "csrf_token": csrf_token(request.session),
        },
    )


@router.post("/{agent_id}/note")
async def save_note(
    request: Request,
    _admin: CurrentAdmin,
    session: Session,
    agent_id: int,
    note: Annotated[str, Form()] = "",
    q: Annotated[str, Form()] = "",
    page: Annotated[int, Form()] = 1,
    csrf: Annotated[str, Form()] = "",
):
    if valid_csrf(request.session, csrf):
        agent = await session.get(Agent, agent_id)
        if agent is not None:
            agent.admin_note = note.strip() or None
            await session.commit()
    return RedirectResponse(f"/admin/partners?{urlencode({'q': q, 'page': page})}", status_code=303)


@router.post("/{agent_id}/block")
async def block_agent(
    request: Request,
    _admin: CurrentAdmin,
    session: Session,
    agent_id: int,
    reason: Annotated[str, Form()] = "",
    q: Annotated[str, Form()] = "",
    page: Annotated[int, Form()] = 1,
    csrf: Annotated[str, Form()] = "",
):
    if valid_csrf(request.session, csrf) and reason.strip():
        agent = await session.get(Agent, agent_id)
        if agent is not None and agent.role != AgentRole.ADMIN:
            agent.is_active = False
            agent.blocked_reason = reason.strip()
            await session.commit()
    return RedirectResponse(f"/admin/partners?{urlencode({'q': q, 'page': page})}", status_code=303)


@router.post("/{agent_id}/unblock")
async def unblock_agent(
    request: Request,
    _admin: CurrentAdmin,
    session: Session,
    agent_id: int,
    q: Annotated[str, Form()] = "",
    page: Annotated[int, Form()] = 1,
    csrf: Annotated[str, Form()] = "",
):
    if valid_csrf(request.session, csrf):
        agent = await session.get(Agent, agent_id)
        if agent is not None:
            agent.is_active = True
            agent.blocked_reason = None
            await session.commit()
    return RedirectResponse(f"/admin/partners?{urlencode({'q': q, 'page': page})}", status_code=303)
