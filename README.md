# Prompts for Analytical Analysis

Ready-to-use prompts that direct an LLM (any agentic coding model — Claude Code, pi, Cursor,
Windsurf, Codex, …) to **write a small, working analytical-chemistry or mass-spectrometry tool
for you from scratch**, together with its own deterministic test data and a machine-checkable
list of acceptance criteria.

No libraries beyond the Python standard library are required. Each prompt is a single
self-contained Markdown file: paste it into a fresh session and the model writes the data
generator, the tool, runs both, and verifies its own output against numbers pinned in the
prompt.

## How to use a prompt

1. **Open a clean, empty folder** and start an agentic coding session there
   (e.g. `claude`, `pi`, or your IDE's agent) in that folder.
2. **Paste the prompt file verbatim** — the whole file, nothing added.
3. The model writes two things: a **deterministic test-data generator** (seeded, so the data is
   identical every run) and the **tool itself**, then runs both.
4. **Check the acceptance criteria** at the end of the prompt. They list the exact commands to
   run and the exact numbers a correct tool must produce (e.g. "area = 7822 ± 5%"). If every
   criterion passes, the tool is correct — you never have to trust the model's own summary.
5. Feed the tool your own data in the pinned input format when you are done.

The `TEST_PLAN.md` beside each prompt describes further validation (perturbed data, real
public datasets) if you want to harden a tool before trusting it with real data.

## The prompt catalog

### Standalone analytical-chemistry tools

| Folder | Tool the model writes | Analysis function |
|---|---|---|
| `examples/chrom_integration/` | `chrom_integrate.py` | HPLC/GC chromatogram peak detection and integration with USP system-suitability parameters: resolution Rs, tailing factor Tf, plate count N, signal-to-noise |
| `examples/calibration/` | `calibrate.py` | Quantitation: 1/x²-weighted calibration curve with internal-standard correction, LOD/LOQ (ICH Q2), and back-calculated unknown concentrations with % bias |
| `examples/uvvis_spectrum/` | `uvvis.py` | UV-Vis spectrum processing: baseline correction, Savitzky–Golay smoothing, band picking (λmax), and Beer–Lambert concentration recovery |
| `examples/spectral_library/` | `libsearch.py` | MS/MS spectral library search: cosine-style score with one-to-one ±0.5 Da peak matching, NO_MATCH thresholding, runner-up separation |
| `examples/formula_finder/` | `formula_finder.py` | Elemental-composition assignment from accurate mass plus M+1/M+2 isotope intensities: brute-force enumeration within ppm, isotope-pattern scoring, Hill-order formulae |
| `examples/nmr_1d/` | `nmr_1d.py` | 1D NMR processing from a raw FID: apodization, zero-filling, FFT (std-lib implementation), phasing, peak picking, and relative integration |
| `examples/titration/` | `titration.py` | Acid–base titration curve analysis: equivalence volume by 1st/2nd derivative, pKa at half-equivalence, analyte concentration |
| `examples/pca_untargeted/` | `pca.py` | Untargeted metabolomics PCA: missing-value filtering/imputation, log2, mean-centering, power-iteration PCA with scores, loadings, and variance fractions |

### LC–MS proteomics/metabolomics pipeline (a 4-task series, run in order in one workspace)

| Folder | Tool the model writes | Analysis function |
|---|---|---|
| `examples/mass_reader/` | `readers` | mzML and FASTA file readers (Task 1/4 — upstream of the series) |
| `examples/database_search/` | `search.py` | Minimal DDA database search engine: tryptic digestion, m/z matching, target/decoy FDR (Task 2/4) |
| `examples/feature_extraction/` | `features.py` | MS1 feature detection: centroiding, isotope-grouped feature picking across runs (Task 3/4) |
| `examples/mass_stats/` | `quant_stats.py` | Two-condition differential quantification: Welch tests, fold changes, multiple-testing correction (Task 4/4) |

## Tips

- **Use a fresh session per prompt** in an empty folder — the prompts assume no pre-existing
  files, and each standalone tool is independent.
- The series tasks (1/4 – 4/4) import each other's outputs; run them in order in the **same**
  workspace.
- If a criterion fails, show the failing output to the model and ask it to fix the tool — the
  numbers in the prompt were verified by execution, so a failing criterion means the generated
  code, not the prompt.
- Validated end-to-end (2026-08-24) on two models — a local 35B (Ornith-1.5-35B-A3B) and a
  remote 27B (Qwen3.8-27B) — with external graders: 47/48 runs passed every acceptance
  criterion; the one miss was a model variance, not a prompt defect. Any competent agentic
  coding model should handle these; small local models may occasionally need a rerun.

## Contents

```
examples/<tool>/minimal_<tool>_prompt.md   # the prompt (paste verbatim)
examples/<tool>/TEST_PLAN.md               # validation plan: synthetic, perturbed, real data
```
