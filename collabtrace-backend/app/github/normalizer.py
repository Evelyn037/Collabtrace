from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.contribution import ContributionEvent, EventType


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def normalize_commit(
    raw: dict[str, Any], repository: str, metric_metadata: dict[str, Any] | None = None
) -> ContributionEvent:
    commit = raw.get("commit") or {}
    git_author = commit.get("author") or {}
    github_author = raw.get("author") or {}
    sha = str(raw.get("sha", ""))
    message = str(commit.get("message") or "Untitled commit")
    return ContributionEvent(
        event_id=f"commit:{sha}", repository=repository, event_type=EventType.COMMIT,
        author_login=github_author.get("login"), title=message.splitlines()[0],
        created_at=_parse_datetime(git_author.get("date")), github_url=raw.get("html_url"), source_id=sha,
        metadata={
            "sha": sha, "author_name": git_author.get("name"),
            "author_email": git_author.get("email"), "message": message,
            **(metric_metadata or {}),
        },
    )


def normalize_pull_request(raw: dict[str, Any], repository: str) -> ContributionEvent:
    source_id = str(raw.get("id", ""))
    return ContributionEvent(
        event_id=f"pr:{source_id}", repository=repository, event_type=EventType.PULL_REQUEST,
        author_login=(raw.get("user") or {}).get("login"), title=str(raw.get("title") or "Untitled pull request"),
        created_at=_parse_datetime(raw.get("created_at")), github_url=raw.get("html_url"), source_id=source_id,
        metadata={
            **{key: raw.get(key) for key in ("number", "state", "updated_at", "closed_at", "merged_at")},
            "draft": bool(raw.get("draft")),
            "merged": bool(raw.get("merged_at")),
        },
    )


def normalize_issue(raw: dict[str, Any], repository: str) -> ContributionEvent | None:
    if "pull_request" in raw:
        return None
    source_id = str(raw.get("id", ""))
    return ContributionEvent(
        event_id=f"issue:{source_id}", repository=repository, event_type=EventType.ISSUE,
        author_login=(raw.get("user") or {}).get("login"), title=str(raw.get("title") or "Untitled issue"),
        created_at=_parse_datetime(raw.get("created_at")), github_url=raw.get("html_url"), source_id=source_id,
        metadata={
            "number": raw.get("number"), "state": raw.get("state"),
            "state_reason": raw.get("state_reason"), "closed_at": raw.get("closed_at"),
            "labels": [label.get("name") for label in raw.get("labels", []) if isinstance(label, dict)],
            "assignees": [user.get("login") for user in raw.get("assignees", []) if isinstance(user, dict)],
        },
    )


def normalize_review(
    raw: dict[str, Any], repository: str, pull_number: int,
    pull_url: str | None = None, pull_author_login: str | None = None,
    inline_comment_count: int | None = None,
) -> ContributionEvent:
    source_id = str(raw.get("id", ""))
    return ContributionEvent(
        event_id=f"review:{source_id}", repository=repository, event_type=EventType.REVIEW,
        author_login=(raw.get("user") or {}).get("login"), title=f"Review PR #{pull_number}",
        created_at=_parse_datetime(raw.get("submitted_at")), github_url=raw.get("html_url") or pull_url,
        source_id=source_id,
        metadata={
            "review_id": raw.get("id"),
            "pull_number": pull_number,
            "pull_request_number": pull_number,
            "pull_request_author_login": pull_author_login,
            "review_state": raw.get("state"),
            "state": raw.get("state"),
            "body": raw.get("body"),
            "body_present": bool(str(raw.get("body") or "").strip()),
            "commit_id": raw.get("commit_id"),
            "inline_comment_count": inline_comment_count,
            "inline_comment_status": "AVAILABLE" if inline_comment_count is not None else "UNAVAILABLE",
            "dedup_confidence": "HIGH" if raw.get("commit_id") else "LOW",
        },
    )
