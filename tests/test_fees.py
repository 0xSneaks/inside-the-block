import os
import tempfile
import unittest

from harness import config
from harness.burst import plan_burst
from harness.fees import CapExceeded, FeeAccountant, burst_fee_lamports, tx_fee_lamports


class TestFees(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ledger = os.path.join(self.tmp, "ledger.json")

    def test_tier_fee_math(self):
        # base 5000 + priority: zero 0, low 12_500, mid 50_000, high 100_000
        self.assertEqual(tx_fee_lamports("zero"), 5_000)
        self.assertEqual(tx_fee_lamports("low"), 17_500)
        self.assertEqual(tx_fee_lamports("mid"), 55_000)
        self.assertEqual(tx_fee_lamports("high"), 105_000)

    def test_planned_study_fits_cap(self):
        plan = plan_burst("b0", 0)
        per_burst = burst_fee_lamports(plan.tiers)
        total = per_burst * config.MIN_VALIDATORS * config.BURSTS_PER_VALIDATOR
        self.assertLessEqual(total, config.CAP_LAMPORTS)

    def test_commit_and_persistence(self):
        acct = FeeAccountant(self.ledger)
        plan = plan_burst("b0", 0)
        total = acct.commit("b0", plan.tiers)
        self.assertEqual(acct.committed, total)
        acct2 = FeeAccountant(self.ledger)
        self.assertEqual(acct2.committed, total)

    def test_cap_refusal(self):
        acct = FeeAccountant(self.ledger)
        # Each all-high burst costs 16 * 105_000 = 1_680_000 lamports.
        # 29 fit (48_720_000); the 30th must be refused.
        high = ["high"] * config.BURST_SIZE
        for i in range(29):
            acct.commit(f"b{i}", high)
        with self.assertRaises(CapExceeded):
            acct.commit("b29", high)
        # check() alone also refuses, without mutating state
        before = acct.committed
        with self.assertRaises(CapExceeded):
            acct.check(high)
        self.assertEqual(acct.committed, before)


if __name__ == "__main__":
    unittest.main()
