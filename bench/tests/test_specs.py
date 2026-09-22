import os, sys, unittest
# brief's test lacked this bootstrap; `import specs` needs bench/ on sys.path
# when discovery runs from the repo root (same pattern as test_run_bench.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import specs

class SpecsTest(unittest.TestCase):
    def test_schema_complete(self):
        for tool, spec in specs.SPECS.items():
            for key in ("prompt", "run_cmd", "grader", "grader_args", "artifacts"):
                self.assertIn(key, spec, "%s missing %s" % (tool, key))
            self.assertTrue(os.path.isfile(spec["prompt"]), spec["prompt"])
            self.assertTrue(os.path.isfile(os.path.join(
                os.path.dirname(specs.__file__), "graders", spec["grader"])))
            self.assertTrue(spec["artifacts"])
            # exactly one data source: a generator to run, or files to copy
            self.assertNotEqual("gen_cmd" in spec, "data" in spec,
                                "%s must have gen_cmd xor data" % tool)

    def test_data_specs_name_real_input_files(self):
        data_root = os.path.join(specs.REPO, "data")
        for tool, spec in specs.SPECS.items():
            for path in spec.get("data", []):
                self.assertTrue(os.path.isfile(path), "%s: %s" % (tool, path))
                self.assertTrue(os.path.abspath(path).startswith(data_root),
                                "%s seeds from outside data/: %s" % (tool, path))
                self.assertNotIn(os.path.basename(path), specs.ANSWER_FILES,
                                 "%s seeds an answer file: %s" % (tool, path))

    def test_short_track_specs_are_suffixed(self):
        for tool, spec in specs.SPECS.items():
            if "data" in spec:
                self.assertTrue(tool.endswith("_s"), tool)
                self.assertTrue(spec["prompt"].endswith("PROMPT.md"), spec["prompt"])

    def test_models(self):
        self.assertIn("local", specs.MODELS)
        self.assertIn("remote", specs.MODELS)

    def test_short_track_deps_match_the_prompt_table(self):
        for tool, spec in specs.SPECS.items():
            if "data" not in spec:
                continue
            text = open(spec["prompt"]).read()
            # The spec key registered for the mass_reader dependency is
            # "mass_reader_s", not "mass_reader" -- checking for the bare
            # name against spec["deps"] is a list-membership test that is
            # always False, disagreeing with a prompt whose Dependencies
            # table does reference examples/mass_reader/PROMPT.md.
            declared = "mass_reader_s" in spec.get("deps", [])
            in_table = "examples/mass_reader/PROMPT.md" in text
            self.assertEqual(declared, in_table,
                             "%s: deps and Dependencies table disagree" % tool)

    def test_pilot_specs_exist(self):
        for tool in ("mass_reader_s", "titration_s", "pca_s", "features_s"):
            self.assertIn(tool, specs.SPECS)

if __name__ == "__main__":
    unittest.main()
