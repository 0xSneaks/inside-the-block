"""Landed-order capture: find our transactions in produced blocks.

For each signature in a burst, locate its slot and its position (index)
within that block's transaction list, plus the block's total transaction
count as the fullness signal. Works against any block source exposing
get_block(slot); the simulated source below drives the dry-run pipeline and
Phase 2's local shakedown.
"""

from __future__ import annotations

import random

from .rpc import Rpc


class RpcBlockSource:
    def __init__(self, rpc: Rpc):
        self.rpc = rpc

    def get_block(self, slot: int) -> dict | None:
        return self.rpc.get_block(slot)


class SimulatedBlockSource:
    """Fabricates one block per burst for dry runs. `rule` is the ground
    truth the simulation lands by: 'arrival' (send order), 'fee' (priority
    fee descending), or 'random' (seeded shuffle — the H0 world)."""

    def __init__(self, rule: str = "random", seed: int = 42):
        self.rule = rule
        self.seed = seed
        self._blocks: dict[int, dict] = {}

    def register_burst(self, slot: int, signatures: list[str],
                       tiers: list[str], tier_rank: dict[str, int]) -> None:
        rng = random.Random(f"{self.seed}:{slot}")
        order = list(range(len(signatures)))
        if self.rule == "fee":
            order.sort(key=lambda i: (-tier_rank[tiers[i]], rng.random()))
        elif self.rule == "random":
            rng.shuffle(order)
        # 'arrival': order stays send order
        filler = [f"filler-{slot}-{i}" for i in range(rng.randint(50, 400))]
        landed_sigs = [signatures[i] for i in order]
        # Place landed txs in their relative order inside the block, with
        # filler transactions spread around them.
        block_txs = []
        chunk = max(1, len(filler) // (len(landed_sigs) + 1))
        pos = 0
        for sig in landed_sigs:
            block_txs.extend(filler[pos:pos + chunk])
            pos += chunk
            block_txs.append(sig)
        block_txs.extend(filler[pos:])
        self._blocks[slot] = {
            "blockTime": 1_700_000_000 + slot,
            "transactions": [
                {"transaction": {"signatures": [s]}, "meta": {"err": None}}
                for s in block_txs
            ],
        }

    def get_block(self, slot: int) -> dict | None:
        return self._blocks.get(slot)


def locate_in_block(block: dict, signatures: list[str]) -> dict[str, dict]:
    """signature -> {landed_position, block_tx_count} for signatures present
    in this block."""
    txs = block.get("transactions") or []
    wanted = set(signatures)
    found = {}
    for idx, entry in enumerate(txs):
        sigs = (entry.get("transaction") or {}).get("signatures") or []
        if sigs and sigs[0] in wanted:
            found[sigs[0]] = {
                "landed_position": idx,
                "block_tx_count": len(txs),
            }
    return found
