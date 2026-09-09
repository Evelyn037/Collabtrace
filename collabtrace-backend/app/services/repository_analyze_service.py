import asyncio
import logging
import secrets
from urllib.parse import urlsplit

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.models import Repository, User
from app.github.service import GitHubService
from app.models.schemas import RepositoryCreate
from app.services.repository_service import RepositoryService
from app.services.sync_service import SyncService
from app.services.errors import ConflictError, ForbiddenError
from app.services.repository_access_service import RepositoryAccessService
from app.models.schemas import UserRole


flow_logger = logging.getLogger("collabtrace.flow")


def parse_repository_input(value: str) -> tuple[str, str]:
    raw = value.strip()
    if "://" in raw:
        parsed = urlsplit(raw)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname is None
            or parsed.hostname.lower() not in {"github.com", "www.github.com"}
            or parsed.port is not None
            or parsed.username is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Repository must be an owner/repo pair or a GitHub URL")
        raw = parsed.path.strip("/")
    else:
        raw = raw.strip("/")
    parts = raw.split("/")
    if len(parts) != 2 or not all(parts) or any(part in {".", ".."} for part in parts):
        raise ValueError("Repository must be an owner/repo pair or a GitHub URL")
    owner, repo = parts
    if repo.lower().endswith(".git"):
        repo = repo[:-4]
    if not repo or any(char.isspace() for char in owner + repo):
        raise ValueError("Repository must be an owner/repo pair or a GitHub URL")
    return owner, repo


class RepositoryAnalyzeService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings

    async def analyze(self, repository_input: str, github: GitHubService, current_user: User) -> dict:
        owner, repo = parse_repository_input(repository_input)
        full_name = f"{owner}/{repo}"
        flow_id = secrets.token_hex(4)
        flow_logger.info("[FLOW] Analyze started flow_id=%s repository=%s", flow_id, full_name)
        try:
            repository = self.db.scalar(
                select(Repository).where(func.lower(Repository.full_name) == full_name.lower())
            )
            created = repository is None
            if repository is None:
                try:
                    repository = await RepositoryService(self.db).create(
                        RepositoryCreate(owner=owner, repo=repo), github
                    )
                except ConflictError:
                    repository = self.db.scalar(
                        select(Repository).where(func.lower(Repository.full_name) == full_name.lower())
                    )
                    if repository is None:
                        raise
                    created = False
                if created:
                    RepositoryAccessService(self.db).grant_access(
                        repository.id, current_user.id, UserRole.ADMIN
                    )
            flow_logger.info(
                "[FLOW] Repository resolved flow_id=%s repository=%s created=%s repository_id=%s",
                flow_id, repository.full_name, str(created).lower(), repository.id,
            )
            if not created and not RepositoryAccessService(self.db).is_repository_admin(
                repository.id, current_user.id
            ):
                raise ForbiddenError(
                    "Repository already exists. Repository administrator permission is required to refresh it."
                )
            github.max_pages = self.settings.quick_analyze_max_pages
            github.max_prs_for_reviews = self.settings.quick_analyze_max_prs_for_reviews
            sync = await SyncService(self.db).sync(repository.id, github, flow_id=flow_id)
            result = {
                "repository": {**repository.__dict__, "current_user_role": UserRole.ADMIN.value},
                "created": created,
                "sync": sync,
                "analysis_scope": {
                    "max_pages": self.settings.quick_analyze_max_pages,
                    "max_prs_for_reviews": self.settings.quick_analyze_max_prs_for_reviews,
                    "scope_limited": True,
                },
            }
            flow_logger.info(
                "[FLOW] Analyze complete flow_id=%s repository=%s repository_id=%s status=%s",
                flow_id, repository.full_name, repository.id, sync["status"],
            )
            return result
        except (Exception, asyncio.CancelledError) as exc:
            flow_logger.warning(
                "[FLOW] Analyze failed flow_id=%s repository=%s reason=%s",
                flow_id, full_name, type(exc).__name__,
            )
            raise
