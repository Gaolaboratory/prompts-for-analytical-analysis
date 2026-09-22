# MS input readers — FASTA and mzML

Write two importable modules. Other prompts import them, so keep the names, the
function signatures and the dict keys exactly as given.

- `fasta_reader.py` → `read_fasta(path) -> [(record_id, sequence), ...]` where
  `record_id` is the first whitespace token of the header line.
- `mzml_reader.py` → `read_mzml(path) -> [dict, ...]` with keys
  `id, ms_level, rt, precursor_mz, precursor_charge, mz, intensity`.
  `precursor_mz` and `precursor_charge` are `None` on MS1. `rt` is always in seconds.

Python standard library plus numpy, pandas and scipy only. No pyteomics, no pymzml.

## Input

Already in the working directory:

- `ecoli_k12_48.fasta` — 48 Swiss-Prot entries, 60-character wrapped sequences.
- `bsa_orbitrap_first40.mzML` — 40 DDA spectra, uncompressed arrays, RT in seconds.
- `thermo_small_raw.mzML` — 2 profile MS1 scans, indexed-mzML wrapper, zlib on the
  second scan, RT in **minutes**.

## Output

`python3 mzml_reader.py <file.mzML>` prints exactly one line:

```
spectra=<n> ms1=<n> ms2=<n> rt_first=<seconds> rt_last=<seconds> tic=<total>
```

where `tic` is the sum of every decoded intensity value in the file.

## Method

- mzML uses the default namespace `http://psi.hupo.org/ms/mzml`. Match qualified tags
  (`{http://psi.hupo.org/ms/mzml}spectrum`) or strip namespaces — otherwise you find
  zero spectra.
- Accessions: `MS:1000511` ms level · `MS:1000016` scan start time, inside
  `scanList/scan` · `MS:1000744` selected ion m/z and `MS:1000041` charge state, inside
  `precursorList/precursor/selectedIonList/selectedIon` · `MS:1000514` m/z array ·
  `MS:1000515` intensity array · `MS:1000523` 64-bit · `MS:1000521` 32-bit ·
  `MS:1000574` zlib · `MS:1000576` no compression.
- `<binary>` is base64 → optionally zlib-decompress → **little-endian** floats
  (`struct.unpack("<%dd" ...)` for 64-bit, `"<%df"` for 32-bit, or
  `numpy.frombuffer(raw, dtype="<f8")`). The m/z and intensity arrays are parallel.
- Encoding and compression cvParams are **flags**: test whether the accession is
  present, never whether its `value` attribute is non-empty. Vendors write
  `<cvParam accession="MS:1000574" name="zlib compression"/>` with no value at all, and
  a value-based check silently skips the decompression.
- `MS:1000016` carries a unit attribute: `UO:0000010` is seconds, `UO:0000031` is
  minutes — multiply the minutes case by 60. `thermo_small_raw.mzML` is in minutes.

## Acceptance criteria

1. `read_fasta("ecoli_k12_48.fasta")` returns 48 records totalling 19929 residues,
   the first being `sp|P00509|AAT_ECOLI` with a 396-residue sequence.
2. `read_mzml("bsa_orbitrap_first40.mzML")` returns 40 spectra — 10 MS1 and 30 MS2 —
   whose first is `spectrum=1011` with 467 peaks and whose last is `spectrum=2471`.
3. In that file `rt` is 1501.414 s for the first spectrum and 1590.187 s for the last
   (±0.001).
4. In that file the first MS2 is `spectrum=2442` with `precursor_mz` 457.72397 (±0.0001)
   and `precursor_charge` 2; the charge states present across the file are exactly
   {2, 3}.
5. `read_mzml("thermo_small_raw.mzML")` returns 2 MS1 spectra of 19914 peaks each with
   `rt` 0.2961 and 0.3561 s (±0.0001) — the minutes-to-seconds case.
6. Summed intensity over every spectrum is 45709750.4 for the BSA file and
   138763684.2 for the Thermo file, each within 0.1%. `python3 mzml_reader.py
   bsa_orbitrap_first40.mzML` prints exactly the one line specified above and
   nothing else, with `spectra=40 ms1=10 ms2=30`, those two retention times, and
   that BSA total.

Do not tune a constant to make a number match; if a criterion fails, the reader is wrong.
