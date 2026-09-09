from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database.db import Base, build_engine, get_db
from app.database.models import ContributionEventRecord, Repository, RepositoryAccess, SyncRecord, User, UserContact, VerificationCode
from app.github.service import GitHubService
from app.main import app
from app.models.contribution import ContributionEvent, EventType
from app.models.schemas import MemberCreate, UserCreate, UserRole, VerificationPurpose
from app.routes.github import get_service
from app.services.auth_service import AuthService
from app.services.errors import AuthenticationError, TooManyRequestsError
from app.services.member_service import MemberService
from app.services.repository_analyze_service import parse_repository_input
from app.services.verification_service import VerificationService


SECRET = "verification-test-secret-long-enough"
JWT_SECRET = "jwt-test-secret-that-is-more-than-thirty-two-bytes-long"


class CapturingProvider:
    def __init__(self):
        self.sent = []

    def send(self, target, code):
        self.sent.append((target, code))


class AnalyzeGitHub:
    def __init__(self):
        self.max_pages = 10
        self.max_prs_for_reviews = 50

    async def get_repository_info(self, owner, repo):
        return {
            "id": 8000 + sum(ord(char) for char in f"{owner}/{repo}"), "name": repo, "full_name": f"{owner}/{repo}", "owner_login": owner,
            "html_url": f"https://github.com/{owner}/{repo}", "description": "Mock",
            "default_branch": "main", "private": False,
        }

    async def get_all_contribution_events(self, owner, repo):
        item = ContributionEvent(
            event_id="commit:analyze", repository=f"{owner}/{repo}", event_type=EventType.COMMIT,
            author_login="External-Dev", title="Evidence", source_id="analyze",
            github_url=f"https://github.com/{owner}/{repo}/commit/analyze",
            created_at=datetime(2026, 9, 3, tzinfo=timezone.utc), metadata={},
        )
        return {"commits": [item], "pull_requests": [], "issues": [], "reviews": [], "all": [item]}


@pytest.fixture
def completion_app(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("VERIFICATION_CODE_SECRET", SECRET)
    provider = CapturingProvider()
    monkeypatch.setattr(
        "app.services.verification_service.build_verification_provider", lambda settings: provider
    )
    engine = build_engine(f"sqlite:///{tmp_path / 'completion.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        AuthService(db).create_user(UserCreate(
            username="admin", display_name="Admin", password="admin-pass-123", role=UserRole.ADMIN
        ))
        AuthService(db).create_user(UserCreate(
            username="member", display_name="Member", password="member-pass-123", role=UserRole.MEMBER
        ))

    def override_db():
        with Session() as db:
            yield db

    github = AnalyzeGitHub()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_service] = lambda: github
    client = TestClient(app)
    yield client, Session, provider, github
    app.dependency_overrides.clear()
    engine.dispose()


def token(client, username, password):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.parametrize("raw, expected", [
    ("pallets/flask", ("pallets", "flask")),
    ("https://github.com/pallets/flask/", ("pallets", "flask")),
    ("https://www.github.com/pallets/flask.git", ("pallets", "flask")),
])
def test_repository_parser_accepts_supported_inputs(raw, expected):
    assert parse_repository_input(raw) == expected


@pytest.mark.parametrize("raw", [
    "https://gitlab.com/a/b", "https://github.com/a/b/issues", "owner", "a/b/c",
    "https://github.com/a/b?tab=readme",
])
def test_repository_parser_rejects_unsupported_inputs(raw):
    with pytest.raises(ValueError):
        parse_repository_input(raw)


def test_registration_password_and_code_login_are_secure_and_compatible(completion_app):
    client, Session, provider, _ = completion_app
    sent = client.post("/api/auth/verification/send", json={
        "email": " New.User@Example.com ", "purpose": "REGISTER"
    })
    assert sent.status_code == 200 and "code" not in sent.json()
    email, code = provider.sent[-1]
    assert len(code) == 6 and code.isdigit()
    assert code not in sent.text
    registered = client.post("/api/auth/register", json={
        "username": "NewUser", "email": email, "verification_code": code,
        "password": "new-user-pass", "confirm_password": "new-user-pass",
    })
    assert registered.status_code == 201
    assert registered.json()["role"] == "MEMBER" and "access_token" not in registered.json()
    assert client.post("/api/auth/login", json={
        "identifier": "new.user@example.com", "password": "new-user-pass"
    }).status_code == 200
    assert client.post("/api/auth/login", json={
        "username": "NEWUSER", "password": "new-user-pass"
    }).status_code == 200
    assert client.post("/api/auth/verification/send", json={
        "email": email, "purpose": "LOGIN"
    }).status_code == 200
    login_code = provider.sent[-1][1]
    assert client.post("/api/auth/login/code", json={
        "email": email, "verification_code": login_code
    }).status_code == 200
    with Session() as db:
        contact = db.scalar(select(UserContact).where(UserContact.email == email))
        records = list(db.scalars(select(VerificationCode).where(VerificationCode.target == email)))
        assert contact.email_verified is True
        assert all(record.code_digest not in {code, login_code} for record in records)
        assert all(len(record.code_digest) == 64 for record in records)


def test_registration_rejects_duplicates_role_injection_and_password_mismatch(completion_app):
    client, _, provider, _ = completion_app
    assert client.post("/api/auth/register", json={
        "username": "bad", "email": "bad@example.com", "verification_code": "123456",
        "password": "password-one", "confirm_password": "password-two",
    }).status_code == 422
    client.post("/api/auth/verification/send", json={"email": "first@example.com", "purpose": "REGISTER"})
    code = provider.sent[-1][1]
    assert client.post("/api/auth/register", json={
        "username": "member", "email": "first@example.com", "verification_code": code,
        "password": "password-one", "confirm_password": "password-one",
    }).status_code == 409
    assert client.post("/api/auth/register", json={
        "username": "attempt-admin", "email": "first@example.com", "verification_code": code,
        "password": "password-one", "confirm_password": "password-one", "role": "ADMIN",
    }).status_code == 422


def test_disabled_user_code_login_is_rejected_without_account_disclosure(completion_app):
    client, Session, provider, _ = completion_app
    with Session() as db:
        user = AuthService(db).create_user(UserCreate(
            username="disabled", display_name="Disabled", email="disabled@example.com",
            password="disabled-pass-123", role=UserRole.MEMBER,
        ))
        AuthService(db).update_user(
            user.id, type("Update", (), {"display_name": None, "role": None, "is_active": False})()
        )
    response = client.post("/api/auth/verification/send", json={
        "email": "disabled@example.com", "purpose": "LOGIN",
    })
    assert response.status_code == 200
    assert response.json()["message"] == "If the account exists, a verification code has been sent"
    assert provider.sent == []
    rejected = client.post("/api/auth/login/code", json={
        "email": "disabled@example.com", "verification_code": "123456",
    })
    assert rejected.status_code in {401, 403}


def test_verification_cooldown_attempt_limit_expiry_and_single_use(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'codes.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    provider = CapturingProvider()
    with Session() as db:
        service = VerificationService(db, Settings(verification_code_secret=SECRET), provider)
        service.send("one@example.com", VerificationPurpose.REGISTER)
        with pytest.raises(TooManyRequestsError):
            service.send("one@example.com", VerificationPurpose.REGISTER)
        correct = provider.sent[-1][1]
        for _ in range(5):
            with pytest.raises(AuthenticationError):
                service.verify("one@example.com", VerificationPurpose.REGISTER, "000000")
        with pytest.raises(AuthenticationError):
            service.verify("one@example.com", VerificationPurpose.REGISTER, correct)

        service.send("expired@example.com", VerificationPurpose.REGISTER)
        expired_code = provider.sent[-1][1]
        record = db.scalar(select(VerificationCode).where(VerificationCode.target == "expired@example.com"))
        record.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        db.commit()
        with pytest.raises(AuthenticationError):
            service.verify("expired@example.com", VerificationPurpose.REGISTER, expired_code)

        service.send("used@example.com", VerificationPurpose.REGISTER)
        used_code = provider.sent[-1][1]
        service.verify("used@example.com", VerificationPurpose.REGISTER, used_code)
        with pytest.raises(AuthenticationError):
            service.verify("used@example.com", VerificationPurpose.REGISTER, used_code)
    engine.dispose()


def test_unknown_login_is_generic_and_smtp_misconfiguration_is_503(completion_app, monkeypatch):
    client, _, provider, _ = completion_app
    response = client.post("/api/auth/verification/send", json={
        "email": "missing@example.com", "purpose": "LOGIN"
    })
    assert response.status_code == 200 and provider.sent == []
    monkeypatch.setenv("VERIFICATION_PROVIDER", "smtp")
    from app.services.email_provider import SMTPVerificationProvider
    monkeypatch.setattr(
        "app.services.verification_service.build_verification_provider",
        lambda settings: SMTPVerificationProvider(settings),
    )
    response = client.post("/api/auth/verification/send", json={
        "email": "smtp@example.com", "purpose": "REGISTER"
    })
    assert response.status_code == 503
    assert response.json() == {"detail": "Email service unavailable"}
    assert "SMTP_" not in response.text and "verification code" not in response.text.lower()


def test_analyze_reuses_repository_obeys_scope_and_rbac(completion_app):
    client, Session, _, github = completion_app
    admin = token(client, "admin", "admin-pass-123")
    member = token(client, "member", "member-pass-123")
    with Session() as db:
        before = (
            db.scalar(select(func.count(Repository.id))),
            db.scalar(select(func.count(SyncRecord.id))),
            db.scalar(select(func.count(ContributionEventRecord.id))),
        )
    assert client.post("/api/repositories/analyze", json={"repository": "other/repo"}).status_code == 401
    with Session() as db:
        assert before == (
            db.scalar(select(func.count(Repository.id))),
            db.scalar(select(func.count(SyncRecord.id))),
            db.scalar(select(func.count(ContributionEventRecord.id))),
        )
    member_created = client.post(
        "/api/repositories/analyze", json={"repository": "member/workspace"}, headers=member
    )
    assert member_created.status_code == 200
    assert member_created.json()["created"] is True
    assert member_created.json()["repository"]["current_user_role"] == "ADMIN"
    with Session() as db:
        member_user = db.scalar(select(User).where(User.username == "member"))
        access = db.scalar(select(RepositoryAccess).where(
            RepositoryAccess.repository_id == member_created.json()["repository"]["id"],
            RepositoryAccess.user_id == member_user.id,
        ))
        assert member_user.role == "MEMBER" and access.role == "ADMIN"
    assert client.post(
        "/api/repositories/analyze", json={"repository": "member/workspace"}, headers=admin
    ).status_code == 403
    first = client.post("/api/repositories/analyze", json={
        "repository": "https://github.com/other/repo.git/"
    }, headers=admin)
    assert first.status_code == 200 and first.json()["created"] is True
    assert first.json()["analysis_scope"] == {
        "max_pages": 1, "max_prs_for_reviews": 5, "scope_limited": True
    }
    second = client.post("/api/repositories/analyze", json={"repository": "OTHER/REPO"}, headers=admin)
    assert second.status_code == 200 and second.json()["created"] is False
    assert second.json()["sync"]["inserted"] == 0
    assert github.max_pages == 1 and github.max_prs_for_reviews == 5


def test_contributor_analytics_include_unmapped_mapping_bot_filter_and_timeline(completion_app):
    client, Session, _, _ = completion_app
    admin = token(client, "admin", "admin-pass-123")
    member_headers = token(client, "member", "member-pass-123")
    analyzed = client.post("/api/repositories/analyze", json={"repository": "other/repo"}, headers=admin)
    repository_id = analyzed.json()["repository"]["id"]
    with Session() as db:
        repository = db.get(Repository, repository_id)
        db.add_all([
            ContributionEventRecord(
                repository_id=repository.id, event_id="issue:ext", event_type="ISSUE",
                author_login="external-dev", title="Issue", source_id="ext",
                github_url="https://github.com/other/repo/issues/1",
                event_created_at=datetime(2026, 9, 3), metadata_json={},
            ),
            ContributionEventRecord(
                repository_id=repository.id, event_id="commit:bot", event_type="COMMIT",
                author_login="dependabot[bot]", title="Bot", source_id="bot",
                github_url="https://github.com/other/repo/commit/bot",
                event_created_at=datetime(2026, 9, 4), metadata_json={},
            ),
        ])
        db.commit()
    path = f"/api/repositories/{repository_id}/contributor-stats"
    before = client.get(path, headers=member_headers)
    assert before.status_code == 200
    assert [row["github_username"] for row in before.json()] == ["external-dev"]
    total_before = before.json()[0]["total_events"]
    with_bot = client.get(path + "?exclude_bots=false", headers=member_headers)
    assert any(row["is_bot"] for row in with_bot.json())
    assert [row["rank"] for row in with_bot.json()] == list(range(1, len(with_bot.json()) + 1))

    with Session() as db:
        mapped_user = AuthService(db).authenticate("member", "member-pass-123")
        _, remapped = MemberService(db).create(repository_id, MemberCreate(
            display_name="External Student", github_username="EXTERNAL-DEV", user_id=mapped_user.id
        ))
        assert remapped == 2
    after = client.get(path, headers=member_headers).json()[0]
    assert after["total_events"] == total_before
    assert after["is_mapped"] is True and after["display_name"] == "External Student"
    assert after["user_id"] is not None and after["member_id"] is not None
    detail = client.get(
        f"/api/repositories/{repository_id}/contributors/EXTERNAL-DEV", headers=member_headers
    )
    assert detail.status_code == 200
    timeline = client.get(
        f"/api/repositories/{repository_id}/contributors/external-dev/timeline", headers=member_headers
    )
    assert timeline.status_code == 200 and timeline.json()[0]["total"] == 2
    evidence = client.get(
        f"/api/repositories/{repository_id}/events?author_login=EXTERNAL-DEV", headers=member_headers
    )
    assert evidence.status_code == 200 and evidence.json()["total"] == 2


def test_local_frontend_cors_is_explicit(completion_app):
    client, _, _, _ = completion_app
    response = client.options("/api/auth/login", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_contribution_index_is_authenticated_read_only_and_rejects_zero_active_weights(completion_app):
    client, Session, _, _ = completion_app
    admin = token(client, "admin", "admin-pass-123")
    analyzed = client.post("/api/repositories/analyze", json={"repository": "rci/repo"}, headers=admin)
    repository_id = analyzed.json()["repository"]["id"]
    path = f"/api/repositories/{repository_id}/contribution-index"
    assert client.get(path).status_code == 401
    with Session() as db:
        before = db.scalar(select(func.count(ContributionEventRecord.id)))
    response = client.get(path, headers=admin)
    assert response.status_code == 200
    assert response.json()["methodology_version"] == "RCI_V1"
    assert response.json()["mode"] == "RESEARCH_BASELINE"
    rejected = client.get(
        path + "?weight_code=0&weight_pr=0&weight_issue=0&weight_review=0", headers=admin
    )
    assert rejected.status_code == 422
    with Session() as db:
        assert db.scalar(select(func.count(ContributionEventRecord.id))) == before
