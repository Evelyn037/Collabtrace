import json

import httpx
import pytest

from app.config import load_settings
from app.github.client import GitHubClient
from app.github.service import GitHubService
from app.routes.github import auth_status, build_probe_warnings, save_probe_result


def test_empty_token_is_not_configured(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("GITHUB_TOKEN=\n", encoding="utf-8")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert load_settings(env_file).github_token is None


def test_non_empty_token_is_loaded(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("GITHUB_TOKEN=test_token\n", encoding="utf-8")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert load_settings(env_file).github_token == "test_token"


@pytest.mark.asyncio
async def test_client_adds_bearer_header_without_leaking_token():
    seen_authorization = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_authorization
        seen_authorization = request.headers.get("Authorization")
        return httpx.Response(
            200,
            json={"resources": {"core": {"limit": 5000, "remaining": 4999, "reset": 1}}},
            headers={"X-RateLimit-Limit": "5000", "X-RateLimit-Remaining": "4999", "X-RateLimit-Reset": "1"},
        )

    token = "test_token"
    async with GitHubClient(token=token, transport=httpx.MockTransport(handler)) as client:
        result = await auth_status(GitHubService(client))

    assert seen_authorization == "Bearer test_token"
    assert result["token_configured"] is True
    assert result["authentication_mode"] == "token"
    assert token not in json.dumps(result)


@pytest.mark.asyncio
async def test_empty_token_omits_authorization_header():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" not in request.headers
        return httpx.Response(200, json=[])

    async with GitHubClient(token="  ", transport=httpx.MockTransport(handler)) as client:
        await client.get("/anything")
        assert client.token_configured is False


@pytest.mark.asyncio
async def test_pagination_fetches_second_page_and_reports_truncation():
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        if page == 1:
            return httpx.Response(
                200,
                json=[{"id": value} for value in range(100)],
                headers={"Link": '<https://api.github.com/items?page=2>; rel="next"'},
            )
        return httpx.Response(200, json=[{"id": 100}])

    transport = httpx.MockTransport(handler)
    async with GitHubClient(transport=transport) as client:
        first_page = await client.get_paginated("/items", max_pages=1)
        assert len(first_page) == 100
        assert client.pagination_status("/items").possibly_truncated is True

        two_pages = await client.get_paginated("/items", max_pages=2)
        assert len(two_pages) == 101
        assert client.pagination_status("/items").possibly_truncated is False


def test_probe_serialization_is_valid_and_contains_no_secret(tmp_path):
    token = "test_token"
    output = tmp_path / "data" / "last_probe.json"
    result = {
        "repository": {"full_name": "o/r", "url": "https://github.com/o/r"},
        "summary": {"commits": 1, "pull_requests": 0, "issues": 0, "reviews": 0, "total_events": 1},
        "rate_limit": {"limit": 5000, "remaining": 4999, "reset": 1},
        "warnings": [],
        "samples": {"commits": [], "pull_requests": [], "issues": [], "reviews": []},
    }
    save_probe_result(result, output)
    text = output.read_text(encoding="utf-8")
    assert json.loads(text)["repository"]["full_name"] == "o/r"
    assert token not in text
    assert "Authorization" not in text


def test_probe_warns_for_low_rate_limit_and_truncation():
    warnings = build_probe_warnings(9, True)
    assert any("rate limit remaining is low" in warning for warning in warnings)
    assert any("may be truncated" in warning for warning in warnings)
