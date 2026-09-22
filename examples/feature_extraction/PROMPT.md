# MS1 feature detection from a real LC–MS run

Write `features.py`. Run: `python3 features.py BSA1_F1.mzML -o features.tsv`

Python standard library plus numpy, pandas and scipy only. No pyteomics, no pymzml.

## Dependencies

| module | provides | build from |
|---|---|---|
| `mzml_reader.py` | `read_mzml(path) -> [spectrum dict, ...]` | `examples/mass_reader/PROMPT.md` |

Check the working directory for `mzml_reader.py` before writing any code. If it is
there, import it — do not re-implement it and do not edit it. If it is missing, build
it from the prompt named above, verify that prompt's acceptance criteria, then come
back here.

## Input

`BSA1_F1.mzML` is in the working directory: a tryptic BSA digest, 767 spectra of which
**286 are MS1**, RT 1501–1999 s. Use the MS1 scans only.

## Output

`features.tsv`, tab-separated, sorted by **descending** `apex_intensity`:

```
feature_id	mz	rt_apex	rt_start	rt_end	apex_intensity	n_scans
```

One line on stdout: `ms1_scans=<n> windows=<n> features=<n>`

## Method

1. Sort every MS1 stick by m/z and group them into windows: add a stick to the current
   window if it is within **0.01** of that window's running mean m/z **and** the window
   holds no stick from the same scan; otherwise start a new window. Keep only windows
   seen in **≥ 5 distinct scans**.
2. Keep the **top 200 windows by maximum stick intensity**. This is what bounds the
   run time — do not skip it.
3. For each kept window build an extracted-ion chromatogram across all 286 MS1 scans,
   with intensity 0 in scans where the window has no stick.
4. Threshold the window at `median + 5·MAD`, computed over its **nonzero** intensities
   only. Including the structural zeros drives the MAD to 0 and then everything passes.
5. A feature is a run of consecutive scans at or above that threshold spanning
   **≥ 3 scans**; bridge a single-scan dip rather than splitting the run in two. Its
   `mz` is the intensity-weighted mean of the window's sticks over the run, `rt_apex`
   the scan time of the most intense scan in it, and `rt_start` / `rt_end` the scan
   times at the ends of the run.

## Acceptance criteria

1. `features.tsv` has the header above plus N tab-separated data rows.
2. **120 ≤ N ≤ 480**; a documented reference method finds 240 features on this file.
3. At least **5 of these 10** reference features are present, matched at
   |Δm/z| ≤ 0.01 and |ΔRT| ≤ 10 s (m/z / RT in seconds):
   395.2392/1943.8, 487.7323/1848.7, 395.7405/1941.7, 325.4912/1850.1,
   488.2334/1848.7, 388.2539/1977.4, 443.7112/1749.7, 722.3250/1788.0,
   738.3110/1900.3, 344.2280/1827.0.
4. Every row has `apex_intensity > 0` and `rt_start ≤ rt_apex ≤ rt_end`.
5. The stdout line reports `ms1_scans=286`.
6. The feature list agrees with the documented reference method well beyond the ten
   pairs above: most of a much larger reference feature set from the same file must
   be recovered, not just enough of it to satisfy criterion 3.

The band in criterion 2 is wide because the reference recipe is one reasonable choice
among several. Do not tune the thresholds to land on 240.
