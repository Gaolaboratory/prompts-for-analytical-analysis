#!/usr/bin/env python3
"""Cell runner for experiments A-H (docs/design/2026-09-17-experiments-A-H-design.md).

Deliberately a sibling of run_bench.py rather than an edit to it: run_bench.py
produced the published measurements and is left untouched so those stay
reproducible. Everything this runner scores comes from bench/graders/*,
UNMODIFIED, and everything it stages comes from bench/specs.py, so a cell here
is directly comparable to a cell there.

What it adds over run_bench.py:
  * a pluggable prompt (ablation levels, ambiguity variants) instead of only
    spec["prompt"]
  * the agent_driver.py loop instead of `pi`, which is absent from this machine
  * a variant axis in the cell path, so one tool can hold many prompt versions

Layout:  bench/exp/<experiment>/<tool>/<variant>/<rep>/{workspace,meta.json,
         transcript.jsonl,grade.txt}
"""
import argparse, concurrent.futures, json, os, shutil, subprocess, sys, threading, time, traceback

BENCH = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BENCH)
sys.path.insert(0, os.path.join(BENCH, "tests"))
from specs import SPECS, REPO
import venv_setup
import run_bench as RB
import content_probe
# Imported, never copied: the runner and the reporter must agree on which
# cells are measurements, or a cell the report drops as infrastructure is a
# cell the runner declines to replace.
from report_exp import VOID_MODES

EXP_DIR = os.path.join(BENCH, "exp")
# Endpoints are handed out per CELL, round-robin, never per tool. A static
# tool-per-endpoint split looks equivalent and is not: when one card died, the
# six tools assigned to it went missing wholesale, which reads downstream as
# "these tools failed" rather than "that card was down". Round-robin makes a
# dead endpoint cost throughput instead of specific tools.
_ep_lock = threading.Lock()
_ep_next = [0]


def next_endpoint(pool):
    if len(pool) == 1:
        return pool[0]
    with _ep_lock:
        ep = pool[_ep_next[0] % len(pool)]
        _ep_next[0] += 1
    return ep
DRIVER = os.path.join(BENCH, "agent_driver.py")
WRAPPER = os.path.join(BENCH, "wrapper_agentic.txt")
WRAPPER_SINGLE = os.path.join(BENCH, "wrapper_single_shot.txt")

DEFAULT_ENDPOINT = os.environ.get("EXP_ENDPOINT", "http://llm-host:4000/v1")
DEFAULT_MODEL = os.environ.get("EXP_MODEL", "qwen3.8-27b-gptq")


def cell_dir(experiment, tool, variant, rep):
    return os.path.join(EXP_DIR, experiment, tool, variant, str(rep))


def prompt_for(tool, variant):
    """The prompt file this variant names.

    'L4' and 'base' both mean the shipped prompt -- one name for the ablation
    ladder's top rung, one for every other experiment's control arm -- so that
    a control cell is provably the published prompt and not a copy that drifted.
    """
    spec = SPECS[tool]
    if variant in ("L4", "base"):
        return spec["prompt"]
    if variant.startswith("L"):
        p = os.path.join(os.path.dirname(spec["prompt"]), "ablation", variant + ".md")
    else:
        p = os.path.join(os.path.dirname(spec["prompt"]), "variants", variant + ".md")
    if not os.path.isfile(p):
        raise SystemExit("no prompt for %s/%s at %s" % (tool, variant, p))
    return p


def should_run(cell, force):
    """Whether this cell needs running, i.e. does not already hold a RESULT.

    Not simply "has no grade.txt": run_cell grades whatever the workspace
    contains, so a cell the driver abandoned at turn 0 gets a grade.txt like
    any other, reading 0/N. Keying the skip on that file alone lets one
    misconfigured launch cement an arm's worth of infrastructure failures --
    report_exp.py drops them from the denominators, correctly, while every
    later resume skips them, so the arm stays short and looks complete.

    A void cell is therefore treated as absent. A cell that was graded but
    whose meta.json is missing or truncated is also treated as absent: that is
    a cell interrupted between grading and bookkeeping, and nothing downstream
    can tell whether it was void without the meta.
    """
    if force:
        return True
    if not os.path.exists(os.path.join(cell, "grade.txt")):
        return True
    try:
        with open(os.path.join(cell, "meta.json")) as fh:
            failure_mode = json.load(fh).get("failure_mode")
    except (OSError, ValueError):
        return True
    return failure_mode in VOID_MODES


def run_cell(experiment, tool, variant, rep, args):
    spec = SPECS[tool]
    cell = cell_dir(experiment, tool, variant, rep)
    ws = os.path.join(cell, "workspace")
    grade_path = os.path.join(cell, "grade.txt")
    meta_path = os.path.join(cell, "meta.json")
    if not should_run(cell, args.force):
        return tool, variant, rep, "skipped", None
    if os.path.isdir(cell):
        shutil.rmtree(cell)
    os.makedirs(ws)

    prompt_path = prompt_for(tool, variant)
    dep_shas = RB.seed_workspace(spec, ws, "solo")

    driver_meta_path = os.path.join(cell, "driver_meta.json")
    endpoint = next_endpoint(args.endpoint_pool)
    cmd = [venv_setup.venv_python(), "-B", DRIVER,
           "--endpoint", endpoint, "--model", args.model,
           "--workspace", ws, "--prompt-file", prompt_path,
           "--transcript", os.path.join(cell, "transcript.jsonl"),
           "--meta", driver_meta_path,
           "--max-iters", str(args.max_iters), "--max-wall", str(args.timeout),
           "--max-tokens", str(args.max_tokens)]
    if args.temperature is not None:
        cmd += ["--temperature", str(args.temperature)]
    if args.disable_fallbacks:
        cmd += ["--disable-fallbacks"]
    if args.expect_served:
        cmd += ["--expect-served", args.expect_served]
    if args.single_shot:
        cmd += ["--single-shot", "--wrapper-file", WRAPPER_SINGLE]
    else:
        cmd += ["--wrapper-file", WRAPPER]
    env = dict(os.environ, AGENT_API_KEY=args.key)

    t0 = time.time()
    # The driver enforces its own wall cap and writes meta.json in a `finally`.
    # This outer timeout is only a backstop for a driver that has itself wedged,
    # and it must not be the thing that kills a working cell: subprocess.run's
    # timeout SIGKILLs, which skips that `finally`, leaving a cell with no meta
    # at all -- indistinguishable, downstream, from a model that produced
    # nothing. Three cells of the cross-model arm were scored 0/6 that way
    # before this was found. So: SIGTERM first, let the driver flush, and only
    # then SIGKILL; and record the event as a harness timeout, which is VOID,
    # not as a model failure.
    harness_timeout = False
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    try:
        proc.communicate(timeout=args.timeout + 300)
    except subprocess.TimeoutExpired:
        harness_timeout = True
        proc.terminate()
        try:
            proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
    driver_meta = {}
    if os.path.isfile(driver_meta_path):
        driver_meta = json.load(open(driver_meta_path))

    meta = {"experiment": experiment, "tool": tool, "variant": variant, "rep": rep,
            "mode": "solo", "harness": "agent_driver",
            "arm": "single_shot" if args.single_shot else "agentic",
            "prompt_path": os.path.relpath(prompt_path, REPO),
            "prompt_sha256": RB.sha256_file(prompt_path),
            "endpoint": endpoint,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t0)),
            "failure_mode": driver_meta.get("failure_mode"),
            "driver": driver_meta}
    if harness_timeout:
        meta["failure_mode"] = "harness_timeout"
    elif not driver_meta:
        # No meta despite no outer timeout: the driver died without unwinding.
        # Also infrastructure, also void -- never a score.
        meta["failure_mode"] = "harness_error"

    # In the single-shot arm the model cannot write files, so the reply IS the
    # submission: extract the fenced block and write it to the expected artifact
    # name before the pinned command runs. Anything else would grade the arm on
    # its inability to use a tool it was never given.
    if args.single_shot:
        write_single_shot_artifact(spec, ws, driver_meta, meta)

    RB.restore_data_files(spec, ws)
    RB.reexecute_commands(spec, ws, meta)
    RB.run_grader(spec, cell, ws, meta, grade_path)
    meta["code_sha256"] = {a: RB.sha256_file(os.path.join(ws, a))
                           for a in spec.get("artifacts", [])
                           if os.path.isfile(os.path.join(ws, a))}
    meta["missing_artifacts"] = [a for a in spec.get("artifacts", [])
                                 if not os.path.isfile(os.path.join(ws, a))]
    if meta["missing_artifacts"] and not meta["failure_mode"]:
        meta["failure_mode"] = "no_artifact"
    meta["harness_timeout"] = harness_timeout
    meta["wall_clock_agent_s"] = driver_meta.get("wall_clock_agent_s")
    meta["iterations"] = driver_meta.get("iterations")
    meta["tokens"] = driver_meta.get("tokens")
    meta["workers"] = args.workers      # contention context for any timing claim
    # Second, format-agnostic score. See bench/content_probe.py for why a cell
    # is scored twice; without it the ladder's lower rungs are indistinguishable.
    if tool in content_probe.TOOLS:
        try:
            meta["content"] = content_probe.score_cell(
                tool, ws, spec.get("data", []))
        except Exception as exc:
            meta["content"] = {"error": "%s: %s" % (type(exc).__name__, exc)}
    json.dump(meta, open(meta_path, "w"), indent=1)
    return tool, variant, rep, "%d/%d" % (meta["passed"], meta["total"]), meta


def write_single_shot_artifact(spec, ws, driver_meta, meta):
    """Pull the program out of a single-shot reply into the artifact the pinned
    command expects. Multi-artifact tools are not gradeable in this arm unless
    the reply labels each file; record that rather than guessing."""
    reply = driver_meta.get("single_shot_reply") or ""
    blocks, cur, in_block = [], [], False
    for line in reply.splitlines():
        if line.strip().startswith("```"):
            if in_block:
                blocks.append("\n".join(cur)); cur = []
            in_block = not in_block
            continue
        if in_block:
            cur.append(line)
    if in_block and cur:
        blocks.append("\n".join(cur))
    code = max(blocks, key=len) if blocks else reply
    artifacts = spec.get("artifacts", [])
    if len(artifacts) != 1:
        meta["single_shot_note"] = ("%d artifacts expected; single-shot extraction "
                                    "writes only the largest code block" % len(artifacts))
    if artifacts:
        open(os.path.join(ws, artifacts[0]), "w").write(code + "\n")
    meta["single_shot_blocks"] = len(blocks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiment", required=True, help="A, B, C, E, ...")
    ap.add_argument("--tools", required=True, help="comma list, or 'all'")
    ap.add_argument("--variants", required=True, help="comma list, e.g. L0,L1,L2,L3,L4")
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--rep-start", type=int, default=1)
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT,
                    help="one endpoint, or several comma-separated: cells are "
                         "handed out round-robin across them")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--key", default=os.environ.get("EXP_API_KEY", ""))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=2700)
    ap.add_argument("--max-iters", type=int, default=80)
    ap.add_argument("--max-tokens", type=int, default=16384)
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--single-shot", action="store_true")
    ap.add_argument("--disable-fallbacks", action="store_true")
    ap.add_argument("--expect-served", default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-list", action="store_true", help="print the grid and exit")
    args = ap.parse_args()

    venv_setup.activate_path()
    args.endpoint_pool = [e.strip() for e in args.endpoint.split(",") if e.strip()]
    if len(args.endpoint_pool) > 1:
        print("endpoint pool (%d, round-robin per cell): %s"
              % (len(args.endpoint_pool), ", ".join(args.endpoint_pool)))
    tools = sorted(SPECS) if args.tools == "all" else args.tools.split(",")
    variants = args.variants.split(",")
    grid = [(t, v, r) for t in tools for v in variants
            for r in range(args.rep_start, args.rep_start + args.reps)]
    print("grid: %d cells (%d tools x %d variants x %d reps)"
          % (len(grid), len(tools), len(variants), args.reps))
    if args.dry_list:
        for g in grid:
            print("  %s/%s/%s -> %s" % (g[0], g[1], g[2],
                                        os.path.relpath(prompt_for(g[0], g[1]), REPO)))
        return 0

    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_cell, args.experiment, t, v, r, args): (t, v, r)
                for t, v, r in grid}
        for fut in concurrent.futures.as_completed(futs):
            t, v, r = futs[fut]
            done += 1
            try:
                _, _, _, score, m = fut.result()
                c = (m or {}).get("content") or {}
                if c and "error" not in c:
                    score += "  content %d/%d method, %d/%d precise" % (
                        c["method_passed"], c["total"], c["precise_passed"], c["total"])
            except Exception:
                score = "ERROR"
                traceback.print_exc()
            print("[%3d/%3d] %-16s %-6s rep%-3d %s" % (done, len(grid), t, v, r, score),
                  flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
