"""Rig for grader tests: run a grader in a dir, parse verdicts, apply mutations."""
import os, shutil, subprocess, sys, tempfile, unittest
import fixtures

HERE = os.path.dirname(os.path.abspath(__file__))
GRADERS = os.path.join(os.path.dirname(HERE), "graders")

def run_grader(name, args, cwd):
    path = name if os.path.isabs(name) else os.path.join(GRADERS, name)
    p = subprocess.run([sys.executable, "-B", path] + args,
                       cwd=cwd, capture_output=True, text=True)
    verdicts = {}
    for line in p.stdout.splitlines():
        if line.startswith(("PASS ", "FAIL ")):
            verdicts[line[5:]] = line.startswith("PASS ")
    return p.returncode, verdicts, p.stdout + p.stderr

def replace(d, name, old, new, count=1):
    path = os.path.join(d, name)
    txt = open(path).read()
    assert old in txt, "mutation target %r not in %s" % (old, path)
    open(path, "w").write(txt.replace(old, new, count))

class GraderCase(unittest.TestCase):
    grader = None      # e.g. "grade_titration.py"
    grader_args = []   # e.g. ["."] ; "{d}" expands to the fixture dir
    tool = None        # fixtures.build_artifacts key

    def grade(self):
        d = tempfile.mkdtemp(prefix="conf_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts(self.tool, d)
        args = [a.replace("{d}", d) for a in self.grader_args]
        return run_grader(self.grader, args, cwd=d)

    def test_conformant(self):
        if self.tool is None:
            self.skipTest("abstract rig base")
        rc, verdicts, out = self.grade()
        self.assertEqual(rc, 0, out)
        self.assertTrue(verdicts and all(verdicts.values()), out)

    def check_mutation(self, mutate, criterion):
        d = tempfile.mkdtemp(prefix="mut_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fixtures.build_artifacts(self.tool, d)
        mutate(d)
        args = [a.replace("{d}", d) for a in self.grader_args]
        rc, verdicts, out = run_grader(self.grader, args, cwd=d)
        self.assertNotEqual(rc, 0, out)
        self.assertIn(criterion, verdicts, out)
        self.assertFalse(verdicts[criterion], out)
