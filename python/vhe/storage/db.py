from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


class PlatformDatabase:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    category TEXT NOT NULL,
                    message TEXT NOT NULL,
                    severity TEXT NOT NULL DEFAULT 'info',
                    payload_json TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS fills (
                    fill_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    quantity INTEGER NOT NULL,
                    fees REAL NOT NULL DEFAULT 0,
                    reason TEXT,
                    filled_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS platform_meta (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def append_event(
        self,
        *,
        category: str,
        message: str,
        severity: str = "info",
        event_type: str = "platform",
        payload: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_log (event_type, category, message, severity, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (event_type, category, message, severity, json.dumps(payload) if payload else None, now),
            )

    def save_fill(self, fill: dict[str, Any]) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO fills
                (fill_id, order_id, symbol, side, price, quantity, fees, reason, filled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fill["fill_id"],
                    fill["order_id"],
                    fill["symbol"],
                    fill["side"],
                    fill["price"],
                    fill["quantity"],
                    fill.get("fees", 0),
                    fill.get("reason"),
                    fill.get("filled_at"),
                ),
            )

    def recent_events(self, limit: int = 40) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT category, message, severity, created_at FROM audit_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "category": row["category"],
                "message": row["message"],
                "severity": row["severity"],
                "timestamp": row["created_at"],
            }
            for row in reversed(rows)
        ]

    def recent_fills(self, limit: int = 25) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM fills ORDER BY filled_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def save_meta(self, key: str, value: dict[str, Any]) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO platform_meta (key, value_json, updated_at)
                VALUES (?, ?, ?)
                """,
                (key, json.dumps(value), now),
            )

    def load_meta(self, key: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute("SELECT value_json FROM platform_meta WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        return json.loads(row["value_json"])

    def persist_fill_dataclass(self, fill: Any) -> None:
        payload = asdict(fill)
        if hasattr(fill.filled_at, "isoformat"):
            payload["filled_at"] = fill.filled_at.isoformat()
        self.save_fill(payload)
