from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd

from vhe.data.schema import normalize_nse_bhavcopy

BHAVCOPY_DATE_PATTERN = re.compile(r"bhavcopy_(\d{4}-\d{2}-\d{2})\.parquet$")



def infer_trading_date_from_path(path: Path) -> date | None:
    match = BHAVCOPY_DATE_PATTERN.search(path.name)
    if not match:
        return None
    return date.fromisoformat(match.group(1))



def load_history_from_parquet_dir(parquet_dir: Path, symbols: list[str] | None = None) -> pd.DataFrame:
    parquet_paths = sorted(parquet_dir.glob("*.parquet"))
    if not parquet_paths:
        raise FileNotFoundError(f"no parquet files found in {parquet_dir}")

    normalized_frames: list[pd.DataFrame] = []
    requested_symbols = {symbol.upper() for symbol in symbols} if symbols else None

    for path in parquet_paths:
        frame = pd.read_parquet(path)
        trading_date = infer_trading_date_from_path(path)
        normalized = normalize_nse_bhavcopy(frame, trading_date=trading_date)
        if requested_symbols is not None:
            normalized = normalized[normalized["symbol"].isin(requested_symbols)]
        normalized_frames.append(normalized)

    history = pd.concat(normalized_frames, ignore_index=True)
    history = history.drop_duplicates(subset=["trading_date", "symbol"], keep="last")
    return history.sort_values(["symbol", "trading_date"]).reset_index(drop=True)
