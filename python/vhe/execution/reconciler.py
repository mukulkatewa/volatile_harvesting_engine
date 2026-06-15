from __future__ import annotations

import logging
from dataclasses import dataclass, field

from vhe.execution.kite_broker import KiteBroker

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Reconciler:
    kite_broker: KiteBroker | None = None
    last_sync_at: str | None = None
    last_error: str | None = None
    open_orders: list[dict] = field(default_factory=list)
    recent_trades: list[dict] = field(default_factory=list)

    def sync(self) -> dict:
        if self.kite_broker is None:
            return self.snapshot()
        try:
            orders = self.kite_broker.fetch_orders()
            trades = self.kite_broker.fetch_trades()
            self.open_orders = [row for row in orders if row.get("status") not in {"COMPLETE", "CANCELLED", "REJECTED"}]
            self.recent_trades = trades[-25:]
            self.last_error = None
            from datetime import datetime, timezone

            self.last_sync_at = datetime.now(tz=timezone.utc).isoformat()
        except Exception as exc:
            logger.exception("reconcile failed: %s", exc)
            self.last_error = str(exc)
        return self.snapshot()

    def snapshot(self) -> dict:
        return {
            "enabled": self.kite_broker is not None,
            "last_sync_at": self.last_sync_at,
            "last_error": self.last_error,
            "open_orders": self.open_orders[-25:],
            "recent_trades": self.recent_trades[-25:],
        }
