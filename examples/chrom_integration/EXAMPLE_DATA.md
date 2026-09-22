# Example data & expected results — chrom_integration

**Dataset:** a real Agilent ChemStation DAD chromatogram (UV 220 nm channel of
`dad1.uv` from the chromConverter test data), converted to the tool's CSV format
(`data/chrom/chrom.csv`, 1,944 points at 0.4 s over 0–777 s). The conversion — a std-lib port of
chromConverter's decoder — is validated to max|Δ| ≈ 1e-12 against the repo's own reference
export; converter, raw file, and validation script ship alongside. Provenance and license:
`data/chrom/README.md`.

**Run:** `python3 chrom_integrate.py chrom.csv --noise 0 70 -o peaks.tsv` (noise region =
peak-free start of the run).

**Expected results (harness-side reference analysis, `data/chrom/analyze_chrom.py`):** **10
peaks**, apexes 325.32, 383.32, 424.92, 474.12, 518.12, 539.72, 596.12, 637.72, 664.52, 694.12 s
(grading: apex match ±5% in seconds, count = 10, no extra detections). Global max 804.1 mAU at
424.92 s; baseline wanders −7→+5 mAU (a real-data stress the synthetic generator does not have).

**Observed local-LLM run** (2026-08-26, Ornith-1.5-35B-A3B via pi; cell
`bench/runs/chrom/local/tierc/`, 19 iterations): exactly 10 peaks, apexes 324.92, 383.32, 424.92,
474.12, 518.12, 540.52, 596.12, 636.92, 663.32, 694.52 s — **PASS**, every apex within 0.2% of
the reference (worst 1.2 s), no spurious detections, on a real drifting-negative baseline.
