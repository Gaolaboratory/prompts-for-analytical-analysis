# data/uvvis — real solution UV-Vis spectrum for tier (c) validation

## Source

- **Dataset:** "Ultrafast spectroscopy of nitrophenols and nitroanisoles", University of
  Bristol research data repository (data.bris), DOI `10.5523/bris.w1wn1z8y4nmk2f0hze1zbuo35`,
  published 2026-07-14. Creators: Andrew Orr-Ewing, Deborin Ghosh, Hallam Greene.
- **Original file:** `w1wn1z8y4nmk2f0hze1zbuo35/2_UV-Vis/Aqueous_UV-visible_spectra.csv`, an
  entry inside the dataset zip:
  https://data.bris.ac.uk/datasets/w1wn1z8y4nmk2f0hze1zbuo35/w1wn1z8y4nmk2f0hze1zbuo35.zip
  (zip is 9,412,424 bytes; only this ~20 KB entry was transferred — see "How obtained").
  Dataset landing page: https://data.bristol.ac.uk/data/dataset/w1wn1z8y4nmk2f0hze1zbuo35
- **Download date:** 2026-08-26
- **License:** Non-Commercial Government Licence for public sector information
  (http://www.nationalarchives.gov.uk/doc/non-commercial-government-licence/non-commercial-government-licence.htm)
- This dataset is the underlying data for the paper "Solvent-dependent triplet-state
  behaviour of nitrophenol and nitroanisole isomers" (Greene, Ghosh, Bravo, Kadrikj,
  Jones, Jordan, Lau, Fielding, Orr-Ewing), per the dataset ReadMe.

## Contents

`4-nitrophenol.csv` — solution UV-Vis absorption spectrum of **4-nitrophenol**
(para-nitrophenol, pNP; CAS 100-02-7) in **acidified aqueous solution** (neutral
molecular form), measured at the University of Bristol. Instrument not stated in the
dataset ReadMe.

- 576 points, **224.99–799.99 nm**, ~1 nm steps, columns `wavelength_nm,absorbance`.
- **The y-values are the molar absorption coefficient ε (dm³ mol⁻¹ cm⁻¹ = M⁻¹ cm⁻¹),
  not raw instrument absorbance** — that is how the source file reports them
  (dataset ReadMe: "the molar absorption coefficient of para-nitrophenol in acidified
  solution in dm^3 mol^-1 cm^-1"). ε equals the absorbance of a 1 mol/L solution in a
  1 cm cell, so band positions and λmax are directly comparable to absorbance data;
  only the absolute y-scale (~10³–10⁴) differs from a typical 0–1.5 A run.
- The source file also contains columns for pNA, pNP⁻ (alkaline), mNA, mNP, mNP⁻;
  only wavelength + pNP were kept.

## Expected results

**Published λmax for the main band: 317 ± 3 nm** (4-nitrophenol, neutral form,
aqueous solution). Citations:

1. Saha, Kurrey, Verma, Deb, *Chemistry* **2022**, 4(4), 1757–1774,
   doi:10.3390/chemistry4040114 — "An aqueous solution of 4-nitrophenol shows a
   distinct spectral contour with an absorption maximum at **~317 nm** … shift of
   λmax value of 4-nitrophenol … from 317 nm to 400 nm … because of deprotonation".
2. Bailey-Darland, Krueger, Fang, *Molecules* **2023**, 28(2), 601,
   doi:10.3390/molecules28020601, Figure 1b — steady-state absorption of 4NP in
   acidic water with the prominent peak wavelength labelled (~317 nm; nitrophenolate
   peak "around 400 nm in water").
3. Vandaele, Mališ, Luber, *J. Chem. Theory Comput.* **2024**, doi:10.1021/acs.jctc.3c01400
   — "Experimentally measured absorption spectra [of 4-NP] in aqueous solution located
   a maximum at 3.88 eV, 3.90 eV, or 3.91 eV" → 317–320 nm.

**Raw argmax measured from this CSV (std-lib python3, global max of absorbance in
250–700 nm): 317.015 nm (ε = 9283 M⁻¹ cm⁻¹)** — 0.0 nm from the pinned 317 nm value,
well inside the ±3 nm acceptance band. Corroborating checks: peak ε ≈ 9.3×10³ M⁻¹ cm⁻¹
is consistent with literature ε ≈ 9–10×10³ near 317 nm, and the pNP⁻ (alkaline)
column of the same source file peaks at 401.0 nm, matching the published 400–405 nm
phenolate band.

## How obtained

1. Queried the data.bris CKAN API
   (`/data/api/3/action/package_show?id=w1wn1z8y4nmk2f0hze1zbuo35`) to locate the
   dataset zip URL and license (per-file download links are not exposed for this
   dataset; only the ReadMe is a standalone resource).
2. The server supports HTTP Range requests, so the single CSV was extracted from the
   remote zip without downloading the whole 9.4 MB archive: fetched the last 128 KB
   (zip central directory), located the entry `…/2_UV-Vis/Aqueous_UV-visible_spectra.csv`
   (deflate, 19,812 → 40,779 bytes), range-fetched exactly those bytes and inflated
   with stdlib `zlib`. Total transfer ≈ 150 KB.
3. Conversion to the tool's CSV format (documented, values unmodified):
   source header `Wavelength / nm,pNA,pNP,pNP-,mNA,mNP,mNP-` → `wavelength_nm,absorbance`
   (column 3, `pNP` = acidified aqueous solution); rows were wavelength-descending and
   were re-sorted ascending; both columns reformatted to 5 decimals. Original text
   header row and one descending-wavelength sample row:
   `Wavelength / nm,pNA,pNP,pNP-,mNA,mNP,mNP-` /
   `799.99127,-16.91224,10.33186,13.98899,7.94208,-13.95542,-16.91646`.
4. Plausibility verified with std-lib python3: single smooth band in 250–700 nm
   (mean |second difference| ≈ 9.7 on a peak of 9283, i.e. ~0.1% noise); no negative
   values in the 250–400 nm band region (min +3.65); negative values occur only in the
   401–799 nm baseline region where the neutral molecule does not absorb (most
   negative −107.8 at 559 nm ≈ 1.2% of peak — normal spectrometer baseline noise; the
   tier (a) "no negative absorbance below −0.05" rule is absorbance-scale and does not
   transfer literally to ε-scale data).
