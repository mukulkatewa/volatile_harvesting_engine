from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import pandas as pd

from vhe.indicators.trend import adx, atr, ema
from vhe.live.models import LiveQuote


@dataclass(frozen=True, slots=True)
class IndicatorSnapshot:
    symbol: str
    ltp: float
    ema_20: float
    ema_50: float
    atr_14: float
    adx_14: float
    fair_value: float
    intraday_drawdown_pct: float = 0.0


@dataclass(slots=True)
class IndicatorService:
    history_size: int = 60
    _history: dict[str, deque[dict[str, float]]] = field(default_factory=dict)
    _session_high: dict[str, float] = field(default_factory=dict)

    def update(self, quote: LiveQuote) -> IndicatorSnapshot:
        bar = {
            "open": quote.open,
            "high": quote.high,
            "low": quote.low,
            "close": quote.close,
            "ltp": quote.ltp,
        }
        history = self._history.setdefault(quote.symbol, deque(maxlen=self.history_size))
        if not history or history[-1]["close"] != quote.close or history[-1]["high"] != quote.high:
            history.append(bar)

        session_high = self._session_high.get(quote.symbol, quote.ltp)
        if quote.ltp > session_high:
            session_high = quote.ltp
        self._session_high[quote.symbol] = session_high
        drawdown_pct = ((quote.ltp - session_high) / session_high * 100) if session_high > 0 else 0.0

        if len(history) < 14:
            atr_value = max(quote.high - quote.low, quote.ltp * 0.006)
            ema_20 = quote.close - (atr_value * 0.04)
            ema_50 = quote.close - (atr_value * 0.14)
            adx_value = 25.0
            fair_value = quote.close
        else:
            frame = pd.DataFrame(history)
            ema_20 = float(ema(frame["close"], 20).iloc[-1])
            ema_50 = float(ema(frame["close"], 50).iloc[-1]) if len(history) >= 50 else float(ema(frame["close"], min(20, len(history))).iloc[-1])
            atr_series = atr(frame.rename(columns={"close": "close", "high": "high", "low": "low"}), period=14)
            atr_value = float(atr_series.iloc[-1])
            if pd.isna(atr_value) or atr_value <= 0:
                atr_value = max(quote.high - quote.low, quote.ltp * 0.006)
            adx_series = adx(frame.rename(columns={"close": "close", "high": "high", "low": "low"}), period=14)
            adx_value = float(adx_series.iloc[-1])
            if pd.isna(adx_value):
                adx_value = 25.0
            adx_value = max(0.0, min(adx_value, 100.0))
            fair_value = ema_50

        return IndicatorSnapshot(
            symbol=quote.symbol,
            ltp=quote.ltp,
            ema_20=ema_20,
            ema_50=ema_50,
            atr_14=atr_value,
            adx_14=adx_value,
            fair_value=fair_value,
            intraday_drawdown_pct=drawdown_pct,
        )

    def reset_session(self) -> None:
        self._session_high.clear()
