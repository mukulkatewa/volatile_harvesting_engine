from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import BytesIO
from zipfile import ZipFile

import httpx
import pandas as pd


class NseDownloadError(RuntimeError):
    """Raised when the NSE download flow fails."""


@dataclass(frozen=True, slots=True)
class NseBhavcopyArtifact:
    trading_date: date
    dataframe: pd.DataFrame


class NseBhavcopyClient:
    """Downloads zipped NSE bhavcopy archives and parses the CSV payload."""

    _BASE_URL = "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{stamp}_F_0000.csv.zip"

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self._timeout_seconds = timeout_seconds

    def download(self, trading_date: date) -> NseBhavcopyArtifact:
        stamp = trading_date.strftime("%Y%m%d")
        url = self._BASE_URL.format(stamp=stamp)
        headers = {
            "User-Agent": "volatile-harvesting-engine/0.1",
            "Accept": "application/zip,application/octet-stream",
        }

        with httpx.Client(timeout=self._timeout_seconds, follow_redirects=True, headers=headers) as client:
            response = client.get(url)

        if response.status_code != 200:
            raise NseDownloadError(f"unexpected status={response.status_code} url={url}")

        try:
            archive = ZipFile(BytesIO(response.content))
        except Exception as exc:  # pragma: no cover - exercised via integration
            raise NseDownloadError("failed to read NSE zip archive") from exc

        member_names = archive.namelist()
        if not member_names:
            raise NseDownloadError("zip archive contained no files")

        with archive.open(member_names[0]) as handle:
            dataframe = pd.read_csv(handle)

        dataframe.columns = [column.strip().lower() for column in dataframe.columns]
        return NseBhavcopyArtifact(trading_date=trading_date, dataframe=dataframe)

