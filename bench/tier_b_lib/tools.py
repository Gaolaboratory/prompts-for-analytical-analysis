"""Per-tool tier (b) specs: perturbations, reference recomputation, grading.

Each entry in TOOLS is a dict:
  key          bench/runs/<key> subdirectory name
  mode         None, or "solo" (dda_s / features_s keep both solo and
               prebuilt trees; tier (b) always uses solo -- the programs the
               model actually wrote, per the task).
  artifacts    submitted filenames to copy out of the rep's workspace
  data_dir     subdirectory of data/ holding the real input(s)
  inputs       basenames of the real input file(s), copied unperturbed into
               a fresh tmp dir before every perturbation's apply() edits them
  script       the artifact file that is actually executed
  build_argv() -> argv (after "python3 <script>") for the run
  timeout      per-run subprocess timeout, seconds
  perturbations  list of Perturbation(name, description, apply)
                 apply(tmp_dir) mutates the already-copied inputs in place
  reference(tmp_dir) -> dict           recomputed from tmp_dir's own inputs
  describe_effect(before, after) -> str   human-readable delta for the report
  grade(tmp_dir, run_result, ref) -> list[(criterion, passed, detail)]
  skip_notes   tier (a) criteria this harness does NOT re-check, and why
"""
import math
import os
import re
import shutil
import sys

from common import (REPO, DATA, num_field, read_text, rel_ok, close_abs,
                     named_fields, capped_line_count, capped_read_lines,
                     keep_spectra, run_program)

import calibration_ref
import chrom_ref
import uvvis_ref
import spectral_ref
import formula_ref
import mass_stats_ref
import pca_ref
import titration_ref
import nmr_ref
import features_ref
import dda_ref
import mzml_reader as trusted_mzml
import fasta_reader as trusted_fasta


class Perturbation:
    def __init__(self, name, description, apply):
        self.name = name
        self.description = description
        self.apply = apply


def _copy_inputs(tool, tmp_dir):
    for base in tool["inputs"]:
        shutil.copy2(os.path.join(DATA, tool["data_dir"], base),
                     os.path.join(tmp_dir, base))


def _copy_artifacts(tool, ws, tmp_dir):
    """Copy each of tool["artifacts"] out of the rep's workspace into tmp_dir.

    Tries the workspace root first (the normal case); if a name isn't there,
    falls back to a recursive search by basename and preserves that file's
    path RELATIVE TO ws when copying it in -- some submissions (observed:
    dda_s rep 2's search.py) keep a dependency module in a subdirectory (e.g.
    examples/mass_reader/fasta_reader.py) and add that subdirectory to
    sys.path relative to the running script's own location, so the same
    relative layout has to exist under tmp_dir for the import to resolve.
    Returns the list of names genuinely not found anywhere in ws."""
    missing = []
    for name in tool["artifacts"]:
        direct = os.path.join(ws, name)
        if os.path.isfile(direct):
            shutil.copy2(direct, os.path.join(tmp_dir, name))
            continue
        found = None
        for root, _dirs, files in os.walk(ws):
            if name in files:
                found = os.path.join(root, name)
                break
        if found is None:
            missing.append(name)
            continue
        rel = os.path.relpath(found, ws)
        dst = os.path.join(tmp_dir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(found, dst)
    return missing


def _path(tmp, base):
    return os.path.join(tmp, base)


def _rewrite_csv(path, header_names, row_fn):
    """Read a simple CSV at `path` (any dtype), apply row_fn(dict) -> dict to
    every row (row_fn may mutate and return the same dict), and write it back
    in place with the same header order."""
    text = read_text(path, newline="")
    lines = [l for l in text.splitlines() if l.strip()]
    hdr = lines[0].split(",")
    out = [",".join(hdr)]
    for line in lines[1:]:
        vals = line.split(",")
        row = dict(zip(hdr, vals))
        row = row_fn(dict(row), len(out) - 1)  # 0-based data-row index
        out.append(",".join(row[h] for h in hdr))
    with open(path, "w", newline="") as fh:
        fh.write("\n".join(out) + "\n")


# ===========================================================================
# calibration_s
# ===========================================================================

def _calib_perturb_subset_scale(tmp_dir):
    """Every 4th row's y scaled by 1.20; the rest untouched. Non-uniform, so
    no single scale factor maps the perturbed OLS fit back onto the original
    or the NIST-certified values (see grade_calibration_s.py's own docstring
    for the uniform-rescale forgery this shape defeats)."""
    path = _path(tmp_dir, "norris.csv")

    def row(r, i):
        if i % 4 == 0:
            r["y"] = "%.10g" % (float(r["y"]) * 1.20)
        return r
    _rewrite_csv(path, None, row)


def _calib_perturb_ramp(tmp_dir):
    """A linear ramp added to y for the LAST THIRD of rows only; the first
    two-thirds are untouched. Not a uniform offset (only a subset of rows
    move, and by a different amount each) so it is not closed-form invertible
    from the unperturbed fit."""
    path = _path(tmp_dir, "norris.csv")
    lines = [l for l in read_text(path, newline="").splitlines() if l.strip()]
    n = len(lines) - 1
    cut = (2 * n) // 3

    def row(r, i):
        if i >= cut:
            r["y"] = "%.10g" % (float(r["y"]) + 0.6 * (i - cut))
        return r
    _rewrite_csv(path, None, row)


def _calib_reference(tmp_dir):
    return calibration_ref.run(_path(tmp_dir, "norris.csv"))


def _calib_effect(before, after):
    return ("slope %.6f -> %.6f, intercept %.6f -> %.6f, r_squared %.8f -> %.8f"
            % (before["slope"], after["slope"], before["intercept"],
               after["intercept"], before["r_squared"], after["r_squared"]))


def _calib_grade(tmp_dir, run, ref):
    out = []
    text = read_text(_path(tmp_dir, "results.tsv"), newline="") or ""
    lines = [l for l in text.splitlines() if l.strip()]
    hdr = lines[0].split("\t") if lines else []
    fields = lines[1].split("\t") if len(lines) > 1 else []
    names = ["slope", "intercept", "residual_sd", "r_squared", "lod", "loq"]
    named = named_fields(hdr, fields, names)
    vals = {}
    for n in names:
        try:
            vals[n] = float(named[n])
        except (KeyError, ValueError):
            vals[n] = None
    for n in ("slope", "intercept", "residual_sd", "r_squared", "lod", "loq"):
        out.append(("%s matches reference (<=1e-6 relative)" % n,
                     rel_ok(vals[n], ref[n], 1e-6),
                     "got %r want %r" % (vals[n], ref[n])))
    stdout = run["stdout"] + "\n" + run["stderr"]
    out.append(("stdout reports all seven fields",
                 all(num_field(stdout, k) is not None for k in
                     ("n", "slope", "intercept", "residual_sd", "r_squared",
                      "lod", "loq")),
                 stdout.strip()[:200]))
    return out


TOOLS_CALIBRATION = {
    "key": "calibration_s", "mode": None,
    "artifacts": ["calibrate.py"],
    "data_dir": "calibration", "inputs": ["norris.csv"],
    "script": "calibrate.py",
    "build_argv": lambda: ["norris.csv", "-o", "results.tsv"],
    "timeout": 60,
    "perturbations": [
        Perturbation("subset_scale",
                     "every 4th row's y scaled by 1.20, rest untouched",
                     _calib_perturb_subset_scale),
        Perturbation("tail_ramp",
                     "increasing ramp added to y for the last third of rows",
                     _calib_perturb_ramp),
    ],
    "reference": _calib_reference,
    "describe_effect": _calib_effect,
    "grade": _calib_grade,
    "skip_notes": [
        "NIST-certified slope/intercept/residual_sd/r_squared (Norris StRD): "
        "meaningless once the input is perturbed away from the certified file.",
    ],
}


# ===========================================================================
# titration_s
# ===========================================================================

def _titr_perturb_drift(tmp_dir):
    """pH drift: rows from the midpoint onward get an increasing additive
    offset (simulated electrode drift during the run). Non-uniform in time
    (first half untouched), so Veq does not simply translate."""
    path = _path(tmp_dir, "acetic_acid_naoh.csv")
    lines = [l for l in read_text(path, newline="").splitlines() if l.strip()]
    n = len(lines) - 1
    mid = n // 2

    def row(r, i):
        if i >= mid:
            r["pH"] = "%.3f" % (float(r["pH"]) + 0.015 * (i - mid))
        return r
    _rewrite_csv(path, None, row)


def _titr_perturb_compress(tmp_dir):
    """Volume increments after the midpoint are stretched 1.6x (pH values
    keep their original row order/values); increments before the midpoint are
    untouched. Not a uniform rescale of V (only the later deltas grow) and
    not a translation, so Veq moves by an amount the derivative/parabola-
    vertex step actually has to work out."""
    path = _path(tmp_dir, "acetic_acid_naoh.csv")
    lines = [l for l in read_text(path, newline="").splitlines() if l.strip()]
    hdr = lines[0].split(",")
    rows = [l.split(",") for l in lines[1:]]
    vols = [float(r[0]) for r in rows]
    n = len(vols)
    mid = n // 2
    new_vols = list(vols)
    acc = 0.0
    for i in range(mid, n):
        d = vols[i] - vols[i - 1]
        acc += d * 1.6
        new_vols[i] = new_vols[mid - 1] + acc if mid > 0 else acc
    out = [",".join(hdr)]
    for (v, ph), nv in zip(((float(r[0]), r[1]) for r in rows), new_vols):
        out.append("%.3f,%s" % (nv, ph))
    with open(path, "w", newline="") as fh:
        fh.write("\n".join(out) + "\n")


def _titr_reference(tmp_dir):
    return titration_ref.analyse(_path(tmp_dir, "acetic_acid_naoh.csv"))


def _titr_effect(before, after):
    return ("Veq %.4f -> %.4f mL, pKa %.4f -> %.4f"
            % (before["veq"], after["veq"], before["pka"], after["pka"]))


def _titr_grade(tmp_dir, run, ref):
    text = read_text(_path(tmp_dir, "results.tsv"), newline="") or ""
    lines = [l for l in text.splitlines() if l.strip()]
    veq = pka = conc = None
    if len(lines) == 2 and len(lines[1].split("\t")) == 3:
        try:
            veq, pka, conc = (float(x) for x in lines[1].split("\t"))
        except ValueError:
            pass
    out = [
        ("Veq matches reference (+/-0.05 mL)",
         close_abs(veq, ref["veq"], 0.05), "got %r want %.4f" % (veq, ref["veq"])),
        ("pKa matches reference (+/-0.02)",
         close_abs(pka, ref["pka"], 0.02), "got %r want %.4f" % (pka, ref["pka"])),
        ("concentration matches reference (+/-0.2%)",
         rel_ok(conc, ref["conc"], 0.002), "got %r want %.5f" % (conc, ref["conc"])),
    ]
    stdout = run["stdout"] + "\n" + run["stderr"]
    out.append(("stdout reports points/Veq/pKa/conc",
                 all(num_field(stdout, k) is not None
                     for k in ("points", "Veq", "pKa", "conc")),
                 stdout.strip()[:200]))
    return out


TOOLS_TITRATION = {
    "key": "titration_s", "mode": None,
    "artifacts": ["titration.py"],
    "data_dir": "titration", "inputs": ["acetic_acid_naoh.csv"],
    "script": "titration.py",
    "build_argv": lambda: ["acetic_acid_naoh.csv", "-o", "results.tsv"],
    "timeout": 60,
    "perturbations": [
        Perturbation("pH_drift", "increasing pH offset for rows past the midpoint",
                     _titr_perturb_drift),
        Perturbation("volume_compress",
                     "volume increments after the midpoint stretched 1.6x",
                     _titr_perturb_compress),
    ],
    "reference": _titr_reference,
    "describe_effect": _titr_effect,
    "grade": _titr_grade,
    "skip_notes": [
        "published Veq 25.0+/-0.5 mL / pKa 4.74+/-0.10 / conc 0.100 M+/-5%: "
        "tied to the shipped file, not re-derivable after perturbation.",
    ],
}


# ===========================================================================
# uvvis_s
# ===========================================================================

def _uvvis_perturb_shoulder(tmp_dir):
    """A small Gaussian bump added at 420 nm (well clear of the 317 nm band),
    amplitude 30% of the original spectrum max -- large enough to clear the
    20%-of-max band-calling threshold and register as a second band, small
    enough not to become the new global max."""
    path = _path(tmp_dir, "4-nitrophenol.csv")
    lines = [l for l in read_text(path, newline="").splitlines() if l.strip()]
    hdr = lines[0].split(",")
    rows = [l.split(",") for l in lines[1:]]
    a = [float(r[1]) for r in rows]
    amax = max(a)
    center, width = 420.0, 8.0
    out = [",".join(hdr)]
    for w_s, a_s in rows:
        w = float(w_s)
        bump = 0.30 * amax * math.exp(-((w - center) ** 2) / (2 * width ** 2))
        out.append("%s,%.5f" % (w_s, float(a_s) + bump))
    with open(path, "w", newline="") as fh:
        fh.write("\n".join(out) + "\n")


def _uvvis_perturb_decimate(tmp_dir):
    """Keep every other point (halves the resolution): the band maximum,
    half-height crossings and interpolated FWHM all have to be recomputed on
    a coarser grid, not merely re-read off the original answer."""
    path = _path(tmp_dir, "4-nitrophenol.csv")
    lines = [l for l in read_text(path, newline="").splitlines() if l.strip()]
    hdr, rows = lines[0], lines[1:]
    kept = [rows[i] for i in range(0, len(rows), 2)]
    with open(path, "w", newline="") as fh:
        fh.write("\n".join([hdr] + kept) + "\n")


def _uvvis_reference(tmp_dir):
    return uvvis_ref.run(_path(tmp_dir, "4-nitrophenol.csv"))


def _uvvis_effect(before, after):
    return ("points %d -> %d, bands %d -> %d, lambda_max %.3f -> %.3f, "
            "fwhm %.3f -> %.3f"
            % (before["points"], after["points"], before["bands"], after["bands"],
               before["lambda_max"], after["lambda_max"],
               before["fwhm"], after["fwhm"]))


def _uvvis_grade(tmp_dir, run, ref):
    text = read_text(_path(tmp_dir, "bands.tsv"), newline="") or ""
    lines = [l for l in text.splitlines() if l.strip()]
    hdr = lines[0].split("\t") if lines else []
    names = ["lambda_max_nm", "epsilon", "fwhm_nm"]
    got = {}
    if len(lines) > 1:
        named = named_fields(hdr, lines[1].split("\t"), names)
        for n in names:
            try:
                got[n] = float(named[n])
            except (KeyError, ValueError):
                got[n] = None
    else:
        got = {n: None for n in names}
    out = [
        ("lambda_max matches reference (+/-3 nm)",
         close_abs(got["lambda_max_nm"], ref["lambda_max"], 3.0),
         "got %r want %.3f" % (got["lambda_max_nm"], ref["lambda_max"])),
        ("epsilon matches reference (+/-3%)",
         rel_ok(got["epsilon"], ref["epsilon"], 0.03),
         "got %r want %.3f" % (got["epsilon"], ref["epsilon"])),
        ("fwhm matches reference (+/-10%)",
         rel_ok(got["fwhm_nm"], ref["fwhm"], 0.10),
         "got %r want %.3f" % (got["fwhm_nm"], ref["fwhm"])),
    ]
    stdout = run["stdout"] + "\n" + run["stderr"]
    bands_field = num_field(stdout, "bands")
    out.append(("stdout bands count matches reference",
                 bands_field is not None and int(bands_field) == ref["bands"],
                 "got %r want %d" % (bands_field, ref["bands"])))
    return out


TOOLS_UVVIS = {
    "key": "uvvis_s", "mode": None,
    "artifacts": ["uvvis.py"],
    "data_dir": "uvvis", "inputs": ["4-nitrophenol.csv"],
    "script": "uvvis.py",
    "build_argv": lambda: ["4-nitrophenol.csv", "-o", "bands.tsv"],
    "timeout": 60,
    "perturbations": [
        Perturbation("added_shoulder", "Gaussian bump injected at 420 nm",
                     _uvvis_perturb_shoulder),
        Perturbation("decimate", "keep every other point",
                     _uvvis_perturb_decimate),
    ],
    "reference": _uvvis_reference,
    "describe_effect": _uvvis_effect,
    "grade": _uvvis_grade,
    "skip_notes": [
        "published lambda_max=317 nm / epsilon=9283: tied to the shipped "
        "file, not re-derivable after perturbation.",
    ],
}


# ===========================================================================
# spectral_s
# ===========================================================================

def _spectral_perturb_library_reweight(tmp_dir):
    """In the library's `caffeine` entry, every OTHER peak's intensity is
    scaled to 30% of its original value (odd-indexed peaks only) -- the
    cosine-style score for any query matched against it changes, but no
    single scale factor describes the transform (half the peaks are
    untouched)."""
    path = _path(tmp_dir, "library.txt")
    text = read_text(path)
    lines = text.splitlines()
    out = []
    in_target, idx = False, 0
    for line in lines:
        s = line.strip()
        if s.startswith(">NAME"):
            in_target = (s.split()[1] == "caffeine")
            idx = 0
            out.append(line)
            continue
        if in_target and s and not s.startswith("#"):
            mz, inten = s.split()
            if idx % 2 == 1:
                inten = "%.1f" % (float(inten) * 0.30)
            out.append("%s %s" % (mz, inten))
            idx += 1
        else:
            out.append(line)
    with open(path, "w") as fh:
        fh.write("\n".join(out))


def _spectral_perturb_query_dropout(tmp_dir):
    """Drop every 3rd peak from query q2 -- fewer peaks to match means fewer
    matched_peaks and a different score against every library entry."""
    path = _path(tmp_dir, "queries.txt")
    text = read_text(path)
    lines = text.splitlines()
    out = []
    in_target, idx = False, 0
    for line in lines:
        s = line.strip()
        if s.startswith(">NAME"):
            in_target = (s.split()[1] == "q2")
            idx = 0
            out.append(line)
            continue
        if in_target and s and not s.startswith("#"):
            if idx % 3 == 2:
                idx += 1
                continue
            out.append(line)
            idx += 1
        else:
            out.append(line)
    with open(path, "w") as fh:
        fh.write("\n".join(out))


def _spectral_reference(tmp_dir):
    rows = spectral_ref.run(_path(tmp_dir, "queries.txt"), _path(tmp_dir, "library.txt"))
    return {r["query"]: r for r in rows}


def _spectral_effect(before, after):
    parts = []
    for q in sorted(set(before) | set(after)):
        b, a = before.get(q), after.get(q)
        if b is None or a is None:
            continue
        parts.append("%s: score %.4f->%.4f match %s->%s" %
                      (q, b["score"], a["score"], b["best_match"], a["best_match"]))
    return "; ".join(parts)


def _spectral_grade(tmp_dir, run, ref):
    text = read_text(_path(tmp_dir, "results.tsv"), newline="") or ""
    lines = [l for l in text.splitlines() if l.strip()]
    names = ["query", "best_match", "score", "matched_peaks", "total_library_peaks"]
    got = {}
    if lines:
        hdr = lines[0].split("\t")
        for line in lines[1:]:
            fields = line.split("\t")
            named = named_fields(hdr, fields, names)
            if "query" in named:
                got[named["query"]] = named
    out = []
    for q, want in sorted(ref.items()):
        row = got.get(q)
        if row is None:
            out.append(("%s: row present" % q, False, "missing from results.tsv"))
            continue
        try:
            score = float(row.get("score"))
        except (TypeError, ValueError):
            score = None
        try:
            matched = int(float(row.get("matched_peaks")))
        except (TypeError, ValueError):
            matched = None
        ok = (row.get("best_match") == want["best_match"]
              and close_abs(score, want["score"], 0.02)
              and matched == want["matched_peaks"])
        out.append(("%s: best_match/score/matched_peaks match reference" % q, ok,
                     "got (%r,%r,%r) want (%r,%.4f,%r)"
                     % (row.get("best_match"), score, matched,
                        want["best_match"], want["score"], want["matched_peaks"])))
    return out


TOOLS_SPECTRAL = {
    "key": "spectral_s", "mode": None,
    "artifacts": ["libsearch.py"],
    "data_dir": "spectral", "inputs": ["queries.txt", "library.txt"],
    "script": "libsearch.py",
    "build_argv": lambda: ["queries.txt", "library.txt", "-o", "results.tsv"],
    "timeout": 60,
    "perturbations": [
        Perturbation("library_reweight",
                     "odd-indexed peaks of library 'caffeine' scaled to 30%",
                     _spectral_perturb_library_reweight),
        Perturbation("query_peak_dropout",
                     "every 3rd peak dropped from query q2",
                     _spectral_perturb_query_dropout),
    ],
    "reference": _spectral_reference,
    "describe_effect": _spectral_effect,
    "grade": _spectral_grade,
    "skip_notes": [
        "the literal q1..q4 identities (caffeine/acetaminophen/"
        "sulfamethoxazole/NO_MATCH) are graded against the reference for "
        "THIS perturbed input, not the tier(a) published compound list.",
    ],
}


# ===========================================================================
# formula_s
# ===========================================================================

def _formula_perturb_mass_shift(tmp_dir):
    """CAFFEINE's mass shifted +3 ppm, AMPA's shifted -4 ppm; ACETAMINOPHEN
    and SULFAMETHOXAZOLE untouched. Verified (bench/tier_b.py --verify) to
    change error_ppm/candidate counts for the shifted rows while leaving the
    other two byte-identical to the unperturbed reference."""
    path = _path(tmp_dir, "measured_caffeine.tsv")
    shift = {"CAFFEINE": 3e-6, "AMPA": -4e-6}
    text = read_text(path, newline="")
    lines = [l for l in text.splitlines() if l.strip()]
    hdr = lines[0].split("\t")
    out = [lines[0]]
    for line in lines[1:]:
        vals = dict(zip(hdr, line.split("\t")))
        if vals["id"] in shift:
            vals["mass"] = "%.6f" % (float(vals["mass"]) * (1 + shift[vals["id"]]))
        out.append("\t".join(vals[h] for h in hdr))
    with open(path, "w", newline="") as fh:
        fh.write("\n".join(out) + "\n")


def _formula_perturb_isotope(tmp_dir):
    """SULFAMETHOXAZOLE's M1 halved and M2 scaled 2.5x -- a false isotope
    pattern that (verified) flips its rank-1 formula to a different, sulfur-
    poor composition. The other three rows are untouched."""
    path = _path(tmp_dir, "measured_caffeine.tsv")
    text = read_text(path, newline="")
    lines = [l for l in text.splitlines() if l.strip()]
    hdr = lines[0].split("\t")
    out = [lines[0]]
    for line in lines[1:]:
        vals = dict(zip(hdr, line.split("\t")))
        if vals["id"] == "SULFAMETHOXAZOLE":
            vals["M1"] = "%.6f" % (float(vals["M1"]) * 0.5)
            vals["M2"] = "%.6f" % (float(vals["M2"]) * 2.5)
        out.append("\t".join(vals[h] for h in hdr))
    with open(path, "w", newline="") as fh:
        fh.write("\n".join(out) + "\n")


def _formula_reference(tmp_dir):
    return formula_ref.run(_path(tmp_dir, "measured_caffeine.tsv"))


def _formula_effect(before, after):
    parts = []
    for cid in ("CAFFEINE", "ACETAMINOPHEN", "SULFAMETHOXAZOLE", "AMPA"):
        b, a = before[cid][0], after[cid][0]
        parts.append("%s: rank1 %s(%.3fppm)->%s(%.3fppm)"
                      % (cid, b["formula"], b["error_ppm"], a["formula"], a["error_ppm"]))
    parts.append("candidates %d->%d" % (before["candidates"], after["candidates"]))
    return "; ".join(parts)


def _formula_grade(tmp_dir, run, ref):
    out_path = _path(tmp_dir, "ranked.tsv")
    out = []
    if not os.path.isfile(out_path):
        out.append(("ranked.tsv present", False, "file missing"))
        return out
    size = os.path.getsize(out_path)
    n_lines, truncated = capped_line_count(out_path, cap=2_000_000)
    out.append(("ranked.tsv is bounded (<2,000,000 lines; %d bytes)" % size,
                 not truncated, "line count>=2,000,000 (capped)" if truncated
                 else "%d lines" % n_lines))
    ids = [cid for cid in ref if cid not in ("blocks", "candidates")]
    rank1 = {}
    for line in capped_read_lines(out_path, cap=200_000):
        line = line.rstrip("\n")
        if not line or line.startswith("id\t"):
            continue
        fields = line.split("\t")
        if len(fields) != 6:
            continue
        cid, rank = fields[0], fields[1]
        if rank == "1" and cid not in rank1:
            rank1[cid] = {"formula": fields[2], "calc_mass": fields[3],
                          "error_ppm": fields[4], "score": fields[5]}
    for cid in ids:
        want = ref[cid][0]
        got = rank1.get(cid)
        ok = (got is not None and got["formula"] == want["formula"]
              and close_abs(float(got["calc_mass"]), want["calc_mass"], 1e-4)
              and close_abs(float(got["error_ppm"]), want["error_ppm"], 0.05))
        out.append(("%s: rank-1 formula/calc_mass/error_ppm match reference" % cid,
                     ok, "got %r want %r" % (got, want)))
    stdout = run["stdout"] + "\n" + run["stderr"]
    blocks_field = num_field(stdout, "blocks")
    cand_field = num_field(stdout, "candidates")
    out.append(("stdout blocks=%d" % ref["blocks"],
                 blocks_field is not None and int(blocks_field) == ref["blocks"],
                 "got %r" % blocks_field))
    out.append(("stdout candidates matches reference (+/-20%, capped at 10x)",
                 cand_field is not None
                 and abs(cand_field - ref["candidates"]) <= max(2, 0.20 * ref["candidates"]),
                 "got %r want %d" % (cand_field, ref["candidates"])))
    return out


TOOLS_FORMULA = {
    "key": "formula_s", "mode": None,
    "artifacts": ["formula_finder.py"],
    "data_dir": "formula", "inputs": ["measured_caffeine.tsv"],
    "script": "formula_finder.py",
    "build_argv": lambda: ["measured_caffeine.tsv", "-o", "ranked.tsv"],
    "timeout": 120,
    "perturbations": [
        Perturbation("mass_shift_subset",
                     "CAFFEINE +3ppm, AMPA -4ppm, other two rows untouched",
                     _formula_perturb_mass_shift),
        Perturbation("isotope_perturb",
                     "SULFAMETHOXAZOLE M1/M2 replaced with a false pattern",
                     _formula_perturb_isotope),
    ],
    "reference": _formula_reference,
    "describe_effect": _formula_effect,
    "grade": _formula_grade,
    "skip_notes": [
        "candidates is graded loosely (+/-20%, floor 2) rather than exactly: "
        "tie-breaking at the ppm-window edge can legitimately differ by a "
        "candidate or two between an equally-correct implementation and the "
        "reference's own enumeration order.",
    ],
}


# ===========================================================================
# chrom_s
# ===========================================================================

def _chrom_perturb_remove_peak(tmp_dir):
    """Linearly interpolates the raw trace across a wide (+/-30 s) window
    centered on the fourth reference peak (rt_apex ~474 s), which sits in a
    cluster of overlapping/tailing peaks (README: this region never returns
    to the global baseline). A narrower window, or a flatten-to-global-
    baseline, was VERIFIED to leave a step discontinuity at the window edge
    that the smoothing/local-max rule reads back as two new peaks (measured:
    a +/-8 s flatten-to-baseline window turns the 10-peak reference into 11,
    with two apexes straddling the old one, not 9) -- exactly the kind of
    injection-site mistake this project already made once for the OTHER
    perturbation below and had to fix by measuring the surrounding trace by
    hand. A +/-30 s linear bridge between the trace values at the window
    edges removes the peak cleanly: verified 10 peaks -> 9, with the other
    nine apexes unchanged."""
    path = _path(tmp_dir, "chrom.csv")
    lines = [l for l in read_text(path, newline="").splitlines() if l.strip()]
    hdr, rows = lines[0], lines[1:]
    t = [float(r.split(",")[0]) for r in rows]
    y = [float(r.split(",")[1]) for r in rows]
    center, half = 474.12, 30.0
    idx = [i for i, ti in enumerate(t) if center - half <= ti <= center + half]
    i0, i1 = idx[0], idx[-1]
    y0, y1 = y[i0], y[i1]
    n = i1 - i0
    for k, i in enumerate(range(i0, i1 + 1)):
        y[i] = y0 + (y1 - y0) * (k / n if n else 0.0)
    out = [hdr] + ["%.4f,%.8f" % (ti, yi) for ti, yi in zip(t, y)]
    with open(path, "w", newline="") as fh:
        fh.write("\n".join(out) + "\n")


def _chrom_perturb_inject_peak(tmp_dir):
    """Adds a Gaussian bump centered at 740.0 s, in the quiet, near-flat
    stretch after the last reference peak (694 s) and before the run ends
    (~778 s) -- the same site this project's own tier(a) grader
    (grade_chrom_s.py) already measured clean after an earlier, too-close
    attempt (3.88 s from a real apex) silently merged into it instead of
    forming a separate peak. Amplitude 15 sigma above the local trace,
    verified to add exactly one new, cleanly separated apex near 739.7 s
    without moving any of the other ten."""
    path = _path(tmp_dir, "chrom.csv")
    lines = [l for l in read_text(path, newline="").splitlines() if l.strip()]
    hdr, rows = lines[0], lines[1:]
    sigma = float(chrom_ref.run(path)["sigma"])
    center, width, amp = 740.0, 2.5, 15.0 * sigma
    out = [hdr]
    for line in rows:
        t_s, y_s = line.split(",")
        t = float(t_s)
        bump = amp * math.exp(-((t - center) ** 2) / (2 * width ** 2))
        out.append("%s,%.8f" % (t_s, float(y_s) + bump))
    with open(path, "w", newline="") as fh:
        fh.write("\n".join(out) + "\n")


def _chrom_reference(tmp_dir):
    return chrom_ref.run(_path(tmp_dir, "chrom.csv"))


def _chrom_effect(before, after):
    b_apex = [round(p["rt_apex_s"], 1) for p in before["peaks"]]
    a_apex = [round(p["rt_apex_s"], 1) for p in after["peaks"]]
    return "npeaks %d -> %d; apexes %s -> %s" % (len(b_apex), len(a_apex), b_apex, a_apex)


def _chrom_grade(tmp_dir, run, ref):
    text = read_text(_path(tmp_dir, "peaks.tsv"), newline="") or ""
    lines = [l for l in text.splitlines() if l.strip()]
    out = []
    if not lines:
        out.append(("peaks.tsv present with rows", False, "empty/missing"))
        return out
    hdr = lines[0].split("\t")
    names = ["peak_id", "rt_apex_s", "height", "area"]
    rows = []
    for line in lines[1:]:
        named = named_fields(hdr, line.split("\t"), names)
        try:
            rows.append((float(named["rt_apex_s"]), float(named["height"])))
        except (KeyError, ValueError):
            pass
    want = sorted((p["rt_apex_s"], p["height"]) for p in ref["peaks"])
    out.append(("peak count matches reference (%d)" % len(want),
                 len(rows) == len(want),
                 "got %d want %d" % (len(rows), len(want))))
    matched = 0
    remaining = list(rows)
    for w_t, w_h in want:
        best = min(remaining, key=lambda r: abs(r[0] - w_t), default=None)
        if best is not None and abs(best[0] - w_t) <= 2.0 and rel_ok(best[1], w_h, 0.10):
            matched += 1
            remaining.remove(best)
    out.append(("every reference apex matched within 2 s / height within 10%",
                 matched == len(want), "matched %d/%d" % (matched, len(want))))
    stdout = run["stdout"] + "\n" + run["stderr"]
    b_field, s_field = num_field(stdout, "baseline"), num_field(stdout, "sigma")
    out.append(("stdout baseline/sigma match reference",
                 close_abs(b_field, ref["baseline"], 0.3)
                 and rel_ok(s_field, ref["sigma"], 0.25),
                 "got (%r,%r) want (%.3f,%.3f)"
                 % (b_field, s_field, ref["baseline"], ref["sigma"])))
    return out


TOOLS_CHROM = {
    "key": "chrom_s", "mode": None,
    "artifacts": ["chrom_integrate.py"],
    "data_dir": "chrom", "inputs": ["chrom.csv"],
    "script": "chrom_integrate.py",
    "build_argv": lambda: ["chrom.csv", "-o", "peaks.tsv"],
    "timeout": 60,
    "perturbations": [
        Perturbation("remove_peak", "linearly bridges across the ~474 s peak (+/-30 s)",
                     _chrom_perturb_remove_peak),
        Perturbation("inject_peak", "Gaussian bump injected at 450.0 s",
                     _chrom_perturb_inject_peak),
    ],
    "reference": _chrom_reference,
    "describe_effect": _chrom_effect,
    "grade": _chrom_grade,
    "skip_notes": [
        "peak area: data/chrom/README.md notes peaks 7-10 ride a wandering "
        "baseline, so area is convention-dependent and was never graded in "
        "tier (a) either.",
    ],
}


# ===========================================================================
# mass_stats_s
# ===========================================================================

def _mass_stats_perturb_flip_labels(tmp_dir):
    """Swaps the group label of one CTRL and one EXP replicate in groups.tsv
    (CTRL_3 <-> EXP_1) -- a relabeling, not a value change, so every t-test
    that involves either sample now compares different populations."""
    path = _path(tmp_dir, "groups.tsv")
    text = read_text(path, newline="")
    lines = text.splitlines()
    hdr = lines[0].split("\t")
    gi = hdr.index("group")
    ci = hdr.index("pinned_column")
    swap = {"CTRL_3": "EXP", "EXP_1": "CTRL"}
    out = [lines[0]]
    for line in lines[1:]:
        if not line.strip():
            continue
        fields = line.split("\t")
        if fields[ci] in swap:
            fields[gi] = swap[fields[ci]]
        out.append("\t".join(fields))
    with open(path, "w", newline="") as fh:
        fh.write("\n".join(out) + "\n")


def _mass_stats_perturb_dropout(tmp_dir):
    """Blanks EXP_2's reading for every 3rd feature row -- pushes some
    features below the >=3-valid-per-condition filter, changing `filtered`
    and `tested` (and every affected feature's own statistics)."""
    path = _path(tmp_dir, "quant_mtbls14397_pos.csv")
    text = read_text(path, newline="")
    lines = [l for l in text.splitlines() if l.strip()]
    hdr = lines[0].split(",")
    ei = hdr.index("EXP_2")
    out = [lines[0]]
    for i, line in enumerate(lines[1:]):
        fields = line.split(",")
        if i % 3 == 0:
            fields[ei] = ""
        out.append(",".join(fields))
    with open(path, "w", newline="") as fh:
        fh.write("\n".join(out) + "\n")


def _mass_stats_reference(tmp_dir):
    return mass_stats_ref.run(_path(tmp_dir, "quant_mtbls14397_pos.csv"),
                               _path(tmp_dir, "groups.tsv"))


def _mass_stats_effect(before, after):
    return ("tested %d -> %d, filtered %d -> %d, significant %d -> %d"
            % (before["tested"], after["tested"], before["filtered"],
               after["filtered"], before["significant"], after["significant"]))


def _mass_stats_grade(tmp_dir, run, ref):
    text = read_text(_path(tmp_dir, "stats.tsv"), newline="") or ""
    lines = [l for l in text.splitlines() if l.strip()]
    out = []
    names = ["feature_id", "log2fc", "t", "df", "p_value", "q_value", "significant"]
    rows_by_id = {}
    if lines:
        hdr = lines[0].split("\t")
        for line in lines[1:]:
            named = named_fields(hdr, line.split("\t"), names)
            if "feature_id" in named:
                rows_by_id[named["feature_id"]] = named
    out.append(("row count matches reference tested count (%d)" % ref["tested"],
                 len(rows_by_id) == ref["tested"],
                 "got %d rows" % len(rows_by_id)))
    if ref["rows"]:
        top = min(ref["rows"], key=lambda r: r["p_value"])
        got = rows_by_id.get(top["feature_id"])
        ok = False
        detail = "row for %s missing" % top["feature_id"]
        if got is not None:
            try:
                ok = (rel_ok(float(got["log2fc"]), top["log2fc"], 0.02)
                      and close_abs(float(got["q_value"]), top["q_value"], 0.02))
                detail = "got %r want log2fc=%.4f q=%.4f" % (
                    got, top["log2fc"], top["q_value"])
            except (KeyError, ValueError):
                pass
        out.append(("reference's top hit (%s) log2fc/q_value match"
                     % top["feature_id"], ok, detail))
    stdout = run["stdout"] + "\n" + run["stderr"]
    out.append(("stdout tested/filtered/significant match reference",
                 num_field(stdout, "tested") == ref["tested"]
                 and num_field(stdout, "filtered") == ref["filtered"]
                 and num_field(stdout, "significant") == ref["significant"],
                 "got %r" % {k: num_field(stdout, k) for k in
                             ("tested", "filtered", "significant")}))
    return out


TOOLS_MASS_STATS = {
    "key": "mass_stats_s", "mode": None,
    "artifacts": ["stats.py"],
    "data_dir": "mass_stats", "inputs": ["quant_mtbls14397_pos.csv", "groups.tsv"],
    "script": "stats.py",
    "build_argv": lambda: ["quant_mtbls14397_pos.csv", "groups.tsv", "-o", "stats.tsv"],
    "timeout": 60,
    "perturbations": [
        Perturbation("flip_labels", "CTRL_3 and EXP_1 group labels swapped",
                     _mass_stats_perturb_flip_labels),
        Perturbation("value_dropout", "EXP_2 blanked for every 3rd feature",
                     _mass_stats_perturb_dropout),
    ],
    "reference": _mass_stats_reference,
    "describe_effect": _mass_stats_effect,
    "grade": _mass_stats_grade,
    "skip_notes": [
        "tested=618 (tier(a)'s pinned count for the shipped file): replaced "
        "here by the count re-derived from the perturbed input.",
    ],
}


# ===========================================================================
# pca_s
# ===========================================================================

def _pca_perturb_group_shift(tmp_dir):
    """Multiplies every feature's raw value by 3x and adds a small offset,
    but ONLY for samples in the 'diabetes mellitus' group -- a batch-like
    effect confined to one group (not a global rescale: the Control Group
    samples in the same rows are untouched), so it changes the covariance
    structure -- and therefore PC1/PC2 variance fractions -- in a way no
    closed-form correction of the original scores reproduces. Verified
    (bench/tier_b.py --verify): pc1_var 0.1558 -> 0.628 on the real data."""
    feat_path = _path(tmp_dir, "features.csv")
    groups_path = _path(tmp_dir, "groups.csv")
    g_lines = [l for l in read_text(groups_path, newline="").splitlines() if l.strip()]
    g_hdr = g_lines[0].split(",")
    group_of = {}
    for line in g_lines[1:]:
        parts = line.split(",")
        group_of[parts[0]] = ",".join(parts[1:])
    target_group = "diabetes mellitus"

    f_lines = [l for l in read_text(feat_path, newline="").splitlines() if l.strip()]
    hdr = f_lines[0].split(",")
    samples = hdr[1:]
    mask = [group_of.get(s, "") == target_group for s in samples]
    out = [f_lines[0]]
    for line in f_lines[1:]:
        vals = line.split(",")
        for j, is_target in enumerate(mask, start=1):
            if is_target and vals[j].strip():
                vals[j] = "%.10g" % (float(vals[j]) * 3.0 + 0.02)
        out.append(",".join(vals))
    with open(feat_path, "w", newline="") as fh:
        fh.write("\n".join(out) + "\n")


def _pca_perturb_borderline_dropout(tmp_dir):
    """Finds the features already closest to the >=80%-valid cutoff and, for
    the 5 nearest the boundary from ABOVE it, blanks just enough additional
    samples to push them below 80% -- moving them out of features_kept.
    Computed from the data at run time rather than hardcoded row numbers."""
    feat_path = _path(tmp_dir, "features.csv")
    lines = [l for l in read_text(feat_path, newline="").splitlines() if l.strip()]
    hdr = lines[0].split(",")
    n_samples = len(hdr) - 1
    threshold = 0.80 * n_samples
    rows = [l.split(",") for l in lines[1:]]
    valid_counts = []
    for i, r in enumerate(rows):
        nv = sum(1 for v in r[1:] if v.strip() != "")
        if nv >= threshold:
            valid_counts.append((nv - threshold, i))
    valid_counts.sort()
    target_rows = [i for _, i in valid_counts[:5]]
    for i in target_rows:
        r = rows[i]
        need = int(sum(1 for v in r[1:] if v.strip() != "") - threshold) + 1
        blanked = 0
        for j in range(1, len(r)):
            if blanked >= need:
                break
            if r[j].strip() != "":
                r[j] = ""
                blanked += 1
    out = [",".join(hdr)] + [",".join(r) for r in rows]
    with open(feat_path, "w", newline="") as fh:
        fh.write("\n".join(out) + "\n")


def _pca_reference(tmp_dir):
    return pca_ref.run(_path(tmp_dir, "features.csv"), _path(tmp_dir, "groups.csv"))


def _pca_effect(before, after):
    return ("features_kept %d -> %d, pc1_var %.4f -> %.4f, pc2_var %.4f -> %.4f"
            % (before["features_kept"], after["features_kept"],
               before["pc1_var"], after["pc1_var"],
               before["pc2_var"], after["pc2_var"]))


def _pca_grade(tmp_dir, run, ref):
    stdout = run["stdout"] + "\n" + run["stderr"]
    fin, fk = num_field(stdout, "features_in"), num_field(stdout, "features_kept")
    pc1, pc2 = num_field(stdout, "pc1_var"), num_field(stdout, "pc2_var")
    out = [
        ("stdout features_in matches reference (%d)" % ref["features_in"],
         fin is not None and int(fin) == ref["features_in"], "got %r" % fin),
        ("stdout features_kept matches reference (%d)" % ref["features_kept"],
         fk is not None and int(fk) == ref["features_kept"], "got %r" % fk),
        ("pc1_var matches reference (+/-0.02)",
         close_abs(pc1, ref["pc1_var"], 0.02), "got %r want %.4f" % (pc1, ref["pc1_var"])),
        ("pc2_var matches reference (+/-0.02)",
         close_abs(pc2, ref["pc2_var"], 0.02), "got %r want %.4f" % (pc2, ref["pc2_var"])),
    ]
    scores_path = _path(tmp_dir, "scores.tsv")
    text = read_text(scores_path, newline="") or ""
    lines = [l for l in text.splitlines() if l]
    corr_ok = False
    if len(lines) > 1:
        try:
            import numpy as np
            hdr = lines[0].split("\t")
            i_pc1, i_pc2, i_s = hdr.index("PC1"), hdr.index("PC2"), hdr.index("sample")
            rows = [l.split("\t") for l in lines[1:]]
            by_sample = {r[i_s]: (float(r[i_pc1]), float(r[i_pc2])) for r in rows}
            order = [s for s in ref["samples"] if s in by_sample]
            if len(order) >= 0.9 * len(ref["samples"]):
                got = np.array([by_sample[s] for s in order])
                want = ref["scores"][[ref["samples"].index(s) for s in order]]
                corr_ok = all(abs(np.corrcoef(got[:, j], want[:, j])[0, 1]) >= 0.99
                              for j in (0, 1))
        except (ValueError, KeyError, IndexError):
            corr_ok = False
    out.append(("PC1/PC2 scores correlate with reference at |r|>=0.99", corr_ok,
                 "scores.tsv unreadable or under-covered" if not corr_ok else "ok"))
    return out


TOOLS_PCA = {
    "key": "pca_s", "mode": None,
    "artifacts": ["pca.py"],
    "data_dir": "pca", "inputs": ["features.csv", "groups.csv"],
    "script": "pca.py",
    "build_argv": lambda: ["features.csv", "groups.csv", "-o", "scores.tsv"],
    "timeout": 60,
    "perturbations": [
        Perturbation("group_batch_shift",
                     "batch-like offset added to feature 1, diabetes group only",
                     _pca_perturb_group_shift),
        Perturbation("borderline_dropout",
                     "5 near-80%-valid features pushed just below the keep threshold",
                     _pca_perturb_borderline_dropout),
    ],
    "reference": _pca_reference,
    "describe_effect": _pca_effect,
    "grade": _pca_grade,
    "skip_notes": [
        "published features_kept=184 / pc1_var=0.1558 / pc2_var=0.1008: "
        "tied to the shipped file, replaced by the reference recomputed "
        "from the perturbed input.",
    ],
}


# ===========================================================================
# nmr_s
# ===========================================================================

def _nmr_inject(tmp_dir, target_ppm, scale, decay):
    """Adds a synthetic decaying-sinusoid resonance to the raw complex FID at
    `target_ppm`, computed from nmr_ref's own SF/CARRIER_PPM constants so the
    injection uses exactly the same frequency axis the reference and any
    correct submission both use."""
    import numpy as np
    path = _path(tmp_dir, "fid_complex.csv")
    t, re_, im_ = [], [], []
    header = []
    for line in read_text(path).splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("time_s"):
            header.append(line)
            continue
        a, b, c = s.split(",")
        t.append(float(a)); re_.append(float(b)); im_.append(float(c))
    t = np.array(t)
    z = np.array(re_) + 1j * np.array(im_)
    f0 = (target_ppm - nmr_ref.CARRIER_PPM) * nmr_ref.SF
    z2 = z + scale * np.exp(-math.pi * decay * t) * np.exp(2j * math.pi * f0 * t)
    out = list(header)
    for a, zi in zip(t, z2):
        out.append("%.8f,%.6f,%.6f" % (a, zi.real, zi.imag))
    with open(path, "w", newline="") as fh:
        fh.write("\n".join(out) + "\n")


def _nmr_perturb_inject_1ppm(tmp_dir):
    """A new resonance injected at 1.000 ppm (clear of every real peak: the
    nearest is 1.921 ppm, ~0.9 ppm away). Verified: 15 peaks -> 16, with the
    other 14 shifting by <1% (FFT leakage), not merging with anything."""
    _nmr_inject(tmp_dir, 1.000, 1.0e5, 3.0)


def _nmr_perturb_inject_7ppm(tmp_dir):
    """A second, independent resonance injected at 7.000 ppm (past every
    real peak; the highest is 4.767 ppm). Different amplitude/decay from the
    1 ppm injection above so the two perturbations are not the same edit at
    two sites. Verified: 15 peaks -> 16, others <1% affected."""
    _nmr_inject(tmp_dir, 7.000, 1.5e5, 4.0)


def _nmr_reference(tmp_dir):
    return nmr_ref.run(_path(tmp_dir, "fid_complex.csv"))


def _nmr_effect(before, after):
    b = sorted(round(p["ppm_center"], 3) for p in before["peaks"])
    a = sorted(round(p["ppm_center"], 3) for p in after["peaks"])
    return "npeaks %d -> %d; new ppm(s): %s" % (len(b), len(a), sorted(set(a) - set(b)))


def _nmr_grade(tmp_dir, run, ref):
    text = read_text(_path(tmp_dir, "multiplets.tsv"), newline="") or ""
    lines = [l for l in text.splitlines() if l.strip()]
    out = []
    names = ["ppm_center", "integral_rel"]
    rows = []
    if lines:
        hdr = lines[0].split("\t")
        for line in lines[1:]:
            named = named_fields(hdr, line.split("\t"), names)
            try:
                rows.append((float(named["ppm_center"]), float(named["integral_rel"])))
            except (KeyError, ValueError):
                pass
    out.append(("peak count matches reference (%d)" % len(ref["peaks"]),
                 len(rows) == len(ref["peaks"]),
                 "got %d want %d" % (len(rows), len(ref["peaks"]))))
    # integral_rel tolerance combines a 15% relative band with a 0.02 absolute
    # floor: a couple of the reference's own peaks sit within noise of zero
    # (e.g. the 3.02/3.024 ppm pair the design doc's P3-1 assessment already
    # flagged as baseline-sensitive -- integral_rel -0.0085), where a purely
    # relative tolerance would fail any tool that (reasonably) clamps a
    # numerically-unstable near-zero integral to 0.0 rather than reproducing
    # its sign.
    matched = 0
    remaining = list(rows)
    for p in ref["peaks"]:
        best = min(remaining, key=lambda r: abs(r[0] - p["ppm_center"]), default=None)
        tol = max(0.15 * abs(p["integral_rel"]), 0.02)
        if (best is not None and abs(best[0] - p["ppm_center"]) <= 0.02
                and abs(best[1] - p["integral_rel"]) <= tol):
            matched += 1
            remaining.remove(best)
    out.append(("every reference peak matched within 0.02 ppm / integral within "
                 "15% (floor 0.02)", matched == len(ref["peaks"]),
                 "matched %d/%d" % (matched, len(ref["peaks"]))))
    stdout = run["stdout"] + "\n" + run["stderr"]
    peaks_field = num_field(stdout, "peaks")
    out.append(("stdout peaks count matches reference",
                 peaks_field is not None and int(peaks_field) == len(ref["peaks"]),
                 "got %r" % peaks_field))
    return out


TOOLS_NMR = {
    "key": "nmr_s", "mode": None,
    "artifacts": ["nmr.py"],
    "data_dir": "nmr", "inputs": ["fid_complex.csv"],
    "script": "nmr.py",
    "build_argv": lambda: ["fid_complex.csv", "-o", "multiplets.tsv"],
    "timeout": 120,
    "perturbations": [
        Perturbation("inject_1ppm", "synthetic resonance injected at 1.000 ppm",
                     _nmr_perturb_inject_1ppm),
        Perturbation("inject_7ppm", "synthetic resonance injected at 7.000 ppm",
                     _nmr_perturb_inject_7ppm),
    ],
    "reference": _nmr_reference,
    "describe_effect": _nmr_effect,
    "grade": _nmr_grade,
    "skip_notes": [
        "the published MTBLS1 multiplet assignments (tier(a)'s citrate/"
        "TSP table): tied to the shipped FID, replaced here by the "
        "reference recomputed from the perturbed FID.",
    ],
}


# ===========================================================================
# mass_reader_s
# ===========================================================================

_FASTA_PROBE = (
    "import sys, json\n"
    "sys.path.insert(0, '.')\n"
    "import fasta_reader\n"
    "recs = fasta_reader.read_fasta(sys.argv[1])\n"
    "print(json.dumps({'n': len(recs), "
    "'total_residues': sum(len(s) for _, s in recs), "
    "'first_id': recs[0][0] if recs else None, "
    "'first_len': len(recs[0][1]) if recs else None}))\n"
)


def _mass_reader_perturb_decimate_mzml(tmp_dir):
    """Drops every 3rd spectrum (MS1 and MS2 both eligible) from the bsa
    mzML; ecoli_k12_48.fasta is untouched by this perturbation."""
    path = _path(tmp_dir, "bsa_orbitrap_first40.mzML")
    keep_spectra(path, path + ".tmp", lambda i, b: i % 3 != 0)
    os.replace(path + ".tmp", path)


def _mass_reader_perturb_truncate_fasta(tmp_dir):
    """Drops the last 5 records from ecoli_k12_48.fasta (changes both record
    count and total residues); the bsa mzML is untouched by this
    perturbation."""
    path = _path(tmp_dir, "ecoli_k12_48.fasta")
    recs = trusted_fasta.read_fasta(path)
    kept = recs[:-5]
    out = []
    for rid, seq in kept:
        out.append(">" + rid)
        for j in range(0, len(seq), 70):
            out.append(seq[j:j + 70])
    with open(path, "w", newline="") as fh:
        fh.write("\n".join(out) + "\n")


def _mass_reader_reference(tmp_dir):
    mzml = trusted_mzml.read_mzml(_path(tmp_dir, "bsa_orbitrap_first40.mzML"))
    rts = [s["rt"] for s in mzml if s["rt"] is not None]
    fasta = trusted_fasta.read_fasta(_path(tmp_dir, "ecoli_k12_48.fasta"))
    return {
        "mzml": {
            "n": len(mzml),
            "n_ms1": sum(1 for s in mzml if s["ms_level"] == 1),
            "n_ms2": sum(1 for s in mzml if s["ms_level"] == 2),
            "rt_first": rts[0] if rts else None,
            "rt_last": rts[-1] if rts else None,
            "tic": sum(float(v) for s in mzml for v in s["intensity"]),
        },
        "fasta": {
            "n": len(fasta),
            "total_residues": sum(len(s) for _, s in fasta),
            "first_id": fasta[0][0] if fasta else None,
            "first_len": len(fasta[0][1]) if fasta else None,
        },
    }


def _mass_reader_effect(before, after):
    return ("mzml spectra %d -> %d (ms1 %d -> %d, ms2 %d -> %d); "
            "fasta records %d -> %d, residues %d -> %d"
            % (before["mzml"]["n"], after["mzml"]["n"],
               before["mzml"]["n_ms1"], after["mzml"]["n_ms1"],
               before["mzml"]["n_ms2"], after["mzml"]["n_ms2"],
               before["fasta"]["n"], after["fasta"]["n"],
               before["fasta"]["total_residues"], after["fasta"]["total_residues"]))


def _mass_reader_grade(tmp_dir, run, ref):
    import json as _json
    stdout = run["stdout"] + "\n" + run["stderr"]
    m = ref["mzml"]
    out = [
        ("mzml_reader.py stdout: spectra/ms1/ms2 match reference",
         num_field(stdout, "spectra") == m["n"]
         and num_field(stdout, "ms1") == m["n_ms1"]
         and num_field(stdout, "ms2") == m["n_ms2"],
         "got %r want spectra=%d ms1=%d ms2=%d"
         % (stdout.strip()[:200], m["n"], m["n_ms1"], m["n_ms2"])),
        ("mzml_reader.py stdout: rt_first/rt_last match reference (+/-1e-3 s)",
         close_abs(num_field(stdout, "rt_first"), m["rt_first"], 1e-3)
         and close_abs(num_field(stdout, "rt_last"), m["rt_last"], 1e-3),
         "want rt_first=%r rt_last=%r" % (m["rt_first"], m["rt_last"])),
        ("mzml_reader.py stdout: tic matches reference (+/-0.1%)",
         rel_ok(num_field(stdout, "tic"), m["tic"], 1e-3),
         "want tic=%r" % m["tic"]),
    ]
    # fasta_reader.py is not exercised by run_cmd (only mzml_reader.py is), so
    # it is probed here with its own subprocess + timeout, exactly mirroring
    # grade_mass_reader_s.py's direct-import approach but via a fresh
    # interpreter so a crash in it cannot take down this grader.
    probe_path = _path(tmp_dir, "_fasta_probe.py")
    with open(probe_path, "w") as fh:
        fh.write(_FASTA_PROBE)
    fr = run_program([sys.executable, "_fasta_probe.py", "ecoli_k12_48.fasta"],
                      tmp_dir, 30)
    got = None
    if fr["ok"]:
        try:
            got = _json.loads(fr["stdout"].strip().splitlines()[-1])
        except (ValueError, IndexError):
            got = None
    f = ref["fasta"]
    out.append(("fasta_reader.py: record count and total residues match reference",
                 got is not None and got.get("n") == f["n"]
                 and got.get("total_residues") == f["total_residues"],
                 "got %r want n=%d total_residues=%d" % (got, f["n"], f["total_residues"])))
    out.append(("fasta_reader.py: first record id/length match reference",
                 got is not None and got.get("first_id") == f["first_id"]
                 and got.get("first_len") == f["first_len"],
                 "got %r want %r/%r" % (got, f["first_id"], f["first_len"])))
    return out


def _mass_reader_run(tmp_dir, tool, timeout):
    """Only mzml_reader.py is exercised by the mandated run_cmd; grade()
    separately probes fasta_reader.py (see _mass_reader_grade)."""
    return run_program([sys.executable, tool["script"]] + tool["build_argv"](),
                        tmp_dir, timeout)


TOOLS_MASS_READER = {
    "key": "mass_reader_s", "mode": None,
    "artifacts": ["fasta_reader.py", "mzml_reader.py"],
    "data_dir": "mass_reader",
    "inputs": ["ecoli_k12_48.fasta", "bsa_orbitrap_first40.mzML"],
    "script": "mzml_reader.py",
    "build_argv": lambda: ["bsa_orbitrap_first40.mzML"],
    "timeout": 60,
    "custom_run": _mass_reader_run,
    "perturbations": [
        Perturbation("decimate_mzml", "every 3rd bsa spectrum dropped",
                     _mass_reader_perturb_decimate_mzml),
        Perturbation("truncate_fasta", "last 5 ecoli FASTA records dropped",
                     _mass_reader_perturb_truncate_fasta),
    ],
    "reference": _mass_reader_reference,
    "describe_effect": _mass_reader_effect,
    "grade": _mass_reader_grade,
    "skip_notes": [
        "thermo_small_raw.mzML (only 2 MS1 spectra, too small to perturb "
        "meaningfully) is copied into the workspace but not perturbed or "
        "re-graded here.",
        "pyteomics-derived literal constants for the unperturbed files "
        "(e.g. bsa tic=45709750.4): replaced by the trusted std-lib reader "
        "(bench/reference/lib) recomputed from the perturbed input.",
    ],
}


# ===========================================================================
# features_s
# ===========================================================================

_MS1_RE = re.compile(r'MS:1000511"[^>]*value="1"')


def _features_perturb_decimate_interleaved(tmp_dir):
    """Drops every 3rd MS1 scan (MS2 untouched, though this file has none)."""
    path = _path(tmp_dir, "BSA1_F1.mzML")
    seen = [0]

    def pred(i, block):
        if not _MS1_RE.search(block):
            return True
        seen[0] += 1
        return seen[0] % 3 != 0
    keep_spectra(path, path + ".tmp", pred)
    os.replace(path + ".tmp", path)


def _features_perturb_drop_tail(tmp_dir):
    """Drops the last 30% of MS1 scans by acquisition order (a shortened
    run), keeping the first 70% -- a different failure mode (late-eluting
    features disappear entirely) from the interleaved dropout above."""
    path = _path(tmp_dir, "BSA1_F1.mzML")
    # Count MS1 scans directly (cheap: one extra parse of the trusted reader).
    n_ms1 = sum(1 for s in trusted_mzml.read_mzml(path) if s["ms_level"] == 1)
    cutoff = int(n_ms1 * 0.70)
    seen = [0]

    def pred(i, block):
        if not _MS1_RE.search(block):
            return True
        seen[0] += 1
        return seen[0] <= cutoff
    keep_spectra(path, path + ".tmp", pred)
    os.replace(path + ".tmp", path)


def _features_reference(tmp_dir):
    return features_ref.detect(_path(tmp_dir, "BSA1_F1.mzML"))


def _features_effect(before, after):
    return ("ms1_scans %d -> %d, windows %d -> %d, features %d -> %d"
            % (before["ms1_scans"], after["ms1_scans"], before["windows"],
               after["windows"], len(before["features"]), len(after["features"])))


def _features_grade(tmp_dir, run, ref):
    text = read_text(_path(tmp_dir, "features.tsv"), newline="") or ""
    lines = [l for l in text.splitlines() if l.strip()]
    out = []
    names = ["mz", "rt_apex", "rt_start", "rt_end", "apex_intensity", "n_scans"]
    rows = []
    if lines:
        hdr = lines[0].split("\t")
        for line in lines[1:]:
            named = named_fields(hdr, line.split("\t"), names)
            try:
                rows.append((float(named["mz"]), float(named["rt_apex"]),
                             float(named["apex_intensity"])))
            except (KeyError, ValueError):
                pass
    ref_top = sorted(ref["features"], key=lambda f: -f["apex_intensity"])[:100]
    matched = 0
    remaining = list(rows)
    for f in ref_top:
        cand = [r for r in remaining
                if abs(r[0] - f["mz"]) <= 0.01 and abs(r[1] - f["rt_apex"]) <= 10.0]
        if cand:
            matched += 1
            remaining.remove(cand[0])
    min_matched = max(1, int(0.70 * len(ref_top)))
    out.append(("top-100-by-intensity reference features matched (mz+/-0.01, "
                 "rt+/-10s): >= %d/%d" % (min_matched, len(ref_top)),
                 matched >= min_matched,
                 "matched %d/%d (of %d rows written)" % (matched, len(ref_top), len(rows))))
    stdout = run["stdout"] + "\n" + run["stderr"]
    ms1_field = num_field(stdout, "ms1_scans")
    out.append(("stdout ms1_scans matches reference (%d)" % ref["ms1_scans"],
                 ms1_field is not None and int(ms1_field) == ref["ms1_scans"],
                 "got %r" % ms1_field))
    return out


TOOLS_FEATURES = {
    "key": "features_s", "mode": "solo",
    "artifacts": ["features.py", "mzml_reader.py"],
    "data_dir": "feature_extraction", "inputs": ["BSA1_F1.mzML"],
    "script": "features.py",
    "build_argv": lambda: ["BSA1_F1.mzML", "-o", "features.tsv"],
    "timeout": 180,
    "perturbations": [
        Perturbation("decimate_ms1_interleaved", "every 3rd MS1 scan dropped",
                     _features_perturb_decimate_interleaved),
        Perturbation("drop_tail_ms1", "last 30% of MS1 scans dropped",
                     _features_perturb_drop_tail),
    ],
    "reference": _features_reference,
    "describe_effect": _features_effect,
    "grade": _features_grade,
    "skip_notes": [
        "data/feature_extraction/README.md's literal top-10 (mz, RT) table "
        "for the shipped file: replaced by the top-100-by-intensity match "
        "against the reference recomputed from the perturbed mzML.",
    ],
}


# ===========================================================================
# dda_s
# ===========================================================================

_IONS_RE = re.compile(r"BEGIN IONS.*?END IONS\n?", re.DOTALL)
_AA20 = "ACDEFGHIKLMNPQRSTVWY"


def _dda_perturb_truncate_mgf(tmp_dir):
    """Keeps only the first 400 of 1200 spectra (a shorter acquisition)."""
    path = _path(tmp_dir, "ups1_yeast_dda_first1200.mgf")
    text = read_text(path)
    blocks = _IONS_RE.findall(text)
    with open(path, "w", newline="") as fh:
        fh.write("".join(blocks[:400]))


def _dda_perturb_mutate_fasta(tmp_dir):
    """Point-mutates residue 10 of every 5th protein (target and, once
    reversed, decoy) to a different standard amino acid -- changes the
    tryptic peptide(s) spanning that position without touching sequence
    length or any other protein."""
    path = _path(tmp_dir, "yeast_pe1_plus_ups.fasta")
    records = trusted_fasta.read_fasta(path)
    out = []
    for i, (rid, seq) in enumerate(records):
        if i % 5 == 0 and len(seq) > 10 and seq[10] in _AA20:
            j = (_AA20.index(seq[10]) + 3) % len(_AA20)
            seq = seq[:10] + _AA20[j] + seq[11:]
        out.append(">" + rid)
        for k in range(0, len(seq), 70):
            out.append(seq[k:k + 70])
    with open(path, "w", newline="") as fh:
        fh.write("\n".join(out) + "\n")


def _dda_reference(tmp_dir):
    return dda_ref.run(_path(tmp_dir, "yeast_pe1_plus_ups.fasta"),
                        _path(tmp_dir, "ups1_yeast_dda_first1200.mgf"))


def _dda_effect(before, after):
    keys = ("targets", "decoys", "spectra", "with_candidate", "best_hits",
            "decoy_hits", "psms_1pct", "proteins_ge2")
    return "; ".join("%s %r->%r" % (k, before[k], after[k]) for k in keys)


def _dda_grade(tmp_dir, run, ref):
    stdout = run["stdout"] + "\n" + run["stderr"]
    out = []
    for key in ("targets", "decoys", "spectra", "with_candidate", "best_hits",
                "decoy_hits", "psms_1pct"):
        got = num_field(stdout, key)
        out.append(("stdout %s matches reference (%r)" % (key, ref[key]),
                     got is not None and int(got) == ref[key],
                     "got %r" % got))
    psms_path = _path(tmp_dir, "psms.tsv")
    proteins_ge2 = None
    if os.path.isfile(psms_path):
        n_lines, truncated = capped_line_count(psms_path, cap=500_000)
        names = ["scan", "peptide", "protein", "decoy", "score", "qvalue"]
        by_protein = {}
        lines = capped_read_lines(psms_path, cap=200_000)
        if lines:
            hdr = lines[0].rstrip("\n").split("\t")
            for line in lines[1:]:
                named = named_fields(hdr, line.rstrip("\n").split("\t"), names)
                if named.get("decoy") in ("0", "0.0"):
                    p = named.get("protein")
                    by_protein[p] = by_protein.get(p, 0) + 1
            proteins_ge2 = sum(1 for v in by_protein.values() if v >= 2)
    out.append(("psms.tsv-derived proteins_ge2 matches reference (%r)" % ref["proteins_ge2"],
                 proteins_ge2 == ref["proteins_ge2"],
                 "got %r" % proteins_ge2))
    return out


TOOLS_DDA = {
    "key": "dda_s", "mode": "solo",
    "artifacts": ["search.py", "fasta_reader.py"],
    "data_dir": "database_search",
    "inputs": ["yeast_pe1_plus_ups.fasta", "ups1_yeast_dda_first1200.mgf"],
    "script": "search.py",
    "build_argv": lambda: ["yeast_pe1_plus_ups.fasta", "ups1_yeast_dda_first1200.mgf",
                           "-o", "psms.tsv"],
    "timeout": 120,
    "perturbations": [
        Perturbation("truncate_mgf", "first 400 of 1200 spectra kept",
                     _dda_perturb_truncate_mgf),
        Perturbation("mutate_fasta", "residue 10 of every 5th protein point-mutated",
                     _dda_perturb_mutate_fasta),
    ],
    "reference": _dda_reference,
    "describe_effect": _dda_effect,
    "grade": _dda_grade,
    "skip_notes": [
        "psms_1pct_unfiltered and decoy_fraction: not graded here (would "
        "require a second, unfiltered search re-run per rep); the filtered "
        "counts above already exercise the same code path.",
        "'>= 5 of 7 named UPS1 proteins' (tier(a) criterion 6): the named "
        "proteins are specific to the unperturbed file; replaced here by "
        "proteins_ge2 recomputed from the perturbed input.",
    ],
}


TOOLS = {
    t["key"]: t for t in [
        TOOLS_CALIBRATION, TOOLS_TITRATION, TOOLS_UVVIS, TOOLS_SPECTRAL,
        TOOLS_FORMULA, TOOLS_CHROM, TOOLS_MASS_STATS, TOOLS_PCA, TOOLS_NMR,
        TOOLS_MASS_READER, TOOLS_FEATURES, TOOLS_DDA,
    ]
}
