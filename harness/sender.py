"""Burst sending.

Two paths:
- simulate_burst(): dry-run. Builds the burst plan, quotes it against the
  fee cap, and returns deterministic simulated signatures. No network, no
  keys, no spend. This is the default everywhere.
- send_burst_live(): the real path, behind THREE gates: the caller passed
  --live, the environment sets INSIDE_BLOCK_LIVE_OK=1 (only set after the
  study checkpoint approves the live phase), and the FeeAccountant approves
  the burst against the hard cap. The keypair is loaded from the path in
  MEASURE_KEYPAIR_PATH at send time only; its contents never leave this
  function and are never logged.
"""

from __future__ import annotations

import json
import os
import time

from . import config, txbuild
from .burst import BurstPlan
from .fees import FeeAccountant
from .rpc import Rpc


class LiveGateError(Exception):
    pass


def simulate_burst(plan: BurstPlan, accountant: FeeAccountant) -> list[dict]:
    """Quote the burst against the cap (raises CapExceeded if over) and
    return per-tx simulated send records. Does NOT commit fees: simulated
    bursts spend nothing."""
    accountant.check(plan.tiers)
    now = int(time.time())
    return [
        {
            "send_index": tx.send_index,
            "fee_tier": tx.tier,
            "marker_amount": tx.marker_amount,
            "signature": txbuild.simulated_signature(plan.burst_id, tx.send_index),
            "sent_at_unix": now,
            "simulated": True,
        }
        for tx in plan.txs
    ]


def _load_seed() -> bytes:
    path = os.environ.get("MEASURE_KEYPAIR_PATH")
    if not path:
        raise LiveGateError("MEASURE_KEYPAIR_PATH is not set")
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, list) or len(raw) != 64:
        raise LiveGateError("keypair file is not a 64-byte Solana keypair array")
    return bytes(raw[:32])


def send_burst_live(plan: BurstPlan, accountant: FeeAccountant, rpc: Rpc) -> list[dict]:
    if os.environ.get("INSIDE_BLOCK_LIVE_OK") != "1":
        raise LiveGateError(
            "live sending is gated: INSIDE_BLOCK_LIVE_OK=1 is only set after "
            "the study checkpoint approves the live phase"
        )
    # Cap check happens BEFORE any key material is loaded or any tx is sent.
    accountant.check(plan.tiers)
    seed = _load_seed()
    from . import ed25519

    pub = ed25519.publickey(seed)
    if txbuild.b58encode(pub) != config.MEASUREMENT_WALLET:
        raise LiveGateError("loaded keypair does not match the measurement wallet")
    blockhash = txbuild.b58decode(rpc.get_latest_blockhash())
    sent = []
    for tx in plan.txs:
        raw, sig = txbuild.build_signed_tx(seed, tx.tier, tx.send_index, blockhash)
        import base64

        rpc.send_transaction(base64.b64encode(raw).decode())
        sent.append(
            {
                "send_index": tx.send_index,
                "fee_tier": tx.tier,
                "marker_amount": tx.marker_amount,
                "signature": sig,
                "sent_at_unix": int(time.time()),
                "simulated": False,
            }
        )
    # Fees are committed only after the burst actually went out.
    accountant.commit(plan.burst_id, plan.tiers)
    return sent
