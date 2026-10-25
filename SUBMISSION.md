# Superteam Earn submission — "Inside the Block" (DRAFT, awaiting Sneaks's approval)

**Submitted by:** Halfmoon Studio (@gethalfmoon)
**Payout address (Solana):** 2RCiezWiYHMULwXdn1MCxs82SDRWLK8QxQVAUGMFAXvJ
**Public repo:** https://github.com/0xSneaks/inside-the-block
**Deadline:** 2026-11-05 21:59 UTC

---

## Entry text (paste-ready)

**Title:** Inside the Block: 400 self-transactions across 22 validators — no stable ordering rule found

**Summary.**
We measured how Solana validators order transactions inside a block
using only our own transactions as evidence. From a dedicated wallet
we fired 25 bursts of 16 self-transfers (400 transactions, all
landed, slots 460,988,576–461,028,101), with priority-fee tiers
deliberately decorrelated from send order and the pattern reversed on
alternate bursts, timed to land in targeted leader windows across 22
validators and 3 client families (jito-solana, firedancer, agave).
Each transaction's position inside its block was then compared
against its send order and its fee tier (Spearman correlation per
burst, pre-registered threshold |rho| ≥ 0.7, verdict requires all of
a validator's qualifying bursts to agree).

**Result: no stable ordering rule (H0).** 19 of 22 validators showed
no pattern; 1 was mixed; the 2 single-burst "ordered" results are
the two halves of one burst that split across two leaders, and meet
no all-bursts rule. The validators with the most bursts agree: the
3-burst agave validator was no-pattern in all three. One honest
qualification: pooled across all 26 groups, higher fees landed
slightly earlier on average (size-weighted rho_fee ≈ −0.14,
permutation p ≈ 0.007) — a weak aggregate tendency, far too
inconsistent to predict any individual validator's ordering. In
plain terms: for ordinary self-transfers at these fee levels,
neither arrival order nor priority fee reliably predicted in-block
position on any client family we measured.

**Verifiability.** The full raw dataset — every signature, slot,
block position, fee tier and send index — ships in the repo
(`data/live-dataset.jsonl`), with a one-command reproduction path
(Docker Compose: tests + simulated pipeline + the exact analysis
that produced the numbers above). The design was pre-registered in
DESIGN.md before the first live transaction; every deviation
encountered (Alpenglow timing, empty leader schedules, RPC send-path
failures, the fragment floor) is documented in REPORT.md with its
evidence. Total on-chain spend: 0.029635 SOL against a hard-capped
0.05 SOL budget, enforced in code.

---

## Pre-submission checklist (Muse, before Sneaks approves)

- [x] Sneaks approves this entry text
- [x] Sneaks approves creating the PUBLIC GitHub repo from this local repo
      (contents: harness/, tests/, DESIGN.md, README.md, REPORT.md,
      data/live-dataset.jsonl + pilot archive; NO keys, NO logs with secrets)
- [ ] Confirm a Superteam submission credit is valid on submission day
      (3 credits issued ~2026-10-24, noted expiring ~2026-10-31 — UNVERIFIED;
      needs Sneaks's Halfmoon login to check)
- [ ] Paste repo URL into the entry above; submit from the Halfmoon
      Superteam account (Sneaks's action or his explicit go-ahead)
