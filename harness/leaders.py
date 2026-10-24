"""Leader schedule lookup and validator / client identification.

Identification rules (DESIGN.md): the validator for a burst is the node
identity that held the leader slot our transactions landed in, taken from
the leader schedule cross-checked against produced blocks. Client family
uses the Phase 2 method in classify_client: Jito's published validator
set, Firedancer's documented calendar version scheme, Agave's release
scheme for the remainder; UNKNOWN when no signal exists, which is an
allowed value. H3 (client-specific rules) may only be claimed for
identified validators.
"""

from __future__ import annotations

from .rpc import Rpc

FAMILY_AGAVE = "agave"
FAMILY_JITO = "jito-solana"
FAMILY_FIREDANCER = "firedancer"
FAMILY_UNKNOWN = "UNKNOWN"


def classify_client(version: str | None, in_jito_set: bool = False) -> str:
    """Client family from public signals, method fixed at Phase 2.
    Precedence is by client IMPLEMENTATION (the version scheme), with
    Jito-set membership applied to Agave-scheme versions:

    - version in Firedancer's calendar scheme vYY.MM.PATCH (26.x) ->
      firedancer, even when the node also runs Jito's BAM (the client is
      Firedancer-family; the Jito flag is kept in the chain snapshot).
      The scheme is documented in Firedancer's own getting-started guide.
    - version in the legacy Frankendancer scheme 0.<3+ digits>.<4+ digits>
      -> firedancer.
    - Agave-scheme version (N.N.N) AND identity in Jito's published
      validator set (kobe API, running_jito) -> jito-solana.
    - Agave-scheme version otherwise -> agave.
    - anything else (e.g. 0.1.1) or no version -> UNKNOWN (allowed;
      never guessed)."""
    import re

    if not version:
        return FAMILY_UNKNOWN
    v = version.strip()
    if re.match(r"^26\.\d+\.\d+$", v):
        return FAMILY_FIREDANCER
    if re.match(r"^0\.\d{3,}\.\d{4,}$", v):
        return FAMILY_FIREDANCER
    if re.match(r"^[1-9]\d*\.\d+\.\d+", v):
        return FAMILY_JITO if in_jito_set else FAMILY_AGAVE
    return FAMILY_UNKNOWN


def epoch_start_slot(epoch_info: dict) -> int:
    return epoch_info["absoluteSlot"] - epoch_info["slotIndex"]


def fetch_slot_leaders(rpc: Rpc, start_slot: int, count: int,
                       chunk: int = 5000) -> dict[int, str]:
    """slot -> leader identity for [start_slot, start_slot+count), via
    getSlotLeaders. NOTE (Phase 2 finding, 2026-10-24): the legacy
    getLeaderSchedule RPC returns an empty schedule for every epoch on
    both providers tested since the Alpenglow activation; getSlotLeaders
    is the working leader-schedule lookup."""
    out: dict[int, str] = {}
    done = 0
    while done < count:
        n = min(chunk, count - done)
        leaders = rpc.call("getSlotLeaders", [start_slot + done, n])
        if not leaders:
            break
        for i, identity in enumerate(leaders):
            out[start_slot + done + i] = identity
        done += len(leaders)
        if len(leaders) < n:
            break
    return out


def leader_at_slot(slot_leaders: dict[int, str], slot: int) -> str | None:
    return slot_leaders.get(slot)


def windows_from_leaders(slot_leaders: dict[int, str],
                         from_slot: int) -> list[dict]:
    """Runs of consecutive slots per identity at or after from_slot."""
    runs: list[dict] = []
    slots = sorted(s for s in slot_leaders if s >= from_slot)
    i = 0
    while i < len(slots):
        identity = slot_leaders[slots[i]]
        j = i
        while (j + 1 < len(slots) and slots[j + 1] == slots[j] + 1
               and slot_leaders[slots[j + 1]] == identity):
            j += 1
        runs.append({
            "identity": identity,
            "first_slot": slots[i],
            "last_slot": slots[j],
            "slots": slots[j] - slots[i] + 1,
        })
        i = j + 1
    return runs


def upcoming_windows(rpc: Rpc, horizon_slots: int = 2000,
                     epoch_info: dict | None = None,
                     schedule: dict | None = None) -> list[dict]:
    """Leader windows (runs of consecutive slots per identity) starting
    between the current slot and current + horizon_slots."""
    info = epoch_info or rpc.get_epoch_info()
    schedule = schedule if schedule is not None else rpc.get_leader_schedule(info["epoch"])
    start = epoch_start_slot(info)
    now_rel = info["slotIndex"]
    runs: list[dict] = []
    by_slot = {}
    for identity, slots in schedule.items():
        for rel in slots:
            by_slot[rel] = identity
    rel = now_rel
    end = now_rel + horizon_slots
    while rel < end:
        identity = by_slot.get(rel)
        if identity is None:
            rel += 1
            continue
        run_start = rel
        while rel < end and by_slot.get(rel) == identity:
            rel += 1
        runs.append(
            {
                "identity": identity,
                "first_slot": start + run_start,
                "last_slot": start + rel - 1,
                "slots": rel - run_start,
            }
        )
    return runs


def node_versions(rpc: Rpc, jito_identities: set[str] | None = None) -> dict[str, dict]:
    """identity pubkey -> {version, family} from getClusterNodes, with the
    Jito published set (identity pubkeys) applied when supplied."""
    jito_identities = jito_identities or set()
    out = {}
    for node in rpc.get_cluster_nodes():
        version = node.get("version")
        out[node["pubkey"]] = {
            "version": version,
            "family": classify_client(version, node["pubkey"] in jito_identities),
        }
    return out


def fetch_jito_identities(opener=None) -> set[str]:
    """Identity pubkeys of validators flagged running_jito in Jito's
    public kobe API validator list."""
    import json
    import urllib.request

    if opener is None:
        import os

        handlers = []
        proxy = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")
        if proxy:
            handlers.append(
                urllib.request.ProxyHandler({"http": proxy, "https": proxy})
            )
        opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(
        "https://kobe.mainnet.jito.network/api/v1/validators",
        headers={"User-Agent": "inside-the-block-harness/0.1"},
    )
    data = json.loads(opener.open(req, timeout=30).read().decode())
    vals = data.get("validators", data if isinstance(data, list) else [])
    return {
        v["identity_account"]
        for v in vals
        if v.get("running_jito") and v.get("identity_account")
    }
