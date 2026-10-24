import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_cli(*argv):
    return subprocess.run(
        [sys.executable, "-m", "harness", *argv],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )


class TestDryRun(unittest.TestCase):
    def test_plan_fits_cap(self):
        r = run_cli("plan")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("hard cap: 50000000 lamports", r.stdout)

    def test_fee_rule_dry_run_detects_fee_ordering(self):
        with tempfile.TemporaryDirectory() as td:
            r = subprocess.run(
                [sys.executable, "-m", "harness", "dry-run", "--rule", "fee"],
                cwd=ROOT, capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("fee-ordered", r.stdout)

    def test_random_rule_dry_run_no_fee_ordering(self):
        r = run_cli("dry-run", "--rule", "random")
        self.assertEqual(r.returncode, 0, r.stderr)
        # In the H0 world no validator may come out fee-ordered across all bursts.
        self.assertNotIn('"verdict": "fee-ordered"', r.stdout)

    def test_live_gate_blocks_without_env(self):
        from harness import sender
        from harness.burst import plan_burst
        from harness.fees import FeeAccountant
        import tempfile as tf

        with tf.TemporaryDirectory() as td:
            acct = FeeAccountant(os.path.join(td, "l.json"))
            env_before = os.environ.pop("INSIDE_BLOCK_LIVE_OK", None)
            try:
                with self.assertRaises(sender.LiveGateError):
                    sender.send_burst_live(plan_burst("x", 0), acct, rpc=None)
            finally:
                if env_before is not None:
                    os.environ["INSIDE_BLOCK_LIVE_OK"] = env_before


if __name__ == "__main__":
    unittest.main()
