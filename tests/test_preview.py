from fastapi.testclient import TestClient

from src.core.config import get_settings

PREVIEW_TOKEN = "preview-demo-token"
DUMMY_REFERRAL_CODE = "00000000-0000-4000-8000-000000000001"


def enable_preview(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ui_preview_enabled", True)
    monkeypatch.setattr(settings, "ui_preview_token", PREVIEW_TOKEN)


def test_preview_is_hidden_when_disabled(client: TestClient) -> None:
    response = client.get(f"/preview?token={PREVIEW_TOKEN}")

    assert response.status_code == 404


def test_preview_rejects_wrong_token(client: TestClient, monkeypatch) -> None:
    enable_preview(monkeypatch)

    response = client.get("/preview?token=wrong-token")

    assert response.status_code == 404


def test_all_preview_pages_render(client: TestClient, monkeypatch) -> None:
    enable_preview(monkeypatch)
    pages = [
        "home",
        "login",
        "register",
        "confirm",
        "reset",
        "reset-confirm",
        "cabinet",
        "success",
        "client",
        "not-found",
    ]
    urls = [f"/preview?token={PREVIEW_TOKEN}"]
    urls.extend(f"/preview/page/{page}?token={PREVIEW_TOKEN}" for page in pages)
    urls.append(f"/preview/referral/{DUMMY_REFERRAL_CODE}?token={PREVIEW_TOKEN}")

    for url in urls:
        response = client.get(url)
        assert response.status_code == 200, url
        assert "Режим предпросмотра" in response.text, url


def test_preview_qr_renders(client: TestClient, monkeypatch) -> None:
    enable_preview(monkeypatch)

    response = client.get(f"/preview/qr.png?token={PREVIEW_TOKEN}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")
