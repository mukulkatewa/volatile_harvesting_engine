from __future__ import annotations

from dataclasses import dataclass

from vhe.backtest.models import OrderSide


@dataclass(frozen=True, slots=True)
class EquityIntradayCostModel:
    brokerage_rate: float = 0.0003
    brokerage_cap_per_order: float = 20.0
    stt_sell_rate: float = 0.00025
    exchange_txn_rate: float = 0.0000297
    sebi_rate: float = 0.000001
    stamp_buy_rate: float = 0.00003
    gst_rate: float = 0.18

    def estimate(self, *, side: OrderSide, price: float, quantity: int) -> float:
        turnover = price * quantity
        brokerage = min(turnover * self.brokerage_rate, self.brokerage_cap_per_order)
        exchange_charge = turnover * self.exchange_txn_rate
        sebi_charge = turnover * self.sebi_rate
        stt = turnover * self.stt_sell_rate if side == OrderSide.SELL else 0.0
        stamp = turnover * self.stamp_buy_rate if side == OrderSide.BUY else 0.0
        gst = (brokerage + exchange_charge + sebi_charge) * self.gst_rate
        return brokerage + exchange_charge + sebi_charge + stt + stamp + gst

