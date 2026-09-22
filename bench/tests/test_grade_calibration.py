import os, shutil, tempfile
from grader_rig import GraderCase, replace, run_grader
import fixtures

def _drop_calibrate_py(d):
    os.remove(os.path.join(d, "calibrate.py"))          # force the session fallback

def _drop_agent_evidence(d):
    # Keep the user prompt echo (which quotes 2.0250/0.0571) but corrupt the
    # agent-side evidence line: the echo alone must not satisfy c6.
    replace(d, "session.jsonl", "-> slope 2.0250 intercept 0.0571 ok",
            "-> slope 2.0786 intercept -0.0500 ok")

class CalibrationGraderTest(GraderCase):
    grader = "grade_calibration.py"
    grader_args = ["stdout.txt", "results.tsv", "{d}/session.jsonl"]
    tool = "calibration"

    def test_mutations(self):
        M = [
            (lambda d: replace(d, "stdout.txt", "slope\t2.5025\n", "slope\t2.5025\nextra\t1\n"), "c1 six stdout lines in order"),
            (lambda d: replace(d, "stdout.txt", "slope\t2.5025", "slope\t2.6500"), "c2 slope/intercept/r2"),
            (lambda d: replace(d, "stdout.txt", "LOD\t0.0060", "LOD\t0.0100"), "c3 sigma/LOD/LOQ"),
            (lambda d: replace(d, "results.tsv", "sample_id", "id"), "c4 header + 3 rows in order"),
            (lambda d: replace(d, "results.tsv", "+0.43", "+6.30"), "c5 |bias| <= 5%"),
            # brief's mutation was ("2.0250", "2.0786"), but the brief's calibrate.py
            # fixture never contains "2.0250" (wls computes it); the intended
            # corruption is "forgot the weights" -> unweighted slope 2.0786.
            (lambda d: replace(d, "calibrate.py", "1.0 / (x * x)", "1.0"), "c6 wls self-check 2.0250/0.0571"),
            # c6 echo regression: no importable wls, agent evidence corrupted,
            # prompt echo intact -> the echo must not carry c6.
            (lambda d: (_drop_calibrate_py(d), _drop_agent_evidence(d)), "c6 wls self-check 2.0250/0.0571"),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)

    def test_c6_session_fallback(self):
        d = tempfile.mkdtemp(prefix="fb_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts("calibration", d)
        _drop_calibrate_py(d)                             # force the fallback path
        rc, verdicts, out = run_grader(self.grader,
                                       ["stdout.txt", "results.tsv", os.path.join(d, "session.jsonl")], cwd=d)
        self.assertTrue(verdicts.get("c6 wls self-check 2.0250/0.0571", False), out)

    def test_c6_prompt_echo_alone_fails(self):
        # The real failure mode: wls missing from the workspace AND the session
        # holds only the user prompt echo -> c6 must FAIL, not pass vacuously.
        d = tempfile.mkdtemp(prefix="echo_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts("calibration", d)
        _drop_calibrate_py(d)
        open(os.path.join(d, "session.jsonl"), "w").write(
            fixtures._session_jsonl(fixtures.CAL_SESSION_ECHO, []))
        rc, verdicts, out = run_grader(self.grader,
                                       ["stdout.txt", "results.tsv", os.path.join(d, "session.jsonl")], cwd=d)
        self.assertFalse(verdicts.get("c6 wls self-check 2.0250/0.0571", False), out)
