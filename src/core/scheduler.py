import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.services.payout_reminders import check_payout_reminders

logger = logging.getLogger(__name__)

MOSCOW_TZ = "Europe/Moscow"


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)
    scheduler.add_job(
        check_payout_reminders,
        trigger=CronTrigger(hour="9-20", minute=0, timezone=MOSCOW_TZ),
        id="payout_reminders",
        misfire_grace_time=3600,
    )
    return scheduler
