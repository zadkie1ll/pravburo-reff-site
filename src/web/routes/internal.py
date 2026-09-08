from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pravburo_ref_common.contracts import DealStageUpdate
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import ReferralApplication
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.internal_auth import require_internal_token

router = APIRouter(tags=["internal"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.post("/internal/applications/{application_id}/stage", dependencies=[Depends(require_internal_token)])
async def update_deal_stage(
    application_id: int, payload: DealStageUpdate, session: Session
) -> dict[str, str]:
    if payload.application_id != application_id:
        raise HTTPException(status_code=400, detail="application_id mismatch")
    application = await session.get(ReferralApplication, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    application.bitrix_deal_id = payload.deal_id
    application.deal_stage_code = payload.stage_code
    await session.commit()
    return {"status": "updated"}
