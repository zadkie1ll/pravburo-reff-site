from types import SimpleNamespace

from pravburo_ref_common.models import DeliveryStatus

from src.core.telegram import build_new_referral_message


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
