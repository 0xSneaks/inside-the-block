"""Pre-registered analysis (DESIGN.md). The rules here are fixed before any
live data exists, so the report cannot cherry-pick:

- Per burst: Spearman rank correlation of landed order vs send order, and
  vs fee tier.
- A validator counts as fee-ordered or arrival-ordered only if the pattern
  holds across ALL of its bursts (|rho| >= 0.7, same winner each burst).
  Anything mixed is reported mixed.
- Aggregation by client family uses identified validators only.
- Weak or inconsistent correlations => H0 (noise) with statistics shown.
"""

from __future__ import annotations

from . import config

TIER_RANK = {name: i for i, name in enumerate(["zero", "low", "mid", "high"])}
RHO_THRESHOLD = 0.7


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 3:
        raise ValueError("spearman needs >= 3 paired values")
    rx, ry = _ranks(xs), _ranks(ys)
    n = len(xs)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den_x = sum((a - mx) ** 2 for a in rx)
    den_y = sum((b - my) ** 2 for b in ry)
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y) ** 0.5


def burst_correlations(rows: list[dict]) -> dict:
    """rows: landed records from ONE burst."""
    landed = [r for r in rows if r.get("landed")]
    landed.sort(key=lambda r: r["landed_position"])
    send_order = [r["send_index"] for r in landed]
    fee_order = [TIER_RANK[r["fee_tier"]] for r in landed]
    position = list(range(len(landed)))
    return {
        "n": len(landed),
        "rho_send": spearman(position, send_order) if len(landed) >= 3 else 0.0,
        # negative rho_fee = higher fee landed earlier = fee-ordered
        "rho_fee": spearman(position, fee_order) if len(landed) >= 3 else 0.0,
    }


def _burst_winner(corr: dict) -> str:
    send_strength = abs(corr["rho_send"])
    fee_strength = abs(corr["rho_fee"])
    if fee_strength >= RHO_THRESHOLD and corr["rho_fee"] < 0 and fee_strength >= send_strength:
        return "fee"
    if send_strength >= RHO_THRESHOLD and send_strength > fee_strength:
        return "arrival"
    return "none"


def validator_verdict(burst_corrs: list[dict]) -> dict:
    """Apply the all-bursts rule for one validator."""
    winners = [_burst_winner(c) for c in burst_corrs]
    if winners and all(w == "fee" for w in winners):
        verdict = "fee-ordered"
    elif winners and all(w == "arrival" for w in winners):
        verdict = "arrival-ordered"
    elif winners and all(w == "none" for w in winners):
        verdict = "no-pattern"
    else:
        verdict = "mixed"
    return {"verdict": verdict, "burst_winners": winners, "bursts": burst_corrs}


def analyze_dataset(rows: list[dict]) -> dict:
    """Full pre-registered analysis over a dataset (list of records)."""
    # A fired burst can split across two leaders' windows; DESIGN.md takes
    # validator identity from the block data itself, so records are grouped
    # by (burst, landed leader) — a split burst contributes one sub-burst
    # per leader it actually landed under.
    bursts: dict[tuple, list[dict]] = {}
    meta: dict[tuple, dict] = {}
    for r in rows:
        key = (r["burst_id"], r.get("validator_identity"))
        bursts.setdefault(key, []).append(r)
        meta[key] = {
            "validator": r.get("validator_identity"),
            "family": r.get("client_family"),
        }
    per_validator: dict[str, list[dict]] = {}
    for key, brows in bursts.items():
        v = meta[key]["validator"] or "UNKNOWN_VALIDATOR"
        per_validator.setdefault(v, []).append(burst_correlations(brows))
    validators = {}
    for v, corrs in per_validator.items():
        fam = next(
            (meta[b]["family"] for b in meta if meta[b]["validator"] == v),
            "UNKNOWN",
        )
        validators[v] = {"family": fam, **validator_verdict(corrs)}
    # Family aggregation: identified validators only.
    families: dict[str, list[str]] = {}
    for v, res in validators.items():
        if res["family"] and res["family"] != "UNKNOWN":
            families.setdefault(res["family"], []).append(res["verdict"])
    family_summary = {
        fam: {
            "validators": len(verds),
            "fee-ordered": verds.count("fee-ordered"),
            "arrival-ordered": verds.count("arrival-ordered"),
            "mixed": verds.count("mixed"),
            "no-pattern": verds.count("no-pattern"),
        }
        for fam, verds in families.items()
    }
    return {"validators": validators, "families": family_summary}
