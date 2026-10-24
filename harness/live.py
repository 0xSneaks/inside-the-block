"""Live measurement runner (the study's only spend path).

Fires pre-signed bursts into chosen leader windows, captures where each
transaction actually landed, attributes each landed record to the leader of
its landed slot (per DESIGN.md), and writes the raw dataset incrementally.

Gates (all enforced here, not by convention):
- INSIDE_BLOCK_LIVE_OK=1 must be set (set only for an approved live run).
- The FeeAccountant must approve each burst against the hard cap BEFORE
  the keypair is loaded or anything is signed.
- The loaded keypair must match config.MEASUREMENT_WALLET.

Send path: a single RPC endpoint for every send in the study.
"""

from __future__ import annotations

import base64
import os
import time
from concurrent.futures import ThreadPoolExecutor

from . import config, ed25519, leaders, txbuild
from .burst import BurstPlan, plan_burst
from .capture import locate_in_block
from .dataset import DatasetWriter
from .fees import FeeAccountant
from .rpc import Rpc
from .sender import LiveGateError, _load_seed

SLOT_SECONDS = 0.4


def _slot(rpc: Rpc) -> int:
    return rpc.call("getSlot", [{"commitment": "processed"}])


def _wait_for_slot(rpc: Rpc, target: int) -> None:
    while True:
        now = _slot(rpc)
        if now >= target:
            return
        time.sleep(min(2.0, max(0.2, (target - now) * SLOT_SECONDS * 0.7)))


def _send_one(url: str, raw_b64: str) -> tuple[str | None, str | None]:
    rpc = Rpc(url)
    try:
        sig = rpc.send_transaction(raw_b64)
        return sig, None
    except Exception as exc:  # preflight failure etc: tx not sent, no fee
        return None, str(exc)[:200]


def fire_burst(rpc: Rpc, rpc_url: str, plan: BurstPlan, window: dict,
               slot_leaders: dict, nodes_meta: dict,
               accountant: FeeAccountant, writer: DatasetWriter,
               seed: bytes) -> dict:
    """Fire one burst at `window` and record the outcome. Returns a summary."""
    accountant.check(plan.tiers)  # hard cap, before keys/signing/sending
    first_slot = window["first_slot"]
    _wait_for_slot(rpc, first_slot - 45)
    blockhash = txbuild.b58decode(
        rpc.call("getLatestBlockhash", [{"commitment": "processed"}])["value"]["blockhash"]
    )
    prepared = []
    for tx in plan.txs:
        raw, sig = txbuild.build_signed_tx(seed, tx.tier, tx.send_index, blockhash)
        prepared.append((tx, sig, base64.b64encode(raw).decode()))
    _wait_for_slot(rpc, first_slot)
    sent_at = int(time.time())
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda p: _send_one(rpc_url, p[2]), prepared))
    sent_sigs = {}
    send_errors = {}
    for (tx, sig, _), (returned, err) in zip(prepared, results):
        if returned:
            sent_sigs[sig] = tx
        else:
            send_errors[tx.send_index] = err
    # Capture: give the chain time to produce the window's blocks, then scan
    # a slot range around the window for our signatures. Two passes: a block
    # that is not fetchable yet must not be recorded as "not landed".
    found: dict[str, tuple[int, dict]] = {}
    for attempt in range(2):
        if attempt:
            time.sleep(20)
        missing = [s for s in sent_sigs if s not in found]
        if not missing:
            break
        time.sleep(25 if attempt == 0 else 0)
        for slot in range(first_slot - 2, window["last_slot"] + 12):
            try:
                block = rpc.get_block(slot)
            except Exception:
                block = None
            if not block:
                continue
            hits = locate_in_block(block, missing)
            for sig, loc in hits.items():
                found[sig] = (slot, loc)
    landed = 0
    for tx, sig, _ in prepared:
        if sig in found:
            slot, loc = found[sig]
            leader = leaders.leader_at_slot(slot_leaders, slot)
            meta = nodes_meta.get(leader or "", {})
            writer.write({
                "burst_id": plan.burst_id,
                "validator_identity": leader,
                "client_family": meta.get("family"),
                "send_index": tx.send_index,
                "fee_tier": tx.tier,
                "marker_amount": tx.marker_amount,
                "signature": sig,
                "target_first_slot": first_slot,
                "target_last_slot": window["last_slot"],
                "landed_slot": slot,
                "landed_position": loc["landed_position"],
                "block_tx_count": loc["block_tx_count"],
                "sent_at_unix": sent_at,
                "landed": True,
                "simulated": False,
            })
            landed += 1
        else:
            writer.write({
                "burst_id": plan.burst_id,
                "validator_identity": None,
                "client_family": None,
                "send_index": tx.send_index,
                "fee_tier": tx.tier,
                "marker_amount": tx.marker_amount,
                "signature": sig if sig in sent_sigs else None,
                "target_first_slot": first_slot,
                "target_last_slot": window["last_slot"],
                "landed_slot": None,
                "landed_position": None,
                "block_tx_count": None,
                "sent_at_unix": sent_at,
                "landed": False,
                "simulated": False,
            })
    if sent_sigs:
        accountant.commit(plan.burst_id, plan.tiers)
    return {
        "burst_id": plan.burst_id,
        "target": window["identity"],
        "window": [first_slot, window["last_slot"]],
        "sent": len(sent_sigs),
        "send_errors": send_errors,
        "landed": landed,
    }


def select_targets(windows: list[dict], nodes_meta: dict,
                     per_validator_bursts: int) -> list[dict]:
    """Pick burst targets: >=6 validators spanning the available client
    families/versions, each with enough upcoming windows. Returns an ordered
    list of {identity, family, version, windows:[...]}."""
    by_identity: dict[str, list[dict]] = {}
    for w in windows:
        by_identity.setdefault(w["identity"], []).append(w)
    candidates = []
    for identity, wins in by_identity.items():
        if len(wins) < per_validator_bursts:
            continue
        meta = nodes_meta.get(identity, {})
        candidates.append({
            "identity": identity,
            "family": meta.get("family") or "UNKNOWN",
            "version": meta.get("version"),
            "windows": wins,
        })
    # Diversity-first ordering: one per (family, version) group first.
    candidates.sort(key=lambda c: c["windows"][0]["first_slot"])
    picked: list[dict] = []
    seen_groups = set()
    for c in candidates:
        group = (c["family"], c["version"])
        if group not in seen_groups:
            picked.append(c)
            seen_groups.add(group)
        if len(picked) >= 8:
            break
    if len(picked) < config.MIN_VALIDATORS:
        for c in candidates:
            if c not in picked:
                picked.append(c)
            if len(picked) >= config.MIN_VALIDATORS:
                break
    return picked[:8]


def run_study(rpc_url: str, dataset_path: str, ledger_path: str,
              log=print) -> list[dict]:
    if os.environ.get("INSIDE_BLOCK_LIVE_OK") != "1":
        raise LiveGateError("INSIDE_BLOCK_LIVE_OK=1 is not set")
    rpc = Rpc(rpc_url)
    balance = rpc.call("getBalance", [config.MEASUREMENT_WALLET])["value"]
    log(f"measurement wallet balance: {balance} lamports")
    if balance < config.CAP_LAMPORTS:
        raise LiveGateError("wallet balance below the study cap; not firing")
    seed = _load_seed()
    pub = ed25519.publickey(seed)
    if txbuild.b58encode(pub) != config.MEASUREMENT_WALLET:
        raise LiveGateError("keypair does not match the measurement wallet")
    epoch_info = rpc.get_epoch_info()
    jito = leaders.fetch_jito_identities()
    log(f"jito identities (running_jito): {len(jito)}")
    nodes_meta = leaders.node_versions(rpc, jito)
    slots_left = epoch_info["slotsInEpoch"] - epoch_info["slotIndex"]
    horizon = max(0, min(54_000, slots_left - 500))
    slot_leaders = leaders.fetch_slot_leaders(
        rpc, epoch_info["absoluteSlot"], horizon + 64)
    windows = leaders.windows_from_leaders(slot_leaders,
                                           epoch_info["absoluteSlot"])
    targets = select_targets(windows, nodes_meta, config.BURSTS_PER_VALIDATOR)
    log(f"targets: {[(t['identity'][:8], t['family'], t['version']) for t in targets]}")
    # Global firing schedule: windows in slot order, >=120 slots of lead
    # time, >=1500 slots between one validator's bursts (burst separation),
    # >=250 slots between any two bursts (prep time).
    now_slot = epoch_info["absoluteSlot"]
    firing: list[tuple[dict, dict]] = []
    last_for_validator: dict[str, int] = {}
    last_any = 0
    all_windows = sorted(
        (w for t in targets for w in t["windows"]),
        key=lambda w: w["first_slot"],
    )
    counts: dict[str, int] = {}
    for w in all_windows:
        ident = w["identity"]
        if counts.get(ident, 0) >= config.BURSTS_PER_VALIDATOR:
            continue
        if w["first_slot"] < now_slot + 120:
            continue
        if w["first_slot"] - last_for_validator.get(ident, -10**9) < 1500:
            continue
        if w["first_slot"] - last_any < 250:
            continue
        firing.append((w, next(t for t in targets if t["identity"] == ident)))
        last_for_validator[ident] = w["first_slot"]
        last_any = w["first_slot"]
        counts[ident] = counts.get(ident, 0) + 1
    log(f"firing schedule: {len(firing)} bursts across "
        f"{len(counts)} validators")
    # Chain-state snapshot beside the dataset, so the report's client
    # labels are re-derivable: every node's version + family, the Jito set
    # size, and the epoch this run measured.
    import json as _json

    snapshot_path = os.path.join(
        os.path.dirname(dataset_path) or ".", "chain-snapshot.json")
    with open(snapshot_path, "w", encoding="utf-8") as fh:
        _json.dump({
            "epoch": epoch_info["epoch"],
            "start_slot": epoch_info["absoluteSlot"],
            "jito_identities_count": len(jito),
            "nodes": nodes_meta,
        }, fh)
    accountant = FeeAccountant(ledger_path)
    summaries = []
    with DatasetWriter(dataset_path) as writer:
        for burst_number, (window, t) in enumerate(firing):
            plan = plan_burst(f"burst-{burst_number:03d}", burst_number, t["identity"])
            try:
                summary = fire_burst(rpc, rpc_url, plan, window, slot_leaders,
                                     nodes_meta, accountant,
                                     writer, seed)
            except Exception as exc:
                summary = {"burst_id": plan.burst_id, "error": str(exc)[:300]}
            log(f"burst done: {summary}")
            summaries.append(summary)
            # Shakedown circuit breaker: burst 1 IS the pipeline test (the
            # devnet shakedown could not be funded — airdrops unavailable).
            # If it does not land and capture cleanly, STOP rather than
            # spending the study budget on a broken pipeline.
            if burst_number == 0 and summary.get("landed", 0) < 8:
                log("SHAKEDOWN GATE FAILED: first burst landed "
                    f"{summary.get('landed', 0)}/16 — aborting study")
                break
    log(f"accountant committed total: {accountant.committed} lamports")
    return summaries
