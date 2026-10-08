#!/usr/bin/env python3
"""Activate/restore existing task managers, preserving their IDs and settings."""
import argparse
import datetime
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

OLD = "org.kde.plasma.taskmanager"
NEW = "org.ezez.plasma.hybridtaskmanager"
SERVICE = "plasma-plasmashell.service"
HOME_DIR = Path.home()
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", HOME_DIR / ".config"))
LAYOUT = CONFIG / "plasma-org.kde.plasma.desktop-appletsrc"
DROPIN = CONFIG / "systemd/user/plasma-plasmashell.service.d/50-hybrid-taskmanager.conf"
STATE = Path(os.environ.get("XDG_STATE_HOME", HOME_DIR / ".local/state")) / "hybrid-taskmanager"
PLUGIN_DIR = HOME_DIR / ".local/lib/qt6/plugins"


def service(*args):
    subprocess.run(["systemctl", "--user", *args], check=True)


def write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        stream.write(data)
    try:
        if path.exists():
            shutil.copymode(path, temp)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["status", "activate", "restore"])
    args = parser.parse_args()
    before, after = (OLD, NEW) if args.action != "restore" else (NEW, OLD)
    pattern = re.compile(rb"^plugin=" + re.escape(before.encode()) + rb"$", re.M)
    layout = LAYOUT.read_bytes()
    count = len(pattern.findall(layout))
    if args.action == "status":
        print(f"Standard task managers: {count}; hybrid: {layout.count(('plugin=' + NEW).encode())}")
        return
    if args.action == "activate" and not (PLUGIN_DIR / "plasma/applets" / (NEW + ".so")).is_file():
        raise SystemExit("Run scripts/install.sh first.")
    already_active = args.action == "activate" and ("plugin=" + NEW).encode() in layout
    if not count and not already_active:
        print(f"No {before} widgets to replace.")
        return

    backup = STATE / datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup.mkdir(parents=True)
    old_dropin = DROPIN.read_bytes() if DROPIN.exists() else None
    if old_dropin is not None:
        (backup / DROPIN.name).write_bytes(old_dropin)
    # Stop only the panel/desktop shell; applications and the compositor stay up.
    service("stop", SERVICE)
    try:
        layout = LAYOUT.read_bytes()  # Include the shell's final saved state.
        shutil.copy2(LAYOUT, backup / LAYOUT.name)
        changed, count = pattern.subn(b"plugin=" + after.encode(), layout)
        write_atomic(LAYOUT, changed)
        if args.action == "activate":
            existing = os.environ.get("QT_PLUGIN_PATH", "")
            paths = str(PLUGIN_DIR) + (":" + existing if existing else "")
            escaped = paths.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
            write_atomic(DROPIN, (f'[Service]\nEnvironment="QT_PLUGIN_PATH={escaped}"\n').encode())
        else:
            DROPIN.unlink(missing_ok=True)
        service("daemon-reload")
        service("start", SERVICE)
        service("is-active", "--quiet", SERVICE)
    except BaseException:
        write_atomic(LAYOUT, layout)
        if old_dropin is None:
            DROPIN.unlink(missing_ok=True)
        else:
            write_atomic(DROPIN, old_dropin)
        service("daemon-reload")
        service("start", SERVICE)
        raise
    print(f"Replaced {count} widgets: {before} -> {after}")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
