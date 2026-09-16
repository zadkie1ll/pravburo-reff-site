import logging
from io import BytesIO
from typing import Annotated
from uuid import UUID

import qrcode
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Agent, AgentRole, Reward
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.email import send_referral_accepted_notice
from src.core.push import send_push_notice
from src.core.security import csrf_token
from src.core.telegram import send_new_referral_notice, send_partner_notice
from src.services.payouts import build_finance_summary
from src.services.protection import rate_limiter, verify_turnstile
from src.services.referrals import (
    ApplicationInput,
    create_first_application,
    get_link_stats,
    get_network_client_rows,
    record_link_visit,
)
from src.site.crm_client import CRMClient
from src.web.dependencies import CurrentAgent
from src.web.routes.pages import templates

logger = logging.getLogger(__name__)
router = APIRouter(tags=["referrals"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/cabinet", response_class=HTMLResponse)
async def cabinet(request: Request, agent: CurrentAgent, session: Session):
    if agent.role == AgentRole.ADMIN:
        return RedirectResponse("/admin", status_code=303)
    all_rewards = (await session.scalars(select(Reward).where(Reward.agent_id == agent.id))).all()
    settings = get_settings()
    stats = await get_link_stats(session, agent.id)
    client_rows = await get_network_client_rows(session, agent.id)
    finance = build_finance_summary(list(all_rewards))
    return templates.TemplateResponse(
        request=request,
        name="agent_dashboard.html",
        context={
            "agent": agent,
            "referral_url": f"{settings.public_base_url}/r/{agent.referral_code}",
            "bounty_admin_url": settings.bounty_admin_url,
            "link_stats": stats,
            "network_client_rows": client_rows,
            "finance": finance,
            "csrf_token": csrf_token(request.session),
        },
    )


@router.get("/cabinet/referral-qr.png")
async def referral_qr(agent: CurrentAgent) -> Response:
    url = f"{get_settings().public_base_url}/r/{agent.referral_code}"
    image = qrcode.make(url)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return Response(buffer.getvalue(), media_type="image/png")


@router.get("/r/{referral_code}", response_class=HTMLResponse)
async def referral_form(request: Request, referral_code: UUID, session: Session) -> HTMLResponse:
    agent = await session.scalar(select(Agent).where(Agent.referral_code == referral_code))
    if agent is None:
        return templates.TemplateResponse(
            request=request, name="not_found.html", context={}, status_code=404
        )
    await record_link_visit(session, agent.id)
    return templates.TemplateResponse(
        request=request,
        name="referral_form.html",
        context={"agent": agent, "turnstile_site_key": get_settings().turnstile_site_key},
    )


@router.post("/r/{referral_code}")
async def submit_referral(
    request: Request,
    referral_code: UUID,
    session: Session,
    full_name: Annotated[str, Form(max_length=200)],
    phone: Annotated[str, Form(max_length=30)],
    preferred_call_time_msk: Annotated[str, Form(max_length=100)] = "",
    city: Annotated[str, Form(max_length=120)] = "",
    debt_amount: Annotated[str, Form(max_length=80)] = "",
    situation: Annotated[str, Form(max_length=3000)] = "",
    website: Annotated[str, Form(max_length=100)] = "",
    turnstile_token: Annotated[str, Form(alias="cf-turnstile-response")] = "",
):
    agent = await session.scalar(select(Agent).where(Agent.referral_code == referral_code))
    if agent is None:
        return templates.TemplateResponse(
            request=request, name="not_found.html", context={}, status_code=404
        )
    settings = get_settings()
    remote_ip = request.client.host if request.client else "unknown"
    allowed = await rate_limiter.allow(
        remote_ip,
        limit=settings.submission_rate_limit,
        window_seconds=settings.submission_rate_window_seconds,
    )
    captcha_ok = await verify_turnstile(turnstile_token, remote_ip)
    if website or not allowed or not captcha_ok:
        return templates.TemplateResponse(
            request=request,
            name="referral_form.html",
            context={
                "agent": agent,
                "error": "Не удалось отправить форму. Попробуйте позже.",
                "turnstile_site_key": get_settings().turnstile_site_key,
            },
            status_code=429,
        )
    if len(full_name.strip()) < 3:
        return templates.TemplateResponse(
            request=request,
            name="referral_form.html",
            context={
                "agent": agent,
                "error": "Укажите ФИО",
                "turnstile_site_key": get_settings().turnstile_site_key,
            },
            status_code=400,
        )
    try:
        application, created = await create_first_application(
            session,
            agent,
            ApplicationInput(
                full_name=full_name,
                phone=phone,
                preferred_call_time_msk=preferred_call_time_msk,
                city=city,
                debt_amount=debt_amount,
                situation=situation,
            ),
            CRMClient(),
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request=request,
            name="referral_form.html",
            context={
                "agent": agent,
                "error": str(exc),
                "turnstile_site_key": get_settings().turnstile_site_key,
            },
            status_code=400,
        )
    if created and agent.email:
        try:
            await send_referral_accepted_notice(agent.email, application.full_name)
        except Exception:
            logger.warning("Failed to notify agent about accepted referral: agent_id=%s", agent.id)
    if created:
        try:
            await send_push_notice(
                session,
                agent.id,
                "Заявка принята",
                f"Заявка на консультацию от {application.full_name} по вашей рекомендации "
                "принята, мы уже связываемся с ним.",
            )
        except Exception:
            logger.warning("Failed to send push about accepted referral: agent_id=%s", agent.id)
    if created:
        try:
            await send_partner_notice(
                session,
                agent.id,
                f"Заявка на консультацию от {application.full_name} по вашей рекомендации "
                "принята, мы уже связываемся с ним.",
            )
        except Exception:
            logger.warning(
                "Failed to send Telegram notice about accepted referral: agent_id=%s", agent.id
            )
    if created:
        try:
            await send_new_referral_notice(agent, application)
        except Exception:
            logger.warning(
                "Failed to notify Telegram chats about accepted referral: agent_id=%s",
                agent.id,
            )
    return RedirectResponse(f"/r/{referral_code}/success", status_code=303)


@router.get("/r/{referral_code}/success", response_class=HTMLResponse)
async def referral_success(request: Request, referral_code: UUID) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="referral_success.html", context={})
