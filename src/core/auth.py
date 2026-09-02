import hmac
import secrets
from datetime import UTC, datetime, timedelta

from pravburo_ref_common.models import (
    Agent,
    AgentCredential,
    AgentRole,
    PendingPasswordReset,
    PendingRegistration,
)
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.security import (
    generate_code,
    hash_code,
    hash_password,
    normalize_email,
    verify_password,
)
from src.core.totp import generate_secret, verify_totp


async def authenticate(session: AsyncSession, email: str, password: str) -> Agent | None:
    normalized = normalize_email(email)
    row = (
        await session.execute(
            select(Agent, AgentCredential.password_hash)
            .join(AgentCredential, AgentCredential.agent_id == Agent.id)
            .where(Agent.email == normalized)
        )
    ).one_or_none()
    if row is None or not verify_password(password, row[1]):
        return None
    return row[0]


async def get_or_create_totp_secret(session: AsyncSession, agent: Agent) -> str:
    if not agent.totp_secret:
        agent.totp_secret = generate_secret()
        await session.commit()
    return agent.totp_secret


async def confirm_totp_setup(session: AsyncSession, agent: Agent, code: str) -> bool:
    if not agent.totp_secret or not verify_totp(agent.totp_secret, code):
        return False
    agent.totp_enabled = True
    await session.commit()
    return True


async def begin_registration(
    session: AsyncSession, email: str, password: str
) -> tuple[PendingRegistration, str] | None:
    settings = get_settings()
    normalized = normalize_email(email)
    if await session.scalar(select(Agent.id).where(Agent.email == normalized)):
        return None
    await session.execute(
        delete(PendingRegistration).where(PendingRegistration.email == normalized)
    )
    token = secrets.token_urlsafe(32)
    code = generate_code()
    pending = PendingRegistration(
        token=token,
        email=normalized,
        password_hash=hash_password(password),
        code_hash=hash_code(token, code),
        expires_at=datetime.now(UTC) + timedelta(seconds=settings.registration_code_ttl_seconds),
    )
    session.add(pending)
    await session.commit()
    return pending, code


async def confirm_registration(session: AsyncSession, token: str, code: str) -> Agent:
    pending = await session.get(PendingRegistration, token, with_for_update=True)
    if pending is None or pending.expires_at < datetime.now(UTC) or pending.attempts >= 5:
        raise ValueError("Неверный или просроченный код")
    if not hmac.compare_digest(pending.code_hash, hash_code(token, code.strip())):
        pending.attempts += 1
        await session.commit()
        raise ValueError("Неверный или просроченный код")
    settings = get_settings()
    agent = Agent(
        email=pending.email,
        role=AgentRole.ADMIN if pending.email in settings.admin_email_set else AgentRole.AGENT,
    )
    session.add(agent)
    await session.flush()
    session.add(AgentCredential(agent_id=agent.id, password_hash=pending.password_hash))
    await session.delete(pending)
    await session.commit()
    await session.refresh(agent)
    return agent


async def begin_password_reset(
    session: AsyncSession, email: str
) -> tuple[PendingPasswordReset, str] | None:
    normalized = normalize_email(email)
    agent = await session.scalar(select(Agent).where(Agent.email == normalized))
    if agent is None:
        return None
    settings = get_settings()
    await session.execute(
        delete(PendingPasswordReset).where(PendingPasswordReset.agent_id == agent.id)
    )
    token = secrets.token_urlsafe(32)
    code = generate_code()
    pending = PendingPasswordReset(
        token=token,
        agent_id=agent.id,
        email=normalized,
        code_hash=hash_code(token, code),
        expires_at=datetime.now(UTC) + timedelta(seconds=settings.password_reset_code_ttl_seconds),
    )
    session.add(pending)
    await session.commit()
    return pending, code


async def confirm_password_reset(
    session: AsyncSession, token: str, code: str, password: str
) -> Agent:
    pending = await session.get(PendingPasswordReset, token, with_for_update=True)
    if pending is None or pending.expires_at < datetime.now(UTC) or pending.attempts >= 5:
        raise ValueError("Неверный или просроченный код")
    if not hmac.compare_digest(pending.code_hash, hash_code(token, code.strip())):
        pending.attempts += 1
        await session.commit()
        raise ValueError("Неверный или просроченный код")
    credential = await session.get(AgentCredential, pending.agent_id)
    if credential is None:
        raise ValueError("Учетная запись повреждена")
    credential.password_hash = hash_password(password)
    agent = await session.get(Agent, pending.agent_id)
    await session.delete(pending)
    await session.commit()
    if agent is None:
        raise ValueError("Учетная запись не найдена")
    return agent
