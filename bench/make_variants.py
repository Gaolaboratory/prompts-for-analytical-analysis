#!/usr/bin/env python3
"""Build Experiment B's ambiguity variants from each shipped PROMPT.md.

Each variant re-introduces EXACTLY ONE documented ambiguity into the hardened
prompt, as a minimal textual edit. Every edit is declared here as an explicit
(find, replace) pair and asserted to match exactly once, so a variant can never
silently become a no-op when a prompt is revised -- which is the failure mode
that would quietly turn this experiment into a measurement of nothing.

Why these ten. Each reproduces a defect that the p3 sweep, the short-prompt
pilot or the Phase-0 baseline actually found by measurement, and that was then
fixed by editing the prompt. Experiment B asks what each fix was worth, under
conditions identical in every other respect -- which the historical before/after
comparisons cannot answer, because model, grader and calendar all moved between
them.

The `expected` field is a pre-registered prediction, written before the runs,
and `silent` records whether the resulting failure is expected to look like
success: a program that runs, emits well-formed output, and is wrong. The
silent/loud split is the finding; the effect sizes are the evidence.
"""
import hashlib, json, os, sys

BENCH = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BENCH)
sys.path.insert(0, BENCH)
from specs import SPECS

V = []


def variant(vid, tool, source, silent, expected, edits):
    V.append({"id": vid, "tool": tool, "source": source, "silent": silent,
              "expected": expected, "edits": edits})


# ---------------------------------------------------------------- dda_s
variant("amb-yion", "dda_s",
        "Phase-0 baseline: 5 of 6 sessions built the y series as a mirror of b",
        silent=True,
        expected="suffix loses the C-terminal residue; the broken engine matches MORE "
                 "fragments at +/-0.5 Da, so every summary statistic looks better",
        edits=[("""   **`b_i` is the first `i` residues; `y_i` is the last `i` residues.** They are
   independent series, not one loop run in reverse. For `QISFVK`: `b1` is `Q` alone
   (129.0659) and `y1` is `K` alone (147.1128) — `y1` **must include the C-terminal
   residue**. Writing the y loop as a mirror image of the b loop drops that residue and
   shifts the entire y series. That bug still produces plausible-looking output: the
   wrong series matches *more* fragments by chance at ±0.5 Da, which makes every
   summary statistic look *better* (fewer decoys, more accepted PSMs) while every
   number is wrong. Print this table and compare before you search:

   ```
   b1..b5  129.0659  242.1499  329.1819  476.2504  575.3188
   y1..y5  147.1128  246.1812  393.2496  480.2817  593.3657
   ```

""", "")])

variant("amb-units", "dda_s",
        "p3 sweep 2026-09-11: two cells reported protein counts, 3,260 vs a reference of 87,060",
        silent=False,
        expected="targets/decoys reported as protein counts; criterion 2 fails",
        edits=[("""`targets`/`decoys` count **peptides indexed after digestion** (the entries in step 4's
mass-sorted index) — not proteins. Same numbers as "peptides indexed: N target, N decoy"
if you print that elsewhere.
""", "")])

variant("amb-encode", "dda_s",
        "p3 sweep 2026-09-11: a submission wrote True/False and the grader discarded every row",
        silent=False,
        expected="decoy emitted as True/False; the structural criterion fails",
        edits=[("""`decoy` is the literal digit `1` or `0` (never `True`/`False`) — 1 if the row's protein
starts with `DECOY_`, else 0.""",
                """`decoy` indicates whether the row's protein starts with `DECOY_`.""")])

variant("amb-criteria-only", "dda_s",
        "Phase-0 baseline: 6 of 6 sessions missed a requirement that lived only in the criteria",
        silent=False,
        expected="the unfiltered control run is never performed; criterion 5 fails. The "
                 "requirement still appears verbatim in the acceptance criteria, which is "
                 "the whole point",
        edits=[("""9. **Run the whole search a second time with peak filtering switched off** (step 6
   skipped, every peak kept), and report that run's target count at `q ≤ 0.01` on
   stdout as `psms_1pct_unfiltered`, next to `psms_1pct` from the peak-filtered run.
   `psms.tsv` holds only rows from the peak-filtered run (steps 1–8); this
   no-peak-filter rerun contributes just its stdout count, never rows to `psms.tsv`.
   This is not a diagnostic afterthought — it is the only evidence that your
   peak-filtering step does anything, and criterion 5 below grades it directly.
   Actually run this second search and print its number; do not wire up a flag for it
   and leave the flag unused.
""", "")])

# ------------------------------------------------------------------ pca_s
variant("amb-orient", "pca_s",
        "short-prompt pilot 2026-09-02: local 1/3 before the transpose bullet, 3/3 after",
        silent=True,
        expected="the wrong Gram matrix is decomposed; variance fractions stay exactly "
                 "correct because X^T X and X X^T share eigenvalues, so the program "
                 "projects into the wrong space with perfect summary statistics",
        edits=[("""- `features.csv` loads with features as rows and samples as columns: transpose it so each
  row is a sample before centering, giving the 60 × (kept features) matrix PCA needs.
  Skipping the transpose still yields correct variance fractions, so a plausible result is not evidence the orientation is right.
""", "")])

# ----------------------------------------------------------- calibration_s
variant("amb-spell", "calibration_s",
        "p3 sweep 2026-09-04: two quantities spelled two ways; the model followed the "
        "more internally consistent half",
        silent=False,
        expected="the model uses one spelling consistently and fails whichever criterion "
                 "names the other",
        edits=[("One line on stdout: `n=<n> slope=<x> intercept=<x> residual_sd=<x> "
                "r_squared=<x> lod=<x> loq=<x>`",
                "One line on stdout: `n=<n> slope=<x> intercept=<x> resid_sd=<x> "
                "r2=<x> lod=<x> loq=<x>`")])

variant("amb-sigfig", "calibration_s",
        "p3 sweep 2026-09-04: 9 significant figures permitted against a 1e-9 relative grader",
        silent=False,
        expected="slope (leading digit 1) fails the 1e-9 check at ~2e-9 while intercept, "
                 "residual_sd and r_squared pass at the same printed precision -- the "
                 "resolution of a significant figure depends on the leading digit",
        edits=[("""- Print slope, intercept, residual_sd and r_squared to at least 12 significant figures:
  the 1e-9 relative tolerance below needs more precision than 9 significant figures
  reliably gives, since a value's last printed digit is coarser or finer depending on
  its leading digit.""",
                """- Print slope, intercept, residual_sd and r_squared to at least 9 significant figures.""")])

# ------------------------------------------------------------ mass_stats_s
variant("amb-stream", "mass_stats_s",
        "tutorial §7: 'print' with the stream unstated; the model printed to stderr",
        silent=False,
        expected="counts go to stderr; every stdout criterion fails while the statistics "
                 "are correct",
        edits=[("One line on stdout: `tested=<n> filtered=<n> significant=<n>`.",
                "Print the counts: `tested=<n> filtered=<n> significant=<n>`.")])

variant("amb-sep", "mass_stats_s",
        "tutorial §7: a tab-delimited header was displayed but never stated; the model emitted CSV",
        silent=False,
        expected="CSV emitted despite the header block showing tabs -- showing a format is "
                 "not specifying it",
        edits=[("`stats.tsv`, tab-separated, one row per **tested** feature, sorted by ascending `p_value`:",
                "`stats.tsv`, one row per **tested** feature, sorted by ascending `p_value`:")])

# --------------------------------------------------------------- formula_s
variant("amb-window", "formula_s",
        "p3 sweep 2026-09-12: a run ignored the ppm window and emitted 6,495,441 candidates "
        "against a reference of 35, on 508 MB of disk, and still scored 6/6",
        silent=True,
        expected="unbounded enumeration; rank-1 rows can still sort out correctly, so the "
                 "failure is invisible to any criterion that does not compare the candidate "
                 "count to a reference",
        edits=[("""- **Enumeration.** Brute force over C 0–30, H 0–60, N 0–10, O 0–10, P 0–2, S 0–2 —
  zero counts allowed — keeping candidates with `|calc_mass − measured| ≤ 5 ppm`, an
  **inclusive** window at both ends (a candidate at exactly 5.000 ppm is kept). No
  valence, DBE, or nitrogen-rule filtering: the candidate count is set by the limits and
  the window alone.""",
                """- **Enumeration.** Brute force over C 0–30, H 0–60, N 0–10, O 0–10, P 0–2, S 0–2 —
  zero counts allowed. No valence, DBE, or nitrogen-rule filtering.""")])


def main():
    wanted = set(sys.argv[1:])
    manifest = {}
    for v in V:
        if wanted and v["id"] not in wanted:
            continue
        src = SPECS[v["tool"]]["prompt"]
        text = open(src).read()
        out = text
        for find, replace in v["edits"]:
            n = out.count(find)
            if n != 1:
                raise SystemExit("variant %s: edit matches %d times in %s (need exactly 1).\n"
                                 "The prompt has changed under this variant; re-derive the edit."
                                 % (v["id"], n, os.path.relpath(src, REPO)))
            out = out.replace(find, replace)
        if out == text:
            raise SystemExit("variant %s is a no-op" % v["id"])
        outdir = os.path.join(os.path.dirname(src), "variants")
        os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, v["id"] + ".md")
        open(path, "w").write(out)
        manifest[v["id"]] = {
            "tool": v["tool"], "path": os.path.relpath(path, REPO),
            "base_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "variant_sha256": hashlib.sha256(out.encode()).hexdigest(),
            "chars_removed": len(text) - len(out),
            "source": v["source"], "silent_expected": v["silent"],
            "expected": v["expected"],
        }
        print("%-20s %-14s %+6d chars  %s"
              % (v["id"], v["tool"], len(out) - len(text),
                 "SILENT" if v["silent"] else "loud"))
    path = os.path.join(BENCH, "variants_manifest.json")
    json.dump(manifest, open(path, "w"), indent=1)
    print("\n%d variants -> %s" % (len(manifest), os.path.relpath(path, REPO)))


if __name__ == "__main__":
    main()
