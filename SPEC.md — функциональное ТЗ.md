# SPEC.md — Furniture Time Tracker

## 1. Purpose
Track active work time; auto-pause on system inactivity; cost = hours * hourly_rate.

## 2. Functional requirements

### FR-1 Controls
- Start -> timer runs.
- Pause/Resume toggles.
- Stop -> persist session, reset.

### FR-2 Idle detection
- Poll system-wide idle every 1 s.
- Threshold in settings (default 300 s).
- When idle >= threshold:
  - Auto-pause.
  - Modal: "Idle Xs. [Keep] [Discard idle] [Resume]".
  - "Discard idle" subtracts idle seconds from active_seconds.
- On user return while auto-paused: show "Resume?" prompt.

### FR-3 Pricing
- Settings: hourly_rate (float, def 0), currency (str, def "€").
- Live cost = elapsed_sec / 3600 * rate.
- On Stop: persist rate_snapshot + final cost.

### FR-4 Persistence
- sessions(id, start_ts, end_ts, active_seconds, idle_seconds, rate_snapshot, cost, note)
- settings(key, value)
- On startup: load settings only. No session auto-resume.

### FR-5 History (optional v1.1)
- Last 20 sessions list.
- CSV export button.

### FR-6 Tray
- Minimize to tray.
- Tray menu: Show / Start-Pause / Quit.

## 3. UI spec
- Frameless, always-on-top, fixed 260x150, draggable by body.
- Layout:
  - Row1: HH:MM:SS (monospace, 28pt).
  - Row2: "rate €/h  ·  cost €" (14pt).
  - Row3: [Start/Pause] [Stop] [⚙] [×]
- Colors: bg #1e1e1e, fg #e0e0e0, accent #4caf50, danger #e53935.
- Tooltip on hover: session start time.

## 4. Idle detection impl
- Windows: ctypes.windll.user32.GetLastInputInfo -> ms since last input.
- macOS/Linux: pynput global listener timestamp (fallback).
- On any failure: log warning, disable idle feature, keep timer running.

## 5. Non-functional
- Cold start < 2 s.
- All strings via i18n.py.

## 6. Out of scope
Cloud sync, multi-user, projects, PDF invoicing, mobile.