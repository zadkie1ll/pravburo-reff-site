from datetime import date

import httpx
from pravburo_ref_common.models import Agent, DeliveryStatus, ReferralApplication, Reward

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


async def _send_admin_notice(message: str) -> None:
    settings = get_settings()
    token = settings.telegram_notification_bot_token
    chat_ids = settings.telegram_notification_chat_id_list
    if not token or not chat_ids:
        return

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


async def send_new_referral_notice(agent: Agent, application: ReferralApplication) -> None:
    settings = get_settings()
    message = build_new_referral_message(agent, application, settings.bitrix_lead_url_template)
    await _send_admin_notice(message)


def build_new_partner_message(agent: Agent) -> str:
    return "\n".join(
        [
            "Новый партнёр зарегистрировался",
            f"Партнёр: {_value_or_dash(agent.display_name)} (#{agent.id})",
            f"Почта: {_value_or_dash(agent.email)}",
            f"Телефон: {_value_or_dash(agent.phone_normalized)}",
        ]
    )


async def send_new_partner_notice(agent: Agent) -> None:
    await _send_admin_notice(build_new_partner_message(agent))


def build_payout_details_changed_message(agent: Agent) -> str:
    return "\n".join(
        [
            "Партнёр изменил реквизиты для выплат",
            f"Партнёр: {_value_or_dash(agent.display_name)} (#{agent.id})",
            f"Почта: {_value_or_dash(agent.email)}",
            "Нужна проверка перед следующей выплатой",
        ]
    )


async def send_payout_details_changed_notice(agent: Agent) -> None:
    await _send_admin_notice(build_payout_details_changed_message(agent))


def build_payout_due_message(
    reward: Reward, agent: Agent, client_name: str, target_date: date
) -> str:
    return "\n".join(
        [
            "Наступила дата запланированной выплаты",
            f"Партнёр: {_value_or_dash(agent.display_name)} (#{agent.id})",
            f"Клиент: {client_name}",
            f"Сумма: {reward.amount}",
            f"Плановая дата: {target_date.isoformat()}",
        ]
    )


async def send_payout_due_notice(
    reward: Reward, agent: Agent, client_name: str, target_date: date
) -> None:
    await _send_admin_notice(build_payout_due_message(reward, agent, client_name, target_date))


def build_payout_overdue_message(
    reward: Reward, agent: Agent, client_name: str, target_date: date, days_overdue: int
) -> str:
    return "\n".join(
        [
            f"Выплата просрочена на {days_overdue} дн.",
            f"Партнёр: {_value_or_dash(agent.display_name)} (#{agent.id})",
            f"Клиент: {client_name}",
            f"Сумма: {reward.amount}",
            f"Плановая дата: {target_date.isoformat()}",
        ]
    )


async def send_payout_overdue_notice(
    reward: Reward, agent: Agent, client_name: str, target_date: date, days_overdue: int
) -> None:
    await _send_admin_notice(
        build_payout_overdue_message(reward, agent, client_name, target_date, days_overdue)
    )
