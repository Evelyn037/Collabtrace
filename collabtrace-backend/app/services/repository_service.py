from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database.models import ContributionEventRecord, Member, Repository
from app.github.service import GitHubService
from app.models.schemas import RepositoryCreate
from app.services.errors import ConflictError, NotFoundError


class RepositoryService:
    def __init__(self, db: Session):
        self.db = db

    async def create(self, payload: RepositoryCreate, github: GitHubService) -> Repository:
        owner, repo = payload.owner.strip(), payload.repo.strip()
        full_name = f"{owner}/{repo}"
        existing = self.db.scalar(select(Repository).where(func.lower(Repository.full_name) == full_name.lower()))
        if existing:
            raise ConflictError("Repository already exists")
        info = await github.get_repository_info(owner, repo)
        record = Repository(
            owner=str(info["owner_login"]).strip(), name=str(info["name"]).strip(),
            full_name=str(info["full_name"]).strip(), github_repo_id=int(info["id"]),
            html_url=str(info["html_url"]), description=info["description"],
            default_branch=str(info["default_branch"]), is_private=bool(info["private"]),
        )
        self.db.add(record)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("Repository already exists") from exc
        self.db.refresh(record)
        return record

    def list(self) -> list[Repository]:
        return list(self.db.scalars(select(Repository).order_by(Repository.id)))

    def get(self, repository_id: int) -> Repository:
        repository = self.db.get(Repository, repository_id)
        if repository is None:
            raise NotFoundError("Repository not found")
        return repository

    def detail(self, repository_id: int) -> dict:
        repository = self.get(repository_id)
        member_count = self.db.scalar(select(func.count(Member.id)).where(Member.repository_id == repository_id)) or 0
        event_count = self.db.scalar(select(func.count(ContributionEventRecord.id)).where(ContributionEventRecord.repository_id == repository_id)) or 0
        return {**repository.__dict__, "member_count": member_count, "event_count": event_count}
