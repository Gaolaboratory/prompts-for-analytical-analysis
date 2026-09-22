#!/usr/bin/env python3
"""Aggregate bench/runs into results.json + AC_BENCHMARK_REPORT.md (house style)."""
import argparse, json, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

def collect(runs_dir, include_dry_run=False):
    """Every cell's meta.json under runs_dir.

    Dry-run cells (`"dry_run": true`) are excluded by default: their stub
    delegates to the reference implementation, so they always score full marks
    and would otherwise be indistinguishable from a model's results — the same
    reason phase0_report.py refuses cells with iterations == 0 or a stale prompt
    sha. Pass include_dry_run=True only to count how many were dropped.
    """
    rows = []
    if not os.path.isdir(runs_dir):
        return rows
    # Walked rather than indexed by <tool>/<model>/<rep>: a spec that declares
    # more than one dependency-resolution mode gets a mode segment in its cell
    # path (<tool>/<mode>/<model>/<rep>), so the depth is not fixed.
    for dirpath, dirnames, filenames in os.walk(runs_dir):
        dirnames.sort()
        if "meta.json" not in filenames:
            continue
        with open(os.path.join(dirpath, "meta.json")) as fh:
            meta = json.load(fh)
        if meta.get("dry_run") and not include_dry_run:
            continue
        # Tier-(c) cells (run_tier_c.py) live in the same tree under a "tierc"
        # rep and carry a different schema: no rep index, no passed/total. They
        # are not tier-(a) results, and rendering them raised KeyError before.
        if not isinstance(meta.get("rep"), int) or "passed" not in meta:
            continue
        gp = os.path.join(dirpath, "grade.txt")
        meta["grade_txt"] = open(gp).read() if os.path.isfile(gp) else ""
        rows.append(meta)
    rows.sort(key=lambda m: (m.get("tool") or "", m.get("mode") or "",
                             m.get("model") or "", m.get("rep") or 0))
    return rows

def render(rows, models):
    lines = ["# AC Prompt Tier (a) Benchmark Report", "",
             "**Date:** %s · **Harness:** pi (`-p --mode json`, agentic)" % time.strftime("%Y-%m-%d"), ""]
    results = {"cells": rows}
    for model in models:
        lines.append("## %s" % model)
        lines.append("")
        lines.append("| tool | " + " | ".join("rep %d" % r for r in (1, 2, 3)) + " |")
        lines.append("|---|" + "---|" * 3)
        # A tool run in more than one dependency-resolution mode gets one row per
        # mode: keying rows on the tool alone made two modes' cells overwrite each
        # other in the table, which is the reporting half of the same defect that
        # let one mode's cells overwrite the other's on disk.
        modes_of = {}
        for r in rows:
            modes_of.setdefault(r["tool"], set()).add(r.get("mode"))
        for tool, mode in sorted({(r["tool"], r.get("mode")) for r in rows},
                                 key=lambda t: (t[0], t[1] or "")):
            cells = ["", "", ""]
            for r in rows:
                if (r["tool"] == tool and r["model"] == model
                        and r.get("mode") == mode):
                    cells[r["rep"] - 1] = "%d/%d%s" % (r["passed"], r["total"],
                        " (%s)" % r["failure_mode"] if r.get("failure_mode") else "")
            label = tool if len(modes_of[tool]) < 2 else "%s (%s)" % (tool, mode)
            lines.append("| %s | %s |" % (label, " | ".join(cells)))
        lines.append("")
    lines.append("## Failures")
    lines.append("")
    any_fail = False
    for r in rows:
        fails = [l for l in r.get("grade_txt", "").splitlines() if l.startswith("FAIL ")]
        if r.get("grader_rc") != 0:
            any_fail = True
            lines.append("### %s / %s / rep %d%s" % (r["tool"], r["model"], r["rep"],
                         " — %s" % r["failure_mode"] if r.get("failure_mode") else ""))
            lines.append("")
            lines.extend("- `%s`" % l for l in fails[:20])
            lines.append("")
    if not any_fail:
        lines.append("(none)")
    lines.append("## Run metadata")
    lines.append("")
    lines.append("| tool | model | rep | iterations | wall_clock_s | prompt_sha256[:8] |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        lines.append("| %s | %s | %d | %s | %s | %s |" % (
            r["tool"], r["model"], r["rep"], r.get("iterations", "?"),
            r.get("wall_clock_agent_s", "?"), (r.get("prompt_sha256") or "")[:8]))
    return results, "\n".join(lines) + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", default=os.path.join(HERE, "runs"))
    args = ap.parse_args()
    rows = collect(args.runs_dir)
    dropped = len(collect(args.runs_dir, include_dry_run=True)) - len(rows)
    results, md = render(rows, sorted({r["model"] for r in rows}))
    with open(os.path.join(REPO, "results.json"), "w") as fh:
        json.dump(results, fh, indent=2)
    with open(os.path.join(REPO, "AC_BENCHMARK_REPORT.md"), "w") as fh:
        fh.write(md)
    print("wrote results.json and AC_BENCHMARK_REPORT.md (%d cells%s)"
          % (len(rows), ", %d dry-run cells excluded" % dropped if dropped else ""))

if __name__ == "__main__":
    main()
