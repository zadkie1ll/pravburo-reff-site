import httpx
from pravburo_ref_common.models import Agent, DeliveryStatus, ReferralApplication

from src.core.config import get_settings


class TelegramNotificationError(RuntimeError):
    pass


def _value_or_dash(value: str | None) -> str:
    return value.strip() if value and value.strip() else "—"


def build_new_referral_message(
    agent: Agent,
    application: ReferralApplication,
    bitrix_lead_url_template: str = "",
) -> str:
    if application.delivery_status == DeliveryStatus.SENT and application.bitrix_lead_id:
        crm_result = f"создан лид #{application.bitrix_lead_id}"
        crm_url = bitrix_lead_url_template.format(lead_id=application.bitrix_lead_id)
    else:
        crm_result = "лид не создан, заявка сохранена и требует повторной отправки"
        crm_url = ""

    lines = [
            "Новая заявка по реферальной ссылке",
            f"Заявка: #{application.id}",
            f"Агент: {_value_or_dash(agent.display_name)} (#{agent.id})",
            f"Клиент: {application.full_name}",
            f"Телефон: {application.phone_normalized}",
            f"Время звонка (МСК): {_value_or_dash(application.preferred_call_time_msk)}",
            f"Город: {_value_or_dash(application.city)}",
            f"Сумма долга: {_value_or_dash(application.debt_amount)}",
            f"Ситуация: {_value_or_dash(application.situation)}",
            f"Bitrix24: {crm_result}",
    ]
    if crm_url:
        lines.append(f"Открыть лид: {crm_url}")
    return "\n".join(lines)


async def send_new_referral_notice(agent: Agent, application: ReferralApplication) -> None:
    settings = get_settings()
    token = settings.telegram_notification_bot_token
    chat_ids = settings.telegram_notification_chat_id_list
    if not token or not chat_ids:
        return

    message = build_new_referral_message(
        agent,
        application,
        settings.bitrix_lead_url_template,
    )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as client:
        for chat_id in chat_ids:
            response = await client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "disable_web_page_preview": True,
                },
            )
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            if response.is_error or payload.get("ok") is not True:
                raise TelegramNotificationError(
                    f"Telegram rejected notification for chat_id={chat_id}"
                )
