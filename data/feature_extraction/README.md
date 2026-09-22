# Feature-extraction validation data (tier c)

## Source

`share/OpenMS/examples/FRACTIONS/BSA1_F1.mzML` from the **OpenMS** repository — the fractionated BSA-digest example set shipped with OpenMS. Real measured LC-MS/MS data of a bovine serum albumin digest (fraction 1), acquired on a Thermo **LTQ Orbitrap XL** with nanoelectrospray (mzML softwareList records the provenance chain: Xcalibur 2.4 SP1 → ProteoWizard 1.6.0 FileFilter/PeakPicker/FileMerger → OpenMS FileConverter).

- Pinned raw file (commit-pinned, immutable):
  https://raw.githubusercontent.com/OpenMS/OpenMS/cd1a3fa006abca35ab23b8d754c5cca44ed40e76/share/OpenMS/examples/FRACTIONS/BSA1_F1.mzML
- Same file on the moving `develop` branch:
  https://github.com/OpenMS/OpenMS/blob/develop/share/OpenMS/examples/FRACTIONS/BSA1_F1.mzML
- Path added in OpenMS PR #2643 (2017-06-12), last modified in commit `cd1a3fa0` (2020-08-10).
- Download date: 2026-08-26. SHA-256 `c3eb9b13f423d89997d14ca68470951026a387afa3959b7dd1c59ceb9c16b2f4`.
- License: OpenMS is released under a **three-clause BSD license** (see the `LICENSE` file at the repository root); redistribution of this file with the license notice is permitted. Freely downloadable, no registration.

## Contents

- `BSA1_F1.mzML` — one LC-MS(/MS) run, 5,788,763 bytes (5.6 MiB). mzML 1.1.0 (indexed).
  - 767 spectra = **286 MS1** + 481 MS2 (DDA). The tool under test must keep `ms_level == 1` only.
  - MS1 RT range **1501.41–1998.99 s** (25.02–33.32 min), median MS1 cycle time **1.66 s**.
  - FTMS full scans, positive mode, scan window 300–2000 m/z (observed centroid sticks 300.03–799.83).
  - **Centroided** (cvParam `centroid spectrum`, MS:1000127); binary arrays are 64-bit floats, **no compression** (plain base64 — decodable by a stdlib-only reader).
  - 140,055 MS1 centroid sticks total; stick intensities 5.9e2–1.2e7.
- `reference_features.py` — the reference analysis script (see recipe below).

## Expected results

### Reference method (exact recipe)

Documented coarse reference for MS1 feature detection, implemented in `reference_features.py` (scratch environment: Python 3.14, pyteomics 5.0.1, numpy 2.5.2):

1. Keep MS1 scans only; one RT slice per MS1 scan (the file's native 1.66 s cycle — finer 0.5–1 s binning would only insert empty slices).
2. Cluster all centroid sticks sorted by m/z into windows: greedy — join the previous window if `|mz − running window mean| ≤ 0.01` and that window has no stick from the same scan, else start a new window. Keep windows seen in ≥ 5 distinct scans.
3. Take the **top K = 200 windows by maximum stick intensity**.
4. Per window build the extracted-ion chromatogram over the 286 MS1 scans (intensity 0 for scans without a stick in the window).
5. Robust noise threshold per window: `T = median(x) + 5·MAD(x)` with median/MAD over the window's **observed (nonzero)** intensities (absent scans are structural zeros; including them drives MAD to 0).
6. Chromatographic peak event = maximal run of consecutive scans with `x ≥ T`, merging single-scan dips below T; count the run if it spans ≥ 3 scans (~5 s). Apex = max-intensity scan in the run; event m/z = intensity-weighted mean of the window's sticks over the run; event RT = apex scan start time.
7. Reference feature count N = total events over the 200 windows.

### Reference results on `BSA1_F1.mzML`

- 2,733 windows pass the ≥ 5-scan filter; 161 of the top 200 windows yield ≥ 1 event.
- **N = 240 features** (RT × m/z peak events) found by the documented reference method.
- Event width median 6 scans (~10 s), range 3–46 scans.
- Top 10 events by apex intensity:

| rank | m/z | RT apex (s) | apex intensity | width (scans) |
| --- | --- | --- | --- | --- |
| 1 | 395.2392 | 1943.80 | 1.13e7 | 7 |
| 2 | 487.7323 | 1848.68 | 6.20e6 | 14 |
| 3 | 395.7405 | 1941.74 | 5.05e6 | 10 |
| 4 | 325.4912 | 1850.10 | 3.97e6 | 10 |
| 5 | 488.2334 | 1848.68 | 3.29e6 | 14 |
| 6 | 388.2539 | 1977.38 | 3.24e6 | 24 |
| 7 | 443.7112 | 1749.73 | 2.79e6 | 16 |
| 8 | 722.3250 | 1788.01 | 2.35e6 | 18 |
| 9 | 738.3110 | 1900.27 | 2.31e6 | 16 |
| 10 | 344.2280 | 1827.04 | 2.31e6 | 31 |

(Ranks 1/3 and 2/5 are +1/+2 isotope events of the same analytes — Δm/z ≈ 0.501, i.e. z = 2 — so a tool that emits one monoisotopic feature per isotope group can match at most 8 of these 10.)

### Consistency bounds (tier c for feature detection is deliberately qualitative)

The tool under test (`python3 features.py BSA1_F1.mzML -o features.tsv` on this file) counts as **consistent** if:

1. its feature (or trace-level peak) count is within a factor of ~2 of 240 (i.e. 120–480), and
2. at least 50% of the reference top-10 events above are matched by a tool feature at `|Δm/z| ≤ 0.01` and `|ΔRT| ≤ 10 s`.

Parameter sensitivity of the reference (varied K ∈ {100, 300}, k ∈ {4, 6}: N ranges 121–364) stays inside the factor-2 band, so the bound is robust to reasonable recipe choices. Intensities are compared by rank only (tool areas vs reference apex intensities are not directly commensurable).

## How obtained

```sh
curl -sL "https://raw.githubusercontent.com/OpenMS/OpenMS/cd1a3fa006abca35ab23b8d754c5cca44ed40e76/share/OpenMS/examples/FRACTIONS/BSA1_F1.mzML" -o BSA1_F1.mzML
shasum -a 256 BSA1_F1.mzML   # c3eb9b13f423d89997d14ca68470951026a387afa3959b7dd1c59ceb9c16b2f4
```

Candidates screened before choosing this file (all from the OpenMS repo tree, searched via the GitHub API): `doc/pyopenms/src/data/Metabolomics_1.mzML` (8.5 MB, sample provenance unclear), `share/OpenMS/examples/LCMS-centroided.mzML` (212 KB but no explicit centroid cvParam and only 112 scans), and the pyteomics fixture `tests/test.mzML` (real but only 2 spectra). `BSA1_F1.mzML` was chosen: known-standard sample (BSA digest), explicit centroided flag, 286 MS1 scans spanning 8.3 min of real peptide elution, uncompressed 64-bit arrays, and well under 10 MB. Reference numbers were produced with `reference_features.py` in a scratch venv (no LLM calls).
