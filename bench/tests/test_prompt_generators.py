"""Every shipped generator must keep producing byte-identical data.

The pinned oracle numbers in each prompt's acceptance criteria are only meaningful
against one exact dataset. bench/generator_hashes.json records the sha256 of every
file each generator writes, captured when the generators were extracted from their
prompts in Phase 1. If a generator drifts, the criteria silently start describing
data no agent will ever produce -- the failure that put criteria 4/5 of the NMR
prompt 3-6% out of reach.
"""
import hashlib, json, os, shutil, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.dirname(HERE)
REPO = os.path.dirname(BENCH)
HASHES = json.load(open(os.path.join(BENCH, "generator_hashes.json")))


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class GeneratorHashTest(unittest.TestCase):
    def test_all_generators_reproduce_pinned_output(self):
        for key, expected in sorted(HASHES.items()):
            with self.subTest(key):
                src = os.path.join(REPO, "examples", key)
                self.assertTrue(os.path.isfile(src), "missing generator %s" % key)
                target = os.path.basename(key)

                if not target.endswith(".py"):        # a shipped data file, not a script
                    self.assertEqual(_sha(src), expected[target], "%s drifted" % key)
                    continue

                tmp = tempfile.mkdtemp(prefix="gen_")
                self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
                shutil.copy2(src, os.path.join(tmp, target))
                r = subprocess.run([sys.executable, target], cwd=tmp,
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                produced = {f: _sha(os.path.join(tmp, f))
                            for f in os.listdir(tmp) if f != target}
                self.assertEqual(produced, expected, "%s output drifted" % key)

    def test_every_generator_is_pinned(self):
        """A generator shipped beside a prompt but absent from the manifest is a gap."""
        found = set()
        for d in os.listdir(os.path.join(REPO, "examples")):
            dp = os.path.join(REPO, "examples", d)
            if not os.path.isdir(dp):
                continue
            for f in os.listdir(dp):
                if f.startswith("make_") and f.endswith(".py"):
                    found.add("%s/%s" % (d, f))
        self.assertEqual(found - set(HASHES), set(), "unpinned generators")


if __name__ == "__main__":
    unittest.main()
