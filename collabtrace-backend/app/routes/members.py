from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.dependencies.auth import CurrentUser, RepositoryAdminUser
from app.models.schemas import MemberCreate, MemberMutationResponse, MemberResponse, MemberUpdate
from app.services.member_service import MemberService

router = APIRouter(prefix="/api/repositories/{repository_id}/members", tags=["Members"])
DB = Annotated[Session, Depends(get_db)]


@router.post("", response_model=MemberMutationResponse, status_code=201)
def create_member(repository_id: int, payload: MemberCreate, db: DB, _: RepositoryAdminUser):
    member, remapped = MemberService(db).create(repository_id, payload)
    return {"member": {**member.__dict__, "mapped_event_count": remapped}, "remapped_events": remapped}


@router.get("", response_model=list[MemberResponse])
def list_members(repository_id: int, db: DB, _: CurrentUser):
    return MemberService(db).list(repository_id)


@router.patch("/{member_id}", response_model=MemberMutationResponse)
def update_member(repository_id: int, member_id: int, payload: MemberUpdate, db: DB, _: RepositoryAdminUser):
    member, remapped = MemberService(db).update(repository_id, member_id, payload)
    return {"member": {**member.__dict__, "mapped_event_count": remapped}, "remapped_events": remapped}
