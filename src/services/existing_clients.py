"""Import a local client binding without submitting a lead or replaying past rewards."""

import logging
from datetime import date
from decimal import Decimal, InvalidOperation

from pravburo_ref_common.models import (
    Agent,
    AgentRole,
    DeliveryStatus,
    ExistingClientImport,
    ProcessingStatus,
    ReferralApplication,
    Reward,
    RewardStatus,
    RewardType,
)
from sqlalchemy import or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import normalize_phone
from src.services.client_workflow import WorkflowInput, save_workflow

logger = logging.getLogger(__name__)


class ExistingClientConflict(ValueError):
    pass


def accounted_milestones(snapshot: dict) -> list[str]:
    if snapshot["category_id"] != 2:
        return []
    result = []
    payment = Decimal(snapshot.get("first_payment") or "0")
    if payment >= 8000:
        result.append(RewardType.ADVANCE.value)
    if snapshot["stage_code"] in {"C2:UC_MYA2I0", "C2:UC_7TR7XT", "C2:WON"}:
        result.append(RewardType.MAIN.value)
        if snapshot.get("paid_in_full"):
            result.append(RewardType.BONUS_FULL_PAYMENT.value)
    return result


def current_balance(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    try:
        amount = Decimal(value)
        if not amount.is_finite() or amount <= 0 or amount > Decimal("9999999999.99"):
            raise ValueError("Укажите положительную сумму остатка к выплате")
        if amount != amount.quantize(Decimal("0.01")):
            raise ValueError("В сумме допустимо не более двух знаков после запятой")
        return amount
    except InvalidOperation as exc:
        raise ValueError("Некорректная сумма остатка к выплате") from exc


async def import_existing_client(
    session: AsyncSession,
    *,
    admin_id: int,
    agent_id: int,
    snapshot: dict,
    full_name: str,
    phone: str,
    admin_note: str,
    current_amount: Decimal | None,
    payout_due_date: date | None = None,
    workflow: WorkflowInput | None = None,
) -> ExistingClientImport:
    deal_id = snapshot["deal_id"]
    name = full_name.strip()
    if not name:
        raise ValueError("Укажите ФИО клиента")
    phone = normalize_phone(phone)
    actual_phone = snapshot.get("phone")
    if actual_phone and normalize_phone(actual_phone) != phone:
        raise ValueError("Телефон не совпадает с контактом сделки Битрикса")
    amount = current_balance(current_amount)
    if workflow is not None and amount is not None:
        raise ValueError("Выберите учёт по этапам или единую сумму выплаты")
    if payout_due_date is not None and amount is None:
        raise ValueError("Укажите сумму к выплате для выбранной даты")
    # Serialize both deal imports and client-phone imports across workers.
    for key in sorted([f"existing-deal:{deal_id}", f"existing-phone:{phone}"]):
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key}
        )
    agent = await session.get(Agent, agent_id)
    if agent is None or agent.role != AgentRole.AGENT or not agent.is_active:
        raise ValueError("Выберите действующего партнёра")
    existing = await session.scalar(
        select(ExistingClientImport).where(ExistingClientImport.deal_id == deal_id)
    )
    if existing:
        application = await session.get(ReferralApplication, existing.application_id)
        if application.agent_id != agent_id:
            raise ExistingClientConflict("Эта сделка уже закреплена за другим партнёром")
        return existing  # Idempotent retry never changes an existing financial balance.
    if (
        snapshot.get("attributed_application_id") is not None
        or snapshot.get("attributed_agent_id") is not None
    ):
        raise ExistingClientConflict(
            "Сделка уже содержит реферальную привязку. Проверьте её перед переносом"
        )
    duplicate = await session.scalar(
        select(ReferralApplication.id)
        .where(
            or_(
                ReferralApplication.bitrix_deal_id == deal_id,
                ReferralApplication.phone_normalized == phone,
            )
        )
        .limit(1)
    )
    if duplicate is not None:
        raise ExistingClientConflict(
            "Клиент или сделка уже есть в системе. Повторный перенос не выполнен"
        )
    if (
        await session.scalar(select(Reward.id).where(Reward.deal_id == deal_id).limit(1))
        is not None
    ):
        raise ExistingClientConflict(
            "По сделке уже существуют начисления. Проверьте привязку клиента"
        )
    excluded = accounted_milestones(snapshot)
    application = ReferralApplication(
        agent_id=agent_id,
        full_name=name,
        phone_normalized=phone,
        delivery_status=DeliveryStatus.SENT,
        processing_status=ProcessingStatus.IN_PROGRESS,
        bitrix_deal_id=deal_id,
        deal_stage_code=snapshot["stage_code"],
    )
    try:
        session.add(application)
        await session.flush()
        reward_id = None
        if amount is not None:
            reward = Reward(
                deal_id=deal_id,
                application_id=application.id,
                agent_id=agent_id,
                reward_type=RewardType.MAIN,
                amount=amount,
                payout_due_date=payout_due_date,
                status=RewardStatus.PENDING,
            )
            session.add(reward)
            await session.flush()
            reward_id = reward.id
            if RewardType.MAIN.value not in excluded:
                excluded.append(RewardType.MAIN.value)
        record = ExistingClientImport(
            application_id=application.id,
            deal_id=deal_id,
            excluded_reward_types=excluded,
            current_reward_id=reward_id,
            imported_by_agent_id=admin_id,
            admin_note=admin_note.strip() or None,
        )
        session.add(record)
        await session.flush()
        if workflow is not None:
            await save_workflow(session, record, workflow, admin_id)
        await session.commit()
        await session.refresh(record)
    except IntegrityError as exc:
        await session.rollback()
        raise ExistingClientConflict("Сделка уже перенесена. Обновите список клиентов") from exc
    logger.info(
        "Existing client imported: admin_id=%s agent_id=%s application_id=%s",
        admin_id,
        agent_id,
        application.id,
    )
    return record


async def update_current_payout(
    session: AsyncSession,
    *,
    application_id: int,
    admin_id: int,
    amount: Decimal,
    payout_due_date: date,
) -> ExistingClientImport | None:
    amount = current_balance(amount)
    record = await session.get(ExistingClientImport, application_id, with_for_update=True)
    if record is None:
        return None
    if record.workflow_data is not None:
        raise ExistingClientConflict(
            "Откройте договор и выплаты клиента для редактирования по этапам"
        )
    reward = (
        await session.get(
            Reward, record.current_reward_id, with_for_update=True, populate_existing=True
        )
        if record.current_reward_id is not None
        else None
    )
    if record.current_reward_id is not None and reward is None:
        raise ExistingClientConflict("Начисление не найдено. Обновите список клиентов")
    if reward is not None:
        if reward.paid_at is not None or reward.status == RewardStatus.REJECTED:
            raise ExistingClientConflict("Выплаченное или отклонённое начисление изменить нельзя")
        if reward.payout_due_date != payout_due_date:
            reward.due_notice_sent_at = None
            reward.overdue_notice_sent_at = None
        reward.amount = amount
        reward.payout_due_date = payout_due_date
    else:
        # Never replace an automatically created reward with a manual balance.
        application = await session.get(ReferralApplication, application_id)
        if (
            await session.scalar(
                select(Reward.id)
                .where(
                    Reward.deal_id == record.deal_id,
                    Reward.agent_id == application.agent_id,
                    Reward.reward_type == RewardType.MAIN,
                )
                .limit(1)
            )
            is not None
        ):
            raise ExistingClientConflict(
                "По сделке уже есть основное начисление. Проверьте начисления"
            )
        reward = Reward(
            deal_id=record.deal_id,
            application_id=application_id,
            agent_id=application.agent_id,
            reward_type=RewardType.MAIN,
            status=RewardStatus.PENDING,
            amount=amount,
            payout_due_date=payout_due_date,
        )
        session.add(reward)
        try:
            await session.flush()
        except IntegrityError as exc:
            await session.rollback()
            raise ExistingClientConflict(
                "Начисление уже создано. Обновите список клиентов"
            ) from exc
        record.current_reward_id = reward.id
        record.excluded_reward_types = list(
            dict.fromkeys([*record.excluded_reward_types, RewardType.MAIN.value])
        )
    await session.commit()
    logger.info("Imported payout updated: admin_id=%s reward_id=%s", admin_id, reward.id)
    return record


async def update_existing_client(
    session: AsyncSession,
    *,
    application_id: int,
    admin_id: int,
    full_name: str,
    phone: str,
    admin_note: str,
) -> ExistingClientImport | None:
    name = full_name.strip()
    if not name:
        raise ValueError("Укажите ФИО клиента")
    phone = normalize_phone(phone)
    record = await session.get(ExistingClientImport, application_id, with_for_update=True)
    if record is None:
        return None
    application = await session.get(ReferralApplication, application_id, with_for_update=True)
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"existing-phone:{phone}"},
    )
    if (
        await session.scalar(
            select(ReferralApplication.id)
            .where(
                ReferralApplication.phone_normalized == phone,
                ReferralApplication.id != application_id,
            )
            .limit(1)
        )
        is not None
    ):
        raise ExistingClientConflict("Клиент с таким телефоном уже есть в системе")
    application.full_name = name
    application.phone_normalized = phone
    record.admin_note = admin_note.strip() or None
    await session.commit()
    logger.info("Existing client updated: admin_id=%s application_id=%s", admin_id, application_id)
    return record
