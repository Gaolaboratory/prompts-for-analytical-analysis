# mass_stats validation data (tier c) — real two-condition LC-MS feature matrix

## Source

MetaboLights study **MTBLS14397** — "LC-MS-based metabolomic analysis of Vd991 and VdGGCT knockout mutant strains" (*Verticillium dahliae* mycelium, wild-type strain Vd991 vs VdGGCT knockout mutant strain V10498; positive-ion reverse-phase LC-MS).

- Study page: https://www.ebi.ac.uk/metabolights/MTBLS14397
- Study FTP directory (anonymous HTTPS, direct download): https://ftp.ebi.ac.uk/pub/databases/metabolights/studies/public/MTBLS14397/
- Metabolite assignment file used (peak-area abundances, per-sample columns):
  https://ftp.ebi.ac.uk/pub/databases/metabolights/studies/public/MTBLS14397/m_MTBLS14397_LC-MS_positive_reverse-phase_v2_maf.tsv
  (sha256 `1d2a9df3794c9bf4707bded38d04589302681d2e2af3f2cefe2681f0ee44c1da`, 131,838 bytes, 618 features)
- Download date: 2026-08-26
- License: **CC0 1.0 Universal** (`Comment[License]` in `i_Investigation.txt`), no registration required.
- Publication: Li, Su, Mo, Liu, Lu, Li, Zhao, Guo, Ma — "VdGGCT, a GGCT_like super family protein, is required for fungal growth, conidiation and pathogenicity of *Verticillium dahliae*", status **in preparation** (no DOI yet); the data itself is public on MetaboLights (released 2026-05-11), so the accession is the citable identifier.

**Not shared with `data/pca/`**: the PCA tool's matrix (`data/pca/features.csv`, 60 ADG19007u samples, bin features) is a different study. `data/pca/` was empty when sourcing began (2026-08-26 19:32) and had no README when this was written; the PCA matrix also does not fit this prompt's strict two-group `CTRL_*`/`EXP_*` input, so the two tools use different published matrices.

## Contents

| File | What it is |
| --- | --- |
| `quant_mtbls14397_pos.csv` | The pinned-format input for `quant_stats.py`: `feature_id,CTRL_1..CTRL_3,EXP_1..EXP_3`. **618 features × 6 samples**, raw abundance values copied verbatim from the MAF. |
| `groups.tsv` | Pinned column → original sample name, group, genotype, description. `CTRL_*` = wild type Vd991_1..3, `EXP_*` = VdGGCT knockout V10498_1..3 (biological replicates; mycelium). |
| `features_mtbls14397_pos.tsv` | `MET_###` → metabolite_identification, m/z, retention time (min), for interpreting results. |
| `expected_stats.tsv` | Full 618-row harness-side reference (scipy), sorted by p ascending: `feature_id, metabolite_identification, log2FC, t, df, p_value, q_value, significant`. |

Feature IDs `MET_001`–`MET_618` are assigned in MAF row order (MET_001 = Oleamide). No missing values exist in the 6 biological-sample columns, so all 618 features pass the ≥ 3-valid-per-condition filter. The study's 4 QC samples and the negative-ion MAF (418 features) are not included.

## Expected results

Running the pinned pipeline (filter ≥ 3 valid/condition → `log2` transform → Welch t-test, `log2FC = mean(log2 EXP) − mean(log2 CTRL)` → BH across tested → significant iff `q < 0.05` and `|log2FC| ≥ 1`) on `quant_mtbls14397_pos.csv`:

- **Tested: 618; filtered: 0; significant: 253** (253 of 618 features have q < 0.05 and |log2FC| ≥ 1).
- Sign convention: log2FC = knockout − wild type (negative = depleted in the VdGGCT mutant). All top hits are depletions except MET_607.
- Top 10 features by p (reference values, scipy 1.18.1; full precision in `expected_stats.tsv`):

| feature_id | metabolite | log2FC | t | df | p_value | q_value | sig |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MET_235 | 3'-Dephosphocoenzyme A | −7.0798 | −64.2342 | 3.6698 | 9.80969e-07 | 1.26076e-04 | 1 |
| MET_433 | Myrmicacin | −5.6520 | −49.4794 | 3.9402 | 1.18206e-06 | 1.26076e-04 | 1 |
| MET_410 | 2,3-Dinor-8-epi-prostaglandin F2 | −5.5257 | −114.0741 | 3.0338 | 1.30528e-06 | 1.26076e-04 | 1 |
| MET_438 | met-ala | −5.4411 | −69.5918 | 3.4822 | 1.33976e-06 | 1.26076e-04 | 1 |
| MET_594 | 8Z,11Z,14Z-Eicosatrienoic acid | −2.9960 | −52.7617 | 3.8042 | 1.36319e-06 | 1.26076e-04 | 1 |
| MET_283 | 2,3-Dinor-11-prostaglandin F2 | −7.7343 | −52.6953 | 3.8024 | 1.37609e-06 | 1.26076e-04 | 1 |
| MET_173 | S-Adenosylmethionine | −1.2126 | −67.6306 | 3.4917 | 1.43563e-06 | 1.26076e-04 | 1 |
| MET_186 | L-Kynurenine | −3.1631 | −53.9916 | 3.7011 | 1.69095e-06 | 1.26076e-04 | 1 |
| MET_607 | (5S)-5-Butyl-5-ethyldihydro-2(3H)-furanone | +3.6086 | +58.5578 | 3.5755 | 1.83606e-06 | 1.26076e-04 | 1 |
| MET_498 | TCS 2510 | −4.8946 | −41.3853 | 3.9935 | 2.07271e-06 | 1.27309e-04 | 1 |

Null end of the list: MET_266 has the largest p (p = q = 0.9961). Least-extreme log2FC among tested ≈ 0.

**Tolerances** (tool vs `expected_stats.tsv`):

- `t` and `p_value`: within **1e-6 relative** (reference uses `scipy.stats.ttest_ind(equal_var=False)` on log2 values; scipy's p agrees with the prompt's own `betai(df/2, 1/2, df/(df+t²))` to ≤ 2.2e-14 relative over all 618 features, so the two implementations are interchangeable at this tolerance).
- `df`: Welch–Satterthwaite, fractional (here 3.03–4.00); within 1e-6 relative.
- `q_value`: within 1e-6 relative, and **identical q ordering**. Note the top 8 features sit on a BH plateau — exactly tied at q = 1.2607615866e-04 (the monotone sweep from the largest rank down); a correct implementation must reproduce that plateau, with ties ordered by p ascending.
- `log2FC`: within 1e-9 relative (tool parses the same CSV strings, so agreement should be at double-precision level).
- Calls: exactly 253 features with `significant = 1`; nothing at the null end (e.g. MET_266) may be called.

## How obtained

Downloaded with `curl -sL` from the MetaboLights public FTP (URLs above) on 2026-08-26 into a scratch directory; no authentication. The four biological-replicate-group columns were extracted from the positive-mode MAF and written verbatim — **no log transform, no normalization, no imputation, no rounding was applied harness-side** (the prompt's pinned pipeline performs the log2 transform itself, so the CSV carries raw linear peak areas). `MET_###` ids were assigned in MAF row order.

Reference statistics were computed harness-side in a scratch venv (Python 3.14.6, scipy 1.18.1, statsmodels 0.14.x) by re-reading the *shipped* CSV and applying the pinned pipeline exactly: `numpy.log2`, `scipy.stats.ttest_ind(equal_var=False)`, hand-computed Welch–Satterthwaite df, and BH q-values per the prompt's algorithm (ranks from 1, monotone sweep from the largest rank down, capped at 1, m = 618 tested) cross-checked against `statsmodels.stats.multitest.multipletests(method="fdr_bh")` (max relative difference 2.5e-16) and against the prompt's own incomplete-beta p implementation (max relative difference 2.2e-14).

Local checksums (sha256): `quant_mtbls14397_pos.csv` f519f880405814918ee33c9970d3cdaec79fc83446aca3c599e30ca343e28d5a · `expected_stats.tsv` 19a23033498dfd67c5bbb232e91fdf18333f11e16a885f04b36b7ede86cb03ed · `groups.tsv` 5e24d7aae31b32b99f29c485fe681c2a26c46c3b41ce1e0d29d154473434390d · `features_mtbls14397_pos.tsv` d7c11e126977e4c5cc97f37c1d5cc161ce7b3b82e913b7beff7f6b4980d2386f.
