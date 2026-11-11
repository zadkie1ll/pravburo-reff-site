import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.config import get_settings
from src.web.routes.dev_bounty import router


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/admin/rewards?status=pending"),
        ("POST", "/admin/rewards/1/decide"),
        ("GET", "/admin/static/app.css"),
        ("GET", "/admin/reward-rates"),
        ("GET", "/admin/partner-levels"),
    ],
)
def test_local_bounty_routes_forward_requests(monkeypatch, method, path):
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "dev_bounty_port", 8051)
    original = httpx.AsyncClient

    def upstream(request):
        assert request.url.port == 8051
        assert request.headers["host"] == "testserver"
        assert request.headers["cookie"] == "session=demo"
        assert request.content == b"decision=reject&reason=test"
        return httpx.Response(
            303, headers={"location": "/admin/rewards", "set-cookie": "session=updated"}
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(upstream), **kwargs),
    )
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        response = client.request(
            method,
            path,
            content=b"decision=reject&reason=test",
            headers={"Cookie": "session=demo"},
            follow_redirects=False,
        )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/rewards"
    assert response.headers["set-cookie"] == "session=updated"


def test_local_proxy_is_disabled_in_production(monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "production")
    monkeypatch.setattr(get_settings(), "dev_bounty_port", 8051)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        assert client.get("/admin/rewards").status_code == 404
