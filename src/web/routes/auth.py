import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pravburo_ref_common.database import get_session
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
from src.core.security import (
    csrf_token,
    normalize_email,
    valid_csrf,
    valid_email,
    verify_telegram_login,
)
from src.services.protection import login_rate_limiter
from src.services.social_auth import fetch_yandex_profile, login_social_agent, yandex_authorize_url
from src.web.routes.pages import templates

router = APIRouter(tags=["authentication"])
Session = Annotated[AsyncSession, Depends(get_session)]


def context(request: Request, *, error: str = "", info: str = "") -> dict:
    settings = get_settings()
    return {
        "csrf_token": csrf_token(request.session),
        "error": error,
        "info": info,
        "telegram_bot_username": settings.telegram_bot_username,
        "telegram_auth_url": f"{settings.public_base_url}/auth/telegram/callback",
        "yandex_enabled": bool(settings.yandex_client_id and settings.yandex_client_secret),
    }


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="login.html", context=context(request))


@router.post("/login")
async def login(
    request: Request,
    session: Session,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    csrf: Annotated[str, Form()] = "",
):
    if not valid_csrf(request.session, csrf):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context=context(request, error="Обновите страницу"),
            status_code=400,
        )
    settings = get_settings()
    remote_ip = request.client.host if request.client else "unknown"
    allowed = await login_rate_limiter.allow(
        remote_ip,
        limit=settings.login_rate_limit,
        window_seconds=settings.login_rate_window_seconds,
    )
    if not allowed:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context=context(request, error="Слишком много попыток входа. Попробуйте позже."),
            status_code=429,
        )
    agent = await authenticate(session, email, password)
    if agent is None:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context=context(request, error="Неверная почта или пароль"),
            status_code=400,
        )
    request.session.clear()
    request.session["agent_id"] = agent.id
    return RedirectResponse("/cabinet", status_code=303)


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request, name="register.html", context=context(request)
    )


@router.post("/register")
async def register(
    request: Request,
    session: Session,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    password_repeat: Annotated[str, Form()],
    csrf: Annotated[str, Form()] = "",
):
    email = normalize_email(email)
    error = ""
    if not valid_csrf(request.session, csrf):
        error = "Обновите страницу"
    elif not valid_email(email):
        error = "Укажите корректную почту"
    elif len(password) < 6:
        error = "Пароль должен быть не короче 6 символов"
    elif password != password_repeat:
        error = "Пароли не совпадают"
    if error:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context=context(request, error=error),
            status_code=400,
        )
    try:
        pending = await begin_registration(session, email, password)
        if pending is not None:
            await send_code(email, pending[1], "регистрация")
    except RuntimeError as exc:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context=context(request, error=str(exc)),
            status_code=400,
        )
    if pending is None:
        request.session.pop("registration_token", None)
    else:
        request.session["registration_token"] = pending[0].token
    return templates.TemplateResponse(
        request=request,
        name="confirm_registration.html",
        context=context(request, info="Если почта свободна, код отправлен на неё"),
    )


@router.post("/register/confirm")
async def register_confirm(
    request: Request,
    session: Session,
    code: Annotated[str, Form()],
    csrf: Annotated[str, Form()] = "",
):
    if not valid_csrf(request.session, csrf):
        error = "Обновите страницу"
    else:
        try:
            agent = await confirm_registration(
                session, request.session.get("registration_token", ""), code
            )
            request.session.clear()
            request.session["agent_id"] = agent.id
            return RedirectResponse("/cabinet", status_code=303)
        except ValueError as exc:
            error = str(exc)
    return templates.TemplateResponse(
        request=request,
        name="confirm_registration.html",
        context=context(request, error=error),
        status_code=400,
    )


@router.get("/password/reset", response_class=HTMLResponse)
async def reset_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request, name="password_reset.html", context=context(request)
    )


@router.post("/password/reset")
async def reset_begin(
    request: Request,
    session: Session,
    email: Annotated[str, Form()],
    csrf: Annotated[str, Form()] = "",
):
    if not valid_csrf(request.session, csrf):
        return templates.TemplateResponse(
            request=request,
            name="password_reset.html",
            context=context(request, error="Обновите страницу"),
            status_code=400,
        )
    request.session.pop("reset_token", None)
    pending = await begin_password_reset(session, email)
    if pending:
        request.session["reset_token"] = pending[0].token
        await send_code(pending[0].email, pending[1], "восстановление пароля")
    return templates.TemplateResponse(
        request=request,
        name="password_reset_confirm.html",
        context=context(request, info="Если аккаунт существует, код отправлен на почту"),
    )


@router.post("/password/reset/confirm")
async def reset_confirm(
    request: Request,
    session: Session,
    code: Annotated[str, Form()],
    password: Annotated[str, Form()],
    password_repeat: Annotated[str, Form()],
    csrf: Annotated[str, Form()] = "",
):
    if not valid_csrf(request.session, csrf) or password != password_repeat or len(password) < 6:
        error = "Проверьте код и пароли"
    else:
        try:
            agent = await confirm_password_reset(
                session, request.session.get("reset_token", ""), code, password
            )
            request.session.clear()
            request.session["agent_id"] = agent.id
            return RedirectResponse("/cabinet", status_code=303)
        except ValueError as exc:
            error = str(exc)
    return templates.TemplateResponse(
        request=request,
        name="password_reset_confirm.html",
        context=context(request, error=error),
        status_code=400,
    )


@router.post("/logout")
async def logout(request: Request, csrf: Annotated[str, Form()] = ""):
    if valid_csrf(request.session, csrf):
        request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/auth/telegram/callback")
async def telegram_callback(request: Request, session: Session):
    settings = get_settings()
    payload = dict(request.query_params)
    if not settings.telegram_bot_token or not verify_telegram_login(
        payload, settings.telegram_bot_token, settings.telegram_login_max_age_seconds
    ):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context=context(request, error="Не удалось проверить Telegram"),
            status_code=400,
        )
    agent = await login_social_agent(
        session,
        "telegram",
        payload["id"],
        " ".join(filter(None, (payload.get("first_name"), payload.get("last_name")))),
    )
    request.session.clear()
    request.session["agent_id"] = agent.id
    return RedirectResponse("/cabinet", status_code=303)


@router.get("/auth/yandex/start")
async def yandex_start(request: Request):
    if not get_settings().yandex_client_id:
        return RedirectResponse("/login", status_code=303)
    state = secrets.token_urlsafe(32)
    request.session["yandex_state"] = state
    return RedirectResponse(yandex_authorize_url(state), status_code=303)


@router.get("/auth/yandex/callback")
async def yandex_callback(request: Request, session: Session, code: str = "", state: str = ""):
    expected = request.session.pop("yandex_state", "")
    if not expected or not secrets.compare_digest(expected, state) or not code:
        return RedirectResponse("/login", status_code=303)
    try:
        profile = await fetch_yandex_profile(code)
        agent = await login_social_agent(
            session,
            "yandex",
            str(profile["id"]),
            profile.get("display_name") or profile.get("real_name") or "",
            profile.get("default_email"),
        )
    except Exception:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context=context(request, error="Не удалось войти через Яндекс"),
            status_code=400,
        )
    request.session.clear()
    request.session["agent_id"] = agent.id
    return RedirectResponse("/cabinet", status_code=303)
