from datetime import date
from types import SimpleNamespace

from pravburo_ref_common.models import DeliveryStatus

from src.core.telegram import (
    build_new_partner_message,
    build_new_referral_message,
    build_payout_details_changed_message,
    build_payout_due_message,
    build_payout_overdue_message,
)


def test_message_contains_application_agent_and_bitrix_result() -> None:
    agent = SimpleNamespace(id=7, display_name="Анна Агент")
    application = SimpleNamespace(
        id=42,
        full_name="Иван Иванов",
        phone_normalized="79991234567",
        preferred_call_time_msk="15:00–18:00",
        city="Москва",
        debt_amount="500 000",
        situation="Нужна консультация",
        delivery_status=DeliveryStatus.SENT,
        bitrix_lead_id="19925",
    )

    message = build_new_referral_message(
        agent,
        application,
        "https://example.bitrix24.ru/crm/lead/details/{lead_id}/",
    )

    assert "Заявка: #42" in message
    assert "Агент: Анна Агент (#7)" in message
    assert "Телефон: 79991234567" in message
    assert "Bitrix24: создан лид #19925" in message
    assert "https://example.bitrix24.ru/crm/lead/details/19925/" in message


def test_message_marks_failed_crm_delivery_for_retry() -> None:
    agent = SimpleNamespace(id=7, display_name="")
    application = SimpleNamespace(
        id=43,
        full_name="Иван Иванов",
        phone_normalized="79991234568",
        preferred_call_time_msk=None,
        city=None,
        debt_amount=None,
        situation=None,
        delivery_status=DeliveryStatus.FAILED,
        bitrix_lead_id=None,
    )

    message = build_new_referral_message(agent, application)

    assert "Агент: — (#7)" in message
    assert "Bitrix24: лид не создан, заявка сохранена и требует повторной отправки" in message


def test_new_partner_message_contains_agent_details() -> None:
    agent = SimpleNamespace(
        id=11, display_name="Пётр Партнёров", email="petr@example.com", phone_normalized=None
    )

    message = build_new_partner_message(agent)

    assert "Новый партнёр зарегистрировался" in message
    assert "Партнёр: Пётр Партнёров (#11)" in message
    assert "Почта: petr@example.com" in message
    assert "Телефон: —" in message


def test_payout_details_changed_message_contains_agent_details() -> None:
    agent = SimpleNamespace(id=12, display_name="", email="olya@example.com")

    message = build_payout_details_changed_message(agent)

    assert "Партнёр изменил реквизиты для выплат" in message
    assert "Партнёр: — (#12)" in message
    assert "Почта: olya@example.com" in message


def test_payout_due_message_contains_target_date_and_amount() -> None:
    reward = SimpleNamespace(amount="15000.00")
    agent = SimpleNamespace(id=5, display_name="Ольга Партнёрова")

    message = build_payout_due_message(reward, agent, "Иван Клиентов", date(2026, 9, 15))

    assert "Наступила дата запланированной выплаты" in message
    assert "Партнёр: Ольга Партнёрова (#5)" in message
    assert "Клиент: Иван Клиентов" in message
    assert "Сумма: 15000.00" in message
    assert "Плановая дата: 2026-09-15" in message


def test_payout_overdue_message_contains_days_overdue() -> None:
    reward = SimpleNamespace(amount="8000.00")
    agent = SimpleNamespace(id=6, display_name="Зина Партнёрова")

    message = build_payout_overdue_message(
        reward, agent, "Анна Клиентова", date(2026, 9, 10), 3
    )

    assert "Выплата просрочена на 3 дн." in message
    assert "Партнёр: Зина Партнёрова (#6)" in message
    assert "Плановая дата: 2026-09-10" in message
