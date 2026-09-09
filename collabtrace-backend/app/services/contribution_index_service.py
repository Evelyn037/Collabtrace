from __future__ import annotations

from math import log1p
from pathlib import PurePosixPath
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import ContributionEventRecord as Event
from app.database.models import Member, Repository
from app.models.contribution import EventType
from app.services.errors import NotFoundError


METHODOLOGY_VERSION = "RCI_V1"
DIMENSIONS = ("code", "pr", "issue", "review")
EXCLUDED_DIRS = {"node_modules", "vendor", "dist", "build", "coverage", "generated"}
LOCK_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "npm-shrinkwrap.json",
    "poetry.lock", "pipfile.lock", "composer.lock", "cargo.lock", "gemfile.lock",
}
BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz",
    ".tar", ".7z", ".jar", ".war", ".exe", ".dll", ".so", ".dylib", ".woff",
    ".woff2", ".ttf", ".eot", ".mp3", ".mp4", ".mov", ".avi", ".bin",
}


def is_bot(login: str | None) -> bool:
    return bool(login and login.strip().lower().endswith("[bot]"))


def is_excluded_churn_file(filename: str) -> bool:
    path = PurePosixPath(filename.lower().replace("\\", "/"))
    name = path.name
    return (
        any(part in EXCLUDED_DIRS for part in path.parts[:-1])
        or name in LOCK_FILES
        or name.endswith((".min.js", ".min.css", ".map"))
        or path.suffix in BINARY_SUFFIXES
    )


def build_commit_metric_metadata(detail: dict[str, Any] | None) -> dict[str, Any]:
    if not detail:
        return {"metric_version": METHODOLOGY_VERSION, "metric_status": "UNAVAILABLE"}
    stats = detail.get("stats") or {}
    files = detail.get("files") or []
    raw_additions = int(stats.get("additions") or 0)
    raw_deletions = int(stats.get("deletions") or 0)
    filtered_additions = 0
    filtered_deletions = 0
    excluded_files = 0
    for file in files:
        if not isinstance(file, dict):
            continue
        if is_excluded_churn_file(str(file.get("filename") or "")):
            excluded_files += 1
            continue
        filtered_additions += int(file.get("additions") or 0)
        filtered_deletions += int(file.get("deletions") or 0)
    parents_count = len(detail.get("parents") or [])
    return {
        "metric_version": METHODOLOGY_VERSION,
        "parents_count": parents_count,
        "is_merge": parents_count > 1,
        "raw_additions": raw_additions,
        "raw_deletions": raw_deletions,
        "raw_churn": raw_additions + raw_deletions,
        "filtered_additions": filtered_additions,
        "filtered_deletions": filtered_deletions,
        "filtered_churn": filtered_additions + filtered_deletions,
        "excluded_files_count": excluded_files,
        "metric_status": "EMPTY" if int(stats.get("total") or 0) == 0 else "AVAILABLE",
    }


class ContributionIndexService:
    def __init__(self, db: Session):
        self.db = db

    def calculate(
        self,
        repository_id: int,
        exclude_bots: bool = True,
        requested_weights: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        repository = self.db.get(Repository, repository_id)
        if repository is None:
            raise NotFoundError("Repository not found")
        events = list(self.db.scalars(select(Event).where(Event.repository_id == repository_id)))
        members = {
            member.github_username.lower(): member
            for member in self.db.scalars(select(Member).where(Member.repository_id == repository_id))
        }
        contributors: dict[str, dict[str, Any]] = {}
        coverage = {dimension: [0, 0] for dimension in DIMENSIONS}
        review_seen: set[tuple[str, str, str]] = set()

        for event in events:
            login = (event.author_login or "").strip().lower()
            if not login or (exclude_bots and is_bot(login)):
                continue
            bucket = contributors.setdefault(login, self._empty_contributor(login, members.get(login)))
            bucket["total_events"] += 1
            raw = bucket["raw_metrics"]
            metadata = event.metadata_json or {}

            if event.event_type == EventType.COMMIT.value:
                raw["raw_commits"] += 1
                coverage["code"][1] += 1
                if metadata.get("metric_status") in {"AVAILABLE", "EMPTY"}:
                    coverage["code"][0] += 1
                merge = metadata.get("is_merge") is True or (metadata.get("parents_count") or 0) > 1
                empty = metadata.get("metric_status") == "EMPTY" or (
                    "raw_churn" in metadata and metadata.get("raw_churn") == 0
                )
                if not merge and not empty:
                    raw["effective_commits"] += 1
                    if metadata.get("metric_status") == "AVAILABLE":
                        raw["filtered_churn"] += max(0, int(metadata.get("filtered_churn") or 0))

            elif event.event_type == EventType.PULL_REQUEST.value:
                coverage["pr"][1] += 1
                if "state" in metadata and ("draft" in metadata) and (
                    "merged" in metadata or "merged_at" in metadata
                ):
                    coverage["pr"][0] += 1
                merged = metadata.get("merged") is True or bool(metadata.get("merged_at"))
                if merged and metadata.get("draft") is not True:
                    raw["merged_prs"] += 1

            elif event.event_type == EventType.ISSUE.value:
                coverage["issue"][1] += 1
                state = str(metadata.get("state") or "").lower()
                reason = str(metadata.get("state_reason") or "").lower()
                if state == "open" or (state == "closed" and bool(reason)):
                    coverage["issue"][0] += 1
                if state == "open" or (state == "closed" and reason == "completed"):
                    raw["effective_issues"] += 1

            elif event.event_type == EventType.REVIEW.value:
                coverage["review"][1] += 1
                review_state = str(metadata.get("review_state") or metadata.get("state") or "").upper()
                pull_number = str(metadata.get("pull_request_number") or metadata.get("pull_number") or "")
                pull_author = str(metadata.get("pull_request_author_login") or "").lower()
                commit_id = metadata.get("commit_id")
                review_id = str(metadata.get("review_id") or event.source_id)
                if (
                    review_state and pull_number and pull_author and (commit_id or review_id)
                    and metadata.get("inline_comment_count") is not None
                ):
                    coverage["review"][0] += 1
                has_substance = review_state in {"APPROVED", "CHANGES_REQUESTED"} or (
                    review_state == "COMMENTED" and (
                        bool(str(metadata.get("body") or "").strip())
                        or int(metadata.get("inline_comment_count") or 0) > 0
                    )
                )
                if review_state == "DISMISSED" or pull_author == login or not has_substance:
                    continue
                snapshot = str(commit_id) if commit_id else f"review:{review_id}"
                key = (pull_number, login, snapshot)
                if key not in review_seen:
                    review_seen.add(key)
                    raw["effective_reviews"] += 1

        contributor_list = list(contributors.values())
        for contributor in contributor_list:
            contributor["raw_metrics"]["robust_churn"] = log1p(
                contributor["raw_metrics"]["filtered_churn"]
            )

        dimension_scores = self._dimension_scores(contributor_list)
        active_dimensions = [d for d in DIMENSIONS if sum(scores[d] for scores in dimension_scores.values()) > 0]
        mode = "CUSTOM_WEIGHTS" if requested_weights is not None else "RESEARCH_BASELINE"
        supplied = requested_weights or {d: 1.0 for d in DIMENSIONS}
        weights = {d: max(0.0, float(supplied.get(d, 1.0))) for d in DIMENSIONS}
        active_weight_total = sum(weights[d] for d in active_dimensions)
        if active_dimensions and active_weight_total <= 0:
            raise ValueError("At least one active dimension must have a weight greater than zero")
        effective_weights = {
            d: (weights[d] / active_weight_total if d in active_dimensions and active_weight_total else 0.0)
            for d in DIMENSIONS
        }

        activity_order = sorted(contributor_list, key=lambda c: (-c["total_events"], c["github_username"]))
        for rank, contributor in enumerate(activity_order, 1):
            contributor["activity_rank"] = rank
        for contributor in contributor_list:
            login = contributor["github_username"]
            scores = dimension_scores[login]
            weighted = {d: 100 * effective_weights[d] * scores[d] for d in DIMENSIONS}
            contributor["dimension_scores"] = scores
            contributor["weighted_contributions"] = weighted
            contributor["rci"] = sum(weighted.values())
            score_total = sum(scores[d] for d in active_dimensions)
            contributor["composition"] = {
                d: (100 * scores[d] / score_total if score_total else 0.0) for d in DIMENSIONS
            }
            contributor["_unweighted_sum"] = score_total

        contributor_list.sort(key=lambda c: (
            -c["rci"], -c["_unweighted_sum"], -c["total_events"], c["github_username"]
        ))
        for rank, contributor in enumerate(contributor_list, 1):
            contributor["rci_rank"] = rank
            contributor["rci"] = round(contributor["rci"], 4)
            contributor["dimension_scores"] = {k: round(v, 6) for k, v in contributor["dimension_scores"].items()}
            contributor["composition"] = {k: round(v, 4) for k, v in contributor["composition"].items()}
            contributor["weighted_contributions"] = {
                k: round(v, 4) for k, v in contributor["weighted_contributions"].items()
            }
            contributor["raw_metrics"]["robust_churn"] = round(contributor["raw_metrics"]["robust_churn"], 6)
            del contributor["_unweighted_sum"]

        metric_coverage = {
            "code_churn_coverage": self._coverage(*coverage["code"]),
            "pr_status_coverage": self._coverage(*coverage["pr"]),
            "issue_state_reason_coverage": self._coverage(*coverage["issue"]),
            "review_metadata_coverage": self._coverage(*coverage["review"]),
        }
        return {
            "repository_id": repository_id,
            "methodology_version": METHODOLOGY_VERSION,
            "mode": mode,
            "requested_weights": weights,
            "effective_weights": {k: round(v, 6) for k, v in effective_weights.items()},
            "active_dimensions": active_dimensions,
            "metric_coverage": metric_coverage,
            "analysis_scope": {
                "description": "Current bounded synchronized repository data",
                "last_sync_at": repository.last_sync_at,
            },
            "contributors": contributor_list,
        }

    @staticmethod
    def _empty_contributor(login: str, member: Member | None) -> dict[str, Any]:
        return {
            "github_username": login,
            "display_name": member.display_name if member else login,
            "member_id": member.id if member else None,
            "user_id": member.user_id if member else None,
            "is_mapped": member is not None,
            "is_bot": is_bot(login),
            "total_events": 0,
            "activity_rank": 0,
            "raw_metrics": {
                "effective_commits": 0, "raw_commits": 0, "filtered_churn": 0,
                "robust_churn": 0.0, "merged_prs": 0, "effective_issues": 0,
                "effective_reviews": 0,
            },
        }

    @staticmethod
    def _dimension_scores(contributors: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
        totals = {
            "commits": sum(c["raw_metrics"]["effective_commits"] for c in contributors),
            "churn": sum(c["raw_metrics"]["robust_churn"] for c in contributors),
            "pr": sum(c["raw_metrics"]["merged_prs"] for c in contributors),
            "issue": sum(c["raw_metrics"]["effective_issues"] for c in contributors),
            "review": sum(c["raw_metrics"]["effective_reviews"] for c in contributors),
        }
        result: dict[str, dict[str, float]] = {}
        for contributor in contributors:
            raw = contributor["raw_metrics"]
            commit_share = raw["effective_commits"] / totals["commits"] if totals["commits"] else None
            churn_share = raw["robust_churn"] / totals["churn"] if totals["churn"] else None
            if commit_share is not None and churn_share is not None:
                code = 0.5 * commit_share + 0.5 * churn_share
            else:
                code = commit_share if commit_share is not None else (churn_share or 0.0)
            result[contributor["github_username"]] = {
                "code": code,
                "pr": raw["merged_prs"] / totals["pr"] if totals["pr"] else 0.0,
                "issue": raw["effective_issues"] / totals["issue"] if totals["issue"] else 0.0,
                "review": raw["effective_reviews"] / totals["review"] if totals["review"] else 0.0,
            }
        return result

    @staticmethod
    def _coverage(available: int, total: int) -> float:
        return round(available / total, 4) if total else 1.0
