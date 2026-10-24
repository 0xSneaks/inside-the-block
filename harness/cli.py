"""Command-line entry point.

    python3 -m harness plan                 # burst plan + fee quote vs cap
    python3 -m harness dry-run --rule fee   # full simulated pipeline
    python3 -m harness analyze data/x.jsonl # pre-registered analysis
    python3 -m harness send --live ...      # gated live path (see sender.py)

Dry-run is the default posture everywhere; there is no mode in which this
CLI sends anything without --live AND the live-phase environment gate.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import analyze as analyze_mod
from . import burst as burst_mod
from . import capture, config, sender
from .dataset import DatasetWriter, read_dataset
from .fees import FeeAccountant

DEMO_VALIDATORS = [
    ("DemoValidatorA1111111111111111111111111111", "jito-solana"),
    ("DemoValidatorB2222222222222222222222222222", "firedancer"),
    ("DemoValidatorC3333333333333333333333333333", "UNKNOWN"),
    ("DemoValidatorD4444444444444444444444444444", "jito-solana"),
    ("DemoValidatorE5555555555555555555555555555", "UNKNOWN"),
    ("DemoValidatorF6666666666666666666666666666", "firedancer"),
]


def cmd_plan(_args) -> int:
    plan = burst_mod.plan_burst("quote", 0)
    from .fees import burst_fee_lamports

    per_burst = burst_fee_lamports(plan.tiers)
    total_bursts = config.MIN_VALIDATORS * config.BURSTS_PER_VALIDATOR
    print(f"burst size: {config.BURST_SIZE} tx")
    print(f"tiers per burst: {plan.tiers}")
    print(f"fee per burst: {per_burst} lamports ({per_burst / 1e9:.6f} SOL)")
    print(f"planned bursts: {total_bursts} "
          f"({config.MIN_VALIDATORS} validators x {config.BURSTS_PER_VALIDATOR})")
    print(f"planned total: {per_burst * total_bursts} lamports "
          f"({per_burst * total_bursts / 1e9:.6f} SOL)")
    print(f"hard cap: {config.CAP_LAMPORTS} lamports ({config.CAP_LAMPORTS / 1e9:.2f} SOL)")
    worst = sum(
        config.BASE_FEE_LAMPORTS + 100_000 for _ in plan.txs
    ) * total_bursts
    print(f"worst case (all tx at top tier): {worst} lamports ({worst / 1e9:.6f} SOL)")
    return 0


def cmd_dry_run(args) -> int:
    os.makedirs("data", exist_ok=True)
    ledger = os.path.join("data", "fee-ledger-dryrun.json")
    if os.path.exists(ledger):
        os.remove(ledger)
    accountant = FeeAccountant(ledger)
    source = capture.SimulatedBlockSource(rule=args.rule, seed=args.seed)
    out_path = os.path.join("data", f"dryrun-{args.rule}.jsonl")
    if os.path.exists(out_path):
        os.remove(out_path)
    slot = 300_000_000
    burst_number = 0
    with DatasetWriter(out_path) as ds:
        for identity, family in DEMO_VALIDATORS:
            for b in range(config.BURSTS_PER_VALIDATOR):
                burst_id = f"burst-{burst_number:03d}"
                plan = burst_mod.plan_burst(burst_id, burst_number, identity)
                sent = sender.simulate_burst(plan, accountant)
                sigs = [s["signature"] for s in sent]
                source.register_burst(slot, sigs, plan.tiers, analyze_mod.TIER_RANK)
                block = source.get_block(slot)
                found = capture.locate_in_block(block, sigs)
                for s in sent:
                    loc = found.get(s["signature"], {})
                    ds.write(
                        {
                            "burst_id": burst_id,
                            "validator_identity": identity,
                            "client_family": family,
                            "send_index": s["send_index"],
                            "fee_tier": s["fee_tier"],
                            "marker_amount": s["marker_amount"],
                            "signature": s["signature"],
                            "target_first_slot": slot,
                            "target_last_slot": slot + 3,
                            "landed_slot": slot if s["signature"] in found else None,
                            "landed_position": loc.get("landed_position"),
                            "block_tx_count": loc.get("block_tx_count"),
                            "sent_at_unix": s["sent_at_unix"],
                            "landed": s["signature"] in found,
                            "simulated": True,
                        }
                    )
                burst_number += 1
                slot += 4
    rows = read_dataset(out_path)
    result = analyze_mod.analyze_dataset(rows)
    print(f"dataset: {out_path} ({len(rows)} records, simulated)")
    print(json.dumps(result, indent=2))
    return 0


def cmd_analyze(args) -> int:
    rows = read_dataset(args.dataset)
    print(json.dumps(analyze_mod.analyze_dataset(rows), indent=2))
    return 0


def cmd_live_study(args) -> int:
    if not args.live:
        print("live-study requires --live (dry-run is the default posture)",
              file=sys.stderr)
        return 2
    rpc_url = os.environ.get("HARNESS_RPC_URL")
    if not rpc_url:
        print("HARNESS_RPC_URL is not set", file=sys.stderr)
        return 2
    from .live import run_study

    os.makedirs("data", exist_ok=True)
    summaries = run_study(
        rpc_url,
        os.path.join("data", "live-dataset.jsonl"),
        os.path.join("data", "fee-ledger.json"),
    )
    print(json.dumps(summaries, indent=2))
    return 0


def cmd_send(args) -> int:
    if not args.live:
        print("send requires --live (dry-run is the default posture)", file=sys.stderr)
        return 2
    from .rpc import Rpc

    accountant = FeeAccountant(os.path.join("data", "fee-ledger.json"))
    plan = burst_mod.plan_burst(args.burst_id, args.burst_number, args.validator)
    rpc = Rpc(config.RPC_URL)
    sent = sender.send_burst_live(plan, accountant, rpc)
    print(json.dumps(sent, indent=2))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="harness")
    sub = p.add_subparsers(required=True)
    sub.add_parser("plan").set_defaults(fn=cmd_plan)
    d = sub.add_parser("dry-run")
    d.add_argument("--rule", choices=["arrival", "fee", "random"], default="random")
    d.add_argument("--seed", type=int, default=42)
    d.set_defaults(fn=cmd_dry_run)
    a = sub.add_parser("analyze")
    a.add_argument("dataset")
    a.set_defaults(fn=cmd_analyze)
    ls = sub.add_parser("live-study")
    ls.add_argument("--live", action="store_true")
    ls.set_defaults(fn=cmd_live_study)
    s = sub.add_parser("send")
    s.add_argument("--live", action="store_true")
    s.add_argument("--validator", required=True)
    s.add_argument("--burst-id", required=True)
    s.add_argument("--burst-number", type=int, required=True)
    s.set_defaults(fn=cmd_send)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
