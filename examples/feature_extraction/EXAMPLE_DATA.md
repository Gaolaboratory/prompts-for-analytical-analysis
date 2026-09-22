# Example data & expected results — feature_extraction

**Dataset:** a real LC-MS MS1 run of a BSA-digest fraction (Thermo LTQ Orbitrap XL, centroided,
286 MS1 scans, RT 1501–1999 s) — `data/feature_extraction/BSA1_F1.mzML` (5.8 MB). Provenance
(OpenMS examples, BSD-3) and the reference method: `data/feature_extraction/README.md`.

**Run:** `python3 features.py BSA1_F1.mzML -o features.tsv` (spec's pinned command).

**Expected results (harness-side reference: peak events over the top-200 m/z windows, threshold
median+5·MAD — full top-10 table in the data README):** **240 reference feature-events**; the
two consistency anchors are (1) ≥50% of the reference top-10 matched by a tool feature at
|Δm/z| ≤ 0.01 and |ΔRT| ≤ 10 s; (2) total feature count within a factor ~2 of 240 — with the
documented caveat that the reference surveys only the top-200 m/z windows while the tool scans
everything, so anchor (2) undercounts by construction.

**Observed local-LLM run** (2026-08-26, Ornith-1.5-35B-A3B via pi; cell
`bench/runs/feature_extraction/local/tierc/`, 39 iterations): 1,730 features; **9 of 10**
reference top-10 events matched within |Δm/z| ≤ 0.01 / |ΔRT| ≤ 10 s (reference #1 — m/z
395.2392 @ 1943.8 s, apex 1.13e7 — reproduced exactly). Verdict: **PASS on the discriminating
anchor (9/10 ≥ 50%)**; the count anchor (1,730 vs 2×240) fails and is documented as the
reference's coverage limitation, not tool error — the tool reports monoisotopic groups across
all m/z; the reference counts trace events in 200 windows only. Both numbers stated, nothing
hidden.
