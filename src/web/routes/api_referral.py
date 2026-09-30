"""Public referral form (a client leaves an application through a partner's link).

Anonymous: protected by Turnstile, a honeypot and a per-IP rate limit, not by CSRF (there is
no session to forge). Behaves like the HTML form in ``referrals.py``.
"""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Agent, ReferralApplication
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.email import send_referral_accepted_notice
from src.core.push import send_push_notice
from src.core.telegram import send_new_referral_notice, send_partner_notice
from src.services.protection import rate_limiter, verify_turnstile
from src.services.referrals import ApplicationInput, create_first_application, record_link_visit
from src.site.crm_client import CRMClient
from src.web.api_errors import ApiError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/site/referral", tags=["site referral api"])
Session = Annotated[AsyncSession, Depends(get_session)]

ACCEPTED_TEXT = (
    "Заявка на консультацию от {name} по вашей рекомендации принята, мы уже связываемся с ним."
)


class ReferralFormInfo(BaseModel):
    turnstile_site_key: str


class ReferralSubmission(BaseModel):
    full_name: str = Field(max_length=200)
    phone: str = Field(max_length=30)
    preferred_call_time_msk: str = Field(default="", max_length=100)
    city: str = Field(default="", max_length=120)
    debt_amount: str = Field(default="", max_length=80)
    situation: str = Field(default="", max_length=3000)
    # Honeypot: humans never see this field, bots fill it in.
    website: str = Field(default="", max_length=100)
    turnstile_token: str = Field(default="", max_length=4096)


class SubmissionResult(BaseModel):
    ok: bool = True


async def _find_agent(session: AsyncSession, referral_code: UUID) -> Agent:
    agent = await session.scalar(select(Agent).where(Agent.referral_code == referral_code))
    if agent is None:
        raise ApiError(404, "not_found", "Ссылка не найдена")
    return agent


async def _notify_partner(
    session: AsyncSession, agent: Agent, application: ReferralApplication
) -> None:
    """Every channel is best effort: a failing notice must not lose the client's application."""
    text = ACCEPTED_TEXT.format(name=application.full_name)
    channels = []
    if agent.email:
        channels.append(send_referral_accepted_notice(agent.email, application.full_name))
    channels.append(send_push_notice(session, agent.id, "Заявка принята", text))
    channels.append(send_partner_notice(session, agent.id, text))
    channels.append(send_new_referral_notice(agent, application))
    for channel in channels:
        try:
            await channel
        except Exception:
            logger.warning("Failed to notify about accepted referral: agent_id=%s", agent.id)


@router.get("/{referral_code}", response_model=ReferralFormInfo)
async def form_info(referral_code: UUID, session: Session) -> ReferralFormInfo:
    agent = await _find_agent(session, referral_code)
    # Opening the form counts as a visit of the link (same as the old page load).
    await record_link_visit(session, agent.id)
    return ReferralFormInfo(turnstile_site_key=get_settings().turnstile_site_key)


@router.post("/{referral_code}", response_model=SubmissionResult)
async def submit(
    request: Request, referral_code: UUID, session: Session, body: ReferralSubmission
) -> SubmissionResult:
    agent = await _find_agent(session, referral_code)
    settings = get_settings()
    remote_ip = request.client.host if request.client else "unknown"
    allowed = await rate_limiter.allow(
        remote_ip,
        limit=settings.submission_rate_limit,
        window_seconds=settings.submission_rate_window_seconds,
    )
    captcha_ok = await verify_turnstile(body.turnstile_token, remote_ip)
    if body.website or not allowed or not captcha_ok:
        # One answer for bots, rate limit and captcha: tells an attacker nothing.
        raise ApiError(429, "submission_rejected", "Не удалось отправить форму. Попробуйте позже.")
    if len(body.full_name.strip()) < 3:
        raise ApiError(400, "validation_error", "Укажите ФИО", {"full_name": "too_short"})
    try:
        application, created = await create_first_application(
            session,
            agent,
            ApplicationInput(
                full_name=body.full_name,
                phone=body.phone,
                preferred_call_time_msk=body.preferred_call_time_msk,
                city=body.city,
                debt_amount=body.debt_amount,
                situation=body.situation,
            ),
            CRMClient(),
        )
    except ValueError as exc:
        raise ApiError(400, "application_invalid", str(exc)) from exc
    if created:
        await _notify_partner(session, agent, application)
    return SubmissionResult()
