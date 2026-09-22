import json, os, re, shutil, signal, subprocess, sys, tempfile, time, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import run_bench
import fixtures

ARGS = lambda **kw: __import__("argparse").Namespace(
    **dict({"dry_run": True, "force": False, "timeout": 60, "regrade": False}, **kw))

def _toy_stub(ws):
    open(os.path.join(ws, "make_toy.py"), "w").write("print('wrote toy data')\n")
    open(os.path.join(ws, "toy.py"), "w").write("print('toy stdout')\n")

class RunBenchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        run_bench.RUNS_DIR = os.path.join(self.tmp, "runs")
        run_bench.PI_CMD = os.environ.get("PI_BIN", "pi").split()
        prompt = os.path.join(self.tmp, "toy_prompt.md")
        open(prompt, "w").write("toy prompt\n")
        grader = os.path.join(self.tmp, "toy_grader.py")
        open(grader, "w").write("print('PASS toy out')\nprint('1/1 passed')\n")
        run_bench.SPECS["_toy"] = {
            "prompt": prompt, "gen_cmd": "python3 make_toy.py",
            "run_cmd": "python3 toy.py > stdout.txt", "grader": grader,
            "grader_args": [], "artifacts": ["make_toy.py", "toy.py"],
        }
        fixtures.STUBS["_toy"] = _toy_stub
        self.addCleanup(run_bench.SPECS.pop, "_toy", None)
        self.addCleanup(fixtures.STUBS.pop, "_toy", None)

    def test_dry_run_cell_passes_and_resumes(self):
        state, path = run_bench.run_cell("_toy", "local", 1, ARGS())
        self.assertEqual(state, "passed")
        meta = json.load(open(os.path.join(os.path.dirname(path), "meta.json")))
        self.assertEqual(meta["criteria"], {"toy out": True})
        self.assertEqual(meta["passed"], 1)
        # workspace untouched by grader except outputs of re-executed commands
        self.assertTrue(os.path.isfile(os.path.join(os.path.dirname(path), "workspace", "stdout.txt")))
        state2, _ = run_bench.run_cell("_toy", "local", 1, ARGS())
        self.assertEqual(state2, "skipped")
        state3, _ = run_bench.run_cell("_toy", "local", 1, ARGS(force=True))
        self.assertEqual(state3, "passed")

    def test_dry_run_is_recorded_in_meta(self):
        _, path = run_bench.run_cell("_toy", "local", 1, ARGS())
        meta = json.load(open(os.path.join(os.path.dirname(path), "meta.json")))
        # Without this flag a stub cell -- which delegates to the reference and
        # therefore always scores full marks -- is indistinguishable from a
        # model's cell in report.py and aggregate().
        self.assertIs(meta["dry_run"], True)

    def test_real_run_records_dry_run_false(self):
        run_bench.PI_CMD = [sys.executable, "-c", "print('hi')"]
        _, path = run_bench.run_cell("_toy", "local", 7, ARGS(dry_run=False))
        meta = json.load(open(os.path.join(os.path.dirname(path), "meta.json")))
        self.assertIs(meta["dry_run"], False)

    def test_single_mode_spec_keeps_the_legacy_cell_path(self):
        # The older track's run trees stay valid: no mode segment appears for a
        # spec that declares at most one mode.
        self.assertEqual(run_bench.cell_dir("_toy", "local", 2, "solo"),
                         os.path.join(run_bench.RUNS_DIR, "_toy", "local", "2"))
        run_bench.SPECS["_toy"]["modes"] = ["solo"]
        self.assertEqual(run_bench.cell_dir("_toy", "local", 2, "solo"),
                         os.path.join(run_bench.RUNS_DIR, "_toy", "local", "2"))

    def test_modes_get_separate_cells_and_do_not_overwrite(self):
        """A spec with two modes must not have one mode's results overwrite the
        other's: keying cells on (tool, model, rep) alone already destroyed six
        real features_s prebuilt cells when the solo re-run reused their paths."""
        run_bench.SPECS["_toy"]["modes"] = ["solo", "prebuilt"]
        solo_state, solo_path = run_bench.run_cell(
            "_toy", "local", 1, ARGS(mode="solo"))
        pre_state, pre_path = run_bench.run_cell(
            "_toy", "local", 1, ARGS(mode="prebuilt"))
        self.assertEqual((solo_state, pre_state), ("passed", "passed"))
        self.assertNotEqual(os.path.dirname(solo_path), os.path.dirname(pre_path))
        for path, mode in ((solo_path, "solo"), (pre_path, "prebuilt")):
            meta = json.load(open(os.path.join(os.path.dirname(path), "meta.json")))
            self.assertEqual(meta["mode"], mode)          # both survive
        self.assertTrue(run_bench.aggregate(["_toy"], ["local"], 1, "solo"))
        self.assertTrue(run_bench.aggregate(["_toy"], ["local"], 1, "prebuilt"))
        # and a regrade of one mode finds that mode's cell, not the other's
        state, regraded = run_bench.regrade_cell("_toy", "local", 1, "prebuilt")
        self.assertEqual(state, "passed")
        self.assertEqual(os.path.dirname(regraded), os.path.dirname(pre_path))

    def test_timeout_marks_failure_mode(self):
        run_bench.PI_CMD = [sys.executable, "-c", "import time; time.sleep(30)"]
        state, path = run_bench.run_cell("_toy", "local", 2, ARGS(dry_run=False, timeout=1))
        self.assertEqual(state, "failed")
        meta = json.load(open(os.path.join(os.path.dirname(path), "meta.json")))
        self.assertEqual(meta["failure_mode"], "timeout")

    def test_count_iterations(self):
        ev = os.path.join(self.tmp, "events.jsonl")
        open(ev, "w").write('{"type":"tool_execution_start"}\nnot json\n'
                            '{"type":"tool_execution_start"}\n{"type":"agent_end"}\n')
        self.assertEqual(run_bench.count_iterations(ev), 2)

    def test_parse_verdicts(self):
        v = run_bench.parse_verdicts("PASS a\nFAIL b\n1/2 passed\n")
        self.assertEqual(v, {"a": True, "b": False})

    def test_worker_survives_exception(self):
        run_bench.SPECS["_broken"] = {
            "prompt": os.path.join(self.tmp, "no_such_prompt.md"),
            "gen_cmd": "python3 make_toy.py",
            "run_cmd": "python3 toy.py > stdout.txt", "grader": os.path.join(self.tmp, "toy_grader.py"),
            "grader_args": [], "artifacts": ["make_toy.py", "toy.py"],
        }
        self.addCleanup(run_bench.SPECS.pop, "_broken", None)
        run_bench.worker("local", [("_broken", 1)], ARGS())  # must not raise
        self.assertFalse(run_bench.aggregate(["_broken"], ["local"], 1))
        state, _ = run_bench.run_cell("_toy", "local", 1, ARGS())
        self.assertEqual(state, "passed")
        self.assertTrue(run_bench.aggregate(["_toy"], ["local"], 1))

    def test_timeout_sets_pi_rc_none(self):
        run_bench.PI_CMD = [sys.executable, "-c", "import time; time.sleep(30)"]
        state, path = run_bench.run_cell("_toy", "local", 3, ARGS(dry_run=False, timeout=1))
        self.assertEqual(state, "failed")
        meta = json.load(open(os.path.join(os.path.dirname(path), "meta.json")))
        self.assertEqual(meta["failure_mode"], "timeout")
        self.assertIsNone(meta["pi_rc"])

    def test_timeout_terminates_gracefully_and_preserves_stdout(self):
        # A well-behaved child: prints an UNFLUSHED line (block-buffered,
        # since stdout is redirected to a file, so it only survives if the
        # child gets to run its own shutdown logic) and traps SIGTERM to
        # flush and exit cleanly. If run_cell escalated straight to SIGKILL,
        # neither line would ever reach events.jsonl.
        script = os.path.join(self.tmp, "graceful_child.py")
        open(script, "w").write(
            "import signal, sys, time\n"
            "def handler(signum, frame):\n"
            "    print('GRACEFUL_EXIT', flush=True)\n"
            "    sys.exit(0)\n"
            "signal.signal(signal.SIGTERM, handler)\n"
            "print('STARTED')\n"
            "time.sleep(30)\n"
        )
        run_bench.PI_CMD = [sys.executable, script]
        state, path = run_bench.run_cell(
            "_toy", "local", 4, ARGS(dry_run=False, timeout=1, timeout_grace=3))
        self.assertEqual(state, "failed")
        cell = os.path.dirname(path)
        meta = json.load(open(os.path.join(cell, "meta.json")))
        self.assertEqual(meta["failure_mode"], "timeout")
        self.assertIsNone(meta["pi_rc"])
        events = open(os.path.join(cell, "events.jsonl")).read()
        self.assertIn("STARTED", events)
        self.assertIn("GRACEFUL_EXIT", events)

    def test_regrade_preserves_agent_meta_and_refreshes_verdict(self):
        state, path = run_bench.run_cell("_toy", "local", 1, ARGS())
        self.assertEqual(state, "passed")
        cell = os.path.dirname(path)
        mp = os.path.join(cell, "meta.json")
        agent_meta = json.load(open(mp))
        # Simulate a stale verdict (as if the grader contract had changed).
        stale = dict(agent_meta, criteria={"toy out": False}, passed=0,
                     grader_rc=1, failure_mode="stale")
        json.dump(stale, open(mp, "w"))
        state, _ = run_bench.regrade_cell("_toy", "local", 1)
        self.assertEqual(state, "passed")
        meta = json.load(open(mp))
        self.assertEqual(meta["criteria"], {"toy out": True})
        self.assertEqual(meta["passed"], 1)
        self.assertEqual(meta["grader_rc"], 0)
        self.assertIsNone(meta["failure_mode"])
        for k in run_bench.AGENT_META_FIELDS:
            self.assertEqual(meta[k], agent_meta[k], k)

    def test_regrade_skips_cells_without_artifacts(self):
        state, path = run_bench.run_cell("_toy", "local", 1, ARGS())
        cell = os.path.dirname(path)
        mp = os.path.join(cell, "meta.json")
        os.remove(os.path.join(cell, "workspace", "toy.py"))
        before = open(mp).read()
        self.assertEqual(run_bench.regrade_cell("_toy", "local", 1)[0], "no_artifact")
        self.assertEqual(open(mp).read(), before)      # verdict left untouched
        self.assertEqual(run_bench.regrade_cell("_toy", "local", 9)[0], "no_cell")

    def test_dry_run_chrom_session_stub_passes_c1(self):
        # The dry-run stub writes cell/session.jsonl from fixtures; the chrom
        # grader's c1 must find its evidence in the stub's NON-user text.
        state, path = run_bench.run_cell("chrom", "local", 1, ARGS())
        self.assertEqual(state, "passed")
        meta = json.load(open(os.path.join(os.path.dirname(path), "meta.json")))
        self.assertTrue(meta["criteria"].get("c1 triangle self-check (session)"), meta["criteria"])

    def test_data_files_are_seeded_and_no_gen_cmd_is_required(self):
        import shutil, tempfile
        d = tempfile.mkdtemp(prefix="dataseed_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        src = os.path.join(d, "input.csv")
        open(src, "w").write("a,b\n1,2\n")
        spec = {"data": [src], "seed": [], "deps": []}
        run_bench.seed_workspace(spec, d2 := tempfile.mkdtemp(prefix="ws_"), "solo")
        self.addCleanup(shutil.rmtree, d2, ignore_errors=True)
        self.assertTrue(os.path.isfile(os.path.join(d2, "input.csv")))

    def test_solo_mode_seeds_dependency_prompt_and_data_prebuilt_seeds_module(self):
        import shutil, tempfile
        spec = run_bench.SPECS["features_s"]
        dep_data = [os.path.basename(f) for f in run_bench.SPECS["mass_reader_s"]["data"]]

        # The dependent prompt's own Dependencies table cites the exact
        # repo-relative path the dependency prompt must be reachable at
        # (e.g. "examples/mass_reader/PROMPT.md"). Derive it from the prompt
        # text itself, rather than hardcoding it, so this test keeps proving
        # the fix even if the dependency is renamed.
        dependent_text = open(spec["prompt"]).read()
        cited_paths = re.findall(r"`([\w./-]*PROMPT\.md)`", dependent_text)
        self.assertTrue(cited_paths, "no PROMPT.md path cited in %s" % spec["prompt"])
        cited_rel = cited_paths[0]

        ws_solo = tempfile.mkdtemp(prefix="ws_solo_")
        self.addCleanup(shutil.rmtree, ws_solo, ignore_errors=True)
        run_bench.seed_workspace(spec, ws_solo, "solo")
        # dependency's own prompt, so the agent can build the module and check
        # that prompt's criteria itself -- seeded at the repo-relative path
        # the dependent prompt actually cites, not at the workspace root.
        seeded_prompt = os.path.join(ws_solo, "examples", "mass_reader", "PROMPT.md")
        self.assertTrue(os.path.isfile(seeded_prompt))
        self.assertIn("Already in the working directory", open(seeded_prompt).read())
        # pins the property the fix is about: the literal path cited in the
        # dependent prompt's Dependencies table must resolve inside the
        # seeded solo workspace.
        self.assertTrue(os.path.isfile(os.path.join(ws_solo, cited_rel)), cited_rel)
        # and the dependency's three real input files, not just its prompt
        for name in dep_data:
            self.assertTrue(os.path.isfile(os.path.join(ws_solo, name)), name)
        self.assertFalse(os.path.isfile(os.path.join(ws_solo, "mzml_reader.py")))
        # no stray copy at the (now-wrong) workspace root either
        self.assertFalse(os.path.isfile(os.path.join(ws_solo, "PROMPT.md")))

        ws_prebuilt = tempfile.mkdtemp(prefix="ws_prebuilt_")
        self.addCleanup(shutil.rmtree, ws_prebuilt, ignore_errors=True)
        run_bench.seed_workspace(spec, ws_prebuilt, "prebuilt")
        # tested module supplied directly, prompt/data NOT seeded -- at
        # either the old root location or the new repo-relative one.
        self.assertTrue(os.path.isfile(os.path.join(ws_prebuilt, "mzml_reader.py")))
        self.assertFalse(os.path.isfile(os.path.join(ws_prebuilt, "PROMPT.md")))
        self.assertFalse(os.path.isfile(
            os.path.join(ws_prebuilt, "examples", "mass_reader", "PROMPT.md")))
        for name in dep_data:
            self.assertFalse(os.path.isfile(os.path.join(ws_prebuilt, name)), name)

    def test_reexecute_skips_a_missing_gen_cmd(self):
        import tempfile
        ws = tempfile.mkdtemp(prefix="ws_")
        meta = {"failure_mode": None}
        run_bench.reexecute_commands({"run_cmd": "true"}, ws, meta)   # no gen_cmd key
        self.assertIsNone(meta["failure_mode"])

    def _data_restore_spec(self, name, src):
        # A minimal spec whose run_cmd echoes the harness-owned data file's
        # current bytes into an output file, so the test can see exactly what
        # the pinned command actually read at re-execution time.
        prompt = os.path.join(self.tmp, "%s_prompt.md" % name)
        open(prompt, "w").write("prompt\n")
        grader = os.path.join(self.tmp, "%s_grader.py" % name)
        open(grader, "w").write("print('PASS ok')\nprint('1/1 passed')\n")
        spec = {
            "prompt": prompt, "data": [src], "run_cmd": "python3 process.py",
            "grader": grader, "grader_args": [], "artifacts": ["process.py"],
        }
        run_bench.SPECS[name] = spec
        self.addCleanup(run_bench.SPECS.pop, name, None)
        return spec

    def test_run_cell_restores_an_overwritten_data_file_before_rerun(self):
        import shutil, tempfile
        d = tempfile.mkdtemp(prefix="dataoverwrite_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        src = os.path.join(d, "input.csv")
        open(src, "w").write("original\n")
        self._data_restore_spec("_dataoverwrite", src)

        def stub(ws):
            open(os.path.join(ws, "process.py"), "w").write(
                "import shutil\nshutil.copy('input.csv', 'echoed.csv')\n")
            # the agent tampers with the harness-owned input in place, same basename
            open(os.path.join(ws, "input.csv"), "w").write("corrupted-by-agent\n")
        fixtures.STUBS["_dataoverwrite"] = stub
        self.addCleanup(fixtures.STUBS.pop, "_dataoverwrite", None)

        state, path = run_bench.run_cell("_dataoverwrite", "local", 1, ARGS())
        self.assertEqual(state, "passed")
        ws = os.path.join(os.path.dirname(path), "workspace")
        self.assertEqual(open(os.path.join(ws, "echoed.csv")).read(), "original\n")

    def test_run_cell_restores_a_deleted_data_file_before_rerun(self):
        import shutil, tempfile
        d = tempfile.mkdtemp(prefix="datadelete_")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        src = os.path.join(d, "input.csv")
        open(src, "w").write("original\n")
        self._data_restore_spec("_datadelete", src)

        def stub(ws):
            open(os.path.join(ws, "process.py"), "w").write(
                "import shutil\nshutil.copy('input.csv', 'echoed.csv')\n")
            os.remove(os.path.join(ws, "input.csv"))   # the agent deletes the input outright
        fixtures.STUBS["_datadelete"] = stub
        self.addCleanup(fixtures.STUBS.pop, "_datadelete", None)

        state, path = run_bench.run_cell("_datadelete", "local", 1, ARGS())
        self.assertEqual(state, "passed")
        ws = os.path.join(os.path.dirname(path), "workspace")
        self.assertEqual(open(os.path.join(ws, "echoed.csv")).read(), "original\n")


class PiModelArgsTest(unittest.TestCase):
    """pi's --model reserves ':' as a thinking-level separator, so a model id
    containing a literal colon (e.g. an OpenRouter id like
    "minimax/minimax-m3:free") must be passed via a separate --provider
    argument plus the bare model id instead of the combined "provider/model"
    form. A mirror with provider_flag set gets that treatment; every other
    mirror keeps today's combined form unchanged."""

    def test_provider_flag_model_gets_separate_provider_and_model_args(self):
        mirror = {"provider": "openrouter", "model": "minimax/minimax-m3:free",
                   "endpoint": "https://openrouter.ai/api/v1", "provider_flag": True}
        self.assertEqual(run_bench.pi_model_args(mirror),
                          ["--provider", "openrouter", "--model", "minimax/minimax-m3:free"])

    def test_normal_model_gets_the_combined_provider_slash_model_form(self):
        mirror = {"provider": "remote-vllm", "model": "Qwen/Qwen3.8-27B-FP8",
                   "endpoint": "http://vllm-host:8000/v1"}
        self.assertEqual(run_bench.pi_model_args(mirror),
                          ["--model", "remote-vllm/Qwen/Qwen3.8-27B-FP8"])


def _proc_gone(pid):
    """True once `pid` is no longer a running process -- ESRCH, or a zombie
    (state contains 'Z') that has exited but not yet been reaped by init."""
    r = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return True
    state = r.stdout.strip()
    return (not state) or ("Z" in state)

def _wait_until_gone(pids, timeout=10):
    deadline = time.time() + timeout
    while True:
        if all(_proc_gone(p) for p in pids):
            return True
        if time.time() >= deadline:
            return False
        time.sleep(0.2)

def _wait_for_pidfile(path, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            try:
                return int(open(path).read().strip())
            except ValueError:
                pass
        time.sleep(0.1)
    raise AssertionError("pidfile %s never appeared" % path)

def _safe_kill(pid, sig=signal.SIGKILL):
    try:
        os.kill(pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


class TerminationCleanupTest(unittest.TestCase):
    """Orphan-prevention fix: run_bench.py used to leave a detached `pi`
    session (and its own children) running forever if the harness itself
    was killed rather than timing out a cell -- observed directly as a `pi`
    process that outlived a killed run by 1h21m, still appending to a
    replacement run's events.jsonl. These tests exercise the real fix:
    cleanup_tracked_pgids / install_termination_handlers / the pgid
    tracking in run_cell -- against real child processes, not just
    bookkeeping."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="orphan_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        # run_bench._live_pgids is process-global state; make sure a failed
        # assertion in one test can't leak a tracked pgid into another.
        self.addCleanup(run_bench._live_pgids.clear)
        old_runs_dir = run_bench.RUNS_DIR
        run_bench.RUNS_DIR = os.path.join(self.tmp, "runs")   # never bench/runs/
        self.addCleanup(setattr, run_bench, "RUNS_DIR", old_runs_dir)
        prompt = os.path.join(self.tmp, "toy_prompt.md")
        open(prompt, "w").write("toy prompt\n")
        grader = os.path.join(self.tmp, "toy_grader.py")
        open(grader, "w").write("print('PASS toy out')\nprint('1/1 passed')\n")
        run_bench.SPECS["_toy"] = {
            "prompt": prompt, "gen_cmd": "python3 make_toy.py",
            "run_cmd": "python3 toy.py > stdout.txt", "grader": grader,
            "grader_args": [], "artifacts": ["make_toy.py", "toy.py"],
        }
        fixtures.STUBS["_toy"] = _toy_stub
        self.addCleanup(run_bench.SPECS.pop, "_toy", None)
        self.addCleanup(fixtures.STUBS.pop, "_toy", None)

    def test_cleanup_tracked_pgids_terminates_a_well_behaved_group(self):
        script = os.path.join(self.tmp, "graceful.py")
        open(script, "w").write(
            "import signal, sys, time\n"
            "signal.signal(signal.SIGTERM, lambda n, f: sys.exit(0))\n"
            "time.sleep(30)\n")
        proc = subprocess.Popen([sys.executable, script], start_new_session=True)
        self.addCleanup(_safe_kill, proc.pid)
        pgid = os.getpgid(proc.pid)
        run_bench._track_pgid(pgid)
        run_bench.cleanup_tracked_pgids(grace=3)
        self.assertTrue(_wait_until_gone([proc.pid], timeout=5))
        self.assertNotIn(pgid, run_bench._live_pgids)

    def test_cleanup_tracked_pgids_escalates_to_sigkill_after_grace(self):
        # Ignores SIGTERM outright, so only the SIGKILL escalation can end it.
        script = os.path.join(self.tmp, "stubborn.py")
        open(script, "w").write(
            "import signal, time\n"
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            "time.sleep(30)\n")
        proc = subprocess.Popen([sys.executable, script], start_new_session=True)
        self.addCleanup(_safe_kill, proc.pid)
        pgid = os.getpgid(proc.pid)
        run_bench._track_pgid(pgid)
        run_bench.cleanup_tracked_pgids(grace=1)
        self.assertTrue(_wait_until_gone([proc.pid], timeout=5))
        self.assertNotIn(pgid, run_bench._live_pgids)

    def test_cleanup_tracked_pgids_kills_the_whole_group_including_grandchildren(self):
        gc_script = os.path.join(self.tmp, "grandchild.py")
        open(gc_script, "w").write(
            "import os, sys, time\n"
            "open(sys.argv[1], 'w').write(str(os.getpid()))\n"
            "time.sleep(30)\n")
        pidfile = os.path.join(self.tmp, "gc.pid")
        parent_script = os.path.join(self.tmp, "parent.py")
        open(parent_script, "w").write(
            "import subprocess, sys, time\n"
            "subprocess.Popen([sys.executable, %r, %r])\n"
            "time.sleep(30)\n" % (gc_script, pidfile))
        proc = subprocess.Popen([sys.executable, parent_script], start_new_session=True)
        self.addCleanup(_safe_kill, proc.pid)
        gc_pid = _wait_for_pidfile(pidfile)
        self.addCleanup(_safe_kill, gc_pid)
        pgid = os.getpgid(proc.pid)
        run_bench._track_pgid(pgid)
        run_bench.cleanup_tracked_pgids(grace=3)
        self.assertTrue(_wait_until_gone([proc.pid, gc_pid], timeout=5))

    def test_run_cell_untracks_pgid_after_normal_completion(self):
        # A "real" (non-dry) pi stand-in that actually writes the tool's
        # artifacts, so this exercises the same pass-through-the-grader
        # path a genuine run would, with the new tracking code active.
        run_bench.PI_CMD = [sys.executable, "-c",
            "open('make_toy.py','w').write(\"print('wrote toy data')\\n\"); "
            "open('toy.py','w').write(\"print('toy stdout')\\n\")"]
        state, _ = run_bench.run_cell("_toy", "local", 5, ARGS(dry_run=False))
        self.assertEqual(state, "passed")
        self.assertEqual(run_bench._live_pgids, set())

    def test_run_cell_untracks_pgid_after_timeout(self):
        run_bench.PI_CMD = [sys.executable, "-c", "import time; time.sleep(30)"]
        state, _ = run_bench.run_cell("_toy", "local", 6, ARGS(dry_run=False, timeout=1))
        self.assertEqual(state, "failed")
        self.assertEqual(run_bench._live_pgids, set())

    def test_sigterm_to_harness_process_leaves_no_orphaned_descendant(self):
        """End-to-end demonstration of the actual fix. Launches a separate
        driver *process* that calls run_bench.run_cell with a fake `pi`
        that itself spawns a grandchild, then sends SIGTERM to exactly the
        pid this test launched and captured (never a name/pattern match --
        that would risk any other run_bench.py or pi process on the
        machine). Confirms neither the fake pi nor its grandchild survives,
        and that the interrupted cell is left with no meta.json rather than
        looking like a normal result."""
        bench_dir = run_bench.BENCH
        tmp = self.tmp
        runs_dir = os.path.join(tmp, "runs")

        gc_script = os.path.join(tmp, "grandchild.py")
        open(gc_script, "w").write(
            "import os, sys, time\n"
            "open(sys.argv[1], 'w').write(str(os.getpid()))\n"
            "time.sleep(60)\n")

        pi_pidfile = os.path.join(tmp, "pi.pid")
        gc_pidfile = os.path.join(tmp, "pi_gc.pid")
        fake_pi = os.path.join(tmp, "fake_pi.py")
        open(fake_pi, "w").write(
            "import os, subprocess, sys, time\n"
            "open(sys.argv[1], 'w').write(str(os.getpid()))\n"
            "subprocess.Popen([sys.executable, sys.argv[3], sys.argv[2]])\n"
            "print('PI_STARTED', flush=True)\n"
            "time.sleep(60)\n")

        prompt = os.path.join(tmp, "prompt.md")
        open(prompt, "w").write("toy prompt\n")
        grader = os.path.join(tmp, "grader.py")
        open(grader, "w").write("print('PASS ok')\nprint('1/1 passed')\n")

        driver = os.path.join(tmp, "driver.py")
        open(driver, "w").write(
            "import argparse, sys\n"
            "sys.path.insert(0, %r)\n"
            "import run_bench\n"
            "run_bench.RUNS_DIR = %r\n"
            "run_bench.PI_CMD = [sys.executable, %r, %r, %r, %r]\n"
            "run_bench.SPECS['_toy'] = {\n"
            "    'prompt': %r, 'run_cmd': 'true', 'grader': %r,\n"
            "    'grader_args': [], 'artifacts': [],\n"
            "}\n"
            "run_bench.install_termination_handlers()\n"
            "args = argparse.Namespace(dry_run=False, force=False, timeout=120,\n"
            "                          timeout_grace=3, regrade=False, mode='solo')\n"
            "run_bench.run_cell('_toy', 'local', 1, args)\n"
            % (bench_dir, runs_dir, fake_pi, pi_pidfile, gc_pidfile, gc_script,
               prompt, grader))

        driver_proc = subprocess.Popen([sys.executable, driver],
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True)
        self.addCleanup(_safe_kill, driver_proc.pid)

        pi_pid = _wait_for_pidfile(pi_pidfile)
        gc_pid = _wait_for_pidfile(gc_pidfile)
        self.addCleanup(_safe_kill, pi_pid)
        self.addCleanup(_safe_kill, gc_pid)

        before = subprocess.run(
            ["ps", "-o", "pid,ppid,pgid,stat,command",
             "-p", "%d,%d,%d" % (driver_proc.pid, pi_pid, gc_pid)],
            capture_output=True, text=True).stdout
        print("\n--- ps BEFORE SIGTERM ---\n" + before)
        self.assertFalse(_proc_gone(driver_proc.pid))
        self.assertFalse(_proc_gone(pi_pid))
        self.assertFalse(_proc_gone(gc_pid))

        os.kill(driver_proc.pid, signal.SIGTERM)   # only this captured pid
        driver_proc.wait(timeout=15)

        gone = _wait_until_gone([pi_pid, gc_pid], timeout=10)
        after = subprocess.run(
            ["ps", "-o", "pid,ppid,pgid,stat,command", "-p", "%d,%d" % (pi_pid, gc_pid)],
            capture_output=True, text=True)
        print("\n--- ps AFTER SIGTERM+cleanup ---\n" +
              (after.stdout if after.stdout.strip() != "" else "(no matching processes -- both gone)\n"))

        self.assertTrue(gone, "pi and/or its child survived the harness's own termination")
        self.assertFalse(os.path.isfile(
            os.path.join(runs_dir, "_toy", "local", "1", "meta.json")),
            "an interrupted cell must not be left looking complete")


if __name__ == "__main__":
    unittest.main()
