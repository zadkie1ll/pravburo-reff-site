"""Explicit settlement of imported clients; all outstanding sums use real Reward rows.

Historical paid stages live only in the import snapshot and never create new rewards.
Normal Bitrix referrals continue to use bounty; managed imports exclude replay there.
"""

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pravburo_ref_common.models import (
    Agent,
    ExistingClientImport,
    NetworkOverrideRate,
    PartnerLevel,
    PartnerLevelMonth,
    ReferralApplication,
    Reward,
    RewardStageRate,
    RewardStatus,
    RewardType,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
MOSCOW = ZoneInfo("Europe/Moscow")
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Day = Annotated[date, Field(ge=date(2000, 1, 1), le=date(2200, 1, 1))]
KINDS = ("advance", "main", "bonus", "curator")
LABELS = {
    "advance": "Аванс агенту",
    "main": "Основная сумма агенту",
    "bonus": "Бонус 100%",
    "curator": "Выплата куратору",
}


class WorkflowConflict(ValueError):
    pass


class WorkflowInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(default=0, ge=0)
    contract_status: Literal["not_signed", "date_unknown", "signed"] | None = None
    contract_date: Day | None = None
    first_payment: Money = Decimal("0")
    deposit_paid_on: Day | None = None
    paid_in_full: bool = False
    advance_amount: Money = Decimal("0")
    main_amount: Money = Decimal("0")
    curator_amount: Money = Decimal("0")
    advance_due_on: Day | None = None
    main_due_on: Day | None = None
    advance_paid_on: Day | None = None
    main_paid_on: Day | None = None
    curator_paid_on: Day | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        today = datetime.now(MOSCOW).date()
        # Existing saved workflows have only contract_date; keep their meaning.
        if self.contract_status is None:
            self.contract_status = "signed" if self.contract_date else "not_signed"
        if self.contract_status == "signed" and self.contract_date is None:
            raise ValueError("Укажите дату договора или выберите «Дата неизвестна»")
        if self.contract_status != "signed" and self.contract_date is not None:
            raise ValueError("Дата договора не соответствует выбранному состоянию договора")
        if self.contract_date and self.contract_date > today:
            raise ValueError("Дата договора не может быть в будущем")
        for label, value in [
            ("оплаты депозита", self.deposit_paid_on),
            ("выплаты аванса", self.advance_paid_on),
            ("основной выплаты", self.main_paid_on),
            ("выплаты куратору", self.curator_paid_on),
        ]:
            if value and ((self.contract_date and value < self.contract_date) or value > today):
                raise ValueError(
                    f"Дата {label} должна быть между датой договора и сегодняшним днём"
                )
        if self.contract_status == "not_signed" and any(
            (
                self.deposit_paid_on,
                self.advance_paid_on,
                self.main_paid_on,
                self.curator_paid_on,
                self.paid_in_full,
            )
        ):
            raise ValueError("Чтобы указать оплаты по договору, отметьте, что договор подписан")
        if self.deposit_paid_on and self.first_payment < 8000:
            raise ValueError(
                "Депозит отмечен оплаченным, но внесено меньше 8 000 ₽. Проверьте сумму"
            )
        if self.advance_paid_on and self.first_payment < 8000:
            raise ValueError("Аванс доступен после поступления от клиента минимум 8 000 ₽")
        if (self.main_paid_on or self.curator_paid_on) and not self.deposit_paid_on:
            raise ValueError("Укажите дату оплаты депозита")
        return self


def workday_after(start: date, days: int) -> date:
    """Matches WORKDAY without a holidays range: Monday–Friday, excluding start."""
    current = start
    for _ in range(days):
        current += timedelta(days=1)
        while current.weekday() >= 5:
            current += timedelta(days=1)
    return current


def stage_plan(body: WorkflowInput, curator_id: int | None) -> dict:
    known_contract = body.contract_status == "signed" and body.contract_date is not None
    main_due = (
        (
            body.main_due_on
            or (workday_after(body.deposit_paid_on, 15) if body.deposit_paid_on else None)
        )
        if known_contract
        else None
    )
    advance_due = (
        (body.advance_due_on or workday_after(body.contract_date, 5)) if known_contract else None
    )
    main_ready = known_contract and body.deposit_paid_on is not None
    return {
        "advance": dict(
            amount=body.advance_amount,
            due=advance_due,
            eligible=known_contract and body.first_payment >= 8000,
            historical=body.advance_paid_on,
            kind=RewardType.ADVANCE,
        ),
        "main": dict(
            amount=body.main_amount,
            due=main_due,
            eligible=main_ready,
            historical=body.main_paid_on,
            kind=RewardType.MAIN,
        ),
        "bonus": dict(
            amount=Decimal("3000") if body.paid_in_full else Decimal("0"),
            due=main_due,
            eligible=main_ready and body.paid_in_full,
            historical=body.main_paid_on,
            kind=RewardType.BONUS_FULL_PAYMENT,
        ),
        "curator": dict(
            amount=body.curator_amount,
            due=main_due,
            eligible=main_ready and curator_id is not None,
            historical=body.curator_paid_on,
            kind=RewardType.CURATOR,
        ),
    }


async def workflow_defaults(session: AsyncSession, agent_id: int, contract_date: date) -> dict:
    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise ValueError("Партнёр не найден")
    level = await session.scalar(
        select(PartnerLevelMonth).where(
            PartnerLevelMonth.agent_id == agent_id,
            PartnerLevelMonth.year == contract_date.year,
            PartnerLevelMonth.month == contract_date.month,
        )
    )
    partner_level = level.level if level else PartnerLevel.START
    advance = await session.get(RewardStageRate, (RewardType.ADVANCE, PartnerLevel.START))
    main = await session.get(RewardStageRate, (RewardType.MAIN, partner_level))
    if advance is None or main is None:
        raise ValueError("Не настроены суммы аванса и основной выплаты")
    curator = (
        await session.get(Agent, agent.invited_by_agent_id) if agent.invited_by_agent_id else None
    )
    rate = await session.get(NetworkOverrideRate, 1) if curator else None
    return dict(
        advance_amount=str(advance.amount),
        main_amount=str(main.amount),
        curator_amount=str(rate.amount if rate else 0),
        curator_id=curator.id if curator else None,
        curator_name=(curator.display_name or f"Куратор #{curator.id}") if curator else None,
        agent_phone=agent.phone_normalized,
        curator_phone=curator.phone_normalized if curator else None,
        level=partner_level.value,
    )


async def save_workflow(
    session: AsyncSession, record: ExistingClientImport, body: WorkflowInput, admin_id: int
) -> None:
    old = record.workflow_data
    if body.version != (old or {}).get("version", 0):
        raise WorkflowConflict("Данные уже изменены. Обновите страницу перед сохранением")
    if old is None:
        if (
            await session.scalar(
                select(Reward.id).where(Reward.application_id == record.application_id).limit(1)
            )
            is not None
        ):
            raise WorkflowConflict(
                "По клиенту уже есть начисления. Сохраните их через существующую карточку выплаты"
            )
    application = await session.get(ReferralApplication, record.application_id)
    agent = await session.get(Agent, application.agent_id)
    curator_id = old.get("curator_id") if old else agent.invited_by_agent_id
    if (body.curator_amount or body.curator_paid_on) and curator_id is None:
        raise ValueError("У партнёра не указан куратор")
    plan = stage_plan(body, curator_id)
    ids = dict((old or {}).get("reward_ids", {}))
    original = WorkflowInput.model_validate(old["input"]) if old else None
    previous = stage_plan(original, curator_id) if original else {}
    for key in KINDS:
        stage = plan[key]
        # Imported history remains immutable and never enters new accrual totals.
        if original and previous[key]["historical"]:
            if any(
                stage[field] != previous[key][field]
                for field in (
                    ("amount", "historical", "eligible")
                    if original.contract_date
                    else ("amount", "historical")
                )
            ):
                raise WorkflowConflict(
                    f"{LABELS[key]}: уже внесённую историю выплаты менять нельзя"
                )
            continue
        reward = (
            await session.get(Reward, ids[key], with_for_update=True, populate_existing=True)
            if key in ids
            else None
        )
        if key in ids and reward is None:
            raise WorkflowConflict("Связанное начисление не найдено")
        if reward:
            if stage["historical"]:
                raise WorkflowConflict(
                    "Для существующего начисления используйте кнопку «Отметить выплаченным»"
                )
            if reward.paid_at or reward.status == RewardStatus.REJECTED:
                if any(
                    stage[field] != previous[key][field] for field in ("amount", "due", "eligible")
                ):
                    raise WorkflowConflict(
                        f"{LABELS[key]}: выплаченное или отклонённое начисление изменить нельзя"
                    )
                continue
            if not stage["eligible"] or stage["amount"] <= 0:
                raise WorkflowConflict(
                    f"{LABELS[key]}: начисление уже создано, нельзя убрать основание выплаты"
                )
            if reward.payout_due_date != stage["due"]:
                reward.due_notice_sent_at = None
                reward.overdue_notice_sent_at = None
            reward.amount, reward.payout_due_date = stage["amount"], stage["due"]
            continue
        if stage["historical"] or not stage["eligible"] or stage["amount"] == 0:
            continue
        if key == "curator":
            recipient = await session.get(Agent, curator_id)
            if recipient is None or not recipient.is_active:
                raise ValueError("Куратор заблокирован: проверьте получателя выплаты")
        reward = Reward(
            deal_id=record.deal_id,
            application_id=application.id,
            agent_id=curator_id if key == "curator" else application.agent_id,
            reward_type=stage["kind"],
            created_at=datetime.combine(body.contract_date, datetime.min.time(), MOSCOW)
            if key == "advance"
            else datetime.now(UTC),
            amount=stage["amount"],
            payout_due_date=stage["due"],
            status=RewardStatus.APPROVED,
            decided_at=datetime.now(UTC),
            decided_by_agent_id=admin_id,
            source_reward_id=None,
            network_level=None,
        )
        session.add(reward)
        await session.flush()
        ids[key] = reward.id
    record.excluded_reward_types = list(
        dict.fromkeys([*record.excluded_reward_types, "advance", "main", "bonus_full_payment"])
    )
    record.workflow_data = dict(
        version=(old or {}).get("version", 0) + 1,
        input=body.model_dump(mode="json"),
        reward_ids=ids,
        curator_id=curator_id,
    )
    # Keep the old singular editor from repricing a structured settlement.
    record.current_reward_id = None
    logger.info(
        "Client settlement saved: application_id=%s admin_id=%s", record.application_id, admin_id
    )


async def workflow_view(session: AsyncSession, record: ExistingClientImport) -> dict | None:
    data = record.workflow_data
    if data is None:
        return None
    body = WorkflowInput.model_validate(data["input"])
    curator = await session.get(Agent, data.get("curator_id")) if data.get("curator_id") else None
    result = []
    outstanding = Decimal("0")
    for key, stage in stage_plan(body, data.get("curator_id")).items():
        reward = (
            await session.get(Reward, data["reward_ids"][key])
            if key in data["reward_ids"]
            else None
        )
        historical = stage["historical"]
        paid = reward.paid_at.date() if reward and reward.paid_at else historical
        status = (
            "paid"
            if paid
            else "rejected"
            if reward and reward.status == RewardStatus.REJECTED
            else "ready"
            if reward
            else "waiting"
        )
        if stage["amount"] == 0:
            status = "none"
        if reward and status == "ready":
            outstanding += reward.amount
        result.append(
            dict(
                key=key,
                label=LABELS[key],
                amount=str(reward.amount if reward and not historical else stage["amount"]),
                due_on=stage["due"],
                paid_on=paid,
                status=status,
                reward_id=reward.id if reward and not historical else None,
                recipient=curator.display_name if key == "curator" and curator else None,
                historical=historical is not None,
            )
        )
    advance, main, bonus, curator_stage = result
    if body.contract_status == "not_signed":
        status_label = "Договор не заключён"
    elif body.contract_date is None:
        status_label = "Договор подписан — уточните дату"
    elif advance["status"] == "waiting":
        status_label = "Ждём поступления от 8 000 ₽"
    elif advance["status"] == "ready":
        status_label = "Ожидает выплаты аванса"
    elif not body.deposit_paid_on:
        status_label = "Ждём оплаты депозита клиентом"
    elif any(row["status"] == "ready" for row in result):
        status_label = (
            "Ожидает основной выплаты"
            if main["status"] == "ready" or bonus["status"] == "ready"
            else "Ожидает выплаты куратору"
        )
    elif any(row["status"] == "rejected" for row in result):
        status_label = "Есть отклонённые начисления"
    else:
        status_label = "Всё выплачено"
    return dict(
        version=data["version"],
        input=data["input"],
        stages=result,
        status_label=status_label,
        outstanding=str(outstanding),
        next_due_on=min(
            (row["due_on"] for row in result if row["status"] == "ready" and row["due_on"]),
            default=None,
        ),
        curator_name=(curator.display_name or f"Куратор #{curator.id}") if curator else None,
        curator_id=data.get("curator_id"),
        curator_phone=curator.phone_normalized if curator else None,
    )
