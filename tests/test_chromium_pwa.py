#!/usr/bin/env python3
"""Chromium web app overrides, isolated in temporary data directories."""
from contextlib import ExitStack, redirect_stdout
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "chromium_pwa", Path(__file__).resolve().parents[1] / "scripts/chromium-pwa.py"
)
chromium_pwa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chromium_pwa)

BROWSER = """[Desktop Entry]
Name=Chromium
Exec=/opt/browser/chromium %U
Icon=chromium
StartupWMClass=chromium

[Desktop Action new-window]
Name=New Window
Exec=/opt/browser/chromium
StartupWMClass=kept-outside-desktop-entry
"""
WEB_APP = """[Desktop Entry]
Name=Web App
Exec=/opt/browser/chromium --profile-directory=Default --app-id=abc
Icon=chrome-abc-Default
StartupWMClass=crx_abc
"""


class ChromiumPwaTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.local = root / "local/applications"
        self.system = root / "system/applications"
        self.local.mkdir(parents=True)
        self.system.mkdir(parents=True)
        self.stack.enter_context(patch.object(chromium_pwa, "LOCAL_APPS", self.local))
        self.stack.enter_context(patch.object(chromium_pwa, "SYSTEM_APPS", [self.system]))
        self.stack.enter_context(patch.object(chromium_pwa, "refresh_application_cache", self.refresh))
        self.refreshes = 0
        (self.system / "chromium.desktop").write_text(BROWSER)
        (self.local / "chrome-abc-Default.desktop").write_text(WEB_APP)

    def refresh(self):
        self.refreshes += 1

    def run_script(self, *args):
        output = io.StringIO()
        with patch.object(sys, "argv", ["chromium-pwa.py", *args]), redirect_stdout(output):
            chromium_pwa.main()
        return output.getvalue()

    def test_override_drops_only_desktop_entry_startup_wm_class(self):
        self.run_script()
        override = (self.local / "chromium.desktop").read_text()
        entry = chromium_pwa.desktop_entry(self.local / "chromium.desktop")
        self.assertNotIn("StartupWMClass", entry)
        self.assertEqual(entry[chromium_pwa.MARKER], str(self.system / "chromium.desktop"))
        self.assertEqual(entry["Exec"], "/opt/browser/chromium %U")
        self.assertIn("StartupWMClass=kept-outside-desktop-entry", override)
        self.assertEqual(self.refreshes, 1)

    def test_rerun_is_idempotent_and_refreshes_from_system_entry(self):
        self.run_script()
        self.assertIn("up to date", self.run_script())
        self.assertEqual(self.refreshes, 1)
        (self.system / "chromium.desktop").write_text(BROWSER.replace("Name=Chromium", "Name=Chromium 2"))
        self.run_script()
        self.assertEqual(chromium_pwa.desktop_entry(self.local / "chromium.desktop")["Name"], "Chromium 2")

    def test_without_web_apps_or_source_override_is_removed(self):
        self.run_script()
        (self.local / "chrome-abc-Default.desktop").unlink()
        self.run_script()
        self.assertFalse((self.local / "chromium.desktop").exists())
        self.run_script()
        self.assertFalse((self.local / "chromium.desktop").exists())
        (self.local / "chrome-abc-Default.desktop").write_text(WEB_APP)
        self.run_script()
        (self.system / "chromium.desktop").unlink()
        self.run_script()
        self.assertFalse((self.local / "chromium.desktop").exists())

    def test_other_browsers_and_own_files_are_left_alone(self):
        (self.system / "other.desktop").write_text(BROWSER.replace("/opt/browser/chromium", "/opt/other/browser"))
        own = "[Desktop Entry]\nName=Mine\nExec=/opt/browser/chromium\nStartupWMClass=chromium\n"
        (self.local / "chromium.desktop").write_text(own)
        self.assertIn("Skipped", self.run_script())
        self.assertEqual((self.local / "chromium.desktop").read_text(), own)
        self.assertFalse((self.local / "other.desktop").exists())
        self.run_script("restore")
        self.assertEqual((self.local / "chromium.desktop").read_text(), own)

    def test_restore_removes_generated_overrides(self):
        self.run_script()
        self.run_script("restore")
        self.assertFalse((self.local / "chromium.desktop").exists())
        self.assertTrue((self.local / "chrome-abc-Default.desktop").exists())
        self.assertIn("No Chromium web app overrides", self.run_script("restore"))


if __name__ == "__main__":
    unittest.main()
