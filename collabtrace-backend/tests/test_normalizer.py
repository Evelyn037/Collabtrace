from app.github.normalizer import normalize_commit, normalize_issue, normalize_pull_request, normalize_review
from app.models.contribution import EventType


def commit(author):
    return {"sha": "abc123", "author": author, "html_url": "https://github.com/o/r/commit/abc123", "commit": {"message": "Fix bug\nDetails", "author": {"name": "Alice", "email": "a@example.com", "date": "2026-01-01T00:00:00Z"}}}


def test_normalize_commit_with_github_author():
    event = normalize_commit(commit({"login": "alice"}), "o/r")
    assert event.event_type == EventType.COMMIT
    assert event.author_login == "alice"
    assert event.title == "Fix bug"


def test_normalize_commit_with_null_github_author():
    event = normalize_commit(commit(None), "o/r")
    assert event.author_login is None
    assert event.metadata["author_name"] == "Alice"


def test_normalize_pull_request():
    raw = {"id": 7, "number": 3, "title": "Add feature", "user": {"login": "bob"}, "state": "closed", "created_at": "2026-01-02T00:00:00Z", "html_url": "https://github.com/o/r/pull/3", "merged_at": "2026-01-03T00:00:00Z"}
    event = normalize_pull_request(raw, "o/r")
    assert event.event_type == EventType.PULL_REQUEST
    assert event.event_id == "pr:7"
    assert event.metadata["merged_at"] is not None


def test_normalize_issue_and_filter_pull_request():
    issue = {"id": 7, "number": 4, "title": "Bug", "user": {"login": "carol"}, "created_at": "2026-01-01T00:00:00Z", "labels": [{"name": "bug"}], "assignees": [{"login": "dave"}]}
    assert normalize_issue({**issue, "pull_request": {}}, "o/r") is None
    event = normalize_issue(issue, "o/r")
    assert event is not None and event.metadata["labels"] == ["bug"]


def test_normalize_review():
    raw = {"id": 7, "user": {"login": "erin"}, "state": "APPROVED", "submitted_at": "2026-01-03T00:00:00Z"}
    event = normalize_review(raw, "o/r", 3, "https://github.com/o/r/pull/3")
    assert event.event_type == EventType.REVIEW
    assert event.metadata["pull_number"] == 3
    assert event.github_url


def test_event_ids_are_namespaced():
    issue = normalize_issue({"id": 7, "title": "Issue"}, "o/r")
    ids = {
        normalize_commit(commit(None), "o/r").event_id,
        normalize_pull_request({"id": 7, "title": "PR"}, "o/r").event_id,
        issue.event_id if issue else "",
        normalize_review({"id": 7}, "o/r", 1).event_id,
    }
    assert ids == {"commit:abc123", "pr:7", "issue:7", "review:7"}
