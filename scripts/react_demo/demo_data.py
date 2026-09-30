"""Demo data for checking the React frontend by hand (throw-away database only).

    python demo_data.py seed          fill an empty database
    python demo_data.py code EMAIL    print the current 2FA code of an admin (local checks only)

All accounts share one password, PASSWORD below. Never point this at a real database.
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pravburo_ref_common.database import close_database, session_factory
from pravburo_ref_common.models import (
    Agent,
    AgentCredential,
    AgentRole,
    DeliveryStatus,
    EmploymentFormat,
    ReferralApplication,
    ReferralLinkVisit,
    Reward,
    RewardStatus,
    RewardType,
)
from sqlalchemy import select

from src.core.security import hash_password
from src.core.totp import totp_now

PASSWORD = "demo12345"
# Fixed on purpose: with it `code admin@demo.test` can produce the current 2FA code.
ADMIN_2FA_SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
NOW = datetime.now(UTC)


def _phone() -> str:
    return f"+7999{uuid.uuid4().int % 10**7:07d}"


async def seed() -> None:
    async with session_factory() as session:
        if await session.scalar(select(Agent.id).where(Agent.email == "olga@demo.test")):
            print("Данные уже есть, пропускаю (база не пустая).")
            return

        def agent(email: str, name: str, **fields) -> Agent:
            fields.setdefault("is_active", True)
            fields.setdefault("employment_format", EmploymentFormat.SELF_EMPLOYED)
            row = Agent(email=email, display_name=name, **fields)
            session.add(row)
            return row

        admin = agent(
            "admin@demo.test",
            "Админ (2FA включена)",
            role=AgentRole.ADMIN,
            employment_format=None,
            totp_secret=ADMIN_2FA_SECRET,
            totp_enabled=True,
        )
        admin_new = agent(
            "admin-new@demo.test",
            "Админ (2FA не настроена)",
            role=AgentRole.ADMIN,
            employment_format=None,
        )
        olga = agent(
            "olga@demo.test",
            "Ольга Партнёрова",
            phone_normalized="+79990001122",
            payout_details="Карта 4276 0000 1111 2222",
            inn="616706684677",
        )
        newbie = agent(
            "newbie@demo.test", "Новичок (без формата сотрудничества)", employment_format=None
        )
        blocked = agent(
            "blocked@demo.test",
            "Заблокированный Партнёр",
            is_active=False,
            blocked_reason="Нарушение правил программы",
        )
        others = [agent(f"partner{i:02d}@demo.test", f"Партнёр Номер{i:02d}") for i in range(1, 29)]
        await session.flush()

        for row in (admin, admin_new, olga, newbie, blocked, *others):
            session.add(AgentCredential(agent_id=row.id, password_hash=hash_password(PASSWORD)))

        # A network under Olga: 01, 02, 03 -> 04, 05 (blocked) under 01 -> 06 under 04.
        by = {a.email: a for a in others}
        for child in ("partner01", "partner02", "partner03"):
            by[f"{child}@demo.test"].invited_by_agent_id = olga.id
        for child in ("partner04", "partner05"):
            by[f"{child}@demo.test"].invited_by_agent_id = by["partner01@demo.test"].id
        by["partner05@demo.test"].is_active = False
        by["partner06@demo.test"].invited_by_agent_id = by["partner04@demo.test"].id

        for _ in range(12):
            session.add(ReferralLinkVisit(agent_id=olga.id))

        # Olga's clients, one per payout state.
        def client(name: str, stage: str | None = None) -> ReferralApplication:
            row = ReferralApplication(
                agent_id=olga.id,
                full_name=name,
                phone_normalized=_phone(),
                city="Казань",
                deal_stage_code=stage,
            )
            session.add(row)
            return row

        paid = client("Иван Оплатов")
        scheduled = client("Мария Запланирова")
        overdue = client("Пётр Опоздалов")
        pending = client("Анна Ожидающая")
        rejected = client("Олег Отказов")
        client("Сергей Новичков")
        client("Денис Депозитов", "UC_4FX5NE")
        client("Игорь Пропавший", "UC_1BEALQ")
        await session.flush()

        def reward(application, **fields) -> None:
            session.add(
                Reward(
                    deal_id=str(uuid.uuid4()),
                    application_id=application.id,
                    agent_id=olga.id,
                    reward_type=RewardType.ADVANCE,
                    amount=Decimal(3000),
                    **fields,
                )
            )

        reward(paid, status=RewardStatus.APPROVED, decided_at=NOW - timedelta(days=5), paid_at=NOW)
        reward(scheduled, status=RewardStatus.APPROVED, decided_at=NOW - timedelta(days=1))
        reward(overdue, status=RewardStatus.APPROVED, decided_at=NOW - timedelta(days=30))
        reward(pending, status=RewardStatus.PENDING)
        reward(
            rejected, status=RewardStatus.REJECTED, rejection_reason="Клиент отказался от договора"
        )

        # Applications of other partners, for the admin's list (25 per page -> two pages).
        for i in range(30):
            owner = others[i % 10]
            session.add(
                ReferralApplication(
                    agent_id=owner.id,
                    full_name=f"Клиент Заявкин{i:02d}",
                    phone_normalized=_phone(),
                    city="Москва" if i % 2 else None,
                    delivery_status=DeliveryStatus.FAILED if i % 3 == 0 else DeliveryStatus.SENT,
                    delivery_error="ConnectionError" if i % 3 == 0 else None,
                )
            )

        await session.commit()
        code = str(olga.referral_code)
    print(f"Готово. Реферальный код Ольги: {code}")


async def print_code(email: str) -> None:
    async with session_factory() as session:
        row = await session.scalar(select(Agent).where(Agent.email == email))
    if row is None or not row.totp_secret:
        print("У этого админа нет секрета 2FA (ещё не настроена).")
    else:
        print(totp_now(row.totp_secret))


async def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if command == "seed":
            await seed()
        elif command == "code" and len(sys.argv) > 2:
            await print_code(sys.argv[2])
        else:
            print(__doc__)
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
