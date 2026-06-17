from pathlib import Path

from vhe.analytics.paper_stats import PaperStatsService
from vhe.analytics.session_tracker import PaperSessionTracker
from vhe.backtest.models import Fill, OrderSide
from datetime import datetime, timezone


def test_paper_session_lifecycle(tmp_path: Path) -> None:
    from vhe.storage.db import PlatformDatabase

    db = PlatformDatabase(tmp_path / "stats.db")
    tracker = PaperSessionTracker(db, mode="paper", initial_cash=75_000)
    tracker.bootstrap()
    assert tracker.session_id is not None

    fill = Fill(
        order_id="dg-ITC-1",
        symbol="ITC",
        side=OrderSide.BUY,
        price=291.0,
        quantity=10,
        timestamp=datetime.now(tz=timezone.utc),
        fees=1.0,
        reason="dynamic_grid_seed_deploy",
    )
    tracker.record_fill(fill)
    fill_id = db.persist_fill_dataclass(fill)
    db.link_fill_to_session(tracker.session_id, fill_id)

    portfolio = {
        "equity": 74_990.0,
        "cash": 20_000.0,
        "gross_exposure": 54_990.0,
        "gross_exposure_pct": 73.3,
        "unrealized_pnl": -10.0,
        "realized_pnl": 0.0,
        "fees_paid": 1.0,
    }
    tracker.maybe_snapshot(portfolio)
    tracker.on_market_close(portfolio)

    report = PaperStatsService(db).build_report(portfolio=portfolio, active_session=None)
    assert report["multi_session"]["sessions_count"] == 1
    assert report["sessions"][0]["status"] == "closed"
    assert report["sessions"][0]["fill_count"] == 1
