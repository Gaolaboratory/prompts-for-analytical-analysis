import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import run_tier_c
import tier_c_specs


class BuildPromptTest(unittest.TestCase):
    def test_prompt_plus_addendum(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "prompt.md")
            open(p, "w").write("# Spec\n\nWrite the tool.\n")
            out = run_tier_c.build_prompt(p, "## Real-data run\n\nUse real.csv.")
        self.assertTrue(out.startswith("# Spec\n\nWrite the tool.\n\n## Real-data run"))
        self.assertTrue(out.endswith("Use real.csv.\n"))

    def test_addendum_disclaims_synthetic_criteria(self):
        for tool, spec in tier_c_specs.TIER_C.items():
            self.assertIn("do NOT apply", spec["addendum"],
                          "%s addendum must disclaim synthetic criteria" % tool)


class RunTierCCellTest(unittest.TestCase):
    def test_dry_run_cell_assembles(self):
        # calibration data is sourced before this test runs; skip if not yet present
        spec = tier_c_specs.TIER_C["calibration"]
        if not all(os.path.isfile(f) for f in spec["data_files"]):
            self.skipTest("calibration data not yet sourced")
        orig = run_tier_c.RUNS_DIR
        tmp = tempfile.mkdtemp(prefix="tierc_")
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        run_tier_c.RUNS_DIR = os.path.join(tmp, "runs")
        cell, meta = run_tier_c.run_tier_c_cell(
            "calibration", __import__("argparse").Namespace(dry_run=True, timeout=60))
        ws = os.path.join(cell, "workspace")
        self.assertTrue(os.path.isfile(os.path.join(ws, "norris.csv")))
        self.assertTrue(os.path.isfile(os.path.join(cell, "prompt_full.txt")))
        prompt = open(os.path.join(cell, "prompt_full.txt")).read()
        self.assertIn("Real-data run (tier c)", prompt)
        self.assertIn("unweighted", prompt)
        self.assertEqual(meta["data_files"], ["norris.csv"])
        self.assertEqual(meta["failure_mode"], None)
        self.assertIn("norris.csv", meta["outputs"])
        run_tier_c.RUNS_DIR = orig


if __name__ == "__main__":
    unittest.main()
