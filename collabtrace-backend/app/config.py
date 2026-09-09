import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseModel):
    github_token: str | None = None
    github_base_url: str = "https://api.github.com"
    github_timeout_seconds: float = 20.0
    default_max_pages: int | None = 10
    default_max_prs_for_reviews: int | None = 50
    database_url: str = "sqlite:///./data/collabtrace.db"
    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    verification_code_secret: str | None = None
    verification_provider: str = "console"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_use_starttls: bool = True
    quick_analyze_max_pages: int = 1
    quick_analyze_max_prs_for_reviews: int = 5
    frontend_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )


def load_settings(env_file: Path | None = None) -> Settings:
    """Read settings without caching so edits to .env apply to the next request."""
    values = dotenv_values(env_file or PROJECT_ROOT / ".env")
    raw_token = os.getenv("GITHUB_TOKEN")
    if raw_token is None:
        raw_token = values.get("GITHUB_TOKEN")
    token = raw_token.strip() if isinstance(raw_token, str) else None
    database_url = os.getenv("DATABASE_URL") or values.get("DATABASE_URL")
    raw_jwt_secret = os.getenv("JWT_SECRET")
    if raw_jwt_secret is None:
        raw_jwt_secret = values.get("JWT_SECRET")
    jwt_secret = raw_jwt_secret.strip() if isinstance(raw_jwt_secret, str) else None
    def value(name: str, default: str = "") -> str:
        return str(os.getenv(name) or values.get(name) or default).strip()

    verification_secret = value("VERIFICATION_CODE_SECRET") or None
    origins = [origin.strip() for origin in value(
        "FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if origin.strip()]
    return Settings(
        github_token=token or None,
        database_url=(database_url or "sqlite:///./data/collabtrace.db").strip(),
        jwt_secret=jwt_secret or None,
        jwt_algorithm=(os.getenv("JWT_ALGORITHM") or values.get("JWT_ALGORITHM") or "HS256").strip(),
        access_token_expire_minutes=int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")
            or values.get("ACCESS_TOKEN_EXPIRE_MINUTES") or 480
        ),
        verification_code_secret=verification_secret,
        verification_provider=value("VERIFICATION_PROVIDER", "console").lower(),
        smtp_host=value("SMTP_HOST") or None,
        smtp_port=int(value("SMTP_PORT", "587")),
        smtp_username=value("SMTP_USERNAME") or None,
        smtp_password=value("SMTP_PASSWORD") or None,
        smtp_from=value("SMTP_FROM") or None,
        smtp_use_starttls=value("SMTP_USE_STARTTLS", "true").lower() in {"1", "true", "yes"},
        quick_analyze_max_pages=int(value("QUICK_ANALYZE_MAX_PAGES", "1")),
        quick_analyze_max_prs_for_reviews=int(value("QUICK_ANALYZE_MAX_PRS_FOR_REVIEWS", "5")),
        frontend_origins=origins,
    )


def get_settings() -> Settings:
    return load_settings()
