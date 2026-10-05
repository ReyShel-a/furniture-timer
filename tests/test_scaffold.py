import sys
from pathlib import Path

import pytest

import furniture_timer
from furniture_timer import main as main_module
from furniture_timer import paths


def test_package_has_version() -> None:
    assert isinstance(furniture_timer.__version__, str)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path layout")
def test_data_dir_is_roaming_appdata() -> None:
    assert paths.data_dir().parts[-2:] == ("Roaming", "FurnitureTimer")
    assert paths.db_path().name == "db.sqlite"


def test_main_logs_to_file_not_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(paths, "log_dir", lambda: tmp_path / "logs")
    monkeypatch.setattr(paths, "db_path", lambda: tmp_path / "db.sqlite")
    monkeypatch.setattr(main_module, "_run_gui", lambda settings, conn: 0)

    assert main_module.main() == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    log_file = tmp_path / "logs" / paths.LOG_FILENAME
    assert "starting" in log_file.read_text(encoding="utf-8")
