from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

REPOSITORY = "s0kkia/PDFTools"
PACKAGE_NAME = "PDFTools_2.0_Windows_x64.zip"
CHECKSUM_NAME = "SHA256SUMS.txt"
USER_AGENT = "PDFTools-Updater"


def _is_windows() -> bool:
    return os.name == "nt"


def latest_release(timeout: int = 20) -> dict:
    request = Request(
        f"https://api.github.com/repos/{REPOSITORY}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT},
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _version_tuple(value: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", value)
    return tuple(int(number) for number in numbers) or (0,)


def is_newer(latest: str, current: str) -> bool:
    a, b = _version_tuple(latest), _version_tuple(current)
    size = max(len(a), len(b))
    return a + (0,) * (size - len(a)) > b + (0,) * (size - len(b))


def auto_check_due(last_checked: str | None = None, now: datetime | None = None, interval_days: int = 14) -> bool:
    """Return True when the automatic release check is due."""
    if last_checked is None:
        marker = _updates_root() / "last_auto_check.txt"
        try:
            last_checked = marker.read_text(encoding="utf-8").strip() or None
        except OSError:
            last_checked = None
    if not last_checked:
        return True
    try:
        previous = datetime.fromisoformat(last_checked)
    except (TypeError, ValueError):
        return True
    current = now or datetime.now(previous.tzinfo)
    if previous.tzinfo is None and current.tzinfo is not None:
        current = current.replace(tzinfo=None)
    elif previous.tzinfo is not None and current.tzinfo is None:
        current = current.replace(tzinfo=previous.tzinfo)
    return current - previous >= timedelta(days=interval_days)


def mark_auto_check(now: datetime | None = None) -> None:
    marker = _updates_root() / "last_auto_check.txt"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text((now or datetime.now()).isoformat(timespec="seconds"), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _updates_root() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "PDFTools" / "Updates"


def _write_update_log(message: str) -> None:
    """Write diagnostics outside the temporary download folder."""
    root = _updates_root()
    root.mkdir(parents=True, exist_ok=True)
    with (root / "update.log").open("a", encoding="utf-8") as stream:
        stream.write(f"{datetime.now().isoformat(timespec='seconds')} {message}\n")


def _download(url: str, destination: Path, progress=None, timeout: int = 60) -> Path:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"})
    destination.parent.mkdir(parents=True, exist_ok=True)
    received = 0
    with urlopen(request, timeout=timeout) as response, destination.open("wb") as output:
        total = int(response.headers.get("Content-Length", "0") or 0)
        while True:
            chunk = response.read(1024 * 512)
            if not chunk:
                break
            output.write(chunk)
            received += len(chunk)
            if progress:
                progress(received, total)
    return destination


def download_and_verify(release: dict, progress=None) -> Path:
    assets = {asset.get("name"): asset for asset in release.get("assets", [])}
    package = assets.get(PACKAGE_NAME)
    checksum_asset = assets.get(CHECKSUM_NAME)
    if not package or not checksum_asset:
        raise RuntimeError("В релизе отсутствует ZIP программы или SHA256SUMS.txt.")
    if not _is_windows():
        raise RuntimeError("Установка обновлений поддерживается только в Windows.")

    version = release.get("tag_name", "unknown").lstrip("v")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    work = _updates_root() / f"{version}-{stamp}"
    work.mkdir(parents=True, exist_ok=False)
    _write_update_log(f"Начата загрузка обновления {release.get('tag_name', version)}; рабочая папка: {work}")
    archive = work / PACKAGE_NAME
    checksum_file = work / CHECKSUM_NAME
    try:
        _download(package.get("browser_download_url") or package["url"], archive, progress)
        _download(checksum_asset.get("browser_download_url") or checksum_asset["url"], checksum_file)
    except Exception as exc:
        _write_update_log(f"ОШИБКА загрузки: {exc}; файлы оставлены: {work}")
        raise

    expected = None
    for line in checksum_file.read_text(encoding="utf-8-sig").splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[-1].strip("*").lower() == PACKAGE_NAME.lower():
            expected = parts[0].lower()
            break
    if not expected or not re.fullmatch(r"[0-9a-fA-F]{64}", expected) or sha256(archive) != expected:
        _write_update_log(f"ОШИБКА SHA256; файлы оставлены: {work}")
        raise RuntimeError(f"Контрольная сумма ZIP не совпадает или имеет неверный формат. Файлы оставлены для диагностики: {work}")
    _write_update_log(f"Загрузка {version} завершена; SHA256 проверена; архив: {archive}")

    extracted = work / "extracted"
    extracted.mkdir()
    try:
        with zipfile.ZipFile(archive) as zipped:
            root = extracted.resolve()
            bad_member = zipped.testzip()
            if bad_member:
                raise RuntimeError(f"Архив повреждён: {bad_member}")
            for member in zipped.infolist():
                # ZIP names may use Windows separators even when validated on another OS.
                normalized = member.filename.replace("\\", "/")
                parts = normalized.split("/")
                if normalized.startswith("/") or (parts and ":" in parts[0]) or ".." in parts:
                    raise RuntimeError("Архив содержит недопустимый путь. Установка отменена.")
                mode = (member.external_attr >> 16) & 0xFFFF
                if (mode & 0o170000) == 0o120000:
                    raise RuntimeError("Архив содержит символическую ссылку. Установка отменена.")
                target = (extracted / normalized).resolve()
                if target != root and root not in target.parents:
                    raise RuntimeError("Архив содержит недопустимый путь. Установка отменена.")
            zipped.extractall(extracted)

        app_folder = extracted / "PDFTools"
        if not (app_folder / "PDFTools.exe").is_file():
            raise RuntimeError("В архиве не найдена PDFTools/PDFTools.exe.")
        _write_update_log(f"Архив распакован; подготовлено к установке: {app_folder}")
        return work
    except Exception as exc:
        _write_update_log(f"ОШИБКА проверки/распаковки архива: {exc}; архив сохранён: {archive}")
        raise


def cleanup_download(work: Path) -> None:
    """Remove a downloaded/staged update when the user cancels installation."""
    work = work.resolve()
    root = _updates_root().resolve()
    if work.parent == root and work.name not in {"PreviousVersion", "PreviousVersion.new"}:
        shutil.rmtree(work, ignore_errors=True)


def launch_update(work: Path, install_dir: Path, process_id: int) -> Path:
    """Install a verified update, retaining exactly one previous application version."""
    if not _is_windows():
        raise RuntimeError("Автоматическая установка доступна только в Windows.")

    work = work.resolve()
    updates_root = _updates_root().resolve()
    install_dir = install_dir.resolve()
    staged = (work / "extracted" / "PDFTools").resolve()
    if work.parent != updates_root:
        raise RuntimeError("Папка обновления находится вне разрешённого каталога.")
    if not (install_dir / "PDFTools.exe").is_file() or not (staged / "PDFTools.exe").is_file():
        _write_update_log(f"ОШИБКА: не найдена текущая или новая PDFTools.exe; install={install_dir}; staged={staged}")
        raise RuntimeError("Не найдена текущая или новая версия PDFTools.exe.")
    _write_update_log(f"Запрошена установка; PID={process_id}; каталог программы: {install_dir}")

    updates_root.mkdir(parents=True, exist_ok=True)
    log = updates_root / "update.log"
    script = work / "install_update.ps1"
    previous = updates_root / "PreviousVersion"
    old_install = install_dir.with_name(install_dir.name + ".update-previous")
    new_install = install_dir.with_name(install_dir.name + ".update-new")

    ps = r"""
$ErrorActionPreference = 'Stop'
$pidToWait = __PID__
$install = '__INSTALL__'
$staged = '__STAGED__'
$updatesRoot = '__UPDATES_ROOT__'
$previous = Join-Path $updatesRoot 'PreviousVersion'
$oldInstall = '__OLD_INSTALL__'
$newInstall = '__NEW_INSTALL__'
$work = '__WORK__'
$log = '__LOG__'
$checkMarker = '__CHECK_MARKER__'

function Write-Log($message) {
    $line = "$(Get-Date -Format o) $message"
    # Logging must never interrupt installation if another process briefly holds the log.
    for ($attempt = 0; $attempt -lt 8; $attempt++) {
        try {
            Add-Content -LiteralPath $log -Value $line -Encoding UTF8 -ErrorAction Stop
            return
        }
        catch {
            Start-Sleep -Milliseconds 250
        }
    }
}
function Remove-Safe($path) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}

$oldMoved = $false
$newStarted = $false
try {
    Write-Log "------------------------------------------------------------"
    Write-Log "Update started. Waiting for PDFTools PID $pidToWait."
    while (Get-Process -Id $pidToWait -ErrorAction SilentlyContinue) {
        Start-Sleep -Seconds 1
    }
    Write-Log "Application closed. Preparing new version."

    Remove-Safe $newInstall
    Remove-Safe $oldInstall
    New-Item -ItemType Directory -Path $newInstall -Force | Out-Null
    Copy-Item -Path (Join-Path $staged '*') -Destination $newInstall -Recurse -Force
    if (!(Test-Path -LiteralPath (Join-Path $newInstall 'PDFTools.exe'))) {
        throw "Staged executable missing."
    }
    Write-Log "New version staged."

    Move-Item -LiteralPath $install -Destination $oldInstall
    $oldMoved = $true
    Write-Log "Current version moved temporarily: $oldInstall"

    Move-Item -LiteralPath $newInstall -Destination $install
    Write-Log "New version installed."

    $newProcess = Start-Process -FilePath (Join-Path $install 'PDFTools.exe') -WorkingDirectory $install -PassThru
    Start-Sleep -Seconds 15
    $newProcess.Refresh()
    if ($newProcess.HasExited) {
        throw "New PDFTools process exited during startup (code $($newProcess.ExitCode))."
    }
    $newStarted = $true
    Write-Log "New version started successfully (PID $($newProcess.Id))."
    try {
        Set-Content -LiteralPath $checkMarker -Value (Get-Date -Format o) -Encoding UTF8
        Write-Log "Automatic update check timestamp saved."
    }
    catch {
        Write-Log "WARNING: could not save automatic update timestamp: $_"
    }

    # Replace the previous backup only after the new version is confirmed running.
    Remove-Safe $previous
    Move-Item -LiteralPath $oldInstall -Destination $previous
    $oldMoved = $false
    Write-Log "Previous version saved at $previous. Older backup discarded."

    # Cleanup is best-effort and must never close a successfully started application.
    Set-Location $env:TEMP
    try {
        Remove-Safe $work
        Get-ChildItem -LiteralPath $updatesRoot -Force |
            Where-Object { $_.Name -notin @('PreviousVersion', 'update.log') } |
            ForEach-Object {
                try { Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction Stop }
                catch { Write-Log "WARNING: temporary folder retained for later cleanup: $($_.FullName); $_" }
            }
        Write-Log "Update completed. Temporary cleanup finished."
    }
    catch {
        Write-Log "WARNING: update installed and running, but temporary cleanup was deferred: $_"
    }
}
catch {
    Write-Log "UPDATE ERROR: $_"
    try {
        if ($newProcess -and !$newProcess.HasExited) {
            Stop-Process -Id $newProcess.Id -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
        }
        if ($oldMoved -and (Test-Path -LiteralPath $oldInstall)) {
            Remove-Safe $install
            Move-Item -LiteralPath $oldInstall -Destination $install
            Write-Log "Previous running version restored."
            Start-Process -FilePath (Join-Path $install 'PDFTools.exe') -WorkingDirectory $install
            Write-Log "Previous version restarted."
        }
        Remove-Safe $newInstall
        # Keep the downloaded archive and installer script after failure for diagnostics.
        Set-Location $env:TEMP
    }
    catch {
        Write-Log "ROLLBACK ERROR: $_"
    }
}
"""
    replacements = {
        "__PID__": str(int(process_id)),
        "__INSTALL__": str(install_dir),
        "__STAGED__": str(staged),
        "__UPDATES_ROOT__": str(updates_root),
        "__OLD_INSTALL__": str(old_install),
        "__NEW_INSTALL__": str(new_install),
        "__WORK__": str(work),
        "__LOG__": str(log),
        "__CHECK_MARKER__": str(updates_root / "last_auto_check.txt"),
    }
    for key, value in replacements.items():
        ps = ps.replace(key, value.replace("'", "''"))
    script.write_text(ps, encoding="utf-8")
    import base64
    encoded = base64.b64encode(ps.encode("utf-16le")).decode("ascii")
    _write_update_log(f"Запускается установщик PowerShell; скрипт: {script}; журнал: {log}")
    subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
        cwd=str(work),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
    )
    return log
