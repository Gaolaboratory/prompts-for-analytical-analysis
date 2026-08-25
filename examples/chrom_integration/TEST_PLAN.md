# TEST PLAN — chrom_integration (peak integration + USP QC)

**Tier (a) executed 2026-08-24:** 8/8 criteria × 3 reps × 2 models (local Ornith-1.5-35B-A3B, remote
Qwen3.8-27B), external grader via the pi harness — see `/AC_BENCHMARK_REPORT.md`. Tiers (b)/(c)
remain plans. The oracle numbers quoted
below were produced by running a reference implementation during prompt authoring
(`make_chrom_data.py` + a reference `chrom_integrate.py`, seed 20260824); they are the grading
targets, not benchmark results.

## Tier (a) — exact synthetic

Commands, in a clean workspace containing only the prompt:

```
python3 make_chrom_data.py                                      # writes chrom.csv (300 pts, 1 s)
python3 chrom_integrate.py chrom.csv --noise 0 25 -o peaks.tsv
python3 grade_chrom.py peaks.tsv stdout.log                     # external grader, see below
```

The agent's run must also pass the in-prompt triangle self-check
(t = 0..4, y = [0,1,2,1,0] → area 4.000, height 2.000, Tf 1.000, N 4.000) — capture its stdout.

**External grader sketch (`grade_chrom.py`, std-lib only, ~80 lines).** Grading is never the
agent's self-report (tutorial.md §3); this script is written and held by the benchmark harness:

1. Parse `peaks.tsv`: split each line on `\t`; assert header equals the pinned 11-column string
   exactly; assert 3 data rows; assert rows sorted by `rt_apex` ascending; assert
   `rs_to_previous == "-"` in row 1; assert all other numeric fields parse as floats.
2. Assert captured stdout contains the line `peaks detected: 3` (stdout, not stderr — capture
   the streams separately) and a noise line with `n=26`, `mean` 51.076 ± 0.001, `sd` 4.291 ± 0.001.
3. Per-criterion numeric checks against the oracle (peak 1 / 2 / 3):
   - `rt_apex` 60.0 / 150.0 / 244.0, ±1.0
   - `area` 7821.509 / 14920.273 / 12032.407, ±5%
   - `height` 786.254 / 1198.618 / 725.128, ±5%
   - `tf` 0.993 / 0.988 (±0.10, must lie in [0.9, 1.1]) / 1.339 (±0.10, must exceed 1.2)
   - `N` 100.000 / 330.579 / 314.901, ±15%
   - `rs_to_previous` − / 3.158 / 2.136, ±0.15
   - `sn` 183.245 / 279.350 / 168.999, ±10%
4. Emit one PASS/FAIL line per acceptance criterion and a final score `k/8`; exit non-zero unless
   all pass.

Optional reproducibility check: run the generator twice and diff `chrom.csv` (byte-identical on the
same machine; cross-machine last-digit drift from platform libm `exp`/`cos` is acceptable — grade
parsed values, not checksums).

## Tier (b) — robustness (perturb the generator, re-grade)

Change one knob at a time in `make_chrom_data.py`, regenerate, re-run tool + grader; re-derive the
oracle for each variant with the reference implementation **before** grading.

| Perturbation | Knob | Must still hold |
|---|---|---|
| High noise | `NOISE_SD` 5 → 15 | 3 peaks; apex ±1 s; area ±10%; `tf` ordering (peak 3 > 1.2, peaks 1–2 in 0.85–1.15) |
| Steep drift | baseline slope 0.10 → 0.50 | 3 peaks; area ±10%; peak 3 still detected (`sn` > 10) |
| Missing peak | drop `(150.0, 5.0, 1200.0)` | exactly 2 peaks, correct apexes; `rs_to_previous` of the EMG peak now spans the gap |
| Extra shoulder | add `(165.0, 3.0, 500.0)` | valley rule resolves or merges per spec — record behavior, check peak count matches the pinned rule's prediction |
| Dense sampling | 300 → 600 points over the same 300 s (0.5 s spacing) | apexes ±0.5 s; areas halve per-sample (±5% after scaling); smoothing window is in *samples*, so document the expected bound change and re-derive the oracle |
| Sparse sampling | 300 → 150 points (2 s spacing) | 3 peaks; apex ±2 s; `N` and `Tf` within ±25% (interpolated 5% crossings coarsen) |

## Tier (c) — real data

- **Source:** a real vendor chromatogram shipped as parser test data in the chromConverter
  repository — Agilent ChemStation UV trace `dad1.uv`:
  https://github.com/ethanbass/chromConverter (`tests/testthat/testdata/dad1.uv`, raw file at
  `https://raw.githubusercontent.com/ethanbass/chromConverter/master/tests/testthat/testdata/dad1.uv`;
  verified reachable 2026-08-24). It is a binary vendor file, so convert to `time,signal` CSV first
  with chromConverter/R, Entab, or rainbow — the conversion step is part of the tier, not part of
  the graded tool.
- **Reference answer:** the vendor Agilent ChemStation integration report for the same file where
  available, or the established open integrator `chromatographR::get_peaks()` on the converted
  trace. Compare peak count, apex RTs (±1%), and relative area percentages (±5% relative);
  USP parameters are convention-sensitive (baseline model, width definition), so compare Rs/Tf/N
  only qualitatively (same ordering, same tailing calls). Any silent unit conversion (minutes vs
  seconds) must be caught here — that is the point of the tier.

## Benchmark protocol

1. Run the prompt in a **fresh agentic coding session in a clean workspace** (no pre-existing
   `chrom_integrate.py`, no reference implementation present). Paste the prompt verbatim.
2. Record: model name + version, full prompt text and its hash (SHA-256), generated code hash,
   iteration count (agent turns / tool calls), wall-clock time, and per-criterion PASS/FAIL from
   `grade_chrom.py` — never the agent's own summary table.
3. Require **cross-model reproduction**: at least one frontier API model and one local model
   (record parameter count, quant, context size); report failures per model rather than dropping
   them — a capability floor is a property of the model, not the task (tutorial.md §6.1–6.2).
4. Context budget: the prompt is ~7.5 KB / 119 lines — it must fit, with room for agentic
   iteration, in the context of the smallest model claimed (tutorial.md §9). State that model.
5. Keep the generator and grader outside the agent's reach: the agent gets the prompt only; the
   harness holds `grade_chrom.py` and the tier (b)/(c) variants.
