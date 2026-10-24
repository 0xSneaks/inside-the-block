import unittest

from harness.analyze import burst_correlations, spearman, validator_verdict


def make_rows(order_with_tiers):
    """order_with_tiers: list of (send_index, tier) in landed order."""
    return [
        {
            "send_index": si,
            "fee_tier": tier,
            "landed_position": pos,
            "landed": True,
        }
        for pos, (si, tier) in enumerate(order_with_tiers)
    ]


TIERS16 = ["zero", "high", "low", "mid"] * 4


class TestAnalyze(unittest.TestCase):
    def test_spearman_perfect(self):
        self.assertAlmostEqual(spearman([0, 1, 2, 3], [10, 20, 30, 40]), 1.0)
        self.assertAlmostEqual(spearman([0, 1, 2, 3], [40, 30, 20, 10]), -1.0)

    def test_arrival_ordered_burst(self):
        rows = make_rows([(i, TIERS16[i]) for i in range(16)])
        corr = burst_correlations(rows)
        self.assertGreater(corr["rho_send"], 0.99)

    def test_fee_ordered_burst(self):
        order = sorted(range(16), key=lambda i: -["zero", "low", "mid", "high"].index(TIERS16[i]))
        rows = make_rows([(i, TIERS16[i]) for i in order])
        corr = burst_correlations(rows)
        self.assertLess(corr["rho_fee"], -0.7)

    def test_verdict_requires_all_bursts(self):
        fee_corr = {"n": 16, "rho_send": 0.1, "rho_fee": -0.95}
        v = validator_verdict([fee_corr, fee_corr, fee_corr])
        self.assertEqual(v["verdict"], "fee-ordered")
        mixed = validator_verdict(
            [fee_corr, {"n": 16, "rho_send": 0.95, "rho_fee": 0.0}, fee_corr]
        )
        self.assertEqual(mixed["verdict"], "mixed")
        none_corr = {"n": 16, "rho_send": 0.1, "rho_fee": -0.1}
        v0 = validator_verdict([none_corr, none_corr, none_corr])
        self.assertEqual(v0["verdict"], "no-pattern")


if __name__ == "__main__":
    unittest.main()
