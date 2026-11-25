from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

REPOSITORY = "s0kkia/PDFTools"
PACKAGE_NAME = "PDFTools_2.0_Windows_x64.zip"
CHECKSUM_NAME = "SHA256SUMS.txt"
USER_AGENT = "PDFTools-Updater"


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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    if os.name != "nt":
        raise RuntimeError("Установка обновлений поддерживается только в Windows.")

    work = Path(tempfile.mkdtemp(prefix="PDFTools-update-"))
    archive = work / PACKAGE_NAME
    checksum_file = work / CHECKSUM_NAME
    _download(package.get("browser_download_url") or package["url"], archive, progress)
    _download(checksum_asset.get("browser_download_url") or checksum_asset["url"], checksum_file)

    expected = None
    for line in checksum_file.read_text(encoding="utf-8-sig").splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[-1].strip("*").lower() == PACKAGE_NAME.lower():
            expected = parts[0].lower()
            break
    if not expected or sha256(archive) != expected:
        shutil.rmtree(work, ignore_errors=True)
        raise RuntimeError("Контрольная сумма ZIP не совпадает. Установка отменена.")

    extracted = work / "extracted"
    extracted.mkdir()
    with zipfile.ZipFile(archive) as zipped:
        root = extracted.resolve()
        for member in zipped.infolist():
            target = (extracted / member.filename).resolve()
            if target != root and root not in target.parents:
                raise RuntimeError("Архив содержит недопустимый путь. Установка отменена.")
        zipped.extractall(extracted)

    app_folder = extracted / "PDFTools"
    executable = app_folder / "PDFTools.exe"
    if not executable.is_file():
        raise RuntimeError("В архиве не найдена PDFTools/PDFTools.exe.")
    return work


def launch_update(work: Path, install_dir: Path, process_id: int) -> None:
    if os.name != "nt":
        raise RuntimeError("Автоматическая установка доступна только в Windows.")
    install_dir = install_dir.resolve()
    staged = (work / "extracted" / "PDFTools").resolve()
    executable = install_dir / "PDFTools.exe"
    if not executable.is_file() or not staged.joinpath("PDFTools.exe").is_file():
        raise RuntimeError("Не найдена текущая или новая версия PDFTools.exe.")

    # Run the updater outside the application folder so it survives replacement.
    script = work / "install_update.ps1"
    backup = install_dir.with_name(install_dir.name + ".backup")
    log = work / "update.log"
    ps = r"""
$ErrorActionPreference = 'Stop'
$pidToWait = __PID__
$install = '__INSTALL__'
$staged = '__STAGED__'
$backup = '__BACKUP__'
$exe = Join-Path $install 'PDFTools.exe'
$log = '__LOG__'
Start-Sleep -Seconds 2
try {
    Wait-Process -Id $pidToWait -ErrorAction SilentlyContinue
    if (Test-Path $backup) { Remove-Item -LiteralPath $backup -Recurse -Force }
    Move-Item -LiteralPath $install -Destination $backup
    try {
        Move-Item -LiteralPath $staged -Destination $install
        if (!(Test-Path (Join-Path $install 'PDFTools.exe'))) { throw 'New executable missing after copy' }
        Start-Process -FilePath (Join-Path $install 'PDFTools.exe')
        Start-Sleep -Seconds 5
        if (Get-Process -Name 'PDFTools' -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $backup -Recurse -Force
        }
    } catch {
        if (Test-Path $install) { Remove-Item -LiteralPath $install -Recurse -Force }
        if (Test-Path $backup) { Move-Item -LiteralPath $backup -Destination $install }
        Start-Process -FilePath (Join-Path $install 'PDFTools.exe')
        throw
    }
} catch {
    $_ | Out-File -FilePath $log -Append -Encoding utf8
}
""".replace("__PID__", str(int(process_id)))
    replacements = {
        "__INSTALL__": str(install_dir),
        "__STAGED__": str(staged),
        "__BACKUP__": str(backup),
        "__LOG__": str(log),
    }
    for key, value in replacements.items():
        ps = ps.replace(key, value.replace("'", "''"))
    script.write_text(ps, encoding="utf-8")
    encoded = __import__("base64").b64encode(ps.encode("utf-16le")).decode("ascii")
    subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
    )
