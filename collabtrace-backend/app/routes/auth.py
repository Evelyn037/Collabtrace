from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.db import get_db
from app.dependencies.auth import CurrentUser
from app.models.schemas import (
    LoginRequest, LoginResponse, MembershipResponse, RegistrationRequest,
    RegistrationResponse, UserSummary, VerificationCodeLoginRequest,
    VerificationSendRequest,
)
from app.security.jwt import create_access_token
from app.services.auth_service import AuthService
from app.services.verification_service import VerificationService

router = APIRouter(prefix="/api/auth", tags=["Auth"])
DB = Annotated[Session, Depends(get_db)]


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: DB):
    settings = get_settings()
    user = AuthService(db).authenticate(payload.identifier or payload.username or "", payload.password)
    return _login_response(user, settings)


@router.post("/verification/send")
def send_verification(payload: VerificationSendRequest, db: DB):
    settings = get_settings()
    message = VerificationService(db, settings).send(str(payload.email), payload.purpose)
    return {"message": message}


@router.post("/register", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegistrationRequest, db: DB):
    settings = get_settings()
    return AuthService(db).register(payload, VerificationService(db, settings))


@router.post("/login/code", response_model=LoginResponse)
def login_code(payload: VerificationCodeLoginRequest, db: DB):
    settings = get_settings()
    user = AuthService(db).authenticate_code(
        str(payload.email), payload.verification_code, VerificationService(db, settings)
    )
    return _login_response(user, settings)


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
