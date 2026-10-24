"""Fee accountant with a hard cumulative cap.

The accountant is the study's spend authority. It quotes a burst's exact fee
total before any send, and REFUSES (raises CapExceeded) any commit that would
push cumulative spend over config.CAP_LAMPORTS. State persists to a JSON
ledger so the cap holds across process runs, not just within one.
"""

from __future__ import annotations

import json
import os

from . import config


class CapExceeded(Exception):
    """Raised when a planned spend would exceed the hard cap."""


def priority_fee_lamports(tier: str) -> int:
    """Exact priority fee for a tier: ceil(CU_LIMIT * price / 1e6)."""
    price = config.FEE_TIERS[tier]
    return -(-config.CU_LIMIT * price // 1_000_000)


def tx_fee_lamports(tier: str) -> int:
    """Total network fee for one burst tx at a tier (base + priority)."""
    return config.BASE_FEE_LAMPORTS + priority_fee_lamports(tier)


def burst_fee_lamports(tiers: list[str]) -> int:
    return sum(tx_fee_lamports(t) for t in tiers)


class FeeAccountant:
    def __init__(self, ledger_path: str):
        self.ledger_path = ledger_path
        self.committed = 0
        self.entries: list[dict] = []
        if os.path.exists(ledger_path):
            with open(ledger_path, "r", encoding="utf-8") as fh:
                state = json.load(fh)
            self.committed = int(state["committed_lamports"])
            self.entries = state["entries"]

    @property
    def remaining_lamports(self) -> int:
        return config.CAP_LAMPORTS - self.committed

    def quote_burst(self, tiers: list[str]) -> int:
        """Exact fee total for a burst with these tiers. Pure, no state change."""
        return burst_fee_lamports(tiers)

    def check(self, tiers: list[str]) -> int:
        """Return the burst fee total, or raise CapExceeded. No state change."""
        total = self.quote_burst(tiers)
        if self.committed + total > config.CAP_LAMPORTS:
            raise CapExceeded(
                f"burst fee {total} lamports would push cumulative spend "
                f"{self.committed} over hard cap {config.CAP_LAMPORTS}"
            )
        return total

    def commit(self, label: str, tiers: list[str]) -> int:
        """Record a burst's fees against the cap. Raises CapExceeded first."""
        total = self.check(tiers)
        self.committed += total
        self.entries.append(
            {"label": label, "fee_lamports": total, "tiers": list(tiers)}
        )
        self._save()
        return total

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.ledger_path) or ".", exist_ok=True)
        tmp = self.ledger_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(
                {"committed_lamports": self.committed, "entries": self.entries},
                fh,
                indent=2,
            )
        os.replace(tmp, self.ledger_path)
