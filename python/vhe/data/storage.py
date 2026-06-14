from __future__ import annotations

from pathlib import Path

import pandas as pd


def build_bhavcopy_path(root_dir: Path, output_subdir: str, trading_date: str) -> Path:
    return root_dir / output_subdir / f"bhavcopy_{trading_date}.parquet"


def write_parquet_frame(dataframe: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_parquet(output_path, index=False)

