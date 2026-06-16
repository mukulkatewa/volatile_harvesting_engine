import os
from pathlib import Path

import pytest

from vhe.config.loader import load_platform_config
from vhe.live.feed import SimulatedQuoteFeed
from vhe.live.feed_factory import build_quote_feed


def test_build_quote_feed_simulated_by_default(project_root: Path) -> None:
    base = load_platform_config(project_root)
    strategies = base.strategies.model_copy(
        update={"feed": base.strategies.feed.model_copy(update={"source": "simulated"})}
    )
    config = base.model_copy(update={"strategies": strategies})
    result = build_quote_feed(config, project_root=project_root)
    assert result.source == "simulated"
    assert isinstance(result.feed, SimulatedQuoteFeed)


def test_build_quote_feed_falls_back_without_credentials(project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = load_platform_config(project_root)
    strategies = base.strategies.model_copy(
        update={"feed": base.strategies.feed.model_copy(update={"source": "kite"})}
    )
    live = base.live.model_copy(update={"broker": base.live.broker.model_copy(update={"websocket_enabled": True})})
    config = base.model_copy(update={"strategies": strategies, "live": live})
    monkeypatch.delenv("KITE_API_KEY", raising=False)
    monkeypatch.delenv("KITE_ACCESS_TOKEN", raising=False)
    result = build_quote_feed(config, project_root=project_root)
    assert result.source == "simulated"
    assert result.warning is not None
