"""Solana legacy transaction construction for burst self-transfers.

Each burst transaction is a self-transfer from the measurement wallet to
itself whose lamport amount encodes the send index (the marker candidate),
plus Compute Budget instructions that set the priority-fee tier:

  1. SetComputeUnitLimit(CU_LIMIT)
  2. SetComputeUnitPrice(tier price)   [omitted for the "zero" tier]
  3. System Transfer(amount = MARKER_BASE + send_index, to self)

Construction and signing are pure Python (harness.ed25519), so a transaction
can be built and verified fully offline. The live send path lives in
sender.py and stays gated; nothing here touches the network.
"""

from __future__ import annotations

import hashlib

from . import config, ed25519

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_IDX = {c: i for i, c in enumerate(_B58)}


def b58decode(s: str) -> bytes:
    n = 0
    for ch in s:
        n = n * 58 + _B58_IDX[ch]
    pad = len(s) - len(s.lstrip("1"))
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\x00" * pad + body


def b58encode(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = _B58[r] + out
    pad = len(data) - len(data.lstrip(b"\x00"))
    return "1" * pad + (out or "")


def _shortvec(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def marker_amount(send_index: int) -> int:
    if not 0 <= send_index < config.BURST_SIZE:
        raise ValueError("send_index out of range")
    return config.MARKER_BASE_LAMPORTS + send_index


def build_message(sender_pubkey: bytes, tier: str, send_index: int,
                  blockhash: bytes) -> bytes:
    """Compile a legacy message. Accounts (deduped, Solana ordering):
    0 sender (signer, writable); 1 Compute Budget (readonly);
    2 System Program (readonly). The recipient is the sender itself, so no
    additional account appears."""
    if len(sender_pubkey) != 32 or len(blockhash) != 32:
        raise ValueError("pubkey and blockhash must be 32 bytes")
    cb = b58decode(config.COMPUTE_BUDGET_PROGRAM)
    sysp = b58decode(config.SYSTEM_PROGRAM)
    accounts = [sender_pubkey, cb, sysp]
    header = bytes([1, 0, 2])  # 1 signer, 0 readonly signers, 2 readonly

    ixs = []
    # SetComputeUnitLimit: discriminator 2 + u32 LE
    ixs.append((1, [], bytes([2]) + config.CU_LIMIT.to_bytes(4, "little")))
    price = config.FEE_TIERS[tier]
    if price > 0:
        # SetComputeUnitPrice: discriminator 3 + u64 LE
        ixs.append((1, [], bytes([3]) + price.to_bytes(8, "little")))
    # System Transfer: discriminator 2 (u32) + u64 LE lamports; accounts from,to
    transfer_data = (2).to_bytes(4, "little") + marker_amount(send_index).to_bytes(8, "little")
    ixs.append((2, [0, 0], transfer_data))

    msg = bytearray()
    msg += header
    msg += _shortvec(len(accounts))
    for a in accounts:
        msg += a
    msg += blockhash
    msg += _shortvec(len(ixs))
    for prog_idx, acct_idxs, data in ixs:
        msg.append(prog_idx)
        msg += _shortvec(len(acct_idxs))
        msg += bytes(acct_idxs)
        msg += _shortvec(len(data))
        msg += data
    return bytes(msg)


def build_signed_tx(seed: bytes, tier: str, send_index: int,
                    blockhash: bytes) -> tuple[bytes, str]:
    """Return (raw transaction bytes, base58 signature). Fully offline."""
    pub = ed25519.publickey(seed)
    msg = build_message(pub, tier, send_index, blockhash)
    sig = ed25519.sign(seed, msg)
    tx = _shortvec(1) + sig + msg
    return tx, b58encode(sig)


def simulated_signature(burst_id: str, send_index: int) -> str:
    """Deterministic fake signature for dry runs (clearly derived, never a
    real on-chain signature)."""
    digest = hashlib.sha256(f"dryrun:{burst_id}:{send_index}".encode()).digest()
    return b58encode(digest + digest)
