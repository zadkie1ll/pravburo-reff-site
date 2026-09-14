import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Agent, AgentCredential, AgentIdentity, EmploymentFormat
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.email import send_admin_profile_change_notice, send_code
from src.core.security import (
    csrf_token,
    generate_code,
    normalize_email,
    valid_csrf,
    valid_email,
    verify_password,
)
from src.core.telegram import send_payout_details_changed_notice
from src.services.profile import EMPLOYMENT_FORMAT_LABELS, ProfileInput, update_profile
from src.web.dependencies import CurrentAgent
from src.web.routes.pages import templates

logger = logging.getLogger(__name__)
router = APIRouter(tags=["profile"])
Session = Annotated[AsyncSession, Depends(get_session)]

EMAIL_CHANGE_CODE_TTL_SECONDS = 600


async def _is_yandex_linked(session: AsyncSession, agent_id: int) -> bool:
    return (
        await session.scalar(
            select(AgentIdentity.id).where(
                AgentIdentity.agent_id == agent_id, AgentIdentity.provider == "yandex"
            )
        )
    ) is not None


async def _render(
    request: Request,
    agent: Agent,
    session: AsyncSession,
    *,
    error: str = "",
    info: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    pending = request.session.get("pending_email_change")
    context = {
        "agent": agent,
        "employment_formats": EMPLOYMENT_FORMAT_LABELS,
        "error": error,
        "info": info,
        "pending_email": pending["email"] if pending else "",
        "csrf_token": csrf_token(request.session),
        "yandex_linked": await _is_yandex_linked(session, agent.id),
        "yandex_enabled": bool(
            get_settings().yandex_client_id and get_settings().yandex_client_secret
        ),
    }
    return templates.TemplateResponse(
        request=request, name="profile.html", context=context, status_code=status_code
    )


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request, agent: CurrentAgent, session: Session, info: str = "", error: str = ""
) -> HTMLResponse:
    return await _render(request, agent, session, info=info, error=error)


@router.post("/profile")
async def profile_update(
    request: Request,
    session: Session,
    agent: CurrentAgent,
    display_name: Annotated[str, Form(max_length=200)],
    employment_format: Annotated[EmploymentFormat, Form()],
    payout_details: Annotated[str, Form(max_length=200)] = "",
    inn: Annotated[str, Form(max_length=12)] = "",
    phone: Annotated[str, Form(max_length=20)] = "",
    csrf: Annotated[str, Form()] = "",
):
    if not valid_csrf(request.session, csrf):
        return await _render(request, agent, session, error="Обновите страницу", status_code=400)
    try:
        changed_fields = await update_profile(
            session,
            agent,
            ProfileInput(
                display_name=display_name,
                employment_format=employment_format,
                payout_details=payout_details,
                inn=inn,
                phone=phone,
            ),
        )
    except ValueError as exc:
        return await _render(request, agent, session, error=str(exc), status_code=400)

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
        if "реквизиты для выплат" in changed_fields:
            try:
                await send_payout_details_changed_notice(agent)
            except Exception:
                logger.warning(
                    "Failed to notify Telegram chats about payout details change: agent_id=%s",
                    agent.id,
                )

    return await _render(request, agent, session, info="Профиль обновлён")


@router.post("/profile/email")
async def profile_email_begin(
    request: Request,
    session: Session,
    agent: CurrentAgent,
    new_email: Annotated[str, Form(max_length=254)],
    current_password: Annotated[str, Form()],
    csrf: Annotated[str, Form()] = "",
):
    if not valid_csrf(request.session, csrf):
        return await _render(request, agent, session, error="Обновите страницу", status_code=400)
    if not valid_email(new_email):
        return await _render(
            request, agent, session, error="Укажите корректную почту", status_code=400
        )
    normalized = normalize_email(new_email)
    if normalized == agent.email:
        return await _render(
            request, agent, session, error="Это и так ваша текущая почта", status_code=400
        )
    credential = await session.get(AgentCredential, agent.id)
    if credential is None or not verify_password(current_password, credential.password_hash):
        return await _render(request, agent, session, error="Неверный пароль", status_code=400)
    if await session.scalar(select(Agent.id).where(Agent.email == normalized)):
        return await _render(
            request,
            agent,
            session,
            error="Эта почта уже используется другим аккаунтом",
            status_code=400,
        )

    code = generate_code()
    request.session["pending_email_change"] = {
        "email": normalized,
        "code": code,
        "expires_at": (
            datetime.now(UTC) + timedelta(seconds=EMAIL_CHANGE_CODE_TTL_SECONDS)
        ).isoformat(),
        "attempts": 0,
    }
    await send_code(normalized, code, "смена почты")
    return await _render(request, agent, session, info="Код отправлен на новую почту")


@router.post("/profile/email/confirm")
async def profile_email_confirm(
    request: Request,
    session: Session,
    agent: CurrentAgent,
    code: Annotated[str, Form()],
    csrf: Annotated[str, Form()] = "",
):
    if not valid_csrf(request.session, csrf):
        return await _render(request, agent, session, error="Обновите страницу", status_code=400)
    pending = request.session.get("pending_email_change")
    if pending is None:
        return await _render(
            request, agent, session, error="Нет активного запроса на смену почты", status_code=400
        )
    expired = datetime.fromisoformat(pending["expires_at"]) < datetime.now(UTC)
    if expired or pending["attempts"] >= 5:
        request.session.pop("pending_email_change", None)
        return await _render(
            request, agent, session, error="Код истёк, начните заново", status_code=400
        )
    if not secrets.compare_digest(pending["code"], code.strip()):
        pending["attempts"] += 1
        request.session["pending_email_change"] = pending
        return await _render(request, agent, session, error="Неверный код", status_code=400)
    if await session.scalar(select(Agent.id).where(Agent.email == pending["email"])):
        request.session.pop("pending_email_change", None)
        return await _render(
            request,
            agent,
            session,
            error="Эта почта уже используется другим аккаунтом",
            status_code=400,
        )

    agent.email = pending["email"]
    await session.commit()
    request.session.pop("pending_email_change", None)
    return await _render(request, agent, session, info="Почта изменена")
