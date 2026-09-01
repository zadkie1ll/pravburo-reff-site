from pravburo_ref_common.models import Agent
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import normalize_email, normalize_phone, valid_email
from src.integrations.legacy_lk.gateway import LegacyClientRecord


async def ensure_legacy_client_agent(
    session: AsyncSession,
    client: LegacyClientRecord,
    contact_phone: str | None,
) -> tuple[Agent, bool]:
    phone = normalize_phone(contact_phone) if contact_phone else None
    email = normalize_email(client.email or "") if valid_email(client.email or "") else None
    conditions = [Agent.legacy_client_id == client.id]
    if phone:
        conditions.append(Agent.phone_normalized == phone)
    agent = await session.scalar(select(Agent).where(or_(*conditions)).with_for_update())
    created = agent is None
    if agent is None:
        agent = Agent(
            email=email,
            phone_normalized=phone,
            display_name=client.full_name,
            legacy_client_id=client.id,
        )
        session.add(agent)
    else:
        agent.legacy_client_id = client.id
        agent.display_name = agent.display_name or client.full_name
        agent.phone_normalized = agent.phone_normalized or phone
        agent.email = agent.email or email
    await session.commit()
    await session.refresh(agent)
    return agent, created
