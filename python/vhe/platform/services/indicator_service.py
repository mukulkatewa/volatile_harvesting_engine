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
    # Fair-value anchor lag. The anchor is a slow EMA of price so intraday swings
    # create a harvestable dislocation (price below anchor -> buy, above -> sell).
    # If fair_value simply tracked spot, no mean-reversion signal could ever fire.
    anchor_alpha: float = 0.04
    _history: dict[str, deque[dict[str, float]]] = field(default_factory=dict)
    _session_high: dict[str, float] = field(default_factory=dict)
    _anchor: dict[str, float] = field(default_factory=dict)

    def update(self, quote: LiveQuote) -> IndicatorSnapshot:
        bar = {
            "open": quote.open,
            "high": quote.high,
            "low": quote.low,
            "close": quote.close,
            "ltp": quote.ltp,
        }
        history = self._history.setdefault(quote.symbol, deque(maxlen=self.history_size))
        if history:
            last = history[-1]
            if last["close"] == quote.close and last["high"] == quote.high and last["low"] == quote.low:
                history[-1] = bar
            elif last["close"] != quote.close or last["high"] != quote.high:
                history.append(bar)
        else:
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
            adx_value = 17.0
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
                adx_value = 17.0
            adx_value = max(0.0, min(adx_value, 100.0))

        fair_value = self._update_anchor(quote.symbol, quote.ltp, ema_50, len(history))

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

    def _update_anchor(self, symbol: str, ltp: float, ema_50: float, history_len: int) -> float:
        prev = self._anchor.get(symbol)
        if prev is None:
            # Bootstrap from the warmed-up mean when available, else current price.
            prev = ema_50 if history_len >= 14 and ema_50 > 0 else ltp
        anchor = prev * (1 - self.anchor_alpha) + ltp * self.anchor_alpha
        self._anchor[symbol] = anchor
        return round(anchor, 2)

    def seed_bars(self, symbol: str, bars: list[dict[str, float]]) -> None:
        if not bars:
            return
        history = self._history.setdefault(symbol, deque(maxlen=self.history_size))
        for bar in bars:
            if history and history[-1]["close"] == bar["close"] and history[-1]["high"] == bar["high"]:
                history[-1] = bar
            else:
                history.append(bar)
        closes = [bar["close"] for bar in history if bar.get("close", 0) > 0]
        if closes:
            # Anchor to the recent mean so a dislocation exists from the first live tick.
            self._anchor[symbol] = sum(closes) / len(closes)

    def reset_session(self) -> None:
        self._session_high.clear()
        self._history.clear()
        self._anchor.clear()
