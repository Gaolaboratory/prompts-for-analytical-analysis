"""Resume logic for the experiment runner.

A cell is skipped on resume because it holds a RESULT, not merely because it
holds a grade.txt. Void cells hold a grade.txt too -- run_cell grades whatever
the workspace contains even when the driver never made a tool call -- so a
skip keyed on that file alone cements infrastructure failures as measurements.

That is not hypothetical. A run of A/dda_s launched without --expect-served
aborted all 16 cells at turn 0 (`model_substituted`, iterations=0, 3-6 s) and
wrote 16 grade.txt files reading 0/6. report_exp.py excluded them from every
denominator, correctly, but every later resume skipped them, so the ablation
would have stayed 16 cells short while looking complete.
"""
import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import run_exp


def make_cell(root, graded=True, failure_mode=None, meta=True):
    cell = os.path.join(root, "cell")
    os.makedirs(cell, exist_ok=True)
    if graded:
        with open(os.path.join(cell, "grade.txt"), "w") as fh:
            fh.write("FAIL something\n0/6 passed\n")
    if meta:
        with open(os.path.join(cell, "meta.json"), "w") as fh:
            json.dump({"failure_mode": failure_mode}, fh)
    return cell


class ShouldRunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_ungraded_cell_runs(self):
        cell = make_cell(self.tmp, graded=False, meta=False)
        self.assertTrue(run_exp.should_run(cell, force=False))

    def test_missing_cell_runs(self):
        self.assertTrue(run_exp.should_run(os.path.join(self.tmp, "absent"),
                                           force=False))

    def test_graded_cell_is_skipped(self):
        cell = make_cell(self.tmp, failure_mode=None)
        self.assertFalse(run_exp.should_run(cell, force=False))

    def test_void_cell_is_rerun(self):
        """The bug this test exists for: void is not a result."""
        for mode in sorted(run_exp.VOID_MODES):
            with self.subTest(mode=mode):
                tmp = tempfile.mkdtemp()
                cell = make_cell(tmp, failure_mode=mode)
                self.assertTrue(run_exp.should_run(cell, force=False),
                                "%s is void and must not be skipped" % mode)

    def test_context_overflow_is_a_result_and_is_skipped(self):
        """Deliberately NOT void: it is a real finding about whether the
        prompt and its agentic trace fit the model being claimed for it."""
        cell = make_cell(self.tmp, failure_mode="context_overflow")
        self.assertFalse(run_exp.should_run(cell, force=False))

    def test_scored_model_failure_is_skipped(self):
        """malformed_tool_call is a property of the model under this prompt,
        not of the endpoint, so a cell carrying it is a measurement."""
        cell = make_cell(self.tmp, failure_mode="malformed_tool_call")
        self.assertFalse(run_exp.should_run(cell, force=False))

    def test_graded_but_unreadable_meta_runs(self):
        cell = make_cell(self.tmp, meta=False)
        self.assertTrue(run_exp.should_run(cell, force=False))
        with open(os.path.join(cell, "meta.json"), "w") as fh:
            fh.write("{truncated")
        self.assertTrue(run_exp.should_run(cell, force=False))

    def test_force_reruns_everything(self):
        cell = make_cell(self.tmp, failure_mode=None)
        self.assertTrue(run_exp.should_run(cell, force=True))


class VoidModesAreSharedTest(unittest.TestCase):
    def test_single_source_of_truth(self):
        """One definition, so the runner and the reporter can never disagree
        about which cells are measurements."""
        import report_exp
        self.assertIs(run_exp.VOID_MODES, report_exp.VOID_MODES)


if __name__ == "__main__":
    unittest.main()
