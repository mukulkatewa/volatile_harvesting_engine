from __future__ import annotations

from datetime import date

import pandas as pd

from vhe.indicators.trend import adx, atr, ema



def _compute_symbol_metrics(symbol_history: pd.DataFrame, as_of: date) -> dict[str, float | str | date]:
    history = symbol_history[symbol_history["trading_date"] <= as_of].copy()
    history = history.sort_values("trading_date").reset_index(drop=True)
    warmup_rows = max(50, 2 * 14)
    if len(history) < warmup_rows:
        raise ValueError(f"at least {warmup_rows} rows are required to compute scanner metrics")

    history["atr_14"] = atr(history, period=14)
    history["adx_14"] = adx(history, period=14)
    history["ema_50"] = ema(history["close"], span=50)
    history["avg_turnover_20d"] = history["turnover"].rolling(window=20, min_periods=20).mean()
    history["prev_close"] = history["close"].shift(1)
    history["gap_pct"] = ((history["open"] - history["prev_close"]) / history["prev_close"]) * 100

    last_row = history.iloc[-1]
    if pd.isna(last_row["atr_14"]) or pd.isna(last_row["adx_14"]) or pd.isna(last_row["avg_turnover_20d"]):
        raise ValueError("insufficient lookback for final row")

    atr_pct = (last_row["atr_14"] / last_row["close"]) * 100
    distance_from_ema50_pct = ((last_row["close"] - last_row["ema_50"]) / last_row["ema_50"]) * 100 if pd.notna(last_row["ema_50"]) else 0.0

    return {
        "trading_date": last_row["trading_date"],
        "symbol": last_row["symbol"],
        "close": float(last_row["close"]),
        "atr_14": float(last_row["atr_14"]),
        "atr_pct": float(atr_pct),
        "adx_14": float(last_row["adx_14"]),
        "ema_50": float(last_row["ema_50"]) if pd.notna(last_row["ema_50"]) else float("nan"),
        "avg_turnover_20d": float(last_row["avg_turnover_20d"]),
        "gap_pct": float(last_row["gap_pct"]) if pd.notna(last_row["gap_pct"]) else 0.0,
        "distance_from_ema50_pct": float(distance_from_ema50_pct),
    }



def compute_candidate_metrics(history: pd.DataFrame, as_of: date) -> pd.DataFrame:
    required_columns = {"trading_date", "symbol", "open", "high", "low", "close", "turnover"}
    missing_columns = required_columns - set(history.columns)
    if missing_columns:
        raise ValueError(f"missing required history columns: {sorted(missing_columns)}")

    metrics: list[dict[str, float | str | date]] = []
    for symbol, symbol_history in history.groupby("symbol", sort=True):
        try:
            metrics.append(_compute_symbol_metrics(symbol_history, as_of=as_of))
        except ValueError:
            continue

    if not metrics:
        return pd.DataFrame(
            columns=[
                "trading_date",
                "symbol",
                "close",
                "atr_14",
                "atr_pct",
                "adx_14",
                "ema_50",
                "avg_turnover_20d",
                "gap_pct",
                "distance_from_ema50_pct",
            ]
        )

    return pd.DataFrame(metrics).sort_values(["symbol"]).reset_index(drop=True)



def score_candidate_metrics(
    metrics: pd.DataFrame,
    *,
    min_close_price_inr: float,
    min_turnover_inr: float,
    max_gap_pct: float,
) -> pd.DataFrame:
    if metrics.empty:
        return metrics.copy()

    filtered = metrics[
        (metrics["close"] >= min_close_price_inr) &
        (metrics["avg_turnover_20d"] >= min_turnover_inr)
    ].copy()
    if filtered.empty:
        return filtered

    filtered["volatility_score"] = filtered["atr_pct"].rank(method="average", pct=True)
    filtered["trend_penalty"] = filtered["adx_14"].rank(method="average", pct=True)
    filtered["range_score"] = 1.0 - filtered["trend_penalty"]
    filtered["volume_score"] = filtered["avg_turnover_20d"].rank(method="average", pct=True)
    filtered["gap_penalty"] = (filtered["gap_pct"].abs() / max_gap_pct).clip(upper=1.0)
    filtered["candidate_score"] = (
        0.40 * filtered["volatility_score"] +
        0.30 * filtered["range_score"] +
        0.20 * filtered["volume_score"] -
        0.10 * filtered["gap_penalty"]
    )

    return filtered.sort_values(["candidate_score", "atr_pct"], ascending=[False, False]).reset_index(drop=True)



def build_candidate_report(
    history: pd.DataFrame,
    *,
    as_of: date,
    min_close_price_inr: float,
    min_turnover_inr: float,
    max_gap_pct: float,
    top_n: int = 10,
) -> pd.DataFrame:
    metrics = compute_candidate_metrics(history, as_of=as_of)
    scored = score_candidate_metrics(
        metrics,
        min_close_price_inr=min_close_price_inr,
        min_turnover_inr=min_turnover_inr,
        max_gap_pct=max_gap_pct,
    )
    if scored.empty:
        return scored
    return scored.head(top_n).reset_index(drop=True)
