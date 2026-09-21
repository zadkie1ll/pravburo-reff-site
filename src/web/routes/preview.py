import hmac
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from pravburo_ref_common.models import EmploymentFormat

from src.core.config import get_settings
from src.services.payouts import (
    PAGE_STATUS_LABELS,
    REWARD_TYPE_LABELS,
    FinanceSummary,
    PayoutFilters,
    PayoutRow,
    PendingGroup,
)
from src.services.profile import EMPLOYMENT_FORMAT_LABELS, EMPLOYMENT_FORMAT_OPTIONS
from src.services.referrals import LinkStats, NetworkClientRow
from src.web.routes.pages import templates

router = APIRouter(prefix="/preview", tags=["UI preview"])
DUMMY_REFERRAL_CODE = UUID("00000000-0000-4000-8000-000000000001")
DUMMY_FAQ_ITEMS = [
    (
        "Когда я получу деньги?",
        "Аванс начисляется, когда клиент подписывает договор. Основная выплата — когда "
        "клиент оплачивает депозит по делу. Статус каждой выплаты видно в вашем кабинете.",
    ),
    (
        "Как узнать на каком этапе мой клиент?",
        "Текущий статус по каждому клиенту виден в вашем кабинете.",
    ),
]


def require_preview(token: str = Query(default="")) -> str:
    settings = get_settings()
    if (
        not settings.ui_preview_enabled
        or not settings.ui_preview_token
        or not token
        or not hmac.compare_digest(token, settings.ui_preview_token)
    ):
        raise HTTPException(status_code=404, detail="Preview not found")
    return token


PreviewToken = Annotated[str, Depends(require_preview)]


def preview_context(**values) -> dict:
    return {
        "preview_mode": True,
        "csrf_token": "preview-csrf-token",
        "error": "",
        "info": "",
        "telegram_bot_username": "",
        "telegram_auth_url": "#",
        "yandex_enabled": False,
        **values,
    }


def sample_data(token: str) -> dict:
    status_sent = SimpleNamespace(value="sent")
    status_pending = SimpleNamespace(value="pending")
    status_rejected = SimpleNamespace(value="rejected")
    role_admin = SimpleNamespace(value="admin")
    agent = SimpleNamespace(
        id=101,
        email="agent@example.ru",
        display_name="Светлана Иванова",
        role=role_admin,
        referral_code=DUMMY_REFERRAL_CODE,
        phone_normalized="+79991234567",
        employment_format=EmploymentFormat.SELF_EMPLOYED,
        payout_details="Карта •••• 4242",
        inn="616700000000",
        is_active=True,
        created_at=datetime(2025, 1, 15, tzinfo=UTC),
    )
    first_application = SimpleNamespace(
        id=501,
        full_name="Ангелина Петрова",
        city="Ростов-на-Дону",
        debt_amount="850 000 ₽",
        preferred_call_time_msk="с 15:00 до 18:00",
        situation="Есть несколько кредитов, нужна консультация по возможным вариантам.",
        delivery_status=status_sent,
    )
    second_application = SimpleNamespace(
        id=502,
        full_name="Алексей Смирнов",
        city="Краснодар",
        debt_amount="1 200 000 ₽",
        preferred_call_time_msk="после 17:00",
        situation="Потерял работу и больше не справляюсь с ежемесячными платежами.",
        delivery_status=status_sent,
    )
    pending_reward = SimpleNamespace(
        id=701,
        deal_id="123456",
        application_id=501,
        status=status_pending,
        rejection_reason=None,
    )
    rejected_reward = SimpleNamespace(
        id=702,
        deal_id="123457",
        application_id=502,
        status=status_rejected,
        rejection_reason="Не подтверждено выполнение условий программы",
    )
    query = urlencode({"token": token})
    return {
        "agent": agent,
        "application_one": first_application,
        "application_two": second_application,
        "reward_one": pending_reward,
        "reward_two": rejected_reward,
        "referral_url": f"https://preview.example/r/{DUMMY_REFERRAL_CODE}",
        "qr_url": f"/preview/qr.png?{query}",
        "client": SimpleNamespace(
            id=123,
            name="Иван",
            surname="Иванов",
            middlename="Иванович",
            full_name="Иванов Иван Иванович",
            email="client@example.ru",
            registered_at=datetime(2025, 1, 15, tzinfo=UTC),
            stage_id=4,
        ),
    }


@router.get("", response_class=HTMLResponse)
async def preview_index(request: Request, token: PreviewToken) -> HTMLResponse:
    query = urlencode({"token": token})
    referral_url = f"/preview/referral/{DUMMY_REFERRAL_CODE}?{query}"
    pages = [
        ("Главная", "Стартовая страница приложения", f"/preview/page/home?{query}"),
        ("Вход", "Email, пароль и социальный вход", f"/preview/page/login?{query}"),
        ("Регистрация", "Создание агентского аккаунта", f"/preview/page/register?{query}"),
        ("Подтверждение", "Шестизначный код из письма", f"/preview/page/confirm?{query}"),
        ("Восстановление", "Запрос кода восстановления", f"/preview/page/reset?{query}"),
        ("Новый пароль", "Код и установка пароля", f"/preview/page/reset-confirm?{query}"),
        ("Кабинет агента", "Ссылка, QR, клиенты и начисления", f"/preview/page/cabinet?{query}"),
        ("Профиль", "Данные агента и реквизиты", f"/preview/page/profile?{query}"),
        ("Выбор формы", "Первый вход: форма сотрудничества", f"/preview/page/onboarding?{query}"),
        ("Реферальная форма", "Публичная форма по UUID-ссылке", referral_url),
        ("Заявка принята", "Успешная отправка формы", f"/preview/page/success?{query}"),
        ("FAQ", "Как это работает и частые вопросы", f"/preview/page/faq?{query}"),
        ("История выплат", "Таблица выплат с фильтрами и PDF", f"/preview/page/payouts?{query}"),
        ("Legacy-клиент", "Профиль из старого ЛК", f"/preview/page/client?{query}"),
        ("404", "Страница отсутствующего клиента", f"/preview/page/not-found?{query}"),
        (
            "Настройка 2FA",
            "Подключение приложения-аутентификатора",
            f"/preview/page/2fa-setup?{query}",
        ),
        ("Проверка 2FA", "Ввод одноразового кода", f"/preview/page/2fa-verify?{query}"),
    ]
    return templates.TemplateResponse(
        request=request,
        name="preview_index.html",
        context=preview_context(
            pages=[
                {"title": title, "description": description, "url": url}
                for title, description, url in pages
            ]
        ),
    )


@router.get("/qr.png")
async def preview_qr(_: PreviewToken) -> Response:
    image = qrcode.make(f"https://preview.example/r/{DUMMY_REFERRAL_CODE}")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return Response(buffer.getvalue(), media_type="image/png")


@router.get("/referral/{referral_code}", response_class=HTMLResponse)
async def preview_referral(
    request: Request, referral_code: UUID, token: PreviewToken
) -> HTMLResponse:
    data = sample_data(token)
    data["agent"].referral_code = referral_code
    return templates.TemplateResponse(
        request=request,
        name="referral_form.html",
        context=preview_context(agent=data["agent"], turnstile_site_key=""),
    )


@router.get("/page/{page}", response_class=HTMLResponse)
async def preview_page(request: Request, page: str, token: PreviewToken) -> HTMLResponse:
    data = sample_data(token)
    network_client_rows = [
        NetworkClientRow(
            client_name="Иванов Пётр",
            masked_phone="+7 *** *** ** 67",
            created_at=datetime.now(UTC),
            reward_summary="Аванс: Ожидает решения",
            stage="Договор подписан",
            reward_totals="Выплачено: 0 ₽ · Ожидается: 3 000 ₽",
        ),
        NetworkClientRow(
            client_name="Смирнова Анна",
            masked_phone="+7 *** *** ** 09",
            created_at=datetime.now(UTC),
            reward_summary="Аванс: Отклонено",
            stage="Заявка получена",
            reward_totals="—",
        ),
        NetworkClientRow(
            client_name="Кузнецов Дмитрий",
            masked_phone="+7 *** *** ** 31",
            created_at=datetime.now(UTC),
            reward_summary="Бонус за сеть: Выплачено",
            stage="Заявление подано в суд",
            reward_totals="Выплачено: 1 000 ₽ · Ожидается: 0 ₽",
        ),
    ]
    templates_by_page = {
        "home": ("index.html", {"app_name": "Prav-Buro Refferal"}),
        "login": ("login.html", {}),
        "register": ("register.html", {}),
        "confirm": ("confirm_registration.html", {}),
        "reset": ("password_reset.html", {}),
        "reset-confirm": (
            "password_reset_confirm.html",
            {"info": "Код отправлен на agent@example.ru"},
        ),
        "cabinet": (
            "agent_dashboard.html",
            {
                "agent": data["agent"],
                "referral_url": data["referral_url"],
                "qr_url": data["qr_url"],
                "bounty_admin_url": get_settings().bounty_admin_url,
                "link_stats": LinkStats(visits=48, applications=2, contracts=1),
                "network_client_rows": network_client_rows,
                "finance": FinanceSummary(
                    total_paid_label="18 000 ₽",
                    this_month_label="3 000 ₽",
                    pending_total_label="10 000 ₽",
                    pending_groups=[
                        PendingGroup(label="Ждём выплаты", amount_label="10 000 ₽"),
                    ],
                ),
            },
        ),
        "success": ("referral_success.html", {}),
        "profile": (
            "profile.html",
            {"agent": data["agent"], "employment_formats": EMPLOYMENT_FORMAT_LABELS},
        ),
        "faq": (
            "faq.html",
            {
                "faq_items": DUMMY_FAQ_ITEMS,
                "telegram_manager_url": get_settings().telegram_manager_url,
                "telegram_materials_url": get_settings().telegram_materials_url,
            },
        ),
        "client": ("dashboard.html", {"client": data["client"]}),
        "payouts": (
            "payouts.html",
            {
                "rows": [
                    PayoutRow(
                        reward=data["reward_one"],
                        client_name=data["application_one"].full_name,
                        type_label="Аванс",
                        status_label="Запланировано",
                        status_slug="scheduled",
                        amount_label="3 000 ₽",
                        payout_date_label="—",
                    ),
                    PayoutRow(
                        reward=data["reward_two"],
                        client_name=data["application_two"].full_name,
                        type_label="Основная выплата",
                        status_label="Выплачено",
                        status_slug="paid",
                        amount_label="45 000 ₽",
                        payout_date_label="12.02.2026",
                    ),
                    PayoutRow(
                        reward=data["reward_two"],
                        client_name=data["application_one"].full_name,
                        type_label="Аванс",
                        status_label="Отклонено",
                        status_slug="rejected",
                        amount_label="3 000 ₽",
                        payout_date_label="—",
                        rejection_reason="Не удалось связаться с клиентом",
                    ),
                    PayoutRow(
                        reward=None,
                        client_name="Петров Сергей",
                        type_label="—",
                        status_label="Оплата депозита",
                        status_slug="deposit",
                        amount_label="—",
                        payout_date_label="—",
                    ),
                    PayoutRow(
                        reward=None,
                        client_name="Сидорова Анна",
                        type_label="—",
                        status_label="Анализ ситуации",
                        status_slug="analysis",
                        amount_label="—",
                        payout_date_label="—",
                    ),
                    PayoutRow(
                        reward=None,
                        client_name="Козлов Игорь",
                        type_label="—",
                        status_label="Ушел в игнор",
                        status_slug="ignored",
                        amount_label="—",
                        payout_date_label="—",
                    ),
                ],
                "filters": PayoutFilters(),
                "reward_types": REWARD_TYPE_LABELS,
                "statuses": PAGE_STATUS_LABELS,
            },
        ),
        "onboarding": (
            "onboarding.html",
            {
                "onboarding": True,
                "options": EMPLOYMENT_FORMAT_OPTIONS,
                "telegram_manager_url": "https://t.me/pravburo",
                "csrf_token": "preview",
            },
        ),
        "not-found": ("not_found.html", {}),
        "2fa-setup": ("admin_2fa_setup.html", {"qr_url": data["qr_url"]}),
        "2fa-verify": ("admin_2fa_verify.html", {}),
    }
    selected = templates_by_page.get(page)
    if selected is None:
        raise HTTPException(status_code=404, detail="Preview page not found")
    template_name, context = selected
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=preview_context(**context),
    )
