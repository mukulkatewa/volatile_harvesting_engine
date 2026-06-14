from __future__ import annotations

from datetime import date

import pandas as pd

STANDARD_COLUMNS = [
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

RAW_TO_STANDARD = {
    "date1": "trading_date",
    "symbol": "symbol",
    "series": "series",
    "open_price": "open",
    "high_price": "high",
    "low_price": "low",
    "close_price": "close",
    "ttl_trd_qnty": "volume",
    "ttl_trf_val": "turnover",
}


def normalize_nse_bhavcopy(dataframe: pd.DataFrame, trading_date: date | None = None) -> pd.DataFrame:
    frame = dataframe.copy()
    frame.columns = [column.strip().lower() for column in frame.columns]
    frame = frame.rename(columns=RAW_TO_STANDARD)

    if "trading_date" not in frame.columns:
        if trading_date is None:
            raise ValueError("trading_date missing and could not be inferred")
        frame["trading_date"] = trading_date

    if "series" not in frame.columns:
        frame["series"] = "EQ"

    missing = [column for column in STANDARD_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")

    frame["trading_date"] = pd.to_datetime(frame["trading_date"]).dt.date
    numeric_columns = ["open", "high", "low", "close", "volume", "turnover"]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = frame[frame["series"] == "EQ"].copy()
    frame = frame.dropna(subset=["trading_date", "symbol", "open", "high", "low", "close", "volume", "turnover"])
    frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
    frame["series"] = frame["series"].astype(str).str.upper().str.strip()
    frame["volume"] = frame["volume"].astype("int64")

    return frame[STANDARD_COLUMNS].sort_values(["trading_date", "symbol"]).reset_index(drop=True)
