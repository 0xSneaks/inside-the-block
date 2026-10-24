"""Burst planning: the unit of evidence for the study.

One burst = BURST_SIZE self-transactions from the measurement wallet aimed
at one leader window. Fee tiers follow config.TIER_PATTERN (decorrelated
from send order); the pattern is REVERSED on alternate bursts to control
for position effects (see DESIGN.md, Controls).
"""

from __future__ import annotations

from dataclasses import dataclass

from . import config


@dataclass
class BurstTx:
    send_index: int
    tier: str
    marker_amount: int


@dataclass
class BurstPlan:
    burst_id: str
    validator_identity: str | None  # target leader, if known at plan time
    txs: list[BurstTx]

    @property
    def tiers(self) -> list[str]:
        return [t.tier for t in self.txs]


def plan_burst(burst_id: str, burst_number: int,
               validator_identity: str | None = None) -> BurstPlan:
    """burst_number is 0-based across the study; odd bursts use the reversed
    tier pattern."""
    pattern = list(config.TIER_PATTERN)
    if burst_number % 2 == 1:
        pattern = pattern[::-1]
    txs = [
        BurstTx(
            send_index=i,
            tier=pattern[i],
            marker_amount=config.MARKER_BASE_LAMPORTS + i,
        )
        for i in range(config.BURST_SIZE)
    ]
    return BurstPlan(burst_id=burst_id, validator_identity=validator_identity, txs=txs)
