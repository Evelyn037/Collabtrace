import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.database.db import Base, build_engine
from app.database.models import ContributionEventRecord, Member, Repository, SyncRecord
from app.github.client import GitHubAPIError
from app.models.contribution import ContributionEvent, EventType
from app.models.schemas import MemberCreate, MemberUpdate, RepositoryCreate
from app.services.analytics_service import AnalyticsService
from app.services.errors import ConflictError, NotFoundError
from app.services.member_service import MemberService
from app.services.repository_service import RepositoryService
from app.services.sync_service import SyncService


@pytest.fixture
def db(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class FakeGitHub:
    def __init__(self, events=None, fail=False):
        self.events = events or []
        self.fail = fail

    async def get_repository_info(self, owner, repo):
        return {
            "id": 123, "name": repo, "full_name": f"{owner}/{repo}", "owner_login": owner,
            "html_url": f"https://github.com/{owner}/{repo}", "description": "Test repository",
            "default_branch": "main", "private": False, "created_at": None, "updated_at": None,
        }

    async def get_all_contribution_events(self, owner, repo):
        if self.fail:
            raise GitHubAPIError(502, "Unable to reach GitHub API")
        grouped = {"commits": [], "pull_requests": [], "issues": [], "reviews": []}
        for event in self.events:
            key = {
                EventType.COMMIT: "commits", EventType.PULL_REQUEST: "pull_requests",
                EventType.ISSUE: "issues", EventType.REVIEW: "reviews",
            }[event.event_type]
            grouped[key].append(event)
        grouped["all"] = list(self.events)
        return grouped


def event(event_type, source_id, author="alice", title=None):
    prefix = {EventType.COMMIT: "commit", EventType.PULL_REQUEST: "pr", EventType.ISSUE: "issue", EventType.REVIEW: "review"}[event_type]
    return ContributionEvent(
        event_id=f"{prefix}:{source_id}", repository="owner/repo", event_type=event_type,
        author_login=author, title=title or f"{event_type.value} event",
        created_at=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        github_url=f"https://github.com/owner/repo/{prefix}/{source_id}", source_id=str(source_id),
        metadata={"source": source_id},
    )


async def create_repository(db):
    return await RepositoryService(db).create(RepositoryCreate(owner=" owner ", repo=" repo "), FakeGitHub())


@pytest.mark.asyncio
async def test_repository_create_duplicate_and_not_found(db):
    repository = await create_repository(db)
    assert repository.full_name == "owner/repo"
    assert RepositoryService(db).list() == [repository]
    assert RepositoryService(db).detail(repository.id)["event_count"] == 0
    with pytest.raises(ConflictError):
        await RepositoryService(db).create(RepositoryCreate(owner="OWNER", repo="REPO"), FakeGitHub())
    with pytest.raises(NotFoundError):
        RepositoryService(db).get(999)


@pytest.mark.asyncio
async def test_member_creation_case_insensitive_duplicate_and_historical_mapping(db):
    repository = await create_repository(db)
    record = ContributionEventRecord(
        repository_id=repository.id, event_id="commit:1", event_type="COMMIT",
        author_login="Alice-Dev", title="Commit", source_id="1",
        github_url="https://github.com/owner/repo/commit/1", metadata_json={"sha": "1"},
    )
    db.add(record)
    db.commit()
    member, remapped = MemberService(db).create(
        repository.id, MemberCreate(display_name="Alice", github_username="  ALICE-dev ")
    )
    db.refresh(record)
    assert member.github_username == "alice-dev"
    assert remapped == 1 and record.member_id == member.id
    with pytest.raises(ConflictError):
        MemberService(db).create(repository.id, MemberCreate(display_name="Other", github_username="Alice-Dev"))


@pytest.mark.asyncio
async def test_member_mapping_update_unmaps_old_and_maps_new_username(db):
    repository = await create_repository(db)
    alice = ContributionEventRecord(repository_id=repository.id, event_id="commit:a", event_type="COMMIT", author_login="alice", title="A", source_id="a", metadata_json={})
    bob = ContributionEventRecord(repository_id=repository.id, event_id="commit:b", event_type="COMMIT", author_login="BOB", title="B", source_id="b", metadata_json={})
    db.add_all([alice, bob]); db.commit()
    member, _ = MemberService(db).create(repository.id, MemberCreate(display_name="Student", github_username="alice"))
    updated, remapped = MemberService(db).update(repository.id, member.id, MemberUpdate(github_username="Bob"))
    db.refresh(alice); db.refresh(bob)
    assert updated.github_username == "bob" and remapped == 1
    assert alice.member_id is None and bob.member_id == member.id


@pytest.mark.asyncio
async def test_sync_insert_deduplicate_update_mapping_and_evidence(db):
    repository = await create_repository(db)
    member, _ = MemberService(db).create(repository.id, MemberCreate(display_name="Alice", github_username="ALICE"))
    events = [
        event(EventType.COMMIT, "a"), event(EventType.PULL_REQUEST, "1"),
        event(EventType.ISSUE, "1", author="external"), event(EventType.REVIEW, "1"),
    ]
    first = await SyncService(db).sync(repository.id, FakeGitHub(events))
    second = await SyncService(db).sync(repository.id, FakeGitHub(events))
    changed = list(events)
    changed[1] = event(EventType.PULL_REQUEST, "1", title="PR closed")
    third = await SyncService(db).sync(repository.id, FakeGitHub(changed))
    assert (first["inserted"], first["mapped"], first["unmapped"]) == (4, 3, 1)
    assert (second["inserted"], second["updated"], second["unchanged"]) == (0, 0, 4)
    assert (third["inserted"], third["updated"], third["unchanged"]) == (0, 1, 3)
    assert db.scalar(select(func.count(ContributionEventRecord.id))) == 4
    records = list(db.scalars(select(ContributionEventRecord)))
    assert all(record.github_url for record in records)
    assert all(isinstance(record.metadata_json, dict) for record in records)
    assert next(record for record in records if record.author_login == "external").member_id is None
    assert next(record for record in records if record.author_login == "alice").member_id == member.id
    assert db.scalar(select(func.count(SyncRecord.id)).where(SyncRecord.status == "SUCCESS")) == 3


@pytest.mark.asyncio
async def test_failed_sync_preserves_events_and_records_failure(db):
    repository = await create_repository(db)
    await SyncService(db).sync(repository.id, FakeGitHub([event(EventType.COMMIT, "a")]))
    with pytest.raises(GitHubAPIError):
        await SyncService(db).sync(repository.id, FakeGitHub(fail=True))
    assert db.scalar(select(func.count(ContributionEventRecord.id))) == 1
    failed = db.scalar(select(SyncRecord).where(SyncRecord.status == "FAILED"))
    assert failed is not None and failed.error_message == "Unable to reach GitHub API"


@pytest.mark.asyncio
async def test_cancelled_sync_records_failure_instead_of_remaining_running(db):
    repository = await create_repository(db)

    class CancelledGitHub:
        async def get_all_contribution_events(self, owner, repo):
            raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await SyncService(db).sync(repository.id, CancelledGitHub())
    failed = db.scalar(select(SyncRecord).where(SyncRecord.status == "FAILED"))
    assert failed is not None
    assert failed.finished_at is not None
    assert failed.error_message == "Synchronization failed"


@pytest.mark.asyncio
async def test_analytics_overview_stats_events_unmapped_and_timeline(db):
    repository = await create_repository(db)
    member, _ = MemberService(db).create(repository.id, MemberCreate(display_name="Alice", github_username="alice"))
    events = [event(EventType.COMMIT, "a"), event(EventType.PULL_REQUEST, "1"), event(EventType.ISSUE, "1", "external"), event(EventType.REVIEW, "1")]
    await SyncService(db).sync(repository.id, FakeGitHub(events))
    analytics = AnalyticsService(db)
    overview = analytics.overview(repository.id)
    assert overview["totals"] == {"events": 4, "commits": 1, "pull_requests": 1, "issues": 1, "reviews": 1}
    assert overview["mapped_events"] == 3 and overview["unmapped_events"] == 1
    stats = analytics.member_stats(repository.id)
    assert stats[0]["member_id"] == member.id and stats[0]["total_events"] == 3
    assert analytics.events(repository.id, None, None, None, 50, 0)["total"] == 4
    assert analytics.events(repository.id, member.id, "COMMIT", None, 50, 0)["total"] == 1
    assert analytics.unmapped_contributors(repository.id) == [{"github_username": "external", "event_count": 1}]
    timeline = analytics.member_timeline(repository.id, member.id)
    assert timeline == [{"date": "2026-09-01", "total": 3, "commits": 1, "pull_requests": 1, "issues": 0, "reviews": 1}]
