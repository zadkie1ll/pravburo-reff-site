"""Partner payouts list for the React frontend (the PDF export stays a plain download)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import RewardType
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.payouts import (
    PAGE_STATUS_LABELS,
    REWARD_TYPE_LABELS,
    PayoutFilters,
    PayoutRow,
    get_payout_rows,
)
from src.web.api_dependencies import ApiPartner
from src.web.api_schemas import OptionOut

router = APIRouter(prefix="/api/v1/site/payouts", tags=["site payouts api"])
Session = Annotated[AsyncSession, Depends(get_session)]


class PayoutRowOut(BaseModel):
    payout_date_label: str
    client_name: str
    type_label: str
    amount_label: str
    status_label: str
    status_slug: str
    rejection_reason: str


class PayoutsResponse(BaseModel):
    rows: list[PayoutRowOut]
    reward_types: list[OptionOut]
    statuses: list[OptionOut]


def _row(row: PayoutRow) -> PayoutRowOut:
    return PayoutRowOut(
        payout_date_label=row.payout_date_label,
        client_name=row.client_name,
        type_label=row.type_label,
        amount_label=row.amount_label,
        status_label=row.status_label,
        status_slug=row.status_slug,
        rejection_reason=row.rejection_reason,
    )


@router.get("", response_model=PayoutsResponse)
async def payouts(
    agent: ApiPartner,
    session: Session,
    month: Annotated[str, Query()] = "",
    reward_type: Annotated[RewardType | None, Query()] = None,
    status: Annotated[str, Query()] = "",
) -> PayoutsResponse:
    filters = PayoutFilters(
        month=month, reward_type=reward_type.value if reward_type else "", status=status
    )
    rows = await get_payout_rows(session, agent.id, filters)
    return PayoutsResponse(
        rows=[_row(row) for row in rows],
        reward_types=[
            OptionOut(value=value.value, label=label) for value, label in REWARD_TYPE_LABELS.items()
        ],
        statuses=[OptionOut(value=slug, label=label) for slug, label in PAGE_STATUS_LABELS.items()],
    )
