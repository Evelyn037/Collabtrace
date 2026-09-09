from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.dependencies.auth import AdminUser, CurrentUser, RepositoryAdminUser
from app.github.service import GitHubService
from app.models.schemas import RepositoryAccessResponse, RepositoryAccessUpdate, RepositoryAnalyzeRequest, RepositoryAnalyzeResponse, RepositoryCreate, RepositoryDetail, RepositoryResponse, SyncRecordResponse, SyncResponse, UserRole
from app.routes.github import get_service
from app.services.repository_service import RepositoryService
from app.services.repository_analyze_service import RepositoryAnalyzeService
from app.services.sync_service import SyncService
from app.services.repository_access_service import RepositoryAccessService

router = APIRouter(prefix="/api/repositories", tags=["Repositories"])
DB = Annotated[Session, Depends(get_db)]
GitHub = Annotated[GitHubService, Depends(get_service)]


@router.post("/analyze", response_model=RepositoryAnalyzeResponse)
async def analyze_repository(payload: RepositoryAnalyzeRequest, db: DB, github: GitHub, user: CurrentUser):
    from app.config import get_settings
    try:
        return await RepositoryAnalyzeService(db, get_settings()).analyze(payload.repository, github, user)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def create_repository(payload: RepositoryCreate, db: DB, github: GitHub, user: AdminUser):
    repository = await RepositoryService(db).create(payload, github)
    RepositoryAccessService(db).grant_access(repository.id, user.id, UserRole.ADMIN)
    return {**repository.__dict__, "current_user_role": "ADMIN"}


@router.get("", response_model=list[RepositoryResponse])
def list_repositories(db: DB, user: CurrentUser):
    access = RepositoryAccessService(db)
    return [
        {**repository.__dict__, "current_user_role": access.get_repository_role(repository.id, user.id).value}
        for repository in RepositoryService(db).list()
    ]


@router.get("/{repository_id}", response_model=RepositoryDetail)
def repository_detail(repository_id: int, db: DB, user: CurrentUser):
    return {
        **RepositoryService(db).detail(repository_id),
        "current_user_role": RepositoryAccessService(db).get_repository_role(repository_id, user.id).value,
    }


@router.post("/{repository_id}/sync", response_model=SyncResponse, tags=["Sync"])
async def sync_repository(repository_id: int, db: DB, github: GitHub, _: RepositoryAdminUser):
    return await SyncService(db).sync(repository_id, github)


@router.get("/{repository_id}/syncs", response_model=list[SyncRecordResponse], tags=["Sync"])
def sync_history(repository_id: int, db: DB, _: CurrentUser,
                 limit: Annotated[int, Query(ge=1, le=100)] = 20):
    return SyncService(db).history(repository_id, limit)


@router.get("/{repository_id}/access", response_model=list[RepositoryAccessResponse])
def list_repository_access(repository_id: int, db: DB, _: RepositoryAdminUser):
    return RepositoryAccessService(db).list_repository_access(repository_id)


@router.patch("/{repository_id}/access/{user_id}", response_model=RepositoryAccessResponse)
def update_repository_access(
    repository_id: int, user_id: int, payload: RepositoryAccessUpdate,
    db: DB, _: RepositoryAdminUser,
):
    RepositoryAccessService(db).update_access(repository_id, user_id, payload.role)
    return next(
        row for row in RepositoryAccessService(db).list_repository_access(repository_id)
        if row["user_id"] == user_id
    )
