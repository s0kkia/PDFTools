from __future__ import annotations
from pathlib import Path
import sqlite3
from datetime import datetime
from pdftools.services.data_paths import data_dir


class HistoryStore:
    def __init__(self, db_path: str | Path | None = None):
        base = data_dir("database")
        self.db_path = Path(db_path) if db_path else base / "history.sqlite3"
        self._init()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init(self):
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS operations(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                operation TEXT NOT NULL,
                source TEXT,
                output TEXT,
                status TEXT NOT NULL,
                details TEXT
            )""")

    def add(self, operation: str, source: str = "", output: str = "", status: str = "OK", details: str = ""):
        with self._connect() as db:
            db.execute("INSERT INTO operations(created_at,operation,source,output,status,details) VALUES(?,?,?,?,?,?)",
                       (datetime.now().isoformat(timespec="seconds"), operation, source, output, status, details))

    def recent(self, limit: int = 300):
        with self._connect() as db:
            return db.execute("SELECT created_at,operation,source,output,status,details FROM operations ORDER BY id DESC LIMIT ?",
                              (limit,)).fetchall()
