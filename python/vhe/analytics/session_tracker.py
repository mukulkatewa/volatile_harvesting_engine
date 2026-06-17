from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from vhe.analytics.paper_stats import classify_strategy, trading_date_ist
from vhe.backtest.models import Fill
from vhe.storage.db import PlatformDatabase


class PaperSessionTracker:
    def __init__(self, database: PlatformDatabase, *, mode: str, initial_cash: float) -> None:
        self.database = database
        self.mode = mode
        self.initial_cash = initial_cash
        self._session_id: str | None = None
        self._peak_equity = initial_cash
        self._max_drawdown_pct = 0.0
        self._max_exposure_pct = 0.0
        self._last_snapshot_at: datetime | None = None
        self._snapshot_interval_seconds = 60.0

    @property
    def session_id(self) -> str | None:
        return self._session_id

    def bootstrap(self) -> None:
        active = self.database.get_active_paper_session()
        if active is not None:
            self._session_id = active["session_id"]
            self._peak_equity = float(active.get("peak_equity") or active.get("initial_cash") or self.initial_cash)
            self._max_drawdown_pct = float(active.get("max_drawdown_pct") or 0)
            self._max_exposure_pct = float(active.get("max_exposure_pct") or 0)
            return
        self._open_session(reset_suffix=None)

    def on_reset_paper(self, *, initial_cash: float) -> None:
        self.initial_cash = initial_cash
        if self._session_id:
            self._close_session(portfolio={"equity": initial_cash, "cash": initial_cash, "gross_exposure": 0, "unrealized_pnl": 0, "realized_pnl": 0, "fees_paid": 0})
        self._open_session(reset_suffix=self._next_reset_suffix())

    def on_market_close(self, portfolio: dict[str, Any]) -> None:
        if self._session_id:
            self._close_session(portfolio=portfolio)

    def on_market_open(self, portfolio: dict[str, Any]) -> None:
        if self._session_id is None:
            self._open_session(reset_suffix=None)
            return
        active = self.database.get_active_paper_session()
        if active is None:
            self._open_session(reset_suffix=None)

    def record_fill(self, fill: Fill) -> None:
        if self._session_id is None:
            self.bootstrap()
        self.database.increment_session_fill(
            self._session_id,
            side=fill.side.value,
            strategy=classify_strategy(fill.reason),
        )

    def maybe_snapshot(self, portfolio: dict[str, Any]) -> None:
        if self._session_id is None:
            return
        now = datetime.now(tz=timezone.utc)
        if self._last_snapshot_at is not None:
            elapsed = (now - self._last_snapshot_at).total_seconds()
            if elapsed < self._snapshot_interval_seconds:
                return
        self._last_snapshot_at = now
        equity = float(portfolio.get("equity") or self.initial_cash)
        self._peak_equity = max(self._peak_equity, equity)
        if self._peak_equity > 0:
            drawdown = (self._peak_equity - equity) / self._peak_equity
            self._max_drawdown_pct = max(self._max_drawdown_pct, drawdown)
        exposure_pct = float(portfolio.get("gross_exposure_pct") or 0)
        self._max_exposure_pct = max(self._max_exposure_pct, exposure_pct)

        self.database.record_session_snapshot(
            session_id=self._session_id,
            equity=equity,
            cash=float(portfolio.get("cash") or 0),
            gross_exposure=float(portfolio.get("gross_exposure") or 0),
            unrealized_pnl=float(portfolio.get("unrealized_pnl") or 0),
            realized_pnl=float(portfolio.get("realized_pnl") or 0),
        )
        self.database.update_session_risk_peaks(
            self._session_id,
            max_exposure_pct=self._max_exposure_pct,
            max_drawdown_pct=self._max_drawdown_pct,
            peak_equity=self._peak_equity,
        )

    def active_session_row(self) -> dict[str, Any] | None:
        if self._session_id is None:
            return None
        return self.database.get_paper_session(self._session_id)

    def _open_session(self, *, reset_suffix: int | None) -> None:
        trading_date = trading_date_ist()
        session_id = trading_date if reset_suffix is None else f"{trading_date}-r{reset_suffix}"
        now = datetime.now(tz=timezone.utc).isoformat()
        self.database.create_paper_session(
            session_id=session_id,
            trading_date=trading_date,
            mode=self.mode,
            initial_cash=self.initial_cash,
            started_at=now,
        )
        self._session_id = session_id
        self._peak_equity = self.initial_cash
        self._max_drawdown_pct = 0.0
        self._max_exposure_pct = 0.0
        self._last_snapshot_at = None

    def _close_session(self, *, portfolio: dict[str, Any]) -> None:
        if self._session_id is None:
            return
        equity = float(portfolio.get("equity") or self.initial_cash)
        fills = self.database.fills_for_session(self._session_id)
        breakdown: dict[str, int] = {}
        for fill in fills:
            bucket = classify_strategy(fill.get("reason"))
            breakdown[bucket] = breakdown.get(bucket, 0) + 1

        now = datetime.now(tz=timezone.utc).isoformat()
        self.database.close_paper_session(
            session_id=self._session_id,
            ended_at=now,
            final_equity=equity,
            total_pnl=equity - self.initial_cash,
            realized_pnl=float(portfolio.get("realized_pnl") or 0),
            unrealized_pnl=float(portfolio.get("unrealized_pnl") or 0),
            fees_paid=float(portfolio.get("fees_paid") or 0),
            fill_count=len(fills),
            strategy_breakdown=breakdown,
            max_exposure_pct=self._max_exposure_pct,
            max_drawdown_pct=self._max_drawdown_pct,
        )
        self._session_id = None

    def _next_reset_suffix(self) -> int:
        trading_date = trading_date_ist()
        sessions = self.database.list_paper_sessions(limit=50)
        same_day = [session for session in sessions if session.get("trading_date") == trading_date]
        return len(same_day) + 1
