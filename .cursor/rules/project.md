---
description: Furniture Time Tracker — project rules
globs: ["**/*.py"]
alwaysApply: true
---

# Project context
Read and follow AGENTS.md, SPEC.md, and TASKS.md in the repository root.

# Workflow
1. Always start in Plan mode before writing code.
2. Implement tasks strictly in order from TASKS.md.
3. After each task, run the relevant acceptance check from TASKS.md.
4. Do not skip tasks; do not combine unrelated tasks.

# Constraints
- Stack locked: Python 3.11+, PySide6, sqlite3, ctypes (Windows idle), platformdirs.
- Max 300 LOC per file. Type hints mandatory.
- All user-facing strings in i18n.py (en + ru).
- Never crash on idle-detect failure — degrade gracefully.

# Definition of Done
- Code compiles, tests for the task pass.
- No new dependencies beyond: PySide6, pynput, platformdirs.
- Commit message follows: "task-N: <short description>".

# Language
- All code comments, commit messages, docstrings: English.
- All user-facing strings: via i18n.py (en + ru).
- All communication in chat with the user: match the user's last message language.
- NEVER modify AGENTS.md, SPEC.md, or TASKS.md unless explicitly instructed.
- NEVER translate these three files. They are the source of truth.

# Idle state semantics (Tasks 5 and 8)
- Auto-pause is RETROACTIVE to idle_start_ts, not threshold-crossing time.
- Modal buttons:
  - Keep         -> state PAUSED,   idle_seconds += idle_elapsed
  - Resume       -> state RUNNING,  idle_seconds += idle_elapsed
  - Discard idle -> state RUNNING,  idle_elapsed dropped entirely (incl. pre-threshold seconds)
- Modal is non-blocking (no focus steal).
- "Resume?" prompt appears ONLY when: state == AUTO_PAUSED AND user returned AND modal is not on screen.
- If user chose Keep earlier, never show "Resume?" prompt.

# i18n
- Create src/furniture_timer/i18n.py in Task 6 with the stub API.
- All user-facing strings added to _STRINGS["en"] as they appear.
- Task 14 = fill _STRINGS["ru"] and wire Settings.language; not creation of the module.
- Never use f-strings for UI text; always t("key", **fmt).