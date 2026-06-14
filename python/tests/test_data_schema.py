from datetime import date

import pandas as pd

from vhe.data.schema import normalize_nse_bhavcopy



def test_normalize_nse_bhavcopy_maps_raw_columns_and_filters_non_eq_series() -> None:
    raw = pd.DataFrame(
        {
            "DATE1": ["2026-06-13", "2026-06-13"],
            "SYMBOL": ["RELIANCE", "NIFTYBEES"],
            "SERIES": ["EQ", "BE"],
            "OPEN_PRICE": [100, 50],
            "HIGH_PRICE": [110, 55],
            "LOW_PRICE": [95, 45],
            "CLOSE_PRICE": [108, 48],
            "TTL_TRD_QNTY": [1000, 2000],
            "TTL_TRF_VAL": [108000, 96000],
        }
    )

    normalized = normalize_nse_bhavcopy(raw, trading_date=date(2026, 6, 13))

    assert list(normalized.columns) == [
        "trading_date",
        "symbol",
        "series",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "turnover",
    ]
    assert len(normalized) == 1
    assert normalized.iloc[0]["symbol"] == "RELIANCE"
