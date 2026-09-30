"""Cabinet (partner dashboard) data for the React frontend."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Reward
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.services.partner_levels import (
    LEVEL_LABELS,
    LEVEL_RANGE_LABELS,
    LevelProgress,
    contracts_word,
    get_current_month_progress,
)
from src.services.payouts import FinanceSummary, build_finance_summary
from src.services.referrals import (
    ApplicationRow,
    LinkStats,
    NetworkClientRow,
    VisitDay,
    get_application_rows,
    get_link_stats,
    get_network_client_rows,
    get_visits_by_day,
)
from src.web.api_dependencies import ApiPartner

router = APIRouter(prefix="/api/v1/site/cabinet", tags=["site cabinet api"])
Session = Annotated[AsyncSession, Depends(get_session)]


class PendingGroupOut(BaseModel):
    label: str
    amount_label: str


class FinanceOut(BaseModel):
    total_paid_label: str
    this_month_label: str
    pending_total_label: str
    pending_groups: list[PendingGroupOut]


class LinkStatsOut(BaseModel):
    visits: int
    applications: int
    contracts: int
    conversion_rate_label: str


class LevelNodeOut(BaseModel):
    level: str
    label: str
    range_label: str
    is_reached: bool
    is_current: bool


class LevelOut(BaseModel):
    level: str
    label: str
    contracts_count: int
    contracts_word: str
    is_manual: bool
    nodes: list[LevelNodeOut]
    # Fill of the segment between node i and i+1, in percent, quantized to 10.
    segment_fills: list[int]
    next_level_label: str | None
    contracts_to_next: int | None
    contracts_to_next_word: str | None


class ClientRowOut(BaseModel):
    client_name: str
    masked_phone: str
    created_at_label: str
    stage: str
    reward_summary: str
    reward_totals: str


class CabinetResponse(BaseModel):
    name: str
    referral_url: str
    finance: FinanceOut
    link_stats: LinkStatsOut
    level: LevelOut
    clients: list[ClientRowOut]


def _finance(summary: FinanceSummary) -> FinanceOut:
    return FinanceOut(
        total_paid_label=summary.total_paid_label,
        this_month_label=summary.this_month_label,
        pending_total_label=summary.pending_total_label,
        pending_groups=[
            PendingGroupOut(label=group.label, amount_label=group.amount_label)
            for group in summary.pending_groups
        ],
    )


def _link_stats(stats: LinkStats) -> LinkStatsOut:
    return LinkStatsOut(
        visits=stats.visits,
        applications=stats.applications,
        contracts=stats.contracts,
        conversion_rate_label=stats.conversion_rate_label,
    )


def _level(progress: LevelProgress) -> LevelOut:
    to_next = progress.contracts_to_next
    return LevelOut(
        level=progress.level.value,
        label=LEVEL_LABELS[progress.level],
        contracts_count=progress.contracts_count,
        contracts_word=contracts_word(progress.contracts_count),
        is_manual=progress.is_manual,
        nodes=[
            LevelNodeOut(
                level=node.level.value,
                label=LEVEL_LABELS[node.level],
                range_label=LEVEL_RANGE_LABELS[node.level],
                is_reached=node.is_reached,
                is_current=node.is_current,
            )
            for node in progress.nodes
        ],
        segment_fills=[segment.fill_percent for segment in progress.segments],
        next_level_label=LEVEL_LABELS[progress.next_level] if progress.next_level else None,
        contracts_to_next=to_next,
        contracts_to_next_word=contracts_word(to_next) if to_next is not None else None,
    )


def _client_row(row: NetworkClientRow) -> ClientRowOut:
    return ClientRowOut(
        client_name=row.client_name,
        masked_phone=row.masked_phone,
        created_at_label=row.created_at.strftime("%d.%m.%Y"),
        stage=row.stage,
        reward_summary=row.reward_summary,
        reward_totals=row.reward_totals,
    )


@router.get("", response_model=CabinetResponse)
async def cabinet(agent: ApiPartner, session: Session) -> CabinetResponse:
    rewards = list((await session.scalars(select(Reward).where(Reward.agent_id == agent.id))).all())
    return CabinetResponse(
        name=agent.display_name or agent.email or "",
        referral_url=f"{get_settings().public_base_url}/r/{agent.referral_code}",
        finance=_finance(build_finance_summary(rewards)),
        link_stats=_link_stats(await get_link_stats(session, agent.id)),
        level=_level(await get_current_month_progress(session, agent.id)),
        clients=[_client_row(row) for row in await get_network_client_rows(session, agent.id)],
    )


class VisitDayOut(BaseModel):
    day_label: str
    count: int


class VisitsResponse(BaseModel):
    days: list[VisitDayOut]
    total: int


class ApplicationRowOut(BaseModel):
    client_name: str
    masked_phone: str
    created_at_label: str
    status: str


class ApplicationsResponse(BaseModel):
    rows: list[ApplicationRowOut]


def _visit_day(day: VisitDay) -> VisitDayOut:
    return VisitDayOut(day_label=day.day_label, count=day.count)


def _application_row(row: ApplicationRow) -> ApplicationRowOut:
    return ApplicationRowOut(
        client_name=row.client_name,
        masked_phone=row.masked_phone,
        created_at_label=row.created_at.strftime("%d.%m.%Y"),
        status=row.status,
    )


@router.get("/visits", response_model=VisitsResponse)
async def visits(agent: ApiPartner, session: Session) -> VisitsResponse:
    days = await get_visits_by_day(session, agent.id)
    return VisitsResponse(days=[_visit_day(day) for day in days], total=sum(d.count for d in days))


@router.get("/applications", response_model=ApplicationsResponse)
async def applications(agent: ApiPartner, session: Session) -> ApplicationsResponse:
    rows = await get_application_rows(session, agent.id)
    return ApplicationsResponse(rows=[_application_row(row) for row in rows])
