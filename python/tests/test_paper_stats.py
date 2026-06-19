from vhe.analytics.paper_stats import PaperStatsService, classify_strategy, evaluate_strategy_health
from vhe.storage.db import PlatformDatabase


def test_classify_strategy_grid() -> None:
    assert classify_strategy("dynamic_grid_level_1") == "grid"
    assert classify_strategy("dynamic_grid_seed_deploy") == "grid"


def test_classify_strategy_pair_and_momentum() -> None:
    assert classify_strategy("pair_entry") == "pair"
    assert classify_strategy("momentum_breakout") == "momentum"


def test_strategy_health_too_early() -> None:
    health = evaluate_strategy_health(
        fill_count=3,
        strategy_breakdown={"grid": 3},
        total_pnl=-5.0,
        fees_paid=4.0,
        avg_deployed=50_000,
        minutes_active=12.0,
        exit_reasons={},
    )
    assert health.verdict == "too_early"
    assert "80% deployed" in health.notes[0]


def test_report_falls_back_to_last_session_when_none_active(tmp_path) -> None:
    # Regression: after market close the active session is cleared, which left the
    # stats panel stuck on "Collecting session data...". The report must surface the
    # most recent (closed) session instead of returning current_session=None.
    db = PlatformDatabase(tmp_path / "stats.db")
    db.create_paper_session(
        session_id="2026-06-19",
        trading_date="2026-06-19",
        mode="paper",
        initial_cash=75_000.0,
        started_at="2026-06-19T04:00:00+00:00",
    )
    db.close_paper_session(
        session_id="2026-06-19",
        ended_at="2026-06-19T09:30:00+00:00",
        final_equity=75_120.0,
        total_pnl=120.0,
        realized_pnl=120.0,
        unrealized_pnl=0.0,
        fees_paid=18.0,
        fill_count=22,
        strategy_breakdown={"grid": 22},
        max_exposure_pct=40.0,
        max_drawdown_pct=1.2,
    )

    service = PaperStatsService(db)
    report = service.build_report(portfolio={"equity": 75_000.0, "cash": 75_000.0}, active_session=None)

    assert report["current_session"] is not None
    assert report["current_session"]["is_active"] is False
    assert report["current_session"]["total_pnl"] == 120.0
    assert report["current_session"]["fill_count"] == 22


def test_strategy_health_deployed_waiting_for_exits() -> None:
    health = evaluate_strategy_health(
        fill_count=12,
        strategy_breakdown={"grid": 12},
        total_pnl=2.0,
        fees_paid=5.0,
        avg_deployed=60_000,
        minutes_active=45.0,
        exit_reasons={},
    )
    assert health.verdict == "deployed"
