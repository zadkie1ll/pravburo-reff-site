import asyncio
import logging
import smtplib
from email.message import EmailMessage

from src.core.config import get_settings

logger = logging.getLogger(__name__)


async def _send_email(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        if settings.app_env == "production":
            raise RuntimeError("SMTP is not configured")
        logger.warning("Development email: recipient=%s subject=%s body=%s", to, subject, body)
        return

    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    def deliver() -> None:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)

    await asyncio.to_thread(deliver)


async def send_code(email: str, code: str, purpose: str) -> None:
    await _send_email(
        email,
        "Код подтверждения Правбюро",
        f"Код для операции «{purpose}»: {code}\nКод действует ограниченное время.",
    )


async def send_referral_accepted_notice(email: str, applicant_name: str) -> None:
    await _send_email(
        email,
        "Заявка по вашей рекомендации принята",
        f"Заявка на консультацию от {applicant_name} по вашей рекомендации принята, "
        "мы уже связываемся с ним.",
    )


async def send_admin_profile_change_notice(
    admin_emails: list[str], agent_label: str, changed_fields: list[str]
) -> None:
    body = (
        f"Партнёр {agent_label} изменил в профиле: {', '.join(changed_fields)}.\n"
        "Проверьте данные перед следующей выплатой."
    )
    for email in admin_emails:
        await _send_email(email, "Партнёр изменил реквизиты", body)
