"""Unit tests for monitor.checker."""

from unittest.mock import Mock, patch

import requests

from monitor.checker import SiteStatus, check_website, load_websites


def test_check_website_online():
    mock_response = Mock(status_code=200)
    with patch("monitor.checker.requests.get", return_value=mock_response):
        status, code, elapsed = check_website("https://example.com")

    assert status == "ONLINE"
    assert code == 200
    assert elapsed >= 0


def test_check_website_error_status():
    mock_response = Mock(status_code=500)
    with patch("monitor.checker.requests.get", return_value=mock_response):
        status, code, _ = check_website("https://example.com")

    assert status == "ERROR"
    assert code == 500


def test_check_website_offline_on_connection_error():
    with patch(
        "monitor.checker.requests.get",
        side_effect=requests.exceptions.ConnectionError,
    ):
        status, code, _ = check_website("https://example.com")

    assert status == "OFFLINE"
    assert code is None


def test_check_website_offline_on_timeout():
    with patch(
        "monitor.checker.requests.get",
        side_effect=requests.exceptions.Timeout,
    ):
        status, code, _ = check_website("https://example.com")

    assert status == "OFFLINE"
    assert code is None


def test_load_websites_strips_blank_lines_and_comments(tmp_path):
    path = tmp_path / "websites.txt"
    path.write_text("https://a.com\n\n# a comment\nhttps://b.com\n")

    assert load_websites(str(path)) == ["https://a.com", "https://b.com"]


def test_uptime_pct_with_no_checks_defaults_to_100():
    site = SiteStatus(url="https://example.com")
    assert site.uptime_pct == 100.0


def test_uptime_pct_reflects_failures():
    site = SiteStatus(url="https://example.com", checks=4, failures=1)
    assert site.uptime_pct == 75.0
