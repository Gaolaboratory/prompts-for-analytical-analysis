# MS input readers — FASTA, mzML, MGF

## Dependencies

None — this is a base module. Other prompts depend on it.

Standard library only (no `pyteomics`, `pymzml`, `numpy`). Write three files:

- `fasta_reader.py` → `read_fasta(path) -> [(record_id, sequence), ...]`, ID = first whitespace token of the header.
- `mzml_reader.py` → `read_mzml(path) -> [dict, ...]` with keys `id, ms_level, rt, precursor_mz, precursor_charge, mz, intensity`. `precursor_*` are `None` on MS1.
- `mgf_reader.py` → `read_mgf(path) -> [dict, ...]` returning **the same dict shape as `read_mzml`**, so a tool that consumes spectra never has to know which format they came from.

Other prompts import these readers rather than re-implementing them. **Keep the
signatures and dict keys exactly as given** — they are the interface those prompts
are written against.

## Data

Run `python3 make_test_data.py` (shipped beside this prompt) to write `mini.fasta`,
`mini.mzml`, `mini_ms1.mzml` and `mini.mgf`. It is the oracle: the numbers below hold
only for its exact output. Don't edit it and don't generate the data any other way.

## The parts of mzML you can't guess

Everything else is ordinary XML parsing — this is the domain knowledge you need:

- Default namespace `http://psi.hupo.org/ms/mzml`, so match qualified tags (`{...}spectrum`) or strip namespaces.
- Accessions: `MS:1000511` ms level · `MS:1000016` scan start time (inside `scanList/scan`) · `MS:1000744` selected ion m/z and `MS:1000041` charge state (inside `precursorList/precursor/selectedIonList/selectedIon`) · `MS:1000514` m/z array · `MS:1000515` intensity array · `MS:1000523` 64-bit / `MS:1000521` 32-bit · `MS:1000574` zlib / `MS:1000576` no compression.
- `<binary>` is base64 → (optionally zlib-decompress) → `struct.unpack` **little-endian** (`'<%dd' % (len(raw)//8)`, or `'<%df'` for 32-bit). m/z and intensity arrays are parallel.
- **Encoding and compression cvParams are flags: test whether the accession is present, never whether its `value` attribute is non-empty.** Vendors write `<cvParam accession="MS:1000574" name="zlib compression"/>` with no `value` at all, so a `value`-based check silently skips decompression and the unpack then fails or returns garbage.
- **`rt` must always be returned in seconds.** `MS:1000016` carries a unit: `UO:0000010` is seconds, `UO:0000031` is minutes — multiply those by 60. Vendor files commonly use minutes.

### MGF

Simpler than mzML, with its own traps:

- Records run `BEGIN IONS` … `END IONS`. Inside, `KEY=VALUE` lines are metadata and
  bare `mz intensity` pairs are peaks.
- **`PEPMASS` is the precursor m/z, not a neutral mass**, and it may carry a second
  value (the precursor intensity) — take the first whitespace token.
- **`CHARGE=2+` has a trailing sign** that must be stripped before `int()`. It can also
  be `2-`, and it may be absent.
- `RTINSECONDS` is already seconds. `SCANS` gives the scan number; build `id` as
  `scan=<n>` so it matches what `read_mzml` returns for the same spectrum.
- MGF carries fragmentation spectra only, so `ms_level` is always **2**.


`mini.mzml` stores scan=1 uncompressed and scan=2 zlib-compressed, so a reader that mishandles either path fails immediately.

## Acceptance criteria

Run `python3 make_test_data.py`, then check all of:

1. `read_fasta("mini.fasta")` → exactly `[("sp|P00001|MINI1", "MKTAYIAKQRQISFVKSHFSRQDILDLWQNLTTGPGR"), ("sp|P00002|MINI2", "MAGDRSPGTWEQLKDAVEILRQNYVGAFW")]`. Blank lines, wrapped sequences and lowercase input must also parse.
2. `read_mzml("mini.mzml")` → 2 spectra, both `ms_level=2`, `mz` ascending, `len(mz) == len(intensity)`.
3. `scan=1`: `rt=101.0`, `precursor_mz=361.2158`, `precursor_charge=2`, **25 peaks**, first m/z 129.0649, last 1496.7187, max intensity 9682.8, sum 64705.8.
4. `scan=2`: `rt=102.0`, `precursor_mz=523.2693`, `precursor_charge=2`, **31 peaks**, first m/z 88.0485, last 1436.4881, max intensity 9987.7, sum 95772.6.
5. `read_mzml("mini_ms1.mzml")` → 24 MS1 spectra, RT 60.0–83.0 s, 13 peaks each.
6. `read_mgf("mini.mgf")` → 2 spectra that agree with `read_mzml("mini.mzml")` **exactly**:
   same `id`, `ms_level`, `rt`, `precursor_mz`, `precursor_charge`, and identical `mz` and
   `intensity` lists. `mini.mgf` carries the same two spectra as `mini.mzml`, written with
   enough decimals to round-trip losslessly, so any difference at all is a bug in one of your
   two readers. Assert this equality in code rather than eyeballing the summaries.

Give each reader a `main` printing a one-line-per-spectrum summary.

## If something fails

0 spectra → namespace. Wrong peak count or a `struct.error` → you skipped zlib (see the flag-cvParam rule) or used the wrong float width. Garbled values → not little-endian. `precursor_*` `None` on MS2 → wrong nesting depth. `rt` a string → cvParam `value` attributes are always strings.

## Optional

`iter_mzml(path)` streaming via `iterparse`. Then run your reader on any real vendor mzML you have: passing the synthetic criteria above does not prove it handles real files.
