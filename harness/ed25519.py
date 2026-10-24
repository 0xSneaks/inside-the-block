"""Minimal pure-Python Ed25519 (RFC 8032) signing and verification.

Dependency-free so the harness runs anywhere Python 3 does, including the
one-command Docker repro. Speed is irrelevant at this study's scale
(hundreds of signatures). Verified against the RFC 8032 test vectors in
tests/test_ed25519.py.
"""

from __future__ import annotations

import hashlib

_Q = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _Q - 2, _Q) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)
_BY = 46316835694926478169428394003475163141307993866256225615783033603165251855960


def _derive_base_x() -> int:
    """Bx from By: x = sqrt((y^2-1)/(d*y^2+1)); the base point's x is even
    (its canonical encoding 0x586666...66 has sign bit 0)."""
    yy = _BY * _BY % _Q
    x = pow((yy - 1) * pow(_D * yy + 1, _Q - 2, _Q), (_Q + 3) // 8, _Q)
    if (x * x - (yy - 1) * pow(_D * yy + 1, _Q - 2, _Q)) % _Q != 0:
        x = x * _I % _Q
    if x & 1:
        x = _Q - x
    return x


_B = (_derive_base_x(), _BY % _Q)


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _point_add(p, q):
    x1, y1 = p
    x2, y2 = q
    t = _D * x1 * x2 * y1 * y2 % _Q
    x3 = (x1 * y2 + x2 * y1) * pow(1 + t, _Q - 2, _Q) % _Q
    y3 = (y1 * y2 + x1 * x2) * pow(1 - t, _Q - 2, _Q) % _Q
    return x3, y3


def _point_mul(p, e: int):
    q = (0, 1)
    while e > 0:
        if e & 1:
            q = _point_add(q, p)
        p = _point_add(p, p)
        e >>= 1
    return q


def _encode_point(p) -> bytes:
    x, y = p
    bits = [(y >> i) & 1 for i in range(255)] + [x & 1]
    out = bytearray(32)
    for i in range(256):
        if bits[i]:
            out[i // 8] |= 1 << (i % 8)
    return bytes(out)


def _decode_point(data: bytes):
    if len(data) != 32:
        raise ValueError("point encoding must be 32 bytes")
    y = int.from_bytes(data, "little") & ((1 << 255) - 1)
    sign = (data[31] >> 7) & 1
    x = pow((y * y - 1) * pow(_D * y * y + 1, _Q - 2, _Q), (_Q + 3) // 8, _Q)
    if (x * x - (y * y - 1) * pow(_D * y * y + 1, _Q - 2, _Q)) % _Q != 0:
        x = x * _I % _Q
    if x & 1 != sign:
        x = _Q - x
    return x, y


def _clamp(h: bytes) -> int:
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a


def publickey(seed: bytes) -> bytes:
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    h = _sha512(seed)
    return _encode_point(_point_mul(_B, _clamp(h)))


def sign(seed: bytes, message: bytes) -> bytes:
    """Return the 64-byte Ed25519 signature of message under seed."""
    h = _sha512(seed)
    a = _clamp(h)
    prefix = h[32:]
    pub = _encode_point(_point_mul(_B, a))
    r = int.from_bytes(_sha512(prefix + message), "little") % _L
    r_enc = _encode_point(_point_mul(_B, r))
    k = int.from_bytes(_sha512(r_enc + pub + message), "little") % _L
    s = (r + k * a) % _L
    return r_enc + s.to_bytes(32, "little")


def verify(pub: bytes, message: bytes, signature: bytes) -> bool:
    if len(signature) != 64 or len(pub) != 32:
        return False
    try:
        a_point = _decode_point(pub)
        r_point = _decode_point(signature[:32])
    except Exception:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _L:
        return False
    k = int.from_bytes(_sha512(signature[:32] + pub + message), "little") % _L
    left = _point_mul(_B, s)
    right = _point_add(r_point, _point_mul(a_point, k))
    return left == right
