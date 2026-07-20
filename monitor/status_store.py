"""Shared status snapshot so the GUI can see what the monitor is doing.

The background monitor (main.py) writes a JSON snapshot after every
check cycle; the dashboard (gui.py) polls that file. This keeps the
two processes fully decoupled -- the GUI works whether it's started
before or after the monitor, and neither needs to know the other
exists. All it takes is agreeing on `config.STATUS_FILE`.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

# SiteStatus is only used for type hints here, never called at
# runtime. Importing it unconditionally would drag `monitor.checker`
# (and its `requests` dependency) into every process that imports
# status_store -- including gui.py, which should stay dependency-free
# so it can be packaged as a standalone executable without also
# bundling requests/urllib3/certifi.
if TYPE_CHECKING:
    from monitor.checker import SiteStatus


def save_status(sites: "dict[str, SiteStatus]", path: str) -> None:
    """Atomically write the current status of every site to `path`.

    Writes to a temp file and renames it into place, so a reader never
    sees a half-written file.
    """
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "sites": [
            {
                "url": site.url,
                "status": site.status,
                "status_code": site.status_code,
                "response_time_ms": site.response_time_ms,
                "last_checked": site.last_checked,
                "checks": site.checks,
                "failures": site.failures,
                "uptime_pct": site.uptime_pct,
            }
            for site in sites.values()
        ],
    }

    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".status_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def load_status(path: str) -> Optional[dict]:
    """Read the status snapshot, or None if it doesn't exist / isn't ready yet."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # Extremely rare race: file mid-write despite the atomic rename
        # (e.g. read right as os.replace() is happening on some
        # platforms). Treat it like "not ready yet" rather than crash.
        return None
