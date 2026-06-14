from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KiteFeedConfig:
    api_key: str
    access_token: str
    instrument_tokens: list[int]
    mode: str = "full"


class KiteWebSocketFeed:
    """Placeholder for the real Kite binary WebSocket parser."""

    def __init__(self, config: KiteFeedConfig) -> None:
        self.config = config

    async def stream(self):
        raise NotImplementedError("Kite feed requires binary packet parsing and auth wiring")
