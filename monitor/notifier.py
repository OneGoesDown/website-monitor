"""Email alerts for status changes, sent via Gmail SMTP.

Credentials (GMAIL_ADDRESS / GMAIL_APP_PASSWORD) are read from
environment variables -- see config.py, which loads them from a local,
git-ignored .env file. They are never hardcoded here or anywhere else
in the project. See .env.example for the template and the README's
"Email alerts" section for how to generate a Gmail app password.

Sending an alert never raises: a network hiccup or bad credentials
should log an error, not take down the monitor itself.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

import config
from monitor.checker import SiteStatus

_warned_not_configured = False


def is_configured() -> bool:
    """Whether enough settings are present to actually send an email."""
    return bool(config.SMTP_USERNAME and config.SMTP_APP_PASSWORD and config.ALERT_EMAIL_TO)


def _send(subject: str, body: str) -> None:
    """Send one email via Gmail SMTP. Raises on failure; callers handle it."""
    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = config.SMTP_USERNAME
    message["To"] = config.ALERT_EMAIL_TO

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
        smtp.login(config.SMTP_USERNAME, config.SMTP_APP_PASSWORD)
        smtp.send_message(message)


def notify(event: str, site: SiteStatus, logger: logging.Logger) -> None:
    """Send a DOWN/RECOVERED alert email for `site`.

    `event` is "DOWN" or "RECOVERED". If alerts aren't configured, this
    logs a one-time warning and does nothing -- it never raises.
    """
    global _warned_not_configured

    if not is_configured():
        if not _warned_not_configured:
            logger.warning(
                "Email alerts are not configured (missing GMAIL_ADDRESS / "
                "GMAIL_APP_PASSWORD). See .env.example. Skipping alert for %s.",
                site.url,
            )
            _warned_not_configured = True
        return

    if event == "DOWN":
        subject = f"[Website Monitor] {site.url} is DOWN"
        body = (
            f"{site.url} has failed {config.ALERT_FAILURE_THRESHOLD} consecutive check(s).\n\n"
            f"Status: {site.status}\n"
            f"HTTP code: {site.status_code or '--'}\n"
            f"Last checked: {site.last_checked}\n"
        )
    elif event == "RECOVERED":
        subject = f"[Website Monitor] {site.url} is back ONLINE"
        body = (
            f"{site.url} responded successfully again.\n\n"
            f"HTTP code: {site.status_code}\n"
            f"Response time: {site.response_time_ms} ms\n"
            f"Last checked: {site.last_checked}\n"
        )
    else:
        return

    try:
        _send(subject, body)
        logger.info("Sent %s alert email for %s", event, site.url)
    except Exception as exc:  # noqa: BLE001 -- alerting must never crash the monitor
        logger.error("Failed to send alert email for %s: %s", site.url, exc)


def send_test(site: SiteStatus, logger: logging.Logger) -> bool:
    """Send a one-off test email for `site`, including its current latency.

    Used by the "Test Email" button in app.py to confirm alerts are set
    up correctly, without waiting for a real outage. Returns True if
    the email was sent, False otherwise (including when alerts aren't
    configured) -- never raises.
    """
    if not is_configured():
        logger.warning(
            "Email alerts are not configured (missing GMAIL_ADDRESS / "
            "GMAIL_APP_PASSWORD). See .env.example. Cannot send test email for %s.",
            site.url,
        )
        return False

    latency = f"{site.response_time_ms:.0f} ms" if site.response_time_ms is not None else "not yet measured"
    subject = f"[Website Monitor] Test alert for {site.url}"
    body = (
        f"This is a test notification from Website Monitor.\n\n"
        f"Site: {site.url}\n"
        f"Current status: {site.status or 'PENDING'}\n"
        f"Latency: {latency}\n"
        f"Last checked: {site.last_checked or '--'}\n\n"
        f"If you received this, your email alerts are configured correctly.\n"
    )

    try:
        _send(subject, body)
        logger.info("Sent test alert email for %s", site.url)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send test email for %s: %s", site.url, exc)
        return False
