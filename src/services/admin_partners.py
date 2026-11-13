"""Create and edit partner profiles without changing roles, credentials or reward history."""

import logging
import secrets
import string
from dataclasses import dataclass

from pravburo_ref_common.models import (
    Agent,
    AgentCredential,
    AgentRole,
    EmploymentFormat,
    PendingRegistration,
)
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import hash_password, normalize_email, normalize_phone, valid_email
from src.services.agents import link_agent_to_referrer
from src.services.profile import validate_inn

logger = logging.getLogger(__name__)


def generate_partner_password() -> str:
    characters = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
        *(secrets.choice(string.ascii_letters + string.digits) for _ in range(5)),
    ]
    secrets.SystemRandom().shuffle(characters)
    return "".join(characters)


@dataclass(frozen=True, slots=True)
class PartnerInput:
    display_name: str
    phone: str
    employment_format: EmploymentFormat
    payout_details: str
    inn: str
    admin_note: str


def _validated(data: PartnerInput) -> dict:
    name = data.display_name.strip()
    details = data.payout_details.strip()
    if not name:
        raise ValueError("Укажите ФИО партнёра")
    if not details:
        raise ValueError("Укажите реквизиты для выплат")
    return {
        "display_name": name,
        "phone_normalized": normalize_phone(data.phone) if data.phone.strip() else None,
        "employment_format": data.employment_format,
        "payout_details": details,
        "inn": validate_inn(data.employment_format, data.inn),
        "admin_note": data.admin_note.strip() or None,
    }


async def _check_phone(session: AsyncSession, phone: str | None, exclude_id: int | None) -> None:
    if phone:
        stmt = select(Agent.id).where(Agent.phone_normalized == phone)
        if exclude_id is not None:
            stmt = stmt.where(Agent.id != exclude_id)
        if await session.scalar(stmt) is not None:
            raise ValueError("Этот номер телефона уже используется другим аккаунтом")


async def _commit(session: AsyncSession) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError("Почта или телефон уже используются другим аккаунтом") from exc


async def create_partner(
    session: AsyncSession, admin_id: int, email: str | None, data: PartnerInput
) -> Agent:
    email = normalize_email(email or "") or None
    if email is not None and not valid_email(email):
        raise ValueError("Укажите корректную почту")
    values = _validated(data)
    if (
        email is not None
        and await session.scalar(select(Agent.id).where(func.lower(Agent.email) == email))
        is not None
    ):
        raise ValueError("Эта почта уже используется другим аккаунтом")
    await _check_phone(session, values["phone_normalized"], None)
    password = generate_partner_password()
    password_note = f"Пароль: {password}"
    values["admin_note"] = (
        f"{values['admin_note']}\n{password_note}" if values["admin_note"] else password_note
    )
    agent = Agent(email=email, role=AgentRole.AGENT, **values)
    session.add(agent)
    try:
        await session.flush()
        # The requested copy is kept only in the admin note; login uses the hash.
        session.add(AgentCredential(agent_id=agent.id, password_hash=hash_password(password)))
        await link_agent_to_referrer(session, agent)
        if email is not None:
            await session.execute(
                delete(PendingRegistration).where(PendingRegistration.email == email)
            )
        await _commit(session)
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError("Почта или телефон уже используются другим аккаунтом") from exc
    await session.refresh(agent)
    logger.info("Admin created partner: admin_id=%s agent_id=%s", admin_id, agent.id)
    return agent


async def edit_partner(
    session: AsyncSession, admin_id: int, agent: Agent, data: PartnerInput
) -> Agent:
    if agent.role != AgentRole.AGENT:
        raise ValueError("Аккаунт администратора нельзя редактировать как партнёра")
    values = _validated(data)
    await _check_phone(session, values["phone_normalized"], agent.id)
    for field, value in values.items():
        setattr(agent, field, value)
    await _commit(session)
    await session.refresh(agent)
    logger.info("Admin edited partner: admin_id=%s agent_id=%s", admin_id, agent.id)
    return agent
