# Inside the Block — Phase 1 experiment design (draft, prepared 2026-10-24)

Status: design pre-registered 2026-10-24, before any code or data. The
harness skeleton implementing this design was built the same day (dry-run
only; no transactions, no mainnet sends). The design below is unchanged
from its pre-registration. All spend stays behind the existing gates
(checkpoint Oct 30–31, live phase Nov 1–3, submission only with the
operator's approval).

Deadline: 2026-11-05 21:59 UTC. Budget hard cap: 0.05 SOL cumulative from the
dedicated measurement wallet only; the 0.008612973 SOL excess above the funded
amount is never touched.

## Question

When transactions from one sender arrive in a leader's window in a known send
order with known priority fees, in what order do they land in the block?

## Hypotheses (exactly one family should win per validator, or none)

- H1 Arrival order: landed order tracks send order regardless of priority fee.
- H2 Priority-fee order: landed order tracks priority fee (descending),
  regardless of send order.
- H3 Client-specific rule: the winning pattern differs systematically by
  client/fork family (Agave / Jito-Solana / Firedancer-family, as identifiable
  at measurement time).
- H0 Noise: no stable rule — landed order is not reproducibly explained by
  send order or fee. The listing explicitly accepts this as a valid,
  supported conclusion.

## Burst design (the unit of evidence)

- One burst = 16 self-transactions sent back-to-back from the measurement
  wallet into a single leader window (one validator's slot run), each with:
  - a known send index (0–15),
  - a priority-fee tier assigned by a pre-registered pattern that decorrelates
    fee from send order (e.g. tiers rotate 0 / low / high / mid across send
    positions, pattern reversed on alternate bursts),
  - a unique marker so every landed tx is identifiable in the block
    (exact marker mechanism is a Phase 2 shakedown decision — candidate:
    distinct tiny self-transfer amounts; do NOT lock this in design).
- Per validator: 3 bursts minimum, at different times of day, to separate a
  validator rule from a one-off congestion event.
- Validators: at least 6, spanning at least 3 client/fork families as
  identifiable at measurement time (identification method below; if a family
  cannot be identified reliably, the report says so rather than guessing).

## Sample size and fee arithmetic (checked 2026-10-24)

- Planned primary sample: 6 validators × 3 bursts × 16 tx = 288 transactions.
- Base fee at 5,000 lamports/signature: 288 × 0.000005 = 0.00144 SOL.
- Blended cost if priority fees average 40,000 lamports/tx (tiers spread
  0–100,000): 288 × 0.000045 ≈ 0.01296 SOL total — under one third of the cap.
- Worst case in design (every tx at the 100,000-lamport tier):
  288 × 0.000105 = 0.03024 SOL — still under the 0.05 SOL cap, leaving
  headroom for the aborted/retried bursts the report must disclose.
- The harness fee accountant refuses (hard stop, not a warning) before any
  send that would push cumulative spend over 0.05 SOL.

## Controls

- Self-interaction: all burst txs come from one wallet, so nonce/account
  ordering effects are part of the design, not a hidden variable; the design
  doc for the submission must state this explicitly and the analysis must
  test send-index correlation before claiming a fee effect.
- Competing traffic: record slot, block time, and how full each landed block
  is; bursts landing in unusually congested blocks are flagged in the dataset,
  not silently dropped.
- Send path: one RPC path for all sends in a burst, named in the report;
  no mid-study path changes (tx path is one of the listing's named
  accounting points).
- Reversal: alternating the fee-tier pattern between bursts controls for
  position effects (early-send advantage independent of fee).

## Leader / validator / client identification

- Leader windows from the leader schedule for the relevant epoch
  (RPC leader-schedule lookup), cross-checked against the blocks actually
  produced for those slots.
- Validator identity = the vote account / node identity that held the leader
  slot for the slots our txs landed in, taken from the block data itself.
- Client family = best available signal at measurement time (cluster-node
  version / gossip data where exposed). This is the weakest identification
  leg: Jito-Solana and Firedancer-family are not always distinguishable from
  public data. UNKNOWN is an allowed value per validator; H3 is only claimed
  for validators whose family is actually identified.

## Data captured per transaction

send index, fee tier, signature, target leader window, landed slot,
landed position within block, block fullness signal, burst id, timestamp.
Raw dataset (every signature + slot) is published with the submission so a
judge can re-derive every claim with getBlock — that is 25% of the score
(Verifiability & Reproducibility) and the design treats it as non-optional.

## Analysis plan (pre-registered, so the report cannot cherry-pick)

- Per validator: rank correlation of landed order vs send order, and vs
  fee tier; report both, with the burst count behind each number.
- A validator counts as "fee-ordered" or "arrival-ordered" only if the
  pattern holds across all 3 of its bursts; anything mixed is reported mixed.
- Aggregate by client family only for identified validators.
- Null result is a submission, not a failure: if correlations are weak or
  inconsistent, the report's conclusion is H0 with the statistics shown.

## Open items for Phase 2 (devnet shakedown, Oct 27–29)

1. Marker mechanism for identifying our txs in a block (test on devnet).
2. Whether 16 tx can reliably be sent inside one leader window from our
   connection; if not, burst size drops and burst count rises within the
   same fee envelope (arithmetic above has the headroom).
3. Client-family identification reliability test against known validators.
4. Fee-cap hard-stop test: deliberately attempt to exceed 0.05 SOL on
   devnet and verify the harness refuses.

## What this design does NOT do

- No live sends, no code, no repo, no submission — those stay on the plan's
  existing gates and Sneaks's word.
- It does not resolve the listing's HUMAN_ONLY agentAccess question
  (UNVERIFIED in the slate); submission is as the Halfmoon Studio profile,
  and that question is part of the Oct 30–31 checkpoint.
