# Tier (c) real data — pca_untargeted

## Source

- **Study**: MetaboLights **MTBLS1** — "A metabolomic study of urinary changes in type 2
  diabetes in human compared to the control group" (human urine, 1H-NMR untargeted).
  Study page: https://www.ebi.ac.uk/metabolights/MTBLS1
- **Publication**: Salek RM, Maguire ML, Bentley E, Rubtsov DV, Hough T, Cheeseman M,
  Nunez D, Sweatman BC, Haselden JN, Cox RD, Connor SC, Griffin JL.
  *A metabolomic comparison of urinary changes in type 2 diabetes in mouse, rat, and human.*
  Physiol Genomics 31(1):9–19 (2007). DOI 10.1152/physiolgenomics.00194.2006, PMID 17190852.
- **Files used** (downloaded 2026-08-26 from the public FTP-over-HTTP tree
  `http://ftp.ebi.ac.uk/pub/databases/metabolights/studies/public/MTBLS1/`):
  - `m_MTBLS1_metabolite_profiling_NMR_spectroscopy_v2_maf.tsv` — the ISA metabolite
    assignment (bucket) file: 220 NMR spectral buckets (rows) × 132 urine samples
    (columns), bucket intensities. This *is* the study's data matrix; no raw spectra
    were processed. (SHA-256 `a95d4a1c…af797e5`)
  - `s_MTBLS1.txt` — ISA sample file; `Factor Value[Metabolic syndrome]` gives the
    two-group design: 48 `diabetes mellitus` vs 84 `Control Group` samples
    (case/control). The NMR assay file and `i_Investigation.txt` were also checked.
- **License / terms**: EMBL-EBI Terms of Use (dataset license recorded in the study's
  MetaboLights metadata; revision 3, 2025-09-02, "updating data license").
  https://www.ebi.ac.uk/about/terms-of-use/
- No substitution was needed — MTBLS1 (the study named in TEST_PLAN.md tier (c)) was
  fully retrievable per-file.

## Contents

- **`features.csv`** — 200 features × 60 samples, 95 KB. Header
  `feature_id,<60 sample names>`; one feature per row; **empty cell = missing**.
  - feature_id = `b<NNN>_<ppm-range>` (e.g. `b001_0.10-0.14`), derived from the MAF
    `chemical_shift` bucket column; the zero-padded index makes ids unique (32 ppm
    ranges appear twice in the source). Row order = MAF order after subsetting.
  - Units: NMR bucket intensities as published (arbitrary, normalized spectral
    integral per ppm bucket; values ~1e-4 … 21.4, no negatives).
  - Samples: 30 `Control Group` (columns 1–30, sorted) then 30 `diabetes mellitus`
    (columns 31–60, sorted); names are ISA sample names (e.g. `ADG19007u_015`).
  - SHA-256 `10ba0168a48b538c7a967b5c8c5d1859b2d947651fde4476ca2e865cb01ffb2e`
- **`groups.csv`** — header `sample,group`, 60 rows, group values verbatim from the
  ISA factor (`Control Group` / `diabetes mellitus`).
  SHA-256 `13e34e5805c1137f032b63a71330d30b237b77d13b1a4b917bcb48daee3f1bca`
- Missingness: 702 / 12 000 cells empty (5.9%).

## Expected results

Reference computation (method below): **features kept = 184 of 200** — 16 buckets have
< 80% valid values in these 60 samples and must be filtered; all 184 pass the filter,
get row-mean (linear-scale) imputation, log2, per-feature mean-centering, no scaling.

- **PC1 variance fraction = 0.1558**
- **PC2 variance fraction = 0.1008**
- **Separation verdict: OVERLAP on PC1** (the strict `min(group A) > max(group B)`
  criterion is NOT met — this is real-data behavior, unlike the tier (a) synthetic set).
  Control PC1 range [−7.142, 8.912], diabetes range [−6.619, 6.873]; 176/900
  cross-group pairs violate the ordering. A clear directional shift does exist along
  PC1: mean control PC1 = +1.709, mean diabetes PC1 = −1.709 (controls positive after
  the sign rule "first sample's score positive" — first sample is a control).
- Tolerances for grading: variance fractions ± 0.01; score correlation vs reference
  |r| > 0.999 (sign-normalized). Sign flips of PCs are expected and normalized.

## How obtained

Download (harness-side, no LLM): the three ISA files + MAF above via plain HTTP from
the public FTP tree (the `ws/files/studies/public/…` endpoint 404s for this study).

Documented subsetting/preparation (script `/tmp/pca_tierc/prepare.py`, std-lib only,
seed 20260826 — all deterministic):

1. **Samples**: balanced subset — 30 of 84 controls + 30 of 48 diabetics, drawn with
   `random.Random(20260826).sample` from each group's sorted sample list; columns
   ordered controls-then-cases.
2. **Zeros → missing**: the MAF contains exact 0.0 bucket intensities (3187/29 040
   cells in the full matrix, 11%) = below-detection signal; log2 is undefined at 0.
   They are written as **empty cells** so the prompt's own ≥80%-valid filter +
   row-mean imputation machinery handles them (instead of an ad-hoc small-offset
   rule; this is the "preprocessing deviation forced by the real file" recorded in
   TEST_PLAN.md tier (c)). No other value was altered.
3. **Features**: 220 → top **200** by sample variance of valid (non-empty) values
   across the 60 selected samples (linear scale; ties → earlier MAF row).
4. Non-zero cells copied **verbatim** as strings (source precision preserved).

Reference processing recipe (exactly the prompt's pipeline; scratch venv, std-lib csv
+ math, numpy 2.5.2 + scikit-learn 1.9.0; script `/tmp/pca_tierc/reference.py`,
bit-deterministic across reruns):

1. Filter: keep feature if non-empty in ≥ 48 of 60 samples (≥ 80%).
2. Impute each remaining empty cell with the feature's mean over its valid values, in
   the linear scale (before log2). All row means > 0, so log2 is defined everywhere.
3. `log2` every value → matrix X (60 × 184).
4. Subtract per-feature mean over samples; do **not** divide by per-feature SD
   (covariance PCA, not correlation PCA).
5. `sklearn.decomposition.PCA(n_components=2).fit_transform(X)`; variance fraction =
   `explained_variance_ratio_` (= eigenvalue / trace of XᵀX/(n−1)).
   Cross-checked against `numpy.linalg.eigvalsh` on C = XᵀX/(n−1): agreement to 1e-16.
6. Sign rule from the prompt applied: PC flipped (scores and loadings together) so the
   first sample's score is positive (PC1 and PC2).

Std-lib verification of the formatted files: 200×60, no all-empty rows, both groups
present with 30 samples each (≥ 6), every non-empty cell parses as float, no duplicate
feature ids or sample names.
