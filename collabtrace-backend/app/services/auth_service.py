from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Member, Repository, User, UserContact, UserCredential
from app.models.schemas import RegistrationRequest, UserCreate, UserUpdate
from app.security.passwords import hash_password, verify_password
from app.services.errors import AuthenticationError, ConflictError, ForbiddenError, NotFoundError


def normalize_username(username: str) -> str:
    value = username.strip().lower()
    if not value:
        raise ValueError("username must not be blank")
    return value


def normalize_email(email: str) -> str:
    value = email.strip().lower()
    if not value:
        raise ValueError("email must not be blank")
    return value


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def create_user(self, payload: UserCreate) -> User:
        username = normalize_username(payload.username)
        if self.db.scalar(select(User).where(func.lower(User.username) == username)):
            raise ConflictError("Username already exists")
        email = normalize_email(str(payload.email)) if payload.email else None
        if email and self.db.scalar(select(UserContact).where(func.lower(UserContact.email) == email)):
            raise ConflictError("Email already exists")
        user = User(
            username=username,
            display_name=payload.display_name.strip(),
            role=payload.role.value,
        )
        user.credential = UserCredential(
            password_hash=hash_password(payload.password), is_active=True
        )
        if email:
            user.contact = UserContact(email=email, email_verified=True)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def authenticate(self, identifier: str, password: str) -> User:
        normalized = identifier.strip().lower()
        query = select(User, UserCredential).join(UserCredential, UserCredential.user_id == User.id)
        if "@" in normalized:
            query = query.join(UserContact, UserContact.user_id == User.id).where(
                func.lower(UserContact.email) == normalized
            )
        else:
            query = query.where(func.lower(User.username) == normalize_username(identifier))
        row = self.db.execute(query).one_or_none()
        if row is None or not verify_password(password, row.UserCredential.password_hash):
            raise AuthenticationError("Invalid identifier or password")
        if not row.UserCredential.is_active:
            raise ForbiddenError("Account is disabled")
        return row.User

    def register(self, payload: RegistrationRequest) -> User:
        username = normalize_username(payload.username)
        email = normalize_email(str(payload.email))
        if self.db.scalar(select(User.id).where(func.lower(User.username) == username)):
            raise ConflictError("Username already exists")
        if self.db.scalar(select(UserContact.id).where(func.lower(UserContact.email) == email)):
            raise ConflictError("Email already exists")
        try:
            user = User(username=username, display_name=payload.username.strip(), role="MEMBER")
            user.credential = UserCredential(
                password_hash=hash_password(payload.password), is_active=True
            )
            user.contact = UserContact(email=email, email_verified=False)
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            return user
        except Exception:
            self.db.rollback()
            raise

    def list_users(self) -> list[dict]:
        rows = self.db.execute(
            select(User, UserCredential.is_active)
            .join(UserCredential, UserCredential.user_id == User.id)
            .order_by(User.id)
        ).all()
        return [self._user_dict(user, is_active) for user, is_active in rows]

    def update_user(self, user_id: int, payload: UserUpdate) -> dict:
        row = self.db.execute(
            select(User, UserCredential)
            .join(UserCredential, UserCredential.user_id == User.id)
            .where(User.id == user_id)
        ).one_or_none()
        if row is None:
            raise NotFoundError("User not found")
        user, credential = row
        if payload.display_name is not None:
            user.display_name = payload.display_name.strip()
        if payload.role is not None:
            user.role = payload.role.value
        if payload.is_active is not None:
            credential.is_active = payload.is_active
        self.db.commit()
        self.db.refresh(user)
        return self._user_dict(user, credential.is_active)

    @staticmethod
    def _user_dict(user: User, is_active: bool) -> dict:
        return {
            **user.__dict__, "is_active": is_active, "email": user.email,
            "email_verified": user.email_verified,
        }

    def set_password(self, username: str, password: str) -> User:
        user = self.db.scalar(select(User).where(func.lower(User.username) == normalize_username(username)))
        if user is None:
            raise NotFoundError("User not found")
        if user.credential is None:
            user.credential = UserCredential(password_hash=hash_password(password), is_active=True)
        else:
            user.credential.password_hash = hash_password(password)
        self.db.commit()
        return user

    def memberships(self, user_id: int) -> list[dict]:
        rows = self.db.execute(
            select(Member, Repository.full_name)
            .join(Repository, Repository.id == Member.repository_id)
            .where(Member.user_id == user_id).order_by(Repository.full_name)
        ).all()
        return [
            {
                "repository_id": member.repository_id,
                "repository_full_name": full_name,
                "member_id": member.id,
                "display_name": member.display_name,
                "github_username": member.github_username,
            }
            for member, full_name in rows
        ]
