# Task 1/4 — mzML and FASTA readers

Standard library only (no `pyteomics`, `pymzml`, `numpy`). Write three files:

- `fasta_reader.py` → `read_fasta(path) -> [(record_id, sequence), ...]`, ID = first whitespace token of the header.
- `mzml_reader.py` → `read_mzml(path) -> [dict, ...]` with keys `id, ms_level, rt, precursor_mz, precursor_charge, mz, intensity`. `precursor_*` are `None` on MS1.
- `make_test_data.py` — exactly the script below; run it to produce the test files.

Tasks 2–4 of this series import these readers and re-run this generator. **Keep the signatures and dict keys exactly as given.**

## The parts of mzML you can't guess

Everything else is ordinary XML parsing — this is the domain knowledge you need:

- Default namespace `http://psi.hupo.org/ms/mzml`, so match qualified tags (`{...}spectrum`) or strip namespaces.
- Accessions: `MS:1000511` ms level · `MS:1000016` scan start time (inside `scanList/scan`) · `MS:1000744` selected ion m/z and `MS:1000041` charge state (inside `precursorList/precursor/selectedIonList/selectedIon`) · `MS:1000514` m/z array · `MS:1000515` intensity array · `MS:1000523` 64-bit / `MS:1000521` 32-bit · `MS:1000574` zlib / `MS:1000576` no compression.
- `<binary>` is base64 → (optionally zlib-decompress) → `struct.unpack` **little-endian** (`'<%dd' % (len(raw)//8)`, or `'<%df'` for 32-bit). m/z and intensity arrays are parallel.
- **Encoding and compression cvParams are flags: test whether the accession is present, never whether its `value` attribute is non-empty.** Vendors write `<cvParam accession="MS:1000574" name="zlib compression"/>` with no `value` at all, so a `value`-based check silently skips decompression and the unpack then fails or returns garbage.
- **`rt` must always be returned in seconds.** `MS:1000016` carries a unit: `UO:0000010` is seconds, `UO:0000031` is minutes — multiply those by 60. Vendor files commonly use minutes.

## Test data generator

```python
#!/usr/bin/env python3
"""Writes every test file the mini-tool series needs. Std-lib only, fully deterministic."""
import base64, math, struct, zlib

def b64(vals, compress):
    raw = struct.pack("<%dd" % len(vals), *vals)
    return base64.b64encode(zlib.compress(raw) if compress else raw).decode()

def arrays(mz, it, compress):
    comp = "MS:1000574" if compress else "MS:1000576"
    out = ['        <binaryDataArrayList count="2">']
    for acc, vals in (("MS:1000514", mz), ("MS:1000515", it)):
        out += ['          <binaryDataArray>',
                f'            <cvParam cvRef="MS" accession="{acc}"/>',
                '            <cvParam cvRef="MS" accession="MS:1000523"/>',
                f'            <cvParam cvRef="MS" accession="{comp}"/>',
                f'            <binary>{b64(vals, compress)}</binary>',
                '          </binaryDataArray>']
    return out + ['        </binaryDataArrayList>']

# ---------------- mini.fasta ----------------
open("mini.fasta", "w").write(
    ">sp|P00001|MINI1 Mini protein 1\nMKTAYIAKQRQISFVKSHFSRQDILDLWQNLTTGPGR\n"
    ">sp|P00002|MINI2 Mini protein 2\nMAGDRSPGTWEQLKDAVEILRQNYVGAFW\n")

# ---------------- mini.mzml : 2 MS2 spectra ----------------
# scan=1 is uncompressed, scan=2 is zlib-compressed, so the reader must honour both.
MS2 = [
 dict(id="scan=1", rt=101.0, pmz=361.2158, z=2, compress=False,
  mz=[129.0649,142.1156,147.1159,242.1501,246.1851,320.4917,329.1845,366.2916,393.2415,476.2422,
      480.2753,504.6559,541.3881,575.3284,593.3742,716.7436,740.2618,799.6824,826.7738,839.7338,
      1172.8030,1276.3018,1285.2171,1441.2593,1496.7187],
  it=[6038.0,258.8,6540.6,6286.5,1376.9,56.8,8136.8,158.9,3730.6,8286.8,5607.2,81.6,153.3,9682.8,
      5190.9,429.1,175.2,348.1,338.1,76.8,230.2,368.5,223.9,431.3,498.1]),
 dict(id="scan=2", rt=102.0, pmz=523.2693, z=2, compress=True,
  mz=[88.0485,145.1701,147.1080,168.7752,185.0858,223.3532,242.1213,260.2061,299.1127,343.1632,
      388.2624,516.2459,517.3057,529.2447,537.4613,597.9796,623.2899,658.2793,673.2190,703.3810,
      786.3504,804.4342,808.7916,860.3687,861.4495,899.4297,958.4897,1034.5011,1042.5328,1383.0490,
      1436.4881],
  it=[2263.3,466.3,9610.5,289.3,2085.3,498.4,3085.7,6096.8,421.4,9388.8,6245.4,318.0,6306.0,1436.0,
      401.5,244.3,312.2,2711.2,347.4,9314.6,7965.6,3875.1,282.8,245.1,4110.8,6510.9,9987.7,133.3,
      287.7,188.3,342.9])]

out = ['<?xml version="1.0" encoding="UTF-8"?>',
       '<mzML xmlns="http://psi.hupo.org/ms/mzml" version="1.1.0">',
       '  <run id="mini_run">', f'    <spectrumList count="{len(MS2)}">']
for i, s in enumerate(MS2):
    out += [f'      <spectrum index="{i}" id="{s["id"]}" defaultArrayLength="{len(s["mz"])}">',
            '        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="2"/>',
            '        <scanList count="1"><scan>',
            f'          <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="{s["rt"]}" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>',
            '        </scan></scanList>',
            '        <precursorList count="1"><precursor><selectedIonList count="1"><selectedIon>',
            f'          <cvParam cvRef="MS" accession="MS:1000744" name="selected ion m/z" value="{s["pmz"]}"/>',
            f'          <cvParam cvRef="MS" accession="MS:1000041" name="charge state" value="{s["z"]}"/>',
            '        </selectedIon></selectedIonList></precursor></precursorList>']
    out += arrays(s["mz"], s["it"], s["compress"]) + ['      </spectrum>']
open("mini.mzml", "w").write("\n".join(out + ['    </spectrumList>', '  </run>', '</mzML>']) + "\n")

# ---------------- mini_ms1.mzml : 24 MS1 scans, 2 analytes + noise ----------------
NEUTRON = 1.003355
ANALYTES = [(500.2697, 1, 66.0, 3.0, 3000.0, [1.0, 0.40]),
            (451.2297, 2, 76.0, 2.5, 6000.0, [1.0, 0.60, 0.20])]
def lcg(state):
    while True:
        state = (1103515245 * state + 12345) % 2147483648
        yield state / 2147483648.0
rnd = lcg(20260823)

out = ['<?xml version="1.0" encoding="UTF-8"?>',
       '<mzML xmlns="http://psi.hupo.org/ms/mzml" version="1.1.0">',
       '  <run id="mini_ms1_run">', '    <spectrumList count="24">']
for i in range(24):
    rt = 60.0 + i
    pk = []
    for mono, z, apex, sig, h, ratios in ANALYTES:
        amp = h * math.exp(-((rt - apex) ** 2) / (2 * sig * sig))
        for k, r in enumerate(ratios):
            pk.append((mono + k * NEUTRON / z + (next(rnd) - 0.5) * 0.004, amp * r))
    for _ in range(8):
        pk.append((200.0 + next(rnd) * 1300.0, 50.0 + next(rnd) * 250.0))
    pk.sort()
    out += [f'      <spectrum index="{i}" id="scan={i+1}" defaultArrayLength="{len(pk)}">',
            '        <cvParam cvRef="MS" accession="MS:1000511" name="ms level" value="1"/>',
            '        <scanList count="1"><scan>',
            f'          <cvParam cvRef="MS" accession="MS:1000016" name="scan start time" value="{rt}" unitCvRef="UO" unitAccession="UO:0000010" unitName="second"/>',
            '        </scan></scanList>']
    out += arrays([p[0] for p in pk], [p[1] for p in pk], i % 2 == 1) + ['      </spectrum>']
open("mini_ms1.mzml", "w").write("\n".join(out + ['    </spectrumList>', '  </run>', '</mzML>']) + "\n")

print("wrote mini.fasta, mini.mzml, mini_ms1.mzml")
```

`mini.mzml` stores scan=1 uncompressed and scan=2 zlib-compressed, so a reader that mishandles either path fails immediately.

## Acceptance criteria

Run `python3 make_test_data.py`, then check all of:

1. `read_fasta("mini.fasta")` → exactly `[("sp|P00001|MINI1", "MKTAYIAKQRQISFVKSHFSRQDILDLWQNLTTGPGR"), ("sp|P00002|MINI2", "MAGDRSPGTWEQLKDAVEILRQNYVGAFW")]`. Blank lines, wrapped sequences and lowercase input must also parse.
2. `read_mzml("mini.mzml")` → 2 spectra, both `ms_level=2`, `mz` ascending, `len(mz) == len(intensity)`.
3. `scan=1`: `rt=101.0`, `precursor_mz=361.2158`, `precursor_charge=2`, **25 peaks**, first m/z 129.0649, last 1496.7187, max intensity 9682.8, sum 64705.8.
4. `scan=2`: `rt=102.0`, `precursor_mz=523.2693`, `precursor_charge=2`, **31 peaks**, first m/z 88.0485, last 1436.4881, max intensity 9987.7, sum 95772.6.
5. `read_mzml("mini_ms1.mzml")` → 24 MS1 spectra, RT 60.0–83.0 s, 13 peaks each.

Give each reader a `main` printing a one-line-per-spectrum summary.

## If something fails

0 spectra → namespace. Wrong peak count or a `struct.error` → you skipped zlib (see the flag-cvParam rule) or used the wrong float width. Garbled values → not little-endian. `precursor_*` `None` on MS2 → wrong nesting depth. `rt` a string → cvParam `value` attributes are always strings.

## Optional

`iter_mzml(path)` streaming via `iterparse`. Then run your reader on any real vendor mzML you have: passing the synthetic criteria above does not prove it handles real files.
