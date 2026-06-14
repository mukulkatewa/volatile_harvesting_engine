from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx

from vhe.live.kite import KiteInstrument, parse_instruments_csv


KITE_INSTRUMENTS_URL = "https://api.kite.trade/instruments"


@dataclass(frozen=True, slots=True)
class KiteAuth:
    api_key: str
    access_token: str


@dataclass(frozen=True, slots=True)
class InstrumentCacheResult:
    path: Path
    instruments: list[KiteInstrument]


class KiteInstrumentClient:
    def __init__(self, auth: KiteAuth, timeout_seconds: float = 30.0) -> None:
        self.auth = auth
        self.timeout_seconds = timeout_seconds

    def download_csv(self) -> str:
        headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {self.auth.api_key}:{self.auth.access_token}",
        }
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True, headers=headers) as client:
            response = client.get(KITE_INSTRUMENTS_URL)
        response.raise_for_status()
        return response.text


def cache_instruments_csv(csv_payload: str, *, cache_dir: Path, trading_date: date) -> InstrumentCacheResult:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = instrument_cache_path(cache_dir=cache_dir, trading_date=trading_date)
    path.write_text(csv_payload)
    return InstrumentCacheResult(path=path, instruments=parse_instruments_csv(csv_payload))


def load_cached_instruments(*, cache_dir: Path, trading_date: date) -> InstrumentCacheResult:
    path = instrument_cache_path(cache_dir=cache_dir, trading_date=trading_date)
    if not path.exists():
        raise FileNotFoundError(f"missing Kite instruments cache: {path}")
    payload = path.read_text()
    return InstrumentCacheResult(path=path, instruments=parse_instruments_csv(payload))


def instrument_cache_path(*, cache_dir: Path, trading_date: date) -> Path:
    return cache_dir / f"kite_instruments_{trading_date.isoformat()}.csv"
