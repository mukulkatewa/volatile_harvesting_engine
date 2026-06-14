import pandas as pd

from vhe.indicators.trend import adx, atr, ema



def test_trend_indicators_return_expected_shapes_and_values() -> None:
    closes = list(range(100, 160))
    frame = pd.DataFrame(
        {
            "high": [close + 1 for close in closes],
            "low": [close - 1 for close in closes],
            "close": closes,
        }
    )

    ema_series = ema(frame["close"], span=5)
    atr_series = atr(frame, period=14)
    adx_series = adx(frame, period=14)

    assert len(ema_series) == len(frame)
    assert len(atr_series) == len(frame)
    assert len(adx_series) == len(frame)
    assert round(float(ema_series.iloc[-1]), 2) == 157.0
    assert float(atr_series.iloc[-1]) > 0
    assert pd.notna(adx_series.iloc[-1])
    assert float(adx_series.iloc[-1]) >= 0
