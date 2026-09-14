import re
from dataclasses import dataclass

from pravburo_ref_common.models import Agent, EmploymentFormat
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import normalize_phone
from src.services.agents import link_agent_to_referrer

INN_RE = re.compile(r"^\d{10}$|^\d{12}$")

EMPLOYMENT_FORMAT_LABELS = {
    EmploymentFormat.SELF_EMPLOYED: "Самозанятый",
    EmploymentFormat.INDIVIDUAL_ENTREPRENEUR: "ИП",
    EmploymentFormat.INDIVIDUAL: "Физлицо",
}


def validate_inn(employment_format: EmploymentFormat, inn: str) -> str | None:
    inn = inn.strip()
    if employment_format == EmploymentFormat.INDIVIDUAL:
        return None
    if not INN_RE.fullmatch(inn):
        raise ValueError("Укажите корректный ИНН (10 или 12 цифр) для выбранного формата")
    return inn


@dataclass(slots=True)
class ProfileInput:
    display_name: str
    employment_format: EmploymentFormat
    payout_details: str
    inn: str
    phone: str = ""


async def update_profile(session: AsyncSession, agent: Agent, data: ProfileInput) -> list[str]:
    inn = validate_inn(data.employment_format, data.inn)

    phone = data.phone.strip()
    normalized_phone = normalize_phone(phone) if phone else None
    if normalized_phone and normalized_phone != agent.phone_normalized:
        conflict = await session.scalar(
            select(Agent.id).where(
                Agent.phone_normalized == normalized_phone, Agent.id != agent.id
            )
        )
        if conflict is not None:
            raise ValueError("Этот номер телефона уже используется другим аккаунтом")

    changed_fields = []
    payout_details = data.payout_details.strip() or None
    if payout_details != agent.payout_details:
        changed_fields.append("реквизиты для выплат")
    if data.employment_format != agent.employment_format:
        changed_fields.append("формат сотрудничества")

    display_name = data.display_name.strip()
    if display_name:
        agent.display_name = display_name
    agent.payout_details = payout_details
    agent.employment_format = data.employment_format
    agent.inn = inn
    if normalized_phone and normalized_phone != agent.phone_normalized:
        agent.phone_normalized = normalized_phone
        await link_agent_to_referrer(session, agent)

    await session.commit()
    return changed_fields
