from vhe.analytics.paper_stats import classify_strategy, evaluate_strategy_health


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
