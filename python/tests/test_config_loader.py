from vhe.config.loader import load_platform_config
from vhe.execution.capital import CapitalAllocator


def test_load_platform_config_reads_yaml(project_root) -> None:
    config = load_platform_config(project_root)
    assert config.live.capital_cap_inr == 25_000
    assert config.strategies.pair.symbol_a == "RELIANCE"
    assert config.strategies.capital.grid_bucket_pct == 0.70
    assert config.strategies.grid.seed_deploy_pct == 0.0
    assert config.strategies.grid.min_spacing_pct == 0.004


def test_capital_allocator_buckets(project_root) -> None:
    config = load_platform_config(project_root)
    allocator = CapitalAllocator(
        total_capital=config.live.capital_cap_inr,
        buckets=config.strategies.capital,
        max_symbols=config.live.max_symbols,
        max_grid_levels=config.live.max_grid_levels,
    )
    buckets = allocator.compute_buckets()
    assert buckets.total == 25_000
    assert buckets.grid == 17_500
    assert buckets.pair == 2_500
    assert buckets.reserve == 2_500
    assert buckets.deployable == 22_500

    symbol = allocator.symbol_grid_allocation("RELIANCE", active_symbol_count=2)
    assert symbol.capital == 2_250
    assert symbol.level_capital == 450
