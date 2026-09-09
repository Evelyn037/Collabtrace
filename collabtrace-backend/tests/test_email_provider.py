import logging
import ssl

import pytest

from app.config import Settings
from app.services import email_provider
from app.services.email_provider import ConsoleVerificationProvider, SMTPVerificationProvider
from app.services.errors import ServiceUnavailableError


class FakeSMTP:
    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.starttls_context = None
        self.login_args = None
        self.message = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def starttls(self, *, context):
        self.starttls_context = context

    def login(self, username, password):
        self.login_args = (username, password)

    def send_message(self, message):
        self.message = message


def smtp_settings(**overrides):
    values = {
        "verification_provider": "smtp",
        "smtp_host": "smtp.qq.com",
        "smtp_port": 587,
        "smtp_username": "sender@example.com",
        "smtp_password": "smtp-authorization-secret",
        "smtp_from": "sender@example.com",
        "smtp_use_starttls": True,
    }
    values.update(overrides)
    return Settings(**values)


def test_smtp_provider_uses_timeout_starttls_login_and_send_message(monkeypatch, capsys):
    instances = []
    monkeypatch.delenv("SSLKEYLOGFILE", raising=False)

    def factory(host, port, timeout):
        instance = FakeSMTP(host, port, timeout)
        instances.append(instance)
        return instance

    monkeypatch.setattr(email_provider.smtplib, "SMTP", factory)
    SMTPVerificationProvider(smtp_settings()).send("recipient@example.com", "123456")

    smtp = instances[0]
    assert (smtp.host, smtp.port, smtp.timeout) == ("smtp.qq.com", 587, 15)
    assert isinstance(smtp.starttls_context, ssl.SSLContext)
    assert smtp.login_args == ("sender@example.com", "smtp-authorization-secret")
    assert smtp.message["To"] == "recipient@example.com"
    assert "123456" in smtp.message.get_content()
    assert capsys.readouterr().out == ""


def test_smtp_transport_failure_is_safe_and_does_not_log_secrets(monkeypatch, caplog):
    def fail(*_args, **_kwargs):
        raise OSError("transport details must remain internal")

    monkeypatch.setattr(email_provider.smtplib, "SMTP", fail)
    with caplog.at_level(logging.WARNING):
        with pytest.raises(ServiceUnavailableError, match="^Email service unavailable$"):
            SMTPVerificationProvider(smtp_settings()).send("recipient@example.com", "654321")

    assert "OSError" in caplog.text
    assert "654321" not in caplog.text
    assert "smtp-authorization-secret" not in caplog.text
    assert "transport details must remain internal" not in caplog.text


@pytest.mark.parametrize(
    ("settings", "missing_name"),
    [
        (smtp_settings(smtp_host=None), "SMTP_HOST"),
        (smtp_settings(smtp_from=None), "SMTP_FROM"),
        (smtp_settings(smtp_password=None), "SMTP_PASSWORD"),
        (smtp_settings(smtp_username=None), "SMTP_USERNAME"),
    ],
)
def test_incomplete_smtp_configuration_fails_safely(settings, missing_name, caplog):
    with caplog.at_level(logging.WARNING):
        with pytest.raises(ServiceUnavailableError, match="^Email service unavailable$"):
            SMTPVerificationProvider(settings).send("recipient@example.com", "123456")

    assert missing_name in caplog.text
    assert "123456" not in caplog.text
    assert "smtp-authorization-secret" not in caplog.text


def test_console_provider_remains_development_fallback(capsys):
    ConsoleVerificationProvider().send("developer@example.com", "123456")
    output = capsys.readouterr().out
    assert "developer@example.com" in output
    assert "123456" in output
