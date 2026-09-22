#!/usr/bin/env python3
"""Self-test: the probe must score a CONFORMANT submission full marks.

A probe whose aliases do not match the prompt's own mandated field names reports
zero for a perfect program, and would do it silently across a whole grid. Two
real alias bugs were caught this way before any cell was scored: `fwhm` appears
only as bands.tsv's `fwhm_nm` column and never on uvvis stdout, and a bare
"pc1" alias reads the first sample's PC1 SCORE out of scores.tsv instead of the
variance fraction.

Run: .venv-bench/bin/python3 bench/tests/test_content_probe.py
"""
import os, shutil, sys, tempfile

BENCH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BENCH)
import content_probe as CP
from specs import SPECS

# Exactly what each prompt's Output section mandates, filled with the reference
# values -- i.e. what a fully conformant program writes.
CONFORMANT = {
    "calibration_s": lambda r: {
        "stdout.log": "n=36 slope=%.15g intercept=%.15g residual_sd=%.15g "
                      "r_squared=%.15g lod=%.15g loq=%.15g\n"
                      % (r["slope"], r["intercept"], r["residual_sd"],
                         r["r_squared"], r["lod"], r["loq"]),
        "results.tsv": "slope\tintercept\tresidual_sd\tr_squared\tlod\tloq\n"
                       + "\t".join("%.15g" % r[k] for k in
                                   ("slope", "intercept", "residual_sd",
                                    "r_squared", "lod", "loq")) + "\n"},
    "titration_s": lambda r: {
        # 4 decimals / 1 sig fig: exactly what the real submissions printed.
        # The earlier %.10g fixture hid a tolerance bug that zeroed three cells.
        "stdout.log": "points=%d Veq=%.4f pKa=%.4f conc=%.3g\n"
                      % (r["points"], r["veq"], r["pka"], r["conc"]),
        "results.tsv": "equivalence_volume_mL\tpKa\tanalyte_concentration_M\n"
                       "%.4f\t%.4f\t%.3g\n" % (r["veq"], r["pka"], r["conc"])},
    "uvvis_s": lambda r: {
        "stdout.log": "points=%d bands=%d lambda_max=%.2f epsilon=%.1f\n"
                      % (r["points"], r["bands"], r["lambda_max"], r["epsilon"]),
        "bands.tsv": "lambda_max_nm\tepsilon\tfwhm_nm\n%.2f\t%.1f\t%.2f\n"
                     % (r["lambda_max"], r["epsilon"], r["fwhm"])},
    "pca_s": lambda r: {
        "stdout.log": "features_in=%d features_kept=%d pc1_var=%.4f pc2_var=%.4f\n"
                      % (r["features_in"], r["features_kept"], r["pc1_var"], r["pc2_var"]),
        # The trap: scores.tsv's own PC1/PC2 columns must NOT be read as the
        # variance fractions. Sample 1's scores here are deliberately nothing
        # like pc1_var/pc2_var, so a regression shows up as a wrong value.
        "scores.tsv": "sample\tgroup\tPC1\tPC2\nS1\tA\t12.5\t-3.25\nS2\tB\t-8.0\t4.5\n"},
    "mass_stats_s": lambda r: {
        "stdout.log": "tested=%d filtered=%d significant=%d\n"
                      % (r["tested"], r["filtered"], r["significant"]),
        "stats.tsv": "feature_id\tlog2fc\tt\tdf\tp_value\tq_value\tsignificant\n"
                     "F1\t1.5\t3.0\t3.1\t0.001\t0.01\t1\n"},
    "formula_s": lambda r: {
        "stdout.log": "blocks=%d candidates=%d\n" % (r["blocks"], r["candidates"]),
        "ranked.tsv": "id\trank\tformula\tcalc_mass\terror_ppm\tscore\n"
                      "CAFFEINE\t1\tC8H10N4O2\t194.080376\t-0.124\t0.13\n"},
    "chrom_s": lambda r: {
        "stdout.log": "points=9000 baseline=%.10g sigma=%.10g peaks=%d\n"
                      % (r["baseline"], r["sigma"], r["n_peaks"]),
        "peaks.tsv": "peak_id\trt_apex_s\theight\tarea\n1\t100.0\t5.0\t50.0\n"},
}


def mutated(build, ref, field):
    """The conformant submission with one field scaled by 1.10 (or +7 for a
    count), i.e. a deliberately wrong program."""
    bad = dict(ref)
    v = bad[field]
    bad[field] = v + 7 if isinstance(v, int) else v * 1.10
    return build(bad)


def negative_control(tool, build, ref):
    """Every field must be shown to FAIL on a deliberately wrong value, and to
    read 'absent' on an empty workspace.

    This is the tutorial's own rule -- validate every criterion with one
    deliberate mutation before trusting it -- applied to the analysis code that
    scores the experiment. A probe that has never been shown to fail is a
    detector that has never been shown a blank, and the earlier alias bugs are
    the proof that the concern is not theoretical: a bare `pc1` alias returned a
    number for every cell, so nothing looked wrong.
    """
    bad = 0
    ws = tempfile.mkdtemp()
    try:
        res = CP.score_cell(tool, ws, SPECS[tool].get("data", []))
        if res["present"] != 0:
            print("      empty workspace scored present=%d, expected 0" % res["present"])
            bad += 1
    finally:
        shutil.rmtree(ws, ignore_errors=True)
    for field in CP.TOOLS[tool]["fields"]:
        ws = tempfile.mkdtemp()
        try:
            for name, body in mutated(build, ref, field).items():
                open(os.path.join(ws, name), "w").write(body)
            res = CP.score_cell(tool, ws, SPECS[tool].get("data", []))
            if res["fields"][field]["method"]:
                print("      mutating %s did NOT fail the probe (found=%s)"
                      % (field, res["fields"][field]["found"]))
                bad += 1
        finally:
            shutil.rmtree(ws, ignore_errors=True)
    return bad


def main():
    failures = 0
    for tool, build in CONFORMANT.items():
        ref = CP.reference(tool)
        ws = tempfile.mkdtemp()
        try:
            for name, body in build(ref).items():
                open(os.path.join(ws, name), "w").write(body)
            res = CP.score_cell(tool, ws, SPECS[tool].get("data", []))
            ok = (res["precise_passed"] == res["total"])
            print("%-16s precise %d/%d  method %d/%d  %s"
                  % (tool, res["precise_passed"], res["total"],
                     res["method_passed"], res["total"], "OK" if ok else "*** FAIL"))
            if not ok:
                failures += 1
                for f, r in res["fields"].items():
                    if not r["precise"]:
                        print("      %-14s want=%-22s found=%-24s %s"
                              % (f, r["want"], r["found"], r["note"]))
        finally:
            shutil.rmtree(ws, ignore_errors=True)
        nbad = negative_control(tool, build, ref)
        if nbad:
            failures += 1
            print("%-16s negative control: %d problem(s)" % (tool, nbad))
    print("\n%s" % ("all conformant submissions score full marks, and every "
                    "field fails when mutated"
                    if not failures else "%d tool(s) FAILED" % failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
