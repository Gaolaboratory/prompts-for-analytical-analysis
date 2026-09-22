#!/usr/bin/env python3
"""bench/tier_b.py -- tier (b) robustness sweep.

Tier (a) (docs/design/2026-09-11-p3-sweep-results.md) measured whether each
submitted program gets the right answer on the one real file it shipped
with. Every examples/*/TEST_PLAN.md defines tier (b) as "perturb the
generator knobs one at a time" -- but the short-prompt track (design decision
D2) deliberately removed the generators, so there are no knobs left to turn.

The replacement, approved before this was built: take the 36 programs the
models actually wrote (12 tools x 3 reps, preserved under
bench/runs/<tool>[/solo]/local/<rep>/workspace/) and run them again on
systematically perturbed real inputs, checking that they still agree with a
reference recomputed FROM THE SAME PERTURBED INPUT. A program that only
memorised its one shipped file, rather than the method, is expected to
diverge from that recomputed reference even though it happily reproduced the
tier(a) answer.

Design constraints (docs/design/2026-09-11-p3-sweep-results.md's conventions
discussion; this task's rule 5 is the one leaned on hardest here):

  - every perturbation is NON-uniform (a subset of rows, a ramp, an injected
    or removed feature, decimation) -- never a global scale/offset/unit
    change, which an OLS-style answer can absorb by closed-form algebra
    without the program doing any real analysis (this repo measured that
    mistake directly: see calibration_s's tier(a) grader);
  - every perturbation is measured against the reference BEFORE being relied
    on (see each tool's Perturbation docstring in bench/tier_b_lib/tools.py,
    and --verify below), because an unmeasured injection site can silently
    do nothing or merge into a neighbour (this repo's chrom_s tier(a) grader
    hit exactly that, at 3.88 s from a real peak);
  - only quantities RE-DERIVABLE from the perturbed input are graded; each
    tool's skip_notes lists what tier(a) criteria are skipped and why
    (typically: pinned to a literal constant of the one shipped file);
  - nothing is ever written into bench/runs/, data/ or examples/ -- every
    perturbed input and every copied program lives under a tempfile.mkdtemp()
    directory that is removed as soon as that (tool, rep, perturbation) cell
    finishes, win or lose;
  - every submitted-program invocation carries a timeout, recorded as its own
    outcome ("timeout") distinct from a wrong answer or a crash.

Usage:
    python3 bench/tier_b.py                  # run the full sweep
    python3 bench/tier_b.py --tool chrom_s    # one tool only
    python3 bench/tier_b.py --verify          # print each perturbation's
                                               # before/after reference
                                               # effect and exit (no
                                               # submitted programs are run)
    python3 bench/tier_b.py --out FILE.json   # where the results go
                                               # (default: bench/tier_b_out/
                                               # results.json, a fresh
                                               # directory -- not bench/runs/)
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tier_b_lib"))

from common import reps_for, run_program, RUNS  # noqa: E402
from tools import TOOLS, _copy_artifacts  # noqa: E402


DEFAULT_OUT = os.path.join(HERE, "tier_b_out", "results.json")


def _mode_dir(tool):
    """The bench/runs/<key>[/<mode>] path this tool's reps live under."""
    return tool["key"] if tool.get("mode") is None else \
        os.path.join(tool["key"], tool["mode"])


def build_inputs(tool, tmp_dir):
    from tools import _copy_inputs
    _copy_inputs(tool, tmp_dir)


def run_submission(tool, tmp_dir):
    if "custom_run" in tool:
        return tool["custom_run"](tmp_dir, tool, tool["timeout"])
    argv = [sys.executable, tool["script"]] + tool["build_argv"]()
    return run_program(argv, tmp_dir, tool["timeout"])


def verify_perturbations(tool, log):
    """Compute each perturbation's reference-before/after once (perturbations
    are deterministic and rep-independent) and log the effect. Returns
    (refs, effects): refs maps perturbation name -> reference recomputed on
    the perturbed input (reused for every rep, so it is not recomputed 3x for
    no reason); effects maps perturbation name -> the human-readable
    before/after description, for the JSON report."""
    refs, effects = {}, {}
    for pert in tool["perturbations"]:
        tmp = tempfile.mkdtemp(prefix="tierb_verify_")
        try:
            build_inputs(tool, tmp)
            before = tool["reference"](tmp)
            pert.apply(tmp)
            after = tool["reference"](tmp)
            effect = tool["describe_effect"](before, after)
            log("  [%s / %s] %s -> %s" % (tool["key"], pert.name,
                                           pert.description, effect))
            refs[pert.name] = after
            effects[pert.name] = "%s -- %s" % (pert.description, effect)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return refs, effects


def run_cell(tool, pert, rep, ws, ref):
    """Run one (tool, rep, perturbation) cell in an isolated tmp dir and
    return its result dict. Always cleans up the tmp dir, and never raises:
    a crash inside grading is caught and recorded as its own outcome so one
    bad cell cannot stop the sweep."""
    tmp = tempfile.mkdtemp(prefix="tierb_")
    try:
        build_inputs(tool, tmp)
        pert.apply(tmp)
        missing = _copy_artifacts(tool, ws, tmp)
        if missing:
            return {"outcome": "missing_artifact", "missing": missing,
                     "criteria": []}
        t0 = time.time()
        run = run_submission(tool, tmp)
        elapsed = time.time() - t0
        if run["timed_out"]:
            return {"outcome": "timeout", "elapsed_s": elapsed, "criteria": []}
        if run["crashed"]:
            return {"outcome": "crash", "elapsed_s": elapsed,
                     "returncode": run["returncode"],
                     "stderr_tail": (run["stderr"] or "")[-500:], "criteria": []}
        try:
            criteria = tool["grade"](tmp, run, ref)
        except Exception as exc:
            return {"outcome": "grader_error", "elapsed_s": elapsed,
                     "error": "%s: %s" % (type(exc).__name__, exc), "criteria": []}
        passed = sum(1 for _, ok, _ in criteria if ok)
        outcome = "pass" if passed == len(criteria) and criteria else "fail"
        return {"outcome": outcome, "elapsed_s": elapsed,
                 "criteria": [{"name": n, "passed": bool(ok), "detail": str(d)}
                              for n, ok, d in criteria]}
    except Exception as exc:
        return {"outcome": "harness_error",
                 "error": "%s: %s" % (type(exc).__name__, exc), "criteria": []}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_tool(tool, log):
    log("== %s ==" % tool["key"])
    refs, effects = verify_perturbations(tool, log)
    reps = reps_for(_mode_dir(tool))
    if not reps:
        log("  no reps found under bench/runs/%s/local/*/workspace" % _mode_dir(tool))
    cells = []
    for rep, ws in reps:
        for pert in tool["perturbations"]:
            t0 = time.time()
            result = run_cell(tool, pert, rep, ws, refs[pert.name])
            result.update({"tool": tool["key"], "rep": rep,
                            "perturbation": pert.name,
                            "wall_s": round(time.time() - t0, 3)})
            n_ok = sum(1 for c in result["criteria"] if c["passed"])
            n_tot = len(result["criteria"])
            log("  rep %s / %-24s %-14s %s" % (
                rep, pert.name, result["outcome"],
                ("%d/%d criteria" % (n_ok, n_tot)) if n_tot else ""))
            cells.append(result)
    return {"tool": tool["key"], "perturbation_effects": effects,
             "skip_notes": tool["skip_notes"], "cells": cells}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tool", action="append", dest="tools",
                     help="only run this tool key (repeatable); default: all 12")
    ap.add_argument("--verify", action="store_true",
                     help="print each perturbation's reference before/after "
                          "effect and exit without running any submitted "
                          "program")
    ap.add_argument("--out", default=DEFAULT_OUT,
                     help="where to write the JSON results (default: %(default)s)")
    args = ap.parse_args(argv)

    keys = args.tools or sorted(TOOLS)
    unknown = [k for k in keys if k not in TOOLS]
    if unknown:
        ap.error("unknown tool(s): %s (known: %s)" % (unknown, sorted(TOOLS)))

    def log(msg):
        print(msg)
        sys.stdout.flush()

    if args.verify:
        for key in keys:
            log("== %s ==" % key)
            verify_perturbations(TOOLS[key], log)
        return 0

    report = {"tools": {}}
    t_start = time.time()
    for key in keys:
        report["tools"][key] = run_tool(TOOLS[key], log)
    report["wall_s"] = round(time.time() - t_start, 1)

    out_path = args.out
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
    log("\nwrote %s" % out_path)

    total_cells = sum(len(t["cells"]) for t in report["tools"].values())
    full_pass = sum(1 for t in report["tools"].values() for c in t["cells"]
                     if c["outcome"] == "pass")
    log("%d/%d perturbation cells fully passed" % (full_pass, total_cells))
    return 0


if __name__ == "__main__":
    sys.exit(main())
