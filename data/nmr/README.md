# data/nmr — complex-quadrature 1H FID (MTBLS1 ADG10003u_007)

This is the **complex quadrature** FID (both receiver channels, `time_s,real,imag`)
on the **true** ppm axis. It replaces an earlier tier-(c) validation dataset built
from the **real channel only**, preserved at
`.superpowers/tierc/nmr-data-preserved/`. That single-channel dataset folds every
resonance below the carrier onto a mirror image at
`ppm_tool = 9.5330 - ppm_true` (identity derived there from `CARRIER_PPM = 4.76648`),
because a single real channel cannot distinguish positive from negative frequency
offsets from the carrier. It could not be repaired into complex form because the
imaginary channel was discarded when it was written — hence this task re-downloads
the raw Bruker FID (both channels) from the same source and converts it properly.
Do not use the preserved file or any value derived from it as an oracle for this
dataset.

## Source

- **Dataset:** MetaboLights **MTBLS1** — "A metabolomic study of urinary changes in
  type 2 diabetes in human compared to the control group" (Salek et al.; study
  identifier MTBLS1, first public 2012-02-14). Human urine, 1H NMR, Bruker.
- **File used:** sample `ADG10003u_007`, experiment `10` (single sample,
  direct per-file download, no login):
  https://ftp.ebi.ac.uk/pub/databases/metabolights/studies/public/MTBLS1/FILES/ADG10003u_007.zip
  (570,685 bytes, sha256 `a023c811036490b630d6df2dcf9f622b3251e7a2fda9c07525037781f310f9c2`;
  contains Bruker dir `ADG10003u_007/10/` with `acqus`, `fid`, `pdata/1/` including
  the instrument-processed spectrum `1r`/`1i` and `procs`).
- **Download date:** 2026-09-03.
- **License:** EMBL-EBI Terms of Use (https://www.ebi.ac.uk/about/terms-of-use/).
- **Acquisition (from `acqus`):** 1H `noesypr1d` (NOESY with water presaturation),
  NS = 128, solvent "Urine", 5 mm PATXI 1H-13C/15N probe, BF1 = 699.87 MHz
  (17.45 T), O1 = 3290.5 Hz, SW_h = 14005.6022 Hz (20.01172 ppm), TD = 65536
  (32,768 complex points), DSPFVS = 12, DECIM = 12, RG = 574.7, TE = 300 K.
  `pdata/1/title`: "Compound Human Urine / NMN 4PY — PPAR PAN study looking for
  BioMarker NMN 4PY". Note: the water presaturation pulse sequence suppresses the
  water resonance, so water's peak height/integral is small relative to the
  unsuppressed metabolite peaks below — that is expected instrument behavior, not
  a conversion artifact.

## Contents

- **`fid_complex.csv`** (1,191,319 bytes) — 32,697 complex data points, header
  `time_s,real,imag` (preceded by 2 `#` comment lines recording the acquisition
  constants), 32,700 lines total. `time_s` = index x dt, dt = 7.14000e-05 s
  (0 .. 2.334366 s). Derivation: `ng.bruker.read` on `ADG10003u_007/10` (32,768
  complex points) followed by `ng.bruker.remove_digital_filter` (Bruker DSP
  group-delay removal, DSPFVS 12 / DECIM 12 -> 69.5-point group delay -> 71
  points dropped -> 32,697 points remain). Both receiver channels (real and
  imaginary) are kept, unlike the retired real-channel-only dataset.

## Acquisition constants

- Spectrometer frequency SF = 699.869954581 MHz (`pdata/1/procs` SF, the
  TSP-referenced axis — not raw BF1)
- Carrier CARRIER_PPM = 4.76648 ppm (= procs `OFFSET` - SW_ppm/2 =
  14.77234 - 10.00586)
- Spectral width SW = 14005.6022 Hz (= 20.01172 ppm, full complex bandwidth;
  `acqus` `SW_h`)
- dt = 7.14000e-05 s (= 1/SW)
- Zero-fill: 65536 (next power of 2 >= 32,697 points)
- Line broadening LB = 1.0 Hz (apodization used for the reference processing below)

These constants and `N = 32697` are printed verbatim by the converter (see "How
obtained").

## Expected results

**Build-time validation** (harness-side, nmrglue 0.12 / numpy 2.5.2, venv at
`/tmp/nmrvenv`, via `bench/reference/convert_mtbls1_complex.py`, run once to
produce and validate `fid_complex.csv`): read the complex FID, apodize
`em(lb = 1.0 Hz)`, zero-fill to 65,536, FFT, apply the instrument's own phase
correction (`procs` PHC0 = -37.977, PHC1 = -9.746), take the real part,
sign-normalized so the water region is positive; `ppm = CARRIER_PPM + f/SF`
(ascending, no mirroring — this is the true axis). This confirmed the six
resonances land on the true ppm axis, not the mirrored one: measured apex ppm
agreed with the instrument's own processed spectrum (`pdata/1/1r` + `procs`
axis) to within 0.0016 ppm for all six (bound 0.01 ppm) — see "How obtained".

**Grading oracle** (`bench/reference/nmr_expected.py`, **numpy only**, no
nmrglue, runs under the pinned `.venv-bench` and reads `fid_complex.csv` as its
only input — this is what a Task 9 (`nmr_s`) submission is graded against):
read the complex FID (`real + 1j*imag`), apodize `exp(-pi * LB * t)` at
LB = 1.0 Hz, zero-fill to NFFT = 65536, FFT, `fftshift`; build
`ppm = CARRIER_PPM + f/SF` with `f = (arange(NFFT) - NFFT//2) * SW_HZ/NFFT`;
take the **magnitude** spectrum (`abs`, not the phased real part above — a
magnitude spectrum needs no phase constants and is not sensitive to the sign
of a phase-correction convention, so this is the recipe the tool prompt
specifies); pick local maxima at or above **5%** of the spectrum maximum (not
3% or 8%); for each of the six named resonances, integrate its picked peak
over a **valley-bounded** window, capped at **+/-0.10 ppm** per side (not
+/-0.05 or +/-0.15): starting at the apex bin, step outward one bin at a time
in each direction for as long as the next bin is **strictly lower** than the
current one (`spec[next] < spec[current]`); stop as soon as that stops being
true, i.e. **the moment the next bin is not lower** (`spec[next] >= spec[current]`
— a flat run of bins stops the walk immediately, it is not walked through
waiting for an actual rise), or the +/-0.10 ppm cap is reached, whichever
comes first. Take the local baseline as the **mean of the spectrum values at
the two resulting window-boundary bins** (not the minimum value inside the
window, and not a linear interpolation between the boundaries), subtract it,
and sum over the window; normalize every integral to the resonance nearest
**0.000 ppm (TSP/DSS)**, which becomes 1.000.

TSP/DSS, not water, is the normalization reference. Water was tried first and
rejected: TSP/DSS is the sample's internal chemical-shift standard, a sharp
line, whereas water in this `noesypr1d` acquisition is a broad,
presaturation-attenuated line whose integral is unusually sensitive to the
exact window width (see "Oracle sensitivity check" below) — normalizing to it
put the scale of the whole table on the least stable feature in the spectrum.

| resonance | nominal ppm | measured apex ppm | delta (ppm) | rel. integral (TSP/DSS = 1.0) | graded on integral? |
|---|---:|---:|---:|---:|---|
| TSP/DSS | 0.000 | -0.0001 | 0.0001 | 1.0000 (reference) | no (defines the scale) |
| acetate | 1.921 | 1.9212 | 0.0002 | 0.1456 | yes |
| citrate | 2.549 | 2.5493 | 0.0003 | 0.1649 | yes |
| creatinine CH3 | 3.048 | 3.0476 | 0.0004 | 0.9307 | yes |
| creatinine CH2 | 4.058 | 4.0587 | 0.0007 | 0.4750 | yes |
| water | 4.767 | 4.7671 | 0.0001 | 0.8816 | **no — informational only** |

- **Bounds for grading:** all six ppm positions within **+/- 0.05 ppm**
  (unchanged — water's position is still a criterion). Relative integral
  within **+/- 20%** for the four metabolite resonances only: acetate,
  citrate, creatinine CH3, creatinine CH2. TSP/DSS's integral is the
  reference (1.000 by construction, not a separate criterion). **Water's
  integral is reported above for information but is not graded** — a
  presaturated water line is broad, and this recipe's valley-bounded window
  width for a broad line is comparatively sensitive to exactly where the
  walk happens to stop, which is exactly what the sensitivity check below
  measures.
- All six relative integrals are positive (verified — see "How obtained");
  the earlier build of this table (phased-complex mode, fixed +/-0.03 ppm
  window with a distant flanking baseline) produced a spuriously negative
  citrate integral because that fixed flanking window overlapped citrate's
  own second AB-doublet multiplet near 2.656 ppm. The valley-bounded rule
  above fixes that at the root, for all six resonances uniformly, not with a
  citrate-specific carve-out.

### Oracle sensitivity check

Before pinning the four-integral bound above, `bench/reference/nmr_expected.py
--sensitivity` recomputed the four graded relative integrals under each of
four ambiguous-or-diagnostic readings of the same written recipe, one axis at
a time, against the pinned default as baseline. Three axes are genuine
ambiguities the written recipe's prose does not settle by itself (which is
why the recipe wording above pins all three in exact terms); the fourth
(window cap) is not ambiguous — it is pinned at exactly +/-0.10 ppm — and was
tested only to measure how load-bearing that pin is:

| axis | variant | worst graded-resonance deviation |
|---|---|---:|
| peak-pick threshold (ambiguous) | 3% and 8% (pinned: 5%) | 0.00% |
| baseline estimator (ambiguous) | min-in-window and linear-interp (pinned: mean-of-boundary) | +7.88% (creatinine CH3, min-in-window) |
| valley-test strictness (ambiguous) | stop-only-on-strict-rise (pinned: stop-on-non-decrease) | 0.00% |
| window cap (**not ambiguous, pinned at +/-0.10**; diagnostic only) | +/-0.05 and +/-0.15 ppm | +18.89% (citrate/acetate/creatinine CH3/CH2 tied, cap=0.05) |

**Worst deviation among the three genuinely ambiguous axes: +7.88%** —
comfortably inside +/-20%. **Worst deviation across all four axes, including
the non-ambiguous cap diagnostic: +18.89%** — inside +/-20%, but close to it,
which is exactly why the +/-0.10 ppm cap is pinned rather than left as a
free parameter: an earlier run of this same check, before TSP/DSS
replaced water as the normalization reference, found the +/-0.05 ppm cap
variant moved four resonances by **+20.92%** — just outside +/-20% — because
narrowing the cap shrank water's (the reference at the time) window and
denominator by a similar amount for every resonance at once. Renormalizing to
TSP/DSS (a narrower, sharper line whose own window is far less sensitive to
the cap) brought that same variant back under the bound (+18.89%), but the
margin is not large. **Conclusion: the +/-0.10 ppm window cap is load-bearing
and must be implemented exactly as pinned (not approximated); the +/-20%
integral bound stands, verified against the three genuine ambiguities in the
written recipe with the cap held fixed.**

## How obtained

```bash
mkdir -p /tmp/nmrsrc && cd /tmp/nmrsrc
curl -sSL -o ADG10003u_007.zip \
  "https://ftp.ebi.ac.uk/pub/databases/metabolights/studies/public/MTBLS1/FILES/ADG10003u_007.zip"
unzip -q ADG10003u_007.zip          # -> ADG10003u_007/10/{acqus,fid,pdata/1}

python3 -m venv /tmp/nmrvenv
/tmp/nmrvenv/bin/pip -q install nmrglue numpy

# from the repository root, with bench/reference/convert_mtbls1_complex.py's
# OUT changed from 'data/nmr_quad' to 'data/nmr' (SRC left as
# '/tmp/nmrsrc/ADG10003u_007/10', which the fetch above recreates exactly):
/tmp/nmrvenv/bin/python3 bench/reference/convert_mtbls1_complex.py
```

Actual stdout from the run that produced this dataset:

```
N=32697 dt=7.140000e-05 SW_h=14005.6022 SF=699.869954581 carrier=4.76648 SW_ppm=20.01172 PHC0=-37.977 PHC1=-9.746
wrote data/nmr/fid_complex.csv 1191319 bytes

reference peaks (true ppm axis, complex processing):
  TSP/DSS          nominal   0.000  apex -0.0007  height  2.6037e+08  integral  4.8225e+08
  acetate          nominal   1.921  apex  1.9206  height  5.1383e+07  integral  5.9250e+07
  citrate          nominal   2.549  apex  2.5481  height  4.2694e+07  integral -7.8261e+07
  creatinine_CH3   nominal   3.048  apex  3.0464  height  2.2144e+08  integral  2.7403e+08
  creatinine_CH2   nominal   4.058  apex  4.0571  height  1.0723e+08  integral  6.2934e+07
  water            nominal   4.767  apex  4.7656  height  1.1974e+08  integral  8.2311e+06
```

(The script also prints hippurate cross-checks and a general peak-picking table;
omitted here as not part of the six-resonance validation gate. The exact
commands are also recorded in `bench/reference/short/nmr_sourcing_notes.md`.)

The full converter script writes additional harness-side scratch files
(`ref_ppm.npy`, `ref_spec.npy`, `reference.json`) into its `OUT` directory for
its own use; those were deleted after verification and are not part of this
dataset (only `fid_complex.csv` and this README are shipped).

**Reproducing the grading oracle** (magnitude mode, numpy only, pinned
`.venv-bench`, reads only `fid_complex.csv` — no source archive or nmrglue
needed):

```bash
.venv-bench/bin/python3 bench/reference/nmr_expected.py
```

Actual stdout from the run that produced the "Expected results" table above:

```
N=32697 dt=7.140000e-05 SW_h=14005.6022 SF=699.869954581 carrier=4.76648 NFFT=65536 LB=1.000 cap_bins=327 dppm=3.053546e-04
total local maxima >= 5% of spectrum max: 15

magnitude-mode reference peaks (valley-bounded integration, TSP/DSS-normalised):
  resonance          nominal      apex     delta          window(ppm)   rel_integral  graded?
  TSP/DSS              0.000   -0.0001    0.0001  [ -0.0850,  0.0817]         1.0000  position only (reference, =1.000 by definition)
  acetate              1.921    1.9212    0.0002  [  1.8885,  1.9407]         0.1456  position + integral
  citrate              2.549    2.5493    0.0003  [  2.5353,  2.5844]         0.1649  position + integral
  creatinine CH3       3.048    3.0476    0.0004  [  3.0238,  3.0925]         0.9307  position + integral
  creatinine CH2       4.058    4.0587    0.0007  [  4.0397,  4.0932]         0.4750  position + integral
  water                4.767    4.7671    0.0001  [  4.6917,  4.8669]         0.8816  position only (integral informational)

all relative integrals positive: True
max apex delta (ppm): 0.0006679721846234443
```

**Reproducing the sensitivity check** (same constraints, no source archive or
nmrglue needed):

```bash
.venv-bench/bin/python3 bench/reference/nmr_expected.py --sensitivity
```

See "Oracle sensitivity check" above for the summary; the full per-variant,
per-resonance table is recorded in the Task 1 fix-round report
(`.superpowers/sdd/2026-09-03-p3-sweep/task-1-report.md`, fix round 3).

## Local checksum

```
$ shasum -a 256 data/nmr/fid_complex.csv
a8415fa5fe15cbe3817de5d3495281fe2ca8f3ce89e8844d958b51b75e0510e8  data/nmr/fid_complex.csv
```

File size: 1,191,319 bytes.
