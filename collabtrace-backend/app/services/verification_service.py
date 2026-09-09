from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.models import UserContact, UserCredential, VerificationCode
from app.models.schemas import VerificationPurpose
from app.services.email_provider import VerificationProvider, build_verification_provider
from app.services.errors import AuthenticationError, ConflictError, ServiceUnavailableError, TooManyRequestsError


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_email(email: str) -> str:
    return email.strip().lower()


class VerificationService:
    def __init__(self, db: Session, settings: Settings, provider: VerificationProvider | None = None):
        self.db = db
        self.settings = settings
        self.provider = provider or build_verification_provider(settings)

    def _digest(self, email: str, purpose: str, code: str) -> str:
        if not self.settings.verification_code_secret:
            raise ServiceUnavailableError("Verification service unavailable")
        message = f"{purpose}:{email}:{code}".encode()
        return hmac.new(
            self.settings.verification_code_secret.encode(), message, hashlib.sha256
        ).hexdigest()

    def send(self, email: str, purpose: VerificationPurpose) -> str:
        target = normalize_email(email)
        contact = self.db.scalar(select(UserContact).where(UserContact.email == target))
        if purpose == VerificationPurpose.REGISTER and contact is not None:
            raise ConflictError("Email already registered")
        if purpose == VerificationPurpose.LOGIN:
            active_contact = self.db.scalar(
                select(UserContact)
                .join(UserCredential, UserCredential.user_id == UserContact.user_id)
                .where(UserContact.email == target, UserContact.email_verified.is_(True), UserCredential.is_active.is_(True))
            )
            if active_contact is None:
                return "If the account exists, a verification code has been sent"

        now = utc_now_naive()
        latest = self.db.scalar(
            select(VerificationCode)
            .where(VerificationCode.target == target, VerificationCode.purpose == purpose.value)
            .order_by(VerificationCode.created_at.desc()).limit(1)
        )
        if latest and latest.created_at.replace(tzinfo=None) > now - timedelta(seconds=60):
            raise TooManyRequestsError("Please wait before requesting another verification code")

        code = f"{secrets.randbelow(1_000_000):06d}"
        self.db.execute(
            update(VerificationCode)
            .where(VerificationCode.target == target, VerificationCode.purpose == purpose.value, VerificationCode.used_at.is_(None))
            .values(used_at=now)
        )
        record = VerificationCode(
            target=target, purpose=purpose.value,
            code_digest=self._digest(target, purpose.value, code),
            expires_at=now + timedelta(minutes=5), created_at=now,
        )
        self.db.add(record)
        try:
            self.provider.send(target, code)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return (
            "Verification code sent" if purpose == VerificationPurpose.REGISTER
            else "If the account exists, a verification code has been sent"
        )

    def verify(self, email: str, purpose: VerificationPurpose, code: str, commit: bool = True) -> VerificationCode:
        target = normalize_email(email)
        record = self.db.scalar(
            select(VerificationCode)
            .where(VerificationCode.target == target, VerificationCode.purpose == purpose.value, VerificationCode.used_at.is_(None))
            .order_by(VerificationCode.created_at.desc()).limit(1)
        )
        now = utc_now_naive()
        invalid = AuthenticationError("Invalid or expired verification code")
        if record is None or record.expires_at.replace(tzinfo=None) <= now or record.attempt_count >= 5:
            raise invalid
        expected = self._digest(target, purpose.value, code)
        if not hmac.compare_digest(record.code_digest, expected):
            record.attempt_count += 1
            self.db.commit()
            raise invalid
        record.used_at = now
        if commit:
            self.db.commit()
        return record
