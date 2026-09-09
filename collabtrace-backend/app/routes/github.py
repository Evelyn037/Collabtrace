from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from app.config import PROJECT_ROOT, get_settings
from app.dependencies.auth import require_admin
from app.github.client import GitHubClient
from app.github.service import GitHubService
from app.models.contribution import ContributionEvent

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/github", tags=["GitHub PoC"], dependencies=[Depends(require_admin)]
)


class EventListResponse(BaseModel):
    count: int
    events: list[ContributionEvent]


def save_probe_result(result: dict, output_path=PROJECT_ROOT / "data" / "last_probe.json") -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(jsonable_encoder(result), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_probe_warnings(
    remaining: int | None, possibly_truncated: bool
) -> list[str]:
    warnings: list[str] = []
    if remaining is not None and remaining < 10:
        warnings.append(
            "GitHub API rate limit remaining is low; configure GITHUB_TOKEN or retry after reset."
        )
    if possibly_truncated:
        warnings.append(
            "One or more result sets may be truncated by max_pages or max_prs_for_reviews."
        )
    return warnings


async def get_service(
    max_pages: Annotated[int, Query(ge=0, description="最多读取的分页数；0 表示读取全部")] = 10,
    max_prs_for_reviews: Annotated[int, Query(ge=0, description="最多检查 Review 的 PR 数；0 表示不限制")] = 50,
):
    settings = get_settings()
    async with GitHubClient(settings.github_token, settings.github_base_url, settings.github_timeout_seconds) as client:
        yield GitHubService(client, max_pages or None, max_prs_for_reviews or None)


Service = Annotated[GitHubService, Depends(get_service)]


@router.get("/auth-status")
async def auth_status(service: Service):
    payload = await service.client.get("/rate_limit")
    core = (payload.get("resources") or {}).get("core") or {}
    rate_limit = {
        "limit": core.get("limit", service.client.rate_limit.limit),
        "remaining": core.get("remaining", service.client.rate_limit.remaining),
        "reset": core.get("reset", service.client.rate_limit.reset),
    }
    warnings: list[str] = []
    if service.client.token_configured and rate_limit["limit"] == 60:
        warnings.append(
            "A token is configured but GitHub still reports an unauthenticated-style rate limit."
        )
    return {
        "token_configured": service.client.token_configured,
        "authentication_mode": "token" if service.client.token_configured else "unauthenticated",
        "rate_limit": rate_limit,
        "warnings": warnings,
    }


@router.get("/{owner}/{repo}")
async def repository_info(owner: str, repo: str, service: Service):
    return await service.get_repository_info(owner, repo)


@router.get("/{owner}/{repo}/commits", response_model=EventListResponse)
async def commits(owner: str, repo: str, service: Service):
    events = await service.get_commits(owner, repo)
    return {"count": len(events), "events": events}


@router.get("/{owner}/{repo}/pulls", response_model=EventListResponse)
async def pulls(owner: str, repo: str, service: Service):
    events = await service.get_pull_requests(owner, repo)
    return {"count": len(events), "events": events}


@router.get("/{owner}/{repo}/issues", response_model=EventListResponse)
async def issues(owner: str, repo: str, service: Service):
    events = await service.get_issues(owner, repo)
    return {"count": len(events), "events": events}


@router.get("/{owner}/{repo}/reviews", response_model=EventListResponse)
async def reviews(owner: str, repo: str, service: Service):
    events = await service.get_reviews(owner, repo)
    return {"count": len(events), "events": events}


@router.get("/{owner}/{repo}/probe")
async def probe(owner: str, repo: str, service: Service):
    repository = await service.get_repository_info(owner, repo)
    grouped = await service.get_all_contribution_events(owner, repo)
    completeness = service.get_data_completeness(owner, repo)
    result = {
        "repository": {"full_name": repository["full_name"], "url": repository["html_url"]},
        "summary": {
            "commits": len(grouped["commits"]), "pull_requests": len(grouped["pull_requests"]),
            "issues": len(grouped["issues"]), "reviews": len(grouped["reviews"]),
            "total_events": len(grouped["all"]),
        },
        "rate_limit": service.client.get_rate_limit(),
        "pagination": {
            "max_pages": service.max_pages,
            "max_prs_for_reviews": service.max_prs_for_reviews,
            "possibly_truncated": any(completeness.values()),
            "resources": completeness,
        },
        "warnings": [],
        "samples": {name: events[:3] for name, events in grouped.items() if name != "all"},
    }
    result["warnings"] = build_probe_warnings(
        result["rate_limit"]["remaining"], result["pagination"]["possibly_truncated"]
    )
    save_probe_result(result)
    logger.info("Probe completed for %s/%s", owner, repo)
    return result
