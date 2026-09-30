"""Server-side legs of social sign-in.

Telegram and Yandex send the browser back to these URLs, so they must stay real backend routes.
Everything else about authentication (login, registration, password reset) is the JSON API in
``api_auth.py``. Failures redirect to the React login page, which shows ``?error=``.
"""

import logging
import secrets
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Agent, AgentRole
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.security import verify_telegram_login
from src.services.social_auth import (
    fetch_yandex_profile,
    link_social_identity,
    login_social_agent,
    yandex_authorize_url,
)
from src.web.dependencies import OptionalAgent

logger = logging.getLogger(__name__)
router = APIRouter(tags=["authentication"])
Session = Annotated[AsyncSession, Depends(get_session)]


def _log_in(request: Request, agent) -> RedirectResponse:
    request.session["agent_id"] = agent.id
    request.session["role"] = agent.role.value
    destination = "/admin" if agent.role == AgentRole.ADMIN else "/cabinet"
    return RedirectResponse(destination, status_code=303)


def _login_error(message: str) -> RedirectResponse:
    return RedirectResponse(f"/login?{urlencode({'error': message})}", status_code=303)


@router.get("/auth/telegram/callback")
async def telegram_callback(request: Request, session: Session):
    settings = get_settings()
    payload = dict(request.query_params)
    if not settings.telegram_bot_token or not verify_telegram_login(
        payload, settings.telegram_bot_token, settings.telegram_login_max_age_seconds
    ):
        return _login_error("Не удалось проверить Telegram")
    agent = await login_social_agent(
        session,
        "telegram",
        payload["id"],
        " ".join(filter(None, (payload.get("first_name"), payload.get("last_name")))),
    )
    request.session.clear()
    return _log_in(request, agent)


@router.get("/auth/yandex/start")
async def yandex_start(request: Request, agent: OptionalAgent):
    if not get_settings().yandex_client_id:
        return RedirectResponse("/login", status_code=303)
    state = secrets.token_urlsafe(32)
    request.session["yandex_state"] = state
    if agent is not None:
        request.session["yandex_link_agent_id"] = agent.id
    return RedirectResponse(yandex_authorize_url(state), status_code=303)


@router.get("/auth/yandex/callback")
async def yandex_callback(request: Request, session: Session, code: str = "", state: str = ""):
    expected = request.session.pop("yandex_state", "")
    link_agent_id = request.session.pop("yandex_link_agent_id", None)
    if not expected or not secrets.compare_digest(expected, state) or not code:
        return RedirectResponse("/login", status_code=303)
    try:
        profile = await fetch_yandex_profile(code)
    except Exception:
        return _login_error("Не удалось войти через Яндекс")
    if link_agent_id is not None:
        agent = await session.get(Agent, link_agent_id)
        if agent is None or request.session.get("agent_id") != link_agent_id:
            return RedirectResponse("/profile", status_code=303)
        try:
            await link_social_identity(session, agent, "yandex", str(profile["id"]))
        except ValueError as exc:
            return RedirectResponse(f"/profile?{urlencode({'error': str(exc)})}", status_code=303)
        return RedirectResponse(
            f"/profile?{urlencode({'info': 'Яндекс привязан'})}", status_code=303
        )
    try:
        agent = await login_social_agent(
            session,
            "yandex",
            str(profile["id"]),
            profile.get("display_name") or profile.get("real_name") or "",
            profile.get("default_email"),
        )
    except Exception:
        return _login_error("Не удалось войти через Яндекс")
    request.session.clear()
    return _log_in(request, agent)
