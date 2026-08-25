# TEST PLAN — pca_untargeted

**Tier (a) executed 2026-08-24:** 15/15 criteria × 3 reps × 2 models (local Ornith-1.5-35B-A3B, remote Qwen3.8-27B), external grader via the pi harness — see `/AC_BENCHMARK_REPORT.md`. Tiers (b)/(c) remain plans. Every oracle number quoted below was produced by a reference implementation executed during prompt authoring (LCG generator + std-lib power iteration, cross-checked against an independent Jacobi eigensolver).

## Tier (a) — exact synthetic

Commands (in a clean workspace containing only the prompt):

```
python3 make_test_data.py                                   # writes features.csv (28 x 10)
python3 pca.py features.csv -o scores.tsv --loadings loadings.tsv > stdout.txt
python3 grade.py                                            # external grader, exits non-zero on failure
```

`grade.py` is a **separate program** (never the agent's self-report) that checks each acceptance criterion of the prompt mechanically:

```python
# sketch: grade.py
import subprocess, sys, math

def close(a, b, tol): return abs(a - b) <= tol

def load_tsv(path):
    lines = open(path).read().splitlines()
    header = lines[0].split("\t")
    rows = [l.split("\t") for l in lines[1:]]
    return header, rows

checks = []
out = open("stdout.txt").read().splitlines()
checks.append(("stdout counts",  out[0] == "kept 27 of 28 features (filtered: MET_X28)"))
checks.append(("stdout PC1",     out[1] == "PC1 variance fraction 0.9218"))
checks.append(("stdout PC2",     out[2] == "PC2 variance fraction 0.0719"))

sh, srows = load_tsv("scores.tsv")
checks.append(("scores header",  sh == ["sample", "PC1", "PC2"]))
checks.append(("scores order",   [r[0] for r in srows] ==
               ["CTRL_%d" % i for i in range(1,6)] + ["EXP_%d" % i for i in range(1,6)]))
pc1 = [float(r[1]) for r in srows]
checks.append(("sign rule",      pc1[0] > 0))
checks.append(("separation",     min(pc1[:5]) > max(pc1[5:])))
checks.append(("CTRL_1 PC1",     close(pc1[0],  3.4354, 0.01)))
checks.append(("EXP_1 PC1",      close(pc1[5], -3.6524, 0.01)))
checks.append(("CTRL_2 PC2",     close(float(srows[1][2]), -1.7934, 0.01)))

lh, lrows = load_tsv("loadings.tsv")
checks.append(("loadings header", lh == ["feature", "PC1", "PC2"]))
checks.append(("loadings rows",   len(lrows) == 27 and "MET_X28" not in [r[0] for r in lrows]))
l1 = {r[0]: float(r[1]) for r in lrows}
l2 = {r[0]: float(r[2]) for r in lrows}
checks.append(("signal loadings", all(-0.35 <= l1["MET_S%02d" % i] <= -0.20 for i in range(1,13))))
checks.append(("blockB loadings", all(0.35 <= l2["MET_B%02d" % i] <= 0.45 for i in range(13,19))))
checks.append(("noise loadings",  all(abs(l1["MET_N%02d" % i]) < 0.05 for i in range(19,27))
                                   and abs(l1["MET_M27"]) < 0.05))

for name, ok in checks:
    print(("PASS" if ok else "FAIL"), name)
sys.exit(0 if all(ok for _, ok in checks) else 1)
```

The grader parses `scores.tsv`/`loadings.tsv` with `str.split("\t")`, so comma-separated output fails the header checks directly. All spot values above (3.4354, −3.6524, −1.7934, the loading bands, the 0.9218/0.0719 fractions) come from the executed reference run, with the λ2/λ3 eigen-gap measured at 32× so PC2's direction is stable.

## Tier (b) — robustness knobs

Perturb the generator (each knob independently, re-run tool + grader), and require the *structural* criteria to survive even where the pinned values change:

- **Noise amplitude** (`noise(0.10)`/`noise(0.30)` → up to 2×): group separation on PC1 and the loading-band inequalities must still hold; variance fractions will drift and the grader's tight tolerances should be relaxed to ±0.02 for this tier.
- **Missing-data rate** (add missing cells to `MET_N*` / `MET_B*` rows): filter/impute logic must keep rows at exactly 20% missing and drop rows above; counts line must track.
- **Block sizes** (12/6/8 → 8/4/12 signal/B/noise): PC1 fraction drops but must remain > 0.5; separation must survive.
- **Sample count** (5+5 → 8+8): the ≥ 80% filter must scale with `n` (13 of 16 valid keeps a row); the reference run must be regenerated before grading — do not reuse pinned values.
- **Delimiter/quirk check**: feed a table with CRLF line endings and whitespace-padded cells; the tool must parse identically.

Tier (b) grading compares the perturbed run against a fresh reference run on the perturbed generator, not against the tier (a) constants.

## Tier (c) — real data

Dataset: **MetaboLights MTBLS1** — "A metabolomic study of urinary changes in type 2 diabetes in human compared to the control group" (Salek et al.), 1D NMR bucket table, case/control design.
URL: https://www.ebi.ac.uk/metabolights/MTBLS1

Protocol: extract the NMR data matrix (buckets × samples) from the study files, apply the identical pipeline (≥ 80% valid filter, row-mean imputation, log2, mean-center, covariance PCA — note real NMR intensities may contain zeros/negatives, so add a documented small-offset rule before log2 and state it), then compare against **`sklearn.decomposition.PCA(n_components=2)`** run on the identically preprocessed matrix. Acceptance: PC1/PC2 variance fractions agree within ±0.01, and per-sample scores correlate with |r| > 0.999 (sign flips between implementations are expected and normalized before correlating). Record any preprocessing deviation forced by the real file (zeros, headers, sample annotation) as part of the report.

## Benchmark protocol

- Run the prompt in a **fresh agentic coding session in a clean workspace** (no reference implementation, no `features.csv` present beforehand — the model must write the generator from the prompt).
- Record: model name + version, prompt SHA-256, generated `pca.py` SHA-256, iteration count (prompt→grade cycles), wall-clock time, and the per-criterion pass/fail from `grade.py` — never the agent's own claim of success.
- Require cross-model reproduction: at least one remote frontier-class model and one local model; report each run separately, including failures.
- The prompt must fit the context budget of the smallest model claimed: current prompt is ~7.7 KB / 146 lines, well under the 32 K-context local budget used elsewhere in this repo's benchmarks.
- Update this file with results after execution; until then it remains a plan.
