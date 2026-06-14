from __future__ import annotations

import numpy as np
import pandas as pd



def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=span).mean()



def true_range(dataframe: pd.DataFrame) -> pd.Series:
    prev_close = dataframe["close"].shift(1)
    ranges = pd.concat(
        [
            dataframe["high"] - dataframe["low"],
            (dataframe["high"] - prev_close).abs(),
            (dataframe["low"] - prev_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1)



def atr(dataframe: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = true_range(dataframe)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()



def adx(dataframe: pd.DataFrame, period: int = 14) -> pd.Series:
    up_move = dataframe["high"].diff()
    down_move = -dataframe["low"].diff()

    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=dataframe.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=dataframe.index,
    )

    atr_series = atr(dataframe, period=period)
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr_series
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr_series

    denominator = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / denominator
    return dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
