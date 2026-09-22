# Example data & expected results — nmr_1d (real-data run: FAILED bounds, kept for the record)

**Dataset:** a real 700 MHz ¹H noesypr1d FID of human urine (MetaboLights **MTBLS1**, sample
ADG10003u_007, NS 128), converted to the tool's single-real-channel input
(`data/nmr/fid.csv`, 32,697 points, dt 71.4 µs) with the required constant overrides in
`acqus_constants.txt`. Provenance: `data/nmr/README.md`. **This dataset is not shipped in
`data/`** — the tier (c) run below failed its pinned bounds (see verdict), so per the campaign
rule only passing tools' data ship; the dataset and its full documentation are preserved at
`.superpowers/tierc/` (ask the repo owner) pending a tool or bounds revision.

**Run:** `python3 nmr_1d.py fid.csv -o multiplets.tsv` with spectral width / dwell / carrier
from `acqus_constants.txt` (SFO1 699.87 MHz, carrier 4.766 ppm, SW 7002.8 Hz).

**Expected results (harness reference: nmrglue em(lb=1) → zf 65,536 → FFT → magnitude; peaks in
the *folded* convention the single-real-channel tool model produces):** 4.77 (water, 1.00),
5.47 (1.13), 6.49 (~2.2–2.3), 6.98 (0.53), 9.53 (1.86) ppm; bounds ±0.05 ppm / ±20% relative
integral on the strongest 3–5.

**Observed local-LLM run** (2026-08-26, Ornith-1.5-35B-A3B via pi; cell
`bench/runs/nmr/local/tierc/`, 49 iterations): 6 multiplets — 4.772 (1.000), 5.973 (3.487),
6.505 (5.627), 6.997 (3.486), 7.612 (0.785), 9.534 (2.064). Verdict: **FAIL** — 4/5 expected
ppm centers within ±0.05 (water, 6.49, 6.98, 9.53 ✓) but the 5.47 ppm expected peak has no
counterpart (nearest tool peak 5.97, 0.50 ppm off) and 3/5 relative integrals are far outside
±20% (+209%, +150%, +558%). Root cause (documented, matches the TEST_PLAN's own caveat): the
real FID is complex quadrature, and squeezing it through the prompt's single-real-channel model
folds mirror partners onto neighboring resonances, inflating integration windows — a
tool-input-model limitation on real data, not an LLM failure (the agent followed the spec
faithfully; 49 iterations, all self-checks green). Tier (c) status for this prompt: **open** —
either the prompt needs a complex-input variant or the bounds need re-derivation for folded
spectra.
