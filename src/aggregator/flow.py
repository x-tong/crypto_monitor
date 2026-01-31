# src/aggregator/flow.py
from dataclasses import dataclass, field

from src.storage.models import Trade


@dataclass
class FlowResult:
    net: float = 0.0
    buy: float = 0.0
    sell: float = 0.0
    by_exchange: dict[str, float] = field(default_factory=dict)


def calculate_flow(trades: list[Trade]) -> FlowResult:
    if not trades:
        return FlowResult()

    buy = sum(t.value_usd for t in trades if t.side == "buy")
    sell = sum(t.value_usd for t in trades if t.side == "sell")
    net = buy - sell

    by_exchange: dict[str, float] = {}
    for t in trades:
        exchange_net = t.value_usd if t.side == "buy" else -t.value_usd
        by_exchange[t.exchange] = by_exchange.get(t.exchange, 0) + exchange_net

    return FlowResult(net=net, buy=buy, sell=sell, by_exchange=by_exchange)
