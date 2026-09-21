import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Agent, AgentRole, EmploymentFormat
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.email import send_admin_profile_change_notice
from src.core.security import csrf_token, valid_csrf
from src.services.profile import EMPLOYMENT_FORMAT_OPTIONS
from src.web.dependencies import ONBOARDING_PATH, CurrentAgent
from src.web.routes.pages import templates

logger = logging.getLogger(__name__)
router = APIRouter(tags=["onboarding"])
Session = Annotated[AsyncSession, Depends(get_session)]


def _render(request: Request, *, error: str = "", status_code: int = 200) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="onboarding.html",
        context={
            "onboarding": True,
            "options": EMPLOYMENT_FORMAT_OPTIONS,
            "telegram_manager_url": get_settings().telegram_manager_url,
            "csrf_token": csrf_token(request.session),
            "error": error,
        },
        status_code=status_code,
    )


def _already_done(agent: Agent) -> bool:
    return agent.role == AgentRole.ADMIN or agent.employment_format is not None


@router.get(ONBOARDING_PATH, response_class=HTMLResponse)
async def onboarding_page(request: Request, agent: CurrentAgent):
    if _already_done(agent):
        return RedirectResponse("/cabinet", status_code=303)
    return _render(request)


@router.post(ONBOARDING_PATH)
async def onboarding_submit(
    request: Request,
    session: Session,
    agent: CurrentAgent,
    employment_format: Annotated[EmploymentFormat, Form()],
    csrf: Annotated[str, Form()] = "",
):
    if _already_done(agent):
        return RedirectResponse("/cabinet", status_code=303)
    if not valid_csrf(request.session, csrf):
        return _render(request, error="Обновите страницу и попробуйте ещё раз", status_code=400)

    stored_agent = await session.get(Agent, agent.id)
    stored_agent.employment_format = employment_format
    await session.commit()

    admin_emails = list(get_settings().admin_email_set)
    if admin_emails:
        try:
            await send_admin_profile_change_notice(
                admin_emails,
                stored_agent.display_name or stored_agent.email or str(stored_agent.id),
                ["формат сотрудничества"],
            )
        except Exception:
            logger.warning("Failed to notify admins about onboarding: agent_id=%s", agent.id)
    return RedirectResponse("/cabinet", status_code=303)
