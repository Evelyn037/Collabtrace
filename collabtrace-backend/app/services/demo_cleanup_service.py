from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.database.models import (
    ContributionEventRecord,
    Member,
    Repository,
    RepositoryAccess,
    SyncRecord,
    User,
    UserContact,
    UserCredential,
    VerificationCode,
)


_AUTOMATED_ACCOUNT_PATTERNS = (
    re.compile(r"^acceptance_[0-9a-f]{8}$", re.IGNORECASE),
    re.compile(r"^acceptance_(?:alice|bob)_\d+$", re.IGNORECASE),
    re.compile(r"^phase3b_[0-9a-f]{12}$", re.IGNORECASE),
)


@dataclass(frozen=True)
class DemoCleanupPlan:
    user_ids: tuple[int, ...]
    usernames: tuple[str, ...]
    repository_ids: tuple[int, ...]
    repositories: tuple[str, ...]
    counts: dict[str, int]
    blocked_users: tuple[str, ...]


def _is_automated_account(user: User) -> bool:
    if not any(pattern.fullmatch(user.username) for pattern in _AUTOMATED_ACCOUNT_PATTERNS):
        return False
    return user.contact is None or user.contact.email.lower().endswith("@example.com")


def build_demo_cleanup_plan(db: Session) -> DemoCleanupPlan:
    candidates = [user for user in db.scalars(select(User).order_by(User.id)) if _is_automated_account(user)]
    candidate_ids = {user.id for user in candidates}

    repository_ids: set[int] = set()
    for repository in db.scalars(select(Repository).order_by(Repository.id)):
        access_user_ids = {access.user_id for access in repository.accesses}
        mapped_user_ids = {member.user_id for member in repository.members if member.user_id is not None}
        if access_user_ids and access_user_ids <= candidate_ids and mapped_user_ids <= candidate_ids:
            repository_ids.add(repository.id)

    safe_users: list[User] = []
    blocked_users: list[str] = []
    for user in candidates:
        access_repository_ids = {access.repository_id for access in user.repository_accesses}
        if access_repository_ids <= repository_ids:
            safe_users.append(user)
        else:
            blocked_users.append(user.username)

    user_ids = {user.id for user in safe_users}
    contact_targets = set(db.scalars(select(UserContact.email).where(UserContact.user_id.in_(user_ids)))) if user_ids else set()

    def count(model: type, condition) -> int:
        return int(db.scalar(select(func.count()).select_from(model).where(condition)) or 0)

    if repository_ids:
        repository_condition = Repository.id.in_(repository_ids)
        access_condition = RepositoryAccess.repository_id.in_(repository_ids)
        member_condition = Member.repository_id.in_(repository_ids)
        event_condition = ContributionEventRecord.repository_id.in_(repository_ids)
        sync_condition = SyncRecord.repository_id.in_(repository_ids)
    else:
        repository_condition = Repository.id == -1
        access_condition = RepositoryAccess.id == -1
        member_condition = Member.id == -1
        event_condition = ContributionEventRecord.id == -1
        sync_condition = SyncRecord.id == -1

    counts = {
        "users": len(user_ids),
        "repositories": count(Repository, repository_condition),
        "repository_accesses": count(RepositoryAccess, access_condition),
        "members": count(Member, member_condition),
        "member_mappings_unlinked": count(Member, Member.user_id.in_(user_ids)) if user_ids else 0,
        "contribution_events": count(ContributionEventRecord, event_condition),
        "sync_records": count(SyncRecord, sync_condition),
        "user_contacts": count(UserContact, UserContact.user_id.in_(user_ids)) if user_ids else 0,
        "user_credentials": count(UserCredential, UserCredential.user_id.in_(user_ids)) if user_ids else 0,
        "verification_codes": count(VerificationCode, VerificationCode.target.in_(contact_targets)) if contact_targets else 0,
    }
    repositories = tuple(db.scalars(select(Repository.full_name).where(repository_condition).order_by(Repository.id)))
    return DemoCleanupPlan(
        user_ids=tuple(sorted(user_ids)),
        usernames=tuple(user.username for user in safe_users),
        repository_ids=tuple(sorted(repository_ids)),
        repositories=repositories,
        counts=counts,
        blocked_users=tuple(blocked_users),
    )


def apply_demo_cleanup(db: Session, plan: DemoCleanupPlan) -> None:
    contact_targets: set[str] = set()
    if plan.user_ids:
        contact_targets = set(db.scalars(select(UserContact.email).where(UserContact.user_id.in_(plan.user_ids))))
        if contact_targets:
            db.execute(delete(VerificationCode).where(VerificationCode.target.in_(contact_targets)))
    if plan.repository_ids:
        db.execute(delete(ContributionEventRecord).where(ContributionEventRecord.repository_id.in_(plan.repository_ids)))
        db.execute(delete(Member).where(Member.repository_id.in_(plan.repository_ids)))
        db.execute(delete(SyncRecord).where(SyncRecord.repository_id.in_(plan.repository_ids)))
        db.execute(delete(RepositoryAccess).where(RepositoryAccess.repository_id.in_(plan.repository_ids)))
        db.execute(delete(Repository).where(Repository.id.in_(plan.repository_ids)))
    if plan.user_ids:
        db.execute(update(Member).where(Member.user_id.in_(plan.user_ids)).values(user_id=None))
        db.execute(delete(RepositoryAccess).where(RepositoryAccess.user_id.in_(plan.user_ids)))
        db.execute(delete(UserContact).where(UserContact.user_id.in_(plan.user_ids)))
        db.execute(delete(UserCredential).where(UserCredential.user_id.in_(plan.user_ids)))
        db.execute(delete(User).where(User.id.in_(plan.user_ids)))
    db.commit()
