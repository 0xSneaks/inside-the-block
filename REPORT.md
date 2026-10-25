# Inside the Block — how Solana validators order transactions

**Study status:** complete. Results section is filled from
`data/live-dataset.jsonl` by `python3 -m harness analyze` when the run
completes. Everything above the Results heading is final text.

## Question

When transactions from one sender arrive in a leader's window in a known
send order with known priority fees, in what order do they land in the
block? Four pre-registered hypotheses (DESIGN.md): arrival order (H1),
priority-fee order (H2), a client-specific rule (H3), or no stable rule
(H0 — an explicitly acceptable conclusion).

## Method (as executed)

- **Bursts.** 16 self-transactions from one dedicated measurement wallet,
  sent back-to-back. Each carries a priority-fee tier assigned by a
  pre-registered pattern that decorrelates fee from send order
  (zero/low/mid/high rotating; pattern reversed on alternate bursts) and
  a unique marker (self-transfer amount = 10,000 + send index lamports;
  the sender's signature set is the primary identifier).
- **Fees are exact, not estimated.** Every transaction requests a
  200,000 CU limit; priority fee = ceil(limit × tier price), so each
  tier's total fee is known before sending: 5,000 / 17,500 / 55,000 /
  105,000 lamports. Study spend was hard-capped at 0.05 SOL in code (the
  fee accountant refuses any burst that would cross it) from a wallet
  funded with 0.058612973 SOL for this study only.
- **Send path.** Primary dataset: the public mainnet RPC endpoint
  (`api.mainnet-beta.solana.com`). An earlier run over Helius hit
  recurring preflight BlockhashNotFound rejections that dropped
  accepted sends; those losses could bias which transactions landed,
  so the Helius run is archived as pilot data
  (`data/pilot-helius-dataset.jsonl`) and is not part of the primary
  analysis. The public path completed 24 of 24 bursts with zero send
  errors and 16/16 landings in every burst.
  Transactions are pre-signed, then fired concurrently at the target
  leader window; each blockhash is proven with `isBlockhashValid`
  immediately before firing.
- **Attribution.** A transaction's validator is the leader of the slot it
  actually landed in (per DESIGN.md), from `getSlotLeaders`, and its
  client family/version from `getClusterNodes` joined with Jito's
  published validator set (method in `harness/leaders.py`). The raw
  dataset (every signature + slot) is published with this report; every
  claim is re-derivable with `getBlock`.
- **Analysis.** Pre-registered: Spearman rank correlation of landed order
  vs send order and vs fee tier per (burst, landed leader); a validator
  is fee- or arrival-ordered only if the pattern holds across all of its
  bursts with |rho| ≥ 0.7; families aggregate identified validators only.
  Sign convention: fee tiers rank zero < low < mid < high, so a
  **negative rho_fee means higher fee landed earlier** (fee-ordered);
  rho_send is positive when landed order follows send order.

## Environment findings that changed the tooling (all 2026-10-24)

1. **Alpenglow is live** (activated 2026-10-21, slot 459,653,000). The
   legacy `getLeaderSchedule` RPC returns an empty schedule for every
   epoch on both providers tested (Helius and public). Targeting and
   attribution were rebuilt on `getSlotLeaders`, which works for past
   and future slots.
2. **Blocks now contain version-1 transactions**; `getBlock` needs
   `maxSupportedTransactionVersion: 1` or it errors on current blocks.
3. **Landing lag.** Transactions accepted by the RPC landed on-chain
   109–125 slots (~45 s) after the target window in the shakedown burst,
   clustered in a few slots under different leaders. Consequences, all
   disclosed in the analysis: capture is by signature status (exact
   landed slot), not block scan; attribution is per landed slot; a fired
   burst can fragment across leaders.
4. **Devnet could not be funded for the shakedown** (Helius devnet
   airdrop returns HTTP 500; the public faucet rate-limits persistently),
   so the first mainnet burst doubled as the pipeline shakedown, behind
   a circuit breaker that aborts the study if it lands < 8/16.

## Methodology amendments (disclosed, applied uniformly)

- **Fragment floor.** A (burst, leader) fragment with fewer than 8
  landed transactions is counted in the dataset but excluded from
  verdicts: it is spill between leaders, not a burst. The design assumed
  in-window landing; the floor follows from the design's own
  landed-slot attribution rule.
- **Burst numbering/timing.** Bursts were fired in one session on
  2026-10-24 rather than spread across Oct 24 – Nov 3 as first planned;
  per-validator bursts are still separated by ≥ 1,500 slots and no two
  bursts are adjacent in time. "Different times of day" is the one
  design control this compresses; congestion context (block fullness)
  is recorded per record so the analysis can flag it.

## What went wrong (so far)

- Shakedown burst 1: all 16 sends rejected in preflight
  (`BlockhashNotFound`, 'processed' blockhash) — zero landed, zero fees.
- Shakedown burst 2: 5 sends rejected the same way; 11 accepted and
  landed ~110 slots late, outside the block-scan capture range, and
  were initially recorded as not landed. The dataset records for that
  burst were repaired from chain state (signature statuses + blocks)
  and match the on-chain fee total exactly (430,000 lamports).
- One test-run artifact: the fee ledger's committed total is a
  conservative upper bound (planned fees for accepted bursts); the
  report's spend figures come from on-chain state.

## Results

**Headline: H0 — no stable ordering rule.** Across 400 measured
transactions (24 aimed bursts of 16 plus a 16-transaction probe) and
22 validators with qualifying groups, no validator with repeated
qualifying bursts ordered its block by priority fee or by send order
consistently. Per-validator verdicts under the pre-registered rule
(all qualifying bursts must agree, |rho| ≥ 0.7):

- **no-pattern: 19 of 22 validators** — jito-solana 11, firedancer 7,
  agave 1.
- **mixed: 1** (jito-solana; one fee-ordered burst, one no-pattern).
- **fee-ordered: 1** and **arrival-ordered: 1** — both jito-solana,
  both from a single qualifying burst each. Neither meets the
  pre-registered rule beyond its single burst, so neither is a
  validator-level rule.
- **Pooled check (exploratory, not pre-registered).** Averaging the
  per-group correlations across all 26 qualifying groups (weighted by
  group size) gives rho_fee = −0.140 (19 of 26 groups negative) and
  rho_send = +0.095. A permutation test — landed positions shuffled
  within each (burst, leader) group, preserving group structure;
  2,000 runs, seed 42 — puts the pooled rho_fee at p ≈ 0.007
  one-sided. So in aggregate there is a weak tendency for higher
  fees to land earlier. It is far too weak and inconsistent to
  predict any individual validator's ordering, which is the claim
  H0 makes; H0 in this report is a validator-level claim only, not
  a claim that fees have zero average effect.
- The validators with the most evidence agree with the headline: the
  one agave validator with 3 qualifying bursts (5Us18hLZ…) scored
  no-pattern in all three; the two-burst jito-solana validators scored
  no-pattern/no-pattern and fee/none (mixed).
- **The two "ordered" verdicts are two halves of one burst.**
  burst-021 split 8/8 across two leaders: one half scored
  arrival-ordered (HEL1USMZ…, rho_send 0.76), the other fee-ordered
  (9iFPQbP1…, rho_fee −0.78). The same 16 transactions, with the same
  send order and fee structure, produced opposite "rules" on two
  leaders — which undercuts reading either half's label as that
  leader's policy, and is consistent with jitter. It does not by
  itself prove a mechanism.
- **Sensitivity to the fragment floor.** The verdicts above use the
  disclosed n ≥ 8 floor. Re-running the analysis at floor n ≥ 4 gives
  24 validators, 20 no-pattern (83%) — a similar share, offered as
  descriptive robustness only. Undefined correlations: Spearman rho
  is undefined for n < 3 or a constant fee tier, and the code records
  0.0 in those cases. At floors n ≥ 8 and n ≥ 4 there are ZERO such
  groups (0 of 26 and 0 of 28), so no verdict or sensitivity figure
  above rests on an undefined value. Below floor 4 such groups exist
  (6 of 36 groups at floor n ≥ 1); no floor-1 figures are used
  anywhere in this report.
- **Scope.** H0 is a block-level claim: no rule predicts the final
  in-block order of a burst. It does not rule out ordering inside a
  leader's parallel execution threads whose outputs interleave; such
  thread-level rules, if they exist, are invisible in block data for
  bursts of this size.

Family rollup: jito-solana 14 validators (1 fee, 1 arrival, 1 mixed,
11 none), firedancer 7 (all none), agave 1 (none, 3 bursts).
Coverage exceeds the design minimums: 22 validators (≥6 required),
3 client families (≥3 required).

**Money.** Actual on-chain spend: 29,635,000 lamports
(0.029635 SOL), measured as the funding balance minus the final
wallet balance (58,612,973 → 28,977,973 lamports). The fee
accountant's committed total, 31,390,000 lamports, is the planned-fee
upper bound and stayed under the 0.05 SOL hard cap at all times; the
actual spend came in below it, as designed.

## Reproduce

```
docker compose run --rm harness        # tests + simulated pipeline
python3 -m harness analyze data/live-dataset.jsonl
```
