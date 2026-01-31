# src/aggregator/liquidation.py
from dataclasses import dataclass

from src.storage.models import Liquidation


@dataclass
class LiqStats:
    long: float = 0.0
    short: float = 0.0

    @property
    def total(self) -> float:
        return self.long + self.short


def calculate_liquidations(liqs: list[Liquidation]) -> LiqStats:
    if not liqs:
        return LiqStats()

    # sell = 多头爆仓 (long liquidation)
    # buy = 空头爆仓 (short liquidation)
    long_liq = sum(liq.value_usd for liq in liqs if liq.side == "sell")
    short_liq = sum(liq.value_usd for liq in liqs if liq.side == "buy")

    return LiqStats(long=long_liq, short=short_liq)
