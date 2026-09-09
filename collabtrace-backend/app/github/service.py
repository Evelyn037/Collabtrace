from __future__ import annotations

import asyncio
from typing import Any

from app.github.client import GitHubAPIError, GitHubClient
from app.github.normalizer import normalize_commit, normalize_issue, normalize_pull_request, normalize_review
from app.models.contribution import ContributionEvent
from app.services.contribution_index_service import build_commit_metric_metadata


class GitHubService:
    def __init__(self, client: GitHubClient, max_pages: int | None = 10, max_prs_for_reviews: int | None = 50):
        self.client = client
        self.max_pages = max_pages
        self.max_prs_for_reviews = max_prs_for_reviews
        self.reviews_limited_by_pr_count = False

    async def get_repository_info(self, owner: str, repo: str) -> dict[str, Any]:
        raw = await self.client.get(f"/repos/{owner}/{repo}")
        return {
            "id": raw.get("id"), "name": raw.get("name"), "full_name": raw.get("full_name"),
            "owner_login": (raw.get("owner") or {}).get("login"), "html_url": raw.get("html_url"),
            "description": raw.get("description"), "default_branch": raw.get("default_branch"),
            "private": raw.get("private"), "created_at": raw.get("created_at"), "updated_at": raw.get("updated_at"),
        }

    async def get_commits(self, owner: str, repo: str) -> list[ContributionEvent]:
        raw = await self.client.get_paginated(f"/repos/{owner}/{repo}/commits", max_pages=self.max_pages)
        events: list[ContributionEvent] = []
        for item in raw:
            metric_metadata = None
            remaining = self.client.rate_limit.remaining
            if remaining is None or remaining > 1:
                try:
                    detail = await self.client.get(f"/repos/{owner}/{repo}/commits/{item.get('sha')}")
                    metric_metadata = build_commit_metric_metadata(detail if isinstance(detail, dict) else None)
                except GitHubAPIError:
                    metric_metadata = build_commit_metric_metadata(None)
            else:
                metric_metadata = build_commit_metric_metadata(None)
            events.append(normalize_commit(item, f"{owner}/{repo}", metric_metadata))
        return events

    async def get_pull_requests(self, owner: str, repo: str) -> list[ContributionEvent]:
        raw = await self._get_raw_pull_requests(owner, repo)
        return [normalize_pull_request(item, f"{owner}/{repo}") for item in raw]

    async def _get_raw_pull_requests(self, owner: str, repo: str) -> list[dict[str, Any]]:
        return await self.client.get_paginated(
            f"/repos/{owner}/{repo}/pulls", {"state": "all", "sort": "updated", "direction": "desc"}, self.max_pages
        )

    async def get_issues(self, owner: str, repo: str) -> list[ContributionEvent]:
        raw = await self.client.get_paginated(f"/repos/{owner}/{repo}/issues", {"state": "all"}, self.max_pages)
        events = [normalize_issue(item, f"{owner}/{repo}") for item in raw]
        return [event for event in events if event is not None]

    async def get_reviews(self, owner: str, repo: str, pull_requests: list[dict[str, Any]] | None = None) -> list[ContributionEvent]:
        pulls = pull_requests if pull_requests is not None else await self._get_raw_pull_requests(owner, repo)
        selected = pulls if self.max_prs_for_reviews is None else pulls[: self.max_prs_for_reviews]
        self.reviews_limited_by_pr_count = len(selected) < len(pulls)

        async def reviews_for_pr(pull: dict[str, Any]) -> list[ContributionEvent]:
            number = int(pull["number"])
            raw_reviews = await self.client.get_paginated(
                f"/repos/{owner}/{repo}/pulls/{number}/reviews", max_pages=self.max_pages
            )
            inline_counts: dict[str, int] | None = None
            remaining = self.client.rate_limit.remaining
            if remaining is None or remaining > 1:
                try:
                    comments = await self.client.get_paginated(
                        f"/repos/{owner}/{repo}/pulls/{number}/comments", max_pages=self.max_pages
                    )
                    inline_counts = {}
                    for comment in comments:
                        review_id = comment.get("pull_request_review_id")
                        if review_id is not None:
                            key = str(review_id)
                            inline_counts[key] = inline_counts.get(key, 0) + 1
                except GitHubAPIError:
                    pass
            pull_author = (pull.get("user") or {}).get("login")
            return [
                normalize_review(
                    item, f"{owner}/{repo}", number, pull.get("html_url"), pull_author,
                    None if inline_counts is None else inline_counts.get(str(item.get("id")), 0),
                )
                for item in raw_reviews
            ]

        events: list[ContributionEvent] = []
        for pull in selected:
            remaining = self.client.rate_limit.remaining
            if remaining is not None and remaining <= 1:
                break
            events.extend(await reviews_for_pr(pull))
        return events

    def get_data_completeness(self, owner: str, repo: str) -> dict[str, bool]:
        base = f"/repos/{owner}/{repo}"
        pulls_truncated = self.client.pagination_status(f"{base}/pulls").possibly_truncated
        return {
            "commits": self.client.pagination_status(f"{base}/commits").possibly_truncated,
            "pull_requests": pulls_truncated,
            "issues": self.client.pagination_status(f"{base}/issues").possibly_truncated,
            "reviews": (
                pulls_truncated
                or self.reviews_limited_by_pr_count
                or self.client.any_pagination_truncated(f"{base}/pulls/")
            ),
        }

    async def get_all_contribution_events(self, owner: str, repo: str) -> dict[str, list[ContributionEvent]]:
        raw_pulls, commits, issues = await asyncio.gather(
            self._get_raw_pull_requests(owner, repo), self.get_commits(owner, repo), self.get_issues(owner, repo)
        )
        pulls = [normalize_pull_request(item, f"{owner}/{repo}") for item in raw_pulls]
        reviews = await self.get_reviews(owner, repo, raw_pulls)
        all_events = commits + pulls + issues + reviews
        all_events.sort(key=lambda event: (event.created_at is not None, event.created_at), reverse=True)
        return {"commits": commits, "pull_requests": pulls, "issues": issues, "reviews": reviews, "all": all_events}
