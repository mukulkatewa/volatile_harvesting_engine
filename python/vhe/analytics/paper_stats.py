from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from vhe.analytics.sentiment import sentiment_snapshot_from_dict
from vhe.storage.db import PlatformDatabase

IST = ZoneInfo("Asia/Kolkata")


def trading_date_ist(*, now: datetime | None = None) -> str:
    moment = now or datetime.now(tz=timezone.utc)
    return moment.astimezone(IST).date().isoformat()


def classify_strategy(reason: str | None) -> str:
    text = (reason or "").lower()
    if text.startswith("dynamic_grid") or text.startswith("dg-"):
        return "grid"
    if "pair" in text or "spread" in text:
        return "pair"
    if "momentum" in text:
        return "momentum"
    if "force_exit" in text or "session_force" in text:
        return "session_exit"
    if "demo" in text:
        return "demo"
    return "other"


@dataclass(frozen=True, slots=True)
class StrategyHealth:
    verdict: str
    summary: str
    notes: tuple[str, ...]
    grid_fills: int
    grid_exits: int
    pair_fills: int
    momentum_fills: int
    fee_drag_ratio: float | None
    return_on_deployed_bps: float | None
    minutes_active: float | None


def evaluate_strategy_health(
    *,
    fill_count: int,
    strategy_breakdown: dict[str, int],
    total_pnl: float,
    fees_paid: float,
    avg_deployed: float,
    minutes_active: float | None,
    exit_reasons: dict[str, int],
) -> StrategyHealth:
    grid_fills = strategy_breakdown.get("grid", 0)
    grid_exits = sum(count for reason, count in exit_reasons.items() if "exit" in reason or "mean" in reason)
    pair_fills = strategy_breakdown.get("pair", 0)
    momentum_fills = strategy_breakdown.get("momentum", 0)

    fee_drag_ratio = (fees_paid / abs(total_pnl)) if total_pnl != 0 else None
    return_on_deployed_bps = (
        (total_pnl / avg_deployed) * 10_000 if avg_deployed > 0 else None
    )

    notes: list[str] = []

    if fill_count < 5 or (minutes_active is not None and minutes_active < 20):
        return StrategyHealth(
            verdict="too_early",
            summary="Not enough data yet — grid needs full sessions, not 10 minutes.",
            notes=(
                "80% deployed with flat P&L is normal: grid buys first, profits come on mean-reversion sells.",
                "Judge after 5–10 full sessions with round-trip exits, not opening exposure.",
                "yfinance 15m delay makes intraday P&L unreliable for tuning.",
            ),
            grid_fills=grid_fills,
            grid_exits=grid_exits,
            pair_fills=pair_fills,
            momentum_fills=momentum_fills,
            fee_drag_ratio=fee_drag_ratio,
            return_on_deployed_bps=return_on_deployed_bps,
            minutes_active=minutes_active,
        )

    if fees_paid > 0 and total_pnl <= 0 and fees_paid >= abs(total_pnl) * 0.8:
        notes.append("Fees are eating most of the edge — reduce turnover or widen grid spacing.")

    if grid_fills > 0 and grid_exits == 0:
        notes.append("Grid has entries but no mean exits yet — inventory deployed, waiting for oscillation.")

    if grid_exits > 0 and total_pnl > 0:
        verdict = "promising"
        summary = "Grid round-trips are closing with positive session P&L."
    elif grid_exits > 0 and total_pnl <= 0:
        verdict = "needs_review"
        summary = "Exits are happening but net P&L is negative after fees."
    elif grid_fills > 0:
        verdict = "deployed"
        summary = "Capital deployed; awaiting mean-reversion exits to validate edge."
    else:
        verdict = "idle"
        summary = "Little or no grid activity this session."

    if not notes:
        if return_on_deployed_bps is not None:
            notes.append(f"Return on avg deployed capital: {return_on_deployed_bps:.1f} bps.")
        if fee_drag_ratio is not None:
            notes.append(f"Fee drag vs |P&L|: {fee_drag_ratio:.0%}.")

    return StrategyHealth(
        verdict=verdict,
        summary=summary,
        notes=tuple(notes) if notes else ("Continue paper logging — compare across sessions.",),
        grid_fills=grid_fills,
        grid_exits=grid_exits,
        pair_fills=pair_fills,
        momentum_fills=momentum_fills,
        fee_drag_ratio=fee_drag_ratio,
        return_on_deployed_bps=return_on_deployed_bps,
        minutes_active=minutes_active,
    )


class PaperStatsService:
    def __init__(self, database: PlatformDatabase) -> None:
        self.database = database

    def build_report(
        self,
        *,
        portfolio: dict[str, Any],
        active_session: dict[str, Any] | None,
        sentiment: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        sessions = self.database.list_paper_sessions(limit=30)
        closed = [session for session in sessions if session.get("status") == "closed"]
        cumulative_pnl = sum(float(session.get("total_pnl") or 0) for session in closed)
        win_sessions = sum(1 for session in closed if float(session.get("total_pnl") or 0) > 0)
        total_fees = sum(float(session.get("fees_paid") or 0) for session in closed)

        current = self._enrich_session(active_session, portfolio) if active_session else None
        sentiment_view = sentiment_snapshot_from_dict(sentiment).to_dict() if sentiment else sentiment_snapshot_from_dict({}).to_dict()

        multi = {
            "sessions_count": len(closed),
            "active_session_id": active_session.get("session_id") if active_session else None,
            "cumulative_pnl": round(cumulative_pnl, 2),
            "avg_session_pnl": round(cumulative_pnl / len(closed), 2) if closed else 0.0,
            "win_rate_pct": round((win_sessions / len(closed)) * 100, 1) if closed else 0.0,
            "total_fees": round(total_fees, 2),
            "best_session_pnl": round(max((float(s.get("total_pnl") or 0) for s in closed), default=0.0), 2),
            "worst_session_pnl": round(min((float(s.get("total_pnl") or 0) for s in closed), default=0.0), 2),
        }

        health = None
        if current:
            health = evaluate_strategy_health(
                fill_count=int(current.get("fill_count") or 0),
                strategy_breakdown=current.get("strategy_breakdown") or {},
                total_pnl=float(current.get("total_pnl") or 0),
                fees_paid=float(current.get("fees_paid") or 0),
                avg_deployed=float(current.get("avg_deployed") or 0),
                minutes_active=current.get("minutes_active"),
                exit_reasons=current.get("exit_reasons") or {},
            )

        return {
            "multi_session": multi,
            "current_session": current,
            "sessions": [self._public_session_row(session) for session in sessions],
            "strategy_health": _strategy_health_dict(health),
            "sentiment": sentiment_view,
        }

    def _enrich_session(self, session: dict[str, Any], portfolio: dict[str, Any]) -> dict[str, Any]:
        started_at = _parse_dt(session.get("started_at"))
        now = datetime.now(tz=timezone.utc)
        minutes_active = ((now - started_at).total_seconds() / 60) if started_at else None

        initial = float(session.get("initial_cash") or 0)
        equity = float(portfolio.get("equity") or initial)
        total_pnl = equity - initial

        fills = self.database.fills_for_session(session["session_id"])
        breakdown: dict[str, int] = {}
        exit_reasons: dict[str, int] = {}
        for fill in fills:
            reason = fill.get("reason") or ""
            bucket = classify_strategy(reason)
            breakdown[bucket] = breakdown.get(bucket, 0) + 1
            if fill.get("side") == "SELL":
                exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

        snapshots = self.database.session_snapshots(session["session_id"])
        avg_deployed = _avg_deployed_from_snapshots(snapshots, equity, portfolio)

        row = dict(session)
        row.update(
            {
                "equity": round(equity, 2),
                "cash": round(float(portfolio.get("cash") or 0), 2),
                "invested": round(float(portfolio.get("gross_exposure") or 0), 2),
                "total_pnl": round(total_pnl, 2),
                "unrealized_pnl": round(float(portfolio.get("unrealized_pnl") or 0), 2),
                "realized_pnl": round(float(portfolio.get("realized_pnl") or 0), 2),
                "fees_paid": round(float(portfolio.get("fees_paid") or 0), 2),
                "fill_count": len(fills),
                "strategy_breakdown": breakdown,
                "exit_reasons": exit_reasons,
                "avg_deployed": round(avg_deployed, 2),
                "minutes_active": round(minutes_active, 1) if minutes_active is not None else None,
                "max_exposure_pct": round(float(session.get("max_exposure_pct") or portfolio.get("gross_exposure_pct") or 0), 1),
            }
        )
        return row

    def _public_session_row(self, session: dict[str, Any]) -> dict[str, Any]:
        return {
            "session_id": session.get("session_id"),
            "trading_date": session.get("trading_date"),
            "status": session.get("status"),
            "started_at": session.get("started_at"),
            "ended_at": session.get("ended_at"),
            "initial_cash": session.get("initial_cash"),
            "final_equity": session.get("final_equity"),
            "total_pnl": session.get("total_pnl"),
            "fees_paid": session.get("fees_paid"),
            "fill_count": session.get("fill_count"),
            "max_exposure_pct": session.get("max_exposure_pct"),
            "max_drawdown_pct": session.get("max_drawdown_pct"),
            "strategy_breakdown": session.get("strategy_breakdown") or {},
        }


def _strategy_health_dict(health: StrategyHealth | None) -> dict[str, Any] | None:
    if health is None:
        return None
    return {
        "verdict": health.verdict,
        "summary": health.summary,
        "notes": list(health.notes),
        "grid_fills": health.grid_fills,
        "grid_exits": health.grid_exits,
        "pair_fills": health.pair_fills,
        "momentum_fills": health.momentum_fills,
        "fee_drag_ratio": round(health.fee_drag_ratio, 3) if health.fee_drag_ratio is not None else None,
        "return_on_deployed_bps": round(health.return_on_deployed_bps, 2) if health.return_on_deployed_bps is not None else None,
        "minutes_active": health.minutes_active,
    }


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _avg_deployed_from_snapshots(snapshots: list[dict[str, Any]], equity: float, portfolio: dict[str, Any]) -> float:
    if snapshots:
        exposures = [float(row.get("gross_exposure") or 0) for row in snapshots]
        return sum(exposures) / len(exposures)
    return float(portfolio.get("gross_exposure") or max(equity - float(portfolio.get("cash") or 0), 0))
