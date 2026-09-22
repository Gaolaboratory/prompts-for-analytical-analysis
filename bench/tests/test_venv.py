import os, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import venv_setup
import run_bench


class VenvTest(unittest.TestCase):
    def test_requirements_pinned(self):
        lines = [l.strip() for l in open(venv_setup.REQUIREMENTS) if l.strip()
                 and not l.startswith("#")]
        self.assertEqual(sorted(lines), ["numpy==2.5.2", "pandas==3.0.5", "scipy==1.18.1"])

    def test_ensure_venv_gives_a_python_with_the_stack(self):
        py = venv_setup.ensure_venv()
        self.assertTrue(os.path.isfile(py), py)
        out = subprocess.run([py, "-c",
            "import numpy,pandas,scipy;print(numpy.__version__,pandas.__version__,scipy.__version__)"],
            capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.split(), ["2.5.2", "3.0.5", "1.18.1"])

    def test_ensure_venv_is_idempotent(self):
        self.assertEqual(venv_setup.ensure_venv(), venv_setup.ensure_venv())

    def _throwaway_venv(self):
        """Point venv_setup at a THROWAWAY venv directory for one test.

        This test used to uninstall numpy from the repo's own .venv-bench and
        --clear the interpreter running the suite: with no network and no
        timeout it could leave the shared venv broken for every later suite run
        and for run_bench.main(). Nothing here touches the shared venv.
        """
        import shutil
        tmp = tempfile.mkdtemp(prefix="throwaway_venv_")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        real = venv_setup.VENV_DIR
        venv_setup.VENV_DIR = os.path.join(tmp, "venv")
        self.addCleanup(setattr, venv_setup, "VENV_DIR", real)
        return venv_setup.VENV_DIR

    def _versions(self, py):
        out = subprocess.run([py, "-c", "import numpy,pandas,scipy;print("
            "numpy.__version__,pandas.__version__,scipy.__version__)"],
            capture_output=True, text=True, timeout=300)
        return out.returncode, out.stdout.split(), out.stderr

    def test_ensure_venv_repairs_broken_venv(self):
        """A venv that exists but is missing a package (interrupted install,
        manual tinkering, a version bump) must be rebuilt IN PLACE, not left
        permanently broken -- ensure_venv's docstring promises "absent or
        incomplete", not just "absent". Because the directory already exists,
        the rebuild only works with `uv venv --clear`; drop that flag and uv
        refuses to touch the existing venv and this test fails.
        """
        import shutil
        self._throwaway_venv()
        py = venv_setup.ensure_venv()
        self.assertEqual(self._versions(py)[1], ["2.5.2", "3.0.5", "1.18.1"])

        for entry in os.listdir(os.path.join(
                os.path.dirname(os.path.dirname(py)),
                "lib", "python%s" % venv_setup.PYTHON_VERSION, "site-packages")):
            if entry.startswith("numpy"):        # package dir and its dist-info
                shutil.rmtree(os.path.join(
                    os.path.dirname(os.path.dirname(py)), "lib",
                    "python%s" % venv_setup.PYTHON_VERSION, "site-packages", entry),
                    ignore_errors=True)
        broken = subprocess.run([py, "-c", "import numpy"], capture_output=True)
        self.assertNotEqual(broken.returncode, 0,
                            "removing numpy did not actually break the venv")
        self.assertFalse(venv_setup._stack_ok(py))

        repaired = venv_setup.ensure_venv()

        self.assertEqual(repaired, py)
        rc, versions, err = self._versions(repaired)
        self.assertEqual(rc, 0, err)
        self.assertEqual(versions, ["2.5.2", "3.0.5", "1.18.1"])
        # the shared venv the suite itself runs on was never involved
        shared = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(venv_setup.__file__))),
            ".venv-bench", "bin", "python3")
        self.assertEqual(self._versions(shared)[1], ["2.5.2", "3.0.5", "1.18.1"])

    def test_stack_ok_rejects_a_venv_that_is_off_its_pins(self):
        """A venv whose versions drifted off requirements-bench.txt -- an agent
        session pip-installing into it, say, since it is first on PATH -- must
        count as "needs rebuild": the expected values in data/*/README.md were
        computed against the pins, so a silent repin invalidates them. Checked by
        moving the pins rather than the installation, so the test needs neither
        the network nor a write to the shared venv."""
        py = venv_setup.venv_python()
        self.assertTrue(venv_setup._stack_ok(py))          # at the real pins
        tmp = tempfile.mkdtemp(prefix="pins_")
        self.addCleanup(__import__("shutil").rmtree, tmp, ignore_errors=True)
        moved = os.path.join(tmp, "requirements-bench.txt")
        with open(moved, "w") as fh:
            fh.write("numpy==1.0.0\npandas==3.0.5\nscipy==1.18.1\n")
        real = venv_setup.REQUIREMENTS
        venv_setup.REQUIREMENTS = moved
        self.addCleanup(setattr, venv_setup, "REQUIREMENTS", real)
        # Importable but the wrong version: the old check (import numpy,pandas,
        # scipy) accepted this.
        self.assertFalse(venv_setup._stack_ok(py),
                         "_stack_ok accepted a venv that is off its pins")

    def test_ensure_venv_reports_a_uv_timeout_clearly(self):
        """Both uv calls are on run_bench.main()'s critical path; a hang there
        used to be unbounded and silent."""
        self._throwaway_venv()
        real = venv_setup.UV_TIMEOUT
        venv_setup.UV_TIMEOUT = 0.001
        self.addCleanup(setattr, venv_setup, "UV_TIMEOUT", real)
        with self.assertRaises(RuntimeError) as caught:
            venv_setup.ensure_venv()
        self.assertIn("timed out", str(caught.exception))

    def test_pinned_versions_reads_the_requirements_file(self):
        self.assertEqual(venv_setup.pinned_versions(),
                         {"numpy": "2.5.2", "pandas": "3.0.5", "scipy": "1.18.1"})

    def test_activate_path_puts_venv_first(self):
        venv_setup.ensure_venv()
        old = os.environ["PATH"]
        self.addCleanup(os.environ.__setitem__, "PATH", old)
        venv_setup.activate_path()
        first = os.environ["PATH"].split(os.pathsep)[0]
        self.assertEqual(first, os.path.join(venv_setup.VENV_DIR, "bin"))
        which = subprocess.run(["python3", "-c", "import scipy;print('ok')"],
                               capture_output=True, text=True)
        self.assertEqual(which.stdout.strip(), "ok", which.stderr)


class RunGraderVenvTest(unittest.TestCase):
    """run_bench.run_grader launches the grader with the bench venv's python,
    not sys.executable, so a grader that `import numpy` (added in a later
    task) works even though the Homebrew python3 running the harness itself
    has no numpy. Proven by running a throwaway grader that only succeeds
    under the venv interpreter."""

    def test_run_grader_uses_venv_python(self):
        venv_setup.ensure_venv()
        tmp = tempfile.mkdtemp()
        grader = os.path.join(tmp, "toy_grader.py")
        open(grader, "w").write(
            "import numpy, sys\n"
            "assert sys.executable == %r, sys.executable\n"
            "print('PASS x')\n" % venv_setup.venv_python()
        )
        spec = {"grader": grader, "grader_args": []}
        meta = {"failure_mode": None}
        grade_path = os.path.join(tmp, "grade.txt")
        run_bench.run_grader(spec, "cell1", tmp, meta, grade_path)
        self.assertEqual(meta.get("grader_rc"), 0, open(grade_path).read())
        self.assertEqual(meta["criteria"], {"x": True})


if __name__ == "__main__":
    unittest.main()
