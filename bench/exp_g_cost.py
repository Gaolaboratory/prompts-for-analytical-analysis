#!/usr/bin/env python3
"""Experiment G — cost and data locality, plus the pooled replication figure.

Two jobs, one file, because they read the same cells:

1. The pooled twelve-tool n=10 replication figure (Experiment E's seven tools
   plus Experiment A's L4 rung for the five tools E does not cover; dda_s is
   counted once, from E, where it ran at n=10). This supersedes the 97/104
   figure computed while dda_s was still running.

2. Experiment G per the pre-registered design (docs/design/
   2026-09-17-experiments-A-H-design.md, section G): per-tool and
   *per-validated-tool* accounting over the cells A/B/C/E already record.
   Energy is omitted by decision — no power meter exists on the serving host,
   GPU-only draw would be mistaken for a system figure, and TDP x wall clock
   is not a measurement. What is measured is stated; what is not is said.

The frontier counterfactual prices the SAME token counts at list rates; it is
a currency conversion, not a claim that a frontier model would need as many
tokens.
"""
import argparse, collections, glob, json, math, os, sys

BENCH = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(BENCH, "exp")

VOID_MODES = {"endpoint_error", "harness_error", "harness_timeout",
              "rate_limited", "grader_hang", "model_substituted"}

# 2026-09-22 list prices, USD per 1M tokens, stated in the manuscript so a
# reader can re-do the conversion at any other rate. Mid-tier frontier class
# (e.g. Claude Sonnet / GPT mid-tier): $3 input / $15 output.
FRONTIER_IN, FRONTIER_OUT = 3.0, 15.0


def wilson(k, n, z=1.959963985):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def load(experiment):
    out = []
    for f in sorted(glob.glob(os.path.join(EXP, experiment, "*", "*", "*", "meta.json"))):
        try:
            m = json.load(open(f))
        except ValueError:
            continue
        if m.get("failure_mode") in VOID_MODES:
            continue  # void cells ran but are not scored; their cost still counts below
        out.append(m)
    return out


def load_all(experiment):
    """Void cells included: infrastructure failures are part of what a tool costs."""
    out = []
    for f in sorted(glob.glob(os.path.join(EXP, experiment, "*", "*", "*", "meta.json"))):
        try:
            m = json.load(open(f))
        except ValueError:
            continue
        out.append(m)
    return out


def tokens_of(m):
    t = m.get("tokens") or {}
    return (t.get("input") or 0), (t.get("output") or 0)


def pooled_replication():
    e = [m for m in load("E") if m.get("variant") == "base"]
    e_tools = {m["tool"] for m in e}
    a_l4 = [m for m in load("A") if m.get("variant") == "L4" and m["tool"] not in e_tools]
    cells = e + a_l4
    k = sum(1 for m in cells if (m.get("total") or 0) > 0 and m.get("passed") == m.get("total"))
    n = len(cells)
    crit = sum(m.get("passed") or 0 for m in cells)
    crit_tot = sum(m.get("total") or 0 for m in cells)
    lo, hi = wilson(k, n)
    clo, chi = wilson(crit, crit_tot)
    print("POOLED TWELVE-TOOL REPLICATION (E base + A/L4 for the five tools E lacks; dda_s from E)")
    print("  cells full-pass   %d/%d = %.1f%% [%.1f, %.1f]" % (k, n, 100 * k / n, 100 * lo, 100 * hi))
    print("  criteria (strict) %d/%d = %.1f%% [%.1f, %.1f]" % (crit, crit_tot, 100 * crit / crit_tot, 100 * clo, 100 * chi))
    print("  tools: %s" % ", ".join(sorted({m["tool"] for m in cells})))
    print("  per tool: " + "; ".join(
        "%s %d/%d" % (t, sum(1 for m in cells if m["tool"] == t and (m.get("total") or 0) > 0
                             and m.get("passed") == m.get("total")),
                      sum(1 for m in cells if m["tool"] == t))
        for t in sorted({m["tool"] for m in cells})))


def cost_table():
    # Basis for "cost of one validated tool": the shipped-prompt arms, i.e. the
    # same cells as the replication figure. Failed sessions are part of the cost.
    e = [m for m in load_all("E")]
    e_tools = {m["tool"] for m in e}
    base = [m for m in e if m.get("variant") == "base"] + \
           [m for m in load_all("A") if m.get("variant") == "L4" and m["tool"] not in e_tools]

    per = collections.defaultdict(lambda: dict(cells=0, full=0, wall=0.0,
                                               tin=0, tout=0, iters=[], walls=[]))
    for m in base:
        a = per[m["tool"]]
        a["cells"] += 1
        tot, passed = m.get("total") or 0, m.get("passed") or 0
        a["full"] += int(tot > 0 and passed == tot)
        ti, to = tokens_of(m)
        a["tin"] += ti
        a["tout"] += to
        if m.get("wall_clock_agent_s"):
            a["wall"] += m["wall_clock_agent_s"]
            a["walls"].append(m["wall_clock_agent_s"])
        if m.get("driver", {}).get("iterations"):
            a["iters"].append(m["driver"]["iterations"])

    print("\nEXPERIMENT G — cost of the shipped-prompt arms (n=10 per tool, dda_s included from E)")
    print("%-15s %5s %5s %9s %8s %11s %11s  %9s  %8s" %
          ("tool", "cells", "pass", "wall h", "med s", "tok in", "tok out", "$ frontier", "$/val.tool"))
    tw = tti = tto = 0.0
    for t in sorted(per):
        a = per[t]
        usd = (a["tin"] * FRONTIER_IN + a["tout"] * FRONTIER_OUT) / 1e6
        rate = a["full"] / a["cells"] if a["cells"] else float("nan")
        med = sorted(a["walls"])[len(a["walls"]) // 2] if a["walls"] else float("nan")
        print("%-15s %5d %5d %9.2f %8.0f %11.2f %11.2f  %9.2f  %8.2f" %
              (t, a["cells"], a["full"], a["wall"] / 3600.0, med,
               a["tin"] / 1e6, a["tout"] / 1e6, usd, usd / rate if rate else float("nan")))
        tw += a["wall"]; tti += a["tin"]; tto += a["tout"]
    full = sum(a["full"] for a in per.values())
    cells = sum(a["cells"] for a in per.values())
    tusd = (tti * FRONTIER_IN + tto * FRONTIER_OUT) / 1e6
    print("%-15s %5d %5d %9.2f %8s %11.2f %11.2f  %9.2f  %8.2f" %
          ("TOTAL", cells, full, tw / 3600.0, "", tti / 1e6, tto / 1e6,
           tusd, tusd / (full / cells)))

    # Whole-campaign context: everything A+B+C+E cost, including voids.
    print("\nwhole campaign A+B+C+E (all arms, voids included — infrastructure is part of cost):")
    grand_w = grand_ti = grand_to = grand_n = 0
    for exp in ("A", "B", "C_gemma4", "C_gemma4_single", "C_gptq", "E"):
        ms = load_all(exp)
        if not ms:
            continue
        w = sum(m.get("wall_clock_agent_s") or 0 for m in ms)
        ti = sum(tokens_of(m)[0] for m in ms)
        to = sum(tokens_of(m)[1] for m in ms)
        usd = (ti * FRONTIER_IN + to * FRONTIER_OUT) / 1e6
        print("  %-15s %4d cells  %7.2f h  %8.2f Mtok in %8.2f Mtok out  $%8.2f" %
              (exp, len(ms), w / 3600.0, ti / 1e6, to / 1e6, usd))
        grand_w += w; grand_ti += ti; grand_to += to; grand_n += len(ms)
    gusd = (grand_ti * FRONTIER_IN + grand_to * FRONTIER_OUT) / 1e6
    print("  %-15s %4d cells  %7.2f h  %8.2f Mtok in %8.2f Mtok out  $%8.2f" %
          ("TOTAL", grand_n, grand_w / 3600.0, grand_ti / 1e6, grand_to / 1e6, gusd))
    print("\nenergy: omitted by pre-registered decision (no meter; GPU draw != system figure)")
    print("locality: every cell ran on hardware in the building; no datum left it")


def main():
    global FRONTIER_IN, FRONTIER_OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--rates", help="USD per 1M tokens 'in,out'", default="%f,%f" % (FRONTIER_IN, FRONTIER_OUT))
    args = ap.parse_args()
    FRONTIER_IN, FRONTIER_OUT = (float(x) for x in args.rates.split(","))
    pooled_replication()
    cost_table()
    return 0


if __name__ == "__main__":
    sys.exit(main())
