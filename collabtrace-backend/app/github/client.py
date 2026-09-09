from __future__ import annotations

from dataclasses import dataclass
import os
import ssl
from typing import Any

import certifi
import httpx


@dataclass(slots=True)
class RateLimitInfo:
    limit: int | None = None
    remaining: int | None = None
    reset: int | None = None

    def model_dump(self) -> dict[str, int | None]:
        return {"limit": self.limit, "remaining": self.remaining, "reset": self.reset}


@dataclass(slots=True)
class PaginationInfo:
    pages_fetched: int = 0
    possibly_truncated: bool = False


class GitHubAPIError(Exception):
    def __init__(self, status_code: int, message: str, rate_limit: RateLimitInfo | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.rate_limit = rate_limit


class GitHubClient:
    def __init__(
        self,
        token: str | None = None,
        base_url: str = "https://api.github.com",
        timeout: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        token = (token or "").strip() or None
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "CollabTrace-GitHub-PoC",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        # Some managed environments set SSLKEYLOGFILE to an unwritable location.
        # It is only a TLS debugging aid, so ignore it while creating the verified context.
        keylog_file = os.environ.pop("SSLKEYLOGFILE", None)
        try:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
        finally:
            if keylog_file is not None:
                os.environ["SSLKEYLOGFILE"] = keylog_file
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=timeout,
            verify=ssl_context,
            transport=transport,
        )
        self.token_configured = token is not None
        self.rate_limit = RateLimitInfo()
        self.pagination: dict[str, PaginationInfo] = {}

    async def __aenter__(self) -> GitHubClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    def get_rate_limit(self) -> dict[str, int | None]:
        return self.rate_limit.model_dump()

    def pagination_status(self, path: str) -> PaginationInfo:
        return self.pagination.get(path, PaginationInfo())

    def any_pagination_truncated(self, path_prefix: str) -> bool:
        return any(
            info.possibly_truncated
            for path, info in self.pagination.items()
            if path.startswith(path_prefix)
        )

    def _update_rate_limit(self, response: httpx.Response) -> None:
        def as_int(name: str) -> int | None:
            value = response.headers.get(name)
            try:
                return int(value) if value is not None else None
            except ValueError:
                return None

        self.rate_limit = RateLimitInfo(
            limit=as_int("X-RateLimit-Limit"),
            remaining=as_int("X-RateLimit-Remaining"),
            reset=as_int("X-RateLimit-Reset"),
        )

    async def get_response(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        try:
            response = await self._client.get(path, params=params)
        except httpx.TimeoutException as exc:
            raise GitHubAPIError(504, "GitHub API request timed out", self.rate_limit) from exc
        except httpx.RequestError as exc:
            raise GitHubAPIError(502, "Unable to reach GitHub API", self.rate_limit) from exc

        self._update_rate_limit(response)
        if response.is_error:
            self._raise_api_error(response)
        return response

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = await self.get_response(path, params)
        try:
            return response.json()
        except ValueError as exc:
            raise GitHubAPIError(502, "GitHub API returned invalid JSON", self.rate_limit) from exc

    async def get_paginated(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        max_pages: int | None = 10,
    ) -> list[dict[str, Any]]:
        query = dict(params or {})
        query["per_page"] = 100
        page = 1
        results: list[dict[str, Any]] = []
        possibly_truncated = False

        while max_pages is None or page <= max_pages:
            query["page"] = page
            response = await self.get_response(path, query)
            try:
                payload = response.json()
            except ValueError as exc:
                raise GitHubAPIError(502, "GitHub API returned invalid JSON", self.rate_limit) from exc
            if not isinstance(payload, list):
                raise GitHubAPIError(502, "GitHub API returned an unexpected response", self.rate_limit)
            results.extend(item for item in payload if isinstance(item, dict))
            has_next = 'rel="next"' in response.headers.get("Link", "")
            if not payload or len(payload) < 100 or not has_next:
                break
            if max_pages is not None and page >= max_pages:
                possibly_truncated = True
                break
            if self.rate_limit.remaining is not None and self.rate_limit.remaining <= 1:
                raise GitHubAPIError(403, "GitHub API rate limit is nearly exhausted", self.rate_limit)
            page += 1
        self.pagination[path] = PaginationInfo(
            pages_fetched=page, possibly_truncated=possibly_truncated
        )
        return results

    def _raise_api_error(self, response: httpx.Response) -> None:
        try:
            github_message = response.json().get("message", "")
        except (ValueError, AttributeError):
            github_message = ""
        if response.status_code == 401:
            message = "GitHub authentication failed"
        elif response.status_code == 404:
            message = "Repository not found"
        elif response.status_code == 403:
            message = "Permission denied or GitHub API rate limit exceeded"
        else:
            message = github_message or f"GitHub API error ({response.status_code})"
        raise GitHubAPIError(response.status_code, message, self.rate_limit)
