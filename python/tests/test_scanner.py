from datetime import date

import pandas as pd

from vhe.scanner.daily import score_candidate_metrics



def test_score_candidate_metrics_prefers_higher_volatility_and_lower_trend() -> None:
    metrics = pd.DataFrame(
        {
            "trading_date": [date(2026, 6, 13)] * 3,
            "symbol": ["AAA", "BBB", "CCC"],
            "close": [500.0, 500.0, 500.0],
            "atr_14": [25.0, 10.0, 18.0],
            "atr_pct": [5.0, 2.0, 3.6],
            "adx_14": [12.0, 30.0, 18.0],
            "ema_50": [490.0, 495.0, 497.0],
            "avg_turnover_20d": [200_000_000.0, 250_000_000.0, 150_000_000.0],
            "gap_pct": [0.5, 0.3, 0.2],
            "distance_from_ema50_pct": [2.0, 1.0, 0.6],
        }
    )

    scored = score_candidate_metrics(
        metrics,
        min_close_price_inr=100.0,
        min_turnover_inr=100_000_000.0,
        max_gap_pct=5.0,
    )

    assert list(scored["symbol"]) == ["AAA", "CCC", "BBB"]
    assert scored.iloc[0]["candidate_score"] > scored.iloc[1]["candidate_score"]
