#!/usr/bin/env python3
"""Recompute every cell's content score from its preserved workspace.

Needed for two reasons, both structural rather than accidental:

  * run_exp.py imports content_probe once per process, so a long-running grid
    keeps whatever version of the probe was on disk when it started. A probe fix
    mid-campaign therefore reaches new PROCESSES, not new CELLS.
  * the probe is an analysis, not a measurement. Re-deriving it from preserved
    artifacts must always be possible and must never touch the strict grader
    verdicts, which are the measurement.

Strict criteria, timings, tokens and failure modes are left exactly as the
harness recorded them; only `content` is rewritten, and `content_probe_version`
records which probe produced it.
"""
import argparse, glob, hashlib, json, os, sys

BENCH = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BENCH)
import content_probe
from specs import SPECS

PROBE_SHA = hashlib.sha256(
    open(os.path.join(BENCH, "content_probe.py"), "rb").read()).hexdigest()[:12]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("experiments", nargs="+")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    changed = same = skipped = 0
    for exp in args.experiments:
        pat = os.path.join(BENCH, "exp", exp, "*", "*", "*", "meta.json")
        for f in sorted(glob.glob(pat)):
            m = json.load(open(f))
            tool = m["tool"]
            ws = os.path.join(os.path.dirname(f), "workspace")
            if tool not in content_probe.TOOLS or not os.path.isdir(ws):
                skipped += 1
                continue
            try:
                new = content_probe.score_cell(tool, ws, SPECS[tool].get("data", []))
            except Exception as exc:
                new = {"error": "%s: %s" % (type(exc).__name__, exc)}
            old = m.get("content") or {}
            key = lambda c: (c.get("method_passed"), c.get("precise_passed"),
                             c.get("present"))
            if key(old) != key(new):
                changed += 1
                print("%-14s %-6s rep%-3d  %s -> %s"
                      % (tool, m["variant"], m["rep"], key(old), key(new)))
            else:
                same += 1
            if not args.dry_run:
                m["content"] = new
                m["content_probe_version"] = PROBE_SHA
                json.dump(m, open(f, "w"), indent=1)
    print("\nprobe %s: %d cells changed, %d unchanged, %d skipped%s"
          % (PROBE_SHA, changed, same, skipped,
             "  (dry run, nothing written)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
