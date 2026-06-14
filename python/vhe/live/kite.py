from __future__ import annotations

from dataclasses import dataclass
from io import StringIO

import pandas as pd


@dataclass(frozen=True, slots=True)
class KiteFeedConfig:
    api_key: str
    access_token: str
    instrument_tokens: list[int]
    mode: str = "full"


@dataclass(frozen=True, slots=True)
class KiteInstrument:
    instrument_token: int
    exchange_token: int
    tradingsymbol: str
    name: str
    exchange: str
    instrument_type: str
    segment: str
    tick_size: float
    lot_size: int


class KiteWebSocketFeed:
    """Placeholder for the real Kite binary WebSocket parser."""

    def __init__(self, config: KiteFeedConfig) -> None:
        self.config = config

    async def stream(self):
        raise NotImplementedError("Kite feed requires binary packet parsing and auth wiring")


def parse_instruments_csv(csv_payload: str) -> list[KiteInstrument]:
    frame = pd.read_csv(StringIO(csv_payload))
    required = {
        "instrument_token",
        "exchange_token",
        "tradingsymbol",
        "name",
        "exchange",
        "instrument_type",
        "segment",
        "tick_size",
        "lot_size",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Kite instrument CSV missing columns: {sorted(missing)}")

    instruments: list[KiteInstrument] = []
    for row in frame.itertuples(index=False):
        instruments.append(
            KiteInstrument(
                instrument_token=int(row.instrument_token),
                exchange_token=int(row.exchange_token),
                tradingsymbol=str(row.tradingsymbol).upper(),
                name=str(row.name),
                exchange=str(row.exchange),
                instrument_type=str(row.instrument_type),
                segment=str(row.segment),
                tick_size=float(row.tick_size),
                lot_size=int(row.lot_size),
            )
        )
    return instruments


def nse_equity_token_map(instruments: list[KiteInstrument], symbols: list[str]) -> dict[str, int]:
    requested = {symbol.upper() for symbol in symbols}
    return {
        instrument.tradingsymbol: instrument.instrument_token
        for instrument in instruments
        if instrument.exchange == "NSE"
        and instrument.segment == "NSE"
        and instrument.instrument_type == "EQ"
        and instrument.tradingsymbol in requested
    }
