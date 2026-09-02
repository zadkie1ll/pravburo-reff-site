from io import BytesIO
from typing import Annotated

import qrcode
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pravburo_ref_common.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import confirm_totp_setup, get_or_create_totp_secret
from src.core.config import get_settings
from src.core.security import csrf_token, valid_csrf
from src.core.totp import provisioning_uri, verify_totp
from src.services.protection import totp_rate_limiter
from src.web.dependencies import PendingAdmin
from src.web.routes.pages import templates

router = APIRouter(prefix="/admin/2fa", tags=["admin 2fa"])
Session = Annotated[AsyncSession, Depends(get_session)]


async def _check_rate_limit(agent_id: int) -> bool:
    settings = get_settings()
    return await totp_rate_limiter.allow(
        str(agent_id),
        limit=settings.totp_rate_limit,
        window_seconds=settings.totp_rate_window_seconds,
    )


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, admin: PendingAdmin, session: Session) -> HTMLResponse:
    if admin.totp_enabled:
        return RedirectResponse("/admin/2fa/verify", status_code=303)
    await get_or_create_totp_secret(session, admin)
    return templates.TemplateResponse(
        request=request,
        name="admin_2fa_setup.html",
        context={"csrf_token": csrf_token(request.session), "error": ""},
    )


@router.get("/qr.png")
async def setup_qr(admin: PendingAdmin, session: Session) -> Response:
    secret = await get_or_create_totp_secret(session, admin)
    uri = provisioning_uri(secret, admin.email or f"agent-{admin.id}")
    image = qrcode.make(uri)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return Response(buffer.getvalue(), media_type="image/png")


@router.post("/setup")
async def setup_confirm(
    request: Request,
    admin: PendingAdmin,
    session: Session,
    code: Annotated[str, Form()],
    csrf: Annotated[str, Form()] = "",
):
    if not valid_csrf(request.session, csrf):
        return templates.TemplateResponse(
            request=request,
            name="admin_2fa_setup.html",
            context={"csrf_token": csrf_token(request.session), "error": "Обновите страницу"},
            status_code=400,
        )
    if not await _check_rate_limit(admin.id):
        return templates.TemplateResponse(
            request=request,
            name="admin_2fa_setup.html",
            context={
                "csrf_token": csrf_token(request.session),
                "error": "Слишком много попыток. Попробуйте позже.",
            },
            status_code=429,
        )
    if not await confirm_totp_setup(session, admin, code):
        return templates.TemplateResponse(
            request=request,
            name="admin_2fa_setup.html",
            context={"csrf_token": csrf_token(request.session), "error": "Неверный код"},
            status_code=400,
        )
    request.session.pop("pending_admin_id", None)
    request.session["agent_id"] = admin.id
    return RedirectResponse("/cabinet", status_code=303)


@router.get("/verify", response_class=HTMLResponse)
async def verify_page(request: Request, admin: PendingAdmin) -> HTMLResponse:
    if not admin.totp_enabled:
        return RedirectResponse("/admin/2fa/setup", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="admin_2fa_verify.html",
        context={"csrf_token": csrf_token(request.session), "error": ""},
    )


@router.post("/verify")
async def verify_confirm(
    request: Request,
    admin: PendingAdmin,
    code: Annotated[str, Form()],
    csrf: Annotated[str, Form()] = "",
):
    if not valid_csrf(request.session, csrf):
        return templates.TemplateResponse(
            request=request,
            name="admin_2fa_verify.html",
            context={"csrf_token": csrf_token(request.session), "error": "Обновите страницу"},
            status_code=400,
        )
    if not await _check_rate_limit(admin.id):
        return templates.TemplateResponse(
            request=request,
            name="admin_2fa_verify.html",
            context={
                "csrf_token": csrf_token(request.session),
                "error": "Слишком много попыток. Попробуйте позже.",
            },
            status_code=429,
        )
    if not admin.totp_secret or not verify_totp(admin.totp_secret, code):
        return templates.TemplateResponse(
            request=request,
            name="admin_2fa_verify.html",
            context={"csrf_token": csrf_token(request.session), "error": "Неверный код"},
            status_code=400,
        )
    request.session.pop("pending_admin_id", None)
    request.session["agent_id"] = admin.id
    return RedirectResponse("/cabinet", status_code=303)
