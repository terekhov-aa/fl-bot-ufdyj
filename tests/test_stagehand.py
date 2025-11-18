import pytest
from fastapi.testclient import TestClient

from app.services import stagehand_client


@pytest.fixture(autouse=True)
def clear_settings_cache():
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_parse_site_success(client: TestClient, monkeypatch):
    async def fake_parse_site(url: str, **kwargs):
        assert url == "https://example.com"
        assert kwargs["instruction"] == "extract"
        return {"result": {"title": "Example"}}

    monkeypatch.setattr(stagehand_client, "parse_site", fake_parse_site)

    response = client.post(
        "/api/parse-site",
        json={"url": "https://example.com", "instruction": "extract"},
    )

    assert response.status_code == 200
    assert response.json() == {"result": {"title": "Example"}}


def test_parse_site_invalid_url(client: TestClient):
    response = client.post("/api/parse-site", json={"url": "notaurl"})
    assert response.status_code == 400
    assert response.json()["detail"] == "A valid http(s) URL is required"


def test_parse_site_stagehand_error(client: TestClient, monkeypatch):
    async def fake_parse_site(url: str, **kwargs):
        raise stagehand_client.StagehandServiceError("bad gateway")

    monkeypatch.setattr(stagehand_client, "parse_site", fake_parse_site)

    response = client.post("/api/parse-site", json={"url": "https://example.com"})
    assert response.status_code == 502
    assert response.json()["detail"] == "bad gateway"
