import logging
import os
import smtplib
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

        stage = "message_construction"
        try:
            logger.info("[SMTP] stage=%s start", stage)
            message = EmailMessage()
            message["Subject"] = "CollabTrace verification code"
            message["From"] = config.smtp_from
            message["To"] = email
            message.set_content(
                f"Your CollabTrace verification code is {code}.\n\nThis code expires in 5 minutes."
            )
            logger.info("[SMTP] stage=%s success", stage)

            stage = "connect"
            logger.info("[SMTP] stage=%s start", stage)
            with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15) as smtp:
                logger.info("[SMTP] stage=%s success", stage)
                if config.smtp_use_starttls:
                    stage = "starttls"
                    logger.info("[SMTP] stage=%s start", stage)
                    smtp.starttls(context=ssl.create_default_context())
                    logger.info("[SMTP] stage=%s success", stage)
                if config.smtp_username and config.smtp_password:
                    stage = "login"
                    logger.info("[SMTP] stage=%s start", stage)
                    smtp.login(config.smtp_username, config.smtp_password)
                    logger.info("[SMTP] stage=%s success", stage)
                stage = "send_message"
                logger.info("[SMTP] stage=%s start", stage)
                smtp.send_message(message)
                logger.info("[SMTP] stage=%s success", stage)
                stage = "disconnect"
                logger.info("[SMTP] stage=%s start", stage)
            logger.info("[SMTP] stage=%s success", stage)
        except (OSError, smtplib.SMTPException, ValueError) as exc:
            ssl_keylogfile_set = stage == "starttls" and bool(os.environ.get("SSLKEYLOGFILE"))
            logger.warning(
                "[SMTP] stage=%s failed reason=%s sslkeylogfile_set=%s",
                stage,
                type(exc).__name__,
                str(ssl_keylogfile_set).lower(),
            )
            raise ServiceUnavailableError("Email service unavailable") from exc


def build_verification_provider(settings: Settings) -> VerificationProvider:
    if settings.verification_provider == "console":
        return ConsoleVerificationProvider()
    if settings.verification_provider == "smtp":
        return SMTPVerificationProvider(settings)
    raise ServiceUnavailableError("Email service unavailable")
