from pathlib import Path

from furniture_timer import db
from furniture_timer.db import SessionRow
from furniture_timer.session_csv import CSV_COLUMNS, write_sessions_csv


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
            f"{row.idle_seconds},{row.rate_snapshot},{row.cost},{row.note}"
        )
        assert line == expected


def test_write_sessions_csv_empty_writes_header_only(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    write_sessions_csv(path, [])
    text = path.read_text(encoding="utf-8-sig")
    assert text.splitlines() == [",".join(CSV_COLUMNS)]
