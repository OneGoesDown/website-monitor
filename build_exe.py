"""Build a standalone Website Monitor executable with PyInstaller.

Usage:
    pip install -r requirements.txt
    pip install pyinstaller
    python build_exe.py

Produces dist/WebsiteMonitor(.exe) -- a single file that checks your
sites and shows the dashboard, no Python install required. Unlike an
earlier version of this script, it does NOT bundle websites.txt into
the executable: that file is copied alongside it instead, since it's
meant to be edited after the fact. config.py resolves it (and logs/,
status.json) relative to wherever the .exe itself lives, so keep them
in the same folder as you move things around.
"""

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is not installed. Run: pip install pyinstaller")
        sys.exit(1)

    try:
        import requests  # noqa: F401
    except ImportError:
        print("requests is not installed in this environment.")
        print("The app performs the actual site checks itself, so it needs")
        print("requests bundled. Run: pip install -r requirements.txt")
        sys.exit(1)

    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--windowed",
            "--name", "WebsiteMonitor",
            "app.py",
        ],
        check=True,
    )

    dist_dir = Path("dist")
    shutil.copy("websites.txt", dist_dir / "websites.txt")

    print(f"\nDone. WebsiteMonitor + websites.txt are in {dist_dir.resolve()}")
    print("Edit websites.txt there to change which sites it watches.")


if __name__ == "__main__":
    main()
