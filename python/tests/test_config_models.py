from pathlib import Path

from vhe.config.models import AppConfig


def test_app_config_loads_from_yaml() -> None:
    config = AppConfig.from_yaml(Path("configs/app.yaml"))

    assert config.universe.name == "nifty100"
    assert "RELIANCE" in config.universe.symbols
    assert config.paths.raw_data_dir == Path("data/raw")

