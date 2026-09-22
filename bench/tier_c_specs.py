#!/usr/bin/env python3
"""Tier (c) run specs: per-tool real-data addenda + data files for the local-LLM campaign.

Each entry:
  prompt     — path to the prompt file (verbatim prefix of the cell prompt)
  data_files — files copied from data/<tool>/ into the fresh cell workspace
  addendum   — appended to the prompt: names the real data, the run command(s),
               constant overrides, and what to report. The synthetic acceptance
               criteria are explicitly disclaimed; grading is harness-side
               against data/<tool>/README.md expected results.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def _p(directory, name):
    return os.path.join(REPO, "examples", directory, name)


def _d(tool, name):
    return os.path.join(REPO, "data", tool, name)


def _add(tool, data_names, command, overrides="", report=""):
    files = ", ".join("`%s`" % n for n in data_names)
    text = (
        "## Real-data run (tier c)\n\n"
        "This workspace already contains real data (not generated): %s. "
        "**Do not create or run the test-data generator.** Write the tool exactly as "
        "specified above, then apply it to the real data:\n\n%s\n"
        % (files, command)
    )
    if overrides:
        text += "\nConstant overrides for this dataset: %s\n" % overrides
    text += (
        "\nThe synthetic acceptance-criteria numbers above do NOT apply to this run; "
        "this is real data and your outputs will be compared against independent "
        "reference values by the harness.\n"
    )
    if report:
        text += "\nReport: %s\n" % report
    return text


TIER_C = {
    "calibration": {
        "prompt": _p("calibration", "minimal_calibration_prompt.md"),
        "data_files": [_d("calibration", "norris.csv")],
        "addendum": _add(
            "calibration", ["norris.csv"],
            "Regress y on x (columns `y,x`) using your weighted least-squares kernel "
            "**with every weight set to 1 (unweighted mode)** on `norris.csv`.",
            "unweighted fit (w_i = 1); x = instrument response, y = ozone density",
            "slope, intercept, residual standard deviation about the fitted line, and "
            "unweighted R², each to at least 9 significant digits, plus the number of "
            "observations used.",
        ),
    },
    "titration": {
        "prompt": _p("titration", "minimal_titration_prompt.md"),
        "data_files": [_d("titration", "acetic_acid_naoh.csv")],
        "addendum": _add(
            "titration", ["acetic_acid_naoh.csv"],
            "`python3 titration.py acetic_acid_naoh.csv -o results.tsv`",
            "C_b = 0.100 M NaOH titrant, V0 = 25.00 mL analyte (acetic acid)",
            "equivalence volume (both derivative methods), pKa, and analyte "
            "concentration, same results.tsv format as the spec.",
        ),
    },
    "formula": {
        "prompt": _p("formula_finder", "minimal_formula_finder_prompt.md"),
        "data_files": [_d("formula", "measured_caffeine.tsv")],
        "addendum": _add(
            "formula", ["measured_caffeine.tsv"],
            "`python3 formula_finder.py measured_caffeine.tsv -o ranked.tsv`",
            "none — masses are neutral monoisotopic as the spec assumes",
            "the standard ranked.tsv plus the candidate-count stdout lines.",
        ),
    },
    "spectral": {
        "prompt": _p("spectral_library", "minimal_spectral_library_prompt.md"),
        "data_files": [_d("spectral", "library.txt"), _d("spectral", "queries.txt")],
        "addendum": _add(
            "spectral", ["library.txt", "queries.txt"],
            "`python3 libsearch.py queries.txt library.txt -o results.tsv`",
            "none — files already use the spec's text format",
            "the standard results.tsv and summary stdout line (real spectra: scores "
            "will differ from the synthetic criteria).",
        ),
    },
    "uvvis": {
        "prompt": _p("uvvis_spectrum", "minimal_uvvis_prompt.md"),
        "data_files": [_d("uvvis", "4-nitrophenol.csv")],
        "addendum": _add(
            "uvvis", ["4-nitrophenol.csv"],
            "`python3 uvvis.py 4-nitrophenol.csv -o peaks.tsv` (real spectrum of "
            "4-nitrophenol in acidified water, 225–800 nm)",
            "the y-column holds molar absorption coefficients (M⁻¹ cm⁻¹), not raw "
            "absorbance — band detection is unaffected; the concentration line is "
            "not meaningful for this dataset — print `n/a` for it",
            "band table (lambda_max, a_max) only.",
        ),
    },
    "chrom": {
        "prompt": _p("chrom_integration", "minimal_chrom_integration_prompt.md"),
        "data_files": [_d("chrom", "chrom.csv")],
        "addendum": _add(
            "chrom", ["chrom.csv"],
            "`python3 chrom_integrate.py chrom.csv --noise <T0> <T1> -o peaks.tsv` "
            "where <T0>/<T1> bracket a peak-free region at the start of the run "
            "(pick the first 10% of the time span unless it contains a peak).",
            "same USP conventions as the spec",
            "the standard peaks.tsv + noise statistics stdout.",
        ),
    },
    "nmr": {
        "prompt": _p("nmr_1d", "minimal_nmr_1d_prompt.md"),
        "data_files": [_d("nmr", "fid.csv"), _d("nmr", "acqus_constants.txt")],
        "addendum": _add(
            "nmr", ["fid.csv", "acqus_constants.txt"],
            "`python3 nmr_1d.py fid.csv -o multiplets.tsv`",
            "use the spectral width, dwell time, and carrier (ppm) from "
            "`acqus_constants.txt` instead of the spec's synthetic constants",
            "the standard multiplets.tsv (ppm centers + relative integrals).",
        ),
    },
    "pca": {
        "prompt": _p("pca_untargeted", "minimal_pca_prompt.md"),
        "data_files": [_d("pca", "features.csv"), _d("pca", "groups.csv")],
        "addendum": _add(
            "pca", ["features.csv", "groups.csv"],
            "`python3 pca.py features.csv -o scores.tsv --loadings loadings.tsv` "
            "(`groups.csv` is provided for context only; the tool does not read it).",
            "same preprocessing pipeline as the spec (≥80% filter, linear row-mean "
            "imputation, log2, mean-center, covariance PCA). Empty cells are "
            "below-detection values — the spec's filter/impute rules handle them. "
            "Real data: the two groups need NOT separate cleanly on PC1; report the "
            "numbers as computed",
            "the standard stdout lines (kept features, variance fractions) plus "
            "scores.tsv/loadings.tsv.",
        ),
    },
    "mass_reader": {
        "prompt": _p("mass_reader", "minimal_readers_prompt.md"),
        "data_files": [
            _d("mass_reader", "bsa_orbitrap_first40.mzML"),
            _d("mass_reader", "thermo_small_raw.mzML"),
            _d("mass_reader", "ecoli_k12_48.fasta"),
        ],
        "addendum": _add(
            "mass_reader", ["bsa_orbitrap_first40.mzML", "thermo_small_raw.mzML",
                            "ecoli_k12_48.fasta"],
            "Run the mzML readers on BOTH real mzML files (one centroided MS1+MS2 "
            "in seconds, one profile MS1 with zlib-compressed binary arrays and "
            "retention times in minutes) and the FASTA reader on the real FASTA, "
            "with the tool's pinned command-line interface.",
            "files are real instrument exports — follow the spec's decoding rules; "
            "TIC = float64 sum of the decoded intensity arrays",
            "for each mzML: scan counts by MS level, TIC, first/last scan retention "
            "times in seconds, precursor count, charge states; for the FASTA: entry "
            "count, total residues, first entry id.",
        ),
    },
    "database_search": {
        "prompt": _p("database_search", "minimal_dda_search_prompt.md"),
        "data_files": [
            _d("database_search", "ups1_yeast_dda_first1200.mgf"),
            _d("database_search", "yeast_pe1_plus_ups.fasta"),
        ],
        "addendum": _add(
            "database_search", ["ups1_yeast_dda_first1200.mgf", "yeast_pe1_plus_ups.fasta"],
            "Run `search.py` on the provided real MS2 peak lists (MGF format: "
            "BEGIN IONS/END IONS blocks with PEPMASS and CHARGE headers — add an "
            "MGF reader alongside your mzML reader) against the provided real "
            "FASTA (3260 proteins), with the spec's enzyme, tolerance, scoring, "
            "and target/decoy rules.",
            "same enzyme/tolerance/FDR rules as the spec; 1200 spectra",
            "PSM count at the spec's FDR threshold and the list of identified "
            "proteins with their hit counts (top 25 by hits is enough).",
        ),
    },
    "feature_extraction": {
        "prompt": _p("feature_extraction", "minimal_feature_detection_prompt.md"),
        "data_files": [_d("feature_extraction", "BSA1_F1.mzML")],
        "addendum": _add(
            "feature_extraction", ["BSA1_F1.mzML"],
            "Run the feature detection on the provided real LC-MS mzML (centroided "
            "BSA digest fraction, 286 MS1 scans) with the spec's pinned command.",
            "same detection rules as the spec; expect more chemical noise and "
            "isotope events than the synthetic mix",
            "feature count and the top features by intensity (m/z, RT, intensity).",
        ),
    },
    "mass_stats": {
        "prompt": _p("mass_stats", "minimal_differential_stats_prompt.md"),
        "data_files": [_d("mass_stats", "quant_mtbls14397_pos.csv"),
                       _d("mass_stats", "groups.tsv")],
        "addendum": _add(
            "mass_stats", ["quant_mtbls14397_pos.csv", "groups.tsv"],
            "Run the differential statistics on the provided real quantification "
            "matrix (618 named metabolites × 6 samples, raw peak areas) and group "
            "labels with the spec's pinned command.",
            "same statistics (Welch t, fold change, FDR) as the spec; the tool "
            "log2-transforms the raw areas itself per the spec",
            "the top differential features with t, p, adjusted p, and log2 fold "
            "change, plus the count of significant features at the spec's "
            "threshold.",
        ),
    },
}
