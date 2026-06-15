from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from vhe.live.feed import LiveFeed
from vhe.live.kite_binary import parse_kite_binary_message
from vhe.live.models import LiveQuote

logger = logging.getLogger(__name__)

KITE_WS_URL = "wss://ws.kite.trade"


@dataclass(slots=True)
class KiteWebSocketFeed(LiveFeed):
    api_key: str
    access_token: str
    token_symbol_map: dict[int, str]
    mode: str = "quote"
    reconnect_seconds: float = 5.0
    _quotes: dict[str, LiveQuote] = field(default_factory=dict, init=False)

    @property
    def instrument_tokens(self) -> list[int]:
        return list(self.token_symbol_map.keys())

    async def stream(self) -> AsyncIterator[LiveQuote]:
        while True:
            try:
                async for quote in self._connect_and_stream():
                    yield quote
            except ConnectionClosed as exc:
                logger.warning("Kite websocket closed: %s", exc)
            except Exception as exc:
                logger.exception("Kite websocket error: %s", exc)
            await asyncio.sleep(self.reconnect_seconds)

    async def _connect_and_stream(self) -> AsyncIterator[LiveQuote]:
        uri = f"{KITE_WS_URL}?api_key={self.api_key}&access_token={self.access_token}"
        async with websockets.connect(uri, ping_interval=20, ping_timeout=20, max_size=8_388_608) as websocket:
            await self._subscribe(websocket)
            async for message in websocket:
                if isinstance(message, bytes):
                    for quote in self._parse_binary(message):
                        self._quotes[quote.symbol] = quote
                        yield quote
                else:
                    self._handle_text_message(message)

    async def _subscribe(self, websocket: Any) -> None:
        tokens = self.instrument_tokens
        if not tokens:
            raise ValueError("no instrument tokens configured for Kite feed")
        await websocket.send(json.dumps({"a": "subscribe", "v": tokens}))
        await websocket.send(json.dumps({"a": "mode", "v": [self.mode, tokens]}))

    def _parse_binary(self, payload: bytes) -> list[LiveQuote]:
        quotes: list[LiveQuote] = []
        for packet in parse_kite_binary_message(payload):
            quotes.append(packet.to_live_quote(self.token_symbol_map))
        return quotes

    def _handle_text_message(self, payload: str) -> None:
        try:
            body = json.loads(payload)
        except json.JSONDecodeError:
            logger.debug("ignored non-json kite message: %s", payload[:120])
            return
        message_type = body.get("type")
        if message_type == "error":
            logger.error("kite websocket error message: %s", body.get("data"))
        elif message_type not in {None, "order"}:
            logger.debug("kite websocket message: %s", body)


@dataclass(frozen=True, slots=True)
class FeedHealth:
    source: str
    connected: bool
    subscribed_symbols: tuple[str, ...]
    last_tick_at: datetime | None
    reconnect_count: int = 0
    last_error: str | None = None

    def snapshot(self, *, quotes: dict[str, LiveQuote], max_stale_ms: int) -> dict[str, Any]:
        now = datetime.now(tz=timezone.utc)
        stale_symbols: list[str] = []
        symbol_age_ms: dict[str, int] = {}
        for symbol in self.subscribed_symbols:
            quote = quotes.get(symbol)
            if quote is None:
                stale_symbols.append(symbol)
                continue
            age_ms = max(int((now - quote.timestamp).total_seconds() * 1000), 0)
            symbol_age_ms[symbol] = age_ms
            if age_ms > max_stale_ms:
                stale_symbols.append(symbol)
        last_tick_age_ms = None
        if self.last_tick_at is not None:
            last_tick_age_ms = max(int((now - self.last_tick_at).total_seconds() * 1000), 0)
        return {
            "source": self.source,
            "connected": self.connected,
            "subscribed_symbols": list(self.subscribed_symbols),
            "last_tick_at": self.last_tick_at.isoformat() if self.last_tick_at else None,
            "last_tick_age_ms": last_tick_age_ms,
            "reconnect_count": self.reconnect_count,
            "last_error": self.last_error,
            "stale_symbols": stale_symbols,
            "symbol_age_ms": symbol_age_ms,
            "is_stale": bool(stale_symbols) or (last_tick_age_ms is not None and last_tick_age_ms > max_stale_ms),
        }
