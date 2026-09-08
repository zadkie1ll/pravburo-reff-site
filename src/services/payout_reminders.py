import logging
from datetime import UTC, datetime, timedelta

from pravburo_ref_common.database import session_factory
from pravburo_ref_common.models import Agent, ReferralApplication, Reward, RewardStatus
from sqlalchemy import select

from src.core.telegram import send_payout_due_notice, send_payout_overdue_notice
from src.services.admin_payouts import get_overdue_days

OVERDUE_ALERT_AFTER_DAYS = 2

logger = logging.getLogger(__name__)


async def check_payout_reminders() -> None:
    async with session_factory() as session:
        overdue_days = await get_overdue_days(session)
        today = datetime.now(UTC).date()

        stmt = (
            select(Reward, ReferralApplication.full_name, Agent)
            .join(ReferralApplication, ReferralApplication.id == Reward.application_id)
            .join(Agent, Agent.id == Reward.agent_id)
            .where(
                Reward.status == RewardStatus.APPROVED,
                Reward.paid_at.is_(None),
                Reward.decided_at.is_not(None),
            )
        )
        rows = (await session.execute(stmt)).all()

        for reward, client_name, agent in rows:
            target_date = reward.decided_at.date() + timedelta(days=overdue_days)

            if reward.due_notice_sent_at is None and today >= target_date:
                try:
                    await send_payout_due_notice(reward, agent, client_name, target_date)
                except Exception:
                    logger.warning(
                        "Failed to send payout-due Telegram notice: reward_id=%s", reward.id
                    )
                else:
                    reward.due_notice_sent_at = datetime.now(UTC)
                    await session.commit()

            days_overdue = (today - target_date).days
            if (
                reward.overdue_notice_sent_at is None
                and days_overdue > OVERDUE_ALERT_AFTER_DAYS
            ):
                try:
                    await send_payout_overdue_notice(
                        reward, agent, client_name, target_date, days_overdue
                    )
                except Exception:
                    logger.warning(
                        "Failed to send payout-overdue Telegram notice: reward_id=%s", reward.id
                    )
                else:
                    reward.overdue_notice_sent_at = datetime.now(UTC)
                    await session.commit()
