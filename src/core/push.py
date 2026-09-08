import json
import logging

from pravburo_ref_common.models import PushSubscription
from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings

logger = logging.getLogger(__name__)


async def send_push_notice(session: AsyncSession, agent_id: int, title: str, body: str) -> None:
    settings = get_settings()
    if not settings.vapid_public_key or not settings.vapid_private_key:
        return

    subscriptions = (
        await session.scalars(
            select(PushSubscription).where(PushSubscription.agent_id == agent_id)
        )
    ).all()
    if not subscriptions:
        return

    payload = json.dumps({"title": title, "body": body})
    dead_subscription_ids: list[int] = []
    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": f"mailto:{settings.vapid_contact_email}"},
            )
        except WebPushException as exc:
            status_code = getattr(exc.response, "status_code", None)
            if status_code in (404, 410):
                dead_subscription_ids.append(subscription.id)
            else:
                logger.warning(
                    "Push delivery failed: agent_id=%s subscription_id=%s",
                    agent_id,
                    subscription.id,
                )

    if dead_subscription_ids:
        await session.execute(
            delete(PushSubscription).where(PushSubscription.id.in_(dead_subscription_ids))
        )
        await session.commit()
