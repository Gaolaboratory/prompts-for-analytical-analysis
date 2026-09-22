"""Tests for the tier (b) robustness harness (bench/tier_b.py,
bench/tier_b_lib/{common,tools}.py).

Three things are worth locking down here, matching the task's own emphasis:

1. Schema completeness -- every tool in tools.TOOLS has the fields the
   runner depends on, and every real input file it names actually exists
   under data/.
2. Rule 5 as a REGRESSION TEST, not just a one-time manual check: every
   perturbation must measurably change what its tool's reference computes.
   This is exactly the check this project's own design doc says was skipped
   once already (calibration_s/uvvis_s/chrom_s's first, closed-form-
   invertible perturbations, and chrom_s's too-close injection site) --
   encoding it as a test means a future edit to a perturbation function that
   silently stops perturbing anything fails CI instead of being caught by
   chance months later.
3. The harness's own control flow (run_cell / run_program): a pass, a wrong
   answer, a crash and a timeout must all be distinguishable outcomes, and a
   missing artifact must not raise.

These run against the REAL data/ files (they're small enough: the slowest,
dda_s's reference, takes about a second), but never against bench/runs/ --
no submitted program is executed by this test file.
"""
import os
import sys
import tempfile
import time
import shutil
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(BENCH, "tier_b_lib"))

import common  # noqa: E402
import tools as tb_tools  # noqa: E402

sys.path.insert(0, BENCH)
import tier_b  # noqa: E402

# Tests that read the preserved per-run workspaces under bench/runs/ skip when that
# archive is absent: it is 443 MB and does not ship with the public release, and a
# suite that errors on missing optional fixtures reports less than one that skips.
needs_runs = unittest.skipUnless(
    os.path.isdir(os.path.join(common.RUNS, "calibration_s", "local")),
    "preserved run workspaces (bench/runs/) not present")


class SchemaTest(unittest.TestCase):
    REQUIRED_KEYS = ("key", "artifacts", "data_dir", "inputs", "script",
                     "build_argv", "timeout", "perturbations", "reference",
                     "describe_effect", "grade", "skip_notes")

    def test_all_twelve_tools_present(self):
        expected = {"calibration_s", "titration_s", "uvvis_s", "spectral_s",
                    "formula_s", "chrom_s", "mass_stats_s", "pca_s", "nmr_s",
                    "mass_reader_s", "features_s", "dda_s"}
        self.assertEqual(set(tb_tools.TOOLS), expected)

    def test_schema_complete(self):
        for key, tool in tb_tools.TOOLS.items():
            for field in self.REQUIRED_KEYS:
                self.assertIn(field, tool, "%s missing %s" % (key, field))
            self.assertEqual(tool["key"], key)
            self.assertTrue(tool["artifacts"])
            self.assertIn(tool["script"], tool["artifacts"])
            self.assertGreaterEqual(len(tool["perturbations"]), 2,
                                     "%s needs >=2 perturbations" % key)
            self.assertLessEqual(len(tool["perturbations"]), 4,
                                  "%s should have <=4 perturbations" % key)
            self.assertTrue(tool["skip_notes"], "%s: skip_notes must not be "
                             "empty -- every tool skips SOME tier(a) "
                             "criteria as non-re-derivable" % key)

    def test_input_files_exist_under_data(self):
        for key, tool in tb_tools.TOOLS.items():
            for base in tool["inputs"]:
                path = os.path.join(common.DATA, tool["data_dir"], base)
                self.assertTrue(os.path.isfile(path), "%s: %s" % (key, path))

    def test_perturbation_names_unique_per_tool(self):
        for key, tool in tb_tools.TOOLS.items():
            names = [p.name for p in tool["perturbations"]]
            self.assertEqual(len(names), len(set(names)), key)


class PerturbationsChangeReferenceTest(unittest.TestCase):
    """Rule 5, as a test: every perturbation must move the reference's
    answer relative to the unperturbed input. A perturbation that leaves the
    reference unchanged tests nothing (this task's own wording) -- so a
    before == after here is a hard failure, not a warning."""

    def _refs_differ(self, tool, before, after):
        # describe_effect renders both dicts into one string; the two differ
        # in this string iff at least one described field changed, which is
        # good enough as a generic "did anything move" check across 12
        # structurally different reference shapes without hand-writing a
        # deep-equality rule per tool.
        return tool["describe_effect"](before, before) != tool["describe_effect"](before, after)

    def test_every_perturbation_changes_its_reference(self):
        for key, tool in tb_tools.TOOLS.items():
            for pert in tool["perturbations"]:
                tmp = tempfile.mkdtemp(prefix="tierb_test_")
                try:
                    tb_tools._copy_inputs(tool, tmp)
                    before = tool["reference"](tmp)
                    pert.apply(tmp)
                    after = tool["reference"](tmp)
                    self.assertTrue(
                        self._refs_differ(tool, before, after),
                        "%s/%s: reference unchanged by its own perturbation "
                        "-- %s" % (key, pert.name, pert.description))
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)

    def test_perturbations_do_not_mutate_data_or_examples(self):
        """Nothing under data/ or examples/ may be touched by applying a
        perturbation -- it must operate entirely on the tmp-dir copy."""
        data_snapshot = {}
        for root, _dirs, files in os.walk(common.DATA):
            for f in files:
                p = os.path.join(root, f)
                data_snapshot[p] = os.path.getmtime(p)
        for key, tool in tb_tools.TOOLS.items():
            for pert in tool["perturbations"]:
                tmp = tempfile.mkdtemp(prefix="tierb_test_")
                try:
                    tb_tools._copy_inputs(tool, tmp)
                    pert.apply(tmp)
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)
        for p, mtime in data_snapshot.items():
            self.assertEqual(os.path.getmtime(p), mtime, "%s was modified" % p)


class CommonHelpersTest(unittest.TestCase):
    def test_named_fields_resolves_independently_by_name(self):
        # CONVENTIONS.md rule 10: a reordered header still resolves every
        # requested field by name, and a field genuinely absent (or
        # duplicated) from the header is simply missing from the result
        # rather than corrupting the others.
        hdr = ["b", "a", "c"]
        fields = ["2", "1", "3"]
        got = common.named_fields(hdr, fields, ["a", "b", "missing"])
        self.assertEqual(got, {"a": "1", "b": "2"})

    def test_named_fields_empty_on_width_mismatch(self):
        self.assertEqual(common.named_fields(["a", "b"], ["1"], ["a"]), {})

    def test_rel_ok_and_close_abs(self):
        self.assertTrue(common.rel_ok(1.0000001, 1.0, 1e-6))
        self.assertFalse(common.rel_ok(1.1, 1.0, 1e-6))
        self.assertFalse(common.rel_ok(None, 1.0, 1e-6))
        self.assertTrue(common.close_abs(1.001, 1.0, 0.01))
        self.assertFalse(common.close_abs(None, 1.0, 0.01))

    def test_capped_line_count(self):
        path = os.path.join(tempfile.mkdtemp(), "big.txt")
        with open(path, "w") as fh:
            fh.write("\n".join(str(i) for i in range(1000)) + "\n")
        n, truncated = common.capped_line_count(path, cap=10_000)
        self.assertEqual(n, 1000)
        self.assertFalse(truncated)
        n2, truncated2 = common.capped_line_count(path, cap=100)
        self.assertGreaterEqual(n2, 100)
        self.assertTrue(truncated2)

    def test_mzml_roundtrip_preserves_kept_spectra(self):
        sys.path.insert(0, os.path.join(BENCH, "reference", "lib"))
        import mzml_reader
        src = os.path.join(common.DATA, "mass_reader", "bsa_orbitrap_first40.mzML")
        before = mzml_reader.read_mzml(src)
        dst = os.path.join(tempfile.mkdtemp(), "out.mzML")
        kept, total = common.keep_spectra(src, dst, lambda i, b: i % 2 == 0)
        self.assertEqual(total, len(before))
        after = mzml_reader.read_mzml(dst)
        self.assertEqual(len(after), kept)
        self.assertEqual([s["id"] for s in after],
                          [s["id"] for i, s in enumerate(before) if i % 2 == 0])

    @needs_runs
    def test_reps_for_skips_missing_workspaces(self):
        reps = common.reps_for("calibration_s")
        self.assertTrue(reps)
        for rep, ws in reps:
            self.assertTrue(os.path.isdir(ws))


def _write_script(tmp, name, body):
    path = os.path.join(tmp, name)
    with open(path, "w") as fh:
        fh.write(body)
    return path


class RunProgramTest(unittest.TestCase):
    """run_program (bench/tier_b_lib/common.py) must turn every submission
    outcome -- success, wrong exit code, and a hang -- into a distinct
    result dict rather than raising."""

    def test_success(self):
        tmp = tempfile.mkdtemp()
        _write_script(tmp, "ok.py", "print('hello')\n")
        r = common.run_program([sys.executable, "ok.py"], tmp, 10)
        self.assertTrue(r["ok"])
        self.assertFalse(r["crashed"])
        self.assertFalse(r["timed_out"])
        self.assertIn("hello", r["stdout"])

    def test_crash(self):
        tmp = tempfile.mkdtemp()
        _write_script(tmp, "bad.py", "import sys\nsys.exit(3)\n")
        r = common.run_program([sys.executable, "bad.py"], tmp, 10)
        self.assertFalse(r["ok"])
        self.assertTrue(r["crashed"])
        self.assertFalse(r["timed_out"])
        self.assertEqual(r["returncode"], 3)

    def test_timeout(self):
        tmp = tempfile.mkdtemp()
        _write_script(tmp, "slow.py", "import time\ntime.sleep(5)\n")
        t0 = time.time()
        r = common.run_program([sys.executable, "slow.py"], tmp, 1)
        elapsed = time.time() - t0
        self.assertTrue(r["timed_out"])
        self.assertFalse(r["crashed"])
        self.assertLess(elapsed, 4, "run_program did not honour the timeout")


class RunCellTest(unittest.TestCase):
    """Drives bench/tier_b.py's run_cell against a synthetic, minimal tool
    spec (not a real one from tools.TOOLS) so pass/fail/crash/timeout/
    missing-artifact are each exercised deterministically and fast, without
    depending on any real submitted program in bench/runs/."""

    def _make_tool(self, script_body, timeout=5):
        return {
            "key": "_toy", "artifacts": ["toy.py"],
            "data_dir": "calibration", "inputs": ["norris.csv"],  # any real, small input
            "script": "toy.py",
            "build_argv": lambda: [],
            "timeout": timeout,
            "reference": lambda tmp: {"n": 1},
            "grade": lambda tmp, run, ref: [("always true", True, "ok")],
            "skip_notes": ["n/a"],
        }

    def _make_ws(self, script_body):
        ws = tempfile.mkdtemp()
        _write_script(ws, "toy.py", script_body)
        return ws

    def test_pass(self):
        tool = self._make_tool("print('ok')\n")
        ws = self._make_ws("print('ok')\n")
        pert = tb_tools.Perturbation("noop", "no-op", lambda tmp: None)
        result = tier_b.run_cell(tool, pert, 1, ws, {"n": 1})
        self.assertEqual(result["outcome"], "pass")

    def test_fail_when_grade_reports_a_failing_criterion(self):
        tool = self._make_tool("print('ok')\n")
        tool["grade"] = lambda tmp, run, ref: [("nope", False, "detail")]
        ws = self._make_ws("print('ok')\n")
        pert = tb_tools.Perturbation("noop", "no-op", lambda tmp: None)
        result = tier_b.run_cell(tool, pert, 1, ws, {"n": 1})
        self.assertEqual(result["outcome"], "fail")

    def test_crash_is_distinct_from_fail(self):
        tool = self._make_tool("import sys; sys.exit(1)\n")
        ws = self._make_ws("import sys\nsys.exit(1)\n")
        pert = tb_tools.Perturbation("noop", "no-op", lambda tmp: None)
        result = tier_b.run_cell(tool, pert, 1, ws, {"n": 1})
        self.assertEqual(result["outcome"], "crash")
        self.assertEqual(result["criteria"], [])

    def test_timeout_is_distinct_from_crash_and_fail(self):
        tool = self._make_tool("import time; time.sleep(5)\n", timeout=1)
        ws = self._make_ws("import time\ntime.sleep(5)\n")
        pert = tb_tools.Perturbation("noop", "no-op", lambda tmp: None)
        result = tier_b.run_cell(tool, pert, 1, ws, {"n": 1})
        self.assertEqual(result["outcome"], "timeout")

    def test_missing_artifact_does_not_raise(self):
        tool = self._make_tool("print('ok')\n")
        ws = tempfile.mkdtemp()  # no toy.py in here
        pert = tb_tools.Perturbation("noop", "no-op", lambda tmp: None)
        result = tier_b.run_cell(tool, pert, 1, ws, {"n": 1})
        self.assertEqual(result["outcome"], "missing_artifact")
        self.assertIn("toy.py", result["missing"])

    def test_grader_exception_is_a_distinct_outcome(self):
        tool = self._make_tool("print('ok')\n")
        tool["grade"] = lambda tmp, run, ref: (_ for _ in ()).throw(ValueError("boom"))
        ws = self._make_ws("print('ok')\n")
        pert = tb_tools.Perturbation("noop", "no-op", lambda tmp: None)
        result = tier_b.run_cell(tool, pert, 1, ws, {"n": 1})
        self.assertEqual(result["outcome"], "grader_error")

    def test_run_cell_cleans_up_its_tmp_dir(self):
        import tier_b as tb_mod
        seen = {}
        orig_mkdtemp = tempfile.mkdtemp

        def spy_mkdtemp(*a, **kw):
            d = orig_mkdtemp(*a, **kw)
            seen["path"] = d
            return d
        tempfile.mkdtemp = spy_mkdtemp
        try:
            tool = self._make_tool("print('ok')\n")
            ws = self._make_ws("print('ok')\n")
            pert = tb_tools.Perturbation("noop", "no-op", lambda tmp: None)
            tb_mod.run_cell(tool, pert, 1, ws, {"n": 1})
        finally:
            tempfile.mkdtemp = orig_mkdtemp
        self.assertIn("path", seen)
        self.assertFalse(os.path.isdir(seen["path"]),
                          "run_cell must remove its tmp dir when done")


class ArtifactCopyTest(unittest.TestCase):
    """dda_s rep 2 (bench/runs/dda_s/solo/local/2/workspace) keeps
    fasta_reader.py under examples/mass_reader/ rather than at the workspace
    root and adds that path to sys.path relative to its own file -- this is
    the real case that motivated the recursive-search fallback in
    _copy_artifacts, reproduced here with a synthetic workspace so the test
    does not depend on that rep still existing on disk unmodified."""

    def test_copies_from_workspace_root_first(self):
        ws = tempfile.mkdtemp()
        open(os.path.join(ws, "a.py"), "w").write("# a\n")
        tmp = tempfile.mkdtemp()
        missing = tb_tools._copy_artifacts({"artifacts": ["a.py"]}, ws, tmp)
        self.assertEqual(missing, [])
        self.assertTrue(os.path.isfile(os.path.join(tmp, "a.py")))

    def test_falls_back_to_a_nested_copy_preserving_relative_path(self):
        ws = tempfile.mkdtemp()
        nested = os.path.join(ws, "examples", "mass_reader")
        os.makedirs(nested)
        open(os.path.join(nested, "fasta_reader.py"), "w").write("# nested\n")
        tmp = tempfile.mkdtemp()
        missing = tb_tools._copy_artifacts(
            {"artifacts": ["fasta_reader.py"]}, ws, tmp)
        self.assertEqual(missing, [])
        self.assertTrue(os.path.isfile(
            os.path.join(tmp, "examples", "mass_reader", "fasta_reader.py")))

    def test_reports_genuinely_missing_artifacts(self):
        ws = tempfile.mkdtemp()
        tmp = tempfile.mkdtemp()
        missing = tb_tools._copy_artifacts({"artifacts": ["nope.py"]}, ws, tmp)
        self.assertEqual(missing, ["nope.py"])


if __name__ == "__main__":
    unittest.main()
