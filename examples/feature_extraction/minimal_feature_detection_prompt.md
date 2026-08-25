# Task 3/4 — MS1 feature extraction

Standard library only. Write `features.py`.

**Reuse task 1:** `from mzml_reader import read_mzml`; run `python3 make_test_data.py` for `mini_ms1.mzml` (24 MS1 scans, 1 s apart, two analytes with Gaussian elution plus noise below 300). Do not re-implement parsing. (If those files are missing, build task 1 first.)

`python3 features.py mini_ms1.mzml -o features.tsv` — detect features and write, sorted by m/z:

```
feature_id	mono_mz	charge	rt_apex	rt_start	rt_end	area	n_isotopes
```

## Algorithm

Keep `ms_level == 1`. Print the count after each of steps 1–3 **to stdout**.

1. **Threshold** — keep peaks with intensity ≥ 500 as `(mz, scan_index, rt, intensity)`.
2. **Traces (EICs)** — sort peaks by m/z; greedily append a peak to an existing trace if `|mz − trace_mean_mz| ≤ 0.01` **and** that trace has no peak from the same scan, updating the running mean; else start a new trace. Keep traces spanning ≥ 5 distinct scans.
3. **Peak shape per trace** — apex = max intensity; extend left/right from the apex, stopping when intensity < 5% of apex **or** scan indices are non-consecutive; m/z = intensity-weighted mean; area = trapezoid of intensity over **RT** (not scan index).
4. **Isotope grouping** — `NEUTRON = 1.003355`. Walk traces by ascending m/z; each joins at most one group. For an ungrouped trace `t0`: among ungrouped traces above it with apex RT within 1.0 s, take the **smallest** m/z gap `d` with `0.2 < d ≤ 1.02`; set `z = round(NEUTRON/d)`, accepting only if `1 ≤ z ≤ 3` and `|d − NEUTRON/z| ≤ 0.01`, else `z = 1`. Then for `k = 1, 2, …` claim an ungrouped trace at `mz(t0) + k·NEUTRON/z` (±0.01) with apex RT within 1.0 s, stopping at the first gap. Emit one feature: `t0`'s m/z and area, charge `z`, `n_isotopes` = group size.

## Acceptance criteria

1. Prints **24** scans, **45** peaks above threshold, **5** traces — on stdout, not stderr.
2. `features.tsv` has exactly **2** rows.
3. `mono_mz` 451.23 ± 0.01, `charge` 2, `rt_apex` 76.0 ± 1.0, `n_isotopes` 3.
4. `mono_mz` 500.27 ± 0.01, `charge` 1, `rt_apex` 66.0 ± 1.0, `n_isotopes` 2.
5. Every area > 0, and each monoisotopic area exceeds its own isotopes' areas.

Reference traces (last digit may differ): 451.2301 / 451.7313 / 452.2337 all apex 76.0 with areas ≈ 35781 / 19980 / 5742; 500.2698 / 501.2730 apex 66.0 with areas ≈ 20334 / 6120.

## If something fails

Peaks ≠ 45 → threshold, or you kept MS2. Traces ≠ 5 → you compared against the trace's first peak instead of its running mean, allowed two peaks from one scan, or skipped the ≥ 5-scan filter. Charge 1 on the 451.23 feature → you paired it with its M+2 (+1.0034) instead of the nearest trace above it (+0.5012); always take the smallest qualifying gap. Wrong `n_isotopes` → the step is `NEUTRON/z`, divided by z. Wrong scan counts → fix `mzml_reader.py` in task 1, not here.

## Optional

ppm tolerance; 3-point smoothing before apex detection; an isotope-pattern score against 1.0/0.6/0.2 (z=2) or 1.0/0.4 (z=1).
