from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pravburo_ref_common.models import Agent, AgentRole

from src.core.auth import authenticate
from src.core.security import hash_password


@pytest.mark.parametrize(
    "identifier", ["+79991112233", "89991112233", "9991112233", "8 (999) 111-22-33"]
)
async def test_phone_login_uses_normalized_phone_and_password(identifier):
    agent = Agent(id=7, email=None, phone_normalized="+79991112233", role=AgentRole.AGENT)
    session = SimpleNamespace(execute=AsyncMock(return_value=Mock()))
    session.execute.return_value.one_or_none.return_value = (agent, hash_password("secret1"))
    assert await authenticate(session, identifier, "secret1") is agent
    statement = session.execute.call_args.args[0]
    assert statement.compile().params == {"phone_normalized_1": "+79991112233"}
    assert await authenticate(session, identifier, "wrong-password") is None


async def test_email_login_is_preserved():
    agent = Agent(id=7, email="agent@example.test", role=AgentRole.AGENT)
    session = SimpleNamespace(execute=AsyncMock(return_value=Mock()))
    session.execute.return_value.one_or_none.return_value = (agent, hash_password("secret1"))
    assert await authenticate(session, " Agent@Example.test ", "secret1") is agent
    assert session.execute.call_args.args[0].compile().params == {"email_1": "agent@example.test"}


@pytest.mark.parametrize("identifier", ["", "123", "unknown", "letters79991112233", "----"])
async def test_invalid_phone_cannot_be_used_to_find_an_account(identifier):
    session = SimpleNamespace(execute=AsyncMock(return_value=Mock()))
    assert await authenticate(session, identifier, "secret1") is None
    session.execute.assert_not_called()


async def test_unknown_phone_does_not_log_in():
    session = SimpleNamespace(execute=AsyncMock(return_value=Mock()))
    session.execute.return_value.one_or_none.return_value = None
    assert await authenticate(session, "+79991112233", "secret1") is None
