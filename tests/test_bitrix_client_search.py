import httpx
import pytest
from pravburo_ref_common.models import Agent, AgentRole

from src.core.config import get_settings
from src.main import app
from src.services.bitrix_links import entity_link, parse_deal_reference
from src.site.crm_client import CRMClient
from src.web.dependencies import optional_agent
from src.web.routes.api_admin_clients import ImportRequest


@pytest.fixture(autouse=True)
def configured_portal(monkeypatch):
    monkeypatch.setattr(
        get_settings(),
        "bitrix_lead_url_template",
        "https://portal.example.test/crm/lead/details/{lead_id}/",
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("123", "123"),
        (" 00123 ", "123"),
        ("https://portal.example.test/crm/deal/details/123/", "123"),
        ("https://portal.example.test/crm/deal/details/123?tab=main#details", "123"),
    ],
)
def test_accept_id_or_our_portal_deal_link(value, expected):
    assert parse_deal_reference(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "0",
        "-1",
        "javascript:alert(1)",
        "https://evil.example/crm/deal/details/123/",
        "https://portal.example.test.evil.example/crm/deal/details/123/",
        "https://user:pass@portal.example.test/crm/deal/details/123/",
        "https://portal.example.test:9443/crm/deal/details/123/",
        "https://portal.example.test/crm/lead/details/123/",
        "https://portal.example.test/rest/token/crm.deal.get.json",
    ],
)
def test_reject_untrusted_urls_and_other_entity_types(value):
    with pytest.raises(ValueError):
        parse_deal_reference(value)


def test_import_body_uses_numeric_deal_id():
    body = ImportRequest(
        agent_id=1,
        deal_id="https://portal.example.test/crm/deal/details/123/",
        full_name="Иван",
        phone="+79990001122",
    )
    assert body.deal_id == "123"


@pytest.fixture
def admin():
    app.dependency_overrides[optional_agent] = lambda: Agent(
        id=1, role=AgentRole.ADMIN, is_active=True
    )
    yield
    app.dependency_overrides.pop(optional_agent, None)


def test_search_proxies_query_and_rebuilds_safe_links(client, admin, monkeypatch):
    async def search(self, query, page):
        assert (query, page) == ("Иванов Иван", 2)
        return {
            "page": 2,
            "has_more": True,
            "rows": [
                {
                    "kind": "deal",
                    "id": "10",
                    "full_name": "Иванов Иван",
                    "category_id": 0,
                    "category_label": "Основная",
                    "url": "https://secret.invalid/rest/token",
                },
                {
                    "kind": "deal",
                    "id": "11",
                    "full_name": "Иванов Иван",
                    "category_id": 2,
                    "category_label": "Сопровождение",
                },
                {"kind": "lead", "id": "12", "full_name": "Иванов Иван"},
            ],
        }

    monkeypatch.setattr(CRMClient, "search_existing_clients", search)
    response = client.get(
        "/api/v1/site/admin/clients/search", params={"q": "  Иванов   Иван ", "page": 2}
    )
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert len(rows) == 3
    assert rows[0]["url"] == entity_link("deal", "10")
    assert rows[2]["url"] == entity_link("lead", "12")
    assert "secret.invalid" not in response.text
    assert response.json()["has_more"] is True


def test_link_preview_reads_only_extracted_id(client, admin, monkeypatch):
    async def existing(self, deal_id):
        assert deal_id == "123"
        return {"deal_id": "123", "stage_code": "C2:NEW", "full_name": "Иван"}

    monkeypatch.setattr(CRMClient, "get_existing_client", existing)
    response = client.get(
        "/api/v1/site/admin/clients/deals/preview",
        params={"deal": "https://portal.example.test/crm/deal/details/123/"},
    )
    assert response.status_code == 200
    assert response.json()["deal_url"] == entity_link("deal", "123")


def test_bad_link_does_not_call_crm(client, admin, monkeypatch):
    async def forbidden(*args):
        raise AssertionError("Untrusted link must not be sent to CRM")

    monkeypatch.setattr(CRMClient, "get_existing_client", forbidden)
    response = client.get(
        "/api/v1/site/admin/clients/deals/preview",
        params={"deal": "https://evil.example/crm/deal/details/123/"},
    )
    assert response.status_code == 400


def test_search_errors_are_sanitized(client, admin, monkeypatch):
    async def error(*args):
        raise httpx.ConnectError("secret token")

    monkeypatch.setattr(CRMClient, "search_existing_clients", error)
    response = client.get("/api/v1/site/admin/clients/search", params={"q": "Иванов"})
    assert response.status_code == 502
    assert "secret token" not in response.text


def test_search_requires_admin(client):
    app.dependency_overrides[optional_agent] = lambda: None
    try:
        assert (
            client.get("/api/v1/site/admin/clients/search", params={"q": "Иванов"}).status_code
            == 401
        )
    finally:
        app.dependency_overrides.pop(optional_agent, None)
