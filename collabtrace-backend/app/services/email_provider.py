import smtplib
import logging
import ssl
from email.message import EmailMessage
from typing import Protocol

from app.config import Settings
from app.services.errors import ServiceUnavailableError


logger = logging.getLogger(__name__)


class VerificationProvider(Protocol):
    def send(self, email: str, code: str) -> None: ...


class ConsoleVerificationProvider:
    def send(self, email: str, code: str) -> None:
        print(f"CollabTrace verification code for {email}: {code}", flush=True)


class SMTPVerificationProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, email: str, code: str) -> None:
        config = self.settings
        missing = []
        if not config.smtp_host:
            missing.append("SMTP_HOST")
        if not config.smtp_from:
            missing.append("SMTP_FROM")
        if config.smtp_username and not config.smtp_password:
            missing.append("SMTP_PASSWORD")
        if config.smtp_password and not config.smtp_username:
            missing.append("SMTP_USERNAME")
        if missing:
            logger.warning("SMTP configuration incomplete: %s missing", ", ".join(missing))
            raise ServiceUnavailableError("Email service unavailable")
        message = EmailMessage()
        message["Subject"] = "CollabTrace verification code"
        message["From"] = config.smtp_from
        message["To"] = email
        message.set_content(
            f"Your CollabTrace verification code is {code}.\n\nThis code expires in 5 minutes."
        )
        try:
            with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15) as smtp:
                if config.smtp_use_starttls:
                    smtp.starttls(context=ssl.create_default_context())
                if config.smtp_username and config.smtp_password:
                    smtp.login(config.smtp_username, config.smtp_password)
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            logger.warning("SMTP delivery failed: %s", type(exc).__name__)
            raise ServiceUnavailableError("Email service unavailable") from exc


def build_verification_provider(settings: Settings) -> VerificationProvider:
    if settings.verification_provider == "console":
        return ConsoleVerificationProvider()
    if settings.verification_provider == "smtp":
        return SMTPVerificationProvider(settings)
    raise ServiceUnavailableError("Email service unavailable")
