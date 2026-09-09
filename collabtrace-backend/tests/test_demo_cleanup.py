from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database.db import Base
from app.database.models import ContributionEventRecord, Member, Repository, RepositoryAccess, User, UserContact, UserCredential
from app.services.demo_cleanup_service import apply_demo_cleanup, build_demo_cleanup_plan


def add_user(db: Session, username: str, email: str | None = None) -> User:
    user = User(username=username, display_name=username, role="MEMBER")
    user.credential = UserCredential(password_hash="not-a-real-password", is_active=True)
    if email:
        user.contact = UserContact(email=email, email_verified=True)
    db.add(user)
    db.flush()
    return user


def add_repository(db: Session, repository_id: int, full_name: str) -> Repository:
    repository = Repository(owner=full_name.split('/')[0], name=full_name.split('/')[1], full_name=full_name, github_repo_id=repository_id, html_url=f"https://github.com/{full_name}", default_branch="main", is_private=False)
    db.add(repository)
    db.flush()
    return repository


def test_cleanup_plan_is_narrow_and_apply_removes_only_automated_scope(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'cleanup.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        real = add_user(db, "team_admin", "team@example.org")
        automated = add_user(db, "acceptance_alice_1234567890")
        acceptance_repository = add_repository(db, 1, "demo/acceptance")
        real_repository = add_repository(db, 2, "demo/real")
        db.add_all([
            RepositoryAccess(repository_id=acceptance_repository.id, user_id=automated.id, role="ADMIN"),
            RepositoryAccess(repository_id=real_repository.id, user_id=real.id, role="ADMIN"),
            ContributionEventRecord(repository_id=acceptance_repository.id, event_id="commit:1", event_type="COMMIT", title="Acceptance", source_id="1", metadata_json={}),
        ])
        db.commit()

        plan = build_demo_cleanup_plan(db)
        assert plan.usernames == (automated.username,)
        assert plan.repositories == ("demo/acceptance",)
        assert plan.counts["contribution_events"] == 1
        assert db.scalar(select(User).where(User.id == automated.id)) is not None

        apply_demo_cleanup(db, plan)
        assert db.scalar(select(User).where(User.id == automated.id)) is None
        assert db.scalar(select(Repository).where(Repository.id == acceptance_repository.id)) is None
        assert db.scalar(select(User).where(User.id == real.id)) is not None
        assert db.scalar(select(Repository).where(Repository.id == real_repository.id)) is not None


def test_cleanup_blocks_candidate_linked_to_a_non_candidate_repository(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'blocked.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        automated = add_user(db, "phase3b_abcdef123456", "phase3b_abcdef123456@example.com")
        real = add_user(db, "member_demo")
        shared = add_repository(db, 3, "demo/shared")
        db.add_all([
            RepositoryAccess(repository_id=shared.id, user_id=automated.id, role="ADMIN"),
            RepositoryAccess(repository_id=shared.id, user_id=real.id, role="MEMBER"),
        ])
        db.commit()

        plan = build_demo_cleanup_plan(db)
        assert plan.usernames == ()
        assert plan.repositories == ()
        assert plan.blocked_users == (automated.username,)


def test_cleanup_unlinks_automated_user_without_deleting_real_repository_member(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mapping.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        automated = add_user(db, "acceptance_abcdef12", "acceptance-abcdef12@example.com")
        real_repository = add_repository(db, 4, "demo/kept")
        member = Member(repository_id=real_repository.id, user_id=automated.id, display_name="Kept Contributor", github_username="kept-dev")
        db.add(member)
        db.commit()

        plan = build_demo_cleanup_plan(db)
        assert plan.usernames == (automated.username,)
        assert plan.repositories == ()
        assert plan.counts["member_mappings_unlinked"] == 1
        apply_demo_cleanup(db, plan)

        assert db.scalar(select(User).where(User.id == automated.id)) is None
        kept_member = db.scalar(select(Member).where(Member.id == member.id))
        assert kept_member is not None
        assert kept_member.user_id is None
        assert db.scalar(select(Repository).where(Repository.id == real_repository.id)) is not None


def test_cleanup_preserves_repository_with_a_real_user_member_mapping(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mapped-real-user.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        automated = add_user(db, "acceptance_1234abcd", "acceptance_1234abcd@example.com")
        real = add_user(db, "real_member", "real@example.org")
        repository = add_repository(db, 5, "demo/mapped-real-user")
        db.add_all([
            RepositoryAccess(repository_id=repository.id, user_id=automated.id, role="ADMIN"),
            Member(repository_id=repository.id, user_id=real.id, display_name="Real Member", github_username="real-dev"),
        ])
        db.commit()

        plan = build_demo_cleanup_plan(db)
        assert plan.repositories == ()
        assert plan.usernames == ()
        assert plan.blocked_users == (automated.username,)
