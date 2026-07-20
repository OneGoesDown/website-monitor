"""Tests for monitor.engine: run_check_cycle, alert thresholds, and MonitorThread."""

import threading
import time
from unittest.mock import Mock, patch

import config
from monitor.checker import SiteStatus
from monitor.engine import MonitorThread, run_check_cycle


# -- run_check_cycle -----------------------------------------------------

def test_run_check_cycle_logs_only_on_status_change():
    sites = {"https://example.com": SiteStatus(url="https://example.com")}
    logger = Mock()

    with patch("monitor.engine.check_website", return_value=("ONLINE", 200, 12.3)):
        run_check_cycle(sites, logger)  # None -> ONLINE: logs
        run_check_cycle(sites, logger)  # still ONLINE: should NOT log again

    assert logger.info.call_count == 1
    site = sites["https://example.com"]
    assert site.status == "ONLINE"
    assert site.checks == 2
    assert site.failures == 0


def test_run_check_cycle_updates_uptime_on_failure():
    sites = {"https://example.com": SiteStatus(url="https://example.com")}
    logger = Mock()
    results = [("ONLINE", 200, 10.0), ("OFFLINE", None, 5000.0)]

    with patch("monitor.engine.check_website", side_effect=results):
        run_check_cycle(sites, logger)
        run_check_cycle(sites, logger)

    site = sites["https://example.com"]
    assert site.status == "OFFLINE"
    assert site.checks == 2
    assert site.failures == 1
    assert site.uptime_pct == 50.0


def test_run_check_cycle_sets_last_checked():
    sites = {"https://example.com": SiteStatus(url="https://example.com")}
    logger = Mock()

    with patch("monitor.engine.check_website", return_value=("ONLINE", 200, 12.3)):
        run_check_cycle(sites, logger)

    assert sites["https://example.com"].last_checked is not None


def test_run_check_cycle_respects_lock_without_deadlocking():
    sites = {"https://example.com": SiteStatus(url="https://example.com")}
    logger = Mock()
    lock = threading.Lock()

    with patch("monitor.engine.check_website", return_value=("ONLINE", 200, 12.3)):
        run_check_cycle(sites, logger, lock=lock)

    assert sites["https://example.com"].status == "ONLINE"
    assert lock.acquire(blocking=False)  # lock was released, not left held
    lock.release()


# -- Alert thresholds ------------------------------------------------------

def test_no_alert_below_failure_threshold(monkeypatch):
    monkeypatch.setattr(config, "ALERT_FAILURE_THRESHOLD", 2)
    sites = {"https://a.com": SiteStatus(url="https://a.com")}
    logger = Mock()
    notify = Mock()

    with patch("monitor.engine.check_website", return_value=("OFFLINE", None, 5000.0)):
        run_check_cycle(sites, logger, notify=notify)  # 1st failure

    notify.assert_not_called()


def test_down_alert_fires_exactly_at_threshold(monkeypatch):
    monkeypatch.setattr(config, "ALERT_FAILURE_THRESHOLD", 2)
    sites = {"https://a.com": SiteStatus(url="https://a.com")}
    logger = Mock()
    notify = Mock()

    with patch("monitor.engine.check_website", return_value=("OFFLINE", None, 5000.0)):
        run_check_cycle(sites, logger, notify=notify)  # 1st: below threshold
        run_check_cycle(sites, logger, notify=notify)  # 2nd: hits threshold

    notify.assert_called_once_with("DOWN", sites["https://a.com"])


def test_down_alert_does_not_repeat_while_still_down(monkeypatch):
    monkeypatch.setattr(config, "ALERT_FAILURE_THRESHOLD", 2)
    sites = {"https://a.com": SiteStatus(url="https://a.com")}
    logger = Mock()
    notify = Mock()

    with patch("monitor.engine.check_website", return_value=("OFFLINE", None, 5000.0)):
        for _ in range(4):
            run_check_cycle(sites, logger, notify=notify)

    notify.assert_called_once_with("DOWN", sites["https://a.com"])


def test_recovery_alert_fires_once_after_down_alert(monkeypatch):
    monkeypatch.setattr(config, "ALERT_FAILURE_THRESHOLD", 2)
    sites = {"https://a.com": SiteStatus(url="https://a.com")}
    logger = Mock()
    notify = Mock()

    with patch("monitor.engine.check_website", return_value=("OFFLINE", None, 5000.0)):
        run_check_cycle(sites, logger, notify=notify)
        run_check_cycle(sites, logger, notify=notify)  # DOWN alert fires here

    notify.reset_mock()
    with patch("monitor.engine.check_website", return_value=("ONLINE", 200, 40.0)):
        run_check_cycle(sites, logger, notify=notify)  # RECOVERED
        run_check_cycle(sites, logger, notify=notify)  # still online, no repeat

    assert notify.call_count == 1
    notify.assert_called_once_with("RECOVERED", sites["https://a.com"])


def test_no_recovery_alert_if_never_reached_threshold(monkeypatch):
    monkeypatch.setattr(config, "ALERT_FAILURE_THRESHOLD", 2)
    sites = {"https://a.com": SiteStatus(url="https://a.com")}
    logger = Mock()
    notify = Mock()

    with patch("monitor.engine.check_website", return_value=("OFFLINE", None, 3000.0)):
        run_check_cycle(sites, logger, notify=notify)  # 1 failure, below threshold

    with patch("monitor.engine.check_website", return_value=("ONLINE", 200, 40.0)):
        run_check_cycle(sites, logger, notify=notify)  # recovers before threshold

    notify.assert_not_called()


# -- MonitorThread -----------------------------------------------------------

def test_monitor_thread_start_updates_sites_then_stop_exits_cleanly():
    sites = {"https://example.com": SiteStatus(url="https://example.com")}
    logger = Mock()

    with patch("monitor.engine.check_website", return_value=("ONLINE", 200, 5.0)):
        thread = MonitorThread(sites, logger, lock=threading.Lock(), interval=60)
        assert not thread.running

        thread.start()

        deadline = time.time() + 2
        while sites["https://example.com"].status is None and time.time() < deadline:
            time.sleep(0.02)

        assert sites["https://example.com"].status == "ONLINE"
        assert thread.running

        thread.stop()
        thread._thread.join(timeout=2)  # interval=60 but stop() should wake it immediately
        assert not thread.running


def test_monitor_thread_start_is_idempotent():
    sites = {"https://example.com": SiteStatus(url="https://example.com")}
    logger = Mock()

    with patch("monitor.engine.check_website", return_value=("ONLINE", 200, 5.0)):
        thread = MonitorThread(sites, logger, lock=threading.Lock(), interval=60)
        thread.start()
        first_thread = thread._thread

        thread.start()  # should be a no-op since already running
        assert thread._thread is first_thread

        thread.stop()
        thread._thread.join(timeout=2)
