import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.github.client import GitHubAPIError
from app.database.db import init_db
from app.routes.analytics import router as analytics_router
from app.routes.auth import router as auth_router
from app.routes.github import router as github_router
from app.routes.members import router as members_router
from app.routes.repositories import router as repositories_router
from app.routes.users import router as users_router
from app.config import get_settings
from app.services.errors import AuthenticationError, ConflictError, ForbiddenError, NotFoundError, ServiceUnavailableError, TooManyRequestsError
from app.database.db import SessionLocal
from app.services.repository_access_service import RepositoryAccessService

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with SessionLocal() as db:
        RepositoryAccessService.bootstrap_existing_repository_admins(db)
    yield


app = FastAPI(title="CollabTrace", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(github_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(repositories_router)
app.include_router(members_router)
app.include_router(analytics_router)


@app.exception_handler(GitHubAPIError)
async def github_error_handler(_: Request, exc: GitHubAPIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "rate_limit": exc.rate_limit.model_dump() if exc.rate_limit else None},
    )


@app.exception_handler(NotFoundError)
async def not_found_handler(_: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ConflictError)
async def conflict_handler(_: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(AuthenticationError)
async def authentication_handler(_: Request, exc: AuthenticationError) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"detail": str(exc)},
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(ForbiddenError)
async def forbidden_handler(_: Request, exc: ForbiddenError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(TooManyRequestsError)
async def too_many_requests_handler(_: Request, exc: TooManyRequestsError) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": str(exc)})


@app.exception_handler(ServiceUnavailableError)
async def service_unavailable_handler(_: Request, exc: ServiceUnavailableError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/health", tags=["System"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "CollabTrace GitHub PoC"}
