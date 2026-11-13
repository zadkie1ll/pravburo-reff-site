import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pravburo_ref_common.models import AgentCredential, EmploymentFormat

from src.core.security import verify_password
from src.services import admin_partners


def test_generated_password_has_exactly_eight_ascii_letters_and_digits():
    passwords = {admin_partners.generate_partner_password() for _ in range(100)}
    assert len(passwords) == 100
    for password in passwords:
        assert re.fullmatch(r"[A-Za-z0-9]{8}", password)
        assert any(c.islower() for c in password)
        assert any(c.isupper() for c in password)
        assert any(c.isdigit() for c in password)


@pytest.mark.parametrize("note", ["", "Позвонить вечером", "а" * 1983])
async def test_created_partner_can_log_in_using_the_password_in_admin_notes(monkeypatch, note):
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=None),
        add=Mock(),
        flush=AsyncMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
        execute=AsyncMock(),
    )
    monkeypatch.setattr(admin_partners, "link_agent_to_referrer", AsyncMock())
    data = admin_partners.PartnerInput(
        display_name="Партнёр",
        phone="89991112233",
        employment_format=EmploymentFormat.INDIVIDUAL,
        payout_details="Карта 2200",
        inn="",
        admin_note=note,
    )
    agent = await admin_partners.create_partner(session, 1, None, data)
    password = agent.admin_note.rsplit("Пароль: ", 1)[1]
    assert agent.admin_note == (note + "\n" if note else "") + f"Пароль: {password}"
    assert len(agent.admin_note) <= 2000
    assert agent.email is None
    assert agent.phone_normalized == "+79991112233"
    credential = next(
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], AgentCredential)
    )
    assert verify_password(password, credential.password_hash)
    assert password != credential.password_hash
    session.commit.assert_awaited_once()
