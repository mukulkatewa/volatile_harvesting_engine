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

    def fake_fetch(symbols: list[str]) -> list[LiveQuote]:
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

    monkeypatch.setattr(yf_module, "fetch_yfinance_quotes", fake_fetch)
    quotes = yf_module.fetch_yfinance_quotes(["RELIANCE"])
    assert quotes[0].symbol == "RELIANCE"
    assert quotes[0].ltp == 2500.0


def test_build_yfinance_feed(project_root) -> None:
    from vhe.config.loader import load_platform_config
    from vhe.live.feed_factory import build_quote_feed

    config = load_platform_config(project_root)
    result = build_quote_feed(config, project_root=project_root)
    assert result.source == "yfinance"
    assert isinstance(result.feed, YFinanceQuoteFeed)
