#!/usr/bin/env python3
"""Oracle-conformant `search.py` for the DDA v2 prompt: the pinned settings only.

Used to build the grader's conformant fixture. dda_search.py is the parameterised
research tool; this pins it to exactly what minimal_dda_search_v2_prompt.md specifies
(count score, 12 peaks per 100 Da window, length 6-18, 0.02 Da x z precursor window,
0.5 Da fragment tolerance, no fixed modifications) and reports the criterion-6
differential by running the search a second time with filtering off.
"""
import argparse

from dda_search import (digest, fragments, neutral, qvalues, read_fasta, read_mgf,
                        preprocess, score_psm)

PREC_TOL, FRAG_TOL, MIN_LEN, MAX_LEN = 0.02, 0.5, 6, 18
TOP_N, WINDOW, CAM = 12, 100.0, False


def build_index(fasta):
    entries = []
    for name, seq in read_fasta(fasta):
        for pname, s, dec in ((name, seq, 0), ("DECOY_" + name, seq[::-1], 1)):
            for pep in digest(s, MIN_LEN, MAX_LEN):
                entries.append((neutral(pep, CAM), pep, pname, dec))
    entries.sort()
    return entries


def search(entries, spectra, top_n):
    import bisect
    masses = [e[0] for e in entries]
    psms, with_cand = [], 0
    for sp in spectra:
        z = sp["z"]
        obs = sp["pmz"] * z - z * 1.0072765
        tol = PREC_TOL * z
        lo = bisect.bisect_left(masses, obs - tol)
        hi = bisect.bisect_right(masses, obs + tol)
        if hi <= lo:
            continue
        with_cand += 1
        mzs, ints = preprocess(sp["peaks"], sp["pmz"], top_n, WINDOW)
        best = None
        for _, pep, pname, dec in entries[lo:hi]:
            s, n, total, inten = score_psm(mzs, ints, pep, FRAG_TOL, "count", CAM)
            key = (s, inten)
            if best is None or key > best[0]:
                best = (key, dict(scan=sp["scan"], pmz=sp["pmz"], charge=z, peptide=pep,
                                  protein=pname, decoy=dec, matched=n, total=total, score=s))
        if best:
            psms.append(best[1])
    return psms, with_cand


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fasta"); ap.add_argument("spectra")
    ap.add_argument("-o", "--out", default="psms.tsv")
    a = ap.parse_args()

    entries = build_index(a.fasta)
    n_t = sum(1 for e in entries if not e[3])
    n_d = len(entries) - n_t
    spectra = read_mgf(a.spectra)
    print("peptides indexed: %d target, %d decoy" % (n_t, n_d))
    print("spectra read: %d" % len(spectra))

    psms, with_cand = search(entries, spectra, TOP_N)
    print("spectra with >=1 candidate: %d" % with_cand)
    n_dec = sum(p["decoy"] for p in psms)
    print("best hits: %d (decoy %d = %.1f%%)"
          % (len(psms), n_dec, 100.0 * n_dec / len(psms) if psms else 0.0))
    psms = qvalues(psms)
    acc = sum(1 for p in psms if not p["decoy"] and p["q"] <= 0.01)
    print("target PSMs at q <= 0.01: %d" % acc)

    unf, _ = search(entries, spectra, 0)
    unf = qvalues(unf)
    acc_u = sum(1 for p in unf if not p["decoy"] and p["q"] <= 0.01)
    print("target PSMs at q <= 0.01 without peak filtering: %d (decoy %d)"
          % (acc_u, sum(p["decoy"] for p in unf)))

    with open(a.out, "w", newline="") as fh:
        fh.write("scan\tprecursor_mz\tcharge\tpeptide\tprotein\tdecoy\t"
                 "matched_fragments\ttotal_fragments\tscore\tq_value\n")
        for p in sorted(psms, key=lambda p: int(p["scan"])):
            fh.write("%s\t%.4f\t%d\t%s\t%s\t%d\t%d\t%d\t%.4f\t%.5f\n"
                     % (p["scan"], p["pmz"], p["charge"], p["peptide"], p["protein"],
                        p["decoy"], p["matched"], p["total"], p["score"], p["q"]))


if __name__ == "__main__":
    main()
