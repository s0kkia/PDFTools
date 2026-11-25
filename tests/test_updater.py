from pathlib import Path

from pdftools.services import updater


def test_update_log_uses_one_line_per_message(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    updater._write_update_log("first")
    updater._write_update_log("second")

    log = tmp_path / "PDFTools" / "Updates" / "update.log"
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert lines[0].endswith(" first")
    assert lines[1].endswith(" second")
