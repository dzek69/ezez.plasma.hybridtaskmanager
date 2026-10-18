#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cmake -S "$project_dir" -B "$project_dir/build" -G Ninja \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DCMAKE_INSTALL_PREFIX="$HOME/.local" \
    -DKDE_INSTALL_PLUGINDIR=lib/qt6/plugins
cmake --build "$project_dir/build" -j 2
ctest --test-dir "$project_dir/build" --output-on-failure
bash "$project_dir/scripts/test-integration.sh"
staging_dir=$(mktemp -d -t hybrid-taskmanager-install.XXXXXXXX)
trap 'rm -rf -- "$staging_dir"' EXIT
cmake --install "$project_dir/build" --prefix "$staging_dir"
# Replace files atomically: never truncate a library already mapped by Plasma.
python3 - "$staging_dir" "$HOME/.local" <<'PY'
import os
from pathlib import Path
import shutil
import sys
import tempfile
source, destination = map(Path, sys.argv[1:])
for file in source.rglob('*'):
    if not file.is_file():
        continue
    target = destination / file.relative_to(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=target.parent)
    os.close(fd)
    try:
        shutil.copy2(file, temporary)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
PY
# Keep Chromium web apps from being shown as the browser (see README).
python3 "$project_dir/scripts/chromium-pwa.py"
if [[ "${1:-}" == --activate ]]; then
    python3 "$project_dir/scripts/panel.py" activate
fi
