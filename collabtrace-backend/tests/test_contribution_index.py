from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from app.database.db import Base, build_engine
from app.database.models import ContributionEventRecord, Repository
from app.services.contribution_index_service import (
    ContributionIndexService,
    build_commit_metric_metadata,
    is_excluded_churn_file,
)


@pytest.fixture
def rci_db(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'rci.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    repository = Repository(
        owner="owner", name="repo", full_name="owner/repo", github_repo_id=991,
        html_url="https://github.com/owner/repo", default_branch="main", is_private=False,
    )
    session.add(repository)
    session.commit()
    try:
        yield session, repository
    finally:
        session.close()
        engine.dispose()


def add_event(db, repository, event_id, event_type, author, metadata=None):
    db.add(ContributionEventRecord(
        repository_id=repository.id, event_id=event_id, event_type=event_type,
        author_login=author, title=event_id, source_id=event_id.split(":", 1)[-1],
        github_url=f"https://github.com/owner/repo/{event_id}",
        event_created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        metadata_json=metadata or {},
    ))


def test_commit_metric_filters_vendor_generated_lock_minified_map_and_binary():
    for filename in (
        "node_modules/lib.js", "vendor/a.php", "dist/app.js", "build/out.css",
        "coverage/index.html", "generated/client.py", "package-lock.json",
        "assets/app.min.js", "assets/app.min.css", "assets/app.js.map", "logo.png",
    ):
        assert is_excluded_churn_file(filename)
    assert not is_excluded_churn_file("src/application.ts")

    metadata = build_commit_metric_metadata({
        "stats": {"total": 127, "additions": 100, "deletions": 27},
        "parents": [{"sha": "one"}],
        "files": [
            {"filename": "src/app.py", "additions": 30, "deletions": 7},
            {"filename": "package-lock.json", "additions": 70, "deletions": 20},
        ],
    })
    assert metadata["raw_churn"] == 127
    assert metadata["filtered_churn"] == 37
    assert metadata["excluded_files_count"] == 1
    assert metadata["metric_status"] == "AVAILABLE"


def test_commit_merge_empty_and_bot_are_excluded_but_raw_events_remain(rci_db):
    db, repository = rci_db
    add_event(db, repository, "commit:good", "COMMIT", "alice", {
        "parents_count": 1, "is_merge": False, "raw_churn": 12,
        "filtered_churn": 10, "metric_status": "AVAILABLE",
    })
    add_event(db, repository, "commit:merge", "COMMIT", "alice", {
        "parents_count": 2, "is_merge": True, "raw_churn": 20,
        "filtered_churn": 20, "metric_status": "AVAILABLE",
    })
    add_event(db, repository, "commit:empty", "COMMIT", "alice", {
        "parents_count": 1, "raw_churn": 0, "filtered_churn": 0, "metric_status": "EMPTY",
    })
    add_event(db, repository, "commit:bot", "COMMIT", "dependabot[bot]", {
        "parents_count": 1, "raw_churn": 12, "filtered_churn": 12, "metric_status": "AVAILABLE",
    })
    db.commit()
    result = ContributionIndexService(db).calculate(repository.id)
    alice = result["contributors"][0]
    assert alice["total_events"] == 3
    assert alice["raw_metrics"]["raw_commits"] == 3
    assert alice["raw_metrics"]["effective_commits"] == 1
    assert all(row["github_username"] != "dependabot[bot]" for row in result["contributors"])


def test_pr_issue_review_filters_and_review_snapshot_dedup(rci_db):
    db, repository = rci_db
    add_event(db, repository, "pr:1", "PULL_REQUEST", "alice", {
        "state": "closed", "draft": False, "merged": True, "merged_at": "2026-09-01",
    })
    add_event(db, repository, "pr:2", "PULL_REQUEST", "alice", {
        "state": "open", "draft": False, "merged": False, "merged_at": None,
    })
    add_event(db, repository, "issue:1", "ISSUE", "alice", {"state": "open", "state_reason": None})
    add_event(db, repository, "issue:2", "ISSUE", "alice", {"state": "closed", "state_reason": "not_planned"})
    base = {"pull_request_number": 4, "pull_request_author_login": "alice", "review_state": "COMMENTED"}
    add_event(db, repository, "review:1", "REVIEW", "bob", {**base, "review_id": 1, "commit_id": "a", "body": "Useful"})
    add_event(db, repository, "review:2", "REVIEW", "bob", {**base, "review_id": 2, "commit_id": "a", "body": "Again"})
    add_event(db, repository, "review:3", "REVIEW", "bob", {**base, "review_id": 3, "commit_id": "b", "body": "New snapshot"})
    add_event(db, repository, "review:4", "REVIEW", "bob", {**base, "review_id": 4, "commit_id": "c", "body": ""})
    add_event(db, repository, "review:5", "REVIEW", "alice", {**base, "review_id": 5, "commit_id": "d", "body": "self"})
    db.commit()
    result = ContributionIndexService(db).calculate(repository.id)
    people = {row["github_username"]: row for row in result["contributors"]}
    assert people["alice"]["raw_metrics"]["merged_prs"] == 1
    assert people["alice"]["raw_metrics"]["effective_issues"] == 1
    assert people["bob"]["raw_metrics"]["effective_reviews"] == 2


def test_normalization_custom_weights_composition_and_all_zero(rci_db):
    db, repository = rci_db
    add_event(db, repository, "commit:a", "COMMIT", "alice", {
        "parents_count": 1, "raw_churn": 100, "filtered_churn": 100, "metric_status": "AVAILABLE",
    })
    add_event(db, repository, "commit:b", "COMMIT", "bob", {
        "parents_count": 1, "raw_churn": 10, "filtered_churn": 10, "metric_status": "AVAILABLE",
    })
    add_event(db, repository, "issue:a", "ISSUE", "bob", {"state": "open", "state_reason": None})
    db.commit()
    service = ContributionIndexService(db)
    baseline = service.calculate(repository.id)
    custom = service.calculate(repository.id, requested_weights={
        "code": 0, "pr": 0, "issue": 1, "review": 0,
    })
    assert baseline["active_dimensions"] == ["code", "issue"]
    assert baseline["effective_weights"] == {"code": 0.5, "pr": 0.0, "issue": 0.5, "review": 0.0}
    assert abs(sum(row["rci"] for row in baseline["contributors"]) - 100) < 0.01
    baseline_composition = {r["github_username"]: r["composition"] for r in baseline["contributors"]}
    custom_composition = {r["github_username"]: r["composition"] for r in custom["contributors"]}
    assert baseline_composition == custom_composition
    assert custom["contributors"][0]["github_username"] == "bob"
    with pytest.raises(ValueError):
        service.calculate(repository.id, requested_weights={d: 0 for d in ("code", "pr", "issue", "review")})


def test_partial_coverage_is_reported(rci_db):
    db, repository = rci_db
    add_event(db, repository, "commit:old", "COMMIT", "alice", {})
    add_event(db, repository, "commit:new", "COMMIT", "alice", {
        "metric_status": "AVAILABLE", "raw_churn": 2, "filtered_churn": 2, "parents_count": 1,
    })
    db.commit()
    coverage = ContributionIndexService(db).calculate(repository.id)["metric_coverage"]
    assert coverage["code_churn_coverage"] == 0.5


def test_draft_and_unmerged_prs_and_unknown_closed_issues_are_excluded(rci_db):
    db, repository = rci_db
    add_event(db, repository, "pr:merged", "PULL_REQUEST", "alice", {
        "state": "closed", "draft": False, "merged": True, "merged_at": "now",
    })
    add_event(db, repository, "pr:draft", "PULL_REQUEST", "alice", {
        "state": "closed", "draft": True, "merged": True, "merged_at": "now",
    })
    add_event(db, repository, "pr:closed", "PULL_REQUEST", "alice", {
        "state": "closed", "draft": False, "merged": False, "merged_at": None,
    })
    add_event(db, repository, "issue:complete", "ISSUE", "alice", {
        "state": "closed", "state_reason": "completed",
    })
    add_event(db, repository, "issue:unknown", "ISSUE", "alice", {"state": "closed"})
    db.commit()
    raw = ContributionIndexService(db).calculate(repository.id)["contributors"][0]["raw_metrics"]
    assert raw["merged_prs"] == 1
    assert raw["effective_issues"] == 1


def test_review_states_inline_comments_self_review_and_missing_snapshot_fallback(rci_db):
    db, repository = rci_db
    common = {"pull_request_number": 8, "pull_request_author_login": "alice"}
    reviews = [
        ("review:approved", "bob", {**common, "review_id": 1, "commit_id": "a", "review_state": "APPROVED"}),
        ("review:changes", "bob", {**common, "review_id": 2, "commit_id": "b", "review_state": "CHANGES_REQUESTED"}),
        ("review:inline", "carol", {**common, "review_id": 3, "commit_id": "a", "review_state": "COMMENTED", "body": "", "inline_comment_count": 1}),
        ("review:empty", "dave", {**common, "review_id": 4, "commit_id": "a", "review_state": "COMMENTED", "body": "", "inline_comment_count": 0}),
        ("review:dismissed", "erin", {**common, "review_id": 5, "commit_id": "a", "review_state": "DISMISSED"}),
        ("review:self", "alice", {**common, "review_id": 6, "commit_id": "a", "review_state": "APPROVED"}),
        ("review:no-snapshot-1", "frank", {**common, "review_id": 7, "commit_id": None, "review_state": "APPROVED"}),
        ("review:no-snapshot-2", "frank", {**common, "review_id": 8, "commit_id": None, "review_state": "APPROVED"}),
        ("review:bot", "reviewer[bot]", {**common, "review_id": 9, "commit_id": "a", "review_state": "APPROVED"}),
    ]
    for event_id, author, metadata in reviews:
        add_event(db, repository, event_id, "REVIEW", author, metadata)
    db.commit()
    people = {row["github_username"]: row for row in ContributionIndexService(db).calculate(repository.id)["contributors"]}
    assert people["bob"]["raw_metrics"]["effective_reviews"] == 2
    assert people["carol"]["raw_metrics"]["effective_reviews"] == 1
    assert people["dave"]["raw_metrics"]["effective_reviews"] == 0
    assert people["erin"]["raw_metrics"]["effective_reviews"] == 0
    assert people["alice"]["raw_metrics"]["effective_reviews"] == 0
    assert people["frank"]["raw_metrics"]["effective_reviews"] == 2
    assert "reviewer[bot]" not in people


def test_rci_tie_break_is_deterministic_by_login(rci_db):
    db, repository = rci_db
    for login in ("zoe", "amy"):
        add_event(db, repository, f"commit:{login}", "COMMIT", login, {
            "parents_count": 1, "raw_churn": 5, "filtered_churn": 5,
            "metric_status": "AVAILABLE",
        })
    db.commit()
    contributors = ContributionIndexService(db).calculate(repository.id)["contributors"]
    assert [(row["github_username"], row["rci_rank"]) for row in contributors] == [
        ("amy", 1), ("zoe", 2),
    ]
