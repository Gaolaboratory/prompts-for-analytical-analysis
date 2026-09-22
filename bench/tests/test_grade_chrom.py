import os, shutil, sys, tempfile, unittest
from grader_rig import GraderCase, replace, run_grader

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "graders"))
import _grading
import fixtures

class ChromGraderTest(GraderCase):
    grader = "grade_chrom.py"
    grader_args = ["peaks.tsv", "stdout.log", "{d}/session.jsonl"]
    tool = "chrom"

    def test_mutations(self):
        M = [
            # c1 regression: corrupt the agent-side evidence only — the session's
            # opening user message still echoes all five literals from the prompt,
            # so this flips c1 to FAIL only if the grader ignores the prompt echo.
            (lambda d: replace(d, "session.jsonl", "crossings 0.100 and 3.900", "crossings 0.200 and 3.900"), "c1 triangle self-check (session)"),
            (lambda d: replace(d, "peaks.tsv", "peak_id\trt_apex", "peak_id,rt_apex"), "c2 peaks.tsv structure"),
            (lambda d: replace(d, "stdout.log", "sd=4.291", "sd=5.000"), "c3 stdout noise stats"),
            (lambda d: replace(d, "stdout.log", "peaks detected: 3", "peaks detected: 4"), "c4 stdout peaks detected: 3"),
            (lambda d: replace(d, "peaks.tsv", "1\t60.000", "1\t70.000"), "c5 rt_apex ±1.0"),
            (lambda d: replace(d, "peaks.tsv", "7821.509", "6000.000"), "c6 area ±5% and height ±5%"),
            (lambda d: replace(d, "peaks.tsv", "0.993", "1.500"), "c7 tf bands"),
            (lambda d: replace(d, "peaks.tsv", "3.158", "2.000"), "c8 N/rs/sn"),
        ]
        for mutate, crit in M:
            with self.subTest(crit):
                self.check_mutation(mutate, crit)

    def test_c1_prompt_echo_alone_fails(self):
        # The real failure mode: session = user prompt echo (all five literals)
        # with NO agent-side evidence -> c1 must FAIL, not pass vacuously.
        d = tempfile.mkdtemp(prefix="echo_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts("chrom", d)
        open(os.path.join(d, "session.jsonl"), "w").write(
            fixtures._session_jsonl(fixtures.CHROM_SESSION_ECHO, []))
        rc, verdicts, out = run_grader(self.grader,
                                       ["peaks.tsv", "stdout.log", os.path.join(d, "session.jsonl")], cwd=d)
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(verdicts["c1 triangle self-check (session)"], out)

class SessionTextExcludingUserTest(unittest.TestCase):
    def test_user_echo_excluded_agent_text_kept(self):
        d = tempfile.mkdtemp(prefix="st_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        p = os.path.join(d, "session.jsonl")
        open(p, "w").write(fixtures.CHROM_SESSION)
        txt = _grading.session_text_excluding_user(p)
        self.assertIn(fixtures.CHROM_SESSION_EVIDENCE, txt)
        self.assertNotIn("prompt excerpt", txt)          # user echo dropped

    def test_missing_file_and_bad_lines(self):
        self.assertEqual(_grading.session_text_excluding_user("/no/such/file.jsonl"), "")
        d = tempfile.mkdtemp(prefix="st_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        p = os.path.join(d, "session.jsonl")
        open(p, "w").write("not json\n" + fixtures.CHROM_SESSION)
        self.assertIn("4.000", _grading.session_text_excluding_user(p))
