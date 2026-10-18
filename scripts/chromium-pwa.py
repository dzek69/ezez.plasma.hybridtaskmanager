#!/usr/bin/env python3
"""Keep Chromium-based web apps (PWAs) separate from their browser in task managers.

On Wayland, KWin reports every window of a Chromium-based browser with the
executable name (e.g. "chromium") as its resource name, including web app
windows. Plasma's task model matches that name against StartupWMClass before
it matches the window's app ID against .desktop file names, so a browser entry
declaring StartupWMClass=chromium claims all web app windows: they get the
browser's icon and name, and are grouped with it.

This script installs user overrides of such browser entries without
StartupWMClass. The browser's own windows still match its entry by app ID.
Running it again refreshes the overrides from the system entries; "restore"
removes them.
"""
import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

MARKER = "X-HybridTaskManager-Source"
HOME_DIR = Path.home()
LOCAL_APPS = Path(os.environ.get("XDG_DATA_HOME") or HOME_DIR / ".local/share") / "applications"
SYSTEM_APPS = [
    Path(directory) / "applications"
    for directory in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
    if directory
]


def desktop_entry(path):
    """Return the keys of the [Desktop Entry] group."""
    keys = {}
    group = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("["):
            group = line
        elif group == "[Desktop Entry]" and "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            keys.setdefault(key.strip(), value.strip())
    return keys


def program(entry):
    try:
        command = shlex.split(entry.get("Exec", ""))
    except ValueError:
        return None
    if not command:
        return None
    path = command[0] if "/" in command[0] else shutil.which(command[0])
    return os.path.realpath(path) if path else None


def without_startup_wm_class(text, source):
    lines = []
    group = None
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("["):
            group = stripped
            lines.append(line)
            if group == "[Desktop Entry]":
                lines.append(f"{MARKER}={source}\n")
        elif group == "[Desktop Entry]" and stripped.split("=", 1)[0].strip() == "StartupWMClass":
            continue
        else:
            lines.append(line)
    return "".join(lines)


def write_atomic(path, text):
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def generated_overrides():
    if not LOCAL_APPS.is_dir():
        return {}
    return {path.name: path for path in LOCAL_APPS.glob("*.desktop") if MARKER in desktop_entry(path)}


def system_entries():
    entries = {}
    for directory in SYSTEM_APPS:
        if directory.is_dir():
            for path in directory.glob("*.desktop"):
                entries.setdefault(path.name, path)  # Earlier data directories take precedence.
    return entries


def web_app_programs():
    programs = set()
    if LOCAL_APPS.is_dir():
        for path in LOCAL_APPS.glob("*.desktop"):
            entry = desktop_entry(path)
            if entry.get("StartupWMClass", "").startswith("crx_") and program(entry):
                programs.add(program(entry))
    return programs


def wanted_overrides(generated):
    """Map override file names to the system entries they are generated from."""
    programs = web_app_programs()
    wanted = {}
    for name, path in system_entries().items():
        entry = desktop_entry(path)
        wm_class = entry.get("StartupWMClass", "")
        if not wm_class or wm_class.startswith("crx_") or program(entry) not in programs:
            continue
        if (LOCAL_APPS / name).exists() and name not in generated:
            print(f"Skipped {LOCAL_APPS / name}: it is your own file. Remove its StartupWMClass line manually.")
            continue
        wanted[name] = path
    return wanted


def refresh_application_cache():
    if shutil.which("kbuildsycoca6"):
        subprocess.run(["kbuildsycoca6"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", nargs="?", choices=["apply", "restore"], default="apply")
    args = parser.parse_args()
    generated = generated_overrides()
    wanted = wanted_overrides(generated) if args.action == "apply" else {}
    changed = False
    for name, path in generated.items():
        if name not in wanted:
            path.unlink()
            print(f"Removed {path}")
            changed = True
    for name, source in wanted.items():
        target = LOCAL_APPS / name
        text = without_startup_wm_class(source.read_text(encoding="utf-8"), source)
        if target.exists() and target.read_text(encoding="utf-8") == text:
            continue
        LOCAL_APPS.mkdir(parents=True, exist_ok=True)
        write_atomic(target, text)
        print(f"Wrote {target} (from {source}, without StartupWMClass)")
        changed = True
    if changed:
        refresh_application_cache()
    elif args.action == "restore":
        print("No Chromium web app overrides to remove.")
    elif not wanted:
        print("No Chromium-based browser entries need an override.")
    else:
        print("Chromium web app overrides are up to date.")


if __name__ == "__main__":
    try:
        main()
    except OSError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
