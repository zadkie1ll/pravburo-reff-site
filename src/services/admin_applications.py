from dataclasses import dataclass

from pravburo_ref_common.models import (
    Agent,
    AgentRole,
    DeliveryStatus,
    ProcessingStatus,
    ReferralApplication,
)
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

PAGE_SIZE = 25

DELIVERY_STATUS_LABELS = {
    DeliveryStatus.PENDING: "Ожидает отправки",
    DeliveryStatus.SENT: "Отправлена",
    DeliveryStatus.FAILED: "Ошибка отправки",
}

PROCESSING_STATUS_LABELS = {
    ProcessingStatus.NEW: "Новая",
    ProcessingStatus.IN_PROGRESS: "В работе",
    ProcessingStatus.CLOSED: "Закрыта",
}


@dataclass(frozen=True, slots=True)
class ManagerOption:
    id: int
    label: str


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


async def list_managers(session: AsyncSession) -> list[ManagerOption]:
    admins = (
        await session.scalars(
            select(Agent).where(Agent.role == AgentRole.ADMIN).order_by(Agent.display_name)
        )
    ).all()
    return [
        ManagerOption(id=admin.id, label=admin.display_name or admin.email or f"#{admin.id}")
        for admin in admins
    ]


async def set_processing_status(
    session: AsyncSession, application_id: int, status: ProcessingStatus
) -> None:
    application = await session.get(ReferralApplication, application_id)
    if application is not None:
        application.processing_status = status
        await session.commit()


async def assign_manager(
    session: AsyncSession, application_id: int, manager_id: int | None
) -> None:
    application = await session.get(ReferralApplication, application_id)
    if application is not None:
        application.assigned_manager_id = manager_id
        await session.commit()
