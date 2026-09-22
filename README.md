# Prompts for Analytical Analysis

Ready-to-use prompts that direct a large language model (any agentic coding model — Claude Code,
pi, Codex, Cursor, …) to **write a small, working analytical-chemistry or mass-spectrometry tool
for you from scratch** — together with the real test data, pinned acceptance criteria, and an
external grader that prove the tool is right.

This release is the second generation of the library. Each tool now ships as one canonical
**`PROMPT.md`** (the "short-prompt track"), points at **real public datasets** (NIST certified
values, MassBank, MetaboLights, published teaching sets) instead of a self-written data
generator, and is validated by a **machine-checkable grader held outside the model** — the model
never grades itself. The first-generation prompts (self-contained, standard-library-only, with
seeded data generators written by the model itself) remain in each example folder as
`minimal_*_prompt.md` and still work.

## How to use a prompt

1. **Open a clean, empty folder** and start an agentic coding session there.
2. **Copy the tool's data file(s)** from `data/<tool>/` into the folder.
3. **Paste `examples/<tool>/PROMPT.md` verbatim** — the whole file, nothing added.
4. The model writes the tool, runs it on the shipped data, and checks its output against the
   acceptance criteria pinned in the prompt.
5. **Do not trust the model's own summary.** Re-run the acceptance criteria yourself (each is a
   command whose expected output is pinned), or use the external graders in `bench/graders/`.
6. Feed the tool your own data in the pinned input format when you are done.

Each prompt allows numpy, pandas, and scipy. Each `data/<tool>/README.md` documents the dataset's
source, license, and conversion; each `examples/<tool>/EXAMPLE_DATA.md` records expected results
and provenance.

## The catalog (twelve tools)

| Folder | Tool the model writes | Analysis function |
|---|---|---|
| `examples/calibration/` | `calibrate.py` | Unweighted OLS calibration with LOD/LOQ, certified against the NIST StRD Norris benchmark to 1e-9 relative |
| `examples/titration/` | `titration.py` | Acid–base titration: derivative equivalence point, p*K*a*, concentration |
| `examples/uvvis_spectrum/` | `uvvis.py` | UV–Vis band analysis: baseline, smoothing, λmax, band count, ε |
| `examples/chrom_integration/` | `chrom_integrate.py` | Chromatographic peak detection, integration, USP suitability parameters |
| `examples/pca_untargeted/` | `pca.py` | Untargeted PCA: filtering, imputation, log2, scores, loadings, variance fractions |
| `examples/mass_stats/` | `stats.py` | Two-condition differential statistics: Welch tests, fold changes, FDR |
| `examples/mass_reader/` | `fasta_reader.py`, `mzml_reader.py` | mzML / MGF / FASTA readers for MS data |
| `examples/feature_extraction/` | `features.py` | MS1 feature detection (centroids, isotope grouping, top-N windows) |
| `examples/database_search/` | `search.py` | DDA peptide database search with target–decoy FDR |
| `examples/formula_finder/` | `formula_finder.py` | Formula assignment from accurate mass + isotope pattern |
| `examples/spectral_library/` | `libsearch.py` | MS/MS spectral-library matching with NO_MATCH thresholding |
| `examples/nmr_1d/` | `nmr.py` | 1D NMR FID processing: apodization, FFT, phasing, peaks, integrals |

## The validation protocol

A tool is not "done" when it runs; it is done when it survives, in this order:

- **Tier (a) — exact agreement.** Reproduce pinned reference values on the shipped file, at
  stated relative tolerances (trueness).
- **Tier (b) — robustness.** Re-run the finished programs on verified, non-uniform perturbations
  of the input (subsets rescaled, peaks injected or removed, labels swapped, scans dropped),
  graded against references recomputed from each perturbed input (ruggedness).
- **Tier (c) — real data.** One public dataset with an accepted answer per tool (specificity).

Three rules hold throughout: **the oracle exists before the prompt is sent** (expected values
come from certified sources or independent reference implementations, never from the model);
**grading is external** (a grader the model has never seen applies the criteria mechanically);
and **every criterion is shown to fail once** — one deliberate mutation per criterion, a negative
control, run as a build gate by the test suite in `bench/tests/`.

## Measured results (this generation)

Full experiment records ship in `results/` (per-cell `meta.json` and `grade.txt` for every
session of every experiment; internal endpoint addresses are redacted to placeholders).

- **Replication, n = 10 sessions per tool** on a locally served ~35B model: **103/112 sessions
  pass every criterion, 92.0% [85.4, 95.7]** (Wilson 95% interval). Non-passing sessions spread
  across five tools — session variance, not a defective specification.
- **Specification ablation** (six tools × five nested prompt levels × ten sessions): no session
  below the output-contract level passes (0/162); adding the output contract moves pooled
  criterion pass rate from 18% to 93%. The under-specified prompt is also the expensive one
  (~3.4× wall clock, ~2.6× tokens pooled).
- **Ambiguity injection**: re-introducing single documented prompt defects under matched
  conditions; a ten-character internal spelling inconsistency takes the calibration tool from
  10/10 to 0/10 sessions while the underlying values stay exactly correct.
- **Robustness (tier b)**: 30/36 programs survive every perturbation; the failures are the
  instructive part (see `bench/tier_b.py` and the manuscript).
- **Head-to-head**: generated calibration code agrees with `scipy.stats.linregress` and the NIST
  certificate to the floating-point floor; generated feature detection vs OpenMS is reported as
  agreement with a documented definitional offset (`bench/exp_d_pair*.py/.json`).
- **Cost**: the whole validated twelve-tool library — failures included — cost 13.5 agent-hours
  and ≈ US$123 at frontier list rates on the local GPU (US$134 per validated tool).

## Repository layout

```
examples/<tool>/   PROMPT.md (canonical), EXAMPLE_DATA.md,
                   ablation/ (nested specification ladder), variants/ (ambiguity injections),
                   minimal_*_prompt.md + TEST_PLAN.md (first generation, kept as archive)
data/<tool>/       real test data with README (source, license, conversion)
bench/             the validation harness: graders/, reference/ implementations,
                   tests/ (206 tests incl. one-mutation-per-criterion gates), tier_b*.py
                   (perturbation sweep), agent_driver.py + run_exp.py (agentic runner),
                   report_exp.py, exp_d_pair*.py, exp_g_cost.py
results/           raw per-cell records for every experiment (exp/...), tier_b_out/
```

Set up the pinned interpreter with `python3 bench/venv_setup.py` (numpy/pandas/scipy), then run
the suite with `cd bench/tests && ../../.venv-bench/bin/python3 -m unittest discover -s . -t .`
(206 tests; the handful that exercise the preserved per-run workspaces — a 443 MB archive not
shipped with this release — skip when that archive is absent).

## Contributing

A merged contribution must include the **prompt and test data and criteria**; expected values
must be verified by execution against an independent source, never copied from a model's output;
and every criterion must be shown to fail once before the prompt is listed. Tools we would most
like to see: ion mobility, DIA and imaging MS, GC×GC, capillary electrophoresis,
electrochemistry, surface analysis.

## Citation

A Tutorial manuscript describing the protocol and measurements is in preparation for
*Analytical Chemistry*; until then, please cite this repository. The first-generation library
and its 48-cell benchmark are described in `AC_BENCHMARK_REPORT.md` at the initial release
commit (`59b9930`).
