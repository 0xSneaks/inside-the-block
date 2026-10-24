"""Raw dataset recording (JSON Lines).

One record per burst transaction, exactly the fields DESIGN.md requires so
that every claim in the final report is re-derivable by a judge with
getBlock: send index, fee tier, signature, target leader window, landed
slot, landed position within block, block fullness signal, burst id,
timestamp.
"""

from __future__ import annotations

import json
import os

FIELDS = [
    "burst_id",
    "validator_identity",
    "client_family",
    "send_index",
    "fee_tier",
    "marker_amount",
    "signature",
    "target_first_slot",
    "target_last_slot",
    "landed_slot",
    "landed_position",
    "block_tx_count",
    "sent_at_unix",
    "landed",
    "simulated",
]


class DatasetWriter:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._fh = open(path, "a", encoding="utf-8")

    def write(self, record: dict) -> None:
        row = {k: record.get(k) for k in FIELDS}
        self._fh.write(json.dumps(row) + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def read_dataset(path: str) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows
