"""Tests for monitor.notifier (Gmail SMTP alerts)."""

from unittest.mock import MagicMock, patch

import config
import monitor.notifier as notifier
from monitor.checker import SiteStatus


def _configure(monkeypatch, username="me@gmail.com", password="app-pass", to=None):
    monkeypatch.setattr(config, "SMTP_USERNAME", username)
    monkeypatch.setattr(config, "SMTP_APP_PASSWORD", password)
    monkeypatch.setattr(config, "ALERT_EMAIL_TO", to or username)
    monkeypatch.setattr(config, "ALERT_FAILURE_THRESHOLD", 2)
    notifier._warned_not_configured = False


def test_is_configured_true_when_all_present(monkeypatch):
    _configure(monkeypatch)
    assert notifier.is_configured() is True


def test_is_configured_false_when_missing_password(monkeypatch):
    _configure(monkeypatch, password="")
    assert notifier.is_configured() is False


def test_notify_skips_and_warns_once_when_not_configured(monkeypatch):
    _configure(monkeypatch, password="")
    logger = MagicMock()
    site = SiteStatus(url="https://a.com", status="OFFLINE")

    notifier.notify("DOWN", site, logger)
    notifier.notify("DOWN", site, logger)

    assert logger.warning.call_count == 1  # only warns once, not every call
    logger.error.assert_not_called()


def test_notify_sends_email_on_down(monkeypatch):
    _configure(monkeypatch)
    logger = MagicMock()
    site = SiteStatus(url="https://a.com", status="OFFLINE", status_code=None)

    mock_smtp = MagicMock()
    with patch("monitor.notifier.smtplib.SMTP_SSL") as mock_ssl:
        mock_ssl.return_value.__enter__.return_value = mock_smtp
        notifier.notify("DOWN", site, logger)

    mock_smtp.login.assert_called_once_with("me@gmail.com", "app-pass")
    mock_smtp.send_message.assert_called_once()
    sent_message = mock_smtp.send_message.call_args[0][0]
    assert "DOWN" in sent_message["Subject"]
    assert site.url in sent_message["Subject"]
    assert sent_message["To"] == "me@gmail.com"
    logger.info.assert_called_once()


def test_notify_sends_email_on_recovery(monkeypatch):
    _configure(monkeypatch)
    logger = MagicMock()
    site = SiteStatus(url="https://a.com", status="ONLINE", status_code=200, response_time_ms=42.0)

    mock_smtp = MagicMock()
    with patch("monitor.notifier.smtplib.SMTP_SSL") as mock_ssl:
        mock_ssl.return_value.__enter__.return_value = mock_smtp
        notifier.notify("RECOVERED", site, logger)

    sent_message = mock_smtp.send_message.call_args[0][0]
    assert "back ONLINE" in sent_message["Subject"]


def test_notify_logs_error_and_does_not_raise_on_smtp_failure(monkeypatch):
    _configure(monkeypatch)
    logger = MagicMock()
    site = SiteStatus(url="https://a.com", status="OFFLINE")

    with patch("monitor.notifier.smtplib.SMTP_SSL", side_effect=OSError("network unreachable")):
        notifier.notify("DOWN", site, logger)  # must not raise

    logger.error.assert_called_once()


# -- send_test (the "Test Email" button) ------------------------------------

def test_send_test_includes_current_latency(monkeypatch):
    _configure(monkeypatch)
    logger = MagicMock()
    site = SiteStatus(
        url="https://a.com", status="ONLINE", status_code=200,
        response_time_ms=87.3, last_checked="2026-07-19T12:00:00+00:00",
    )

    mock_smtp = MagicMock()
    with patch("monitor.notifier.smtplib.SMTP_SSL") as mock_ssl:
        mock_ssl.return_value.__enter__.return_value = mock_smtp
        result = notifier.send_test(site, logger)

    assert result is True
    sent_message = mock_smtp.send_message.call_args[0][0]
    assert "Test alert" in sent_message["Subject"]
    assert site.url in sent_message["Subject"]
    assert "87 ms" in sent_message.get_payload()


def test_send_test_handles_missing_latency(monkeypatch):
    _configure(monkeypatch)
    logger = MagicMock()
    site = SiteStatus(url="https://b.com")  # never checked yet

    mock_smtp = MagicMock()
    with patch("monitor.notifier.smtplib.SMTP_SSL") as mock_ssl:
        mock_ssl.return_value.__enter__.return_value = mock_smtp
        result = notifier.send_test(site, logger)

    assert result is True
    assert "not yet measured" in mock_smtp.send_message.call_args[0][0].get_payload()


def test_send_test_returns_false_when_not_configured(monkeypatch):
    _configure(monkeypatch, password="")
    logger = MagicMock()
    site = SiteStatus(url="https://a.com", status="ONLINE", response_time_ms=10.0)

    result = notifier.send_test(site, logger)

    assert result is False
    logger.warning.assert_called_once()


def test_send_test_returns_false_on_smtp_failure(monkeypatch):
    _configure(monkeypatch)
    logger = MagicMock()
    site = SiteStatus(url="https://a.com", status="ONLINE", response_time_ms=10.0)

    with patch("monitor.notifier.smtplib.SMTP_SSL", side_effect=OSError("boom")):
        result = notifier.send_test(site, logger)

    assert result is False
    logger.error.assert_called_once()
