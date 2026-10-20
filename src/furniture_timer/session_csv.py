"""Write session rows to CSV (stdlib csv, no Qt)."""

import csv
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

from furniture_timer.db import SessionRow

CSV_COLUMNS: tuple[str, ...] = SessionRow._fields
GROUP_COLUMNS: tuple[str, ...] = (
    "project_number",
    "project_name",
    "active_seconds",
    "cost",
)
BLANK_PROJECT = "—"


class ProjectTotal(NamedTuple):
    number: str
    name: str
    active_seconds: int
    cost: float


def group_sessions_by_project(rows: Sequence[SessionRow]) -> list[ProjectTotal]:
    """Group by project number. The name is taken from the newest session in the group.

    Group order follows the first row of that number. A blank name becomes an em dash.
    """
    order: list[str] = []
    grouped: dict[str, list[SessionRow]] = {}
    for row in rows:
        number = row.project_number.strip()
        if number not in grouped:
            order.append(number)
            grouped[number] = []
        grouped[number].append(row)
    totals: list[ProjectTotal] = []
    for number in order:
        members = grouped[number]
        newest = max(members, key=lambda member: member.id)
        name = newest.project_name.strip() or BLANK_PROJECT
        totals.append(
            ProjectTotal(
                number,
                name,
                sum(member.active_seconds for member in members),
                sum(member.cost for member in members),
            )
        )
    return totals


def write_sessions_csv(path: Path, rows: Sequence[SessionRow]) -> None:
    """Write UTF-8 BOM CSV with DB column headers; *rows* as stored (unix ts)."""
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_COLUMNS)
        writer.writerows(rows)


def write_selection_report_csv(path: Path, rows: Sequence[SessionRow]) -> None:
    """Write selected sessions, then per-project totals and a TOTAL row."""
    groups = group_sessions_by_project(rows)
    total_seconds = sum(group.active_seconds for group in groups)
    total_cost = sum(group.cost for group in groups)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_COLUMNS)
        writer.writerows(rows)
        writer.writerow([])
        writer.writerow(GROUP_COLUMNS)
        writer.writerows(groups)
        writer.writerow(("TOTAL", "", total_seconds, total_cost))
