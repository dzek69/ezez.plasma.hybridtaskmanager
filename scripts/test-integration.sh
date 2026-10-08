#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
test_dir=$(mktemp -d -t hybrid-taskmanager-test.XXXXXXXX)
trap 'rm -rf -- "$test_dir"' EXIT
mkdir -p "$test_dir/config" "$test_dir/runtime" "$project_dir/artifacts"
chmod 700 "$test_dir/runtime"
export XDG_CONFIG_HOME="$test_dir/config"
export XDG_DATA_HOME="$test_dir/data"
export XDG_CACHE_HOME="$test_dir/cache"
export XDG_RUNTIME_DIR="$test_dir/runtime"
export QT_PLUGIN_PATH="$project_dir/build/bin${QT_PLUGIN_PATH:+:$QT_PLUGIN_PATH}"
export HYBRID_TEST_ARTIFACTS="$project_dir/artifacts"
export QT_LOGGING_RULES='*.debug=false;qt.qml.connections=false'
export QT_QUICK_BACKEND=software
export QT_QPA_PLATFORM=xcb
export LIBGL_ALWAYS_SOFTWARE=1
export QT_ACCESSIBILITY=0
export NO_AT_BRIDGE=1
unset WAYLAND_DISPLAY DISPLAY SESSION_MANAGER
# No window manager/compositor or hardware graphics. The harness publishes
# fixture windows through EWMH, the same X11 protocol read by Plasma's model.
timeout 45s xvfb-run -a -s '-screen 0 1280x800x24 -nolisten tcp' \
    dbus-run-session --config-file="$project_dir/tests/session-bus.conf" -- "$project_dir/build/bin/test_applet" \
    > "$project_dir/artifacts/integration.log" 2>&1
cat "$project_dir/artifacts/integration.log"
grep -Eq 'Totals: [0-9]+ passed, 0 failed' "$project_dir/artifacts/integration.log"
! grep -Eq 'FAIL!|QFATAL|ReferenceError|TypeError|Binding loop' "$project_dir/artifacts/integration.log"
