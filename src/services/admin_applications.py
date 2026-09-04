from dataclasses import dataclass

from pravburo_ref_common.models import Agent, DeliveryStatus, ReferralApplication
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

PAGE_SIZE = 25

DELIVERY_STATUS_LABELS = {
    DeliveryStatus.PENDING: "Ожидает отправки",
    DeliveryStatus.SENT: "Отправлена",
    DeliveryStatus.FAILED: "Ошибка отправки",
}


@dataclass(frozen=True, slots=True)
class ApplicationRow:
    application: ReferralApplication
    agent_name: str
    agent_email: str | None


@dataclass(frozen=True, slots=True)
class ApplicationsPage:
    rows: list[ApplicationRow]
    page: int
    total_pages: int
    total_count: int


def _search_filter(stmt, query: str):
    pattern = f"%{query}%"
    return stmt.where(
        or_(
            ReferralApplication.full_name.ilike(pattern),
            ReferralApplication.phone_normalized.ilike(pattern),
        )
    )


async def list_applications(
    session: AsyncSession, q: str = "", status: str = "", page: int = 1
) -> ApplicationsPage:
    query = q.strip()
    page = max(page, 1)

    count_stmt = select(func.count(ReferralApplication.id))
    if query:
        count_stmt = _search_filter(count_stmt, query)
    if status:
        count_stmt = count_stmt.where(ReferralApplication.delivery_status == status)
    total_count = await session.scalar(count_stmt) or 0
    total_pages = max((total_count + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    page = min(page, total_pages)

    stmt = (
        select(ReferralApplication)
        .join(Agent, Agent.id == ReferralApplication.agent_id)
        .order_by(ReferralApplication.created_at.desc())
        .add_columns(Agent.display_name, Agent.email)
    )
    if query:
        stmt = _search_filter(stmt, query)
    if status:
        stmt = stmt.where(ReferralApplication.delivery_status == status)
    stmt = stmt.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    rows = (await session.execute(stmt)).all()

    return ApplicationsPage(
        rows=[
            ApplicationRow(application=app, agent_name=name or "Без имени", agent_email=email)
            for app, name, email in rows
        ],
        page=page,
        total_pages=total_pages,
        total_count=total_count,
    )
