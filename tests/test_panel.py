#!/usr/bin/env python3
"""Activation regressions, isolated from the real desktop and user service."""
from contextlib import ExitStack, redirect_stdout
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "panel", Path(__file__).resolve().parents[1] / "scripts/panel.py"
)
panel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel)


class ActivationTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        paths = {
            "LAYOUT": root / "config/appletsrc",
            "DROPIN": root / "config/systemd/user/plasma.service.d/hybrid.conf",
            "STATE": root / "state",
            "PLUGIN_DIR": root / "plugins",
        }
        for name, value in paths.items():
            self.stack.enter_context(patch.object(panel, name, value))
        panel.LAYOUT.parent.mkdir(parents=True)
        self.original = (
            f"[Containments][2][Applets][109]\nplugin={panel.OLD}\n"
            "[Containments][2][Applets][109][Configuration]\nlaunchers=applications:org.kde.dolphin.desktop\n"
            "[Containments][2][Applets][110]\nplugin=org.kde.plasma.digitalclock\n"
        ).encode()
        panel.LAYOUT.write_bytes(self.original)
        plugin = panel.PLUGIN_DIR / "plasma/applets" / (panel.NEW + ".so")
        plugin.parent.mkdir(parents=True)
        plugin.touch()
        self.running = True
        self.manual = False
        self.refuse_manual_stop = False
        self.starts = 0
        self.fail_starts = 0
        self.final_save = None
        self.events = []
        self.start_layouts = []
        self.stack.enter_context(patch.object(panel, "service", self.service))
        self.stack.enter_context(patch.object(panel, "shell_pid", self.shell_pid))
        self.stack.enter_context(patch.object(panel, "stop_unmanaged_shell", self.stop_manual))
        # Fail closed if the tests ever escape the fake service/bus boundary.
        self.stack.enter_context(patch.object(panel, "run_command", side_effect=AssertionError("Real command attempted")))
        self.stack.enter_context(patch.dict(panel.os.environ, {"QT_PLUGIN_PATH": ""}))

    def shell_pid(self):
        return 202 if self.manual else (101 if self.running else None)

    def service(self, *args):
        self.events.append(args[0])
        if args[0] == "stop":
            self.running = False
        elif args[0] == "start":
            self.assertFalse(self.manual, "Starting systemd's shell while a manual shell owns D-Bus")
            self.starts += 1
            self.running = True
            self.start_layouts.append(panel.LAYOUT.read_bytes())
        elif args[0] == "is-active":
            if self.starts <= self.fail_starts:
                raise RuntimeError("simulated service startup failure")
            self.assertTrue(self.running)
        elif args[0] == "show":
            return "101"
        elif args[0] not in ("reset-failed", "daemon-reload"):
            self.fail(f"Unexpected service command: {args}")
        return ""

    def stop_manual(self):
        self.events.append("stop-manual")
        if self.refuse_manual_stop:
            raise RuntimeError("manual shell did not exit")
        self.manual = False
        if self.final_save is not None:
            panel.LAYOUT.write_bytes(self.final_save)
            self.final_save = None

    def run_action(self, action):
        output = io.StringIO()
        with patch.object(sys, "argv", ["panel.py", action]), redirect_stdout(output):
            panel.main()
        return output.getvalue()

    def set_dropin(self, data):
        panel.DROPIN.parent.mkdir(parents=True, exist_ok=True)
        panel.DROPIN.write_bytes(data)

    def test_activate_takes_over_manual_shell_and_preserves_final_save(self):
        self.running = False
        self.manual = True
        final_layout = self.original + b"[Panel]\nlastSaved=on-quit\n"
        self.final_save = final_layout
        self.run_action("activate")
        expected = final_layout.replace(panel.OLD.encode(), panel.NEW.encode())
        self.assertEqual(panel.LAYOUT.read_bytes(), expected)
        self.assertEqual(self.start_layouts, [expected])
        self.assertEqual(self.events[:3], ["stop", "stop-manual", "daemon-reload"])
        self.assertLess(self.events.index("reset-failed"), self.events.index("start"))
        self.assertIn(str(panel.PLUGIN_DIR), panel.DROPIN.read_text())
        backups = list(panel.STATE.glob("*/appletsrc"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), final_layout)

    def test_reactivate_existing_widgets_after_manual_restart(self):
        existing = self.original.replace(panel.OLD.encode(), panel.NEW.encode())
        panel.LAYOUT.write_bytes(existing)
        self.running = False
        self.manual = True
        output = self.run_action("activate")
        self.assertEqual(panel.LAYOUT.read_bytes(), existing)
        self.assertEqual(self.starts, 1)
        self.assertIn("Reloaded existing", output)
        self.assertFalse(self.manual)

    def test_hung_manual_shell_leaves_configuration_untouched(self):
        self.running = False
        self.manual = True
        self.refuse_manual_stop = True
        self.set_dropin(b"original override\n")
        with self.assertRaisesRegex(RuntimeError, "manual shell did not exit"):
            self.run_action("activate")
        self.assertEqual(panel.LAYOUT.read_bytes(), self.original)
        self.assertEqual(panel.DROPIN.read_bytes(), b"original override\n")
        self.assertEqual(self.starts, 0)

    def test_failed_launch_stops_shell_before_rollback(self):
        self.fail_starts = 1
        self.set_dropin(b"original override\n")
        real_write = panel.write_atomic

        def guarded_write(path, data):
            self.assertFalse(self.running or self.manual, "Writing configuration while Plasma is running")
            real_write(path, data)

        with patch.object(panel, "write_atomic", guarded_write):
            with self.assertRaisesRegex(RuntimeError, "Previous configuration restored"):
                self.run_action("activate")
        self.assertEqual(panel.LAYOUT.read_bytes(), self.original)
        self.assertEqual(panel.DROPIN.read_bytes(), b"original override\n")
        self.assertEqual(self.starts, 2)
        self.assertEqual(self.start_layouts[-1], self.original)
        self.assertTrue(self.running)

    def test_failed_first_install_removes_new_dropin(self):
        self.fail_starts = 1
        with self.assertRaisesRegex(RuntimeError, "Previous configuration restored"):
            self.run_action("activate")
        self.assertFalse(panel.DROPIN.exists())
        self.assertEqual(panel.LAYOUT.read_bytes(), self.original)

    def test_failed_recovery_reports_backup_and_diagnostics(self):
        self.fail_starts = 2
        with self.assertRaisesRegex(RuntimeError, "Recovery also failed") as error:
            self.run_action("activate")
        self.assertIn("Backup:", str(error.exception))
        self.assertIn("journalctl --user", str(error.exception))
        self.assertEqual(panel.LAYOUT.read_bytes(), self.original)

    def test_restore_also_handles_manual_shell(self):
        panel.LAYOUT.write_bytes(self.original.replace(panel.OLD.encode(), panel.NEW.encode()))
        self.set_dropin(b"hybrid override\n")
        self.running = False
        self.manual = True
        self.run_action("restore")
        self.assertEqual(panel.LAYOUT.read_bytes(), self.original)
        self.assertFalse(panel.DROPIN.exists())
        self.assertTrue(self.running)

    def test_status_does_not_touch_shell_or_configuration(self):
        output = self.run_action("status")
        self.assertIn("Standard task managers: 1; hybrid: 0", output)
        self.assertEqual(self.events, [])
        self.assertFalse(panel.STATE.exists())


class ShellControlTest(unittest.TestCase):
    def disposable_process(self):
        # A plain sleep process exercises Linux pidfd waiting without running Plasma.
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])

        def cleanup():
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)

        self.addCleanup(cleanup)
        return child

    def test_waits_for_quit_to_finish(self):
        child = self.disposable_process()
        with patch.object(panel, "shell_pid", side_effect=[child.pid, None]), \
                patch.object(panel, "bus_call", side_effect=lambda *args: child.terminate()):
            panel.stop_unmanaged_shell()
        self.assertIsNotNone(child.poll())

    def test_quit_failure_falls_back_to_sigterm(self):
        child = self.disposable_process()
        with patch.object(panel, "shell_pid", side_effect=[child.pid, None]), \
                patch.object(panel, "bus_call", side_effect=RuntimeError("quit unavailable")):
            panel.stop_unmanaged_shell()
        self.assertEqual(child.poll(), -panel.signal.SIGTERM)

    def test_timeout_leaves_hung_shell_alive_and_aborts(self):
        child = self.disposable_process()
        with patch.object(panel, "shell_pid", return_value=child.pid), \
                patch.object(panel, "bus_call", return_value=""), \
                patch.object(panel, "STOP_TIMEOUT_MS", 10):
            with self.assertRaisesRegex(RuntimeError, "a second shell will not be started"):
                panel.stop_unmanaged_shell()
        self.assertIsNone(child.poll())

    def test_another_shell_appearing_during_shutdown_aborts(self):
        child = self.disposable_process()
        with patch.object(panel, "shell_pid", side_effect=[child.pid, 999]), \
                patch.object(panel, "bus_call", side_effect=lambda *args: child.terminate()):
            with self.assertRaisesRegex(RuntimeError, "Another plasmashell"):
                panel.stop_unmanaged_shell()

    def test_shell_disappears_between_owner_and_pid_query(self):
        with patch.object(panel, "bus_call", side_effect=["b true", RuntimeError("gone"), "b false"]):
            self.assertIsNone(panel.shell_pid())

    def test_failed_pid_query_with_live_owner_is_not_ignored(self):
        with patch.object(panel, "bus_call", side_effect=["b true", RuntimeError("access denied"), "b true"]):
            with self.assertRaisesRegex(RuntimeError, "access denied"):
                panel.shell_pid()

    def test_session_bus_pid_is_parsed(self):
        with patch.object(panel, "bus_call", side_effect=["b true", "u 1234"]):
            self.assertEqual(panel.shell_pid(), 1234)

    def test_rejects_active_service_that_does_not_own_shell(self):
        def service(*args):
            return "101" if args[0] == "show" else ""

        with patch.object(panel, "service", side_effect=service), \
                patch.object(panel, "shell_pid", return_value=202):
            with self.assertRaisesRegex(RuntimeError, "not owned by"):
                panel.start_shell()


if __name__ == "__main__":
    unittest.main()
