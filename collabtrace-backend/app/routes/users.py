from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.dependencies.auth import AdminUser
from app.models.schemas import UserCreate, UserResponse, UserUpdate
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/users", tags=["Users"])
DB = Annotated[Session, Depends(get_db)]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: DB, _: AdminUser):
    user = AuthService(db).create_user(payload)
    return AuthService._user_dict(user, user.credential.is_active)


@router.get("", response_model=list[UserResponse])
def list_users(db: DB, _: AdminUser):
    return AuthService(db).list_users()


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, payload: UserUpdate, db: DB, _: AdminUser):
    return AuthService(db).update_user(user_id, payload)
