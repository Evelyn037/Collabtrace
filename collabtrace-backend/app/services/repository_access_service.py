import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Repository, RepositoryAccess, User, UserCredential
from app.models.schemas import UserRole
from app.services.errors import ConflictError, ForbiddenError, NotFoundError


logger = logging.getLogger(__name__)


class RepositoryAccessService:
    def __init__(self, db: Session):
        self.db = db

    def get_repository_role(self, repository_id: int, user_id: int) -> UserRole:
        if self.db.get(Repository, repository_id) is None:
            raise NotFoundError("Repository not found")
        role = self.db.scalar(
            select(RepositoryAccess.role).where(
                RepositoryAccess.repository_id == repository_id,
                RepositoryAccess.user_id == user_id,
            )
        )
        return UserRole(role or UserRole.MEMBER.value)

    def is_repository_admin(self, repository_id: int, user_id: int) -> bool:
        return self.get_repository_role(repository_id, user_id) == UserRole.ADMIN

    def require_repository_admin(self, repository_id: int, user_id: int) -> None:
        if not self.is_repository_admin(repository_id, user_id):
            raise ForbiddenError("Repository administrator permission required")

    def grant_access(self, repository_id: int, user_id: int, role: UserRole) -> RepositoryAccess:
        if self.db.get(Repository, repository_id) is None:
            raise NotFoundError("Repository not found")
        if self.db.get(User, user_id) is None:
            raise NotFoundError("User not found")
        access = self.db.scalar(
            select(RepositoryAccess).where(
                RepositoryAccess.repository_id == repository_id,
                RepositoryAccess.user_id == user_id,
            )
        )
        if access is None:
            access = RepositoryAccess(repository_id=repository_id, user_id=user_id, role=role.value)
            self.db.add(access)
        else:
            access.role = role.value
        self.db.commit()
        self.db.refresh(access)
        return access

    def update_access(self, repository_id: int, user_id: int, role: UserRole) -> RepositoryAccess:
        existing = self.db.scalar(
            select(RepositoryAccess).where(
                RepositoryAccess.repository_id == repository_id,
                RepositoryAccess.user_id == user_id,
            )
        )
        if existing and existing.role == UserRole.ADMIN.value and role == UserRole.MEMBER:
            administrators = self.db.scalar(
                select(func.count(RepositoryAccess.id)).where(
                    RepositoryAccess.repository_id == repository_id,
                    RepositoryAccess.role == UserRole.ADMIN.value,
                )
            ) or 0
            if administrators <= 1:
                raise ConflictError("Repository must have at least one administrator")
        return self.grant_access(repository_id, user_id, role)

    def list_repository_access(self, repository_id: int) -> list[dict]:
        if self.db.get(Repository, repository_id) is None:
            raise NotFoundError("Repository not found")
        explicit = {
            access.user_id: access.role
            for access in self.db.scalars(
                select(RepositoryAccess).where(RepositoryAccess.repository_id == repository_id)
            )
        }
        rows = self.db.execute(
            select(User, UserCredential)
            .join(UserCredential, UserCredential.user_id == User.id)
            .order_by(User.created_at, User.id)
        ).all()
        return [
            {
                "user_id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "email": user.email,
                "is_active": credential.is_active,
                "role": explicit.get(user.id, UserRole.MEMBER.value),
                "explicit": user.id in explicit,
            }
            for user, credential in rows
        ]

    @staticmethod
    def bootstrap_existing_repository_admins(db: Session) -> int:
        global_admin = db.scalar(
            select(User)
            .join(UserCredential, UserCredential.user_id == User.id)
            .where(User.role == UserRole.ADMIN.value, UserCredential.is_active.is_(True))
            .order_by(User.created_at, User.id)
            .limit(1)
        )
        created = 0
        for repository in db.scalars(select(Repository).order_by(Repository.id)):
            has_admin = db.scalar(
                select(RepositoryAccess.id).where(
                    RepositoryAccess.repository_id == repository.id,
                    RepositoryAccess.role == UserRole.ADMIN.value,
                ).limit(1)
            )
            if has_admin:
                continue
            if global_admin is None:
                logger.warning(
                    "Repository %s has no administrator; run grant-repository-admin recovery",
                    repository.full_name,
                )
                continue
            access = db.scalar(
                select(RepositoryAccess).where(
                    RepositoryAccess.repository_id == repository.id,
                    RepositoryAccess.user_id == global_admin.id,
                )
            )
            if access is None:
                db.add(RepositoryAccess(
                    repository_id=repository.id,
                    user_id=global_admin.id,
                    role=UserRole.ADMIN.value,
                ))
            else:
                access.role = UserRole.ADMIN.value
            created += 1
        if created:
            db.commit()
        return created
