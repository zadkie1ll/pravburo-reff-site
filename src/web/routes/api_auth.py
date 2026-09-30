"""JSON authentication endpoints for the React frontend.

Same rules as the HTML forms in ``auth.py`` (rate limit, blocked accounts, admin 2FA
step), but answering with JSON instead of redirects. The old form routes go away once
every auth page is migrated.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Agent, AgentRole
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import (
    authenticate,
    begin_password_reset,
    begin_registration,
    confirm_password_reset,
    confirm_registration,
)
from src.core.config import get_settings
from src.core.email import send_code
from src.core.security import normalize_email, valid_email
from src.core.telegram import send_new_partner_notice
from src.services.protection import login_rate_limiter
from src.web.api_dependencies import CsrfProtected
from src.web.api_errors import ApiError
from src.web.dependencies import OptionalAgent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/site/auth", tags=["site auth api"])
MIN_PASSWORD_LENGTH = 6
Session = Annotated[AsyncSession, Depends(get_session)]


class AuthConfig(BaseModel):
    telegram_bot_username: str
    telegram_auth_url: str
    yandex_enabled: bool


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)


class NextResponse(BaseModel):
    # Where the browser goes next (a page still rendered by the backend or by React).
    next: str


def _next_after_login(request: Request, agent: Agent) -> str:
    """Start the session (or the admin's pending 2FA step) and say where to go."""
    request.session.clear()
    if agent.role == AgentRole.ADMIN:
        request.session["pending_admin_id"] = agent.id
        return "/admin/2fa/verify" if agent.totp_enabled else "/admin/2fa/setup"
    request.session["agent_id"] = agent.id
    request.session["role"] = agent.role.value
    return "/cabinet"


@router.get("/config", response_model=AuthConfig)
async def auth_config() -> AuthConfig:
    settings = get_settings()
    return AuthConfig(
        telegram_bot_username=settings.telegram_bot_username or "",
        telegram_auth_url=f"{settings.public_base_url}/auth/telegram/callback",
        yandex_enabled=bool(settings.yandex_client_id and settings.yandex_client_secret),
    )


@router.post("/login", response_model=NextResponse, dependencies=[CsrfProtected])
async def login(request: Request, session: Session, body: LoginRequest) -> NextResponse:
    settings = get_settings()
    remote_ip = request.client.host if request.client else "unknown"
    allowed = await login_rate_limiter.allow(
        remote_ip,
        limit=settings.login_rate_limit,
        window_seconds=settings.login_rate_window_seconds,
    )
    if not allowed:
        raise ApiError(429, "rate_limited", "Слишком много попыток входа. Попробуйте позже.")
    agent = await authenticate(session, body.email, body.password)
    if agent is None:
        raise ApiError(400, "invalid_credentials", "Неверная почта или пароль")
    if not agent.is_active:
        message = "Аккаунт заблокирован."
        if agent.blocked_reason:
            message += f" Причина: {agent.blocked_reason}"
        raise ApiError(403, "account_blocked", message)
    return NextResponse(next=_next_after_login(request, agent))


class RegisterRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)
    password_repeat: str = Field(max_length=256)


class CodeRequest(BaseModel):
    code: str = Field(max_length=32)


class PasswordResetRequest(BaseModel):
    email: str = Field(max_length=254)


class PasswordResetConfirmRequest(BaseModel):
    code: str = Field(max_length=32)
    password: str = Field(max_length=256)
    password_repeat: str = Field(max_length=256)


class InfoResponse(BaseModel):
    info: str


def _validate_new_password(password: str, password_repeat: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ApiError(
            400,
            "validation_error",
            "Пароль должен быть не короче 6 символов",
            {"password": "too_short"},
        )
    if password != password_repeat:
        raise ApiError(
            400, "validation_error", "Пароли не совпадают", {"password_repeat": "mismatch"}
        )


@router.post("/register", response_model=InfoResponse, dependencies=[CsrfProtected])
async def register(request: Request, session: Session, body: RegisterRequest) -> InfoResponse:
    email = normalize_email(body.email)
    if not valid_email(email):
        raise ApiError(400, "validation_error", "Укажите корректную почту", {"email": "invalid"})
    _validate_new_password(body.password, body.password_repeat)
    try:
        pending = await begin_registration(session, email, body.password)
        if pending is not None:
            await send_code(email, pending[1], "регистрация")
    except RuntimeError as exc:
        raise ApiError(400, "registration_failed", str(exc)) from exc
    if pending is None:
        request.session.pop("registration_token", None)
    else:
        request.session["registration_token"] = pending[0].token
    # Same answer whether or not the address is taken: no account enumeration.
    return InfoResponse(info="Если почта свободна, код отправлен на неё")


@router.post("/register/confirm", response_model=NextResponse, dependencies=[CsrfProtected])
async def register_confirm(request: Request, session: Session, body: CodeRequest) -> NextResponse:
    try:
        agent = await confirm_registration(
            session, request.session.get("registration_token", ""), body.code
        )
    except ValueError as exc:
        raise ApiError(400, "invalid_code", str(exc)) from exc
    if agent.role == AgentRole.AGENT:
        try:
            await send_new_partner_notice(agent)
        except Exception:
            logger.warning(
                "Failed to notify Telegram chats about new partner: agent_id=%s", agent.id
            )
    return NextResponse(next=_next_after_login(request, agent))


@router.post("/password-reset", response_model=InfoResponse, dependencies=[CsrfProtected])
async def password_reset(
    request: Request, session: Session, agent: OptionalAgent, body: PasswordResetRequest
) -> InfoResponse:
    request.session.pop("reset_token", None)
    pending = await begin_password_reset(session, body.email)
    if pending:
        request.session["reset_token"] = pending[0].token
        purpose = "смена пароля" if agent is not None else "восстановление пароля"
        await send_code(pending[0].email, pending[1], purpose)
    return InfoResponse(info="Если аккаунт существует, код отправлен на почту")


@router.post("/password-reset/confirm", response_model=NextResponse, dependencies=[CsrfProtected])
async def password_reset_confirm(
    request: Request, session: Session, body: PasswordResetConfirmRequest
) -> NextResponse:
    _validate_new_password(body.password, body.password_repeat)
    try:
        agent = await confirm_password_reset(
            session, request.session.get("reset_token", ""), body.code, body.password
        )
    except ValueError as exc:
        raise ApiError(400, "invalid_code", str(exc)) from exc
    return NextResponse(next=_next_after_login(request, agent))


@router.post("/logout", response_model=NextResponse, dependencies=[CsrfProtected])
async def logout(request: Request) -> NextResponse:
    request.session.clear()
    return NextResponse(next="/login")
