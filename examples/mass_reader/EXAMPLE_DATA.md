# Example data & expected results — mass_reader

**Dataset:** two small real mzML exports + one real FASTA (`data/mass_reader/`):
`bsa_orbitrap_first40.mzML` (Thermo Orbitrap BSA QC run, 10 MS1 + 30 MS2, centroided,
uncompressed, RT in seconds), `thermo_small_raw.mzML` (pwiz-converted Thermo `small.RAW`,
2 profile MS1 scans, zlib-compressed 32-bit arrays, RT in minutes — exercises compression,
bit-width, and unit handling), `ecoli_k12_48.fasta` (48 reviewed E. coli K-12 entries).
Provenance and licenses: `data/mass_reader/README.md`.

**Run:** the readers' pinned CLI on all three files.

**Expected results (pyteomics 5.0.1 reference — recipe in the data README):**

| file | scans | TIC | RT range (s) | precursors | charges |
|---|---|---|---|---|---|
| bsa_orbitrap_first40 | 40 (10 MS1 / 30 MS2) | 45,709,750.399 | 1501.414–1590.187 | 30 | {2, 3} |
| thermo_small_raw | 2 MS1 | 138,763,684.238 | 0.2961 / 0.3561 | 0 | — |

FASTA: 48 entries, 19,929 residues, first id `sp|P00509|AAT_ECOLI`.

**Observed local-LLM run** (2026-08-26, Ornith-1.5-35B-A3B via pi; cell
`bench/runs/mass_reader/local/tierc/`, 32 iterations): every value matches the reference to the
last printed digit — BSA 40 scans (10/30), TIC 45,709,750.40, RT 1501.41–1590.19 s, 30
precursors {2:17, 3:13}; Thermo 2 MS1, TIC 138,763,684.24, RT 0.2961/0.3561 s (minutes→seconds
handled); FASTA 48 / 19,929 / `sp|P00509|AAT_ECOLI` — **PASS**, exact.
