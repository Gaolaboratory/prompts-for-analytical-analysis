import os, unittest
from grader_rig import run_grader

class RigTest(unittest.TestCase):
    def test_run_grader_parses_verdicts(self):
        d = os.path.join(os.path.dirname(__file__), "_dummy")
        os.makedirs(d, exist_ok=True)
        self.addCleanup(__import__("shutil").rmtree, d, ignore_errors=True)
        g = os.path.join(d, "dummy_grade.py")
        with open(g, "w") as fh:
            fh.write('import sys; print("PASS a"); print("FAIL b"); print("1/2 passed"); sys.exit(1)\n')
        rc, verdicts, out = run_grader(g, [], cwd=d)
        self.assertEqual(rc, 1)
        self.assertEqual(verdicts, {"a": True, "b": False})

if __name__ == "__main__":
    unittest.main()
