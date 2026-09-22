#!/usr/bin/env python3
"""Experiment D, pair 1: generated calibrate.py vs scipy vs the NIST certificate.

The review's point was that tier (c) grades PASS/FAIL where a referee wants
AGREEMENT. So this does not ask "did it pass"; it asks how far each generated
program's coefficients sit from the certified values, and from what a
practitioner would have written instead (scipy.stats.linregress).

The programs are the ones the models actually wrote, taken unmodified from the
preserved workspaces of Experiment A's L4 arm. They are re-executed here on the
same input, and their stdout is parsed the way the grader parses it.
"""
import glob, json, os, re, subprocess, sys, tempfile, shutil

BENCH = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BENCH)
sys.path.insert(0, BENCH)
import venv_setup

# NIST StRD Norris certified values, written literally here -- not imported from
# any reference implementation, so a wrong reference cannot certify a wrong tool.
CERT = {"slope": 1.00211681802045, "intercept": -0.262323073774029,
        "residual_sd": 0.884796396144373, "r_squared": 0.999993745883712}
NORRIS = os.path.join(REPO, "data", "calibration", "norris.csv")
NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"


def scipy_reference():
    import numpy as np
    from scipy import stats
    import pandas as pd
    d = pd.read_csv(NORRIS)
    r = stats.linregress(d["x"], d["y"])
    n = len(d)
    resid = d["y"] - (r.intercept + r.slope * d["x"])
    return {"slope": float(r.slope), "intercept": float(r.intercept),
            "residual_sd": float(np.sqrt((resid ** 2).sum() / (n - 2))),
            "r_squared": float(r.rvalue ** 2)}


def run_program(src_dir):
    """Re-execute a preserved calibrate.py on norris.csv; parse its stdout."""
    ws = tempfile.mkdtemp()
    try:
        shutil.copy2(os.path.join(src_dir, "calibrate.py"), ws)
        shutil.copy2(NORRIS, ws)
        p = subprocess.run([venv_setup.venv_python(), "calibrate.py", "norris.csv",
                            "-o", "results.tsv"], cwd=ws, capture_output=True,
                           text=True, timeout=300)
        out = p.stdout + p.stderr
        got = {}
        for k in CERT:
            m = re.search(k + r"\s*[=:]\s*(" + NUM + ")", out)
            if m:
                got[k] = float(m.group(1))
        return got if len(got) == len(CERT) else None
    except Exception:
        return None
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def rel(a, b):
    return abs(a - b) / abs(b) if b else abs(a)


def main():
    venv_setup.activate_path()
    ref = scipy_reference()
    print("scipy.stats.linregress vs NIST certificate")
    for k in CERT:
        print("  %-12s scipy %-22.15g  cert %-22.15g  rel %.2e"
              % (k, ref[k], CERT[k], rel(ref[k], CERT[k])))

    dirs = sorted(glob.glob(os.path.join(BENCH, "exp", "A", "calibration_s",
                                         "L4", "*", "workspace")))
    print("\n%d generated programs from Experiment A's L4 arm" % len(dirs))
    rows, worst = [], {k: 0.0 for k in CERT}
    for d in dirs:
        got = run_program(d)
        rep = os.path.basename(os.path.dirname(d))
        if not got:
            print("  rep%-3s could not be re-executed or parsed" % rep)
            continue
        devs = {k: rel(got[k], CERT[k]) for k in CERT}
        for k in CERT:
            worst[k] = max(worst[k], devs[k])
        rows.append((rep, got, devs))
        print("  rep%-3s " % rep + "  ".join("%s %.1e" % (k[:4], devs[k]) for k in CERT))

    if rows:
        print("\nworst deviation from the certificate across %d programs:" % len(rows))
        for k in CERT:
            print("  %-12s %.2e" % (k, worst[k]))
        print("\nscipy's own deviation, for scale:")
        for k in CERT:
            print("  %-12s %.2e" % (k, rel(ref[k], CERT[k])))
        agree = sum(1 for _, g, _ in rows
                    if all(rel(g[k], ref[k]) <= 1e-9 for k in CERT))
        print("\n%d of %d generated programs agree with scipy to <=1e-9 relative "
              "on all four coefficients." % (agree, len(rows)))
    json.dump({"certificate": CERT, "scipy": ref,
               "programs": [{"rep": r, "values": g, "rel_to_cert": d}
                            for r, g, d in rows]},
              open(os.path.join(BENCH, "exp_d_pair1.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
