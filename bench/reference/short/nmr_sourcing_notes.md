# Sourcing notes: `data/nmr/fid_complex.csv`

Exact commands used to produce `data/nmr/fid_complex.csv` and `data/nmr/README.md`
(run 2026-09-03), for reproducibility. See `data/nmr/README.md` for the full
provenance, acquisition constants, and expected-results cross-check.

```bash
# 1. Fetch the source archive (MetaboLights MTBLS1, sample ADG10003u_007, exp 10)
mkdir -p /tmp/nmrsrc && cd /tmp/nmrsrc
curl -sSL -o ADG10003u_007.zip \
  "https://ftp.ebi.ac.uk/pub/databases/metabolights/studies/public/MTBLS1/FILES/ADG10003u_007.zip"
ls -l ADG10003u_007.zip     # 570,685 bytes
unzip -q ADG10003u_007.zip
ls ADG10003u_007/10/        # acqus, fid, pdata/ among others

# 2. Throwaway venv with nmrglue (harness-side sourcing only; NOT added to
#    bench/requirements-bench.txt, which stays pinned to numpy 2.5.2 /
#    pandas 3.0.5 / scipy 1.18.1 for the actual bench venv .venv-bench)
python3 -m venv /tmp/nmrvenv
/tmp/nmrvenv/bin/pip -q install nmrglue numpy

# 3. Run the existing converter (bench/reference/convert_mtbls1_complex.py),
#    from the repository root, with its OUT constant changed from
#    'data/nmr_quad' to 'data/nmr' (SRC left untouched at
#    '/tmp/nmrsrc/ADG10003u_007/10', which step 1 recreates exactly):
/tmp/nmrvenv/bin/python3 bench/reference/convert_mtbls1_complex.py
```

That run wrote `data/nmr/fid_complex.csv` and printed the acquisition constants,
the six cross-check resonances, and a general peak-picking table (captured in
`data/nmr/README.md`). The script also writes scratch files (`ref_ppm.npy`,
`ref_spec.npy`, `reference.json`) into its output directory for its own
diagnostic use; those were deleted after verification and are not part of the
shipped dataset.

## Verification performed after the run

1. Cross-checked the six reference resonances (TSP/DSS, acetate, citrate,
   creatinine CH3, creatinine CH2, water) against the instrument's own
   processed spectrum (`pdata/1/1r` + `procs` axis): all six agreed within
   0.0016 ppm (bound: 0.01 ppm). See `data/nmr/README.md` for the table.
2. Shape checks:
   ```bash
   head -3 data/nmr/fid_complex.csv
   awk 'END{print NR}' data/nmr/fid_complex.csv    # 32700 (3 header + 32697 rows)
   awk -F, 'NR>3 && NF!=3 {print "bad row", NR; exit 1}' data/nmr/fid_complex.csv
   ```
3. Checksum: `shasum -a 256 data/nmr/fid_complex.csv`.
