"""Configuration for Website Monitor.

Every setting can be overridden with an environment variable of the
same name. Relative paths (the defaults) are resolved next to this
file when running from source, or next to the executable when running
as a PyInstaller-built app -- so websites.txt, logs/, and status.json
always live beside whichever one you're running, not wherever the
current working directory happens to be. This is what makes it safe
to double-click the built .exe from anywhere.
"""

import os
import sys

from dotenv import load_dotenv


def _base_dir() -> str:
    if getattr(sys, "frozen", False):
        # Running as a PyInstaller executable: anchor to the folder the
        # .exe/binary itself lives in, not the temp extraction dir
        # (sys._MEIPASS), which is read-only and deleted on exit.
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _base_dir()


def _resolve(path: str) -> str:
    """Make a relative path absolute, anchored at BASE_DIR."""
    return path if os.path.isabs(path) else os.path.join(BASE_DIR, path)


# Load secrets (Gmail address / app password) from a local .env file
# next to the app, if one exists. Never commit .env -- see
# .env.example for the template that IS committed. A missing .env is
# not an error: email alerts are simply skipped until one is set up.
load_dotenv(_resolve(".env"))

# How often (in seconds) to re-check every site.
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 30))

# How long to wait for a response before treating a site as unreachable.
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", 5))

# File containing one URL per line (blank lines and "#" comments ignored).
WEBSITES_FILE = _resolve(os.environ.get("WEBSITES_FILE", "websites.txt"))

# Where status-change events are logged.
LOG_FILE = _resolve(os.environ.get("LOG_FILE", "logs/monitor.log"))

# Log rotation: max size per file and how many old files to keep.
LOG_MAX_BYTES = int(os.environ.get("LOG_MAX_BYTES", 1_000_000))
LOG_BACKUP_COUNT = int(os.environ.get("LOG_BACKUP_COUNT", 3))

# HTTP status codes below this are treated as "online"; at or above,
# the site responded but with an error (e.g. 500) and is flagged "ERROR".
OK_STATUS_MAX = int(os.environ.get("OK_STATUS_MAX", 400))

# Snapshot file written by main.py's headless mode, for external tools
# or scripts that want to read live status without running a GUI.
# app.py doesn't use this -- it holds status in memory since checking
# and display happen in the same process.
STATUS_FILE = _resolve(os.environ.get("STATUS_FILE", "status.json"))

# How often (in milliseconds) app.py refreshes its display.
GUI_REFRESH_MS = int(os.environ.get("GUI_REFRESH_MS", 2000))

# --- Email alerts (Gmail SMTP) ------------------------------------------
# Read from .env / environment variables, never hardcoded. See
# .env.example and the README's "Email alerts" section for setup.
# Alerts are simply skipped (with a one-time log warning) if these
# aren't set, so the app still runs fine without them configured.
SMTP_USERNAME = os.environ.get("GMAIL_ADDRESS", "")
SMTP_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
ALERT_EMAIL_TO = os.environ.get("ALERT_EMAIL_TO", SMTP_USERNAME)

# How many consecutive failed checks before sending a DOWN alert.
# Avoids emailing you over a single flaky timeout.
ALERT_FAILURE_THRESHOLD = int(os.environ.get("ALERT_FAILURE_THRESHOLD", 2))
