from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database.db import Base, build_engine, get_db
from app.database.models import ContributionEventRecord, SyncRecord, UserCredential
from app.github.service import GitHubService
from app.main import app
from app.models.contribution import ContributionEvent, EventType
from app.models.schemas import UserCreate, UserRole
from app.routes.github import get_service
from app.security.jwt import create_access_token, decode_access_token
from app.security.passwords import hash_password, verify_password
from app.services.auth_service import AuthService
from app.services.errors import AuthenticationError


TEST_SECRET = "unit-test-secret-that-is-long-enough-and-not-production"
ADMIN_PASSWORD = "admin-pass-123"
MEMBER_PASSWORD = "member-pass-123"


class FakeGitHubClient:
    token_configured = True
    rate_limit = SimpleNamespace(limit=5000, remaining=4999, reset=1)

    async def get(self, path):
        assert path == "/rate_limit"
        return {"resources": {"core": {"limit": 5000, "remaining": 4999, "reset": 1}}}


class FakeGitHubService:
    client = FakeGitHubClient()

    async def get_repository_info(self, owner, repo):
        return {
            "id": 321, "name": repo, "full_name": f"{owner}/{repo}", "owner_login": owner,
            "html_url": f"https://github.com/{owner}/{repo}", "description": "Mock",
            "default_branch": "main", "private": False, "created_at": None, "updated_at": None,
        }

    async def get_all_contribution_events(self, owner, repo):
        event = ContributionEvent(
            event_id="commit:mock", repository=f"{owner}/{repo}", event_type=EventType.COMMIT,
            author_login="member-gh", title="Mock commit",
            created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            github_url=f"https://github.com/{owner}/{repo}/commit/mock", source_id="mock",
            metadata={"sha": "mock"},
        )
        return {"commits": [event], "pull_requests": [], "issues": [], "reviews": [], "all": [event]}


@pytest.fixture
def auth_app(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480")
    engine = build_engine(f"sqlite:///{tmp_path / 'auth-test.db'}")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    with TestSession() as db:
        admin = AuthService(db).create_user(UserCreate(
            username="Admin", display_name="Administrator", password=ADMIN_PASSWORD, role=UserRole.ADMIN
        ))
        member = AuthService(db).create_user(UserCreate(
            username="Member", display_name="Team Member", password=MEMBER_PASSWORD, role=UserRole.MEMBER
        ))
        admin_id, member_id = admin.id, member.id

    def override_db():
        with TestSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_service] = lambda: FakeGitHubService()
    client = TestClient(app)
    yield client, TestSession, admin_id, member_id
    app.dependency_overrides.clear()
    engine.dispose()


def login(client, username, password):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_password_hash_is_argon2_and_never_plaintext():
    raw = "safe-password-123"
    hashed = hash_password(raw)
    assert hashed != raw and hashed.startswith("$argon2")
    assert verify_password(raw, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_jwt_valid_expired_malformed_and_invalid_signature():
    user = SimpleNamespace(id=7, username="alice", role="MEMBER")
    settings = Settings(jwt_secret=TEST_SECRET, jwt_algorithm="HS256")
    token = create_access_token(user, settings)
    payload = decode_access_token(token, settings)
    assert payload["user_id"] == 7 and payload["role"] == "MEMBER"
    expired = create_access_token(user, settings, timedelta(seconds=-1))
    with pytest.raises(AuthenticationError, match="expired"):
        decode_access_token(expired, settings)
    with pytest.raises(AuthenticationError):
        decode_access_token("not-a-jwt", settings)
    with pytest.raises(AuthenticationError):
        decode_access_token(
            token,
            Settings(jwt_secret="different-test-secret-that-is-also-long-enough", jwt_algorithm="HS256"),
        )


def test_login_me_and_inactive_user(auth_app):
    client, TestSession, _, member_id = auth_app
    admin_login = login(client, " ADMIN ", ADMIN_PASSWORD)
    member_login = login(client, "member", MEMBER_PASSWORD)
    assert admin_login.status_code == 200 and admin_login.json()["user"]["role"] == "ADMIN"
    assert member_login.status_code == 200 and member_login.json()["user"]["role"] == "MEMBER"
    assert login(client, "missing", MEMBER_PASSWORD).status_code == 401
    assert login(client, "member", "bad").status_code == 401
    assert client.get("/api/auth/me").status_code == 401
    token = member_login.json()["access_token"]
    assert client.get("/api/auth/me", headers=headers(token)).status_code == 200
    with TestSession() as db:
        AuthService(db).update_user(member_id, SimpleNamespace(display_name=None, role=None, is_active=False))
    assert login(client, "member", MEMBER_PASSWORD).status_code == 403
    assert client.get("/api/auth/me", headers=headers(token)).status_code == 403


def test_user_management_and_no_hash_exposure(auth_app):
    client, _, _, _ = auth_app
    admin_token = login(client, "admin", ADMIN_PASSWORD).json()["access_token"]
    member_token = login(client, "member", MEMBER_PASSWORD).json()["access_token"]
    payload = {"username": "Bob", "display_name": "Bob", "password": "bob-pass-123", "role": "MEMBER"}
    created = client.post("/api/users", json=payload, headers=headers(admin_token))
    assert created.status_code == 201
    assert client.post("/api/users", json={**payload, "username": "BOB"}, headers=headers(admin_token)).status_code == 409
    assert client.post("/api/users", json={**payload, "username": "other"}, headers=headers(member_token)).status_code == 403
    listed = client.get("/api/users", headers=headers(admin_token))
    assert listed.status_code == 200
    assert "password" not in listed.text.lower()
    assert client.get("/api/users", headers=headers(member_token)).status_code == 403


def test_rbac_mutations_reads_and_github_diagnostics(auth_app):
    client, TestSession, _, member_user_id = auth_app
    admin_token = login(client, "admin", ADMIN_PASSWORD).json()["access_token"]
    member_token = login(client, "member", MEMBER_PASSWORD).json()["access_token"]
    admin_headers, member_headers = headers(admin_token), headers(member_token)

    repo_payload = {"owner": "owner", "repo": "repo"}
    assert client.post("/api/repositories", json=repo_payload, headers=member_headers).status_code == 403
    created = client.post("/api/repositories", json=repo_payload, headers=admin_headers)
    assert created.status_code == 201
    repository_id = created.json()["id"]
    member_payload = {
        "display_name": "Mapped", "github_username": "member-gh", "user_id": member_user_id
    }
    assert client.post(f"/api/repositories/{repository_id}/members", json=member_payload, headers=member_headers).status_code == 403
    mapped = client.post(f"/api/repositories/{repository_id}/members", json=member_payload, headers=admin_headers)
    assert mapped.status_code == 201
    mapping_id = mapped.json()["member"]["id"]
    memberships = client.get("/api/auth/me/memberships", headers=member_headers)
    assert memberships.status_code == 200
    assert memberships.json()[0]["repository_full_name"] == "owner/repo"
    assert client.patch(f"/api/repositories/{repository_id}/members/{mapping_id}", json={"display_name": "No"}, headers=member_headers).status_code == 403
    assert client.patch(f"/api/repositories/{repository_id}/members/{mapping_id}", json={"display_name": "Updated"}, headers=admin_headers).status_code == 200

    with TestSession() as db:
        sync_before = db.scalar(select(func.count(SyncRecord.id)))
        events_before = db.scalar(select(func.count(ContributionEventRecord.id)))
    assert client.post(f"/api/repositories/{repository_id}/sync", headers=member_headers).status_code == 403
    with TestSession() as db:
        assert db.scalar(select(func.count(SyncRecord.id))) == sync_before
        assert db.scalar(select(func.count(ContributionEventRecord.id))) == events_before
    assert client.post(f"/api/repositories/{repository_id}/sync", headers=admin_headers).status_code == 200

    read_paths = [
        "/api/repositories", f"/api/repositories/{repository_id}",
        f"/api/repositories/{repository_id}/members", f"/api/repositories/{repository_id}/syncs",
        f"/api/repositories/{repository_id}/events", f"/api/repositories/{repository_id}/overview",
        f"/api/repositories/{repository_id}/member-stats", f"/api/repositories/{repository_id}/timeline",
        f"/api/repositories/{repository_id}/members/{mapping_id}/timeline",
    ]
    assert all(client.get(path, headers=member_headers).status_code == 200 for path in read_paths)
    unmapped = f"/api/repositories/{repository_id}/unmapped-contributors"
    assert client.get(unmapped, headers=member_headers).status_code == 403
    assert client.get(unmapped, headers=admin_headers).status_code == 200
    assert client.get("/api/github/auth-status").status_code == 401
    assert client.get("/api/github/auth-status", headers=member_headers).status_code == 403
    assert client.get("/api/github/auth-status", headers=admin_headers).status_code == 200
