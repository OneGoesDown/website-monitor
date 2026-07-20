"""Tests for monitor.status_store."""

from monitor.checker import SiteStatus
from monitor.status_store import load_status, save_status


def test_load_status_returns_none_when_missing(tmp_path):
    path = tmp_path / "status.json"
    assert load_status(str(path)) is None


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "status.json"
    sites = {
        "https://a.com": SiteStatus(
            url="https://a.com", status="ONLINE", status_code=200,
            response_time_ms=42.5, last_checked="2026-07-17T10:00:00+00:00",
            checks=4, failures=0,
        ),
        "https://b.com": SiteStatus(
            url="https://b.com", status="OFFLINE", status_code=None,
            response_time_ms=5000.0, last_checked="2026-07-17T10:00:01+00:00",
            checks=4, failures=1,
        ),
    }

    save_status(sites, str(path))
    data = load_status(str(path))

    assert data is not None
    assert "updated_at" in data
    by_url = {s["url"]: s for s in data["sites"]}
    assert by_url["https://a.com"]["status"] == "ONLINE"
    assert by_url["https://a.com"]["uptime_pct"] == 100.0
    assert by_url["https://b.com"]["status"] == "OFFLINE"
    assert by_url["https://b.com"]["uptime_pct"] == 75.0


def test_repeated_writes_overwrite_cleanly(tmp_path):
    path = tmp_path / "status.json"
    sites = {"https://a.com": SiteStatus(url="https://a.com", checks=1)}

    save_status(sites, str(path))
    sites["https://a.com"].checks = 5
    save_status(sites, str(path))

    data = load_status(str(path))
    assert data["sites"][0]["checks"] == 5


def test_load_status_returns_none_on_corrupt_json(tmp_path):
    path = tmp_path / "status.json"
    path.write_text("{not valid json")

    assert load_status(str(path)) is None
