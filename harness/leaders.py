"""Leader schedule lookup and validator / client identification.

Identification rules (DESIGN.md): the validator for a burst is the node
identity that held the leader slot our transactions landed in, taken from
the leader schedule cross-checked against produced blocks. Client family is
best-available-signal only: version/gossip strings that explicitly name a
fork identify it; anything else is UNKNOWN, which is an allowed value. H3
(client-specific rules) may only be claimed for identified validators.
"""

from __future__ import annotations

from .rpc import Rpc

FAMILY_AGAVE = "agave"
FAMILY_JITO = "jito-solana"
FAMILY_FIREDANCER = "firedancer"
FAMILY_UNKNOWN = "UNKNOWN"


def classify_client(version: str | None, feature_set: int | None = None) -> str:
    """Best-effort client family from a cluster node's version string.

    Conservative by design: plain semver versions do NOT identify a family,
    because Agave and its forks share version shapes. Only explicit markers
    name a family."""
    if not version:
        return FAMILY_UNKNOWN
    v = version.lower()
    if "firedancer" in v or "frankendancer" in v:
        return FAMILY_FIREDANCER
    if "jito" in v:
        return FAMILY_JITO
    return FAMILY_UNKNOWN


def epoch_start_slot(epoch_info: dict) -> int:
    return epoch_info["absoluteSlot"] - epoch_info["slotIndex"]


def leader_at_slot(schedule: dict, epoch_info: dict, slot: int) -> str | None:
    """schedule maps identity -> relative slot indices within the epoch."""
    rel = slot - epoch_start_slot(epoch_info)
    for identity, slots in schedule.items():
        if rel in slots:
            return identity
    return None


def upcoming_windows(rpc: Rpc, horizon_slots: int = 2000) -> list[dict]:
    """Leader windows (runs of consecutive slots per identity) starting
    between the current slot and current + horizon_slots."""
    info = rpc.get_epoch_info()
    schedule = rpc.get_leader_schedule(info["epoch"])
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


def node_versions(rpc: Rpc) -> dict[str, dict]:
    """identity pubkey -> {version, family} from getClusterNodes."""
    out = {}
    for node in rpc.get_cluster_nodes():
        version = node.get("version")
        out[node["pubkey"]] = {
            "version": version,
            "family": classify_client(version, node.get("featureSet")),
        }
    return out
