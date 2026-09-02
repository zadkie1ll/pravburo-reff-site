from pravburo_ref_common.models import Agent, AgentRole, EmploymentFormat
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.profile import validate_inn


def needs_onboarding(agent: Agent) -> bool:
    return agent.role == AgentRole.AGENT and agent.employment_format is None


async def save_basic_info(
    session: AsyncSession, agent: Agent, display_name: str, employment_format: EmploymentFormat
) -> None:
    agent.display_name = display_name.strip()
    agent.employment_format = employment_format
    await session.commit()


async def save_payout_info(
    session: AsyncSession, agent: Agent, payout_details: str, inn: str
) -> None:
    inn_value = validate_inn(agent.employment_format, inn)
    agent.payout_details = payout_details.strip() or None
    agent.inn = inn_value
    await session.commit()
