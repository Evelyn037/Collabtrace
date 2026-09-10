from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import PROJECT_ROOT, get_settings


class Base(DeclarativeBase):
    pass


def normalize_database_url(database_url: str) -> str:
    """Select psycopg 3 for standard PostgreSQL URLs without exposing URL contents."""
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    return database_url


def build_engine(database_url: str):
    normalized_url = normalize_database_url(database_url)
    if normalized_url.startswith("sqlite"):
        return create_engine(normalized_url, connect_args={"check_same_thread": False})
    return create_engine(normalized_url, pool_pre_ping=True)


settings = get_settings()
if settings.database_url.startswith("sqlite:///./"):
    (PROJECT_ROOT / "data").mkdir(parents=True, exist_ok=True)

engine = build_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    from app.database import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
