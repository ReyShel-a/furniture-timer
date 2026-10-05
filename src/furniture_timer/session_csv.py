"""Write session rows to CSV (stdlib csv, no Qt)."""

import csv
from collections.abc import Sequence
from pathlib import Path

from furniture_timer.db import SessionRow

CSV_COLUMNS: tuple[str, ...] = SessionRow._fields


def write_sessions_csv(path: Path, rows: Sequence[SessionRow]) -> None:
    """Write UTF-8 BOM CSV with DB column headers; *rows* as stored (unix ts)."""
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_COLUMNS)
        writer.writerows(rows)
