from pathlib import Path

from furniture_timer import db
from furniture_timer.db import SessionRow
from furniture_timer.session_csv import (
    BLANK_PROJECT,
    CSV_COLUMNS,
    GROUP_COLUMNS,
    group_sessions_by_project,
    write_selection_report_csv,
    write_sessions_csv,
)


def test_csv_columns_match_session_row() -> None:
    assert CSV_COLUMNS == SessionRow._fields
    assert CSV_COLUMNS == (
        "id",
        "start_ts",
        "end_ts",
        "active_seconds",
        "idle_seconds",
        "rate_snapshot",
        "cost",
        "note",
        "project_number",
        "project_name",
        "client_name",
    )


def test_write_sessions_csv_utf8_sig_headers_and_values(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "db.sqlite")
    try:
        for i in range(1, 26):
            db.insert_session(
                conn, i * 10, i * 10 + 5, i, i % 3, float(i), float(i) / 2, f"n{i}"
            )
        rows = db.list_recent_sessions(conn)
    finally:
        conn.close()

    path = tmp_path / "sessions.csv"
    write_sessions_csv(path, rows)

    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    assert len(lines) == 21
    assert lines[0] == ",".join(CSV_COLUMNS)
    assert len(rows) == 20
    for line, row in zip(lines[1:], rows, strict=True):
        expected = (
            f"{row.id},{row.start_ts},{row.end_ts},{row.active_seconds},"
            f"{row.idle_seconds},{row.rate_snapshot},{row.cost},{row.note},"
            f"{row.project_number},{row.project_name},{row.client_name}"
        )
        assert line == expected


def test_write_sessions_csv_empty_writes_header_only(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    write_sessions_csv(path, [])
    text = path.read_text(encoding="utf-8-sig")
    assert text.splitlines() == [",".join(CSV_COLUMNS)]


def test_group_sessions_uses_newest_name_and_first_seen_order() -> None:
    older = SessionRow(1, 1, 2, 10, 0, 0.0, 1.5, "", "7", "Old", "")
    newer = SessionRow(3, 3, 4, 20, 0, 0.0, 2.5, "", "7", "Kitchen", "")
    blank = SessionRow(2, 2, 3, 5, 0, 0.0, 0.5, "", "  ", "  ", "")
    groups = group_sessions_by_project([older, blank, newer])
    assert [(group.number, group.name, group.active_seconds, group.cost) for group in groups] == [
        ("7", "Kitchen", 30, 4.0),
        ("", BLANK_PROJECT, 5, 0.5),
    ]


def test_write_selection_report_csv_appends_groups_and_total(tmp_path: Path) -> None:
    rows = [
        SessionRow(1, 10, 20, 3600, 0, 20.0, 10.0, "", "7", "Kitchen", "Ivan"),
        SessionRow(2, 30, 40, 1800, 0, 20.0, 5.0, "", "12", "Wardrobe", "Anna"),
    ]
    path = tmp_path / "report.csv"
    write_selection_report_csv(path, rows)
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    assert lines[0] == ",".join(CSV_COLUMNS)
    assert lines[1].startswith("1,10,20,3600,")
    assert lines[2].startswith("2,30,40,1800,")
    assert lines[3] == ""
    assert lines[4] == ",".join(GROUP_COLUMNS)
    assert lines[5] == "7,Kitchen,3600,10.0"
    assert lines[6] == "12,Wardrobe,1800,5.0"
    assert lines[7] == "TOTAL,,5400,15.0"
