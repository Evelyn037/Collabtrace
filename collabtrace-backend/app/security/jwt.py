from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.config import Settings, get_settings
from app.database.models import User
from app.services.errors import AuthenticationError


def _settings(settings: Settings | None) -> Settings:
    resolved = settings or get_settings()
    if not resolved.jwt_secret:
        raise RuntimeError("JWT_SECRET is not configured; run python -m app.cli init-jwt-secret")
    return resolved


def create_access_token(
    user: User, settings: Settings | None = None, expires_delta: timedelta | None = None
) -> str:
    config = _settings(settings)
    now = datetime.now(timezone.utc)
    expires = now + (expires_delta or timedelta(minutes=config.access_token_expire_minutes))
    payload = {
        "sub": user.username,
        "user_id": user.id,
        "role": user.role,
        "iat": now,
        "exp": expires,
    }
    return jwt.encode(payload, config.jwt_secret, algorithm=config.jwt_algorithm)


def decode_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    config = _settings(settings)
    try:
        payload = jwt.decode(token, config.jwt_secret, algorithms=[config.jwt_algorithm])
        if not isinstance(payload.get("user_id"), int) or not payload.get("sub"):
            raise AuthenticationError("Invalid access token")
        return payload
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Access token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid access token") from exc
