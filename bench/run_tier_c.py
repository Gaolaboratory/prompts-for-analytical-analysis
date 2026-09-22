#!/usr/bin/env python3
"""Tier (c) real-data cell runner: prompt + addendum + copied data files -> local LLM.

Unlike run_bench.py there is no external grader wired in: tier (c) verdicts are made
harness-side against each data/<tool>/README.md's expected results. The runner's job
is a clean, fully-captured cell: workspace with the real data, pi session, events,
session transcript, and the agent's outputs left in place for inspection.
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from specs import MODELS
import tier_c_specs

RUNS_DIR = os.path.join(HERE, "runs")
PI_CMD = os.environ.get("PI_BIN", "pi").split()


def build_prompt(prompt_path, addendum):
    """Verbatim prompt + blank line + addendum. Addendum must not repeat the prompt."""
    text = open(prompt_path).read().rstrip("\n")
    return text + "\n\n" + addendum.rstrip("\n") + "\n"


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


def prepare_workspace(cell, data_files):
    """Fresh workspace + copies of the real data files. Returns workspace path."""
    ws = os.path.join(cell, "workspace")
    if os.path.isdir(cell):
        shutil.rmtree(cell)
    os.makedirs(ws)
    for f in data_files:
        if not os.path.isfile(f):
            raise FileNotFoundError("missing data file: %s" % f)
        shutil.copy2(f, ws)
    return ws


def run_tier_c_cell(tool, args):
    spec = tier_c_specs.TIER_C[tool]
    model = MODELS["local"]
    cell = os.path.join(RUNS_DIR, tool, "local", "tierc")
    ws = prepare_workspace(cell, spec["data_files"])
    meta = {
        "tool": tool, "tier": "c", "model": "local", "model_id": model["model"],
        "endpoint": model["endpoint"], "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "data_files": [os.path.basename(f) for f in spec["data_files"]],
        "failure_mode": None,
    }
    prompt = build_prompt(spec["prompt"], spec["addendum"])
    open(os.path.join(cell, "prompt_full.txt"), "w").write(prompt)

    t0 = time.time()
    if args.dry_run:
        # Plumbing check only: no LLM. Record that the cell was assembled correctly.
        marker = os.path.join(ws, ".dry_run_marker")
        open(marker, "w").write("workspace prepared with: %s\n"
                                % ", ".join(meta["data_files"]))
        meta["pi_rc"] = 0
    else:
        proc = subprocess.Popen(
            PI_CMD + ["-p", "--mode", "json", "--model",
                      "%s/%s" % (model["provider"], model["model"]), "--session",
                      os.path.join(cell, "session.jsonl"), prompt],
            cwd=ws, start_new_session=True,
            stdout=open(os.path.join(cell, "events.jsonl"), "w"),
            stderr=subprocess.STDOUT)
        try:
            proc.communicate(timeout=args.timeout)
            meta["pi_rc"] = proc.returncode
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                proc.kill()
            proc.communicate()
            meta["pi_rc"] = None
            meta["failure_mode"] = "timeout"
    meta["wall_clock_agent_s"] = round(time.time() - t0, 1)
    meta["iterations"] = count_iterations(os.path.join(cell, "events.jsonl"))
    meta["outputs"] = sorted(f for f in os.listdir(ws)
                             if not f.startswith(".") and f != ".dry_run_marker")
    with open(os.path.join(cell, "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    return cell, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools", required=True, help="comma list or 'all'")
    ap.add_argument("--timeout", type=int, default=2700)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    tools = sorted(tier_c_specs.TIER_C) if args.tools == "all" else \
        [t.strip() for t in args.tools.split(",")]
    for tool in tools:
        try:
            cell, meta = run_tier_c_cell(tool, args)
            print("[tierc] %s -> %s (iterations=%s, failure_mode=%s)"
                  % (tool, cell, meta["iterations"], meta["failure_mode"]), flush=True)
        except Exception:
            import traceback
            print("[tierc] %s -> harness_error" % tool, flush=True)
            traceback.print_exc()
    return 0


if __name__ == "__main__":
    sys.exit(main())
