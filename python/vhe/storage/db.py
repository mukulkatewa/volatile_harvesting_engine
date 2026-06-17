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

                CREATE TABLE IF NOT EXISTS paper_sessions (
                    session_id TEXT PRIMARY KEY,
                    trading_date TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    initial_cash REAL NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    final_equity REAL,
                    total_pnl REAL,
                    realized_pnl REAL,
                    unrealized_pnl REAL,
                    fees_paid REAL,
                    fill_count INTEGER NOT NULL DEFAULT 0,
                    buy_fills INTEGER NOT NULL DEFAULT 0,
                    sell_fills INTEGER NOT NULL DEFAULT 0,
                    max_exposure_pct REAL NOT NULL DEFAULT 0,
                    max_drawdown_pct REAL NOT NULL DEFAULT 0,
                    peak_equity REAL,
                    strategy_json TEXT,
                    status TEXT NOT NULL DEFAULT 'active'
                );

                CREATE TABLE IF NOT EXISTS session_equity_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    equity REAL NOT NULL,
                    cash REAL NOT NULL,
                    gross_exposure REAL NOT NULL,
                    unrealized_pnl REAL NOT NULL,
                    realized_pnl REAL NOT NULL,
                    recorded_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS session_fills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    fill_id TEXT NOT NULL,
                    UNIQUE(session_id, fill_id)
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
        side = payload.get("side")
        if hasattr(side, "value"):
            payload["side"] = side.value
        filled_at = getattr(fill, "filled_at", None) or getattr(fill, "timestamp", None)
        if hasattr(filled_at, "isoformat"):
            payload["filled_at"] = filled_at.isoformat()
        else:
            payload["filled_at"] = datetime.now(tz=timezone.utc).isoformat()
        payload["fill_id"] = f"{fill.order_id}:{fill.quantity}:{payload['filled_at']}"
        self.save_fill(payload)
        return payload["fill_id"]

    def link_fill_to_session(self, session_id: str, fill_id: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO session_fills (session_id, fill_id) VALUES (?, ?)",
                (session_id, fill_id),
            )

    def create_paper_session(
        self,
        *,
        session_id: str,
        trading_date: str,
        mode: str,
        initial_cash: float,
        started_at: str,
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO paper_sessions
                (session_id, trading_date, mode, initial_cash, started_at, peak_equity, status)
                VALUES (?, ?, ?, ?, ?, ?, 'active')
                """,
                (session_id, trading_date, mode, initial_cash, started_at, initial_cash),
            )

    def get_active_paper_session(self) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM paper_sessions WHERE status = 'active' ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def get_paper_session(self, session_id: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM paper_sessions WHERE session_id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        payload = dict(row)
        payload["strategy_breakdown"] = json.loads(payload.pop("strategy_json") or "{}")
        return payload

    def list_paper_sessions(self, *, limit: int = 30) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM paper_sessions ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        sessions: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["strategy_breakdown"] = json.loads(payload.pop("strategy_json") or "{}")
            sessions.append(payload)
        return sessions

    def close_paper_session(
        self,
        *,
        session_id: str,
        ended_at: str,
        final_equity: float,
        total_pnl: float,
        realized_pnl: float,
        unrealized_pnl: float,
        fees_paid: float,
        fill_count: int,
        strategy_breakdown: dict[str, int],
        max_exposure_pct: float,
        max_drawdown_pct: float,
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE paper_sessions
                SET ended_at = ?, final_equity = ?, total_pnl = ?, realized_pnl = ?, unrealized_pnl = ?,
                    fees_paid = ?, fill_count = ?, strategy_json = ?, max_exposure_pct = ?,
                    max_drawdown_pct = ?, status = 'closed'
                WHERE session_id = ?
                """,
                (
                    ended_at,
                    final_equity,
                    total_pnl,
                    realized_pnl,
                    unrealized_pnl,
                    fees_paid,
                    fill_count,
                    json.dumps(strategy_breakdown),
                    max_exposure_pct,
                    max_drawdown_pct,
                    session_id,
                ),
            )

    def increment_session_fill(self, session_id: str, *, side: str, strategy: str) -> None:
        buy_inc = 1 if side == "BUY" else 0
        sell_inc = 1 if side == "SELL" else 0
        with self.connection() as conn:
            row = conn.execute("SELECT strategy_json FROM paper_sessions WHERE session_id = ?", (session_id,)).fetchone()
            breakdown = json.loads(row["strategy_json"] or "{}") if row else {}
            breakdown[strategy] = breakdown.get(strategy, 0) + 1
            conn.execute(
                """
                UPDATE paper_sessions
                SET fill_count = fill_count + 1,
                    buy_fills = buy_fills + ?,
                    sell_fills = sell_fills + ?,
                    strategy_json = ?
                WHERE session_id = ?
                """,
                (buy_inc, sell_inc, json.dumps(breakdown), session_id),
            )

    def update_session_risk_peaks(
        self,
        session_id: str,
        *,
        max_exposure_pct: float,
        max_drawdown_pct: float,
        peak_equity: float,
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE paper_sessions
                SET max_exposure_pct = ?, max_drawdown_pct = ?, peak_equity = ?
                WHERE session_id = ?
                """,
                (max_exposure_pct, max_drawdown_pct, peak_equity, session_id),
            )

    def record_session_snapshot(
        self,
        *,
        session_id: str,
        equity: float,
        cash: float,
        gross_exposure: float,
        unrealized_pnl: float,
        realized_pnl: float,
    ) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO session_equity_snapshots
                (session_id, equity, cash, gross_exposure, unrealized_pnl, realized_pnl, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, equity, cash, gross_exposure, unrealized_pnl, realized_pnl, now),
            )

    def session_snapshots(self, session_id: str) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM session_equity_snapshots WHERE session_id = ? ORDER BY recorded_at ASC",
                (session_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def fills_for_session(self, session_id: str) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT f.*
                FROM fills f
                JOIN session_fills sf ON sf.fill_id = f.fill_id
                WHERE sf.session_id = ?
                ORDER BY f.filled_at ASC
                """,
                (session_id,),
            ).fetchall()
        return [dict(row) for row in rows]
