from pravburo_ref_common.models import Agent, AgentRole, EmploymentFormat
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.agents import link_agent_to_referrer
from src.services.profile import validate_inn

EMPLOYMENT_FORMAT_NOTES = {
    EmploymentFormat.SELF_EMPLOYED: (
        "Платите налог на профессиональный доход (НПД) самостоятельно — обычно 4-6%. "
        "Чек на сумму выплаты формируется в приложении «Мой налог»."
    ),
    EmploymentFormat.INDIVIDUAL_ENTREPRENEUR: (
        "Платите налоги самостоятельно по своей системе налогообложения (обычно УСН)."
    ),
    EmploymentFormat.INDIVIDUAL: (
        "Мы удержим НДФЛ при выплате как налоговый агент — на руки придёт сумма за вычетом налога."
    ),
}


def needs_onboarding(agent: Agent) -> bool:
    return agent.role == AgentRole.AGENT and agent.employment_format is None


async def save_basic_info(
    session: AsyncSession,
    agent: Agent,
    display_name: str,
    phone: str,
    employment_format: EmploymentFormat,
) -> None:
    if agent.phone_normalized != phone:
        conflict = await session.scalar(
            select(Agent.id).where(Agent.phone_normalized == phone, Agent.id != agent.id)
        )
        if conflict is not None:
            raise ValueError("Этот номер телефона уже используется другим аккаунтом")
        agent.phone_normalized = phone
    agent.display_name = display_name.strip()
    agent.employment_format = employment_format
    await link_agent_to_referrer(session, agent)
    await session.commit()


async def save_payout_info(
    session: AsyncSession, agent: Agent, payout_details: str, inn: str
) -> None:
    inn_value = validate_inn(agent.employment_format, inn)
    agent.payout_details = payout_details.strip() or None
    agent.inn = inn_value
    await session.commit()
