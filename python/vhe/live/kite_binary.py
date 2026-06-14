from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import datetime, timezone

from vhe.live.models import LiveQuote, MarketDepthLevel


class KitePacketError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class KiteQuotePacket:
    instrument_token: int
    ltp: float
    last_quantity: int | None = None
    average_price: float | None = None
    volume: int = 0
    buy_quantity: int | None = None
    sell_quantity: int | None = None
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    exchange_timestamp: datetime | None = None
    bids: tuple[MarketDepthLevel, ...] = ()
    asks: tuple[MarketDepthLevel, ...] = ()

    def to_live_quote(self, token_symbol_map: dict[int, str]) -> LiveQuote:
        symbol = token_symbol_map.get(self.instrument_token, str(self.instrument_token))
        return LiveQuote(
            timestamp=self.exchange_timestamp or datetime.now(tz=timezone.utc),
            symbol=symbol,
            ltp=self.ltp,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
            bid=self.bids[0] if self.bids else None,
            ask=self.asks[0] if self.asks else None,
            bids=self.bids,
            asks=self.asks,
        )


def parse_kite_binary_message(payload: bytes) -> list[KiteQuotePacket]:
    if len(payload) < 2:
        return []

    packet_count = struct.unpack_from(">H", payload, 0)[0]
    offset = 2
    packets: list[KiteQuotePacket] = []

    for _ in range(packet_count):
        if offset + 2 > len(payload):
            raise KitePacketError("truncated packet length")
        packet_length = struct.unpack_from(">H", payload, offset)[0]
        offset += 2
        end = offset + packet_length
        if end > len(payload):
            raise KitePacketError("truncated packet payload")
        packets.append(parse_kite_packet(payload[offset:end]))
        offset = end

    return packets


def parse_kite_packet(packet: bytes) -> KiteQuotePacket:
    if len(packet) == 8:
        instrument_token, ltp = struct.unpack_from(">ii", packet, 0)
        return KiteQuotePacket(instrument_token=instrument_token, ltp=_price(ltp))

    if len(packet) not in {28, 32, 44, 184}:
        raise KitePacketError(f"unsupported Kite packet length: {len(packet)}")

    instrument_token = _i32(packet, 0)
    ltp = _price(_i32(packet, 4))

    if len(packet) in {28, 32}:
        return KiteQuotePacket(
            instrument_token=instrument_token,
            ltp=ltp,
            high=_price(_i32(packet, 8)),
            low=_price(_i32(packet, 12)),
            open=_price(_i32(packet, 16)),
            close=_price(_i32(packet, 20)),
            exchange_timestamp=_timestamp(_i32(packet, 28)) if len(packet) == 32 else None,
        )

    return KiteQuotePacket(
        instrument_token=instrument_token,
        ltp=ltp,
        last_quantity=_i32(packet, 8),
        average_price=_price(_i32(packet, 12)),
        volume=_i32(packet, 16),
        buy_quantity=_i32(packet, 20),
        sell_quantity=_i32(packet, 24),
        open=_price(_i32(packet, 28)),
        high=_price(_i32(packet, 32)),
        low=_price(_i32(packet, 36)),
        close=_price(_i32(packet, 40)),
        exchange_timestamp=_timestamp(_i32(packet, 60)) if len(packet) == 184 else None,
        bids=_depth(packet[64:124]) if len(packet) == 184 else (),
        asks=_depth(packet[124:184]) if len(packet) == 184 else (),
    )


def _depth(payload: bytes) -> tuple[MarketDepthLevel, ...]:
    levels: list[MarketDepthLevel] = []
    for offset in range(0, len(payload), 12):
        quantity, price, orders = struct.unpack_from(">iiH", payload, offset)
        levels.append(MarketDepthLevel(price=_price(price), quantity=quantity, orders=orders))
    return tuple(levels)


def _i32(payload: bytes, offset: int) -> int:
    return struct.unpack_from(">i", payload, offset)[0]


def _price(raw: int) -> float:
    return raw / 100


def _timestamp(raw: int) -> datetime | None:
    if raw <= 0:
        return None
    return datetime.fromtimestamp(raw, tz=timezone.utc)
