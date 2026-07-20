"""Tests for tray.py, using a mocked pystray backend.

pystray needs a real OS tray to actually run, so these tests replace
it with a MagicMock before importing tray.py -- exercising the real
wiring logic (menu construction, thread management, callback
delegation) without needing an actual system tray to exist.
"""

import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def fake_pystray(monkeypatch):
    fake = MagicMock()
    fake.Icon.return_value = MagicMock()
    fake.Menu = lambda *items: list(items)
    fake.MenuItem = lambda text, action, default=False: {
        "text": text, "action": action, "default": default,
    }
    monkeypatch.setitem(sys.modules, "pystray", fake)

    # tray.py may already be imported by a previous test with the real
    # (or a different mocked) pystray -- force a fresh import so it
    # picks up this fixture's fake module.
    monkeypatch.delitem(sys.modules, "tray", raising=False)

    return fake


def test_build_icon_image_is_correct_size(fake_pystray):
    from tray import _build_icon_image

    image = _build_icon_image()

    assert image.size == (64, 64)
    assert image.mode == "RGBA"


def test_menu_has_show_and_quit_with_show_as_default(fake_pystray):
    from tray import TrayIcon

    TrayIcon(on_show=lambda: None, on_quit=lambda: None)

    _, kwargs = fake_pystray.Icon.call_args
    menu = kwargs["menu"]

    assert [item["text"] for item in menu] == ["Show", "Quit"]
    assert menu[0]["default"] is True  # Show fires on the default (double-)click


def test_menu_actions_invoke_the_given_callbacks(fake_pystray):
    from tray import TrayIcon

    on_show_calls = []
    on_quit_calls = []
    TrayIcon(
        on_show=lambda: on_show_calls.append(1),
        on_quit=lambda: on_quit_calls.append(1),
    )

    _, kwargs = fake_pystray.Icon.call_args
    menu = kwargs["menu"]
    menu[0]["action"]()
    menu[1]["action"]()

    assert on_show_calls == [1]
    assert on_quit_calls == [1]


def test_start_spawns_a_daemon_thread(fake_pystray):
    from tray import TrayIcon

    icon = TrayIcon(on_show=lambda: None, on_quit=lambda: None)
    assert icon._thread is None

    icon.start()

    assert icon._thread is not None
    assert icon._thread.daemon is True


def test_start_is_idempotent(fake_pystray):
    from tray import TrayIcon

    icon = TrayIcon(on_show=lambda: None, on_quit=lambda: None)
    icon.start()
    first_thread = icon._thread

    icon.start()  # should not spawn a second thread

    assert icon._thread is first_thread


def test_stop_delegates_to_underlying_icon(fake_pystray):
    from tray import TrayIcon

    icon = TrayIcon(on_show=lambda: None, on_quit=lambda: None)
    icon.stop()

    icon._icon.stop.assert_called_once()


def test_notify_delegates_to_underlying_icon(fake_pystray):
    from tray import TrayIcon

    icon = TrayIcon(on_show=lambda: None, on_quit=lambda: None)
    icon.notify("hello there")

    icon._icon.notify.assert_called_once_with("hello there", "Website Monitor")


def test_notify_swallows_errors_on_unsupported_backends(fake_pystray):
    from tray import TrayIcon

    icon = TrayIcon(on_show=lambda: None, on_quit=lambda: None)
    icon._icon.notify.side_effect = NotImplementedError("unsupported backend")

    icon.notify("should not raise")  # must not raise
