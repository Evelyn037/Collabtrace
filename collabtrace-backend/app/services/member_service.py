from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.database.models import ContributionEventRecord, Member, Repository, User
from app.models.schemas import MemberCreate, MemberUpdate
from app.services.errors import ConflictError, NotFoundError


class MemberService:
    def __init__(self, db: Session):
        self.db = db

    def _repository(self, repository_id: int) -> Repository:
        repository = self.db.get(Repository, repository_id)
        if repository is None:
            raise NotFoundError("Repository not found")
        return repository

    def _normalize_username(self, value: str) -> str:
        username = value.strip().lower()
        if not username:
            raise ValueError("github_username must not be blank")
        return username

    def _ensure_unique(self, repository_id: int, username: str, exclude_id: int | None = None) -> None:
        query = select(Member).where(Member.repository_id == repository_id, Member.github_username == username)
        if exclude_id is not None:
            query = query.where(Member.id != exclude_id)
        if self.db.scalar(query):
            raise ConflictError("GitHub username already mapped in this repository")

    def create(self, repository_id: int, payload: MemberCreate) -> tuple[Member, int]:
        self._repository(repository_id)
        username = self._normalize_username(payload.github_username)
        self._ensure_unique(repository_id, username)
        if payload.user_id is not None:
            if self.db.get(User, payload.user_id) is None:
                raise NotFoundError("User not found")
            if self.db.scalar(select(Member).where(Member.repository_id == repository_id, Member.user_id == payload.user_id)):
                raise ConflictError("User already has a member mapping in this repository")
        member = Member(
            repository_id=repository_id, user_id=payload.user_id,
            display_name=payload.display_name.strip(), github_username=username
        )
        self.db.add(member)
        self.db.flush()
        remapped = self._map_unassigned(repository_id, member)
        self.db.commit()
        self.db.refresh(member)
        return member, remapped

    def list(self, repository_id: int) -> list[dict]:
        self._repository(repository_id)
        rows = self.db.execute(
            select(Member, func.count(ContributionEventRecord.id))
            .outerjoin(ContributionEventRecord, ContributionEventRecord.member_id == Member.id)
            .where(Member.repository_id == repository_id)
            .group_by(Member.id).order_by(Member.id)
        ).all()
        return [{**member.__dict__, "mapped_event_count": count} for member, count in rows]

    def update(self, repository_id: int, member_id: int, payload: MemberUpdate) -> tuple[Member, int]:
        self._repository(repository_id)
        member = self.db.scalar(select(Member).where(Member.id == member_id, Member.repository_id == repository_id))
        if member is None:
            raise NotFoundError("Member not found")
        if payload.display_name is not None:
            member.display_name = payload.display_name.strip()
        remapped = 0
        if payload.github_username is not None:
            username = self._normalize_username(payload.github_username)
            self._ensure_unique(repository_id, username, member_id)
            self.db.execute(
                update(ContributionEventRecord)
                .where(ContributionEventRecord.repository_id == repository_id, ContributionEventRecord.member_id == member_id)
                .values(member_id=None)
            )
            member.github_username = username
            self.db.flush()
            remapped = self._map_unassigned(repository_id, member)
        self.db.commit()
        self.db.refresh(member)
        return member, remapped

    def _map_unassigned(self, repository_id: int, member: Member) -> int:
        result = self.db.execute(
            update(ContributionEventRecord)
            .where(
                ContributionEventRecord.repository_id == repository_id,
                ContributionEventRecord.member_id.is_(None),
                func.lower(ContributionEventRecord.author_login) == member.github_username,
            )
            .values(member_id=member.id)
        )
        return result.rowcount
