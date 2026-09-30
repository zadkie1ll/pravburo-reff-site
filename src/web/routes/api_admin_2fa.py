"""Admin two-factor step of the login: set it up (QR + first code) or enter the current code.

After the password an admin only has ``pending_admin_id`` in the session. A full session
(``agent_id``) exists only once a valid TOTP code has been given here.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Agent
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import confirm_totp_setup, get_or_create_totp_secret
from src.core.config import get_settings
from src.core.totp import verify_totp
from src.services.protection import totp_rate_limiter
from src.web.api_dependencies import ApiPendingAdmin, CsrfProtected
from src.web.api_errors import ApiError
from src.web.routes.api_auth import NextResponse

router = APIRouter(prefix="/api/v1/site/admin/2fa", tags=["site admin api"])
Session = Annotated[AsyncSession, Depends(get_session)]

QR_URL = "/admin/2fa/qr.png"


class TwoFactorState(BaseModel):
    step: Literal["setup", "verify"]
    qr_url: str | None


class CodeRequest(BaseModel):
    code: str = Field(max_length=32)


async def _allow_attempt(admin: Agent) -> None:
    """A few tries per admin, counted on the server (a copied cookie cannot reset it)."""
    settings = get_settings()
    allowed = await totp_rate_limiter.allow(
        str(admin.id),
        limit=settings.totp_rate_limit,
        window_seconds=settings.totp_rate_window_seconds,
    )
    if not allowed:
        raise ApiError(429, "rate_limited", "Слишком много попыток. Попробуйте позже.")


def _log_in(request: Request, admin: Agent) -> NextResponse:
    request.session.pop("pending_admin_id", None)
    request.session["agent_id"] = admin.id
    request.session["role"] = admin.role.value
    return NextResponse(next="/admin")


@router.get("/state", response_model=TwoFactorState)
async def state(admin: ApiPendingAdmin, session: Session) -> TwoFactorState:
    if admin.totp_enabled:
        return TwoFactorState(step="verify", qr_url=None)
    await get_or_create_totp_secret(session, admin)
    return TwoFactorState(step="setup", qr_url=QR_URL)


@router.post("/setup", response_model=NextResponse, dependencies=[CsrfProtected])
async def setup(
    request: Request, admin: ApiPendingAdmin, session: Session, body: CodeRequest
) -> NextResponse:
    if admin.totp_enabled:
        raise ApiError(409, "already_enabled", "Двухфакторная защита уже включена")
    await _allow_attempt(admin)
    if not await confirm_totp_setup(session, admin, body.code):
        raise ApiError(400, "invalid_code", "Неверный код")
    return _log_in(request, admin)


@router.post("/verify", response_model=NextResponse, dependencies=[CsrfProtected])
async def verify(request: Request, admin: ApiPendingAdmin, body: CodeRequest) -> NextResponse:
    if not admin.totp_enabled:
        raise ApiError(409, "setup_required", "Сначала настройте двухфакторную защиту")
    await _allow_attempt(admin)
    if not admin.totp_secret or not verify_totp(admin.totp_secret, body.code):
        raise ApiError(400, "invalid_code", "Неверный код")
    return _log_in(request, admin)
