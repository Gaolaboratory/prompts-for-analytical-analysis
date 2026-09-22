#!/usr/bin/env python3
"""DDA database search - standard library only. Completed version.

Adds what the minimal prompt omits and what real ion-trap data needs:
  - mass-sorted peptide index + bisect (linear rescan is O(spectra x peptides))
  - spectrum preprocessing (top-N per m/z window, precursor removal)
  - selectable scoring: count | fraction | intensity | hyperscore
  - target-decoy FDR with q-values, and a reported accepted set
"""
import sys, math, bisect, argparse
from collections import defaultdict

RES = {'G':57.02146,'A':71.03711,'S':87.03203,'P':97.05276,'V':99.06841,
       'T':101.04768,'C':103.00919,'L':113.08406,'I':113.08406,'N':114.04293,
       'D':115.02694,'Q':128.05858,'K':128.09496,'E':129.04259,'M':131.04049,
       'H':137.05891,'F':147.06841,'R':156.10111,'Y':163.06333,'W':186.07931}
H2O = 18.010565
PROTON = 1.0072765
CAM = 57.021464          # fixed carbamidomethyl on C


def digest(seq, min_len=5, max_len=50, missed=0):
    cuts, n = [0], len(seq)
    for i, r in enumerate(seq):
        if r in 'KR' and not (i + 1 < n and seq[i+1] == 'P'):
            cuts.append(i + 1)
    if cuts[-1] != n:
        cuts.append(n)
    peps = []
    for i in range(len(cuts) - 1):
        for j in range(i + 1, min(i + 2 + missed, len(cuts))):
            peps.append(seq[cuts[i]:cuts[j]])
    return [p for p in set(peps) if min_len <= len(p) <= max_len and all(c in RES for c in p)]


def neutral(seq, cam=True):
    m = sum(RES[c] for c in seq) + H2O
    if cam:
        m += CAM * seq.count('C')
    return m


def fragments(seq, cam=True):
    """b and y singly-protonated fragment m/z, ascending within each series."""
    n = len(seq)
    b, y, pre, suf = [], [], 0.0, 0.0
    for i in range(n - 1):
        pre += RES[seq[i]] + (CAM if cam and seq[i] == 'C' else 0.0)
        b.append(pre + PROTON)
    for i in range(n - 1, 0, -1):
        suf += RES[seq[i]] + (CAM if cam and seq[i] == 'C' else 0.0)
        y.append(suf + H2O + PROTON)
    return b, y


def read_fasta(path):
    out, hdr, chunks = [], None, []
    for line in open(path):
        line = line.rstrip()
        if line.startswith('>'):
            if hdr is not None: out.append((hdr, ''.join(chunks)))
            hdr, chunks = line[1:].strip(), []
        elif line:
            chunks.append(line.strip())
    if hdr is not None: out.append((hdr, ''.join(chunks)))
    return out


def read_mgf(path):
    spectra = []
    scan = pm = ch = None; peaks = []
    for line in open(path):
        line = line.strip()
        if not line: continue
        if line == 'BEGIN IONS':
            scan = pm = ch = None; peaks = []
        elif line == 'END IONS':
            if pm is not None and ch is not None:
                spectra.append({'scan': scan, 'pmz': pm, 'z': ch, 'peaks': peaks})
        elif line.startswith('SCANS='):
            try: scan = int(line.split('=',1)[1].split()[0])
            except ValueError: scan = None
        elif line.startswith('PEPMASS='):
            pm = float(line.split('=',1)[1].split()[0])
        elif line.startswith('CHARGE='):
            try: ch = int(line.split('=',1)[1].strip().rstrip('+-'))
            except ValueError: ch = None
        elif line[0].isdigit():
            p = line.split()
            if len(p) >= 2:
                try: peaks.append((float(p[0]), float(p[1])))
                except ValueError: pass
    return spectra


def preprocess(peaks, pmz, top_n, window):
    """Keep the top_n most intense peaks in each `window`-Da slice; drop the
    precursor region. Real ion-trap scans carry hundreds of noise peaks; at
    +/-0.5 Da tolerance they make random matches as likely as real ones."""
    if top_n <= 0:
        return sorted(p[0] for p in peaks), {p[0]: p[1] for p in peaks}
    kept = []
    buckets = defaultdict(list)
    for mz, it in peaks:
        if abs(mz - pmz) < 2.0:      # precursor and its neighbourhood
            continue
        buckets[int(mz // window)].append((mz, it))
    for _, group in buckets.items():
        group.sort(key=lambda p: -p[1])
        kept.extend(group[:top_n])
    kept.sort()
    mzs = [p[0] for p in kept]
    ints = {p[0]: p[1] for p in kept}
    return mzs, ints


def match(mzs, ints, frags, tol):
    """Return (n_matched, summed_intensity) for one fragment series."""
    n, tot = 0, 0.0
    for f in frags:
        i = bisect.bisect_left(mzs, f - tol)
        best = 0.0
        while i < len(mzs) and mzs[i] <= f + tol:
            v = ints[mzs[i]]
            if v > best: best = v
            i += 1
        if best > 0.0:
            n += 1; tot += best
    return n, tot


def score_psm(mzs, ints, pep, tol, mode, cam):
    b, y = fragments(pep, cam)
    nb, ib = match(mzs, ints, b, tol)
    ny, iy = match(mzs, ints, y, tol)
    n, inten, total = nb + ny, ib + iy, len(b) + len(y)
    if mode == 'count':
        s = float(n)
    elif mode == 'fraction':
        s = n / total if total else 0.0
    elif mode == 'intensity':
        s = math.log1p(inten) * (n / total if total else 0.0)
    elif mode == 'hyperscore':
        s = (math.log(math.factorial(min(nb, 20))) + math.log(math.factorial(min(ny, 20)))
             + math.log1p(ib) + math.log1p(iy)) if n else 0.0
    else:
        raise ValueError(mode)
    return s, n, total, inten


def qvalues(psms):
    """Target-decoy q-values over score-sorted PSMs (higher score = better)."""
    psms.sort(key=lambda p: -p['score'])
    t = d = 0
    fdrs = []
    for p in psms:
        if p['decoy']: d += 1
        else: t += 1
        fdrs.append(d / t if t else 1.0)
    q = 1.0
    for i in range(len(psms) - 1, -1, -1):     # monotone from the bottom up
        q = min(q, fdrs[i])
        psms[i]['q'] = q
    return psms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('fasta'); ap.add_argument('spectra')
    ap.add_argument('-o', '--out', default='psms.tsv')
    ap.add_argument('--prec-tol', type=float, default=0.02)
    ap.add_argument('--prec-ppm', type=float, default=0.0, help='if >0, use ppm instead of Da')
    ap.add_argument('--missed', type=int, default=0, help='max missed cleavages')
    ap.add_argument('--min-z', type=int, default=1)
    ap.add_argument('--min-len', type=int, default=5)
    ap.add_argument('--max-len', type=int, default=50)
    ap.add_argument('--frag-tol', type=float, default=0.5)
    ap.add_argument('--score', default='hyperscore',
                    choices=('count','fraction','intensity','hyperscore'))
    ap.add_argument('--top-n', type=int, default=6, help='peaks kept per window (0 = no filtering)')
    ap.add_argument('--window', type=float, default=100.0)
    ap.add_argument('--fdr', type=float, default=0.01)
    ap.add_argument('--no-cam', action='store_true', help='disable fixed carbamidomethyl-C')
    a = ap.parse_args()
    cam = not a.no_cam

    prots = read_fasta(a.fasta)
    allp = prots + [('DECOY_' + h, s[::-1]) for h, s in prots]

    # mass-sorted peptide index; peptide sequence is unique per (seq, protein)
    entries = []
    for hdr, seq in allp:
        dec = hdr.startswith('DECOY_')
        for pep in digest(seq, min_len=a.min_len, max_len=a.max_len, missed=a.missed):
            entries.append((neutral(pep, cam), pep, hdr, dec))
    entries.sort(key=lambda e: e[0])
    masses = [e[0] for e in entries]
    ntgt = sum(1 for e in entries if not e[3]); ndec = len(entries) - ntgt
    print("peptides indexed: %d target, %d decoy" % (ntgt, ndec))

    spectra = read_mgf(a.spectra)
    print("spectra read: %d" % len(spectra))

    psms = []
    n_with_cand = 0
    for sp in spectra:
        z = sp['z']; pmz = sp['pmz']
        if z < a.min_z:
            continue
        obs_neutral = pmz * z - z * PROTON
        d = obs_neutral * a.prec_ppm * 1e-6 if a.prec_ppm > 0 else a.prec_tol * z
        lo = bisect.bisect_left(masses, obs_neutral - d)
        hi = bisect.bisect_right(masses, obs_neutral + d)
        if hi <= lo:
            continue
        n_with_cand += 1
        mzs, ints = preprocess(sp['peaks'], pmz, a.top_n, a.window)
        best = None
        for k in range(lo, hi):
            m, pep, hdr, dec = entries[k]
            s, n, total, inten = score_psm(mzs, ints, pep, a.frag_tol, a.score, cam)
            cand = {'scan': sp['scan'], 'pmz': pmz, 'z': z, 'pep': pep, 'prot': hdr,
                    'decoy': dec, 'matched': n, 'total': total, 'score': s, 'inten': inten}
            if best is None or s > best['score'] or (s == best['score'] and inten > best['inten']):
                best = cand
        if best: psms.append(best)

    print("spectra with >=1 candidate: %d" % n_with_cand)
    print("best hits: %d  (decoy %d = %.1f%%)"
          % (len(psms), sum(p['decoy'] for p in psms),
             100.0 * sum(p['decoy'] for p in psms) / max(1, len(psms))))

    qvalues(psms)
    acc = [p for p in psms if not p['decoy'] and p['q'] <= a.fdr]
    print("accepted at %.0f%% FDR: %d target PSMs" % (100*a.fdr, len(acc)))

    byprot = defaultdict(int)
    for p in acc: byprot[p['prot']] += 1
    m2 = [k for k, v in byprot.items() if v >= 2]
    ups = sorted([(k.split()[0], v) for k, v in byprot.items() if 'ups' in k.lower()],
                 key=lambda kv: -kv[1])
    print("proteins with >=1 accepted PSM: %d ; with >=2: %d" % (len(byprot), len(m2)))
    print("UPS1 proteins among accepted: %s" % (ups if ups else "none"))

    with open(a.out, 'w') as fh:
        fh.write("scan\tprecursor_mz\tcharge\tpeptide\tprotein\tdecoy\tmatched_fragments\t"
                 "total_fragments\tscore\tq_value\n")
        for p in sorted(psms, key=lambda p: (p['scan'] if p['scan'] is not None else 0)):
            fh.write("%s\t%.4f\t%d\t%s\t%s\t%d\t%d\t%d\t%.4f\t%.5f\n"
                     % (p['scan'], p['pmz'], p['z'], p['pep'], p['prot'].split()[0],
                        int(p['decoy']), p['matched'], p['total'], p['score'], p['q']))
    print("wrote", a.out)


if __name__ == '__main__':
    main()
