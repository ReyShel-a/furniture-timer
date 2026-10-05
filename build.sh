#!/usr/bin/env bash
# Build dist/FurnitureTimer (onefile, windowed).
set -euo pipefail
cd "$(dirname "$0")"

if [[ -x .venv/bin/python ]]; then
    PYTHON=.venv/bin/python
else
    PYTHON=python3
fi

"$PYTHON" -m pip install -e ".[build]"
"$PYTHON" -m PyInstaller --noconfirm --clean furniture_timer.spec
