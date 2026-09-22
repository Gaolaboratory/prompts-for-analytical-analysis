"""Oracle-conformant fixture builders, one per tool (added in grader tasks)."""

BUILDERS = {}   # tool name -> build_artifacts(d)
STUBS = {}      # tool name -> write_stub(ws)

def build_artifacts(tool, d):
    BUILDERS[tool](d)

def write_stub(tool, ws):
    STUBS[tool](ws)

def _titration_csv():
    rows = ["# synthetic titration, seed 20260824", "titrant_volume_mL,pH", "0.00,2.892"]
    for i in range(1, 49):
        rows.append("%.2f,%.3f" % (i * 75.0 / 49, 3.0 + 9.0 * i / 49.0))
    rows.append("75.00,12.283")
    return "\n".join(rows) + "\n"

TITRATION_RESULTS = ("equivalence_volume_mL\tequivalence_volume_d2_mL\tpKa\tanalyte_concentration_M\n"
                     "50.245\t50.245\t4.761\t0.1005\n")

def _build_titration(d):
    import os
    open(os.path.join(d, "titration.csv"), "w").write(_titration_csv())
    open(os.path.join(d, "results.tsv"), "w").write(TITRATION_RESULTS)
    open(os.path.join(d, "session.jsonl"), "w").write("{}\n")

def _stub_titration(ws):
    import os
    open(os.path.join(ws, "make_test_data.py"), "w").write(
        "open('titration.csv','w').write(%r)\nprint('wrote titration.csv')\n" % _titration_csv())
    open(os.path.join(ws, "titration.py"), "w").write(
        "import sys\nopen('results.tsv','w').write(%r)\nprint('wrote results.tsv')\n" % TITRATION_RESULTS)

BUILDERS["titration"] = _build_titration
STUBS["titration"] = _stub_titration

def _session_jsonl(prompt_echo, evidence):
    """A minimal pi session transcript in the real schema: session header,
    one user message (the prompt echo — sessions open with the prompt, which
    is what made whole-file grader scans pass vacuously), then agent-side
    evidence records (toolResult/assistant text)."""
    import json
    def msg(role, text):
        return json.dumps({"type": "message", "message": {"role": role,
            "content": [{"type": "text", "text": text}]}})
    lines = [json.dumps({"type": "session", "version": 3, "id": "fixture-session"})]
    lines.append(msg("user", prompt_echo))
    lines.extend(msg("toolResult", t) for t in evidence)
    return "\n".join(lines) + "\n"

CAL_STDOUT = ("slope\t2.5025\nintercept\t0.0276\nr2\t0.9998\nsigma\t0.0046\nLOD\t0.0060\nLOQ\t0.0183\n")
CAL_RESULTS = ("sample_id\tratio\tcalc_conc_ug_mL\ttrue_conc_ug_mL\tbias_pct\n"
               "UNK_1\t0.4042\t0.1506\t0.15\t+0.43\n"
               "UNK_2\t3.0306\t1.1960\t1.20\t-0.33\n"
               "UNK_3\t9.5671\t3.8186\t3.80\t+0.49\n")

def _calibrate_py():
    return (
        "def wls(xs, ys):\n"
        "    ws = [1.0 / (x * x) for x in xs]\n"
        "    sw = sum(ws)\n"
        "    xw = sum(w * x for w, x in zip(ws, xs)) / sw\n"
        "    yw = sum(w * y for w, y in zip(ws, ys)) / sw\n"
        "    num = sum(w * (x - xw) * (y - yw) for w, x, y in zip(ws, xs, ys))\n"
        "    den = sum(w * (x - xw) ** 2 for w, x in zip(ws, xs))\n"
        "    slope = num / den\n"
        "    return slope, yw - slope * xw\n"
        "import sys\n"
        "print(%r, end='')\n" % CAL_STDOUT +
        "open('results.tsv', 'w').write(%r)\n" % CAL_RESULTS
    )

# Prompt-echo excerpt (what the session's opening user message carries) and the
# agent-side evidence line (toolResult). Phrasings differ on purpose so grader
# mutations can corrupt one without touching the other.
CAL_SESSION_ECHO = ("# Weighted calibration with internal standards (prompt excerpt)\n\n"
    "| call | slope | intercept |\n|---|---|---|\n"
    "| `wls([1, 2, 4], [2.1, 4.0, 8.3])` | 2.0250 | 0.0571 |\n\n"
    "6. The self-check above reproduces slope 2.0250 / intercept 0.0571.")
CAL_SESSION_EVIDENCE = ("hand-check wls([1,2,4],[2.1,4.0,8.3]) -> "
    "slope 2.0250 intercept 0.0571 ok")
CAL_SESSION = _session_jsonl(CAL_SESSION_ECHO, [CAL_SESSION_EVIDENCE])

def _build_calibration(d):
    import os
    open(os.path.join(d, "stdout.txt"), "w").write(CAL_STDOUT)
    open(os.path.join(d, "results.tsv"), "w").write(CAL_RESULTS)
    open(os.path.join(d, "calibrate.py"), "w").write(_calibrate_py())
    open(os.path.join(d, "session.jsonl"), "w").write(CAL_SESSION)

def _stub_calibration(ws):
    import os
    open(os.path.join(ws, "make_cal_data.py"), "w").write("print('wrote standards.csv, unknowns.csv')\n")
    open(os.path.join(ws, "calibrate.py"), "w").write(_calibrate_py())

BUILDERS["calibration"] = _build_calibration
STUBS["calibration"] = _stub_calibration

UVVIS_PEAKS = ("band\tlambda_max_nm\ta_max\n"
               "b1\t320\t0.8803\nb2\t420\t1.2677\nb3\t540\t0.6691\n")
UVVIS_STDOUT = "bands: 3\nconcentration_uM: 50.0\n"

def _build_uvvis(d):
    import os
    open(os.path.join(d, "peaks.tsv"), "w").write(UVVIS_PEAKS)
    open(os.path.join(d, "stdout.txt"), "w").write(UVVIS_STDOUT)
    open(os.path.join(d, "stderr.txt"), "w").write("")

def _stub_uvvis(ws):
    import os
    open(os.path.join(ws, "make_uvvis_data.py"), "w").write("print('wrote sample.csv')\n")
    open(os.path.join(ws, "uvvis.py"), "w").write(
        "print(%r, end='')\nopen('peaks.tsv','w').write(%r)\n" % (UVVIS_STDOUT, UVVIS_PEAKS))

BUILDERS["uvvis"] = _build_uvvis
STUBS["uvvis"] = _stub_uvvis

PCA_STDOUT = ("kept 27 of 28 features (filtered: MET_X28)\n"
              "PC1 variance fraction 0.9218\nPC2 variance fraction 0.0719\n")

def _pca_scores():
    rows = ["sample\tPC1\tPC2"]
    for i in range(1, 6):
        rows.append("CTRL_%d\t%.4f\t-1.7934" % (i, 3.4354 - 0.1 * (i - 1)))
    for i in range(1, 6):
        rows.append("EXP_%d\t%.4f\t%.4f" % (i, -3.6524 + 0.1 * (i - 1), 1.2 - 0.3 * i))
    return "\n".join(rows) + "\n"

def _pca_loadings():
    rows = ["feature\tPC1\tPC2"]
    for i in range(1, 13):
        rows.append("MET_S%02d\t-0.2800\t0.0100" % i)
    for i in range(13, 19):
        rows.append("MET_B%02d\t0.0500\t0.4000" % i)
    for i in range(19, 27):
        rows.append("MET_N%02d\t0.0100\t0.0100" % i)
    rows.append("MET_M27\t0.0100\t0.0100")
    return "\n".join(rows) + "\n"

def _build_pca(d):
    import os
    open(os.path.join(d, "stdout.txt"), "w").write(PCA_STDOUT)
    open(os.path.join(d, "scores.tsv"), "w").write(_pca_scores())
    open(os.path.join(d, "loadings.tsv"), "w").write(_pca_loadings())

def _stub_pca(ws):
    import os
    open(os.path.join(ws, "make_test_data.py"), "w").write("print('wrote features.csv')\n")
    open(os.path.join(ws, "pca.py"), "w").write(
        "print(%r, end='')\nopen('scores.tsv','w').write(%r)\nopen('loadings.tsv','w').write(%r)\n"
        % (PCA_STDOUT, _pca_scores(), _pca_loadings()))

BUILDERS["pca"] = _build_pca
STUBS["pca"] = _stub_pca

NMR_TSV = ("ppm_center\tintegral\trelative_integral\n"
           "0.4998\t24654.39\t1.0000\n"
           "2.0994\t2768.91\t0.1123\n"
           "3.7998\t5451.26\t0.2211\n"
           "7.2502\t8166.71\t0.3312\n")
NMR_STDOUT = "points read: 10000\nzero-filled to: 16384\npeaks found: 4\n"

def _nmr_py():
    return (
        "import math\n"
        "def fft(x):\n"
        "    n = len(x)\n"
        "    if n == 1:\n"
        "        return list(x)\n"
        "    ev = fft(x[0::2]); od = fft(x[1::2])\n"
        "    out = [0j] * n\n"
        "    for k in range(n // 2):\n"
        "        t = math.e ** (-2j * math.pi * k / n) * od[k]\n"
        "        out[k] = ev[k] + t\n"
        "        out[k + n // 2] = ev[k] - t\n"
        "    return out\n"
        "print(%r, end='')\nopen('multiplets.tsv', 'w').write(%r)\n" % (NMR_STDOUT, NMR_TSV)
    )

def _build_nmr(d):
    import os
    open(os.path.join(d, "multiplets.tsv"), "w").write(NMR_TSV)
    open(os.path.join(d, "stdout.log"), "w").write(NMR_STDOUT)
    open(os.path.join(d, "stderr.log"), "w").write("")
    open(os.path.join(d, "nmr_1d.py"), "w").write(_nmr_py())

def _stub_nmr(ws):
    import os
    open(os.path.join(ws, "make_fid.py"), "w").write("print('wrote fid.csv')\n")
    open(os.path.join(ws, "nmr_1d.py"), "w").write(_nmr_py())

BUILDERS["nmr"] = _build_nmr
STUBS["nmr"] = _stub_nmr

_FORMULA_ISO = {
    "C": [(12.000000, 98.93), (13.003355, 1.07)],
    "H": [(1.007825, 99.9885), (2.014102, 0.0115)],
    "N": [(14.003074, 99.636), (15.000109, 0.364)],
    "O": [(15.994915, 99.757), (16.999131, 0.038), (17.999160, 0.205)],
    "P": [(30.973762, 100.0)],
    "S": [(31.972071, 94.99), (32.971459, 0.75), (33.967867, 4.25)],
}

def _pattern(counts):
    mass = sum(_FORMULA_ISO[e][0][0] * n for e, n in counts.items())
    m1 = m2 = 0.0
    for e, n in counts.items():
        a = _FORMULA_ISO[e]
        if len(a) > 1:
            r1 = a[1][1] / a[0][1]
            m1 += n * r1
            m2 += n * (n - 1) / 2.0 * r1 * r1
        if len(a) > 2:
            m2 += n * a[2][1] / a[0][1]
    return mass, m1, m2

_FORMULA_TRUE = [("CPD1", {"C": 6, "H": 12, "O": 6}, "C6H12O6", 7, 1.2763),
                 ("CPD2", {"C": 8, "H": 10, "N": 4, "O": 2}, "C8H10N4O2", 10, 2.1369),
                 ("CPD3", {"C": 5, "H": 11, "N": 1, "O": 2, "S": 1}, "C5H11NO2S", 2, 2.5581)]

def _formula_measured():
    rows = ["id\tmass\tM1\tM2"]
    for cid, counts, _, _, _ in _FORMULA_TRUE:
        m, m1, m2 = _pattern(counts)
        rows.append("%s\t%.4f\t%.6f\t%.6f" % (cid, m, m1, m2))
    return "\n".join(rows) + "\n"

def _formula_ranked():
    lines = ["id\tformula\tcalc_mass\terror_ppm\tM1_calc\tM2_calc\tscore"]
    for k, (cid, counts, formula, n, score) in enumerate(_FORMULA_TRUE):
        m, m1, m2 = _pattern(counts)
        err = 0.0
        lines.append("%s\t%s\t%.6f\t%+.3f\t%.6f\t%.6f\t%.4f" % (cid, formula, m, err, m1, m2, score))
        for j in range(1, n):
            fake = "X%d" % (j + k)
            fm, f1, f2 = m + 0.000455 * j, m1, m2
            ferr = (fm - m) / m * 1e6
            lines.append("%s\t%s\t%.6f\t%+.3f\t%.6f\t%.6f\t%.4f"
                         % (cid, fake, fm, ferr, f1, f2, score + 1.0 * j))
    return "\n".join(lines) + "\n"

FORMULA_STDOUT = "CPD1: 7 candidates\nCPD2: 10 candidates\nCPD3: 2 candidates\n"

def _build_formula(d):
    import os
    open(os.path.join(d, "measured.tsv"), "w").write(_formula_measured())
    open(os.path.join(d, "ranked.tsv"), "w").write(_formula_ranked())
    open(os.path.join(d, "stdout.log"), "w").write(FORMULA_STDOUT)

def _stub_formula(ws):
    import os
    open(os.path.join(ws, "make_test_data.py"), "w").write(
        "open('measured.tsv','w').write(%r)\nprint('wrote measured.tsv')\n" % _formula_measured())
    open(os.path.join(ws, "formula_finder.py"), "w").write(
        "print(%r, end='')\nopen('ranked.tsv','w').write(%r)\n" % (FORMULA_STDOUT, _formula_ranked()))

BUILDERS["formula"] = _build_formula
STUBS["formula"] = _stub_formula

CHROM_PEAKS = ("peak_id\trt_apex\trt_start\trt_end\theight\tarea\twidth\tN\ttf\tsn\trs_to_previous\n"
    "1\t60.000\t48.000\t72.000\t786.254\t7821.509\t24.000\t100.000\t0.993\t183.245\t-\n"
    "2\t150.000\t135.000\t168.000\t1198.618\t14920.273\t33.000\t330.579\t0.988\t279.350\t3.158\n"
    "3\t244.000\t225.000\t280.000\t725.128\t12032.407\t55.000\t314.901\t1.339\t168.999\t2.136\n")
CHROM_STDOUT = "n=26, mean=51.076, sd=4.291\npeaks detected: 3\n"
CHROM_SESSION_ECHO = ("# Chromatographic peak integration and USP system-suitability QC "
    "(prompt excerpt)\n\n"
    "| quantity | area | height | rt_apex | 5% crossings | Tf | N |\n"
    "| expected | 4.000 | 2.000 | 2.000 | 0.100 / 3.900 | 1.000 | 4.000 |")
CHROM_SESSION_EVIDENCE = ("triangle self-check (t=0..4, y=[0,1,2,1,0], l=0, r=4): "
    "area 4.000 height 2.000 rt_apex 2.000 Tf 1.000 N 4.000 "
    "5% crossings 0.100 and 3.900 - all exact")
CHROM_SESSION = _session_jsonl(CHROM_SESSION_ECHO, [CHROM_SESSION_EVIDENCE])

def _build_chrom(d):
    import os
    open(os.path.join(d, "peaks.tsv"), "w").write(CHROM_PEAKS)
    open(os.path.join(d, "stdout.log"), "w").write(CHROM_STDOUT)
    open(os.path.join(d, "session.jsonl"), "w").write(CHROM_SESSION)

def _stub_chrom(ws):
    import os
    open(os.path.join(ws, "make_chrom_data.py"), "w").write("print('wrote chrom.csv')\n")
    open(os.path.join(ws, "chrom_integrate.py"), "w").write(
        "print(%r, end='')\nopen('peaks.tsv','w').write(%r)\n" % (CHROM_STDOUT, CHROM_PEAKS))

BUILDERS["chrom"] = _build_chrom
STUBS["chrom"] = _stub_chrom

SPECTRAL_GEN_SRC = r'''#!/usr/bin/env python3
"""Deterministic generator for the spectral-library-search test data. Std-lib only."""

def lcg(state):
    while True:
        state = (1103515245 * state + 12345) % 2147483648
        yield state / 2147483648.0

LIBRARY = [
    ("caffeine",        [(42.1, 15), (58.0, 100), (69.0, 20), (82.0, 35),
                         (109.1, 55), (138.1, 60), (163.1, 10), (195.1, 90)]),
    ("acetaminophen",   [(43.0, 40), (65.0, 20), (80.9, 10), (92.0, 15),
                         (93.0, 60), (109.0, 45), (110.0, 35), (152.1, 80)]),
    ("sulfamethoxazole",[(65.0, 30), (92.0, 70), (99.0, 25), (108.0, 85),
                         (124.0, 20), (156.0, 90), (188.0, 50), (254.1, 75)]),
    ("nicotine",        [(42.0, 35), (84.1, 100), (117.0, 15), (119.1, 20),
                         (130.1, 25), (132.1, 40), (133.0, 10), (163.1, 60)]),
]

def write_spectra(path, entries, comment):
    lines = [comment, ""]
    for name, peaks in entries:
        lines.append(">NAME %s" % name)
        for i, (mz, inten) in enumerate(peaks):
            sep = "  " if i == 0 else " "   # real files mix spacing
            lines.append("%.4f%s%s" % (mz, sep, inten))
        lines.append("")
    with open(path, "w") as fh:
        fh.write("\n".join(lines).rstrip() + "\n")

write_spectra("library.txt", LIBRARY, "# minimal text spectral library")

rnd = lcg(20260824)
queries = []
for qid, (name, peaks) in zip(("q1", "q2", "q3"), LIBRARY[:3]):
    out = []
    for mz, inten in peaks:
        jmz = mz + (next(rnd) - 0.5) * 0.2
        jint = inten * (0.75 + 0.5 * next(rnd))
        if jint < 12.0:            # low-intensity peaks are dropped
            continue
        out.append((jmz, round(jint, 1)))
    for _ in range(2):             # noise peaks
        out.append((round(60.0 + next(rnd) * 340.0, 4), round(3.0 + next(rnd) * 8.0, 1)))
    out.sort()
    queries.append((qid, out))

queries.append(("q4", [(90.2, 50.0), (131.1, 30.0), (176.1, 80.0),
                       (220.2, 25.0), (300.1, 60.0)]))

write_spectra("queries.txt", queries, "# query spectra")
print("wrote library.txt, queries.txt")
'''

SPECTRAL_RESULTS = ("query_id\tbest_match\tscore\tmatched_peaks\ttotal_library_peaks\n"
    "q1\tcaffeine\t0.9373\t7\t8\n"
    "q2\tacetaminophen\t0.9113\t7\t8\n"
    "q3\tsulfamethoxazole\t0.9583\t8\t8\n"
    "q4\tNO_MATCH\t0.0000\t0\t8\n")
SPECTRAL_STDOUT = "queries: 4  called: 3  no_match: 1\n"

def _build_spectral(d):
    import os, subprocess, sys
    open(os.path.join(d, "make_test_data.py"), "w").write(SPECTRAL_GEN_SRC)
    subprocess.run([sys.executable, "make_test_data.py"], cwd=d, check=True,
                   capture_output=True)
    open(os.path.join(d, "results.tsv"), "w").write(SPECTRAL_RESULTS)
    open(os.path.join(d, "stdout.log"), "w").write(SPECTRAL_STDOUT)

def _stub_spectral(ws):
    import os
    open(os.path.join(ws, "make_test_data.py"), "w").write(SPECTRAL_GEN_SRC)
    open(os.path.join(ws, "libsearch.py"), "w").write(
        "print(%r, end='')\nopen('results.tsv','w').write(%r)\n" % (SPECTRAL_STDOUT, SPECTRAL_RESULTS))

BUILDERS["spectral"] = _build_spectral
STUBS["spectral"] = _stub_spectral


# --------------------------------------------------------------------------
# nmr_quad — quadrature (complex) FID prompt. Oracle from
# bench/reference/nmr_quad_spec.py, a literal implementation of the prompt.
# --------------------------------------------------------------------------

NMR_QUAD_TSV = ("ppm_center\tintegral\trelative_integral\n"
                "1.2000\t3.2215e+04\t1.0000\n"
                "3.4998\t7.2307e+03\t0.2245\n"
                "7.1997\t1.0825e+04\t0.3360\n"
                "8.4998\t3.5749e+03\t0.1110\n")

NMR_QUAD_STDOUT = "points read: 8192\nzero-filled to: 16384\npeaks found: 4\n"

# Only the pinned transform: the grader imports `fft` from the agent's module.
NMR_QUAD_FFT = '''import cmath, math

def fft(x):
    n = len(x)
    if n == 1:
        return list(x)
    ev = fft(x[0::2]); od = fft(x[1::2])
    out = [0j] * n
    for k in range(n // 2):
        t = cmath.exp(-2j * math.pi * k / n) * od[k]
        out[k] = ev[k] + t
        out[k + n // 2] = ev[k] - t
    return out
'''


def _build_nmr_quad(d):
    import os
    open(os.path.join(d, "multiplets.tsv"), "w", newline="").write(NMR_QUAD_TSV)
    open(os.path.join(d, "stdout.log"), "w").write(NMR_QUAD_STDOUT)
    open(os.path.join(d, "stderr.log"), "w").write("")
    open(os.path.join(d, "nmr_quad.py"), "w").write(NMR_QUAD_FFT)


def _stub_nmr_quad(ws):
    import os
    open(os.path.join(ws, "make_fid_quad.py"), "w").write(
        "open('fid_quad.csv','w').write('time_s,real,imag\\n0.0,1.0,0.0\\n')\n"
        "print('wrote fid_quad.csv')\n")
    open(os.path.join(ws, "nmr_quad.py"), "w").write(
        NMR_QUAD_FFT
        + "\nimport sys\n"
        + "open('multiplets.tsv','w',newline='').write(%r)\n" % NMR_QUAD_TSV
        + "sys.stdout.write(%r)\n" % NMR_QUAD_STDOUT)


BUILDERS["nmr_quad"] = _build_nmr_quad
STUBS["nmr_quad"] = _stub_nmr_quad


# --------------------------------------------------------------------------
# dda_v2 — DDA search with FDR. The grader re-executes search.py and times it,
# so this fixture is built by actually running the reference tools rather than
# by hard-coding 59 PSM rows.
# --------------------------------------------------------------------------

def _dda_v2_paths():
    import os
    ref = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reference")
    return (os.path.join(ref, "make_search_data.py"), os.path.join(ref, "dda_search.py"),
            os.path.join(ref, "search_conformant.py"))


def _build_dda_v2(d):
    import os, shutil, subprocess, sys
    gen, engine, conformant = _dda_v2_paths()
    shutil.copy2(gen, os.path.join(d, "make_search_data.py"))
    shutil.copy2(engine, os.path.join(d, "dda_search.py"))
    shutil.copy2(conformant, os.path.join(d, "search.py"))
    subprocess.run([sys.executable, "make_search_data.py"], cwd=d, check=True,
                   stdout=subprocess.DEVNULL)
    out = subprocess.run([sys.executable, "search.py", "bench.fasta", "bench.mgf",
                          "-o", "psms.tsv"], cwd=d, check=True,
                         capture_output=True, text=True)
    open(os.path.join(d, "stdout.log"), "w").write(out.stdout)


def _stub_dda_v2(ws):
    import os, shutil
    gen, engine, conformant = _dda_v2_paths()
    shutil.copy2(gen, os.path.join(ws, "make_search_data.py"))
    shutil.copy2(engine, os.path.join(ws, "dda_search.py"))
    shutil.copy2(conformant, os.path.join(ws, "search.py"))


BUILDERS["dda_v2"] = _build_dda_v2
STUBS["dda_v2"] = _stub_dda_v2


# --------------------------------------------------------------------------
# mass_reader_s — base module, graded by importing the agent's own readers.
# --------------------------------------------------------------------------

def _repo_path(*parts):
    import os
    here = os.path.dirname(os.path.abspath(__file__))          # bench/tests
    return os.path.join(os.path.dirname(os.path.dirname(here)), *parts)


def _build_mass_reader_s(d):
    """Conformant workspace: the tested reference readers plus the real inputs.

    stdout.log is produced by actually running the pinned run_cmd
    (`python3 mzml_reader.py bsa_orbitrap_first40.mzML`), because the grader now
    checks the one-line summary the prompt mandates. It used to be written empty,
    which is how a fixture that violated its own prompt scored 6/6.
    """
    import os, shutil, subprocess, sys
    for mod in ("fasta_reader.py", "mzml_reader.py"):
        shutil.copy2(_repo_path("bench", "reference", "lib", mod), d)
    for f in ("ecoli_k12_48.fasta", "bsa_orbitrap_first40.mzML",
              "thermo_small_raw.mzML"):
        shutil.copy2(_repo_path("data", "mass_reader", f), d)
    out = subprocess.run([sys.executable, "mzml_reader.py",
                          "bsa_orbitrap_first40.mzML"], cwd=d, check=True,
                         capture_output=True, text=True)
    open(os.path.join(d, "stdout.log"), "w").write(out.stdout)


BUILDERS["mass_reader_s"] = _build_mass_reader_s


# --------------------------------------------------------------------------
# titration_s — short prompt on the published acetic-acid table.
# --------------------------------------------------------------------------

def _titration_tool_source():
    """A conformant titration.py: it takes the input path from the command line
    (as the prompt's `python3 titration.py <csv> -o results.tsv` requires) and
    delegates the analysis to the reference. Reading the path from argv is what
    makes it survive the grader's perturbed-input re-run; a version that
    hardcoded "acetic_acid_naoh.csv" would not, and neither should it."""
    return (
        "import sys\n"
        "sys.path.insert(0, %r)\n"
        "import titration_ref\n"
        "argv = sys.argv[1:]\n"
        "src = argv[0]\n"
        "out = argv[argv.index('-o') + 1] if '-o' in argv else 'results.tsv'\n"
        "r = titration_ref.analyse(src)\n"
        "open(out, 'w', newline='').write("
        "'equivalence_volume_mL\\tpKa\\tanalyte_concentration_M\\n' + "
        "'%%.3f\\t%%.3f\\t%%.5f\\n' %% (r['veq'], r['pka'], r['conc']))\n"
        "print('points=%%d Veq=%%.3f pKa=%%.3f conc=%%.5f' %% "
        "(r['points'], r['veq'], r['pka'], r['conc']))\n"
        % _repo_path("bench", "reference", "short"))


def _build_titration_s(d):
    """Conformant artifacts, produced by running a conformant titration.py (the
    reference behind an argv-driven CLI) on the real CSV -- the grader re-runs
    that script on a perturbed input, so the fixture must actually ship one."""
    import os, shutil, subprocess, sys
    src = _repo_path("data", "titration", "acetic_acid_naoh.csv")
    shutil.copy2(src, d)
    open(os.path.join(d, "titration.py"), "w").write(_titration_tool_source())
    out = subprocess.run([sys.executable, "titration.py", "acetic_acid_naoh.csv",
                          "-o", "results.tsv"], cwd=d, check=True,
                         capture_output=True, text=True)
    open(os.path.join(d, "stdout.log"), "w").write(out.stdout)


BUILDERS["titration_s"] = _build_titration_s


# --------------------------------------------------------------------------
# pca_s — short prompt on the MTBLS1 real-data bucket matrix.
# --------------------------------------------------------------------------

def _build_pca_s(d):
    import os, shutil, sys
    for f in ("features.csv", "groups.csv"):
        shutil.copy2(_repo_path("data", "pca", f), d)
    sys.path.insert(0, _repo_path("bench", "reference", "short"))
    import pca_ref
    r = pca_ref.run(os.path.join(d, "features.csv"), os.path.join(d, "groups.csv"))
    with open(os.path.join(d, "scores.tsv"), "w") as fh:
        fh.write("sample\tgroup\tPC1\tPC2\n")
        for s, g, row in zip(r["samples"], r["groups"], r["scores"]):
            fh.write("%s\t%s\t%.6f\t%.6f\n" % (s, g, row[0], row[1]))
    open(os.path.join(d, "stdout.log"), "w").write(
        "features_in=%d features_kept=%d pc1_var=%.4f pc2_var=%.4f\n"
        % (r["features_in"], r["features_kept"], r["pc1_var"], r["pc2_var"]))


BUILDERS["pca_s"] = _build_pca_s


# --------------------------------------------------------------------------
# mass_stats_s — short prompt on the MTBLS14397 real two-condition matrix.
# --------------------------------------------------------------------------

def _build_mass_stats_s(d):
    """Conformant artifacts: run mass_stats_ref on copies of the two real
    inputs. expected_stats.tsv is NOT copied here -- the grader never reads
    it either, only the literal constants (618/0/253, top-10 ids) it
    published in data/mass_stats/README.md, so seeding it in the fixture
    would only let a submission simply copy the answers."""
    import os, shutil, sys
    for f in ("quant_mtbls14397_pos.csv", "groups.tsv"):
        shutil.copy2(_repo_path("data", "mass_stats", f), d)
    sys.path.insert(0, _repo_path("bench", "reference", "short"))
    import mass_stats_ref
    r = mass_stats_ref.run(os.path.join(d, "quant_mtbls14397_pos.csv"),
                            os.path.join(d, "groups.tsv"))
    with open(os.path.join(d, "stats.tsv"), "w") as fh:
        fh.write("feature_id\tlog2fc\tt\tdf\tp_value\tq_value\tsignificant\n")
        for row in r["rows"]:
            fh.write("%s\t%.10g\t%.10g\t%.10g\t%.10g\t%.10g\t%d\n"
                      % (row["feature_id"], row["log2fc"], row["t"], row["df"],
                         row["p_value"], row["q_value"], row["significant"]))
    open(os.path.join(d, "stdout.log"), "w").write(
        "tested=%d filtered=%d significant=%d\n"
        % (r["tested"], r["filtered"], r["significant"]))


BUILDERS["mass_stats_s"] = _build_mass_stats_s


# --------------------------------------------------------------------------
# features_s — short prompt on the real BSA digest MS1 run.
# --------------------------------------------------------------------------

def _build_features_s(d):
    import os, shutil, sys
    shutil.copy2(_repo_path("data", "feature_extraction", "BSA1_F1.mzML"), d)
    shutil.copy2(_repo_path("bench", "reference", "lib", "mzml_reader.py"), d)
    sys.path.insert(0, _repo_path("bench", "reference", "short"))
    import features_ref
    r = features_ref.detect(os.path.join(d, "BSA1_F1.mzML"))
    with open(os.path.join(d, "features.tsv"), "w") as fh:
        fh.write("feature_id\tmz\trt_apex\trt_start\trt_end\tapex_intensity\tn_scans\n")
        for n, f in enumerate(r["features"], 1):
            fh.write("F%04d\t%.4f\t%.2f\t%.2f\t%.2f\t%.1f\t%d\n"
                     % (n, f["mz"], f["rt_apex"], f["rt_start"], f["rt_end"],
                        f["apex_intensity"], f["n_scans"]))
    open(os.path.join(d, "stdout.log"), "w").write(
        "ms1_scans=%d windows=%d features=%d\n"
        % (r["ms1_scans"], r["windows"], len(r["features"])))


BUILDERS["features_s"] = _build_features_s


# --------------------------------------------------------------------------
# calibration_s — short prompt on the NIST StRD Norris calibration data.
# --------------------------------------------------------------------------

def _calibration_tool_source():
    """A conformant calibrate.py: it takes the input path from the command line
    (as the prompt's `python3 calibrate.py <csv> -o results.tsv` requires) and
    delegates the arithmetic to the reference. Reading the path from argv is
    what makes it survive the grader's perturbed-input re-run; a version that
    hardcoded "norris.csv" would not, and neither should it."""
    return (
        "import sys\n"
        "sys.path.insert(0, %r)\n"
        "import calibration_ref\n"
        "argv = sys.argv[1:]\n"
        "src = argv[0]\n"
        "out = argv[argv.index('-o') + 1] if '-o' in argv else 'results.tsv'\n"
        "r = calibration_ref.run(src)\n"
        "open(out, 'w', newline='').write("
        "'slope\\tintercept\\tresidual_sd\\tr_squared\\tlod\\tloq\\n' + "
        "'%%.12f\\t%%.12f\\t%%.12f\\t%%.12f\\t%%.6f\\t%%.6f\\n' %% "
        "(r['slope'], r['intercept'], r['residual_sd'], r['r_squared'], r['lod'], r['loq']))\n"
        "print('n=%%d slope=%%.12f intercept=%%.12f residual_sd=%%.12f "
        "r_squared=%%.12f lod=%%.6f loq=%%.6f' %% "
        "(r['n'], r['slope'], r['intercept'], r['residual_sd'], r['r_squared'], "
        "r['lod'], r['loq']))\n"
        % _repo_path("bench", "reference", "short"))


def _build_calibration_s(d):
    """Conformant artifacts, produced by running a conformant calibrate.py (the
    reference behind an argv-driven CLI) on the real CSV -- the grader re-runs
    that script on a perturbed input, so the fixture must actually ship one."""
    import os, shutil, subprocess, sys
    src = _repo_path("data", "calibration", "norris.csv")
    shutil.copy2(src, d)
    open(os.path.join(d, "calibrate.py"), "w").write(_calibration_tool_source())
    out = subprocess.run([sys.executable, "calibrate.py", "norris.csv",
                          "-o", "results.tsv"], cwd=d, check=True,
                         capture_output=True, text=True)
    open(os.path.join(d, "stdout.log"), "w").write(out.stdout)


BUILDERS["calibration_s"] = _build_calibration_s


# --------------------------------------------------------------------------
# uvvis_s — short prompt on the real 4-nitrophenol UV-Vis spectrum.
# --------------------------------------------------------------------------

def _uvvis_tool_source():
    """A conformant uvvis.py: it takes the input path from the command line
    (as the prompt's `python3 uvvis.py <csv> -o bands.tsv` requires) and
    delegates the arithmetic to the reference. Reading the path from argv is
    what makes it survive the grader's perturbed-input re-run; a version that
    hardcoded "4-nitrophenol.csv" would not, and neither should it."""
    return (
        "import sys\n"
        "sys.path.insert(0, %r)\n"
        "import uvvis_ref\n"
        "argv = sys.argv[1:]\n"
        "src = argv[0]\n"
        "out = argv[argv.index('-o') + 1] if '-o' in argv else 'bands.tsv'\n"
        "r = uvvis_ref.run(src)\n"
        "open(out, 'w', newline='').write("
        "'lambda_max_nm\\tepsilon\\tfwhm_nm\\n' + "
        "'%%.3f\\t%%.2f\\t%%.3f\\n' %% "
        "(r['lambda_max'], r['epsilon'], r['fwhm']))\n"
        "print('points=%%d bands=%%d lambda_max=%%.3f epsilon=%%.2f' %% "
        "(r['points'], r['bands'], r['lambda_max'], r['epsilon']))\n"
        % _repo_path("bench", "reference", "short"))


def _build_uvvis_s(d):
    """Conformant artifacts, produced by running a conformant uvvis.py (the
    reference behind an argv-driven CLI) on the real CSV -- the grader re-runs
    that script on a perturbed input, so the fixture must actually ship one."""
    import os, shutil, subprocess, sys
    src = _repo_path("data", "uvvis", "4-nitrophenol.csv")
    shutil.copy2(src, d)
    open(os.path.join(d, "uvvis.py"), "w").write(_uvvis_tool_source())
    out = subprocess.run([sys.executable, "uvvis.py", "4-nitrophenol.csv",
                          "-o", "bands.tsv"], cwd=d, check=True,
                         capture_output=True, text=True)
    open(os.path.join(d, "stdout.log"), "w").write(out.stdout)


BUILDERS["uvvis_s"] = _build_uvvis_s


# --------------------------------------------------------------------------
# formula_s — short prompt on the real MassBank-derived accurate-mass table.
# --------------------------------------------------------------------------

def _build_formula_s(d):
    """Conformant artifacts, produced by running formula_ref directly against
    the real measured_caffeine.tsv -- no perturbation criterion here (see
    grade_formula_s.py), so no runnable formula_finder.py is needed, same
    shape as _build_pca_s."""
    import os, shutil, sys
    src = _repo_path("data", "formula", "measured_caffeine.tsv")
    shutil.copy2(src, d)
    sys.path.insert(0, _repo_path("bench", "reference", "short"))
    import formula_ref
    r = formula_ref.run(os.path.join(d, "measured_caffeine.tsv"))
    ids = [k for k in r if k not in ("blocks", "candidates")]  # dict preserves input order
    with open(os.path.join(d, "ranked.tsv"), "w", newline="") as fh:
        fh.write("id\trank\tformula\tcalc_mass\terror_ppm\tscore\n")
        for cid in ids:
            for row in r[cid]:
                fh.write("%s\t%d\t%s\t%.6f\t%+.3f\t%.4f\n"
                          % (cid, row["rank"], row["formula"], row["calc_mass"],
                             row["error_ppm"], row["score"]))
    open(os.path.join(d, "stdout.log"), "w").write(
        "blocks=%d candidates=%d\n" % (r["blocks"], r["candidates"]))


BUILDERS["formula_s"] = _build_formula_s


# --------------------------------------------------------------------------
# spectral_s — short prompt on the real MassBank-derived MS/MS library.
# --------------------------------------------------------------------------

def _spectral_tool_source():
    """A conformant libsearch.py: it takes both input paths from the command
    line (as the prompt's `python3 libsearch.py queries.txt library.txt -o
    results.tsv` requires) and delegates the matching/scoring to the
    reference. Reading the paths from argv is what makes it survive the
    grader's reduced-library re-run; a version that hardcoded "library.txt"
    would not, and neither should it."""
    return (
        "import sys\n"
        "sys.path.insert(0, %r)\n"
        "import spectral_ref\n"
        "argv = sys.argv[1:]\n"
        "queries, library = argv[0], argv[1]\n"
        "out = argv[argv.index('-o') + 1] if '-o' in argv else 'results.tsv'\n"
        "rows = spectral_ref.run(queries, library)\n"
        "with open(out, 'w', newline='') as fh:\n"
        "    fh.write('query\\tbest_match\\tscore\\tmatched_peaks\\ttotal_library_peaks\\n')\n"
        "    for r in rows:\n"
        "        fh.write('%%s\\t%%s\\t%%.4f\\t%%d\\t%%d\\n' %% "
        "(r['query'], r['best_match'], r['score'], r['matched_peaks'], "
        "r['total_library_peaks']))\n"
        "called = sum(1 for r in rows if r['best_match'] != 'NO_MATCH')\n"
        "print('queries: %%d  called: %%d  no_match: %%d' %% "
        "(len(rows), called, len(rows) - called))\n"
        % _repo_path("bench", "reference", "short"))


def _build_spectral_s(d):
    """Conformant artifacts, produced by running a conformant libsearch.py
    (the reference behind an argv-driven CLI) on the real queries.txt/
    library.txt -- the grader re-runs that script on a library with one
    entry removed, so the fixture must actually ship one."""
    import os, shutil, subprocess, sys
    for f in ("queries.txt", "library.txt"):
        shutil.copy2(_repo_path("data", "spectral", f), d)
    open(os.path.join(d, "libsearch.py"), "w").write(_spectral_tool_source())
    out = subprocess.run(
        [sys.executable, "libsearch.py", "queries.txt", "library.txt",
         "-o", "results.tsv"], cwd=d, check=True,
        capture_output=True, text=True)
    open(os.path.join(d, "stdout.log"), "w").write(out.stdout)


BUILDERS["spectral_s"] = _build_spectral_s


# --------------------------------------------------------------------------
# chrom_s — short prompt on the real 220 nm Agilent DAD chromatogram.
# --------------------------------------------------------------------------

def _chrom_tool_source():
    """A conformant chrom_integrate.py: it takes the input path from the
    command line (as the prompt's `python3 chrom_integrate.py <csv> -o
    peaks.tsv` requires) and delegates the analysis to the reference. Reading
    the path from argv is what makes it survive the grader's peak-injected
    re-run; a version that hardcoded "chrom.csv" would not, and neither
    should it."""
    return (
        "import sys\n"
        "sys.path.insert(0, %r)\n"
        "import chrom_ref\n"
        "argv = sys.argv[1:]\n"
        "src = argv[0]\n"
        "out = argv[argv.index('-o') + 1] if '-o' in argv else 'peaks.tsv'\n"
        "r = chrom_ref.run(src)\n"
        "lines = ['peak_id\\trt_apex_s\\theight\\tarea']\n"
        "for i, p in enumerate(r['peaks'], start=1):\n"
        "    lines.append('%%d\\t%%.2f\\t%%.2f\\t%%.3f' %% "
        "(i, p['rt_apex_s'], p['height'], p['area']))\n"
        "open(out, 'w', newline='').write('\\n'.join(lines) + '\\n')\n"
        "print('points=%%d baseline=%%.3f sigma=%%.3f peaks=%%d' %% "
        "(r['points'], r['baseline'], r['sigma'], len(r['peaks'])))\n"
        % _repo_path("bench", "reference", "short"))


def _build_chrom_s(d):
    """Conformant artifacts, produced by running a conformant
    chrom_integrate.py (the reference behind an argv-driven CLI) on the real
    chrom.csv -- the grader re-runs that script on a peak-injected input, so
    the fixture must actually ship one."""
    import os, shutil, subprocess, sys
    src = _repo_path("data", "chrom", "chrom.csv")
    shutil.copy2(src, d)
    open(os.path.join(d, "chrom_integrate.py"), "w").write(_chrom_tool_source())
    out = subprocess.run([sys.executable, "chrom_integrate.py", "chrom.csv",
                          "-o", "peaks.tsv"], cwd=d, check=True,
                         capture_output=True, text=True)
    open(os.path.join(d, "stdout.log"), "w").write(out.stdout)


BUILDERS["chrom_s"] = _build_chrom_s


# --------------------------------------------------------------------------
# nmr_s — short prompt on the real MTBLS1 complex-quadrature urine FID.
# --------------------------------------------------------------------------

def _build_nmr_s(d):
    """Conformant artifacts: run nmr_ref directly on a copy of the real
    fid_complex.csv. No perturbation criterion here (see grade_nmr_s.py), so
    no runnable nmr.py is needed -- same shape as _build_formula_s /
    _build_pca_s."""
    import os, shutil, sys
    src = _repo_path("data", "nmr", "fid_complex.csv")
    shutil.copy2(src, d)
    sys.path.insert(0, _repo_path("bench", "reference", "short"))
    import nmr_ref
    r = nmr_ref.run(os.path.join(d, "fid_complex.csv"))
    with open(os.path.join(d, "multiplets.tsv"), "w") as fh:
        fh.write("ppm_center\tintegral_rel\n")
        for p in r["peaks"]:
            fh.write("%.4f\t%.6f\n" % (p["ppm_center"], p["integral_rel"]))
    open(os.path.join(d, "stdout.log"), "w").write(
        "points=%d peaks=%d reference_ppm=%.3f\n"
        % (r["points"], len(r["peaks"]), r["reference_ppm"]))


BUILDERS["nmr_s"] = _build_nmr_s


# --------------------------------------------------------------------------
# dda_s -- short prompt on the real UPS1-in-yeast DDA run (Task 9/10).
# --------------------------------------------------------------------------

# dda_ref.run() takes ~1.1 s per call (~2.2 s for the filtered+unfiltered
# pair) on the full 8.9 MB MGF. The conformant test and each of the six
# mutation subtests in test_grade_dda_s.py call build_artifacts("dda_s", ...)
# independently, so without this module-level cache the suite would pay that
# cost seven times. Keyed on nothing but presence: the inputs are fixed real
# files, so one computation is valid for the whole test process.
_DDA_REF_CACHE = {}


def _dda_reference():
    if "runs" not in _DDA_REF_CACHE:
        import sys
        sys.path.insert(0, _repo_path("bench", "reference", "short"))
        import dda_ref
        fasta = _repo_path("data", "database_search", "yeast_pe1_plus_ups.fasta")
        mgf = _repo_path("data", "database_search", "ups1_yeast_dda_first1200.mgf")
        filtered = dda_ref.run(fasta, mgf, peak_filter=True)
        unfiltered = dda_ref.run(fasta, mgf, peak_filter=False)
        _DDA_REF_CACHE["runs"] = (filtered, unfiltered)
    return _DDA_REF_CACHE["runs"]


def _build_dda_s(d):
    """Conformant artifacts: psms.tsv and stdout.log written directly from
    dda_ref's filtered/unfiltered runs on copies of the two real inputs. No
    perturbation criterion here (see grade_dda_s.py: numbers are literal
    constants from data/database_search/README.md's v2 block, checked
    against stdout.log, plus the UPS1-protein count checked against the rows
    of psms.tsv itself), so no runnable search.py is needed -- same shape as
    _build_formula_s / _build_nmr_s."""
    import os, shutil
    for f in ("yeast_pe1_plus_ups.fasta", "ups1_yeast_dda_first1200.mgf"):
        shutil.copy2(_repo_path("data", "database_search", f), d)
    filtered, unfiltered = _dda_reference()
    with open(os.path.join(d, "psms.tsv"), "w") as fh:
        fh.write("scan\tpeptide\tprotein\tdecoy\tscore\tqvalue\n")
        for row in filtered["rows"]:
            fh.write("%s\t%s\t%s\t%d\t%d\t%.6g\n"
                      % (row["scan"], row["peptide"], row["protein"],
                         row["decoy"], row["score"], row["qvalue"]))
    open(os.path.join(d, "stdout.log"), "w").write(
        "targets=%d decoys=%d spectra=%d with_candidate=%d best_hits=%d "
        "decoy_hits=%d psms_1pct=%d psms_1pct_unfiltered=%d\n"
        % (filtered["targets"], filtered["decoys"], filtered["spectra"],
           filtered["with_candidate"], filtered["best_hits"],
           filtered["decoy_hits"], filtered["psms_1pct"],
           unfiltered["psms_1pct"]))


BUILDERS["dda_s"] = _build_dda_s


# --------------------------------------------------------------------------
# Dry-run stubs for the four pilot specs: each writes the artifact files the
# spec expects, producing conformant output by delegating to the same
# reference code the fixtures above use.
# --------------------------------------------------------------------------

def _stub_mass_reader_s(ws):
    import shutil
    for mod in ("fasta_reader.py", "mzml_reader.py"):
        shutil.copy2(_repo_path("bench", "reference", "lib", mod), ws)


def _stub_titration_s(ws):
    import os
    open(os.path.join(ws, "titration.py"), "w").write(_titration_tool_source())


def _stub_pca_s(ws):
    import os
    open(os.path.join(ws, "pca.py"), "w").write(
        "import sys\n"
        "sys.path.insert(0, %r)\n"
        "import pca_ref\n"
        "r = pca_ref.run('features.csv', 'groups.csv')\n"
        "fh = open('scores.tsv','w')\n"
        "fh.write('sample\\tgroup\\tPC1\\tPC2\\n')\n"
        "[fh.write('%%s\\t%%s\\t%%.6f\\t%%.6f\\n' %% (s, g, row[0], row[1])) "
        "for s, g, row in zip(r['samples'], r['groups'], r['scores'])]\n"
        "fh.close()\n"
        "print('features_in=%%d features_kept=%%d pc1_var=%%.4f pc2_var=%%.4f' %% "
        "(r['features_in'], r['features_kept'], r['pc1_var'], r['pc2_var']))\n"
        % _repo_path("bench", "reference", "short"))


def _stub_features_s(ws):
    import os
    open(os.path.join(ws, "features.py"), "w").write(
        "import sys\n"
        "sys.path.insert(0, %r)\n"
        "import features_ref\n"
        "r = features_ref.detect('BSA1_F1.mzML')\n"
        "fh = open('features.tsv','w')\n"
        "fh.write('feature_id\\tmz\\trt_apex\\trt_start\\trt_end\\t"
        "apex_intensity\\tn_scans\\n')\n"
        "[fh.write('F%%04d\\t%%.4f\\t%%.2f\\t%%.2f\\t%%.2f\\t%%.1f\\t%%d\\n' %% "
        "(n, f['mz'], f['rt_apex'], f['rt_start'], f['rt_end'], "
        "f['apex_intensity'], f['n_scans'])) "
        "for n, f in enumerate(r['features'], 1)]\n"
        "fh.close()\n"
        "print('ms1_scans=%%d windows=%%d features=%%d' %% "
        "(r['ms1_scans'], r['windows'], len(r['features'])))\n"
        % _repo_path("bench", "reference", "short"))


STUBS["mass_reader_s"] = _stub_mass_reader_s
STUBS["titration_s"] = _stub_titration_s
STUBS["pca_s"] = _stub_pca_s
STUBS["features_s"] = _stub_features_s
