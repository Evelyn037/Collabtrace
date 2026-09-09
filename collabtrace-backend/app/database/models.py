from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="MEMBER")

    credential: Mapped[UserCredential | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    contact: Mapped[UserContact | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    repository_accesses: Mapped[list[RepositoryAccess]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def email(self) -> str | None:
        return self.contact.email if self.contact else None

    @property
    def email_verified(self) -> bool | None:
        return self.contact.email_verified if self.contact else None


class Repository(TimestampMixin, Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    github_repo_id: Mapped[int] = mapped_column(Integer, unique=True)
    html_url: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_branch: Mapped[str] = mapped_column(String(255))
    is_private: Mapped[bool] = mapped_column(default=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    members: Mapped[list[Member]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    events: Mapped[list[ContributionEventRecord]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    syncs: Mapped[list[SyncRecord]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    accesses: Mapped[list[RepositoryAccess]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )


class RepositoryAccess(TimestampMixin, Base):
    __tablename__ = "repository_accesses"
    __table_args__ = (
        UniqueConstraint("repository_id", "user_id", name="uq_repository_access_repo_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="MEMBER")

    repository: Mapped[Repository] = relationship(back_populates="accesses")
    user: Mapped[User] = relationship(back_populates="repository_accesses")


class Member(TimestampMixin, Base):
    __tablename__ = "members"
    __table_args__ = (UniqueConstraint("repository_id", "github_username", name="uq_member_repo_username"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    display_name: Mapped[str] = mapped_column(String(200))
    github_username: Mapped[str] = mapped_column(String(100))
    github_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    repository: Mapped[Repository] = relationship(back_populates="members")
    events: Mapped[list[ContributionEventRecord]] = relationship(back_populates="member")


class ContributionEventRecord(TimestampMixin, Base):
    __tablename__ = "contribution_events"
    __table_args__ = (
        UniqueConstraint("repository_id", "event_id", name="uq_event_repo_event_id"),
        Index("ix_event_repo_author", "repository_id", "author_login"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), index=True)
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), nullable=True, index=True)
    event_id: Mapped[str] = mapped_column(String(300))
    event_type: Mapped[str] = mapped_column(String(30), index=True)
    author_login: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str] = mapped_column(String(300))
    github_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    event_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    repository: Mapped[Repository] = relationship(back_populates="events")
    member: Mapped[Member | None] = relationship(back_populates="events")


class SyncRecord(Base):
    __tablename__ = "sync_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="RUNNING")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_count: Mapped[int] = mapped_column(default=0)
    inserted_count: Mapped[int] = mapped_column(default=0)
    updated_count: Mapped[int] = mapped_column(default=0)
    unchanged_count: Mapped[int] = mapped_column(default=0)
    mapped_count: Mapped[int] = mapped_column(default=0)
    unmapped_count: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    repository: Mapped[Repository] = relationship(back_populates="syncs")


class UserCredential(TimestampMixin, Base):
    __tablename__ = "user_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(default=True)

    user: Mapped[User] = relationship(back_populates="credential")


class UserContact(TimestampMixin, Base):
    __tablename__ = "user_contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    email_verified: Mapped[bool] = mapped_column(default=False)

    user: Mapped[User] = relationship(back_populates="contact")


class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    target: Mapped[str] = mapped_column(String(320), index=True)
    purpose: Mapped[str] = mapped_column(String(20), index=True)
    code_digest: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
