import unittest

from harness.leaders import fetch_slot_leaders, leader_at_slot, windows_from_leaders


class FakeRpc:
    def __init__(self, seq):
        self.seq = seq

    def call(self, method, params=None):
        assert method == "getSlotLeaders"
        start, limit = params
        return self.seq[start:start + limit]


class TestWindows(unittest.TestCase):
    def test_windows_from_leaders(self):
        m = {100: "A", 101: "A", 102: "A", 103: "A", 104: "B", 105: "B",
             107: "A"}  # 106 skipped
        wins = windows_from_leaders(m, 100)
        self.assertEqual(
            [(w["identity"], w["first_slot"], w["last_slot"]) for w in wins],
            [("A", 100, 103), ("B", 104, 105), ("A", 107, 107)],
        )

    def test_fetch_chunks(self):
        seq = [f"L{i // 4}" for i in range(23)]
        rpc = FakeRpc(seq)
        m = fetch_slot_leaders(rpc, 0, 23, chunk=10)
        self.assertEqual(len(m), 23)
        self.assertEqual(leader_at_slot(m, 5), "L1")
        self.assertIsNone(leader_at_slot(m, 99))


if __name__ == "__main__":
    unittest.main()
