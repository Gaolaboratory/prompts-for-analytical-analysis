# data/chrom — real UV chromatogram for tier (c), `chrom_integration`

## Source

- **File:** `dad1.uv` — binary Agilent ChemStation DAD (UV) chromatogram, file-format
  version `131_LC`.
- **Repository:** ethanbass/chromConverter (R package, used here as format documentation
  and as the source of the file, not run — no R available on this machine).
- **Repo path:** `tests/testthat/testdata/dad1.uv`
- **Raw URL:** https://raw.githubusercontent.com/ethanbass/chromConverter/master/tests/testthat/testdata/dad1.uv
- **Downloaded:** 2026-08-26 (528,074 bytes).
- **License:** GPL-3 (`LICENSE.md` in the repo root). The parser ported below is GPL-3
  software (chromConverter by Ethan Bass, itself adapted from the `rainbow` Agilent .uv
  parser by Evan Shi); this use is format study + a small derived parser, kept alongside
  the data for provenance.
- **Sample metadata** (from chromConverter's own tests for this file,
  `tests/testthat/test-read_chroms.R`): sample `las_bulk_hexE`, operator "Ethan",
  detector Agilent G1315A DAD, vial 24, detector y-unit mAU.
- **No vendor integration report is published for this file**, so the reference is the
  harness-side analysis below, not a vendor peak table.

## Contents

`chrom.csv` — the tool input (what gets copied into the agent's workspace):

- Columns: `time_s,signal` — time in **seconds**, signal in **mAU** at **220 nm**.
- 1,944 points, t = 0.12 … 777.32 s, **uniform 0.4 s** sampling interval (12.96 min run).
- Baseline ≈ −4.8 mAU (offset negative), global max 804.1 mAU at 424.92 s.

Other files (not tool inputs, kept for provenance/reproducibility):

- `dad1.uv` — original binary, as downloaded.
- `dad1_ref.csv` — the repo's own ChemStation CSV export of the **220 nm channel** of the
  same run (`tests/testthat/testdata/dad1.csv`), used to validate the parser exactly.
- `parse_dad1_uv.py` — the converter (see *How obtained*).
- `analyze_chrom.py` — the frozen harness-side reference analysis (see *Expected results*).

## Expected results (harness-side reference — judge the LLM run against THIS)

Method (frozen, implemented verbatim in `analyze_chrom.py`): baseline = median of first
100 raw points; robust sd = 1.4826·MAD of the first 100 raw points; 5-point centered
moving-average smoothing; peak = local maximum with `sm[i] > sm[i-1] and sm[i] >= sm[i+1]
and sm[i] > baseline + 10·sd`; maxima within 5 points grouped into one peak (tallest wins).

- **Baseline** = −4.797 mAU; robust sd = 0.615 mAU; detection threshold = +1.357 mAU.
  (First ~5 min of the run is flat: nothing above baseline + 3·sd before t = 320 s.)
- **N = 10 peaks**, apex times (and raw heights):

| # | apex (s) | apex (min) | height (mAU) | above baseline | note |
|---|----------|------------|--------------|----------------|------|
| 1 | 325.32 | 5.422 | 174.30 | +179.1 | major, symmetric |
| 2 | 383.32 | 6.389 | 148.19 | +153.0 | major; left flank overlaps peak 1 tail |
| 3 | 424.92 | 7.082 | 804.05 | +808.8 | global max, symmetric |
| 4 | 474.12 | 7.902 | 536.74 | +541.5 | major, symmetric |
| 5 | 518.12 | 8.635 | 298.48 | +303.3 | major, symmetric |
| 6 | 539.72 | 8.995 | 82.44 | +87.2 | resolved (valley 59.7 mAU before it) |
| 7 | 596.12 | 9.935 | 28.04 | +32.8 | minor (~53·sd) on drifting baseline |
| 8 | 637.72 | 10.629 | 26.95 | +31.7 | minor (~52·sd) |
| 9 | 664.52 | 11.075 | 31.86 | +36.7 | minor (~60·sd) |
| 10 | 694.12 | 11.569 | 51.13 | +55.9 | minor (~91·sd) |

**Comparison rule for the LLM tool run** (`python3 chrom_integrate.py chrom.csv --noise 10 110 -o peaks.tsv`):

1. Every reference apex above must appear in `peaks.tsv` with `rt_apex` within **±5 %**
   of the reference time — **in seconds**. A `rt_apex` of 5.4 where 325.3 is expected is
   a minutes-vs-seconds unit error and fails the run (that silent-unit trap is the point
   of this tier).
2. No extra peak may be reported that rises above baseline + 10·sd and that the reference
   method did not find.
3. Peak-count line must report 10 peaks.
4. Qualitative only (USP parameters are convention-sensitive): well-resolved majors
   (1, 3, 4, 5) have half-height front/back symmetry 0.84–1.12 → Tf calls should be
   "symmetric, 0.9–1.3"; peak 2's apparent fronting is tail overlap from peak 1, not
   intrinsic tailing; minor peaks 7–10 ride a baseline that wanders ≈ −7 → +5 mAU, so
   their areas/widths are baseline-model sensitive — judge apex and detection, not width.

## How obtained

R/Rscript are not installed on this machine, so chromConverter could not be run
(route a). Route (b) was used: a minimal Python port of chromConverter's
`read_chemstation_uv` + `decode_uv_delta` (R sources `R/read_chemstation_uv.R`,
`R/agilent_utility_functions.R` at master, retrieved 2026-08-26) — `parse_dad1_uv.py`,
stdlib only. Details:

- Format: version string "131" + file-type code "LC" (byte 348); 1,944 points (BE int32
  at 278); scaling factor 4.76837158203125e-4 = 1000·2⁻²¹ (BE double at 3085); data
  segment at 4096; wavelengths 200–400 nm step 2 (101 channels); per record: 4 bytes
  discard, LE int32 time in ms, 14 bytes discard, then per-channel **delta-coded** LE
  int16 with a single accumulator carried across channels (reset each record), −32768
  sentinel → following LE int32 is absolute.
- Channel: **220 nm** exported — deliberately *not* the first channel (200 nm) — because
  chromConverter's test suite ships a reference export of exactly the 220 nm channel
  (`dad1.csv`) and asserts parser equality with it, which lets this port be validated to
  the same standard as the package's own CI.
- Validation vs `dad1_ref.csv` (1,944 points): max |Δt| = 4.1e-12 s, max |Δy| = 8.0e-13 mAU
  — float-formatting noise only.
- Time rescale: the .uv stores time in ms; chromConverter divides by 60 000 to minutes;
  this export uses **seconds** (ms/1000), as the tool's `time_s` header requires.
- No decimation: 1,944 points ≤ 20 000, sampling already uniform at 0.4 s.
