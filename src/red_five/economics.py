"""Conditional accounting for externally supplied interval weights and costs."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal, localcontext

from .contracts import WeightObservation


def account_weights(rows: tuple[WeightObservation, ...]) -> dict[str, object]:
    groups: dict[tuple[str, datetime], list[WeightObservation]] = defaultdict(list)
    for row in rows:
        groups[row.portfolio_id, row.decision_time].append(row)
    periods: list[dict[str, object]] = []
    with localcontext() as context:
        context.prec = 80
        for (portfolio, decision), sample in sorted(groups.items()):
            gross = Decimal(0)
            trades = Decimal(0)
            holding = Decimal(0)
            turnover = Decimal(0)
            for row in sample:
                change = abs(row.target_weight - row.pre_trade_weight)
                gross += row.target_weight * row.asset_total_return
                trades += change * row.trade_cost_bps / Decimal(10000)
                holding += row.holding_cost_nav_bps / Decimal(10000)
                turnover += change
            periods.append(
                {
                    "portfolio_id": portfolio,
                    "decision_time": decision.isoformat(),
                    "label_start": sample[0].label_start.isoformat(),
                    "label_end": sample[0].label_end.isoformat(),
                    "constituents": len(sample),
                    "gross_return": str(gross),
                    "trading_cost_return": str(trades),
                    "holding_cost_return": str(holding),
                    "turnover_absolute": str(turnover),
                    "net_return": str(gross - trades - holding),
                }
            )
    return {
        "status": "available" if rows else "unavailable",
        "reason": None if rows else "external-weights-not-supplied",
        "basis": "per-interval pre-trade NAV; supplied holdings and returns",
        "periods": periods,
    }
