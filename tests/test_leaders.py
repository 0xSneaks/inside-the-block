import unittest

from harness.leaders import classify_client


class TestClassify(unittest.TestCase):
    def test_jito_set_wins_over_agave_version(self):
        self.assertEqual(classify_client("4.3.2", in_jito_set=True), "jito-solana")

    def test_firedancer_calendar_version(self):
        self.assertEqual(classify_client("26.10.4"), "firedancer")
        self.assertEqual(classify_client("26.9.6"), "firedancer")

    def test_frankendancer_legacy(self):
        self.assertEqual(classify_client("0.1105.40200"), "firedancer")

    def test_unrecognized_short_version_is_unknown(self):
        self.assertEqual(classify_client("0.1.1", in_jito_set=True), "UNKNOWN")

    def test_firedancer_scheme_beats_jito_set(self):
        # FireBAM-style node: Firedancer client + Jito BAM. Client wins.
        self.assertEqual(classify_client("26.10.4", in_jito_set=True), "firedancer")

    def test_agave_versions(self):
        self.assertEqual(classify_client("4.3.2"), "agave")
        self.assertEqual(classify_client("2.3.8"), "agave")

    def test_unknown(self):
        self.assertEqual(classify_client(None), "UNKNOWN")
        self.assertEqual(classify_client(""), "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
