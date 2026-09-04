from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Agent, AgentRole
from sqlalchemy.ext.asyncio import AsyncSession


async def optional_agent(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> Agent | None:
    agent_id = request.session.get("agent_id")
    return await session.get(Agent, agent_id) if agent_id else None


async def require_agent(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> Agent:
    agent = await optional_agent(request, session)
    if agent is None:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return agent


async def require_admin(agent: Annotated[Agent, Depends(require_agent)]) -> Agent:
    if agent.role != AgentRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return agent


async def require_pending_admin(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> Agent:
    """The admin has verified their password but not yet their TOTP code."""
    agent_id = request.session.get("pending_admin_id")
    agent = await session.get(Agent, agent_id) if agent_id else None
    if agent is None or agent.role != AgentRole.ADMIN:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return agent


CurrentAgent = Annotated[Agent, Depends(require_agent)]
OptionalAgent = Annotated[Agent | None, Depends(optional_agent)]
CurrentAdmin = Annotated[Agent, Depends(require_admin)]
PendingAdmin = Annotated[Agent, Depends(require_pending_admin)]
