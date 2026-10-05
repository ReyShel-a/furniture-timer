# TASKS.md — Implementation order

1.  Scaffold: pyproject.toml, src/furniture_timer/, main.py.
2.  settings.py: load/save via sqlite (platformdirs path).
3.  db.py: init + schema version 1.
4.  idle.py: Windows GetLastInputInfo; cross-platform shim.
5.  timer_model.py: state machine IDLE|RUNNING|PAUSED|AUTO_PAUSED.
6.  ui/widget.py: frameless window, drag, dark theme, buttons.
7.  Wire QTimer(1s) -> model -> UI tick.
8.  Idle -> auto-pause -> modal -> resume/discard logic.
9.  Cost calc + live label.
10. Persist session on Stop.
11. Settings dialog: rate, currency, idle threshold.
12. History panel + CSV export.
13. System tray.
14. i18n en/ru.
15. PyInstaller spec + build.ps1 / build.sh.
16. Tests: idle pause, resume, cost accuracy, discard-idle math.

## Acceptance
- Start -> run -> 5 min idle -> auto-pause + prompt.
- Resume restores timer; Discard removes idle seconds.
- Stop writes correct row (active_seconds, cost).
- Widget <= 80 MB RAM, <= 1% CPU idle, cold start < 2 s.