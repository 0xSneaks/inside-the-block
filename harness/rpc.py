"""Minimal Solana JSON-RPC client (stdlib only).

The VM this harness was built on routes HTTPS through an egress proxy that
urllib does not pick up reliably, so the proxy is wired explicitly from the
environment. On a normal machine with no proxy env, this is a plain direct
client.
"""

from __future__ import annotations

import json
import os
import urllib.request


class RpcError(Exception):
    pass


class Rpc:
    def __init__(self, url: str):
        self.url = url
        handlers = []
        proxy = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")
        if proxy:
            handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        self._opener = urllib.request.build_opener(*handlers)
        self._id = 0

    def call(self, method: str, params: list | None = None):
        import time
        import urllib.error

        last_exc = None
        for attempt in range(4):
            self._id += 1
            body = json.dumps(
                {"jsonrpc": "2.0", "id": self._id, "method": method,
                 "params": params or []}
            ).encode()
            req = urllib.request.Request(
                self.url,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "inside-the-block-harness/0.1",
                },
            )
            try:
                with self._opener.open(req, timeout=30) as resp:
                    payload = json.loads(resp.read().decode())
            except urllib.error.HTTPError as exc:
                # 429 = the request was rejected before processing, so a
                # retry cannot double-send. Back off and retry.
                if exc.code == 429 and attempt < 3:
                    last_exc = exc
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise
            if "error" in payload:
                raise RpcError(f"{method}: {payload['error']}")
            return payload["result"]
        raise last_exc  # pragma: no cover

    # --- study-specific helpers -------------------------------------------------
    def get_epoch_info(self) -> dict:
        return self.call("getEpochInfo")

    def get_leader_schedule(self, epoch: int) -> dict:
        """identity pubkey -> list of slot indices RELATIVE to epoch start."""
        result = self.call("getLeaderSchedule", [epoch, {"identity": None, "commitment": "finalized"}])
        return result or {}

    def get_cluster_nodes(self) -> list[dict]:
        return self.call("getClusterNodes")

    def get_latest_blockhash(self) -> str:
        return self.call("getLatestBlockhash", [{"commitment": "finalized"}])["value"]["blockhash"]

    def get_block(self, slot: int) -> dict | None:
        return self.call(
            "getBlock",
            [
                slot,
                {
                    "encoding": "json",
                    "transactionDetails": "full",
                    "rewards": False,
                    "maxSupportedTransactionVersion": 1,
                },
            ],
        )

    def send_transaction(self, raw_tx_b64: str) -> str:
        return self.call(
            "sendTransaction",
            [raw_tx_b64, {"encoding": "base64", "skipPreflight": False}],
        )
