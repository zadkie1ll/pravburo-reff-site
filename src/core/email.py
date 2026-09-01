import asyncio
import logging
import smtplib
from email.message import EmailMessage

from src.core.config import get_settings

logger = logging.getLogger(__name__)


async def send_code(email: str, code: str, purpose: str) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        if settings.app_env == "production":
            raise RuntimeError("SMTP is not configured")
        logger.warning(
            "Development email code: recipient=%s purpose=%s code=%s", email, purpose, code
        )
        return

    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = email
    message["Subject"] = "Код подтверждения Правбюро"
    message.set_content(f"Код для операции «{purpose}»: {code}\nКод действует ограниченное время.")

    def deliver() -> None:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)

    await asyncio.to_thread(deliver)
