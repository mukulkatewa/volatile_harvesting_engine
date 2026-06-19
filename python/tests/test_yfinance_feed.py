from vhe.live.yfinance_feed import (
    YFinanceQuoteFeed,
    from_yfinance_symbol,
    to_yfinance_symbol,
)


def test_to_yfinance_symbol() -> None:
    assert to_yfinance_symbol("reliance") == "RELIANCE.NS"
    assert to_yfinance_symbol("HDFCBANK.NS") == "HDFCBANK.NS"


def test_from_yfinance_symbol() -> None:
    assert from_yfinance_symbol("RELIANCE.NS") == "RELIANCE"


def test_fetch_yfinance_quotes_mock(monkeypatch) -> None:
    from datetime import datetime, timezone

    import vhe.live.yfinance_feed as yf_module
    from vhe.live.models import LiveQuote

    now = datetime.now(tz=timezone.utc)

    def fake_batch(symbols: list[str], timestamp, **kwargs) -> list[LiveQuote]:
        return [
            LiveQuote(
                timestamp=now,
                symbol=symbols[0],
                ltp=2500.0,
                open=2490.0,
                high=2510.0,
                low=2485.0,
                close=2495.0,
                volume=1000,
            )
        ]

    monkeypatch.setattr(yf_module, "_fetch_batch_quotes", fake_batch)
    quotes = yf_module.fetch_yfinance_quotes(["RELIANCE"])
    assert quotes[0].symbol == "RELIANCE"
    assert quotes[0].ltp == 2500.0


def test_fetch_yfinance_quotes_merges_cache_for_missing_symbols(monkeypatch) -> None:
    from datetime import datetime, timezone

    import vhe.live.yfinance_feed as yf_module
    from vhe.live.models import LiveQuote

    now = datetime.now(tz=timezone.utc)
    cache = {
        "TCS": LiveQuote(
            timestamp=now,
            symbol="TCS",
            ltp=2000.0,
            open=1990.0,
            high=2010.0,
            low=1985.0,
            close=2000.0,
            volume=1000,
        )
    }

    def fake_batch(symbols: list[str], timestamp, **kwargs) -> list[LiveQuote]:
        if "RELIANCE" in symbols:
            return [
                LiveQuote(
                    timestamp=timestamp,
                    symbol="RELIANCE",
                    ltp=2500.0,
                    open=2490.0,
                    high=2510.0,
                    low=2485.0,
                    close=2495.0,
                    volume=1000,
                )
            ]
        return []

    monkeypatch.setattr(yf_module, "_fetch_batch_quotes", fake_batch)
    quotes = yf_module.fetch_yfinance_quotes(["RELIANCE", "TCS"], cache=cache)
    symbols = {quote.symbol for quote in quotes}
    assert symbols == {"RELIANCE", "TCS"}


def test_scalar_rejects_nan_volume() -> None:
    import math

    import vhe.live.yfinance_feed as yf_module

    assert yf_module._scalar(float("nan")) == 0.0
    assert yf_module._scalar(math.inf) == 0.0


def test_build_yfinance_feed(project_root) -> None:
    from vhe.config.loader import load_platform_config
    from vhe.live.feed_factory import build_quote_feed

    config = load_platform_config(project_root)
    result = build_quote_feed(config, project_root=project_root)
    assert result.source == "yfinance"
    assert isinstance(result.feed, YFinanceQuoteFeed)
