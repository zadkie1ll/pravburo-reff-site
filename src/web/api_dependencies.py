"""JSON counterparts of the redirecting dependencies in ``dependencies.py``.

The HTML routes answer "not logged in" with a 303 redirect to /login, which a
``fetch`` call would follow and choke on. The API answers with 401/403 JSON and
lets the frontend decide where to send the user.
"""

import logging
from typing import Annotated

from fastapi import Depends, Request
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Agent, AgentRole
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import valid_csrf
from src.web.api_errors import ApiError, forbidden, unauthorized
from src.web.dependencies import optional_agent

logger = logging.getLogger(__name__)

CSRF_HEADER = "X-CSRF-Token"


def onboarding_required(agent: Agent) -> bool:
    """A partner must pick a cooperation format before using the cabinet."""
    return agent.role == AgentRole.AGENT and agent.employment_format is None


async def api_session_agent(
    request: Request, agent: Annotated[Agent | None, Depends(optional_agent)]
) -> Agent:
    """A logged-in, active user, even one who has not finished onboarding yet."""
    if agent is None:
        raise unauthorized()
    if not agent.is_active:
        request.session.clear()
        raise unauthorized()
    return agent


async def api_agent(agent: Annotated[Agent, Depends(api_session_agent)]) -> Agent:
    if onboarding_required(agent):
        raise ApiError(403, "onboarding_required", "Сначала выберите форму сотрудничества")
    return agent


async def api_admin(agent: Annotated[Agent, Depends(api_agent)]) -> Agent:
    if agent.role != AgentRole.ADMIN:
        raise forbidden()
    return agent


async def api_partner(agent: Annotated[Agent, Depends(api_agent)]) -> Agent:
    """Cabinet pages belong to partners; an admin has the admin panel instead."""
    if agent.role == AgentRole.ADMIN:
        raise forbidden()
    return agent


async def api_pending_admin(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> Agent:
    """An admin who has given the right password but not yet the 2FA code (no full session)."""
    agent_id = request.session.get("pending_admin_id")
    agent = await session.get(Agent, agent_id) if agent_id else None
    if agent is None or agent.role != AgentRole.ADMIN or not agent.is_active:
        raise unauthorized()
    return agent


async def require_csrf_header(request: Request) -> None:
    """State-changing JSON requests must echo the session's CSRF token in a header."""
    if not valid_csrf(request.session, request.headers.get(CSRF_HEADER, "")):
        raise ApiError(403, "csrf_failed", "Обновите страницу и попробуйте ещё раз")


ApiSessionAgent = Annotated[Agent, Depends(api_session_agent)]
ApiAgent = Annotated[Agent, Depends(api_agent)]
ApiAdmin = Annotated[Agent, Depends(api_admin)]
ApiPartner = Annotated[Agent, Depends(api_partner)]
ApiPendingAdmin = Annotated[Agent, Depends(api_pending_admin)]
CsrfProtected = Depends(require_csrf_header)
