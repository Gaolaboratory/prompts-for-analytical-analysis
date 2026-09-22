#!/usr/bin/env python3
"""Format-agnostic scoring of what a program actually computed.

Why this exists. Experiment A's pilot found that the shipped graders cannot
resolve the bottom of the specification ladder: at L0 and at L2 `calibration_s`
scores 0/6 alike, because without the output contract there is no `results.tsv`
with the mandated columns for any criterion to read. But the two are not the
same program at all --

    L0 stdout:  slope  1.002117
    L2 stdout:  slope  1.00211681802045
    NIST:              1.00211681802045

L2 reproduces the certified value to every digit it prints and is graded zero.
That is not a defect in the graders: a tool whose output nothing can parse is
genuinely unusable, and saying so is the output contract's whole justification.
It is a defect in using those graders, alone, as the dependent variable of an
ablation.

So each cell is scored twice. The strict score is the shipped grader,
unmodified, exactly as published. The content score ignores filename, column
order, separator, orientation and stream entirely, and asks only: is the right
number present anywhere the program wrote it? The gap between the two curves is
the measured value of the output contract, and the content curve decomposes
further by tolerance:

    method   1e-6 relative   the algorithm is right
    precise  tool tolerance  the algorithm is right AND printed precisely enough

A quantity the program never emitted counts as absent, not as wrong; a quantity
emitted twice with different values counts as wrong, since a reader could not
tell which was meant.
"""
import json, os, re, sys

BENCH = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BENCH)
sys.path.insert(0, os.path.join(BENCH, "reference"))

NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
HARVEST_SUFFIXES = (".tsv", ".csv", ".txt", ".log", ".out", ".json", ".dat", ".md")
MAX_FILE_BYTES = 4_000_000
METHOD_TOL = 1e-6

# Per tool: {quantity: (reference_key, aliases, strict_tol, kind)}
# kind: "rel" relative tolerance, "abs" absolute, "int" an exact count.
#
# "abs" exists because a tolerance must never be tighter than the precision the
# prompt itself mandates. pca_s's Output section says "variance fractions to 4
# decimals", so a fully conformant program prints pc1_var=0.1558 -- which is
# 2.1e-4 away from 0.15583326 in RELATIVE terms and would fail a 1e-4 relative
# check. That is the p3 sweep's own significant-figures defect (calibration_s,
# 2026-09-04) reappearing inside this probe, and the self-test in
# bench/tests/test_content_probe.py is what caught it before any cell was scored.
TOOLS = {
    "calibration_s": {
        "ref": lambda: _ref("calibration_ref").run(_d("calibration", "norris.csv")),
        "fields": {
            "slope":       ("slope",       ["slope"],                         1e-9, "rel"),
            "intercept":   ("intercept",   ["intercept"],                     1e-9, "rel"),
            "residual_sd": ("residual_sd", ["residual_sd", "resid_sd",
                                            "residual_std_dev", "residual sd",
                                            "sigma", "s_yx"],                 1e-9, "rel"),
            "r_squared":   ("r_squared",   ["r_squared", "r2", "rsq", "r^2"],  1e-9, "rel"),
            "lod":         ("lod",         ["lod"],                           1e-6, "rel"),
            "loq":         ("loq",         ["loq"],                           1e-6, "rel"),
        }},
    "titration_s": {
        "ref": lambda: _ref("titration_ref").analyse(_d("titration", "acetic_acid_naoh.csv")),
        "fields": {
            "veq":  ("veq",  ["veq", "v_eq", "equivalence",
                             "equivalence_volume_mL", "equivalence_volume"], 2e-3, "rel"),
            "pka":  ("pka",  ["pka", "pk_a"],                     2e-2, "rel"),
            "conc": ("conc", ["conc", "concentration", "c_acid",
                              "analyte_concentration_M",
                              "analyte_concentration"],           5e-2, "rel"),
        }},
    "uvvis_s": {
        "ref": lambda: _ref("uvvis_ref").run(_d("uvvis", "4-nitrophenol.csv")),
        "fields": {
            "lambda_max": ("lambda_max", ["lambda_max", "lmax", "lambdamax",
                                          "lambda_max_nm", "wavelength_max",
                                          "λmax"],                        1e-4, "rel"),
            "epsilon":    ("epsilon",    ["epsilon", "eps", "molar_absorptivity"], 1e-4, "rel"),
            # `fwhm` never appears on stdout for this tool -- only as the
            # `fwhm_nm` column of bands.tsv -- so the unit-suffixed spelling is
            # not optional here.
            "fwhm":       ("fwhm",       ["fwhm", "fwhm_nm", "width"],     1e-4, "rel"),
            "bands":      ("bands",      ["bands", "n_bands", "band_count"], 0, "int"),
        }},
    "pca_s": {
        "ref": lambda: _ref("pca_ref").run(_d("pca", "features.csv"), _d("pca", "groups.csv")),
        "fields": {
            "features_in":   ("features_in",   ["features_in", "n_features_in"], 0, "int"),
            "features_kept": ("features_kept", ["features_kept", "kept"],        0, "int"),
            # Deliberately NOT aliased to bare "pc1"/"pc2": scores.tsv's own
            # columns are headed PC1/PC2, so the wide-table matcher would read
            # the first sample's SCORE as the variance fraction. A probe that
            # silently reads the wrong column is worse than one that finds
            # nothing, because nothing is visible as "absent".
            "pc1_var":       ("pc1_var",       ["pc1_var", "pc1_variance",
                                                "var_pc1", "pc1_explained"],   1e-4, "abs"),
            "pc2_var":       ("pc2_var",       ["pc2_var", "pc2_variance",
                                                "var_pc2", "pc2_explained"],   1e-4, "abs"),
        }},
    "chrom_s": {
        "ref": lambda: _chrom(),
        "fields": {
            "n_peaks":  ("n_peaks",  ["n_peaks", "peaks", "npeaks", "peak_count"], 0, "int"),
            "baseline": ("baseline", ["baseline"],                                 1e-4, "rel"),
            "sigma":    ("sigma",    ["sigma", "noise"],                           1e-3, "rel"),
        }},
    # Added for Experiment B: amb-stream and amb-sep are FORMAT injections whose
    # whole point is that the statistics stay right while the output breaks.
    # Without a content score for this tool that claim cannot be demonstrated,
    # only asserted.
    "mass_stats_s": {
        "ref": lambda: _mass_stats(),
        "fields": {
            "tested":      ("tested",      ["tested", "n_tested"],           0, "int"),
            "filtered":    ("filtered",    ["filtered", "n_filtered"],       0, "int"),
            "significant": ("significant", ["significant", "n_significant"], 0, "int"),
        }},
    # amb-window removes the ppm window: `candidates` is the quantity that moves
    # (reference 35; the p3 sweep's unbounded run emitted 6,495,441) and the one
    # nothing compared to a reference until that grader was fixed.
    "formula_s": {
        "ref": lambda: _formula(),
        "fields": {
            "blocks":     ("blocks",     ["blocks", "n_blocks"],         0, "int"),
            "candidates": ("candidates", ["candidates", "n_candidates"], 0, "int"),
        }},
    "dda_s": {
        "ref": lambda: _dda(),
        "fields": {
            "targets":        ("targets",        ["targets"],        0, "int"),
            "decoys":         ("decoys",         ["decoys"],         0, "int"),
            "spectra":        ("spectra",        ["spectra"],        0, "int"),
            "with_candidate": ("with_candidate", ["with_candidate"], 0, "int"),
            "best_hits":      ("best_hits",      ["best_hits"],      0, "int"),
        }},
}

# Some field names legitimately appear twice in one submission with different
# meanings. mass_stats_s is the clear case: the prompt mandates a stdout count
# `significant=253` AND a per-row `significant` column of 0/1 flags in
# stats.tsv, so an unrestricted search finds both and can only call it
# ambiguous. RESTRICT names, per field, the files that may supply a value.
#
# The restriction is to the STREAM files, not to stdout.log alone, and that
# distinction is load-bearing: Experiment B's `amb-stream` variant pushes the
# counts to stderr, and the whole point of that variant is that the statistics
# are right while the stream is wrong. Restricting to stdout.log would score it
# as absent and conflate "wrong stream" with "wrong science" -- the exact
# conflation this probe exists to prevent.
STREAMS = ("stdout.log", "stderr.log")
RESTRICT = {
    "mass_stats_s": {"tested": STREAMS, "filtered": STREAMS, "significant": STREAMS},
    "formula_s": {"blocks": STREAMS, "candidates": STREAMS},
    "dda_s": {k: STREAMS for k in
              ("targets", "decoys", "spectra", "with_candidate", "best_hits")},
}

_CACHE = {}


def _d(tool, name):
    return os.path.join(REPO, "data", tool, name)


def _ref(name):
    import importlib
    return importlib.import_module("short." + name)


def _chrom():
    r = _ref("chrom_ref").run(_d("chrom", "chrom.csv"))
    return {"n_peaks": len(r["peaks"]), "baseline": r["baseline"], "sigma": r["sigma"]}


def _mass_stats():
    r = _ref("mass_stats_ref").run(_d("mass_stats", "quant_mtbls14397_pos.csv"),
                                   _d("mass_stats", "groups.tsv"))
    return {k: r[k] for k in ("tested", "filtered", "significant")}


def _formula():
    r = _ref("formula_ref").run(_d("formula", "measured_caffeine.tsv"))
    return {k: r[k] for k in ("blocks", "candidates")}


def _dda():
    r = _ref("dda_ref").run(_d("database_search", "yeast_pe1_plus_ups.fasta"),
                            _d("database_search", "ups1_yeast_dda_first1200.mgf"))
    return {k: r[k] for k in ("targets", "decoys", "spectra", "with_candidate", "best_hits")}


def reference(tool):
    if tool not in _CACHE:
        _CACHE[tool] = TOOLS[tool]["ref"]()
    return _CACHE[tool]


def harvest(workspace, inputs):
    """Every scrap of text the program produced, as one string per file.

    Input files are excluded by name: a program that echoes its input back must
    not get credit for numbers it copied rather than computed. The program's own
    source is excluded for the same reason -- a hardcoded constant in the source
    is not an emitted result.
    """
    out = []
    skip = {os.path.basename(p) for p in inputs} | {"norris.csv"}
    for name in sorted(os.listdir(workspace)):
        path = os.path.join(workspace, name)
        if not os.path.isfile(path) or name in skip:
            continue
        if name.endswith(".py"):
            continue
        if not name.lower().endswith(HARVEST_SUFFIXES):
            continue
        try:
            if os.path.getsize(path) > MAX_FILE_BYTES:
                with open(path, errors="replace") as fh:
                    out.append((name, fh.read(MAX_FILE_BYTES)))
                continue
            with open(path, errors="replace") as fh:
                out.append((name, fh.read()))
        except OSError:
            continue
    return out


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def find_values(text, aliases):
    """Every number this text associates with any alias, format-agnostically.

    Three shapes are recognised, which between them cover everything the ladder
    produced: `name=value` / `name: value` / `name<TAB>value` (inline), a long
    table whose row begins with the name, and a wide table whose HEADER carries
    the name with the value in the same column of the following row.
    """
    found, keys = [], {_norm(a) for a in aliases}
    # inline and long-table forms
    for line in text.splitlines():
        for m in re.finditer(r"([A-Za-z_][A-Za-z0-9_ ^.]{0,28}?)\s*[=:\t,|]\s*(" + NUM + r")\b", line):
            if _norm(m.group(1)) in keys:
                found.append(float(m.group(2)))
        for m in re.finditer(r"([A-Za-z_][A-Za-z0-9_^.]{0,28})\s+(" + NUM + r")\s*$", line):
            if _norm(m.group(1)) in keys:
                found.append(float(m.group(2)))
    # wide-table form: header row naming the column, values on a later row
    lines = text.splitlines()
    for i, line in enumerate(lines):
        cells = re.split(r"[\t,;|]|\s{2,}", line.strip())
        cells = [c.strip() for c in cells]
        idxs = [j for j, c in enumerate(cells) if _norm(c) in keys]
        if not idxs:
            continue
        for follow in lines[i + 1:i + 4]:
            fcells = [c.strip() for c in re.split(r"[\t,;|]|\s{2,}", follow.strip())]
            if len(fcells) != len(cells):
                continue
            for j in idxs:
                try:
                    found.append(float(fcells[j]))
                except ValueError:
                    pass
            break
    return found


def method_tol(strict_tol, kind):
    """The looser bound at which a value counts as 'the algorithm is right'.

    Two invariants, both learned by getting them wrong:

    1. It must be expressed in the same KIND as the strict check. Applying a
       relative bound to a quantity whose precision the prompt fixed in decimals
       re-creates, one level up, exactly the significant-figures defect this
       module's header describes.
    2. It must NEVER be tighter than the strict bound. METHOD_TOL is 1e-6, which
       is looser than calibration_s's 1e-9 but *tighter* than titration_s's
       2e-3 -- so before this max(), a correct titration tool printing the
       perfectly reasonable `Veq=24.9977` (1.4e-6 relative from the reference)
       was scored as having the wrong method, on all three cells of a tool that
       passed the shipped grader 6/6. "Method" is by definition the weaker
       claim; it can never fail where "precise" would pass.
    """
    if kind == "int":
        return 0
    if kind == "abs":
        return max(10 * strict_tol, 1e-3)
    return max(METHOD_TOL, strict_tol)


def agrees(got, want, tol, kind):
    if kind == "int":
        return float(got) == float(want)
    if kind == "abs":
        return abs(got - want) <= tol
    if want == 0:
        return abs(got) <= tol
    return abs(got - want) / abs(want) <= tol


def score_cell(tool, workspace, inputs):
    spec, ref = TOOLS[tool], reference(tool)
    texts = harvest(workspace, inputs)
    blob = "\n".join(t for _, t in texts)
    restrict = RESTRICT.get(tool, {})
    by_name = dict(texts)
    out = {"fields": {}, "method_passed": 0, "precise_passed": 0,
           "present": 0, "total": len(spec["fields"])}
    for field, (refkey, aliases, strict_tol, kind) in spec["fields"].items():
        want = ref[refkey]
        allowed = restrict.get(field)
        haystack = ("\n".join(by_name.get(n, "") for n in allowed)
                    if allowed else blob)
        vals = find_values(haystack, aliases)
        uniq = sorted({round(v, 12) for v in vals})
        rec = {"want": want, "found": uniq[:6], "n_found": len(uniq)}
        if allowed:
            rec["sources"] = list(allowed)
        mtol = method_tol(strict_tol, kind)
        if not uniq:
            rec.update(present=False, method=False, precise=False, note="absent")
        elif len(uniq) > 1 and not all(agrees(v, want, mtol, kind) for v in uniq):
            # Ambiguous: more than one distinct value claims the same name and
            # they do not agree. A reader could not tell which was meant.
            rec.update(present=True, method=False, precise=False, note="ambiguous")
            out["present"] += 1
        else:
            v = (uniq[0] if len(uniq) == 1
                 else next(x for x in uniq if agrees(x, want, mtol, kind)))
            m = agrees(v, want, mtol, kind)
            pr = m and agrees(v, want, strict_tol, kind)
            rec.update(present=True, method=m, precise=pr,
                       note="ok" if pr else ("method only" if m else "wrong"))
            out["present"] += 1
            out["method_passed"] += int(m)
            out["precise_passed"] += int(pr)
        out["fields"][field] = rec
    out["files_seen"] = [n for n, _ in texts]
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("tool")
    ap.add_argument("workspace")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    sys.path.insert(0, BENCH)
    from specs import SPECS
    inputs = SPECS[args.tool].get("data", [])
    res = score_cell(args.tool, args.workspace, inputs)
    if args.json:
        print(json.dumps(res, indent=1))
    else:
        for f, r in res["fields"].items():
            print("%-16s want=%-22s found=%-28s %s"
                  % (f, r["want"], r["found"], r["note"]))
        print("method %d/%d  precise %d/%d  present %d/%d"
              % (res["method_passed"], res["total"], res["precise_passed"],
                 res["total"], res["present"], res["total"]))


if __name__ == "__main__":
    main()
