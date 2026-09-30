"""Onboarding: a new partner picks an employment format before using the cabinet."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Agent, AgentRole, EmploymentFormat
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.email import send_admin_profile_change_notice
from src.services.profile import EMPLOYMENT_FORMAT_OPTIONS
from src.web.api_dependencies import ApiSessionAgent, CsrfProtected
from src.web.routes.api_auth import NextResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/site/onboarding", tags=["site onboarding api"])
Session = Annotated[AsyncSession, Depends(get_session)]


class FormatOption(BaseModel):
    value: EmploymentFormat
    title: str
    text: str


class OnboardingOptions(BaseModel):
    options: list[FormatOption]
    telegram_manager_url: str


class OnboardingRequest(BaseModel):
    employment_format: EmploymentFormat


def _already_done(agent: Agent) -> bool:
    return agent.role == AgentRole.ADMIN or agent.employment_format is not None


@router.get("", response_model=OnboardingOptions)
async def options(_: ApiSessionAgent) -> OnboardingOptions:
    return OnboardingOptions(
        options=[
            FormatOption(value=value, title=title, text=text)
            for value, title, text in EMPLOYMENT_FORMAT_OPTIONS
        ],
        telegram_manager_url=get_settings().telegram_manager_url,
    )


@router.post("", response_model=NextResponse, dependencies=[CsrfProtected])
async def choose_format(
    session: Session, agent: ApiSessionAgent, body: OnboardingRequest
) -> NextResponse:
    if _already_done(agent):
        return NextResponse(next="/cabinet")

    stored_agent = await session.get(Agent, agent.id)
    stored_agent.employment_format = body.employment_format
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
    return NextResponse(next="/cabinet")
