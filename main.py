"""Website Monitor - headless entry point.

Runs continuously from the command line: checks every site every
config.CHECK_INTERVAL seconds, logs any status changes, and writes a
status.json snapshot. Useful for a server or scheduled task, or for
feeding an external tool that reads status.json.

For everyday desktop use, run app.py instead -- it does the checking
and the UI in a single window, with no files shared between processes.
"""

from __future__ import annotations

import sys
import time

import config
from monitor.checker import SiteStatus, load_websites
from monitor.engine import run_check_cycle
from monitor.logger_setup import setup_logging
from monitor.status_store import save_status
from monitor import notifier

logger = setup_logging()


def _notify(event: str, site: SiteStatus) -> None:
    notifier.notify(event, site, logger)


def main() -> None:
    try:
        urls = load_websites(config.WEBSITES_FILE)
    except FileNotFoundError:
        logger.error("Websites file not found: %s", config.WEBSITES_FILE)
        sys.exit(1)

    if not urls:
        logger.error("No websites to monitor. Add URLs to %s", config.WEBSITES_FILE)
        sys.exit(1)

    sites = {url: SiteStatus(url=url) for url in urls}

    logger.info(
        "Starting Website Monitor: %d site(s), checking every %ds",
        len(urls), config.CHECK_INTERVAL,
    )

    try:
        while True:
            run_check_cycle(sites, logger, notify=_notify)
            save_status(sites, config.STATUS_FILE)
            time.sleep(config.CHECK_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Website Monitor stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
