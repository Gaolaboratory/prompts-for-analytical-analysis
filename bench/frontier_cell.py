#!/usr/bin/env python3
"""Set up and grade one benchmark cell run by hand against a frontier model.

The operator runs the model; this script does everything else, so that a
hand-run cell is scored by exactly the same unmodified graders as an automated
one and the two are directly comparable. Nothing here asks the operator to
judge whether an answer is right -- that is the point: the manuscript's own rule
is that the agent's self-report is never the verdict, and a human eyeballing the
output is not much better.

    setup   make a fresh workspace, stage the inputs, print the prompt to use
    grade   run the pinned command, the unmodified grader, the content probe
    report  one table, ready to paste back

Single-shot arm: save the model's reply verbatim to reply.txt inside the cell
directory; `grade --arm single_shot` extracts the program from it.
"""
import argparse, json, os, shutil, subprocess, sys, time

BENCH = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BENCH)
sys.path.insert(0, BENCH)
sys.path.insert(0, os.path.join(BENCH, "tests"))
from specs import SPECS
import venv_setup, content_probe
import run_bench as RB

TOOLS12 = ["calibration_s", "titration_s", "uvvis_s", "pca_s", "chrom_s",
           "spectral_s", "formula_s", "nmr_s", "mass_stats_s", "mass_reader_s",
           "features_s", "dda_s"]


def cell_dir(label, tool, arm, rep):
    return os.path.join(BENCH, "exp", "F_" + label, tool, arm, str(rep))


def do_setup(args):
    spec = SPECS[args.tool]
    cell = cell_dir(args.label, args.tool, args.arm, args.rep)
    ws = os.path.join(cell, "workspace")
    if os.path.isdir(cell):
        if not args.force:
            print("cell already exists (use --force to recreate): %s" % cell)
            return 1
        shutil.rmtree(cell)
    os.makedirs(ws)
    RB.seed_workspace(spec, ws, "solo")
    wrapper = os.path.join(BENCH, "wrapper_agentic.txt" if args.arm == "agentic"
                           else "wrapper_single_shot.txt")
    json.dump({"tool": args.tool, "arm": args.arm, "rep": args.rep,
               "label": args.label, "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "prompt_sha256": RB.sha256_file(spec["prompt"]),
               "wrapper_sha256": RB.sha256_file(wrapper)},
              open(os.path.join(cell, "setup.json"), "w"), indent=1)
    print("workspace : %s" % ws)
    print("prompt    : %s" % os.path.relpath(spec["prompt"], REPO))
    print("wrapper   : %s" % os.path.relpath(wrapper, REPO))
    print("staged    : %s" % ", ".join(sorted(os.listdir(ws))))
    if args.arm == "single_shot":
        print("reply to  : %s" % os.path.join(cell, "reply.txt"))
    print("\nRun the model with the wrapper as the system message and the prompt "
          "file's contents as the single user message.")
    if args.arm == "agentic":
        print("Its working directory MUST be the workspace above. Do not paste "
              "errors back or coach it; let it stop on its own.")
    return 0


def extract_code(reply):
    blocks, cur, inb = [], [], False
    for line in reply.splitlines():
        if line.strip().startswith("```"):
            if inb:
                blocks.append("\n".join(cur)); cur = []
            inb = not inb
            continue
        if inb:
            cur.append(line)
    if inb and cur:
        blocks.append("\n".join(cur))
    return (max(blocks, key=len) if blocks else reply), len(blocks)


def do_grade(args):
    spec = SPECS[args.tool]
    cell = cell_dir(args.label, args.tool, args.arm, args.rep)
    ws = os.path.join(cell, "workspace")
    if not os.path.isdir(ws):
        print("no such cell: %s  (run `setup` first)" % cell)
        return 1
    meta = {"tool": args.tool, "variant": "base", "rep": args.rep, "mode": "solo",
            "harness": args.harness, "arm": args.arm, "model": args.model,
            "label": args.label, "hand_run": True,
            "prompt_sha256": RB.sha256_file(spec["prompt"]),
            "graded": time.strftime("%Y-%m-%dT%H:%M:%S"), "failure_mode": None}
    if args.wall is not None:
        meta["wall_clock_agent_s"] = args.wall

    if args.arm == "single_shot":
        rp = os.path.join(cell, "reply.txt")
        if not os.path.isfile(rp):
            print("single-shot arm needs the model's reply saved at %s" % rp)
            return 1
        code, nblocks = extract_code(open(rp).read())
        arts = spec.get("artifacts", [])
        if len(arts) != 1:
            meta["single_shot_note"] = ("%d artifacts expected; only the largest "
                                        "code block was written" % len(arts))
        if arts:
            open(os.path.join(ws, arts[0]), "w").write(code + "\n")
        meta["single_shot_blocks"] = nblocks

    RB.restore_data_files(spec, ws)
    RB.reexecute_commands(spec, ws, meta)
    RB.run_grader(spec, cell, ws, meta, os.path.join(cell, "grade.txt"))
    meta["code_sha256"] = {a: RB.sha256_file(os.path.join(ws, a))
                           for a in spec.get("artifacts", [])
                           if os.path.isfile(os.path.join(ws, a))}
    meta["missing_artifacts"] = [a for a in spec.get("artifacts", [])
                                 if not os.path.isfile(os.path.join(ws, a))]
    if meta["missing_artifacts"] and not meta["failure_mode"]:
        meta["failure_mode"] = "no_artifact"
    if args.tool in content_probe.TOOLS:
        try:
            meta["content"] = content_probe.score_cell(args.tool, ws,
                                                       spec.get("data", []))
        except Exception as exc:
            meta["content"] = {"error": "%s: %s" % (type(exc).__name__, exc)}
    json.dump(meta, open(os.path.join(cell, "meta.json"), "w"), indent=1)

    c = meta.get("content") or {}
    extra = ("" if not c or "error" in c else
             "   content %d/%d method, %d/%d precise"
             % (c["method_passed"], c["total"], c["precise_passed"], c["total"]))
    print("%-14s %-11s rep%-2d  %s/%s%s   %s"
          % (args.tool, args.arm, args.rep, meta.get("passed"), meta.get("total"),
             extra, meta.get("failure_mode") or ""))
    for line in open(os.path.join(cell, "grade.txt")).read().splitlines():
        if line.startswith("FAIL "):
            print("     %s" % line)
    return 0


def do_report(args):
    import glob
    root = os.path.join(BENCH, "exp", "F_" + args.label)
    rows = []
    for f in sorted(glob.glob(os.path.join(root, "*", "*", "*", "meta.json"))):
        rows.append(json.load(open(f)))
    if not rows:
        print("no graded cells under %s" % os.path.relpath(root, REPO))
        return 1
    print("| tool | arm | rep | criteria | content method | content precise | failure |")
    print("|---|---|---|---|---|---|---|")
    for m in rows:
        c = m.get("content") or {}
        cm = "%d/%d" % (c["method_passed"], c["total"]) if c and "error" not in c else "-"
        cp = "%d/%d" % (c["precise_passed"], c["total"]) if c and "error" not in c else "-"
        print("| %s | %s | %d | %s/%s | %s | %s | %s |"
              % (m["tool"], m["arm"], m["rep"], m.get("passed"), m.get("total"),
                 cm, cp, m.get("failure_mode") or ""))
    for arm in sorted({m["arm"] for m in rows}):
        sub = [m for m in rows if m["arm"] == arm]
        full = sum(1 for m in sub if (m.get("total") or 0) and m["passed"] == m["total"])
        k = sum(m.get("passed") or 0 for m in sub)
        n = sum(m.get("total") or 0 for m in sub)
        print("\n%s: %d/%d cells full-pass, %d/%d criteria"
              % (arm, full, len(sub), k, n))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("setup", "grade"):
        s = sub.add_parser(name)
        s.add_argument("--tool", required=True, choices=TOOLS12)
        s.add_argument("--rep", type=int, default=1)
        s.add_argument("--arm", default="agentic", choices=("agentic", "single_shot"))
        s.add_argument("--label", default="opus5")
        if name == "setup":
            s.add_argument("--force", action="store_true")
        else:
            s.add_argument("--model", default="claude-opus-5")
            s.add_argument("--harness", default="claude-code")
            s.add_argument("--wall", type=float, default=None,
                           help="agent wall clock in seconds, if you timed it")
    r = sub.add_parser("report")
    r.add_argument("--label", default="opus5")
    args = ap.parse_args()
    venv_setup.activate_path()
    return {"setup": do_setup, "grade": do_grade, "report": do_report}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
