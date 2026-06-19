from datetime import datetime, timezone

import pytest

from vhe.live.models import LiveQuote
from vhe.platform.services.indicator_service import IndicatorService
from vhe.platform.services.regime_service import RegimeService
from vhe.config.loader import RegimeConfig


@pytest.fixture
def quote() -> LiveQuote:
    return LiveQuote(
        timestamp=datetime.now(tz=timezone.utc),
        symbol="AAA",
        ltp=100.0,
        open=99.0,
        high=101.0,
        low=98.5,
        close=99.5,
        volume=1000,
    )


def test_indicator_service_produces_snapshot(quote: LiveQuote) -> None:
    service = IndicatorService(history_size=60)
    snapshot = service.update(quote)
    assert snapshot.symbol == "AAA"
    assert snapshot.ltp == 100.0
    assert snapshot.atr_14 > 0


def test_regime_service_classifies_range(quote: LiveQuote) -> None:
    service = IndicatorService()
    regime_service = RegimeService(config=RegimeConfig())
    for i in range(25):
        tick = LiveQuote(
            timestamp=quote.timestamp,
            symbol=quote.symbol,
            ltp=100.0 + (i % 3) * 0.1,
            open=99.8,
            high=100.4,
            low=99.6,
            close=100.0,
            volume=1000,
        )
        snapshot = service.update(tick)
    regime = regime_service.classify(snapshot)
    assert regime.value in {"RANGE", "UNKNOWN", "TREND_UP", "TREND_DOWN", "CRASH"}


def test_indicator_service_seeds_history() -> None:
    service = IndicatorService()
    service.seed_bars(
        "RELIANCE",
        [
            {"open": 100, "high": 101, "low": 99, "close": 100, "ltp": 100},
            {"open": 101, "high": 102, "low": 100, "close": 101, "ltp": 101},
        ],
    )
    assert len(service._history["RELIANCE"]) == 2
