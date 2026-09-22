"""Endpoint-mirror support: model_mirrors(), the cell-partition property
across a model's mirrors, and meta.json recording the mirror that actually
served each cell -- not a base/model-key value."""
import json, os, sys, tempfile, threading, time, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import run_bench
import specs
import fixtures

ARGS = lambda **kw: __import__("argparse").Namespace(
    **dict({"dry_run": True, "force": False, "timeout": 60, "regrade": False}, **kw))


class ModelMirrorsTest(unittest.TestCase):
    """model_mirrors() is a dispatch mechanism: given a model_key it must
    hand back that model's interchangeable endpoints (or, for a model with
    no "mirrors" entry, a single-element list of itself). These tests build
    their own fixture model keys rather than asserting on whatever bench/
    specs.py's live MODELS dict happens to wire up today -- how many
    endpoints "local" actually has is an infrastructure fact, not something
    the mechanism should be judged against, and a routine hardware change
    (an endpoint's model file swapped, a mirror added or removed) must not
    turn this test red."""

    def setUp(self):
        specs.MODELS["_fixture_mirrored"] = {
            "provider": "p0", "model": "m0", "endpoint": "http://ep0",
            "mirrors": [
                {"provider": "p0", "model": "m0", "endpoint": "http://ep0"},
                {"provider": "p1", "model": "m1", "endpoint": "http://ep1"},
            ],
        }
        specs.MODELS["_fixture_unmirrored"] = {
            "provider": "p", "model": "m", "endpoint": "http://ep",
        }
        self.addCleanup(specs.MODELS.pop, "_fixture_mirrored", None)
        self.addCleanup(specs.MODELS.pop, "_fixture_unmirrored", None)

    def test_mirrored_model_exposes_its_two_distinct_mirrors(self):
        mirrors = specs.model_mirrors("_fixture_mirrored")
        self.assertEqual(len(mirrors), 2)
        self.assertEqual(len({m["endpoint"] for m in mirrors}), 2)
        self.assertEqual(len({m["provider"] for m in mirrors}), 2)
        for m in mirrors:
            self.assertEqual(set(m), {"provider", "model", "endpoint"})
        self.assertEqual(mirrors, specs.MODELS["_fixture_mirrored"]["mirrors"])

    def test_local_base_fields_match_its_first_mirror(self):
        # MODELS["local"]'s own provider/model/endpoint are derived from
        # _LOCAL_MIRRORS[0], not hand-duplicated, so they cannot drift apart.
        # This checks a structural relationship (base == mirrors[0]), not
        # any particular endpoint value, so it is unaffected by which model
        # "local" actually serves today.
        base = specs.MODELS["local"]
        first = specs.model_mirrors("local")[0]
        self.assertEqual(base["provider"], first["provider"])
        self.assertEqual(base["model"], first["model"])
        self.assertEqual(base["endpoint"], first["endpoint"])

    def test_unmirrored_model_gets_a_single_element_list_of_itself(self):
        # A model with no "mirrors" entry: behaviour must be exactly as
        # before mirrors existed -- one endpoint, built from its own fields.
        self.assertNotIn("mirrors", specs.MODELS["_fixture_unmirrored"])
        mirrors = specs.model_mirrors("_fixture_unmirrored")
        self.assertEqual(mirrors, [{"provider": "p", "model": "m", "endpoint": "http://ep"}])


class MirrorsShareOneModelIdTest(unittest.TestCase):
    """Live-config guard: every endpoint listed under one model key's
    "mirrors" must serve the same model id. Two endpoints serving different
    models must never be paired -- run_bench.worker() distributes a model's
    cells across its mirrors assuming they are interchangeable, so pairing
    mismatched models would silently send some cells' worth of results to
    the wrong model. This is exactly what nearly happened when
    old-llm-host:35188 was repointed at an unrelated 1.2B document-parsing
    model instead of remaining a mirror of "local"; with only one mirror
    left, this test passes trivially, but it would have failed loudly had
    the stale pairing been left in place."""

    def test_every_configured_models_mirrors_serve_one_model_id(self):
        for model_key in specs.MODELS:
            mirrors = specs.model_mirrors(model_key)
            model_ids = {m["model"] for m in mirrors}
            self.assertEqual(len(model_ids), 1,
                "%r mirrors serve different models: %s" % (model_key, sorted(model_ids)))


class RunCellRecordsServingMirrorTest(unittest.TestCase):
    """A model without mirrors must behave exactly as before mirrors existed,
    and a cell run against an explicit mirror must record THAT mirror in
    meta.json, not MODELS[model_key]'s own values."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        run_bench.RUNS_DIR = os.path.join(self.tmp, "runs")
        prompt = os.path.join(self.tmp, "toy_prompt.md")
        open(prompt, "w").write("toy prompt\n")
        grader = os.path.join(self.tmp, "toy_grader.py")
        open(grader, "w").write("print('PASS toy out')\nprint('1/1 passed')\n")
        run_bench.SPECS["_toymirror"] = {
            "prompt": prompt, "gen_cmd": "python3 make_toy.py",
            "run_cmd": "python3 toy.py > stdout.txt", "grader": grader,
            "grader_args": [], "artifacts": ["make_toy.py", "toy.py"],
        }
        fixtures.STUBS["_toymirror"] = lambda ws: (
            open(os.path.join(ws, "make_toy.py"), "w").write("print('wrote toy data')\n"),
            open(os.path.join(ws, "toy.py"), "w").write("print('toy stdout')\n"))
        self.addCleanup(run_bench.SPECS.pop, "_toymirror", None)
        self.addCleanup(fixtures.STUBS.pop, "_toymirror", None)

        specs.MODELS["_fixture_mirrored"] = {
            "provider": "p0", "model": "m0", "endpoint": "http://ep0",
            "mirrors": [
                {"provider": "p0", "model": "m0", "endpoint": "http://ep0"},
                {"provider": "p1", "model": "m1", "endpoint": "http://ep1"},
            ],
        }
        self.addCleanup(specs.MODELS.pop, "_fixture_mirrored", None)

    def test_no_mirror_argument_falls_back_to_the_model_keys_own_endpoint(self):
        # Exactly today's behaviour: run_cell called the old way (no mirror
        # argument) must still record MODELS[model_key]'s own model/endpoint.
        _, path = run_bench.run_cell("_toymirror", "local", 1, ARGS())
        meta = json.load(open(os.path.join(os.path.dirname(path), "meta.json")))
        self.assertEqual(meta["model_id"], specs.MODELS["local"]["model"])
        self.assertEqual(meta["endpoint"], specs.MODELS["local"]["endpoint"])

    def test_explicit_mirror_is_recorded_instead_of_the_base_model_values(self):
        second = specs.model_mirrors("_fixture_mirrored")[1]
        # Sanity: the mirror under test really does differ from the base
        # entry -- otherwise this test could pass for the wrong reason.
        base = specs.MODELS["_fixture_mirrored"]
        self.assertNotEqual(second["endpoint"], base["endpoint"])
        self.assertNotEqual(second["model"], base["model"])

        _, path = run_bench.run_cell("_toymirror", "_fixture_mirrored", 2, ARGS(), mirror=second)
        meta = json.load(open(os.path.join(os.path.dirname(path), "meta.json")))
        self.assertEqual(meta["model_id"], second["model"])
        self.assertEqual(meta["endpoint"], second["endpoint"])


class MirrorPartitionTest(unittest.TestCase):
    """Proves the partition property run_bench.worker must uphold: every cell
    assigned to a model key is run exactly once, distributed across that
    model's mirrors, with never more than one cell in flight per mirror."""

    def setUp(self):
        specs.MODELS["_mirrortest"] = {
            "provider": "p0", "model": "m0", "endpoint": "http://ep0",
            "mirrors": [
                {"provider": "p0", "model": "m0", "endpoint": "http://ep0"},
                {"provider": "p1", "model": "m1", "endpoint": "http://ep1"},
                {"provider": "p2", "model": "m2", "endpoint": "http://ep2"},
            ],
        }
        self.addCleanup(specs.MODELS.pop, "_mirrortest", None)
        self.orig_run_cell = run_bench.run_cell
        self.addCleanup(setattr, run_bench, "run_cell", self.orig_run_cell)

    def test_cells_partition_across_mirrors_with_no_double_booking(self):
        cells = [("t%d" % i, r) for i in range(4) for r in (1, 2)]   # 8 cells, 3 mirrors
        active = set()
        lock = threading.Lock()
        calls = []
        violations = []
        high_water = [0]

        def fake_run_cell(tool, model_key, rep, args, mirror=None):
            ep = mirror["endpoint"]
            with lock:
                if ep in active:
                    violations.append((ep, tool, rep))   # two cells on one mirror at once
                active.add(ep)
                high_water[0] = max(high_water[0], len(active))
            time.sleep(0.05)   # force overlap between threads
            with lock:
                active.discard(ep)
                calls.append((tool, rep, ep))
            return "passed", "/dev/null"

        run_bench.run_cell = fake_run_cell
        run_bench.worker("_mirrortest", cells, ARGS(dry_run=True))

        # Partition: every cell claimed exactly once, none dropped, none duplicated.
        self.assertEqual(sorted((t, r) for t, r, _ in calls), sorted(cells))
        self.assertEqual(len(calls), len(cells))
        # No mirror was ever handed a second cell while still busy with one.
        self.assertEqual(violations, [])
        # Real concurrency actually happened, bounded by the mirror count.
        self.assertGreater(high_water[0], 1)
        self.assertLessEqual(high_water[0], 3)
        # All three mirrors were put to work.
        self.assertEqual({ep for _, _, ep in calls}, {"http://ep0", "http://ep1", "http://ep2"})

    def test_worker_still_works_for_a_model_with_no_mirrors(self):
        # "_toy"-style single-endpoint model: worker must still run every
        # cell exactly once, single-threaded, same as before mirrors existed.
        specs.MODELS["_nomirror"] = {"provider": "p", "model": "m", "endpoint": "http://ep"}
        self.addCleanup(specs.MODELS.pop, "_nomirror", None)
        cells = [("t%d" % i, 1) for i in range(5)]
        calls = []

        def fake_run_cell(tool, model_key, rep, args, mirror=None):
            calls.append((tool, rep, mirror["endpoint"]))
            return "passed", "/dev/null"

        run_bench.run_cell = fake_run_cell
        run_bench.worker("_nomirror", cells, ARGS(dry_run=True))
        self.assertEqual(sorted((t, r) for t, r, _ in calls), sorted(cells))
        self.assertEqual(len(calls), len(cells))
        self.assertTrue(all(ep == "http://ep" for _, _, ep in calls))


class RegradeDoesNotAcquireMirrorsTest(unittest.TestCase):
    def test_regrade_worker_never_looks_up_the_model_key_in_MODELS(self):
        # A model key entirely absent from specs.MODELS: if the --regrade
        # path touched MODELS/model_mirrors for it at all, this would raise
        # KeyError. regrade_cell only reads bench/runs; here there is no
        # such cell, so the call must complete quietly with "no_cell".
        self.assertNotIn("_ghost_model", specs.MODELS)
        run_bench.worker("_ghost_model", [("calibration_s", 999)],
                          ARGS(regrade=True))   # must not raise


if __name__ == "__main__":
    unittest.main()
