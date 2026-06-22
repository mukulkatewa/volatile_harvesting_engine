from datetime import datetime, timezone

from vhe.sentiment.models import BuzzItem, SentimentAction, SentimentStatus
from vhe.sentiment.scoring import aggregate_symbol_score, lexicon_score, portfolio_snapshot
from vhe.sentiment.service import SentimentConfig, SentimentService
from vhe.sentiment.symbols import match_symbol, search_queries


def test_lexicon_score_detects_bearish_terms() -> None:
    assert lexicon_score("Company faces fraud probe and selloff") < -0.5
    assert lexicon_score("Record profit beat estimates rally") > 0.5


def test_trading_universe_fills_to_max_even_without_buzz() -> None:
    # Regression: when only 1-2 names had buzz, the universe collapsed to those,
    # starving capital deployment. It must fill up to max_symbols with eligible names.
    service = SentimentService(
        SentimentConfig(reddit_enabled=False, hackernews_enabled=False, last30days_enabled=False),
        symbols=["RELIANCE", "INFY", "TCS", "SBIN", "ITC", "LT"],
    )
    universe = service.trading_universe(4)
    assert len(universe) == 4
    assert all(symbol in service.symbols for symbol in universe)


def test_engine_refresh_symbol_runs_without_import_error() -> None:
    # Regression: engine.refresh_symbol used filter_buzz_items without importing it,
    # silently killing every sentiment refresh. It must run and score buzz now.
    from vhe.sentiment.engine import SentimentEngine

    engine = SentimentEngine(
        [],
        half_life_hours=12.0,
        halt_score=-0.55,
        elevated_score=-0.25,
        reduce_size_multiplier=0.5,
        widen_spacing_multiplier=1.35,
    )
    negative = [
        BuzzItem(
            source="reddit",
            symbol="INFY",
            title="INFY fraud probe selloff bankruptcy scandal downgrade",
            url="x",
            engagement=9000,
            published_at=datetime.now(tz=timezone.utc),
            text="investigation crash plunge",
        )
    ]
    row, items = engine.refresh_symbol("INFY", extra_items=negative)
    assert row.status == SentimentStatus.HALT
    assert row.action == SentimentAction.HALT
    assert len(items) == 1


def test_match_symbol_aliases() -> None:
    assert match_symbol("Reliance Industries Q4 results", "RELIANCE")
    assert match_symbol("HDFC Bank earnings", "HDFCBANK")


def test_aggregate_symbol_score_halt_on_negative_buzz() -> None:
    now = datetime.now(tz=timezone.utc)
    items = [
        BuzzItem(
            source="reddit",
            symbol="TMPV",
            title="TMPV crash warning fraud probe",
            url="https://reddit.com/r/stocks/1",
            engagement=1500,
            published_at=now,
            raw_score=-0.8,
        ),
        BuzzItem(
            source="reddit",
            symbol="TMPV",
            title="Tata Motors selloff continues",
            url="https://reddit.com/r/stocks/2",
            engagement=900,
            published_at=now,
            raw_score=-0.7,
        ),
    ]
    row = aggregate_symbol_score(
        items,
        now=now,
        half_life_hours=12,
        halt_score=-0.55,
        elevated_score=-0.25,
        reduce_size_multiplier=0.5,
        widen_spacing_multiplier=1.35,
    )
    assert row.status == SentimentStatus.HALT
    assert row.action == SentimentAction.HALT
    assert row.size_multiplier == 0.0


def test_sentiment_service_allows_buy_when_clear() -> None:
    service = SentimentConfig(enabled=False)
    engine = SentimentService(config=service, symbols=["RELIANCE"])
    assert engine.allows_buy("RELIANCE")


def test_search_queries_include_nse_context() -> None:
    queries = search_queries("RELIANCE")
    assert any("NSE" in query for query in queries)


def test_portfolio_snapshot_flags_halt_symbols() -> None:
    from vhe.sentiment.models import SymbolSentiment

    symbols = {
        "TMPV": SymbolSentiment(
            symbol="TMPV",
            score=-0.7,
            buzz_volume=3,
            status=SentimentStatus.HALT,
            action=SentimentAction.HALT,
            headline="bad",
            size_multiplier=0.0,
            spacing_multiplier=1.35,
        )
    }
    status, headline, _, flagged = portfolio_snapshot(
        symbols,
        last_refresh_at=datetime.now(tz=timezone.utc),
        sources_active=("reddit",),
    )
    assert status == SentimentStatus.HALT
    assert "TMPV" in flagged
