from pravburo_ref_common.models import Agent, AgentCredential, AgentIdentity, ReferralApplication
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import normalize_email, normalize_phone, valid_email
from src.integrations.legacy_lk.gateway import LegacyClientRecord


async def link_agent_to_referrer(session: AsyncSession, agent: Agent) -> None:
    """Connect a newly self-registered partner to whoever first brought them
    in as a client, so override payouts can flow up that chain later.

    Only fires once (invited_by_agent_id never gets reassigned after it's
    set) and only for a phone that matches an existing client application -
    an agent with no such history just has no upline, which is fine.
    """
    if agent.invited_by_agent_id is not None or agent.phone_normalized is None:
        return
    application = await session.scalar(
        select(ReferralApplication).where(
            ReferralApplication.phone_normalized == agent.phone_normalized
        )
    )
    if application is not None and application.agent_id != agent.id:
        agent.invited_by_agent_id = application.agent_id


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
        self_registered = await session.scalar(
            select(AgentCredential.agent_id).where(AgentCredential.agent_id == agent.id)
        ) is not None or await session.scalar(
            select(AgentIdentity.agent_id).where(AgentIdentity.agent_id == agent.id)
        ) is not None
        if not self_registered:
            agent.legacy_client_id = client.id
        agent.display_name = agent.display_name or client.full_name
        agent.phone_normalized = agent.phone_normalized or phone
        agent.email = agent.email or email
    await session.commit()
    await session.refresh(agent)
    return agent, created
