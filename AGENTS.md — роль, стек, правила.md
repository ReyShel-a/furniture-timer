# AGENTS.md — Furniture Time Tracker

## Role
Senior desktop dev. Build minimal always-on-top widget: work-time tracker + cost calc for a furniture constructor.

## Stack (locked — do not substitute)
- Python 3.11+
- UI: PySide6 (Qt6)
- Persistence: sqlite3 (stdlib)
- Idle detection: ctypes + user32.GetLastInputInfo (Windows); pynput fallback (macOS/Linux)
- Paths: platformdirs
- Packaging: PyInstaller (onefile, windowed)

## Hard constraints
- Primary OS: Windows 10/11. macOS/Linux best-effort.
- Widget: frameless, always-on-top, ~260x150 px, draggable, dark theme.
- RAM < 80 MB idle; CPU < 1% idle.
- No network, no telemetry, no admin rights.
- Data at `%APPDATA%/FurnitureTimer/db.sqlite` (platformdirs).

## Coding rules
- Type hints mandatory.
- Max deps: PySide6, pynput, platformdirs.
- Files <= 300 LOC. One responsibility per module.
- Log to file, not stdout. Never crash on idle-detect failure — degrade.
- All user-facing strings in `i18n.py` (en + ru).

## Deliverables
Implement per SPEC.md in order of TASKS.md.