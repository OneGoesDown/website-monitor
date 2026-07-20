"""Shared check-cycle logic used by every entry point (main.py, app.py).

Kept in one place so the concurrent-check-and-log behavior isn't
duplicated between the headless CLI and the desktop app.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Callable, Optional

import config
from monitor.checker import SiteStatus, check_website

# Called as notify(event, site) where event is "DOWN" or "RECOVERED".
NotifyCallback = Callable[[str, SiteStatus], None]


def run_check_cycle(
    sites: dict[str, SiteStatus],
    logger: logging.Logger,
    lock: Optional[threading.Lock] = None,
    notify: Optional[NotifyCallback] = None,
) -> None:
    """Check every site in `sites` concurrently, update each SiteStatus
    in place, log any status changes, and fire alert callbacks.

    `lock`, if given, is held only while updating a SiteStatus object
    -- never during the network request itself -- so a UI reading the
    same dict on another thread is never blocked for more than a
    moment.

    `notify`, if given, is called with ("DOWN", site) once a site has
    failed config.ALERT_FAILURE_THRESHOLD consecutive checks, and with
    ("RECOVERED", site) once it succeeds again after a DOWN alert was
    sent. It's evaluated every cycle, independent of whether the
    status *label* changed, so a site stuck OFFLINE across several
    checks still reaches the threshold.
    """

    def apply_result(url: str, status: str, status_code, response_time_ms: float):
        site = sites[url]
        site.checks += 1

        if status != "ONLINE":
            site.failures += 1
            site.consecutive_failures += 1
        else:
            site.consecutive_failures = 0

        previous_status = site.status
        site.status = status
        site.status_code = status_code
        site.response_time_ms = response_time_ms
        site.last_checked = datetime.now(timezone.utc).isoformat()

        send_down = False
        send_recovered = False
        if status != "ONLINE" and site.consecutive_failures == config.ALERT_FAILURE_THRESHOLD and not site.alert_sent:
            site.alert_sent = True
            send_down = True
        elif status == "ONLINE" and site.alert_sent:
            site.alert_sent = False
            send_recovered = True

        return previous_status, site.uptime_pct, send_down, send_recovered

    with ThreadPoolExecutor(max_workers=min(len(sites), 20) or 1) as pool:
        futures = {
            pool.submit(check_website, url, config.REQUEST_TIMEOUT, config.OK_STATUS_MAX): url
            for url in sites
        }

        for future in as_completed(futures):
            url = futures[future]
            status, status_code, response_time_ms = future.result()

            if lock is not None:
                with lock:
                    previous_status, uptime_pct, send_down, send_recovered = apply_result(
                        url, status, status_code, response_time_ms
                    )
            else:
                previous_status, uptime_pct, send_down, send_recovered = apply_result(
                    url, status, status_code, response_time_ms
                )

            if status != previous_status:
                if previous_status is None:
                    logger.info(
                        "%s is now %s (code=%s, %sms)",
                        url, status, status_code, response_time_ms,
                    )
                else:
                    logger.info(
                        "%s changed status: %s -> %s (code=%s, %sms, uptime=%s%%)",
                        url, previous_status, status, status_code,
                        response_time_ms, uptime_pct,
                    )

            if notify is not None:
                if send_down:
                    notify("DOWN", sites[url])
                elif send_recovered:
                    notify("RECOVERED", sites[url])


class MonitorThread:
    """Runs run_check_cycle repeatedly on a background thread until stopped.

    Used by app.py so checking websites never blocks the UI thread.
    Pass a `threading.Lock` so a UI reading the same `sites` dict can
    do so safely while this thread updates it concurrently.
    """

    def __init__(
        self,
        sites: dict[str, SiteStatus],
        logger: logging.Logger,
        lock: Optional[threading.Lock] = None,
        interval: Optional[int] = None,
        notify: Optional[NotifyCallback] = None,
    ) -> None:
        self._sites = sites
        self._logger = logger
        self._lock = lock
        self._interval = interval if interval is not None else config.CHECK_INTERVAL
        self._notify = notify
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start checking in the background. Safe to call if already running."""
        if self.running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self._logger.info(
            "Monitoring started: %d site(s), checking every %ds",
            len(self._sites), self._interval,
        )

    def stop(self) -> None:
        """Signal the background thread to stop after its current cycle."""
        if self.running:
            self._stop_event.set()
            self._logger.info("Monitoring stopped.")

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            run_check_cycle(self._sites, self._logger, lock=self._lock, notify=self._notify)
            self._stop_event.wait(self._interval)
