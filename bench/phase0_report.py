#!/usr/bin/env python3
"""Phase 0 baseline report. Refuses to count a cell that no agent actually ran.

A --dry-run cell (fixtures stub, iterations == 0, wall clock ~0) writes the same
grade.txt as a real one, so every cell is checked for evidence of an agent session
before it is reported.
"""
import json, os, sys

RUNS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs")
TOOLS = sys.argv[1:] or ["nmr_quad", "dda_v2"]

import hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from specs import SPECS


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


CURRENT = {t: _sha(SPECS[t]["prompt"]) for t in TOOLS if t in SPECS}

rows, suspect, stale = [], [], set()
for tool in TOOLS:
    for model in ("local", "remote"):
        base = os.path.join(RUNS, tool, model)
        if not os.path.isdir(base):
            continue
        for rep in sorted(os.listdir(base)):
            cell = os.path.join(base, rep)
            mp, gp = os.path.join(cell, "meta.json"), os.path.join(cell, "grade.txt")
            if not os.path.isfile(mp):
                continue
            m = json.load(open(mp))
            grade = open(gp).read() if os.path.isfile(gp) else ""
            summary = next((l for l in grade.splitlines() if l.endswith("passed")), "?")
            fails = [l[5:] for l in grade.splitlines() if l.startswith("FAIL ")]
            real = (not m.get("dry_run")
                    and bool(m.get("iterations"))
                    and (m.get("wall_clock_agent_s") or 0) > 5)
            # A cell graded against an older revision of the prompt is not evidence
            # about the current one. Phase 0's dda_v2 retest had stale cells on disk
            # from the pre-fix run that looked identical to fresh results.
            cur_sha = CURRENT.get(tool)
            if cur_sha and m.get("prompt_sha256") != cur_sha:
                real = False
                stale.add((tool, model, rep))
            row = dict(tool=tool, model=model, rep=rep, summary=summary, fails=fails,
                       wall=m.get("wall_clock_agent_s"), iters=m.get("iterations"),
                       failure_mode=m.get("failure_mode"), real=real,
                       prompt_sha=(m.get("prompt_sha256") or "")[:12],
                       dry_run=bool(m.get("dry_run")))
            (rows if real else suspect).append(row)

print("PHASE 0 BASELINE  (tier (a), prompts as written)\n")
hdr = "%-10s %-7s %-4s %-16s %7s %6s  %s"
print(hdr % ("tool", "model", "rep", "result", "wall_s", "iters", "failed criteria"))
print("-" * 92)
for r in rows:
    print(hdr % (r["tool"], r["model"], r["rep"], r["summary"], r["wall"], r["iters"],
                 ", ".join(r["fails"]) or ("-" if not r["failure_mode"] else r["failure_mode"])))

if suspect:
    print("\nEXCLUDED — not evidence about the current prompt:")
    for r in suspect:
        why = ("STALE PROMPT %s" % r["prompt_sha"]
               if (r["tool"], r["model"], r["rep"]) in stale
               else "DRY RUN (stub cell, meta.dry_run)" if r["dry_run"]
               else "no agent session (dry-run stub or crash before first tool call)")
        print("  %s/%s/%s  iters=%s wall=%ss  %s  [%s]"
              % (r["tool"], r["model"], r["rep"], r["iters"], r["wall"], r["summary"], why))

print("\nprompt sha256 (first 12) per tool:")
for tool in TOOLS:
    shas = {r["prompt_sha"] for r in rows if r["tool"] == tool}
    print("  %-10s %s" % (tool, ", ".join(sorted(shas)) or "-"))

full = [r for r in rows if r["summary"].startswith(tuple(str(n) for n in range(1, 10)))
        and r["summary"].split("/")[0] == r["summary"].split("/")[1].split()[0]]
print("\n%d/%d real cells pass every criterion" % (len(full), len(rows)))
