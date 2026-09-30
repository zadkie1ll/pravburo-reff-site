"""Partner profile: personal data, e-mail change with a code, linked Yandex account."""

import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Agent, AgentCredential, AgentIdentity, EmploymentFormat
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.email import send_admin_profile_change_notice, send_code
from src.core.security import (
    generate_code,
    normalize_email,
    valid_email,
    verify_password,
)
from src.core.telegram import send_payout_details_changed_notice
from src.services.profile import EMPLOYMENT_FORMAT_LABELS, ProfileInput, update_profile
from src.web.api_dependencies import ApiAgent, CsrfProtected
from src.web.api_errors import ApiError
from src.web.routes.api_auth import InfoResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/site/profile", tags=["site profile api"])
Session = Annotated[AsyncSession, Depends(get_session)]

EMAIL_CHANGE_CODE_TTL_SECONDS = 600
MAX_CODE_ATTEMPTS = 5
# Own session key: the legacy form route keeps a different shape under "pending_email_change".
PENDING_KEY = "email_change"


class FormatOption(BaseModel):
    value: EmploymentFormat
    label: str


class ProfileResponse(BaseModel):
    display_name: str
    email: str | None
    phone: str | None
    employment_format: EmploymentFormat | None
    payout_details: str | None
    inn: str | None
    registered_at_label: str
    is_active: bool
    is_admin: bool
    pending_email: str
    yandex_enabled: bool
    yandex_linked: bool
    employment_formats: list[FormatOption]


class ProfileUpdate(BaseModel):
    display_name: str = Field(max_length=200)
    phone: str = Field(default="", max_length=20)
    employment_format: EmploymentFormat
    payout_details: str = Field(default="", max_length=200)
    inn: str = Field(default="", max_length=12)


class EmailChangeRequest(BaseModel):
    new_email: str = Field(max_length=254)
    current_password: str = Field(max_length=256)


class EmailConfirmRequest(BaseModel):
    code: str = Field(max_length=32)


def _code_digest(email: str, code: str) -> str:
    """Keyed digest of the code. The session cookie is signed but readable by its owner,
    so the plain code must never be stored in it."""
    key = get_settings().session_secret.encode()
    return hmac.new(key, f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


async def _is_yandex_linked(session: AsyncSession, agent_id: int) -> bool:
    found = await session.scalar(
        select(AgentIdentity.id).where(
            AgentIdentity.agent_id == agent_id, AgentIdentity.provider == "yandex"
        )
    )
    return found is not None


async def _profile(request: Request, session: AsyncSession, agent: Agent) -> ProfileResponse:
    settings = get_settings()
    pending = request.session.get(PENDING_KEY)
    return ProfileResponse(
        display_name=agent.display_name,
        email=agent.email,
        phone=agent.phone_normalized,
        employment_format=agent.employment_format,
        payout_details=agent.payout_details,
        inn=agent.inn,
        registered_at_label=agent.created_at.strftime("%d.%m.%Y"),
        is_active=agent.is_active,
        is_admin=agent.role.value == "admin",
        pending_email=pending["email"] if pending else "",
        yandex_enabled=bool(settings.yandex_client_id and settings.yandex_client_secret),
        yandex_linked=await _is_yandex_linked(session, agent.id),
        employment_formats=[
            FormatOption(value=value, label=label)
            for value, label in EMPLOYMENT_FORMAT_LABELS.items()
        ],
    )


@router.get("", response_model=ProfileResponse)
async def get_profile(request: Request, session: Session, agent: ApiAgent) -> ProfileResponse:
    return await _profile(request, session, agent)


@router.post("", response_model=ProfileResponse, dependencies=[CsrfProtected])
async def update(
    request: Request, session: Session, agent: ApiAgent, body: ProfileUpdate
) -> ProfileResponse:
    try:
        changed_fields = await update_profile(
            session,
            agent,
            ProfileInput(
                display_name=body.display_name,
                employment_format=body.employment_format,
                payout_details=body.payout_details,
                inn=body.inn,
                phone=body.phone,
            ),
        )
    except ValueError as exc:
        raise ApiError(400, "profile_invalid", str(exc)) from exc

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
    return await _profile(request, session, agent)


@router.post("/email", response_model=InfoResponse, dependencies=[CsrfProtected])
async def email_begin(
    request: Request, session: Session, agent: ApiAgent, body: EmailChangeRequest
) -> InfoResponse:
    if not valid_email(body.new_email):
        raise ApiError(
            400, "validation_error", "Укажите корректную почту", {"new_email": "invalid"}
        )
    normalized = normalize_email(body.new_email)
    if normalized == agent.email:
        raise ApiError(400, "same_email", "Это и так ваша текущая почта")
    credential = await session.get(AgentCredential, agent.id)
    if credential is None or not verify_password(body.current_password, credential.password_hash):
        raise ApiError(400, "invalid_password", "Неверный пароль")
    if await session.scalar(select(Agent.id).where(Agent.email == normalized)):
        raise ApiError(400, "email_taken", "Эта почта уже используется другим аккаунтом")

    code = generate_code()
    request.session[PENDING_KEY] = {
        "email": normalized,
        "digest": _code_digest(normalized, code),
        "expires_at": (
            datetime.now(UTC) + timedelta(seconds=EMAIL_CHANGE_CODE_TTL_SECONDS)
        ).isoformat(),
        "attempts": 0,
    }
    await send_code(normalized, code, "смена почты")
    return InfoResponse(info="Код отправлен на новую почту")


@router.post("/email/confirm", response_model=InfoResponse, dependencies=[CsrfProtected])
async def email_confirm(
    request: Request, session: Session, agent: ApiAgent, body: EmailConfirmRequest
) -> InfoResponse:
    pending = request.session.get(PENDING_KEY)
    if pending is None:
        raise ApiError(400, "no_pending_change", "Нет активного запроса на смену почты")
    expired = datetime.fromisoformat(pending["expires_at"]) < datetime.now(UTC)
    if expired or pending["attempts"] >= MAX_CODE_ATTEMPTS:
        request.session.pop(PENDING_KEY, None)
        raise ApiError(400, "code_expired", "Код истёк, начните заново")
    submitted = _code_digest(pending["email"], body.code.strip())
    if not secrets.compare_digest(pending["digest"], submitted):
        pending["attempts"] += 1
        request.session[PENDING_KEY] = pending
        raise ApiError(400, "invalid_code", "Неверный код")
    if await session.scalar(select(Agent.id).where(Agent.email == pending["email"])):
        request.session.pop(PENDING_KEY, None)
        raise ApiError(400, "email_taken", "Эта почта уже используется другим аккаунтом")

    agent.email = pending["email"]
    await session.commit()
    request.session.pop(PENDING_KEY, None)
    return InfoResponse(info="Почта изменена")
