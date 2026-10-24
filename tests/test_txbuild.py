import hashlib
import unittest

from harness import config, ed25519, txbuild

SEED = bytes(range(32))  # throwaway test seed, NOT the measurement key
BLOCKHASH = bytes([7] * 32)


class TestTxBuild(unittest.TestCase):
    def test_b58_roundtrip(self):
        data = bytes(range(32))
        self.assertEqual(txbuild.b58decode(txbuild.b58encode(data)), data)
        self.assertEqual(
            txbuild.b58decode(config.MEASUREMENT_WALLET).__len__(), 32
        )

    def test_message_structure(self):
        pub = ed25519.publickey(SEED)
        msg = txbuild.build_message(pub, "high", 3, BLOCKHASH)
        # header: 1 signer, 0 readonly signed, 2 readonly unsigned
        self.assertEqual(msg[0:3], bytes([1, 0, 2]))
        self.assertEqual(msg[3], 3)  # 3 account keys
        self.assertEqual(msg[4:36], pub)
        # 3 instructions for a priced tier (limit, price, transfer)
        ix_count_at = 4 + 32 * 3 + 32
        self.assertEqual(msg[ix_count_at], 3)
        # zero tier omits the price instruction
        msg0 = txbuild.build_message(pub, "zero", 3, BLOCKHASH)
        self.assertEqual(msg0[ix_count_at], 2)

    def test_signed_tx_verifies(self):
        raw, sig_b58 = txbuild.build_signed_tx(SEED, "mid", 5, BLOCKHASH)
        pub = ed25519.publickey(SEED)
        sig = txbuild.b58decode(sig_b58)
        self.assertEqual(len(sig), 64)
        # tx layout: shortvec(1) + 64-byte sig + message
        self.assertEqual(raw[0], 1)
        self.assertEqual(raw[1:65], sig)
        self.assertTrue(ed25519.verify(pub, raw[65:], sig))

    def test_marker_amount_bounds(self):
        self.assertEqual(txbuild.marker_amount(0), config.MARKER_BASE_LAMPORTS)
        with self.assertRaises(ValueError):
            txbuild.marker_amount(16)


if __name__ == "__main__":
    unittest.main()
