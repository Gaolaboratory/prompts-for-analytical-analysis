# mzML / FASTA reader validation data (tier c)

Real-instrument mzML files and a real UniProt protein database for validating the
Task 1/4 minimal mzML and FASTA readers (`examples/mass_reader/minimal_readers_prompt.md`)
beyond the prompt's synthetic fixtures.

## Source

### bsa_orbitrap_first40.mzML (primary mzML: MS1 + MS2 DDA)

- Origin file: `BSA1.mzML.gz` from the **pymzML** repository test data
  (working URL, HTTP 200, direct download):
  https://raw.githubusercontent.com/pymzml/pymzML/master/tests/data/BSA1.mzML.gz
  (blob: https://github.com/pymzml/pymzML/blob/master/tests/data/BSA1.mzML.gz,
  last changed in pymzML commit `78b3f6c7c086`, 2023-01-06)
- Embedded provenance (from the mzML metadata itself): the parent run is
  `20090810_SvNa_QC_BSA50fmol.RAW`, a 50 fmol BSA QC injection acquired
  2009-08-09T22:32:31 on a **Thermo LTQ Orbitrap XL** (MS:1000556) running
  Xcalibur 2.4 SP1. The distributed mzML was produced by peak-picking and
  merging the MS1 and MS2 streams, then filtering to m/z 0–800 and RT 1500–2500 s
  (all recorded in `dataProcessingList`/userParams). So the spectra are real
  measured peak lists (centroided), not profile, and not synthetic.
- License: the pymzML repository is Apache License 2.0, which covers its
  redistributed test data.

### thermo_small_raw.mzML (secondary mzML: zlib, 32-bit, minutes RT units)

- Origin file: `test.mzML` from the **pyteomics** repository tests
  (working URL, HTTP 200, direct download):
  https://raw.githubusercontent.com/levitsky/pyteomics/master/tests/test.mzML
  (blob: https://github.com/levitsky/pyteomics/blob/master/tests/test.mzML,
  last changed in pyteomics commit `88f9507c3399`, 2018-10-04)
- Embedded provenance: `mzML id="small_RAW"`, `sourceFile name="small.RAW"`
  (MS:1000563 Thermo RAW file), converted by pwiz_Reader_Thermo. It is the
  pwiz/msconvert conversion of the small Thermo RAW demo file (two profile MS1
  scans, 19,914 points each).
- License: the pyteomics repository is Apache License 2.0.

### ecoli_k12_48.fasta

- Origin: **UniProtKB/Swiss-Prot** via the UniProt REST API — the 48
  reviewed (`reviewed:true`) entries of *Escherichia coli* K-12 MG1655
  (`organism_id:83333`) with the smallest primary accessions, fetched in
  canonical FASTA form (`>sp|ACC|ID ...`) exactly as UniProt serves them.
- Downloaded from https://rest.uniprot.org/uniprotkb/search (query in
  "How obtained" below) on 2026-08-26.
- License: UniProt data is CC BY 4.0 (https://www.uniprot.org/help/license).

All files downloaded on 2026-08-26. A UPS1 48-protein FASTA was considered and
dropped: no public, stable, verifiable copy could be located (GitHub code
search and the PRIDE PXD001819 file list both failed to provide one), so the
task's sanctioned alternative — a documented UniProt subset — was used instead.

## Contents

| File | Bytes | What it is |
| --- | --- | --- |
| `bsa_orbitrap_first40.mzML` | 285,032 | 40 spectra subset of the BSA QC run: 10 MS1 + 30 MS2 (DDA). Plain mzML 1.1.0, no index wrapper. Every spectrum: m/z array 64-bit float uncompressed, intensity array **32-bit float** uncompressed. Spectrum ids `spectrum=NNNN` (id attribute before index). RT in **seconds** (UO:0000010). Precursor selected-ion m/z + charge state on every MS2. |
| `thermo_small_raw.mzML` | 445,302 | 2 profile MS1 scans from `small.RAW`, **indexedmzML** wrapper (reader must skip the trailing index). scan=1: 64-bit m/z + 32-bit intensity, **uncompressed**; scan=2: m/z and intensity both **32-bit + zlib** (MS:1000574). Thermo native ids `controllerType=0 controllerNumber=1 scan=N`. RT in **minutes** (UO:0000031) — exercises the ×60 rule. |
| `ecoli_k12_48.fasta` | 25,732 | 48 Swiss-Prot entries, headers `>sp|P00509|AAT_ECOLI Aspartate aminotransferase OS=... OX=83333 GN=... PE=1 SV=1`, 60-char wrapped sequences. |

SHA-256 (shasum -a 256):

```
3ddd28450c752bb1f74ab5cd52bb4ecbb80a2b4ab3894a5db8bba22c5d96bf16  bsa_orbitrap_first40.mzML
0875f22ba358d4b3224c5a9c96d427c8d5ae9e68c50dd830c533819ab76bde7a  thermo_small_raw.mzML
6548debe04e0de5b2a35d8b5d6083fc17283173fffe35722f533e5c67e2d7aae  ecoli_k12_48.fasta
```

Coverage vs the prompt's failure modes: together the two mzML files exercise
namespace-qualified tags, base64 + both float widths, both compression states,
minute/second RT units, attribute-order variance, MS1/MS2 precursor nesting,
an indexed wrapper, and profile-vs-centroid data.

## Expected results

All values computed harness-side with pyteomics 5.0.1 (recipe below), with RT
normalised to seconds using each cvParam's unitAccession (UO:0000031 → ×60).

### bsa_orbitrap_first40.mzML

| Quantity | Expected value |
| --- | --- |
| Total spectra | 40 |
| MS1 count | 10 |
| MS2 count | 30 |
| TIC total (see definition) | 45709750.399179935 |
| First scan RT (s) | 1501.41394042969 |
| Last scan RT (s) | 1590.18725585938 |
| Precursor m/z list length | 30 |
| Charge states present | {2, 3} |
| First spectrum id / peaks | `spectrum=1011`, 467 peaks, m/z 300.08976–794.76366 |
| First MS2 id / precursor | `spectrum=2442`, precursor m/z 457.723968505859, z = 2 |
| Last spectrum id | `spectrum=2471` |

### thermo_small_raw.mzML

| Quantity | Expected value |
| --- | --- |
| Total spectra | 2 |
| MS1 count | 2 |
| MS2 count | 0 |
| TIC total (see definition) | 138763684.23791504 |
| First scan RT (s) | 0.2961 (= 0.004935 min × 60) |
| Last scan RT (s) | 0.3561 (= 0.005935 min × 60) |
| Precursor m/z list length | 0 |
| Charge states present | {} (none — MS1-only file) |
| Peaks per spectrum | 19,914 (profile), m/z 200.00019–2000.00995 |

### ecoli_k12_48.fasta

| Quantity | Expected value |
| --- | --- |
| Entry count | 48 |
| Total sequence length (residues) | 19929 |
| First header (ID token) | `sp|P00509|AAT_ECOLI` |
| First full header line | `sp|P00509|AAT_ECOLI Aspartate aminotransferase OS=Escherichia coli (strain K12) OX=83333 GN=aspC PE=1 SV=1` |
| First sequence length | 396 |
| Shortest/longest sequence | 121 (`sp|P04737|PIL1_ECOLI` Pilin) / 1073 (`sp|P00968|CARB_ECOLI` carbamoyl phosphate synthase large chain) |
| Last header (ID token) | `sp|P06974|FLIM_ECOLI` |

Exact entries (accessions, in file order): P00509 P00803 P00804 P00861 P00946
P00968 P02359 P02916 P02925 P02929 P03023 P03959 P04395 P04805 P04982 P04993
P05041 P05804 P05824 P05825 P06134 P06616 P06960 P06961 P06968 P00393 P00448
P00579 P00888 P00903 P00963 P02358 P02918 P02921 P02931 P02942 P03960 P04079
P04152 P04693 P04737 P04825 P04995 P05042 P05194 P05852 P06722 P06974
(entry IDs: AAT_ECOLI LEP_ECOLI LSPA_ECOLI DCDA_ECOLI MANA_ECOLI CARB_ECOLI
RS7_ECOLI MALF_ECOLI RBSB_ECOLI TONB_ECOLI LACI_ECOLI KDPA_ECOLI 3MG2_ECOLI
SYE_ECOLI RBSD_ECOLI RECD_ECOLI PABB_ECOLI BGLR_ECOLI RECN_ECOLI FEPA_ECOLI
ADA_ECOLI ERA_ECOLI OTC2_ECOLI CCA_ECOLI DUT_ECOLI NDH_ECOLI SODM_ECOLI
RPOD_ECOLI AROF_ECOLI PABA_ECOLI ASNA_ECOLI RS6_ECOLI PBPA_ECOLI MELB_ECOLI
OMPF_ECOLI MCP1_ECOLI KDPB_ECOLI GUAA_ECOLI UMUC_ECOLI TYRB_ECOLI PIL1_ECOLI
AMPN_ECOLI EX1_ECOLI FUMC_ECOLI AROD_ECOLI TSAD_ECOLI MUTH_ECOLI FLIM_ECOLI)

**TIC definition (important).** "TIC total" above is the sum over all spectra
of the sum of the decoded `MS:1000515` intensity arrays, accumulated in float64.
It is **not** the `MS:1000285` cvParam: `bsa_orbitrap_first40.mzML` carries no
TIC cvParams at all, and in `thermo_small_raw.mzML` the cvParam (15245068 per
scan, from the RAW header) disagrees with the profile-array sums (69381842.119
per scan) because the RAW TIC was computed on centroided data. A reader that
reports array-based TIC must match the values above; tolerance 1e-3 relative
(counts ±1) as specified for this tier.

### pyteomics reference recipe

```python
# /tmp/msvenv/bin/pip install pyteomics numpy   (pyteomics 5.0.1)
import re
import numpy as np
from pyteomics import fasta, mzml

MIN = "UO:0000031"  # minute; UO:0000010 is second

def mzml_refs(path):
    text = open(path, encoding="ISO-8859-1").read()
    cv_texts = [m.group(0) for m in re.finditer(
        r'name="scan start time" value="[^"]*"[^/]*/?>', text)]  # per-scan unit
    n, rts, pmz, charges, tic = {"1": 0, "2": 0}, [], [], set(), 0.0
    for i, s in enumerate(mzml.read(path)):
        lvl = s["ms level"]; n[str(lvl)] += 1
        cv = s["scanList"]["scan"][0]["scan start time"]
        rts.append(cv * 60.0 if MIN in cv_texts[i] else float(cv))
        tic += float(np.asarray(s["intensity array"], dtype=np.float64).sum())
        if lvl == 2:
            si = s["precursorList"]["precursor"][0][
                     "selectedIonList"]["selectedIon"][0]
            if "selected ion m/z" in si: pmz.append(si["selected ion m/z"])
            if "charge state" in si: charges.add(si["charge state"])
    return dict(n_spectra=sum(n.values()), n_ms1=n["1"], n_ms2=n["2"],
                tic_total=tic, rt_first=rts[0], rt_last=rts[-1],
                n_precursor_mz=len(pmz), charge_states=sorted(charges))

def fasta_refs(path):
    recs = list(fasta.read(path))
    return dict(n_entries=len(recs), total_length=sum(len(s) for _, s in recs),
                first_header=recs[0][0])
```

## How obtained

```sh
# 1) mzML sources (2026-08-26)
curl -sL -o BSA1.mzML.gz  "https://raw.githubusercontent.com/pymzml/pymzML/master/tests/data/BSA1.mzML.gz"
curl -sL -o pyteomics_test.mzML "https://raw.githubusercontent.com/levitsky/pyteomics/master/tests/test.mzML"
gunzip -kf BSA1.mzML.gz   # -> BSA1.mzML, 13,864,488 bytes, 1684 spectra (564 MS1 + 1120 MS2)

# 2) Subsetting BSA1.mzML (13.9 MB > budget). The file stores all 564 MS1 spectra
#    first, then all 1120 MS2 (the producer merged the picked MS1 and MS2 files),
#    so a plain first-N cut would be MS1-only. A std-lib script cut at
#    <spectrum>-element boundaries, keeping original spectra 0-9 (MS1) and 564-593
#    (first 30 MS2); only spectrum/@index was renumbered 0..39 (schema requires
#    sequential indices) and spectrumList/@count set to 40. No spectral byte was
#    altered otherwise (verified: all 40 m/z and intensity arrays are exactly
#    equal to the source spectra's arrays under pyteomics).
#    -> bsa_orbitrap_first40.mzML (285,032 bytes)
#    pyteomics_test.mzML was kept byte-for-byte as thermo_small_raw.mzML.

# 3) FASTA (2026-08-26): reviewed E. coli K-12 accessions, take the 48 smallest
curl -s "https://rest.uniprot.org/uniprotkb/search?query=reviewed:true+AND+organism_id:83333&fields=accession&format=tsv&size=500" -o acc.tsv
# sort accessions, keep first 48, then fetch those exactly:
curl -sG "https://rest.uniprot.org/uniprotkb/search" \
     --data-urlencode "query=accession:P00509 OR accession:P00803 OR ... (48 terms)" \
     --data-urlencode "format=fasta" --data-urlencode "size=500" -o ecoli_k12_48.fasta
```

Verified: both mzML files are well-formed XML (ElementTree) and parse under
pyteomics with the counts above; the FASTA has 48 headers, canonical Swiss-Prot
`sp|ACC|ID` headers, and no duplicate accessions.
