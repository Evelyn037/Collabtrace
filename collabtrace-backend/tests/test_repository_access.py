from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database.db import Base, build_engine, get_db
from app.database.models import ContributionEventRecord, Repository, RepositoryAccess, SyncRecord, User
from app.config import Settings
from app.github.service import GitHubService
from app.main import app
from app.models.contribution import ContributionEvent, EventType
from app.models.schemas import RepositoryCreate, UserCreate, UserRole
from app.routes.github import get_service
from app.services.auth_service import AuthService
from app.services.repository_access_service import RepositoryAccessService
from app.services.repository_analyze_service import RepositoryAnalyzeService
from app.services.repository_service import RepositoryService
from app.services.errors import ConflictError, ForbiddenError


PASSWORD = "repository-access-test-password"
JWT_SECRET = "repository-access-test-secret-that-is-long-enough"


class AccessGitHub:
    max_pages = 10
    max_prs_for_reviews = 50

    async def get_repository_info(self, owner, repo):
        return {
            "id": 10000 + sum(ord(char) for char in f"{owner}/{repo}"),
            "name": repo, "full_name": f"{owner}/{repo}", "owner_login": owner,
            "html_url": f"https://github.com/{owner}/{repo}", "description": "Access fixture",
            "default_branch": "main", "private": False,
        }

    async def get_all_contribution_events(self, owner, repo):
        event = ContributionEvent(
            event_id=f"commit:{owner}:{repo}", repository=f"{owner}/{repo}",
            event_type=EventType.COMMIT, author_login="external-dev", title="Evidence",
            created_at=datetime(2026, 9, 8, tzinfo=timezone.utc),
            github_url=f"https://github.com/{owner}/{repo}/commit/fixture",
            source_id=f"{owner}-{repo}", metadata={},
        )
        return {"commits": [event], "pull_requests": [], "issues": [], "reviews": [], "all": [event]}


@pytest.fixture
def access_app(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    engine = build_engine(f"sqlite:///{tmp_path / 'repository-access.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        alice = AuthService(db).create_user(UserCreate(
            username="alice", display_name="Alice", password=PASSWORD, role=UserRole.MEMBER
        ))
        bob = AuthService(db).create_user(UserCreate(
            username="bob", display_name="Bob", password=PASSWORD, role=UserRole.MEMBER
        ))
        system_admin = AuthService(db).create_user(UserCreate(
            username="system-admin", display_name="System Admin", password=PASSWORD,
            role=UserRole.ADMIN,
        ))
        ids = {"alice": alice.id, "bob": bob.id, "system_admin": system_admin.id}

    def override_db():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_service] = lambda: AccessGitHub()
    client = TestClient(app)
    yield client, Session, ids
    app.dependency_overrides.clear()
    engine.dispose()


def auth(client, username):
    response = client.post("/api/auth/login", json={"identifier": username, "password": PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def analyze(client, headers, name):
    response = client.post("/api/repositories/analyze", json={"repository": name}, headers=headers)
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_repository_access_table_unique_default_explicit_and_bootstrap(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'model.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        admin = AuthService(db).create_user(UserCreate(
            username="admin", display_name="Admin", password=PASSWORD, role=UserRole.ADMIN
        ))
        member = AuthService(db).create_user(UserCreate(
            username="member", display_name="Member", password=PASSWORD, role=UserRole.MEMBER
        ))
        repository = await RepositoryService(db).create(
            RepositoryCreate(owner="legacy", repo="repo"), AccessGitHub()
        )
        service = RepositoryAccessService(db)
        assert service.get_repository_role(repository.id, member.id) == UserRole.MEMBER
        service.grant_access(repository.id, admin.id, UserRole.MEMBER)
        assert service.bootstrap_existing_repository_admins(db) == 1
        assert service.bootstrap_existing_repository_admins(db) == 0
        assert service.get_repository_role(repository.id, admin.id) == UserRole.ADMIN
        service.grant_access(repository.id, member.id, UserRole.MEMBER)
        assert service.list_repository_access(repository.id)[1]["explicit"] is True
        db.add(RepositoryAccess(repository_id=repository.id, user_id=member.id, role="ADMIN"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    engine.dispose()


def test_two_user_two_repository_roles_and_read_access(access_app):
    client, Session, _ = access_app
    alice, bob = auth(client, "alice"), auth(client, "bob")
    repo_a = analyze(client, alice, "demo/repo-a")
    repo_b = analyze(client, bob, "demo/repo-b")
    assert repo_a["repository"]["current_user_role"] == "ADMIN"
    assert repo_b["repository"]["current_user_role"] == "ADMIN"
    alice_repositories = {row["full_name"]: row["current_user_role"] for row in client.get("/api/repositories", headers=alice).json()}
    bob_repositories = {row["full_name"]: row["current_user_role"] for row in client.get("/api/repositories", headers=bob).json()}
    assert alice_repositories == {"demo/repo-a": "ADMIN", "demo/repo-b": "MEMBER"}
    assert bob_repositories == {"demo/repo-a": "MEMBER", "demo/repo-b": "ADMIN"}
    with Session() as db:
        assert db.scalar(select(User.role).where(User.username == "alice")) == "MEMBER"
        assert db.scalar(select(User.role).where(User.username == "bob")) == "MEMBER"

    repository_id = repo_a["repository"]["id"]
    read_paths = [
        f"/api/repositories/{repository_id}", f"/api/repositories/{repository_id}/overview",
        f"/api/repositories/{repository_id}/contributor-stats",
        f"/api/repositories/{repository_id}/contributors/external-dev",
        f"/api/repositories/{repository_id}/contributors/external-dev/timeline",
        f"/api/repositories/{repository_id}/events", f"/api/repositories/{repository_id}/timeline",
        f"/api/repositories/{repository_id}/syncs",
    ]
    assert all(client.get(path, headers=bob).status_code == 200 for path in read_paths)


def test_existing_member_cannot_refresh_or_sync_and_has_no_side_effect(access_app):
    client, Session, ids = access_app
    alice, bob = auth(client, "alice"), auth(client, "bob")
    created = analyze(client, alice, "demo/protected")
    repository_id = created["repository"]["id"]
    with Session() as db:
        before = (
            db.scalar(select(func.count(SyncRecord.id))),
            db.scalar(select(func.count(ContributionEventRecord.id))),
            db.scalar(select(func.count(RepositoryAccess.id))),
        )
    repeated = client.post(
        "/api/repositories/analyze", json={"repository": "DEMO/PROTECTED"}, headers=bob
    )
    assert repeated.status_code == 403
    assert client.post(f"/api/repositories/{repository_id}/sync", headers=bob).status_code == 403
    with Session() as db:
        after = (
            db.scalar(select(func.count(SyncRecord.id))),
            db.scalar(select(func.count(ContributionEventRecord.id))),
            db.scalar(select(func.count(RepositoryAccess.id))),
        )
        assert RepositoryAccessService(db).get_repository_role(repository_id, ids["bob"]) == UserRole.MEMBER
    assert after == before
    assert client.post(f"/api/repositories/{repository_id}/sync", headers=alice).status_code == 200


def test_repository_mapping_and_access_management_are_scoped_and_independent(access_app):
    client, Session, ids = access_app
    alice, bob = auth(client, "alice"), auth(client, "bob")
    repo_a = analyze(client, alice, "demo/access-a")["repository"]
    repo_b = analyze(client, bob, "demo/access-b")["repository"]
    mapping = {"display_name": "Bob Dev", "github_username": "external-dev", "user_id": ids["bob"]}
    assert client.post(f"/api/repositories/{repo_a['id']}/members", json=mapping, headers=bob).status_code == 403
    assert client.get(f"/api/repositories/{repo_a['id']}/unmapped-contributors", headers=bob).status_code == 403
    mapped = client.post(f"/api/repositories/{repo_a['id']}/members", json=mapping, headers=alice)
    assert mapped.status_code == 201
    before_total = client.get(f"/api/repositories/{repo_a['id']}/overview", headers=bob).json()["totals"]["events"]

    assert client.get(f"/api/repositories/{repo_a['id']}/access", headers=bob).status_code == 403
    access_list = client.get(f"/api/repositories/{repo_a['id']}/access", headers=alice)
    assert access_list.status_code == 200
    implicit_bob = next(row for row in access_list.json() if row["username"] == "bob")
    assert implicit_bob["role"] == "MEMBER" and implicit_bob["explicit"] is False
    promoted = client.patch(
        f"/api/repositories/{repo_a['id']}/access/{ids['bob']}", json={"role": "ADMIN"}, headers=alice
    )
    assert promoted.status_code == 200 and promoted.json()["role"] == "ADMIN"
    assert client.get(f"/api/repositories/{repo_a['id']}/access", headers=bob).status_code == 200
    assert client.get(f"/api/repositories/{repo_b['id']}", headers=bob).json()["current_user_role"] == "ADMIN"
    assert client.get(f"/api/repositories/{repo_a['id']}/overview", headers=bob).json()["totals"]["events"] == before_total

    demoted = client.patch(
        f"/api/repositories/{repo_a['id']}/access/{ids['bob']}", json={"role": "MEMBER"}, headers=alice
    )
    assert demoted.status_code == 200 and demoted.json()["role"] == "MEMBER"
    assert client.get(f"/api/repositories/{repo_b['id']}", headers=bob).json()["current_user_role"] == "ADMIN"
    last_admin = client.patch(
        f"/api/repositories/{repo_a['id']}/access/{ids['alice']}", json={"role": "MEMBER"}, headers=alice
    )
    assert last_admin.status_code == 409
    assert client.get(f"/api/repositories/{repo_a['id']}", headers=alice).json()["current_user_role"] == "ADMIN"


def test_invalid_repository_role_is_rejected(access_app):
    client, _, ids = access_app
    alice = auth(client, "alice")
    repository = analyze(client, alice, "demo/roles")["repository"]
    response = client.patch(
        f"/api/repositories/{repository['id']}/access/{ids['bob']}",
        json={"role": "OWNER"}, headers=alice,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analyze_race_loser_reloads_existing_without_admin_or_sync(tmp_path, monkeypatch):
    engine = build_engine(f"sqlite:///{tmp_path / 'race.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        winner = AuthService(db).create_user(UserCreate(
            username="winner", display_name="Winner", password=PASSWORD, role=UserRole.MEMBER
        ))
        loser = AuthService(db).create_user(UserCreate(
            username="loser", display_name="Loser", password=PASSWORD, role=UserRole.MEMBER
        ))

        async def simulate_race_win(_service, payload, github):
            info = await github.get_repository_info(payload.owner, payload.repo)
            repository = Repository(
                owner=info["owner_login"], name=info["name"], full_name=info["full_name"],
                github_repo_id=info["id"], html_url=info["html_url"],
                description=info["description"], default_branch=info["default_branch"],
                is_private=info["private"],
            )
            db.add(repository)
            db.commit()
            db.refresh(repository)
            RepositoryAccessService(db).grant_access(repository.id, winner.id, UserRole.ADMIN)
            raise ConflictError("Repository already exists")

        monkeypatch.setattr(RepositoryService, "create", simulate_race_win)
        with pytest.raises(ForbiddenError):
            await RepositoryAnalyzeService(db, Settings()).analyze(
                "race/repository", AccessGitHub(), loser
            )

        repository = db.scalar(select(Repository).where(Repository.full_name == "race/repository"))
        assert RepositoryAccessService(db).get_repository_role(repository.id, loser.id) == UserRole.MEMBER
        assert db.scalar(select(RepositoryAccess).where(
            RepositoryAccess.repository_id == repository.id,
            RepositoryAccess.user_id == loser.id,
        )) is None
        assert db.scalar(select(func.count(SyncRecord.id))) == 0
    engine.dispose()
