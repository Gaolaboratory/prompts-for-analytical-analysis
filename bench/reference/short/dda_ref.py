#!/usr/bin/env python3
"""Reference DDA database search for examples/database_search/PROMPT.md (v2 rules).

Implements exactly minimal_dda_search_v2_prompt.md's pipeline (Standard library
only): reversed-sequence DECOY_ proteins digested alongside targets; tryptic
peptides (cleave after K/R, not before P) of length 6-18; monoisotopic residue
masses, H2O=18.010565, PROTON=1.0072765; singly-charged fragments b1..b(n-1)
and y1..y(n-1), where b_i is the first i residues and y_i is the last i
residues -- independent series, not mirror images of each other; a
mass-sorted (neutral_mass, peptide, protein, decoy) index selected with
bisect; candidates within 0.02 x z Da of neutral_obs = pmz*z - z*PROTON; peak
filtering to the 12 most intense peaks per 100 Da window with peaks within
2 Da of the precursor dropped; score = matched-fragment count at +/-0.5 Da,
tie-broken by summed matched intensity; tie-grouped monotone q-values (every
PSM sharing an integer score gets the FDR evaluated at the end of that
score's group, then swept bottom-up from the descending-score-sorted list).

No modifications are applied (fixed carbamidomethyl-C is listed only under
"Optional" in the v2 prompt and is deliberately NOT modelled here, matching
the pinned base-pipeline numbers).

`run(fasta_path, mgf_path, peak_filter=True) -> dict` with keys: targets,
decoys, spectra, with_candidate, best_hits, decoy_hits, psms_1pct (ints),
decoy_fraction (float), rows (list of per-spectrum best-hit dicts with scan,
peptide, protein, decoy, score, qvalue), and proteins_ge2 (int: number of
distinct TARGET proteins that are the best hit for >= 2 spectra, matching the
"M" quantity in data/database_search/README.md's v1 block).
"""
import bisect
from collections import defaultdict

RES = {'G': 57.02146, 'A': 71.03711, 'S': 87.03203, 'P': 97.05276, 'V': 99.06841,
       'T': 101.04768, 'C': 103.00919, 'L': 113.08406, 'I': 113.08406, 'N': 114.04293,
       'D': 115.02694, 'Q': 128.05858, 'K': 128.09496, 'E': 129.04259, 'M': 131.04049,
       'H': 137.05891, 'F': 147.06841, 'R': 156.10111, 'Y': 163.06333, 'W': 186.07931}
H2O = 18.010565
PROTON = 1.0072765

MIN_LEN, MAX_LEN = 6, 18
PREC_TOL = 0.02          # x charge
FRAG_TOL = 0.5
TOP_N, WINDOW = 12, 100.0
PRECURSOR_EXCLUDE = 2.0


def digest(seq, min_len=MIN_LEN, max_len=MAX_LEN):
    """Trypsin: cleave after K/R except before P. Peptide keeps the C-terminal K/R."""
    peps, start, n = [], 0, len(seq)
    for i, r in enumerate(seq):
        if r in 'KR' and not (i + 1 < n and seq[i + 1] == 'P'):
            peps.append(seq[start:i + 1])
            start = i + 1
    if start < n:
        peps.append(seq[start:])
    return [p for p in peps if min_len <= len(p) <= max_len and all(c in RES for c in p)]


def neutral_mass(seq):
    return sum(RES[c] for c in seq) + H2O


def fragments(seq):
    """Singly-charged b1..b(n-1) and y1..y(n-1). b_i = first i residues (+PROTON);
    y_i = last i residues (+H2O+PROTON) -- two independent series, both built
    from the peptide's termini, not one loop mirrored from the other."""
    n = len(seq)
    b, pre = [], 0.0
    for i in range(n - 1):
        pre += RES[seq[i]]
        b.append(pre + PROTON)
    y, suf = [], 0.0
    for i in range(n - 1, 0, -1):
        suf += RES[seq[i]]
        y.append(suf + H2O + PROTON)
    return b, y


def read_fasta(path):
    """[(id, sequence), ...]; id = first whitespace token of the header."""
    out, hdr, chunks = [], None, []
    for line in open(path):
        line = line.rstrip('\n')
        if line.startswith('>'):
            if hdr is not None:
                out.append((hdr, ''.join(chunks)))
            hdr, chunks = line[1:].strip().split()[0], []
        elif line.strip():
            chunks.append(line.strip())
    if hdr is not None:
        out.append((hdr, ''.join(chunks)))
    return out


def read_mgf(path):
    spectra = []
    scan = pmz = z = None
    peaks = []
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        if line == 'BEGIN IONS':
            scan = pmz = z = None
            peaks = []
        elif line == 'END IONS':
            if pmz is not None and z is not None:
                spectra.append({'scan': scan, 'pmz': pmz, 'z': z, 'peaks': peaks})
        elif line.startswith('SCANS='):
            try:
                scan = int(line.split('=', 1)[1].split()[0])
            except ValueError:
                scan = None
        elif line.startswith('PEPMASS='):
            pmz = float(line.split('=', 1)[1].split()[0])
        elif line.startswith('CHARGE='):
            try:
                z = int(line.split('=', 1)[1].strip().rstrip('+-'))
            except ValueError:
                z = None
        elif line[0].isdigit() or line[0] == '-':
            parts = line.split()
            if len(parts) >= 2:
                try:
                    peaks.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    pass
    return spectra


def preprocess(peaks, pmz, top_n, window):
    """Keep the top_n most intense peaks per `window`-Da slice; drop peaks
    within PRECURSOR_EXCLUDE Da of the precursor m/z. top_n<=0 disables
    filtering entirely (step 9's unfiltered run)."""
    if top_n <= 0:
        pts = sorted(peaks)
        mzs = [p[0] for p in pts]
        ints = {p[0]: p[1] for p in pts}
        return mzs, ints
    buckets = defaultdict(list)
    for mz, it in peaks:
        if abs(mz - pmz) < PRECURSOR_EXCLUDE:
            continue
        buckets[int(mz // window)].append((mz, it))
    kept = []
    for group in buckets.values():
        group.sort(key=lambda p: -p[1])
        kept.extend(group[:top_n])
    kept.sort()
    mzs = [p[0] for p in kept]
    ints = {p[0]: p[1] for p in kept}
    return mzs, ints


def _match_series(mzs, ints, series, tol):
    n, tot = 0, 0.0
    for f in series:
        i = bisect.bisect_left(mzs, f - tol)
        best = 0.0
        while i < len(mzs) and mzs[i] <= f + tol:
            v = ints[mzs[i]]
            if v > best:
                best = v
            i += 1
        if best > 0.0:
            n += 1
            tot += best
    return n, tot


def score_psm(mzs, ints, pep, tol=FRAG_TOL):
    """Score = matched-fragment count, tie-broken by summed matched intensity."""
    b, y = fragments(pep)
    nb, ib = _match_series(mzs, ints, b, tol)
    ny, iy = _match_series(mzs, ints, y, tol)
    n = nb + ny
    total = len(b) + len(y)
    return float(n), n, total, ib + iy


def build_index(fasta_path):
    """Mass-sorted (neutral_mass, peptide, protein, decoy) list, targets and
    reversed-sequence DECOY_ proteins digested together."""
    entries = []
    for name, seq in read_fasta(fasta_path):
        for pname, s, dec in ((name, seq, 0), ('DECOY_' + name, seq[::-1], 1)):
            for pep in digest(s):
                entries.append((neutral_mass(pep), pep, pname, dec))
    entries.sort(key=lambda e: e[0])
    return entries


def qvalues(psms):
    """Monotone q-values, tie-grouped: sort by descending score; every PSM
    sharing a score is one group (the score is an integer matched-fragment
    count, so groups are large -- 238/221/216/165 PSMs on the shipped data),
    and ALL members of a group get the SAME FDR estimate, evaluated once
    from the running target/decoy counts at the END of that group (i.e.
    after every tied PSM, target and decoy alike, has been counted). Without
    this, a PSM's q-value would depend on its arbitrary position within its
    own tie group -- not on any property of the PSM itself. Only after every
    group has one FDR value do we sweep bottom-up carrying a running
    minimum, so q-values are monotone."""
    psms = sorted(psms, key=lambda p: -p['score'])
    n = len(psms)
    fdrs = [None] * n
    t = d = 0
    i = 0
    while i < n:
        j = i
        while j < n and psms[j]['score'] == psms[i]['score']:
            if psms[j]['decoy']:
                d += 1
            else:
                t += 1
            j += 1
        f = d / t if t else 1.0
        for k in range(i, j):
            fdrs[k] = f
        i = j
    q = 1.0
    for i in range(n - 1, -1, -1):
        q = min(q, fdrs[i])
        psms[i]['qvalue'] = q
    return psms


def search(entries, spectra, top_n):
    """entries must already be mass-sorted; candidates are selected with bisect,
    never a linear rescan of the whole peptide list."""
    masses = [e[0] for e in entries]
    psms, with_candidate = [], 0
    for sp in spectra:
        z = sp['z']
        obs = sp['pmz'] * z - z * PROTON
        tol = PREC_TOL * z
        lo = bisect.bisect_left(masses, obs - tol)
        hi = bisect.bisect_right(masses, obs + tol)
        if hi <= lo:
            continue
        with_candidate += 1
        mzs, ints = preprocess(sp['peaks'], sp['pmz'], top_n, WINDOW)
        best = None
        for _, pep, pname, dec in entries[lo:hi]:
            s, n, total, inten = score_psm(mzs, ints, pep)
            key = (s, inten)
            if best is None or key > best[0]:
                best = (key, dict(scan=sp['scan'], peptide=pep, protein=pname,
                                   decoy=dec, score=s, matched=n, total=total))
        if best:
            psms.append(best[1])
    return psms, with_candidate


def run(fasta_path, mgf_path, peak_filter=True):
    entries = build_index(fasta_path)
    n_t = sum(1 for e in entries if not e[3])
    n_d = len(entries) - n_t
    spectra = read_mgf(mgf_path)

    top_n = TOP_N if peak_filter else 0
    psms, with_candidate = search(entries, spectra, top_n)
    psms = qvalues(psms)

    best_hits = len(psms)
    decoy_hits = sum(p['decoy'] for p in psms)
    decoy_fraction = (decoy_hits / best_hits) if best_hits else 0.0
    psms_1pct = sum(1 for p in psms if not p['decoy'] and p['qvalue'] <= 0.01)

    byprot = defaultdict(int)
    for p in psms:
        if not p['decoy']:
            byprot[p['protein']] += 1
    proteins_ge2 = sum(1 for v in byprot.values() if v >= 2)

    rows = [dict(scan=p['scan'], peptide=p['peptide'], protein=p['protein'],
                 decoy=p['decoy'], score=p['score'], qvalue=p['qvalue'])
            for p in sorted(psms, key=lambda p: (p['scan'] is None, p['scan']))]

    return dict(targets=n_t, decoys=n_d, spectra=len(spectra),
                with_candidate=with_candidate, best_hits=best_hits,
                decoy_hits=decoy_hits, psms_1pct=psms_1pct,
                decoy_fraction=decoy_fraction, rows=rows,
                proteins_ge2=proteins_ge2)


if __name__ == "__main__":
    import sys
    fasta = sys.argv[1] if len(sys.argv) > 1 else "bench.fasta"
    mgf = sys.argv[2] if len(sys.argv) > 2 else "bench.mgf"

    r = run(fasta, mgf, peak_filter=True)
    u = run(fasta, mgf, peak_filter=False)

    print("peptides indexed: %d target, %d decoy" % (r["targets"], r["decoys"]))
    print("spectra read: %d" % r["spectra"])
    print("spectra with >=1 candidate: %d" % r["with_candidate"])
    print("best hits: %d (decoy %d = %.1f%%)"
          % (r["best_hits"], r["decoy_hits"], 100.0 * r["decoy_fraction"]))
    print("target PSMs at q <= 0.01 (filtered): %d" % r["psms_1pct"])
    print("target PSMs at q <= 0.01 (unfiltered): %d (decoy %d)"
          % (u["psms_1pct"], u["decoy_hits"]))
    print("target proteins with >=2 best-hit spectra: %d" % r["proteins_ge2"])
