"""Website Monitor - single-window desktop app.

Checks every site on a background thread and shows live results in a
dark dashboard, all in one process, one window. Just run this --
no separate script to remember to start, no file shared between
processes to get out of sync.

    python app.py
"""

from __future__ import annotations

import copy
import os
import threading
import tkinter as tk
from datetime import datetime
from typing import Optional

import config
from monitor.checker import SiteStatus, load_websites
from monitor.engine import MonitorThread
from monitor.logger_setup import setup_logging
from monitor import notifier

logger = setup_logging()


def _notify(event: str, site: SiteStatus) -> None:
    notifier.notify(event, site, logger)


# --- Color palette (a small, clean dark theme) -------------------------
BG = "#12131c"
PANEL_BG = "#181a26"
ROW_EVEN = "#181a26"
ROW_ODD = "#1e2030"
BORDER = "#282a3c"
TEXT = "#e4e6f5"
SUBTEXT = "#7d84ab"

COLOR_ONLINE = "#37d67a"
COLOR_ERROR = "#f5c04d"
COLOR_OFFLINE = "#f9548a"
COLOR_PENDING = "#7d84ab"
COLOR_STOP = "#f9548a"
COLOR_START = "#5b7cfa"
BUTTON_TEXT = "#12131c"

BTN_BG = "#232640"
BTN_FG = TEXT
BTN_ACTIVE_BG = "#2d3155"

STATUS_LABELS = {"ONLINE": "ONLINE", "ERROR": "ERROR", "OFFLINE": "OFFLINE"}
STATUS_COLORS = {"ONLINE": COLOR_ONLINE, "ERROR": COLOR_ERROR, "OFFLINE": COLOR_OFFLINE}

FONT = "Segoe UI" if os.name == "nt" else "Helvetica"
MONO = "Consolas" if os.name == "nt" else "Menlo"


class App(tk.Tk):
    """Dark-themed desktop app: checks websites and shows live results."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Website Monitor")
        self.geometry("860x460")
        self.minsize(680, 320)
        self.configure(bg=BG)

        self._lock = threading.Lock()
        self._load_error: Optional[str] = None
        self.sites: dict[str, SiteStatus] = {}
        self._site_order: list[str] = []
        self._row_widgets: dict[str, dict] = {}
        self._load_sites()

        self.monitor = MonitorThread(self.sites, logger, lock=self._lock, notify=_notify)

        self._build_header()
        self._build_table()
        self._build_placeholder()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if not self._load_error:
            self.start_monitoring()

        self.refresh_ui()

    # -- Setup ------------------------------------------------------------

    def _load_sites(self) -> None:
        try:
            urls = load_websites(config.WEBSITES_FILE)
        except FileNotFoundError:
            self._load_error = f"Websites file not found:\n{config.WEBSITES_FILE}"
            urls = []

        if not urls and not self._load_error:
            self._load_error = f"No websites listed in:\n{config.WEBSITES_FILE}"

        self._site_order = urls
        self.sites = {url: SiteStatus(url=url) for url in urls}

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=20, pady=(18, 10))

        tk.Label(
            header, text="Website Monitor", bg=BG, fg=TEXT, font=(FONT, 16, "bold"),
        ).pack(side="left")

        self.summary_label = tk.Label(header, text="", bg=BG, fg=SUBTEXT, font=(FONT, 9))
        self.summary_label.pack(side="left", padx=(16, 0))

        self.toggle_button = tk.Button(
            header, text="Stop", command=self._toggle_monitoring,
            bg=COLOR_STOP, fg=BUTTON_TEXT, activebackground=COLOR_STOP,
            activeforeground=BUTTON_TEXT, font=(FONT, 9, "bold"),
            relief="flat", padx=16, pady=5, bd=0, cursor="hand2",
        )
        self.toggle_button.pack(side="right")

        self.updated_label = tk.Label(header, text="", bg=BG, fg=SUBTEXT, font=(FONT, 9))
        self.updated_label.pack(side="right", padx=(0, 16))

    def _build_table(self) -> None:
        border = tk.Frame(self, bg=BORDER)
        border.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.panel = tk.Frame(border, bg=PANEL_BG)
        self.panel.pack(fill="both", expand=True, padx=1, pady=1)

        self.table = tk.Frame(self.panel, bg=PANEL_BG)
        self.table.pack(fill="both", expand=True)

        headers = ["STATUS", "SITE", "CODE", "LATENCY", "UPTIME", "LAST CHECK", ""]
        weights = [2, 4, 1, 2, 2, 2, 0]
        for col, (text, weight) in enumerate(zip(headers, weights)):
            self.table.grid_columnconfigure(col, weight=weight)
            if text:
                tk.Label(
                    self.table, text=text, bg=PANEL_BG, fg=SUBTEXT,
                    font=(FONT, 9, "bold"), anchor="w",
                ).grid(row=0, column=col, sticky="w", padx=(14, 6), pady=(12, 8))

        if self._load_error:
            return

        for index, url in enumerate(self._site_order, start=1):
            bg = ROW_ODD if index % 2 == 0 else ROW_EVEN
            self._create_row(index, url, bg)

    def _create_row(self, row_index: int, url: str, bg: str) -> None:
        status_label = tk.Label(
            self.table, text="\u25cf PENDING", bg=bg, fg=COLOR_PENDING,
            font=(FONT, 9, "bold"), anchor="w",
        )
        url_label = tk.Label(self.table, text=url, bg=bg, fg=TEXT, font=(MONO, 10), anchor="w")
        code_label = tk.Label(self.table, text="--", bg=bg, fg=SUBTEXT, font=(MONO, 9), anchor="w")
        latency_label = tk.Label(self.table, text="--", bg=bg, fg=SUBTEXT, font=(MONO, 9), anchor="w")
        uptime_label = tk.Label(self.table, text="100.0%", bg=bg, fg=SUBTEXT, font=(MONO, 9), anchor="w")
        checked_label = tk.Label(self.table, text="--", bg=bg, fg=SUBTEXT, font=(MONO, 9), anchor="w")

        test_button = tk.Button(
            self.table, text="Test Email", command=lambda u=url: self._send_test_email(u),
            bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE_BG, activeforeground=BTN_FG,
            font=(FONT, 8, "bold"), relief="flat", padx=10, pady=3, bd=0, cursor="hand2",
        )

        status_label.grid(row=row_index, column=0, sticky="w", padx=(14, 6), pady=8)
        url_label.grid(row=row_index, column=1, sticky="w", padx=(0, 6), pady=8)
        code_label.grid(row=row_index, column=2, sticky="w", padx=(0, 6), pady=8)
        latency_label.grid(row=row_index, column=3, sticky="w", padx=(0, 6), pady=8)
        uptime_label.grid(row=row_index, column=4, sticky="w", padx=(0, 6), pady=8)
        checked_label.grid(row=row_index, column=5, sticky="w", padx=(0, 6), pady=8)
        test_button.grid(row=row_index, column=6, sticky="e", padx=(0, 14), pady=6)

        self._row_widgets[url] = {
            "status": status_label,
            "code": code_label,
            "latency": latency_label,
            "uptime": uptime_label,
            "checked": checked_label,
            "button": test_button,
        }

    def _build_placeholder(self) -> None:
        self.placeholder_label = tk.Label(
            self.panel, text="", bg=PANEL_BG, fg=SUBTEXT, font=(FONT, 10), justify="center",
        )

    # -- Monitoring control -------------------------------------------------

    def start_monitoring(self) -> None:
        self.monitor.start()
        self.toggle_button.config(text="Stop", bg=COLOR_STOP, activebackground=COLOR_STOP)

    def stop_monitoring(self) -> None:
        self.monitor.stop()
        self.toggle_button.config(text="Start", bg=COLOR_START, activebackground=COLOR_START)

    def _toggle_monitoring(self) -> None:
        if self.monitor.running:
            self.stop_monitoring()
        else:
            self.start_monitoring()

    def _on_close(self) -> None:
        self.monitor.stop()
        self.destroy()

    # -- Test email button --------------------------------------------------

    def _send_test_email(self, url: str) -> None:
        widgets = self._row_widgets.get(url)
        if widgets is None:
            return

        with self._lock:
            site = copy.copy(self.sites[url])

        button = widgets["button"]
        button.config(state="disabled", text="Sending...")
        self.update_idletasks()  # repaint the "Sending..." state before the blocking SMTP call

        success = notifier.send_test(site, logger)

        if success:
            button.config(text="Sent \u2713", fg=COLOR_ONLINE)
        else:
            button.config(text="Failed \u2715", fg=COLOR_OFFLINE)

        self.after(2000, lambda: self._reset_test_button(url))

    def _reset_test_button(self, url: str) -> None:
        widgets = self._row_widgets.get(url)
        if widgets is None:
            return
        widgets["button"].config(state="normal", text="Test Email", fg=BTN_FG)

    # -- Rendering ------------------------------------------------------------

    def refresh_ui(self) -> None:
        if self._load_error:
            self._show_placeholder(self._load_error)
        else:
            with self._lock:
                snapshot = {url: copy.copy(site) for url, site in self.sites.items()}

            if not any(site.status for site in snapshot.values()):
                self._show_placeholder("Waiting for the first check to complete...")
            else:
                self._render(snapshot)

        self.after(config.GUI_REFRESH_MS, self.refresh_ui)

    def _show_placeholder(self, message: str) -> None:
        self.table.pack_forget()
        self.placeholder_label.config(text=message)
        self.placeholder_label.pack(expand=True, fill="both")
        self.summary_label.config(text="")
        self.updated_label.config(text="")

    def _render(self, snapshot: dict[str, SiteStatus]) -> None:
        self.placeholder_label.pack_forget()
        self.table.pack(fill="both", expand=True)

        online_count = 0
        latest_check: Optional[str] = None
        for url in self._site_order:
            site = snapshot[url]
            widgets = self._row_widgets[url]

            label = STATUS_LABELS.get(site.status, "PENDING")
            color = STATUS_COLORS.get(site.status, COLOR_PENDING)
            widgets["status"].config(text=f"\u25cf {label}", fg=color)

            if site.status == "ONLINE":
                online_count += 1
            if site.last_checked and (latest_check is None or site.last_checked > latest_check):
                latest_check = site.last_checked

            latency_text = f"{site.response_time_ms:.0f} ms" if site.response_time_ms is not None else "--"
            widgets["code"].config(text=site.status_code or "--")
            widgets["latency"].config(text=latency_text)
            widgets["uptime"].config(text=f"{site.uptime_pct:.1f}%")
            widgets["checked"].config(text=self._format_time(site.last_checked))

        self.summary_label.config(text=f"{online_count}/{len(snapshot)} online")
        self.updated_label.config(
            text=f"Updated {self._format_time(latest_check)}" if latest_check else ""
        )

    @staticmethod
    def _format_time(iso_string: Optional[str]) -> str:
        if not iso_string:
            return "--"
        try:
            dt = datetime.fromisoformat(iso_string)
            return dt.astimezone().strftime("%H:%M:%S")
        except ValueError:
            return "--"


if __name__ == "__main__":
    App().mainloop()
