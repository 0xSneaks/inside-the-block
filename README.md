# Inside the Block — how Solana validators order transactions

A mainnet measurement study built for the Superteam Ukraine bounty
"Inside the Block" (2,500 USDC pool, deadline 2026-11-05 21:59 UTC).

**Question:** when transactions from one sender arrive in a leader's window
in a known send order with known priority fees, in what order do they land
in the block — arrival order, priority-fee order, a client-specific rule,
or no stable rule at all? A supported "it's noise" result is a valid
outcome of this study.

The experiment design — hypotheses, burst structure, controls, sample
sizes, and the pre-registered analysis rules — is in [DESIGN.md](DESIGN.md).
It was fixed before any live data existed.

## Status

Phase 1 skeleton (2026-10-24). The full pipeline runs end-to-end in
dry-run simulation. **Nothing has been sent on mainnet.** Live sending is
behind three gates (see `harness/sender.py`) and only opens after the
project checkpoint that precedes the live measurement phase.

## Reproduce (one command)

```
docker compose run --rm harness
```

This runs the test suite and a simulated dry-run of the whole pipeline
(plan → burst → block capture → dataset → analysis) with no network and
no keys. Without Docker:

```
python3 -m unittest discover -s tests -t .
python3 -m harness plan
python3 -m harness dry-run --rule fee     # simulated fee-ordered world
python3 -m harness dry-run --rule random  # simulated H0 (noise) world
python3 -m harness analyze data/dryrun-fee.jsonl
```

Pure Python 3 standard library — no dependencies to install.

## Layout

- `harness/config.py` — study constants: burst shape, fee tiers, hard cap
- `harness/fees.py` — fee accountant; refuses any burst that would push
  cumulative spend over the 0.05 SOL hard cap (a hard stop, not a warning)
- `harness/burst.py` — burst planning; fee tiers decorrelated from send
  order, pattern reversed on alternate bursts
- `harness/txbuild.py` + `harness/ed25519.py` — offline Solana transaction
  construction and signing (RFC 8032 test-vector verified)
- `harness/leaders.py` — leader schedule lookup; validator and client
  identification (UNKNOWN is an allowed client value, never guessed)
- `harness/capture.py` — landed-order capture from produced blocks
- `harness/dataset.py` — raw dataset (JSONL): every signature + slot, so
  each claim is re-derivable with `getBlock`
- `harness/analyze.py` — the pre-registered analysis from DESIGN.md
- `harness/sender.py` — simulated sender (default) and the gated live path

## Hard rules

- Study spend is capped at **0.05 SOL cumulative**, enforced in code,
  from the dedicated measurement wallet only. Burst transactions are
  self-transfers; only fees are spent.
- Dry-run is the default everywhere. Live mode requires `--live`, the
  `INSIDE_BLOCK_LIVE_OK=1` environment gate, and fee-accountant approval.
- The raw dataset is published with the results: every transaction
  signature and slot.
