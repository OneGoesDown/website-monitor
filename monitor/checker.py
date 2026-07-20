"""Core logic for checking website availability.

Kept free of logging/looping side effects so it can be unit tested
in isolation (see tests/test_checker.py).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class SiteStatus:
    """Tracks the current and historical status of one monitored site."""

    url: str
    status: Optional[str] = None  # "ONLINE" | "ERROR" | "OFFLINE"
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    last_checked: Optional[str] = None  # ISO 8601 timestamp of the last check
    checks: int = 0
    failures: int = 0
    consecutive_failures: int = 0  # resets to 0 on any ONLINE result
    alert_sent: bool = False  # whether a DOWN alert is currently outstanding

    @property
    def uptime_pct(self) -> float:
        """Percentage of checks that resulted in ONLINE, 100.0 if unchecked."""
        if self.checks == 0:
            return 100.0
        return round((self.checks - self.failures) / self.checks * 100, 2)


def check_website(
    url: str,
    timeout: int = 5,
    ok_status_max: int = 400,
) -> tuple[str, Optional[int], float]:
    """Perform a single HTTP GET against `url`.

    Returns a (status, status_code, response_time_ms) tuple. Never
    raises: connection errors and timeouts are caught and reported as
    an "OFFLINE" status rather than propagated.
    """
    start = time.perf_counter()
    try:
        response = requests.get(url, timeout=timeout)
        elapsed_ms = (time.perf_counter() - start) * 1000
        status = "ONLINE" if response.status_code < ok_status_max else "ERROR"
        return status, response.status_code, round(elapsed_ms, 1)
    except requests.exceptions.RequestException:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return "OFFLINE", None, round(elapsed_ms, 1)


def load_websites(path: str) -> list[str]:
    """Read one URL per line from `path`.

    Blank lines and lines starting with "#" are ignored, so the
    websites file can be commented for documentation purposes.
    """
    with open(path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    return [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]
