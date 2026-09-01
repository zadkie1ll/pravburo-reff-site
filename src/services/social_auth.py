from urllib.parse import urlencode

import httpx
from pravburo_ref_common.models import Agent, AgentIdentity
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.security import normalize_email, valid_email


def yandex_authorize_url(state: str) -> str:
    settings = get_settings()
    return "https://oauth.yandex.ru/authorize?" + urlencode(
        {
            "response_type": "code",
            "client_id": settings.yandex_client_id,
            "redirect_uri": settings.yandex_redirect_uri,
            "state": state,
        }
    )


async def fetch_yandex_profile(code: str) -> dict:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        token_response = await client.post(
            "https://oauth.yandex.ru/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.yandex_client_id,
                "client_secret": settings.yandex_client_secret,
            },
        )
        token_response.raise_for_status()
        token = token_response.json()["access_token"]
        profile_response = await client.get(
            "https://login.yandex.ru/info",
            params={"format": "json"},
            headers={"Authorization": f"OAuth {token}"},
        )
        profile_response.raise_for_status()
        return profile_response.json()


async def login_social_agent(
    session: AsyncSession,
    provider: str,
    subject: str,
    display_name: str,
    email: str | None = None,
) -> Agent:
    identity = await session.scalar(
        select(AgentIdentity).where(
            AgentIdentity.provider == provider, AgentIdentity.subject == subject
        )
    )
    if identity:
        agent = await session.get(Agent, identity.agent_id)
        if agent is None:
            raise ValueError("Social identity is invalid")
        return agent
    normalized_email = normalize_email(email or "") if valid_email(email or "") else None
    agent = (
        await session.scalar(select(Agent).where(Agent.email == normalized_email))
        if normalized_email
        else None
    )
    if agent is None:
        agent = Agent(email=normalized_email, display_name=display_name.strip())
        session.add(agent)
        await session.flush()
    session.add(AgentIdentity(agent_id=agent.id, provider=provider, subject=subject))
    await session.commit()
    await session.refresh(agent)
    return agent
