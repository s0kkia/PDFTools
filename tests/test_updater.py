from __future__ import annotations

import hashlib
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from pdftools.services import updater


def _make_archive(path: Path, members: dict[str, bytes] | None = None) -> Path:
    members = members or {"PDFTools/PDFTools.exe": b"fake-exe", "PDFTools/_internal/runtime.dll": b"runtime"}
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return path


def _release_assets(tmp_path: Path, archive: Path, checksum: str | None = None) -> dict:
    digest = checksum or hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum_file = tmp_path / updater.CHECKSUM_NAME
    checksum_file.write_text(f"{digest}  {updater.PACKAGE_NAME}\n", encoding="ascii")
    return {
        "tag_name": "v2.0.3",
        "assets": [
            {"name": updater.PACKAGE_NAME, "browser_download_url": "https://example.invalid/app.zip"},
            {"name": updater.CHECKSUM_NAME, "browser_download_url": "https://example.invalid/SHA256SUMS.txt"},
        ],
        "_local_archive": archive,
        "_local_checksum": checksum_file,
    }


def _fake_download(release):
    def download(url, destination, progress=None, timeout=60):
        source = release["_local_archive"] if url.endswith("app.zip") else release["_local_checksum"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        if progress:
            progress(destination.stat().st_size, destination.stat().st_size)
        return destination
    return download


@pytest.mark.parametrize(("latest", "current", "expected"), [
    ("2.0.3", "2.0.2", True),
    ("v2.0.10", "2.0.9", True),
    ("2.0.2", "2.0.2", False),
    ("2.0.2", "2.0.3", False),
    ("2.0.3", "2.0.3.0", False),
])
def test_version_comparison(latest, current, expected):
    assert updater.is_newer(latest, current) is expected


def test_auto_check_due_first_run_and_fourteen_day_interval():
    now = datetime(2026, 11, 26, 12, 0, 0)
    assert updater.auto_check_due(None, now=now)
    assert not updater.auto_check_due((now - timedelta(days=13, hours=23)).isoformat(), now=now)
    assert updater.auto_check_due((now - timedelta(days=14)).isoformat(), now=now)


def test_auto_check_due_invalid_marker_retries():
    assert updater.auto_check_due("not-a-date", now=datetime(2026, 11, 26))


def test_download_verify_success(tmp_path, monkeypatch):
    archive = _make_archive(tmp_path / "source.zip")
    release = _release_assets(tmp_path, archive)
    monkeypatch.setattr(updater, "_is_windows", lambda: True)
    monkeypatch.setattr(updater, "_updates_root", lambda: tmp_path / "updates")
    monkeypatch.setattr(updater, "_download", _fake_download(release))

    work = updater.download_and_verify(release)

    assert (work / "extracted" / "PDFTools" / "PDFTools.exe").read_bytes() == b"fake-exe"
    assert (tmp_path / "updates" / "update.log").is_file()


def test_download_verify_rejects_checksum_mismatch(tmp_path, monkeypatch):
    archive = _make_archive(tmp_path / "source.zip")
    release = _release_assets(tmp_path, archive, checksum="0" * 64)
    monkeypatch.setattr(updater, "_is_windows", lambda: True)
    monkeypatch.setattr(updater, "_updates_root", lambda: tmp_path / "updates")
    monkeypatch.setattr(updater, "_download", _fake_download(release))

    with pytest.raises(RuntimeError, match="Контрольная сумма"):
        updater.download_and_verify(release)


@pytest.mark.parametrize("bad_name", ["../escape.txt", r"..\\escape.txt", "/absolute.txt", "C:/outside.txt"])
def test_download_verify_rejects_zip_path_traversal(tmp_path, monkeypatch, bad_name):
    archive = _make_archive(tmp_path / "source.zip", {bad_name: b"bad", "PDFTools/PDFTools.exe": b"fake"})
    release = _release_assets(tmp_path, archive)
    monkeypatch.setattr(updater, "_is_windows", lambda: True)
    monkeypatch.setattr(updater, "_updates_root", lambda: tmp_path / "updates")
    monkeypatch.setattr(updater, "_download", _fake_download(release))

    with pytest.raises(RuntimeError, match="недопустимый путь"):
        updater.download_and_verify(release)

    assert not (tmp_path / "escape.txt").exists()


def test_download_verify_rejects_missing_executable(tmp_path, monkeypatch):
    archive = _make_archive(tmp_path / "source.zip", {"PDFTools/readme.txt": b"no exe"})
    release = _release_assets(tmp_path, archive)
    monkeypatch.setattr(updater, "_is_windows", lambda: True)
    monkeypatch.setattr(updater, "_updates_root", lambda: tmp_path / "updates")
    monkeypatch.setattr(updater, "_download", _fake_download(release))

    with pytest.raises(RuntimeError, match="PDFTools.exe"):
        updater.download_and_verify(release)


def test_download_verify_rejects_non_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "_is_windows", lambda: False)
    with pytest.raises(RuntimeError, match="только в Windows"):
        updater.download_and_verify({"assets": []})


def test_cleanup_download_only_inside_updates_root(tmp_path, monkeypatch):
    root = tmp_path / "updates"
    monkeypatch.setattr(updater, "_updates_root", lambda: root)
    work = root / "download"
    work.mkdir(parents=True)
    (work / "partial.zip").write_bytes(b"partial")
    updater.cleanup_download(work)
    assert not work.exists()

    outside = tmp_path / "do-not-delete"
    outside.mkdir()
    updater.cleanup_download(outside)
    assert outside.exists()


def test_launch_update_rejects_non_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "_is_windows", lambda: False)
    with pytest.raises(RuntimeError, match="только в Windows"):
        updater.launch_update(tmp_path, tmp_path, 123)
