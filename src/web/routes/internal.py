import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pravburo_ref_common.contracts import DealStageUpdate, RewardNotify
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Agent, ReferralApplication, RewardType
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.email import send_reward_notice
from src.core.internal_auth import require_internal_token
from src.core.push import send_push_notice
from src.core.telegram import send_partner_notice
from src.services.deal_stages import stage_label
from src.services.payouts import REWARD_TYPE_LABELS, format_amount

logger = logging.getLogger(__name__)
router = APIRouter(tags=["internal"])
Session = Annotated[AsyncSession, Depends(get_session)]

REWARD_NOTICE_TEXT = {
    RewardType.ADVANCE: "Клиент подписал договор — вам начислен аванс: {amount}.",
    RewardType.MAIN: "Клиент оплатил депозит — вам начислена основная выплата: {amount}.",
}


@router.post("/internal/applications/{application_id}/stage", dependencies=[Depends(require_internal_token)])
async def update_deal_stage(
    application_id: int, payload: DealStageUpdate, session: Session
) -> dict[str, str]:
    if payload.application_id != application_id:
        raise HTTPException(status_code=400, detail="application_id mismatch")
    application = await session.get(ReferralApplication, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    previous_stage_code = application.deal_stage_code
    application.bitrix_deal_id = payload.deal_id
    application.deal_stage_code = payload.stage_code
    await session.commit()

    if payload.stage_code != previous_stage_code:
        message = f"Ваш клиент перешёл на новый этап: {stage_label(payload.stage_code)}"
        try:
            await send_push_notice(session, application.agent_id, "Статус дела изменился", message)
        except Exception:
            logger.warning(
                "Failed to push agent about stage change: application_id=%s", application_id
            )
        try:
            await send_partner_notice(session, application.agent_id, message)
        except Exception:
            logger.warning(
                "Failed to Telegram agent about stage change: application_id=%s", application_id
            )

    return {"status": "updated"}


@router.post("/internal/rewards/notify", dependencies=[Depends(require_internal_token)])
async def notify_reward(payload: RewardNotify, session: Session) -> dict[str, str]:
    text_template = REWARD_NOTICE_TEXT.get(payload.reward_type)
    if text_template is None:
        return {"status": "ignored"}
    agent = await session.get(Agent, payload.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    amount_label = format_amount(payload.amount)
    message = text_template.format(amount=amount_label)
    type_label = REWARD_TYPE_LABELS.get(payload.reward_type, payload.reward_type.value)

    if agent.email:
        try:
            await send_reward_notice(agent.email, type_label, amount_label)
        except Exception:
            logger.warning("Failed to email agent about reward: agent_id=%s", agent.id)
    try:
        await send_push_notice(session, agent.id, type_label, message)
    except Exception:
        logger.warning("Failed to push agent about reward: agent_id=%s", agent.id)
    try:
        await send_partner_notice(session, agent.id, message)
    except Exception:
        logger.warning("Failed to Telegram agent about reward: agent_id=%s", agent.id)

    return {"status": "notified"}
