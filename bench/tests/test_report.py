import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import report

def make_cell(runs, tool, model, rep, passed, total, fail_line=None, failure_mode=None,
              dry_run=None, mode=None):
    cell = os.path.join(runs, tool, *([mode] if mode else []), model, str(rep))
    os.makedirs(cell)
    meta = {"tool": tool, "model": model, "rep": rep, "model_id": "m-" + model,
            "endpoint": "http://x", "prompt_sha256": "ab" * 32, "failure_mode": failure_mode,
            "iterations": 5, "wall_clock_agent_s": 100.0, "passed": passed, "total": total,
            "criteria": {"ok": True} if passed == total else {"ok": True, "bad": False},
            "grader_rc": 0 if passed == total else 1, "code_sha256": {}, "pi_rc": 0,
            "started": "2026-08-24T00:00:00"}
    if dry_run is not None:
        meta["dry_run"] = dry_run
    if mode is not None:
        meta["mode"] = mode
    with open(os.path.join(cell, "meta.json"), "w") as fh:
        json.dump(meta, fh)
    with open(os.path.join(cell, "grade.txt"), "w") as fh:
        fh.write("PASS ok\n" + ("PASS all\n" if passed == total else "FAIL bad\n")
                 + "%d/%d passed\n" % (passed, total))

class ReportTest(unittest.TestCase):
    def test_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = os.path.join(tmp, "runs")
            make_cell(runs, "titration", "local", 1, 10, 10)
            make_cell(runs, "titration", "remote", 1, 9, 10, fail_line="FAIL bad")
            rows = report.collect(runs)
            self.assertEqual(len(rows), 2)
            results, md = report.render(rows, ["local", "remote"])
            self.assertIn("| titration |", md)
            self.assertIn("10/10", md)
            self.assertIn("9/10", md)
            self.assertIn("FAIL bad", md)
            self.assertEqual(results["cells"][0]["tool"], "titration")

    def test_collect_skips_stray_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = os.path.join(tmp, "runs")
            make_cell(runs, "titration", "local", 1, 10, 10)
            make_cell(runs, "titration", "remote", 1, 9, 10)
            open(os.path.join(runs, "titration", "local", "stray.txt"), "w").close()
            open(os.path.join(runs, "titration", ".DS_Store"), "w").close()
            rows = report.collect(runs)
            self.assertEqual(len(rows), 2)

    def test_collect_excludes_dry_run_cells(self):
        """A dry-run cell's stub delegates to the reference implementation, so it
        always scores full marks; counting it as a result would misreport the
        model. Same exclusion phase0_report.py makes for iterations == 0 and
        stale-prompt cells."""
        with tempfile.TemporaryDirectory() as tmp:
            runs = os.path.join(tmp, "runs")
            make_cell(runs, "titration", "local", 1, 10, 10, dry_run=False)
            make_cell(runs, "titration", "local", 2, 10, 10, dry_run=True)
            rows = report.collect(runs)
            self.assertEqual([r["rep"] for r in rows], [1])
            self.assertEqual(len(report.collect(runs, include_dry_run=True)), 2)
            _, md = report.render(rows, ["local"])
            self.assertEqual(md.count("10/10"), 1)

    def test_render_keeps_both_modes_of_a_multi_mode_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = os.path.join(tmp, "runs")
            make_cell(runs, "features_s", "local", 1, 6, 6, mode="solo")
            make_cell(runs, "features_s", "local", 1, 4, 6, mode="prebuilt")
            rows = report.collect(runs)
            self.assertEqual(len(rows), 2)
            _, md = report.render(rows, ["local"])
            self.assertIn("| features_s (solo) |", md)
            self.assertIn("| features_s (prebuilt) |", md)
            self.assertIn("6/6", md)
            self.assertIn("4/6", md)


if __name__ == "__main__":
    unittest.main()
