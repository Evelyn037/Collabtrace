from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database.models import User, UserCredential
from app.security.jwt import decode_access_token
from app.services.errors import AuthenticationError, ForbiddenError
from app.services.repository_access_service import RepositoryAccessService

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="JWTBearer")


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Authentication required")
    payload = decode_access_token(credentials.credentials)
    row = db.execute(
        select(User, UserCredential)
        .join(UserCredential, UserCredential.user_id == User.id)
        .where(User.id == payload["user_id"], User.username == payload["sub"])
    ).one_or_none()
    if row is None:
        raise AuthenticationError("Invalid access token")
    user, credential = row
    if not credential.is_active:
        raise ForbiddenError("Account is disabled")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "ADMIN":
        raise ForbiddenError("Administrator permission required")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]


def require_repository_admin(
    repository_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    RepositoryAccessService(db).require_repository_admin(repository_id, user.id)
    return user


RepositoryAdminUser = Annotated[User, Depends(require_repository_admin)]
