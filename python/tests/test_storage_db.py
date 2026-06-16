from pathlib import Path
from datetime import datetime, timezone

from vhe.backtest.models import Fill, OrderSide
from vhe.storage.db import PlatformDatabase


def test_platform_database_persists_events_and_fills(tmp_path: Path) -> None:
    db = PlatformDatabase(tmp_path / "test.db")
    db.append_event(category="control", message="started", severity="info")
    db.save_fill(
        {
            "fill_id": "f1",
            "order_id": "o1",
            "symbol": "AAA",
            "side": "BUY",
            "price": 100.0,
            "quantity": 1,
            "fees": 0.5,
            "reason": "test",
            "filled_at": "2026-06-15T10:00:00+00:00",
        }
    )
    events = db.recent_events()
    fills = db.recent_fills()
    assert len(events) == 1
    assert events[0]["message"] == "started"
    assert len(fills) == 1
    assert fills[0]["symbol"] == "AAA"


def test_platform_database_persists_fill_dataclass(tmp_path: Path) -> None:
    db = PlatformDatabase(tmp_path / "test.db")
    fill = Fill(
        order_id="dg-TMPV-1",
        symbol="TMPV",
        side=OrderSide.BUY,
        price=390.4,
        quantity=1,
        timestamp=datetime(2026, 6, 16, 8, 0, tzinfo=timezone.utc),
        fees=1.0,
        reason="dynamic_grid_level_1",
    )

    db.persist_fill_dataclass(fill)

    rows = db.recent_fills()
    assert len(rows) == 1
    assert rows[0]["symbol"] == "TMPV"
    assert rows[0]["side"] == "BUY"
    assert rows[0]["filled_at"].startswith("2026-06-16")
