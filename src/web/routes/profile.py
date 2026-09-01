import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import EmploymentFormat
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.email import send_admin_profile_change_notice
from src.core.security import csrf_token, valid_csrf
from src.services.profile import ProfileInput, update_profile
from src.web.dependencies import CurrentAgent
from src.web.routes.pages import templates

logger = logging.getLogger(__name__)
router = APIRouter(tags=["profile"])
Session = Annotated[AsyncSession, Depends(get_session)]

EMPLOYMENT_FORMAT_LABELS = {
    EmploymentFormat.SELF_EMPLOYED: "Самозанятый",
    EmploymentFormat.INDIVIDUAL_ENTREPRENEUR: "ИП",
    EmploymentFormat.INDIVIDUAL: "Физлицо",
}


def _context(agent, *, error: str = "", info: str = "") -> dict:
    return {
        "agent": agent,
        "employment_formats": EMPLOYMENT_FORMAT_LABELS,
        "error": error,
        "info": info,
    }


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, agent: CurrentAgent) -> HTMLResponse:
    context = _context(agent)
    context["csrf_token"] = csrf_token(request.session)
    return templates.TemplateResponse(request=request, name="profile.html", context=context)


@router.post("/profile")
async def profile_update(
    request: Request,
    session: Session,
    agent: CurrentAgent,
    display_name: Annotated[str, Form(max_length=200)],
    employment_format: Annotated[EmploymentFormat, Form()],
    payout_details: Annotated[str, Form(max_length=200)] = "",
    inn: Annotated[str, Form(max_length=12)] = "",
    csrf: Annotated[str, Form()] = "",
):
    if not valid_csrf(request.session, csrf):
        context = _context(agent, error="Обновите страницу")
        context["csrf_token"] = csrf_token(request.session)
        return templates.TemplateResponse(
            request=request, name="profile.html", context=context, status_code=400
        )
    try:
        changed_fields = await update_profile(
            session,
            agent,
            ProfileInput(
                display_name=display_name,
                employment_format=employment_format,
                payout_details=payout_details,
                inn=inn,
            ),
        )
    except ValueError as exc:
        context = _context(agent, error=str(exc))
        context["csrf_token"] = csrf_token(request.session)
        return templates.TemplateResponse(
            request=request, name="profile.html", context=context, status_code=400
        )

    if changed_fields:
        admin_emails = list(get_settings().admin_email_set)
        if admin_emails:
            try:
                await send_admin_profile_change_notice(
                    admin_emails, agent.display_name or agent.email or str(agent.id), changed_fields
                )
            except Exception:
                logger.warning(
                    "Failed to notify admins about profile change: agent_id=%s", agent.id
                )

    context = _context(agent, info="Профиль обновлён")
    context["csrf_token"] = csrf_token(request.session)
    return templates.TemplateResponse(request=request, name="profile.html", context=context)
