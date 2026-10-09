#!/usr/bin/env python3
"""Activate/restore existing task managers, preserving their IDs and settings."""
import argparse
import datetime
import os
from pathlib import Path
import re
import select
import shutil
import signal
import subprocess
import sys
import tempfile

OLD = "org.kde.plasma.taskmanager"
NEW = "org.ezez.plasma.hybridtaskmanager"
SERVICE = "plasma-plasmashell.service"
BUS_NAME = "org.kde.plasmashell"
STOP_TIMEOUT_MS = 10000
HOME_DIR = Path.home()
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", HOME_DIR / ".config"))
LAYOUT = CONFIG / "plasma-org.kde.plasma.desktop-appletsrc"
DROPIN = CONFIG / "systemd/user/plasma-plasmashell.service.d/50-hybrid-taskmanager.conf"
STATE = Path(os.environ.get("XDG_STATE_HOME", HOME_DIR / ".local/state")) / "hybrid-taskmanager"
PLUGIN_DIR = HOME_DIR / ".local/lib/qt6/plugins"


def run_command(command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"{' '.join(command)} failed (exit {result.returncode}): {detail}")
    return result.stdout.strip()


def service(*args):
    return run_command(["systemctl", "--user", *args])


def bus_call(destination, path, interface, method, *args):
    return run_command([
        "busctl", "--user", "--auto-start=no", "--timeout=5s", "call",
        destination, path, interface, method, *args,
    ])


def shell_pid():
    """Find this session bus's shell, including one started outside systemd."""
    def has_owner():
        reply = bus_call("org.freedesktop.DBus", "/org/freedesktop/DBus",
                         "org.freedesktop.DBus", "NameHasOwner", "s", BUS_NAME)
        if reply not in ("b true", "b false"):
            raise RuntimeError(f"Unexpected NameHasOwner reply: {reply}")
        return reply == "b true"

    if not has_owner():
        return None
    try:
        reply = bus_call("org.freedesktop.DBus", "/org/freedesktop/DBus",
                         "org.freedesktop.DBus", "GetConnectionUnixProcessID", "s", BUS_NAME)
    except RuntimeError:
        if not has_owner():  # The shell exited between the two calls.
            return None
        raise
    match = re.fullmatch(r"u ([1-9][0-9]*)", reply)
    if not match:
        raise RuntimeError(f"Unexpected shell PID reply: {reply}")
    return int(match[1])


def stop_unmanaged_shell():
    pid = shell_pid()
    if pid is None:
        return
    print(f"Stopping plasmashell started outside systemd (PID {pid})...", flush=True)
    try:
        process = os.pidfd_open(pid)
    except ProcessLookupError:
        if shell_pid() is not None:
            raise RuntimeError("Another plasmashell started during shutdown; retry after closing it.")
        return
    try:
        try:
            bus_call(BUS_NAME, "/MainApplication", "org.qtproject.Qt.QCoreApplication", "quit")
        except RuntimeError:
            # SIGTERM targets this exact process, even if its numeric PID is reused.
            try:
                signal.pidfd_send_signal(process, signal.SIGTERM)
            except ProcessLookupError:
                pass
        poller = select.poll()
        poller.register(process, select.POLLIN)
        if not poller.poll(STOP_TIMEOUT_MS):
            raise RuntimeError(
                "The manually started plasmashell did not exit within 10 seconds. "
                "Close it before retrying; "
                "a second shell will not be started."
            )
    finally:
        os.close(process)
    if shell_pid() is not None:
        raise RuntimeError("Another plasmashell started during shutdown; retry after closing it.")


def stop_shell():
    # Stopping the service disables its automatic respawn, but does not stop
    # shells launched from a terminal with kstart/plasmashell --replace.
    service("stop", SERVICE)
    stop_unmanaged_shell()


def start_shell():
    # Previous unsuccessful launches may have exhausted systemd's start limit.
    service("reset-failed", SERVICE)
    service("start", SERVICE)
    service("is-active", "--quiet", SERVICE)
    pid = service("show", SERVICE, "--property=MainPID", "--value")
    if not pid.isdigit() or int(pid) == 0 or shell_pid() != int(pid):
        raise RuntimeError("The running plasmashell is not owned by plasma-plasmashell.service.")


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
    # Do not edit the layout while any shell can still save over it.
    stop_shell()
    saved_layout = None
    try:
        layout = LAYOUT.read_bytes()  # Include the shell's final saved state.
        saved_layout = layout
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
        start_shell()
    except (OSError, RuntimeError, KeyboardInterrupt) as error:
        # A failed launch can leave a respawning/partially running shell. Stop
        # it before restoring files, otherwise it could overwrite the backup.
        try:
            stop_shell()
            if saved_layout is not None:
                write_atomic(LAYOUT, saved_layout)
            if old_dropin is None:
                DROPIN.unlink(missing_ok=True)
            else:
                write_atomic(DROPIN, old_dropin)
            service("daemon-reload")
            start_shell()
        except (OSError, RuntimeError) as recovery_error:
            raise RuntimeError(
                f"{args.action} failed: {error}\nRecovery also failed: {recovery_error}\n"
                f"Backup: {backup}\nCheck: journalctl --user -u {SERVICE} -n 50 --no-pager"
            ) from error
        raise RuntimeError(f"{args.action} failed: {error}\nPrevious configuration restored. Backup: {backup}") from error
    if count:
        print(f"Replaced {count} widgets: {before} -> {after}")
    else:
        print("Reloaded existing Hybrid Task Manager widgets.")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
