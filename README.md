# Hybrid Task Manager

English | [Polski](README-pl.md)

A fork of KDE's **Icons-and-Text Task Manager** that lets you display selected applications as icons without labels. Based on Plasma Desktop **6.7.5**, using KDE's existing task model.

Right-click an application's task button and enable **Show Only Icon for This Application**. Disable it to restore the label. The icon-only button takes up less space. Your choice applies to all windows of that application and every instance of this widget, and survives application and Plasma restarts. Window names remain available in tooltips and window lists.

Applications are identified by the `.desktop` entry supplied by KDE, falling back to App ID / WM_CLASS when no entry is available. There is no need to enter executable paths, window titles, or process IDs. Flatpak applications use their `.desktop` identifiers. The option is disabled for windows without a usable application identifier.

Selected applications get extra spacing on both sides of their icons: one `Kirigami.Units.smallSpacing`, normally 4 px per side. Dragging a short button over a wider one does not repeatedly swap them back and forth. To reverse a swap, move the pointer back by the system's drag threshold.

## Installation and rollback

Requires Qt 6 / KDE Frameworks 6 and Plasma development libraries, CMake, Ninja, gettext, a C++ compiler, Python 3, and Xvfb. All dependencies were already installed on the machine this project was built for. Tested with Plasma **6.7.5**, KDE Frameworks **6.30**, and Qt **6.12** on Garuda Linux.

```bash
bash scripts/install.sh --activate
```

The script builds and tests the widget, installs it under `~/.local`, backs up the panel configuration, and replaces existing standard Icons-and-Text Task Manager widgets while preserving their IDs, positions, and settings. It briefly restarts `plasma-plasmashell.service`; KWin and running applications remain active. Running the script again updates the library and reloads the widget. Without `--activate`, it installs the files without changing the panel configuration or restarting Plasma.

```bash
python3 scripts/panel.py status
python3 scripts/panel.py restore
```

`restore` switches the widgets back to KDE's standard task manager in the same positions. It preserves subsequent changes to other widgets instead of restoring the entire desktop layout from a backup.

User files:

- Plugin library: `~/.local/lib/qt6/plugins/plasma/applets/org.ezez.plasma.hybridtaskmanager.so`.
- Application preferences: `~/.config/hybridtaskmanagerrc`, group `Appearance`, key `IconOnlyApplications`.
- Local plugin path for Plasma: `~/.config/systemd/user/plasma-plasmashell.service.d/50-hybrid-taskmanager.conf`.
- Configuration backups: `~/.local/state/hybrid-taskmanager/`.

KDE package updates do not overwrite this local widget. Plasma or Qt ABI changes may require rebuilding it. This is a local fork: improvements and fixes from future versions of KDE's task manager are not incorporated automatically.

## Tests

```bash
ctest --test-dir build --output-on-failure
bash scripts/test-integration.sh
```

Rule tests cover application identification, avoiding executable-path matches, persistence, disabling icon-only mode, and preserving unrelated entries. The integration test loads the actual Plasma plugin and window model, opens test windows, and triggers the real context-menu action. It checks labels, button widths, reopening applications, vertical panels, two rows, grouping, and sharing preferences between widget instances.

The drag regression test sends drag-and-drop events to the actual widget. It checks one-pixel movements, a pause longer than the previous timeout, small pointer jitter, and intentional reversal. Both directions are tested in LTR and RTL layouts. Before the fix, this test reproduced the short button oscillating over a wider one.

Integration tests use Xvfb, software rendering, a private D-Bus session with service activation disabled, and temporary configuration, data, and cache directories. They do not start KWin or connect to the user's display. KDE activity services are absent from this test session and may produce warnings about the recent-documents database; those services are not involved in the feature under test.

Logs and test screenshots are written to `artifacts/`. The test runner detects assertion failures, QML `TypeError`/`ReferenceError` messages, and binding loops. An existing layout binding loop when changing panel orientation was also fixed during testing.

## Source and licensing

`src/` is derived from `applets/taskmanager` in [KDE plasma-desktop, tag v6.7.5](https://invent.kde.org/plasma/plasma-desktop/-/tree/v6.7.5/applets/taskmanager). The two activity-history configuration files come from `kcms/recentFiles`. SPDX headers and license texts in `LICENSES/` have been preserved. Translations for standard task-manager features use KDE's original translation catalog.

Source archive: `plasma-desktop-v6.7.5.tar.gz`, SHA-256 `9c93dd185dbe761130f871e15c68896e4d740b987d779137c30f846e7926754f`.
