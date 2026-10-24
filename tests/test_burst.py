import unittest

from harness import config
from harness.analyze import TIER_RANK, spearman
from harness.burst import plan_burst


class TestBurst(unittest.TestCase):
    def test_size_and_markers(self):
        plan = plan_burst("b0", 0)
        self.assertEqual(len(plan.txs), config.BURST_SIZE)
        amounts = [t.marker_amount for t in plan.txs]
        self.assertEqual(len(set(amounts)), config.BURST_SIZE)
        self.assertEqual(amounts, [config.MARKER_BASE_LAMPORTS + i for i in range(16)])

    def test_fee_decorrelated_from_send_order(self):
        plan = plan_burst("b0", 0)
        ranks = [TIER_RANK[t.tier] for t in plan.txs]
        rho = spearman(list(range(16)), ranks)
        self.assertLess(abs(rho), 0.5)

    def test_alternate_burst_reversed(self):
        p0 = plan_burst("b0", 0)
        p1 = plan_burst("b1", 1)
        self.assertEqual(p1.tiers, p0.tiers[::-1])
        p2 = plan_burst("b2", 2)
        self.assertEqual(p2.tiers, p0.tiers)


if __name__ == "__main__":
    unittest.main()
