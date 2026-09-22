# Example data & expected results — uvvis_spectrum

**Dataset:** real UV-Vis spectrum of **4-nitrophenol** (acidified aqueous solution, neutral
form), 576 points over 225–800 nm (`data/uvvis/4-nitrophenol.csv`). Note: the y-column is the
molar absorption coefficient ε (M⁻¹ cm⁻¹), not raw absorbance — band detection is unaffected.
Provenance (data.bris DOI 10.5523/bris.w1wn1z8y4nmk2f0hze1zbuo35) and the λmax citation:
`data/uvvis/README.md`.

**Run:** `python3 uvvis.py 4-nitrophenol.csv -o peaks.tsv` (report the band table; the
concentration line is `n/a` for this dataset — path length/ε pairing is unknown).

**Expected results (TEST_PLAN tier-c bound):** main-band **λmax = 317 ± 3 nm** (published ~317
nm, Saha et al., Chemistry 2022, doi:10.3390/chemistry4040114; harness-measured argmax on the
raw CSV: 317.015 nm).

**Observed local-LLM run** (2026-08-26, Ornith-1.5-35B-A3B via pi; cell
`bench/runs/uvvis/local/tierc/`, 9 iterations): main band λmax = **318 nm**, a_max 3757 —
**PASS** (inside ±3 nm). Caveat, documented not hidden: the tool also reported a weak second
"band" at 797 nm (a_max 81, 2.2% of the main peak) — a phantom from the real dataset's noisy
long-wavelength tail (raw noise down to −107 ε units in 401–799 nm, where the molecule does not
absorb). The synthetic prompt's fixed 0.20×a_max band floor does not reject it; a real-data
robustness knob (noise-relative threshold) would.
