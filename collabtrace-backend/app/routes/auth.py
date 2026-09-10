from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.db import get_db
from app.dependencies.auth import CurrentUser
from app.models.schemas import (
    LoginRequest, LoginResponse, MembershipResponse, RegistrationRequest,
    RegistrationResponse, UserSummary,
)
from app.security.jwt import create_access_token
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["Auth"])
DB = Annotated[Session, Depends(get_db)]


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: DB):
    settings = get_settings()
    user = AuthService(db).authenticate(payload.identifier or payload.username or "", payload.password)
    return _login_response(user, settings)


@router.post("/register", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegistrationRequest, db: DB):
    return AuthService(db).register(payload)


def _login_response(user, settings):
    token = create_access_token(user, settings)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
        "user": user,
    }


@router.get("/me", response_model=UserSummary)
def me(user: CurrentUser):
    return user


@router.get("/me/memberships", response_model=list[MembershipResponse])
def my_memberships(user: CurrentUser, db: DB):
    return AuthService(db).memberships(user.id)
