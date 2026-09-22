#!/usr/bin/env python3
"""Tier (a) benchmark orchestrator: one fresh pi session per cell, external grading."""
import argparse, atexit, hashlib, json, os, queue, shutil, signal, subprocess, sys, threading, time, traceback
from concurrent.futures import ThreadPoolExecutor

BENCH = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BENCH)
from specs import SPECS, MODELS, REPO, model_mirrors
import venv_setup
sys.path.insert(0, os.path.join(BENCH, "tests"))
import fixtures

RUNS_DIR = os.path.join(BENCH, "runs")
# Modules a dependency supplies, seeded in prebuilt mode.
DEP_MODULES = {"mass_reader": ["fasta_reader.py", "mzml_reader.py", "mgf_reader.py"],
               "mass_reader_s": ["fasta_reader.py", "mzml_reader.py"]}
PI_CMD = os.environ.get("PI_BIN", "pi").split()

# Dry-run session transcripts. Real runs get {cell}/session.jsonl from pi's
# --session flag; chrom's grader reads it for the agent self-check (c1), so the
# dry-run stub must stand in for that transcript too. No other grader reads one.
SESSION_STUBS = {"chrom": fixtures.CHROM_SESSION}

LIB = os.path.join(BENCH, "reference", "lib")

# --- Orphan-prevention: track every `pi` process group the harness has live,
# so that if run_bench.py itself is torn down (SIGINT/SIGTERM, an uncaught
# exception, sys.exit) rather than a cell timing out, those detached
# sessions get cleaned up instead of surviving as orphans reparented to
# init. `pi` is spawned with start_new_session=True so the *timeout* path
# can os.killpg its whole group (children of children go down with it);
# that is deliberate and unchanged. This registry exists only to reach the
# same groups from a second trigger: the harness's own termination, not a
# per-cell timeout. Cells run concurrently (one worker per model/mirror),
# so the registry is a plain set behind a lock.
_live_pgids_lock = threading.Lock()
_live_pgids = set()
# Grace period cleanup gives a tracked group after SIGTERM before escalating
# to SIGKILL -- the same courtesy the per-cell timeout path already uses, so
# a harness-level kill doesn't destroy the events.jsonl evidence that grace
# period was added to preserve. main() overwrites this from --timeout-grace.
CLEANUP_GRACE = 8

def _track_pgid(pgid):
    with _live_pgids_lock:
        _live_pgids.add(pgid)

def _untrack_pgid(pgid):
    with _live_pgids_lock:
        _live_pgids.discard(pgid)

def _pgid_alive(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False

def cleanup_tracked_pgids(grace=None):
    """Terminate every `pi` process group still tracked when the harness is
    being torn down early. Same courtesy as the per-cell timeout path:
    SIGTERM to each group, a grace period for pi to flush its buffered
    events.jsonl, then SIGKILL only for stragglers -- an immediate SIGKILL
    would destroy exactly the evidence that grace period exists to
    preserve. Registered with atexit (covers an uncaught exception or
    sys.exit unwinding through normal interpreter shutdown) and also called
    explicitly by the signal handler below, since the default SIGINT/SIGTERM
    disposition terminates the process without running atexit handlers at
    all.

    Other worker threads are not paused while this runs, so a cell can start
    a brand-new `pi` (and track a brand-new pgid) *during* the grace period
    -- a plain one-shot snapshot at entry would miss it and leave it
    orphaned exactly like the bug this function exists to close. Re-scan
    _live_pgids on every iteration of the wait loop and SIGTERM anything new
    as soon as it's seen, so lateness only costs that group its full grace
    window, never the courtesy itself.
    """
    if grace is None:
        grace = CLEANUP_GRACE
    signaled = set()

    def _sigterm_new():
        with _live_pgids_lock:
            todo = set(_live_pgids) - signaled
        for pgid in todo:
            try:
                os.killpg(pgid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        signaled.update(todo)
        return todo

    _sigterm_new()
    if not signaled:
        return
    deadline = time.time() + grace
    while time.time() < deadline:
        _sigterm_new()
        signaled = {p for p in signaled if _pgid_alive(p)}
        if not signaled:
            break
        time.sleep(0.1)
    _sigterm_new()   # last chance to catch anything tracked mid-loop
    for pgid in signaled:
        if _pgid_alive(pgid):
            try:
                os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
    with _live_pgids_lock:
        _live_pgids.clear()

atexit.register(cleanup_tracked_pgids)

def _handle_termination_signal(signum, frame):
    """Installed on the harness process itself (never on `pi`, whose own
    session is untouched). Cleans up every tracked child group with the
    timeout path's grace-period courtesy, then restores the default
    disposition and re-raises the same signal to this process so it still
    dies from that signal (correct exit status; nothing is swallowed)."""
    cleanup_tracked_pgids()
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)

def install_termination_handlers():
    """Install SIGINT/SIGTERM handlers that clean up tracked pi process
    groups before the harness process dies. Called by main(); kept separate
    so a test (or an in-process demonstration) can install the same
    handlers on a driver process without going through argparse."""
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _handle_termination_signal)

def pi_model_args(mirror):
    """The pi CLI arguments that select `mirror`'s provider/model.

    pi's --model reserves ':' as a thinking-level separator ("provider/id"
    with an optional ":<thinking>" suffix), so a model id that itself
    contains a literal colon -- e.g. an OpenRouter id like
    "minimax/minimax-m3:free" -- gets misparsed by the combined
    "provider/model" form. A mirror with provider_flag set is addressed
    instead with a separate --provider argument and the bare model id;
    every other mirror keeps today's combined "provider/model" form
    unchanged."""
    if mirror.get("provider_flag"):
        return ["--provider", mirror["provider"], "--model", mirror["model"]]
    return ["--model", "%s/%s" % (mirror["provider"], mirror["model"])]

def seed_workspace(spec, ws, mode):
    """Place everything the agent is entitled to find before it starts.

    Always: the data generator(s), which ship beside the prompt since Phase 1.
    solo:     the dependency's prompt, generator and data files, so the agent
              can build the module itself and check that prompt's criteria
              against the same real inputs its own workspace would have.
    prebuilt: tested modules from bench/reference/lib, which the agent must import
              unedited. Returns their sha256 so a rewrite can be detected.
    Short track: the real input files named by spec["data"].
    """
    for f in spec.get("seed", []):
        shutil.copy2(f, ws)
    for f in spec.get("data", []):          # short track: real inputs, no generator
        shutil.copy2(f, ws)
    dep_shas = {}
    for dep in spec.get("deps", []):
        dspec = SPECS.get(dep)
        if mode == "prebuilt":
            for mod in DEP_MODULES.get(dep, []):
                src = os.path.join(LIB, mod)
                shutil.copy2(src, ws)
                dep_shas[mod] = sha256_file(src)
        else:
            if dspec:
                # Place the dependency prompt at the same repo-relative path
                # its citation in the dependent prompt's Dependencies table
                # uses (e.g. "examples/mass_reader/PROMPT.md"), not at the
                # workspace root -- a bare PROMPT.md there is both unresolvable
                # by that literal path and ambiguous with the agent's own task
                # prompt.
                rel = os.path.relpath(dspec["prompt"], REPO)
                dst = os.path.join(ws, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(dspec["prompt"], dst)
                for f in dspec.get("seed", []):
                    shutil.copy2(f, ws)
                for f in dspec.get("data", []):  # short track: real inputs
                    shutil.copy2(f, ws)
    return dep_shas


def check_dep_reuse(ws, dep_shas, meta):
    """prebuilt only: a seeded module that changed was rewritten, not reused."""
    edited = [m for m, h in dep_shas.items()
              if not os.path.isfile(os.path.join(ws, m))
              or sha256_file(os.path.join(ws, m)) != h]
    meta["deps_reused"] = not edited
    meta["deps_edited"] = edited
    if edited and meta["failure_mode"] is None:
        meta["failure_mode"] = "dep_modified(%s)" % ",".join(edited)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def parse_verdicts(text):
    verdicts = {}
    for line in text.splitlines():
        if line.startswith(("PASS ", "FAIL ")):
            verdicts[line[5:]] = line.startswith("PASS ")
    return verdicts

def count_iterations(events_path):
    n = 0
    if os.path.isfile(events_path):
        with open(events_path, errors="replace") as fh:
            for line in fh:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict) and obj.get("type") == "tool_execution_start":
                    n += 1
    return n

def cell_dir(tool, model_key, rep, mode="solo"):
    """Path of one cell. The mode segment appears only for specs that declare
    more than one entry in "modes": a single-mode spec keeps the historical
    <tool>/<model>/<rep> layout, so the older track's run trees stay valid,
    while features_s (solo + prebuilt) can no longer have one mode's results
    silently overwrite the other's -- which already destroyed six real cells."""
    spec = SPECS.get(tool) or {}
    parts = [RUNS_DIR, tool]
    if len(spec.get("modes") or []) > 1:
        parts.append(mode)
    return os.path.join(*(parts + [model_key, str(rep)]))


def grader_path(spec):
    g = spec["grader"]
    return g if os.path.isabs(g) else os.path.join(BENCH, "graders", g)

def restore_data_files(spec, ws):
    """Data files are harness-owned inputs, never agent artifacts. Restore them
    unconditionally (plain overwrite) so an agent that edited or replaced an
    input in place -- same basename, still present -- can't drag a grader's
    reference computation along with its own output. Call this right before
    re-executing the pinned commands, in both the live and offline paths."""
    for f in spec.get("data", []):
        shutil.copy2(f, ws)

def reexecute_commands(spec, ws, meta):
    """Re-run the pinned gen/run commands in ws; tag meta on hang (guarded)."""
    for command in [c for c in (spec.get("gen_cmd"), spec["run_cmd"]) if c]:
        try:
            subprocess.run(command, shell=True, cwd=ws, timeout=600,
                           stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        except subprocess.TimeoutExpired:
            if meta["failure_mode"] is None:
                meta["failure_mode"] = "tool_hang"
            break

def run_grader(spec, cell, ws, meta, grade_path):
    """Run the external grader, write grade.txt, fill criteria/passed/total."""
    g_stdout = ""
    try:
        g = subprocess.run([venv_setup.venv_python(), "-B", grader_path(spec)]
            + [a.replace("{cell}", cell) for a in spec["grader_args"]],
            cwd=ws, timeout=300, capture_output=True, text=True)
        g_stdout = g.stdout
        grade_text = g.stdout + (("\n[grader stderr]\n" + g.stderr) if g.stderr else "")
        meta["grader_rc"] = g.returncode
    except subprocess.TimeoutExpired:
        grade_text = "grader timed out"
        meta["grader_rc"] = 1
        if meta["failure_mode"] is None:
            meta["failure_mode"] = "grader_hang"
    open(grade_path, "w").write(grade_text)
    # Verdicts come from grader stdout only: a stderr line starting PASS/FAIL
    # must not overwrite a verdict. grade.txt keeps the combined text.
    meta["criteria"] = parse_verdicts(g_stdout)
    meta["passed"] = sum(meta["criteria"].values())
    meta["total"] = len(meta["criteria"])

# Agent-phase meta fields a --regrade pass must carry over untouched; every
# other graded field (criteria/passed/total/grader_rc/failure_mode) is
# refreshed from the offline re-execution.
AGENT_META_FIELDS = ("prompt_sha256", "started", "pi_rc", "iterations",
                     "wall_clock_agent_s", "code_sha256", "dry_run")

def regrade_cell(tool, model_key, rep, mode="solo"):
    """Offline re-grade of an existing cell: no pi, no LLM endpoint. Re-runs
    the pinned commands in the existing workspace and refreshes grade.txt +
    meta.json, preserving the agent-phase meta fields."""
    spec = SPECS[tool]
    cell = cell_dir(tool, model_key, rep, mode)
    ws = os.path.join(cell, "workspace")
    grade_path = os.path.join(cell, "grade.txt")
    meta_path = os.path.join(cell, "meta.json")
    if not os.path.isfile(meta_path) or not os.path.isdir(ws):
        return "no_cell", grade_path
    meta = json.load(open(meta_path))
    missing = [f for f in spec["artifacts"] if not os.path.isfile(os.path.join(ws, f))]
    if missing:
        return "no_artifact", grade_path
    meta["failure_mode"] = None       # recomputed by this pass only
    for f in spec.get("seed", []):    # generators ship beside prompts, not in the cell
        if not os.path.isfile(os.path.join(ws, os.path.basename(f))):
            shutil.copy2(f, ws)
    restore_data_files(spec, ws)      # unconditional: agent may have overwritten an input
    reexecute_commands(spec, ws, meta)
    run_grader(spec, cell, ws, meta, grade_path)
    with open(meta_path, "w") as fh:
        json.dump(meta, fh, indent=2)
    ok = meta["grader_rc"] == 0 and not meta["failure_mode"]
    return ("passed" if ok else "failed"), grade_path

def run_cell(tool, model_key, rep, args, mirror=None):
    """Run one cell. `mirror` is the {"provider", "model", "endpoint"} that
    actually serves this cell; it is what gets recorded into meta.json (never
    a base/model-key value), so a result can always be traced to the server
    that produced it. Callers that are not mirror-aware (direct calls, tests)
    get today's behaviour unchanged: mirror defaults to MODELS[model_key]
    itself, the single endpoint that existed before mirrors did."""
    spec = SPECS[tool]
    if mirror is None:
        mirror = MODELS[model_key]
    cell = cell_dir(tool, model_key, rep, getattr(args, "mode", "solo"))
    ws = os.path.join(cell, "workspace")
    grade_path = os.path.join(cell, "grade.txt")
    if os.path.exists(grade_path) and not args.force:
        return "skipped", grade_path
    if os.path.isdir(cell):
        shutil.rmtree(cell)
    os.makedirs(ws)
    dep_shas = seed_workspace(spec, ws, getattr(args, "mode", "solo"))
    meta = {"tool": tool, "model": model_key, "rep": rep, "model_id": mirror["model"],
            "mode": getattr(args, "mode", "solo"),
            # A dry-run cell delegates to the reference implementation, so it
            # always scores full marks. Recording it is what lets report.py and
            # aggregate() tell a stub cell from a model cell.
            "dry_run": bool(args.dry_run),
            "endpoint": mirror["endpoint"], "prompt_sha256": sha256_file(spec["prompt"]),
            "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "failure_mode": None}
    prompt = open(spec["prompt"]).read()
    t0 = time.time()
    if args.dry_run:
        # In-process stub via the fixtures registry (same thing stub_agent.py
        # does standalone): a stub_agent.py subprocess could not see STUBS
        # entries registered at test time, and test_run_bench registers its
        # _toy stub that way. stub_agent.py stays usable by hand.
        fixtures.write_stub(tool, ws)
        meta["pi_rc"] = 0
        if tool in SESSION_STUBS:
            open(os.path.join(cell, "session.jsonl"), "w").write(SESSION_STUBS[tool])
    else:
        proc = subprocess.Popen(PI_CMD + ["-p", "--mode", "json"] + pi_model_args(mirror) +
            ["--session", os.path.join(cell, "session.jsonl"), prompt],
            cwd=ws, start_new_session=True,
            stdout=open(os.path.join(cell, "events.jsonl"), "w"),
            stderr=subprocess.STDOUT)
        # Track this cell's process group from the moment it exists, so that
        # if the harness itself is killed (SIGINT/SIGTERM, an uncaught
        # exception, sys.exit) while this cell is in flight, cleanup_tracked_
        # pgids() can still reach it -- untracked otherwise, since only the
        # timeout branch below knows to call os.killpg on it. Untracked again
        # in `finally` once this cell resolves one way or the other, so a
        # long-running harness doesn't accumulate pgids for cells that
        # already finished normally.
        pgid = os.getpgid(proc.pid)
        _track_pgid(pgid)
        try:
            try:
                proc.communicate(timeout=args.timeout)
                meta["pi_rc"] = proc.returncode
            except subprocess.TimeoutExpired:
                # pi runs in its own session: signal the whole process group so
                # spawned tool children go down with it. Terminate gracefully
                # first (SIGTERM) and give pi a short grace period to exit and
                # flush its buffered stdout (events.jsonl) -- a bare SIGKILL
                # discards that buffer, leaving a timed-out cell with zero bytes
                # of evidence about what the agent was doing. Escalate to
                # SIGKILL only if it is still alive after the grace period.
                try:
                    os.killpg(pgid, signal.SIGTERM)
                    proc.communicate(timeout=getattr(args, "timeout_grace", 8))
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(pgid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError):
                        proc.kill()
                    proc.communicate()
                except (ProcessLookupError, PermissionError):
                    proc.kill()
                    proc.communicate()
                meta["pi_rc"] = None
                meta["failure_mode"] = "timeout"
        finally:
            _untrack_pgid(pgid)
    meta["wall_clock_agent_s"] = round(time.time() - t0, 1)
    if not args.dry_run and meta["failure_mode"] is None and meta.get("pi_rc") not in (0, None):
        meta["failure_mode"] = "harness_error(pi_rc=%s)" % meta["pi_rc"]
    meta["iterations"] = count_iterations(os.path.join(cell, "events.jsonl"))
    missing = [f for f in spec["artifacts"] if not os.path.isfile(os.path.join(ws, f))]
    if meta["failure_mode"] is None and missing:
        meta["failure_mode"] = "no_artifact"
    if dep_shas:
        check_dep_reuse(ws, dep_shas, meta)
    if not missing:
        restore_data_files(spec, ws)  # unconditional: agent may have overwritten an input
        reexecute_commands(spec, ws, meta)
    run_grader(spec, cell, ws, meta, grade_path)
    meta["code_sha256"] = {f: sha256_file(os.path.join(ws, f))
                           for f in spec["artifacts"] if os.path.isfile(os.path.join(ws, f))}
    with open(os.path.join(cell, "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    ok = meta["grader_rc"] == 0 and not meta["failure_mode"]
    return ("passed" if ok else "failed"), grade_path

def worker(model_key, cells, args):
    """Run every (tool, rep) cell assigned to one model key.

    --regrade makes no model calls at all (regrade_cell never looks at
    MODELS/mirrors), so it keeps the original one-thread, cells-in-order
    loop untouched -- there is no endpoint to distribute across.

    Otherwise, a model's cells are distributed across its mirrors (a model
    with no "mirrors" entry has exactly one, from model_mirrors(), so this
    is the same one-cell-at-a-time loop as before with mirrors unmirrored).
    Each mirror gets its own thread that pulls the next cell off a shared
    queue and runs it to completion before pulling another -- a mirror is a
    scarce resource, so a thread only ever holds the one cell it is actively
    running, and the shared queue is what guarantees every cell is claimed by
    exactly one thread (a partition), with no coordination needed beyond
    queue.Queue's own thread safety.

    A mirror that goes unreachable mid-run is not special-cased: its thread
    keeps pulling cells off the same queue and each one fails via the
    existing pi_rc/timeout machinery (fast if the endpoint refuses the
    connection, bounded by --timeout if it hangs instead), leaving an
    accurate, traceable failure_mode/endpoint in that cell's meta.json. The
    other mirrors' threads are untouched and keep draining the queue, so one
    dead mirror degrades a run -- some cells fail or run slow -- rather than
    stranding it.
    """
    if args.regrade:
        for tool, rep in cells:
            try:
                state, _ = regrade_cell(tool, model_key, rep,
                                        getattr(args, "mode", "solo"))
            except Exception:
                state = "harness_error"
                print("[%s] %s rep%d -> %s" % (model_key, tool, rep, state), flush=True)
                traceback.print_exc()
                continue
            print("[%s] %s rep%d -> %s" % (model_key, tool, rep, state), flush=True)
        return

    mirrors = model_mirrors(model_key)
    cell_q = queue.Queue()
    for c in cells:
        cell_q.put(c)

    def drain(mirror):
        while True:
            try:
                tool, rep = cell_q.get_nowait()
            except queue.Empty:
                return
            try:
                state, _ = run_cell(tool, model_key, rep, args, mirror)
            except Exception:
                state = "harness_error"
                print("[%s] %s rep%d -> %s" % (model_key, tool, rep, state), flush=True)
                traceback.print_exc()
                continue
            print("[%s] %s rep%d -> %s" % (model_key, tool, rep, state), flush=True)

    if len(mirrors) == 1:
        drain(mirrors[0])           # identical to the pre-mirrors code path
        return
    with ThreadPoolExecutor(max_workers=len(mirrors)) as ex:
        futures = [ex.submit(drain, m) for m in mirrors]
        for f in futures:
            f.result()

def aggregate(tools, models, reps, mode="solo"):
    """True iff every expected cell (tool x model x rep) has a healthy meta.json."""
    ok = True
    for tool in tools:
        for m in models:
            for r in range(1, reps + 1):
                mp = os.path.join(cell_dir(tool, m, r, mode), "meta.json")
                if not os.path.isfile(mp):
                    print("MISSING meta: %s %s %d" % (tool, m, r), flush=True)
                    ok = False
                    continue
                meta = json.load(open(mp))
                if meta.get("grader_rc") != 0 or meta.get("failure_mode"):
                    ok = False
    return ok

def main():
    venv_setup.activate_path()   # `python3` in agent sessions, graders and
                                 # re-executed commands means the bench venv
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools", default="all")
    ap.add_argument("--models", default="local,remote")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=2700)
    ap.add_argument("--timeout-grace", type=int, default=8, dest="timeout_grace",
                    help="seconds to wait for pi to exit after SIGTERM on "
                         "timeout before escalating to SIGKILL")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mode", default="solo", choices=("solo", "prebuilt"),
                    help="how dependencies are resolved; see seed_workspace")
    ap.add_argument("--regrade", action="store_true",
                    help="offline: re-execute commands + graders in existing "
                         "cells, preserving agent-phase meta; no pi/LLM calls")
    args = ap.parse_args()
    global CLEANUP_GRACE
    CLEANUP_GRACE = args.timeout_grace   # same grace period as the per-cell
                                         # timeout path, for harness-level cleanup
    install_termination_handlers()
    tools = sorted(SPECS) if args.tools == "all" else [t.strip() for t in args.tools.split(",")]
    models = [m.strip() for m in args.models.split(",")]
    cells = [(t, r) for t in tools for r in range(1, args.reps + 1)]
    with ThreadPoolExecutor(max_workers=len(models)) as ex:
        for m in models:
            ex.submit(worker, m, cells, args)
    sys.exit(0 if aggregate(tools, models, args.reps, args.mode) else 1)

if __name__ == "__main__":
    main()
