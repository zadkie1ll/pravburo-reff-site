"""Transactional local deletion with a review snapshot and paid-ledger protection."""

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from typing import Literal

from pravburo_ref_common.models import (
    Agent,
    AgentRole,
    ExistingClientImport,
    PartnerLevelMonth,
    PendingRegistration,
    PushSubscription,
    ReferralApplication,
    ReferralLinkVisit,
    Reward,
)
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
Kind = Literal["partners", "clients"]


@dataclass
class DeletionPlan:
    kind: Kind
    target: Agent | ReferralApplication
    applications: list
    imports: list
    rewards: list
    children: list
    external_imports: list
    blocked_reason: str | None
    token: str

    def preview(self):
        return dict(
            kind=self.kind,
            id=self.target.id,
            name=self.target.display_name if self.kind == "partners" else self.target.full_name,
            phone=self.target.phone_normalized,
            email=self.target.email if self.kind == "partners" else None,
            client_count=len(self.applications),
            reward_count=len(self.rewards),
            invited_partner_count=len(self.children),
            curator_client_count=len(self.external_imports),
            can_delete=self.blocked_reason is None,
            blocked_reason=self.blocked_reason,
            token=self.token,
        )


async def _rows(session, statement, lock):
    if lock:
        statement = statement.with_for_update()
    return list(await session.scalars(statement.execution_options(populate_existing=True)))


def _state(rows):
    return [
        {attr.key: getattr(row, attr.key) for attr in row.__mapper__.column_attrs} for row in rows
    ]


def _history_paid(record, curator_only=False):
    data = (record.workflow_data or {}).get("input", {})
    keys = (
        ("curator_paid_on",)
        if curator_only
        else ("advance_paid_on", "main_paid_on", "curator_paid_on")
    )
    return any(data.get(key) for key in keys)


async def deletion_plan(session: AsyncSession, kind: Kind, target_id: int, *, lock=False):
    model = Agent if kind == "partners" else ReferralApplication
    targets = await _rows(
        session, select(model).where(model.id == target_id), lock and kind == "partners"
    )
    if not targets:
        raise LookupError("Партнёр не найден" if kind == "partners" else "Клиент не найден")
    target = targets[0]
    blocked = (
        "Аккаунт администратора удалить нельзя"
        if kind == "partners" and target.role != AgentRole.AGENT
        else None
    )
    owned = (
        ReferralApplication.agent_id == target_id
        if kind == "partners"
        else ReferralApplication.id == target_id
    )
    # Workflow writers lock imports first. Follow that order before locking applications.
    imports = await _rows(
        session,
        select(ExistingClientImport)
        .where(ExistingClientImport.application_id.in_(select(ReferralApplication.id).where(owned)))
        .order_by(ExistingClientImport.application_id),
        lock,
    )
    applications = await _rows(
        session, select(ReferralApplication).where(owned).order_by(ReferralApplication.id), lock
    )
    if kind == "clients" and not applications:
        raise LookupError("Клиент уже удалён")
    app_ids = [row.id for row in applications]
    root = Reward.application_id.in_(app_ids)
    if kind == "partners":
        root = or_(root, Reward.agent_id == target_id)
    cascade = select(Reward.id).where(root).cte("deletion_rewards", recursive=True)
    cascade = cascade.union(
        select(Reward.id).join(cascade, Reward.source_reward_id == cascade.c.id)
    )
    rewards = await _rows(
        session, select(Reward).where(Reward.id.in_(select(cascade.c.id))).order_by(Reward.id), lock
    )
    reward_ids = {row.id for row in rewards}
    children = []
    external_imports = []
    if kind == "partners":
        children = await _rows(
            session,
            select(Agent).where(Agent.invited_by_agent_id == target_id).order_by(Agent.id),
            lock,
        )
        external_imports = await _rows(
            session,
            select(ExistingClientImport)
            .where(
                ExistingClientImport.application_id.not_in(app_ids),
                ExistingClientImport.workflow_data["curator_id"].as_integer() == target_id,
            )
            .order_by(ExistingClientImport.application_id),
            lock,
        )
        author_reference = await session.scalar(
            select(ExistingClientImport.application_id)
            .where(
                ExistingClientImport.application_id.not_in(app_ids),
                ExistingClientImport.imported_by_agent_id == target_id,
            )
            .limit(1)
        )
        if author_reference is not None:
            blocked = (
                blocked or "Партнёр указан автором переноса других клиентов. Удаление недоступно"
            )
    if (
        any(row.paid_at is not None for row in rewards)
        or any(_history_paid(row) for row in imports)
        or any(_history_paid(row, True) for row in external_imports)
    ):
        blocked = blocked or "Есть отмеченные выплаты или история до переноса. Удаление недоступно"
    if any(
        row.application_id not in app_ids and (kind != "partners" or row.agent_id != target_id)
        for row in rewards
    ):
        blocked = blocked or "Начисления связаны с другими клиентами. Удаление недоступно"
    external_refs = await session.scalar(
        select(ExistingClientImport.application_id)
        .where(
            ExistingClientImport.application_id.not_in(app_ids),
            ExistingClientImport.current_reward_id.in_(reward_ids),
        )
        .limit(1)
    )
    if external_refs is not None:
        blocked = blocked or "Начисление используется другим клиентом. Удаление недоступно"
    # Check JSON links as well as SQL foreign keys. Only a curator's own unpaid
    # line on another client's settlement may be removed with their account.
    all_external = (
        list(
            await session.scalars(
                select(ExistingClientImport).where(
                    ExistingClientImport.application_id.not_in(app_ids),
                    ExistingClientImport.workflow_data.is_not(None),
                )
            )
        )
        if reward_ids
        else []
    )
    for record in all_external:
        data = record.workflow_data or {}
        for key, reward_id in data.get("reward_ids", {}).items():
            if reward_id in reward_ids and not (
                kind == "partners" and data.get("curator_id") == target_id and key == "curator"
            ):
                blocked = (
                    blocked
                    or "Начисление используется в выплатах другого клиента. Удаление недоступно"
                )
    # Never return secrets/PII in the snapshot itself; the browser gets only its digest.
    snapshot = dict(
        kind=kind,
        target=_state([target]),
        apps=_state(applications),
        imports=_state(imports),
        rewards=_state(rewards),
        children=_state(children),
        external=_state(external_imports),
    )
    token = hashlib.sha256(json.dumps(snapshot, sort_keys=True, default=str).encode()).hexdigest()
    return DeletionPlan(
        kind, target, applications, imports, rewards, children, external_imports, blocked, token
    )


async def delete_record(
    session: AsyncSession, kind: Kind, target_id: int, token: str, admin_id: int
):
    plan = await deletion_plan(session, kind, target_id, lock=True)
    if plan.blocked_reason:
        raise ValueError(plan.blocked_reason)
    if not hmac.compare_digest(token, plan.token):
        raise ValueError("Данные изменились после открытия подтверждения. Проверьте список заново")
    app_ids = [row.id for row in plan.applications]
    reward_ids = [row.id for row in plan.rewards]
    for record in plan.external_imports:
        data = record.workflow_data
        record.workflow_data = {
            **data,
            "version": data.get("version", 0) + 1,
            "curator_id": None,
            "input": {**data["input"], "curator_amount": "0", "curator_paid_on": None},
            "reward_ids": {
                key: value for key, value in data.get("reward_ids", {}).items() if key != "curator"
            },
        }
    await session.flush()
    await session.execute(
        delete(ExistingClientImport).where(ExistingClientImport.application_id.in_(app_ids))
    )
    # Delete the complete dependency set in one statement, including network rewards.
    await session.execute(delete(Reward).where(Reward.id.in_(reward_ids)))
    await session.execute(delete(ReferralApplication).where(ReferralApplication.id.in_(app_ids)))
    if kind == "partners":
        await session.execute(
            update(Agent)
            .where(Agent.invited_by_agent_id == target_id)
            .values(invited_by_agent_id=None)
        )
        await session.execute(
            update(ReferralApplication)
            .where(ReferralApplication.assigned_manager_id == target_id)
            .values(assigned_manager_id=None)
        )
        await session.execute(
            update(Reward)
            .where(Reward.decided_by_agent_id == target_id)
            .values(decided_by_agent_id=None)
        )
        for model in (PartnerLevelMonth, PushSubscription, ReferralLinkVisit):
            await session.execute(delete(model).where(model.agent_id == target_id))
        if plan.target.email:
            await session.execute(
                delete(PendingRegistration).where(PendingRegistration.email == plan.target.email)
            )
        # Credentials, identities and reset tokens have ON DELETE CASCADE.
        await session.execute(delete(Agent).where(Agent.id == target_id))
    await session.commit()
    logger.info(
        "Admin deleted local record: admin_id=%s kind=%s id=%s clients=%s rewards=%s",
        admin_id,
        kind,
        target_id,
        len(app_ids),
        len(reward_ids),
    )
