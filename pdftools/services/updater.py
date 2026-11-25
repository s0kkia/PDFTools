from __future__ import annotations
from pathlib import Path
from urllib.request import Request, urlopen
import hashlib
import json
import os
import subprocess
import sys
import tempfile


REPOSITORY = "s0kkia/PDFTools"


def latest_release(timeout: int = 15) -> dict:
    req = Request(f"https://api.github.com/repos/{REPOSITORY}/releases/latest",
                  headers={"Accept": "application/vnd.github+json", "User-Agent": "PDFTools-Updater"})
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def download_asset(asset_url: str, destination: Path, progress=None, timeout: int = 30) -> Path:
    req = Request(asset_url, headers={"Accept": "application/octet-stream", "User-Agent": "PDFTools-Updater"})
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(req, timeout=timeout) as response, destination.open("wb") as out:
        total = int(response.headers.get("Content-Length", "0") or 0)
        received = 0
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
            received += len(chunk)
            if progress:
                progress(received, total)
    return destination


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stage_windows_installer(installer: Path):
    """Launches the downloaded installer; do not overwrite a running executable in-place."""
    if os.name != "nt":
        raise RuntimeError("Автоматическая установка доступна только в Windows")
    os.startfile(str(installer))
