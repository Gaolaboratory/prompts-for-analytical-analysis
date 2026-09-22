#!/usr/bin/env python3
"""Experiment D, pair 2: generated features.py vs OpenMS FeatureFinderMetabo.

Tier (c) grades PASS/FAIL. A referee wants AGREEMENT: how many of the same
features does the generated tool find, and where do the two disagree?

Run with the pyopenms venv, which is deliberately SEPARATE from .venv-bench --
the benchmark interpreter is pinned and the agents run inside it, so installing
a reference tool there would change the environment under test.

    .venv-openms/bin/python bench/exp_d_pair2.py
"""
import csv, glob, json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MZML = os.path.join(REPO, "data", "feature_extraction", "BSA1_F1.mzML")
MZ_PPM, RT_TOL = 5.0, 10.0      # the prompt's own matching tolerances


def openms_features():
    """The standard OpenMS untargeted pipeline: mass-trace detection, elution
    peak detection, then feature finding. pyopenms 3.5 exposes these as three
    stages rather than the single FeatureFinderMetabo wrapper.

    Only the mass accuracy is set, to the prompt's own 5 ppm, so both tools are
    asked for the same thing. Nothing else is tuned -- tuning the reference to
    raise agreement would defeat the purpose of the comparison.
    """
    import pyopenms as oms
    exp = oms.MSExperiment()
    oms.MzMLFile().load(MZML, exp)
    exp.updateRanges()

    mtd = oms.MassTraceDetection()
    par = mtd.getParameters()
    par.setValue("mass_error_ppm", MZ_PPM)
    mtd.setParameters(par)
    traces = []
    mtd.run(exp, traces, 0)

    epd = oms.ElutionPeakDetection()
    split = []
    epd.detectPeaks(traces, split)

    ffm = oms.FeatureFindingMetabo()
    fm, chroms = oms.FeatureMap(), []
    ffm.run(split if split else traces, fm, chroms)

    print("  mass traces %d -> elution peaks %d -> features %d"
          % (len(traces), len(split), fm.size()))
    return [{"mz": f.getMZ(), "rt": f.getRT(), "intensity": f.getIntensity()}
            for f in fm]


def read_generated(path):
    out = []
    with open(path) as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            try:
                out.append({"mz": float(row["mz"]), "rt": float(row["rt_apex"]),
                            "intensity": float(row["apex_intensity"])})
            except (KeyError, ValueError, TypeError):
                continue
    return out


def match(a, b):
    """Greedy nearest match, highest-intensity first, each b used once."""
    used, pairs = set(), []
    for x in sorted(a, key=lambda r: -r["intensity"]):
        best, bd = None, None
        for j, y in enumerate(b):
            if j in used:
                continue
            if abs(x["rt"] - y["rt"]) > RT_TOL:
                continue
            ppm = abs(x["mz"] - y["mz"]) / y["mz"] * 1e6
            if ppm > MZ_PPM:
                continue
            d = ppm + abs(x["rt"] - y["rt"])
            if bd is None or d < bd:
                best, bd = j, d
        if best is not None:
            used.add(best)
            pairs.append((x, b[best]))
    return pairs


def main():
    print("running the OpenMS untargeted pipeline on BSA1_F1.mzML ...")
    ref = openms_features()
    ref_sorted = sorted(ref, key=lambda r: -r["intensity"])
    print("  OpenMS features (exhaustive): %d" % len(ref))
    print("""
  NOTE ON FRAMING. The prompt asks for the top 200 m/z windows -- roughly 240
  features -- and its criterion is 120 <= N <= 480. OpenMS at defaults is
  exhaustive. "Recall of OpenMS" would therefore compare a deliberately
  truncated tool against an exhaustive one and report the truncation as error.
  Two fair questions are asked instead:
    (a) PRECISION: of the features the generated tool reports, how many does
        OpenMS confirm anywhere in its full set?
    (b) TOP-N AGREEMENT: against OpenMS's own top-N by intensity, N matched to
        the generated tool's count, do the two pick the same features?
""")
    rows = []
    for ws in sorted(glob.glob(os.path.join(REPO, "bench", "exp", "E", "features_s",
                                            "base", "*", "workspace"))):
        path = os.path.join(ws, "features.tsv")
        if not os.path.isfile(path):
            continue
        rep = os.path.basename(os.path.dirname(ws))
        gen = read_generated(path)
        if not gen:
            continue
        conf = match(gen, ref)                       # (a) against everything
        topn = ref_sorted[:len(gen)]
        agree = match(gen, topn)                     # (b) like-for-like
        import math
        difs = sorted(math.log10(g["intensity"] / r["intensity"])
                      for g, r in conf if g["intensity"] > 0 and r["intensity"] > 0)
        med = difs[len(difs) // 2] if difs else float("nan")
        rows.append({"rep": rep, "generated": len(gen),
                     "precision": len(conf) / len(gen),
                     "topn_agreement": len(agree) / len(gen),
                     "log10_ratio_median": med})
        print("  rep%-3s n=%3d   precision %5.1f%%   top-%d agreement %5.1f%%   "
              "log10(gen/openms) median %+.2f"
              % (rep, len(gen), 100 * len(conf) / len(gen), len(gen),
                 100 * len(agree) / len(gen), med))

    if rows:
        import statistics as st
        pr = [r["precision"] for r in rows]
        tn = [r["topn_agreement"] for r in rows]
        md = [r["log10_ratio_median"] for r in rows]
        print("\nacross %d generated programs:" % len(rows))
        print("  precision vs the full OpenMS set : %.1f%% (%.1f-%.1f)"
              % (100 * st.median(pr), 100 * min(pr), 100 * max(pr)))
        print("  agreement with OpenMS's own top-N: %.1f%% (%.1f-%.1f)"
              % (100 * st.median(tn), 100 * min(tn), 100 * max(tn)))
        print("  log10 intensity ratio, median    : %+.2f  (=%.2fx)"
              % (st.median(md), 10 ** st.median(md)))
        print("""
  The intensity offset is definitional, not an error: the prompt mandates
  `apex_intensity`, a single apex, while OpenMS reports an integrated/summed
  trace. A constant factor is what agreement looks like here; its tightness,
  not its value, is the signal.""")
    json.dump({"mz_ppm": MZ_PPM, "rt_tol_s": RT_TOL, "openms_n": len(ref),
               "programs": rows},
              open(os.path.join(REPO, "bench", "exp_d_pair2.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
