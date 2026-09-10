import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import sessionmaker

from app.database.db import Base, build_engine, normalize_database_url
from app.database.models import Repository, User
from app.models.contribution import ContributionEvent, EventType
from app.models.schemas import RegistrationRequest, RepositoryCreate, UserRole
from app.services.analytics_service import AnalyticsService
from app.services.auth_service import AuthService
from app.services.contribution_index_service import ContributionIndexService
from app.services.errors import ConflictError
from app.services.repository_access_service import RepositoryAccessService
from app.services.repository_service import RepositoryService
from app.services.sync_service import SyncService


PASSWORD = "postgres-integration-password"


class PostgreSQLSmokeGitHub:
    def __init__(self, suffix: str):
        self.suffix = suffix

    async def get_repository_info(self, owner: str, repo: str) -> dict:
        return {
            "id": int(self.suffix[:7], 16),
            "name": repo,
            "full_name": f"{owner}/{repo}",
            "owner_login": owner,
            "html_url": f"https://github.com/{owner}/{repo}",
            "description": "PostgreSQL integration smoke test",
            "default_branch": "main",
            "private": False,
        }

    async def get_all_contribution_events(self, owner: str, repo: str) -> dict:
        event = ContributionEvent(
            event_id=f"commit:{self.suffix}",
            repository=f"{owner}/{repo}",
            event_type=EventType.COMMIT,
            author_login="postgres-smoke-user",
            title="Portable persistence event",
            created_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
            github_url=f"https://github.com/{owner}/{repo}/commit/{self.suffix}",
            source_id=self.suffix,
            metadata={
                "metric_status": "AVAILABLE",
                "parents_count": 1,
                "raw_churn": 8,
                "filtered_churn": 8,
            },
        )
        return {
            "commits": [event],
            "pull_requests": [],
            "issues": [],
            "reviews": [],
            "all": [event],
        }


def postgres_test_url() -> str:
    value = os.getenv("COLLABTRACE_POSTGRES_TEST_URL") or os.getenv("DATABASE_URL")
    if not value or not normalize_database_url(value).startswith("postgresql+psycopg://"):
        pytest.skip("Set DATABASE_URL to an isolated PostgreSQL database for this integration test")
    return value


def unique_column_sets(inspector, table_name: str) -> set[frozenset[str]]:
    constraints = {
        frozenset(item["column_names"])
        for item in inspector.get_unique_constraints(table_name)
    }
    indexes = {
        frozenset(item["column_names"])
        for item in inspector.get_indexes(table_name)
        if item.get("unique")
    }
    return constraints | indexes


@pytest.mark.asyncio
async def test_postgresql_schema_auth_rbac_dedup_analytics_and_rci():
    engine = build_engine(postgres_test_url())
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    expected_tables = {
        "users", "user_credentials", "user_contacts", "repositories",
        "repository_accesses", "members", "contribution_events", "sync_records",
        "verification_codes",
    }
    assert expected_tables <= set(inspector.get_table_names())
    assert frozenset({"username"}) in unique_column_sets(inspector, "users")
    assert frozenset({"email"}) in unique_column_sets(inspector, "user_contacts")
    assert frozenset({"repository_id", "user_id"}) in unique_column_sets(
        inspector, "repository_accesses"
    )
    assert frozenset({"repository_id", "event_id"}) in unique_column_sets(
        inspector, "contribution_events"
    )

    suffix = uuid4().hex
    username = f"pg-smoke-{suffix}"
    email = f"pg-smoke-{suffix}@example.com"
    repository_name = f"repo-{suffix}"
    connection = engine.connect()
    outer_transaction = connection.begin()
    Session = sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    db = Session()
    try:
        auth = AuthService(db)
        user = auth.register(RegistrationRequest(
            username=username,
            email=email,
            password=PASSWORD,
            confirm_password=PASSWORD,
        ))
        assert user.role == UserRole.MEMBER.value
        assert user.email_verified is False
        assert auth.authenticate(username, PASSWORD).id == user.id
        assert auth.authenticate(email, PASSWORD).id == user.id
        with pytest.raises(ConflictError):
            auth.register(RegistrationRequest(
                username=username,
                email=f"other-{suffix}@example.com",
                password=PASSWORD,
                confirm_password=PASSWORD,
            ))
        with pytest.raises(ConflictError):
            auth.register(RegistrationRequest(
                username=f"other-{suffix}",
                email=email,
                password=PASSWORD,
                confirm_password=PASSWORD,
            ))

        github = PostgreSQLSmokeGitHub(suffix)
        repository = await RepositoryService(db).create(
            RepositoryCreate(owner="collabtrace-smoke", repo=repository_name), github
        )
        access = RepositoryAccessService(db)
        access.grant_access(repository.id, user.id, UserRole.ADMIN)
        assert access.get_repository_role(repository.id, user.id) == UserRole.ADMIN

        first = await SyncService(db).sync(repository.id, github)
        second = await SyncService(db).sync(repository.id, github)
        assert first["inserted"] == 1
        assert second["inserted"] == 0
        assert second["unchanged"] == 1
        assert AnalyticsService(db).overview(repository.id)["totals"]["events"] == 1
        assert AnalyticsService(db).repository_timeline(repository.id) == [{
            "date": "2026-09-10",
            "total": 1,
            "commits": 1,
            "pull_requests": 0,
            "issues": 0,
            "reviews": 0,
        }]
        rci = ContributionIndexService(db).calculate(repository.id)
        assert rci["methodology_version"] == "RCI_V1"
        assert rci["contributors"][0]["github_username"] == "postgres-smoke-user"
    finally:
        db.close()
        if outer_transaction.is_active:
            outer_transaction.rollback()
        connection.close()

    with engine.connect() as check:
        assert check.scalar(select(User.id).where(User.username == username)) is None
        assert check.scalar(select(Repository.id).where(Repository.name == repository_name)) is None
    engine.dispose()
