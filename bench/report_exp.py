#!/usr/bin/env python3
"""Aggregate experiment cells into the tables the manuscript needs.

Every rate is reported k/n with a 95% Wilson interval, per the review's Phase-3
finding that nothing in the current manuscript carries an interval. Wilson
rather than Wald because the rates here sit near 0 and 1, where Wald intervals
are known to be wrong (and can run outside [0,1]).

Cells whose failure_mode is infrastructural are VOID: excluded from every
denominator and reported as a separate count. Scoring an endpoint's billing
window as a model failure is the easiest way to publish a wrong number.
"""
import argparse, collections, glob, json, math, os, sys

BENCH = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(BENCH, "exp")

VOID_MODES = {"endpoint_error", "harness_error", "harness_timeout",
              "rate_limited", "grader_hang", "model_substituted"}
# context_overflow is deliberately NOT void: it is a real result about whether
# the prompt and its agentic trace fit the model being claimed for it.


def wilson(k, n, z=1.959963985):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def fmt(k, n):
    if n == 0:
        return "   --      "
    lo, hi = wilson(k, n)
    return "%2d/%-2d %5.1f%% [%4.1f-%4.1f]" % (k, n, 100 * k / n, 100 * lo, 100 * hi)


def load(experiment):
    cells, void = [], []
    for f in sorted(glob.glob(os.path.join(EXP, experiment, "*", "*", "*", "meta.json"))):
        try:
            m = json.load(open(f))
        except ValueError:
            continue
        m["_path"] = os.path.relpath(f, os.path.dirname(BENCH))
        (void if m.get("failure_mode") in VOID_MODES else cells).append(m)
    return cells, void


def agg(cells, keyfn):
    d = collections.defaultdict(lambda: dict(
        cells=0, full=0, crit=0, crit_tot=0,
        method=0, precise=0, present=0, content_tot=0,
        wall=[], tokens=0))
    for m in cells:
        a = d[keyfn(m)]
        a["cells"] += 1
        tot, passed = m.get("total") or 0, m.get("passed") or 0
        a["crit"] += passed
        a["crit_tot"] += tot
        a["full"] += int(tot > 0 and passed == tot)
        c = m.get("content") or {}
        if c and "error" not in c:
            a["method"] += c["method_passed"]
            a["precise"] += c["precise_passed"]
            a["present"] += c["present"]
            a["content_tot"] += c["total"]
        if m.get("wall_clock_agent_s"):
            a["wall"].append(m["wall_clock_agent_s"])
        t = m.get("tokens") or {}
        a["tokens"] += (t.get("input") or 0) + (t.get("output") or 0)
    return d


def table(d, label, order=None):
    keys = order or sorted(d)
    print("\n%-28s %-18s %-18s %-18s %-18s   median s   Mtok"
          % (label, "cells full-pass", "criteria (strict)",
             "content: method", "content: precise"))
    print("-" * 140)
    for k in keys:
        if k not in d:
            continue
        a = d[k]
        w = sorted(a["wall"])
        med = w[len(w) // 2] if w else float("nan")
        print("%-28s %-18s %-18s %-18s %-18s %8.0f  %5.2f"
              % (k, fmt(a["full"], a["cells"]), fmt(a["crit"], a["crit_tot"]),
                 fmt(a["method"], a["content_tot"]), fmt(a["precise"], a["content_tot"]),
                 med, a["tokens"] / 1e6))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("experiment")
    ap.add_argument("--failures", action="store_true", help="list every non-passing cell")
    args = ap.parse_args()
    cells, void = load(args.experiment)
    if not cells and not void:
        print("no cells under bench/exp/%s" % args.experiment)
        return 1
    print("experiment %s: %d scored cells, %d void (infrastructure, excluded)"
          % (args.experiment, len(cells), len(void)))
    if void:
        c = collections.Counter(m.get("failure_mode") for m in void)
        print("  void reasons: %s" % dict(c))

    variants = sorted({m["variant"] for m in cells})
    lad = [v for v in ("L0", "L1", "L2", "L3", "L4") if v in variants]
    order = lad + [v for v in variants if v not in lad]

    table(agg(cells, lambda m: m["variant"]), "POOLED BY VARIANT", order)
    for tool in sorted({m["tool"] for m in cells}):
        sub = [m for m in cells if m["tool"] == tool]
        table(agg(sub, lambda m: m["variant"]), tool, order)

    modes = collections.Counter(m.get("failure_mode") for m in cells
                                if m.get("failure_mode"))
    if modes:
        print("\nnon-void failure modes among scored cells: %s" % dict(modes))
    if args.failures:
        print("\nNON-PASSING CELLS")
        for m in cells:
            if (m.get("total") or 0) == 0 or m.get("passed") != m.get("total"):
                failed = [k for k, v in (m.get("criteria") or {}).items() if not v]
                print("  %-14s %-4s rep%-3d %s/%s  %s"
                      % (m["tool"], m["variant"], m["rep"], m.get("passed"),
                         m.get("total"), m.get("failure_mode") or ""))
                for k in failed[:3]:
                    print("        FAIL %s" % k[:100])
    return 0


if __name__ == "__main__":
    sys.exit(main())
