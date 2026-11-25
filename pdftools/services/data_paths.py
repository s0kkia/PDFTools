from __future__ import annotations
import json
import os
import sys
from pathlib import Path

APP_NAME = "PDFTools"
CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_NAME
CONFIG_FILE = CONFIG_DIR / "settings.json"

def _load_mode() -> str:
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        mode = data.get("storage_mode", "appdata")
        return mode if mode in {"appdata", "local"} else "appdata"
    except (OSError, ValueError, TypeError):
        return "appdata"

def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]

def data_dir(kind: str | None = None) -> Path:
    if _load_mode() == "local":
        base = app_root() / "UserData"
    else:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_NAME
    target = base / kind if kind else base
    target.mkdir(parents=True, exist_ok=True)
    return target

def settings_path() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_FILE

def set_storage_mode(mode: str) -> None:
    if mode not in {"appdata", "local"}:
        raise ValueError("storage_mode должен быть appdata или local")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    current = {}
    try:
        current = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    current["storage_mode"] = mode
    CONFIG_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
