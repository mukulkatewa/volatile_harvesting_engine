from __future__ import annotations

from datetime import date

from vhe.config.models import AppConfig
from vhe.data.contracts import IngestResult
from vhe.data.nse import NseBhavcopyClient
from vhe.data.storage import build_bhavcopy_path, write_parquet_frame


def ingest_nse_bhavcopy(config: AppConfig, trading_date: str, output_subdir: str) -> IngestResult:
    parsed_date = date.fromisoformat(trading_date)
    artifact = NseBhavcopyClient().download(parsed_date)

    output_path = build_bhavcopy_path(
        root_dir=config.paths.raw_data_dir,
        output_subdir=output_subdir,
        trading_date=trading_date,
    )
    write_parquet_frame(artifact.dataframe, output_path)
    return IngestResult(output_path=str(output_path), rows=len(artifact.dataframe))

