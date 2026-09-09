import logging
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database.db import Base, build_engine
from app.database.models import User
from app.github.client import GitHubAPIError
from app.models.contribution import ContributionEvent, EventType
from app.services.repository_analyze_service import RepositoryAnalyzeService


class FlowGitHub:
    max_pages = None
    max_prs_for_reviews = None

    def __init__(self, fail=False):
        self.fail = fail

    async def get_repository_info(self, owner, repo):
        return {
            "id": 987654,
            "name": repo,
            "full_name": f"{owner}/{repo}",
            "owner_login": owner,
            "html_url": f"https://github.com/{owner}/{repo}",
            "description": "Flow test",
            "default_branch": "main",
            "private": False,
        }

    async def get_all_contribution_events(self, owner, repo):
        if self.fail:
            raise GitHubAPIError(502, "sensitive upstream response body")
        commit = ContributionEvent(
            event_id="commit:flow",
            repository=f"{owner}/{repo}",
            event_type=EventType.COMMIT,
            author_login="flow-user",
            title="Flow commit",
            created_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
            github_url=f"https://github.com/{owner}/{repo}/commit/flow",
            source_id="flow",
            metadata={},
        )
        return {
            "commits": [commit],
            "pull_requests": [],
            "issues": [],
            "reviews": [],
            "all": [commit],
        }


@pytest.fixture
def flow_db(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'flow.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    user = User(username="flow-user", display_name="Flow User", role="MEMBER")
    db.add(user)
    db.commit()
    db.refresh(user)
    try:
        yield db, user
    finally:
        db.close()
        engine.dispose()


@pytest.mark.asyncio
async def test_analyze_and_sync_emit_real_flow_stages_and_counts(flow_db, caplog):
    db, user = flow_db
    settings = Settings(
        quick_analyze_max_pages=1,
        quick_analyze_max_prs_for_reviews=5,
        github_token="github-secret-must-not-be-logged",
        jwt_secret="jwt-secret-must-not-be-logged",
        verification_code_secret="123456-must-not-be-logged",
        smtp_password="smtp-secret-must-not-be-logged",
    )

    with caplog.at_level(logging.INFO, logger="collabtrace.flow"):
        result = await RepositoryAnalyzeService(db, settings).analyze(
            "owner/repository", FlowGitHub(), user
        )

    assert result["sync"]["fetched"] == 1
    assert result["sync"]["inserted"] == 1
    for stage in (
        "Analyze started",
        "Repository resolved",
        "Sync started",
        "GitHub fetch started",
        "GitHub fetch complete",
        "Normalization complete",
        "Persistence complete",
        "Sync complete",
        "Analyze complete",
    ):
        assert stage in caplog.text
    assert "commits=1 pull_requests=0 issues=0 reviews=0 total=1" in caplog.text
    assert "fetched=1 inserted=1 updated=0 unchanged=0 mapped=0 unmapped=1" in caplog.text
    for secret in (
        settings.github_token,
        settings.jwt_secret,
        settings.verification_code_secret,
        settings.smtp_password,
    ):
        assert secret not in caplog.text


@pytest.mark.asyncio
async def test_flow_failure_is_observable_without_upstream_details(flow_db, caplog):
    db, user = flow_db
    with caplog.at_level(logging.INFO, logger="collabtrace.flow"):
        with pytest.raises(GitHubAPIError):
            await RepositoryAnalyzeService(db, Settings()).analyze(
                "owner/repository", FlowGitHub(fail=True), user
            )

    assert "Sync failed" in caplog.text
    assert "Analyze failed" in caplog.text
    assert "reason=GitHubAPIError" in caplog.text
    assert "sensitive upstream response body" not in caplog.text
