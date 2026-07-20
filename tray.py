"""System tray icon for the desktop app.

Lets the window be minimized to the system tray instead of closing, so
monitoring (and alerts) keep running quietly in the background.

Built with pystray, which manages its own native tray-icon window
completely separate from tkinter's event loop -- so it has to run on
its own background thread, the same pattern MonitorThread uses for
checking websites. The icon image itself is drawn with Pillow at
runtime (a simple colored dot), so no image file needs to ship with
the project.

Important: pystray's menu callbacks (Show / Quit) run on the tray's
own thread, never tkinter's main thread. tkinter widgets aren't safe
to touch from another thread, so this module never calls into the app
directly -- callers must pass callbacks that hop back onto the main
thread themselves (e.g. via `root.after(0, ...)`), same as
MonitorThread's `notify` callback does for email alerts.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

import pystray
from PIL import Image, ImageDraw


def _build_icon_image(size: int = 64, color: str = "#37d67a") -> Image.Image:
    """Draw a simple colored dot as the tray icon (no image asset needed)."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    margin = size // 8
    draw.ellipse((margin, margin, size - margin, size - margin), fill=color)
    return image


class TrayIcon:
    """Wraps a pystray icon with Show/Quit menu actions.

    `on_show` and `on_quit` are called from the tray's own thread --
    it's the caller's responsibility to marshal back to the main
    thread before touching any tkinter widget.
    """

    def __init__(self, on_show: Callable[[], None], on_quit: Callable[[], None]) -> None:
        self._icon = pystray.Icon(
            "website_monitor",
            icon=_build_icon_image(),
            title="Website Monitor",
            menu=pystray.Menu(
                pystray.MenuItem("Show", lambda: on_show(), default=True),
                pystray.MenuItem("Quit", lambda: on_quit()),
            ),
        )
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the tray icon on a background thread. Safe to call once."""
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Remove the tray icon."""
        self._icon.stop()

    def notify(self, message: str, title: str = "Website Monitor") -> None:
        """Show a balloon/notification, if the platform supports it.

        Not every OS/backend supports tray notifications, so failures
        here are swallowed -- it's a nice-to-have, not core behavior.
        """
        try:
            self._icon.notify(message, title)
        except Exception:
            pass
