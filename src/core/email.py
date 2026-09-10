import asyncio
import logging
import smtplib
from email.message import EmailMessage

from src.core.config import get_settings

logger = logging.getLogger(__name__)

LOGO_URL = "https://agents.prav-buro.ru/static/img/logo.svg"


def _render_html(heading: str, paragraphs: list[str], code: str | None = None) -> str:
    body_html = "".join(
        f'<p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#33475c;">{p}</p>'
        for p in paragraphs
    )
    code_html = ""
    if code:
        code_html = f"""
          <div style="margin:4px 0 24px;padding:16px 24px 16px 24px;background:#eef4fd;
                      border-radius:14px;text-align:center;font-size:32px;font-weight:700;
                      letter-spacing:.4em;color:#2582dc;font-family:'SF Mono',Consolas,monospace;">
            <span style="padding-left:.4em;">{code}</span>
          </div>
        """
    return f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:24px;background:#f4f7fb;
               font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                 style="max-width:480px;background:#ffffff;border-radius:20px;padding:32px;">
            <tr>
              <td align="center" style="padding-bottom:24px;">
                <img src="{LOGO_URL}" width="48" height="48" alt="Правбюро" style="display:block;">
                <div style="margin-top:8px;font-size:13px;color:#8a97a8;letter-spacing:.02em;">
                  Агентская программа
                </div>
              </td>
            </tr>
            <tr>
              <td style="font-size:20px;font-weight:600;color:#33475c;padding-bottom:12px;">
                {heading}
              </td>
            </tr>
            <tr>
              <td>
                {code_html}
                {body_html}
              </td>
            </tr>
          </table>
          <div style="max-width:480px;margin-top:16px;font-size:12px;color:#a3adba;">
            © Правбюро
          </div>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


async def _send_email(
    to: str,
    subject: str,
    body: str,
    *,
    heading: str | None = None,
    code: str | None = None,
) -> None:
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
    paragraphs = [line for line in body.split("\n") if line.strip()]
    message.add_alternative(
        _render_html(heading or subject, paragraphs, code=code), subtype="html"
    )

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
        heading=f"Код для операции «{purpose}»",
        code=code,
    )


async def send_referral_accepted_notice(email: str, applicant_name: str) -> None:
    await _send_email(
        email,
        "Заявка по вашей рекомендации принята",
        f"Заявка на консультацию от {applicant_name} по вашей рекомендации принята, "
        "мы уже связываемся с ним.",
    )


async def send_payout_paid_notice(email: str, amount_label: str) -> None:
    await _send_email(
        email,
        "Выплата произведена",
        f"Ваша выплата на сумму {amount_label} произведена.",
    )


async def send_reward_notice(email: str, type_label: str, amount_label: str) -> None:
    await _send_email(
        email,
        f"Начислено вознаграждение: {type_label}",
        f"Вам начислено вознаграждение «{type_label}» на сумму {amount_label}.",
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
