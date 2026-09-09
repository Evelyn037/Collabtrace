from __future__ import annotations

import getpass
import secrets
import sys
from pathlib import Path

from pydantic import ValidationError

from app.config import PROJECT_ROOT, load_settings
from app.database.db import SessionLocal, init_db
from app.models.schemas import UserCreate, UserRole
from app.services.auth_service import AuthService
from app.services.errors import ConflictError, NotFoundError
from app.database.models import Repository, User
from app.services.repository_access_service import RepositoryAccessService
from app.services.demo_cleanup_service import apply_demo_cleanup, build_demo_cleanup_plan
from sqlalchemy import func, select


def init_jwt_secret() -> int:
    env_path = PROJECT_ROOT / ".env"
    settings = load_settings(env_path)
    if settings.jwt_secret:
        print("JWT_SECRET is already configured in .env")
        return 0
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    secret_line = f"JWT_SECRET={secrets.token_urlsafe(48)}"
    replaced = False
    for index, line in enumerate(lines):
        if line.strip().startswith("JWT_SECRET="):
            lines[index] = secret_line
            replaced = True
            break
    if not replaced:
        lines.append(secret_line)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("JWT_SECRET generated and stored in .env")
    return 0


def init_verification_secret() -> int:
    env_path = PROJECT_ROOT / ".env"
    settings = load_settings(env_path)
    if settings.verification_code_secret:
        print("Verification code secret is already configured in .env")
        return 0
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    secret_line = f"VERIFICATION_CODE_SECRET={secrets.token_urlsafe(48)}"
    for index, line in enumerate(lines):
        if line.strip().startswith("VERIFICATION_CODE_SECRET="):
            lines[index] = secret_line
            break
    else:
        lines.append(secret_line)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Verification code secret generated and stored in .env")
    return 0


def prompt_password() -> str | None:
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        print("Passwords do not match", file=sys.stderr)
        return None
    return password


def create_user_cli(role: UserRole) -> int:
    init_db()
    username = input("Username: ")
    display_name = input("Display name: ")
    password = prompt_password()
    if password is None:
        return 1
    try:
        payload = UserCreate(
            username=username, display_name=display_name, password=password, role=role
        )
        with SessionLocal() as db:
            user = AuthService(db).create_user(payload)
        print(f"{user.role} user created: {user.username}")
        return 0
    except (ValidationError, ConflictError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def set_password_cli(username: str) -> int:
    init_db()
    password = prompt_password()
    if password is None:
        return 1
    try:
        UserCreate(username="placeholder", display_name="placeholder", password=password)
        with SessionLocal() as db:
            AuthService(db).set_password(username, password)
        print("Password updated")
        return 0
    except (ValidationError, NotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def grant_repository_admin_cli() -> int:
    init_db()
    repository_name = input("Repository: ").strip()
    username = input("Username: ").strip()
    with SessionLocal() as db:
        repository = db.scalar(
            select(Repository).where(func.lower(Repository.full_name) == repository_name.lower())
        )
        user = db.scalar(select(User).where(func.lower(User.username) == username.lower()))
        if repository is None or user is None:
            print("Repository or user not found", file=sys.stderr)
            return 1
        confirmation = input(
            f"Grant ADMIN access to user {user.username} for repository {repository.full_name}? [Y/N] "
        ).strip().lower()
        if confirmation not in {"y", "yes"}:
            print("Cancelled")
            return 1
        RepositoryAccessService(db).grant_access(repository.id, user.id, UserRole.ADMIN)
    print("Repository ADMIN access granted")
    return 0


def cleanup_demo_data_cli(apply: bool = False) -> int:
    init_db()
    with SessionLocal() as db:
        plan = build_demo_cleanup_plan(db)
        print("Demo cleanup mode:", "APPLY" if apply else "DRY RUN")
        print("Users:", ", ".join(plan.usernames) or "None")
        print("Repositories:", ", ".join(plan.repositories) or "None")
        for name, count in plan.counts.items():
            print(f"  {name}: {count}")
        if plan.blocked_users:
            print("Blocked users (linked outside cleanup scope):", ", ".join(plan.blocked_users))
        if apply:
            apply_demo_cleanup(db, plan)
            print("Cleanup applied")
        else:
            print("No data changed. Re-run with --apply after reviewing this plan.")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if args == ["init-jwt-secret"]:
        return init_jwt_secret()
    if args == ["init-verification-secret"]:
        return init_verification_secret()
    if args == ["create-admin"]:
        return create_user_cli(UserRole.ADMIN)
    if args == ["create-member"]:
        return create_user_cli(UserRole.MEMBER)
    if len(args) == 2 and args[0] == "set-password":
        return set_password_cli(args[1])
    if args == ["grant-repository-admin"]:
        return grant_repository_admin_cli()
    if args == ["cleanup-demo-data"]:
        return cleanup_demo_data_cli()
    if args == ["cleanup-demo-data", "--apply"]:
        return cleanup_demo_data_cli(apply=True)
    print("Usage: python -m app.cli {init-jwt-secret|init-verification-secret|create-admin|create-member|grant-repository-admin|cleanup-demo-data [--apply]|set-password USERNAME}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
