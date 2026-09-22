"""Shared helpers for the tier (b) robustness harness (bench/tier_b.py).

Nothing here writes into bench/runs/, data/ or examples/: every function that
produces a file takes an explicit destination path, and bench/tier_b.py is the
only caller, which always points that destination inside a tempfile.mkdtemp()
directory it removes when done (see run_one_cell's try/finally).
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(REPO, "data")
RUNS = os.path.join(REPO, "bench", "runs")

sys.path.insert(0, os.path.join(REPO, "bench", "graders"))
sys.path.insert(0, os.path.join(REPO, "bench", "reference", "short"))
sys.path.insert(0, os.path.join(REPO, "bench", "reference", "lib"))

from _grading import num_field  # noqa: E402  (re-exported for tool modules)

__all__ = [
    "REPO", "DATA", "RUNS", "num_field",
    "read_text", "write_text", "rel_ok", "close_abs",
    "named_fields", "run_program", "reps_for", "copy_into",
    "capped_line_count", "capped_read_lines",
    "mzml_only", "split_spectra", "rebuild_mzml", "keep_spectra",
]


def read_text(path, newline=None):
    try:
        with open(path, newline=newline, errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def write_text(path, text):
    with open(path, "w", newline="") as fh:
        fh.write(text)


def rel_ok(got, want, tol):
    """True iff `got` is within `tol` relative to `want` (tol fraction of
    abs(want)). None on either side always fails rather than raising."""
    if got is None or want is None:
        return False
    try:
        return abs(got - want) <= tol * abs(want)
    except TypeError:
        return False


def close_abs(got, want, tol):
    if got is None or want is None:
        return False
    try:
        return abs(got - want) <= tol
    except TypeError:
        return False


def named_fields(hdr, fields, names):
    """dict name -> field string, resolved independently for each name in
    `names` that appears exactly once in `hdr` (CONVENTIONS.md rule 10: a
    format slip in one column must not blank every other column's check).
    Empty dict if the row doesn't have the same width as the header at all."""
    if len(fields) != len(hdr):
        return {}
    return {name: fields[hdr.index(name)] for name in names
            if hdr.count(name) == 1}


def run_program(argv, cwd, timeout):
    """Run a submitted program in an isolated directory with a timeout.

    Returns a dict with keys: returncode (None if it never started or timed
    out), stdout, stderr, timed_out (bool), crashed (bool: started but exited
    nonzero), ok (bool: ran to completion with exit 0).  Never raises -- a
    missing interpreter, a missing script, a hang or a nonzero exit are all
    just different values of this dict, so the caller can always record a
    distinct outcome (pass / wrong-answer / crash / timeout) instead of the
    harness itself dying partway through the sweep.
    """
    try:
        proc = subprocess.run(argv, cwd=cwd, timeout=timeout,
                               capture_output=True, text=True)
    except subprocess.TimeoutExpired as exc:
        return {"returncode": None, "stdout": exc.stdout or "",
                "stderr": exc.stderr or "", "timed_out": True,
                "crashed": False, "ok": False}
    except OSError as exc:
        return {"returncode": None, "stdout": "", "stderr": str(exc),
                "timed_out": False, "crashed": True, "ok": False}
    return {"returncode": proc.returncode, "stdout": proc.stdout,
            "stderr": proc.stderr, "timed_out": False,
            "crashed": proc.returncode != 0, "ok": proc.returncode == 0}


def reps_for(tool_dir, mode=None):
    """Sorted list of (rep_number, workspace_path) for every rep this tool
    has actually run under bench/runs/<tool_dir>[/<mode>]/local/<rep>/workspace,
    skipping any rep with no workspace (a void/harness_error cell) rather than
    failing the whole sweep for one missing directory."""
    base = os.path.join(RUNS, tool_dir, mode, "local") if mode else \
        os.path.join(RUNS, tool_dir, "local")
    out = []
    if not os.path.isdir(base):
        return out
    for name in sorted(os.listdir(base), key=lambda s: (len(s), s)):
        ws = os.path.join(base, name, "workspace")
        if os.path.isdir(ws):
            try:
                rep = int(name)
            except ValueError:
                rep = name
            out.append((rep, ws))
    return out


def copy_into(dst_dir, *srcs):
    """Copy each file path in `srcs` into dst_dir, skipping any that doesn't
    exist (a submission that didn't ship an optional module) rather than
    raising."""
    for src in srcs:
        if src and os.path.isfile(src):
            shutil.copy2(src, os.path.join(dst_dir, os.path.basename(src)))


def capped_line_count(path, cap=2_000_000):
    """Count lines in `path` without loading it into memory, stopping (and
    reporting a lower bound) once `cap` lines are seen -- protects the sweep
    from a submission that (like formula_s's tier(a) 508 MB `ranked.tsv`)
    ignores its filter and writes millions of rows."""
    n = 0
    truncated = False
    with open(path, "rb") as fh:
        for _ in fh:
            n += 1
            if n >= cap:
                truncated = True
                break
    return n, truncated


def capped_read_lines(path, cap=200_000):
    """First `cap` lines of `path` as str, decoded permissively. Used instead
    of a full read()/pandas load so a pathologically large output file is
    bounded in both the memory and the time this harness spends on it."""
    out = []
    with open(path, "r", errors="replace") as fh:
        for i, line in enumerate(fh):
            if i >= cap:
                break
            out.append(line)
    return out


# ---------------------------------------------------------------------------
# mzML surgery, shared by mass_reader_s and features_s perturbations.
#
# Both real files here (`data/mass_reader/*.mzML`, `data/feature_extraction/
# BSA1_F1.mzML`) are plain top-to-bottom XML with no compression across
# spectra; `BSA1_F1.mzML` additionally wraps the document in <indexedmzML>
# with a trailing byte-offset <indexList> that only a random-access reader
# would consult. Neither this harness's trusted reference
# (bench/reference/lib/mzml_reader.py) nor a submitted mzml_reader.py written
# to the prompt's spec uses that index -- both do a single linear
# ElementTree.iter() pass -- so dropping the wrapper and re-numbering the
# <spectrum> blocks in place is a safe, well-formed edit: no byte offset in
# the file is consulted by anything the harness runs.
# ---------------------------------------------------------------------------

_MZML_OPEN = re.compile(r"<mzML[ >]")
_SPECTRUM_LIST = re.compile(
    r'(<spectrumList\b[^>]*\bcount=")(\d+)("[^>]*>)(.*?)(</spectrumList>)',
    re.DOTALL)
_SPECTRUM = re.compile(r"<spectrum\b.*?</spectrum>", re.DOTALL)
_INDEX_ATTR = re.compile(r'(<spectrum\b[^>]*\bindex=")\d+(")')


def mzml_only(text):
    """The substalone `<mzML ...>...</mzML>` document, dropping any outer
    `<indexedmzML>` wrapper and its trailing index/checksum (which would
    otherwise reference now-stale byte offsets after an edit)."""
    m = _MZML_OPEN.search(text)
    if not m:
        raise ValueError("no <mzML> element found")
    start = m.start()
    end = text.rfind("</mzML>")
    if end == -1:
        raise ValueError("no closing </mzML> found")
    end += len("</mzML>")
    decl = "<?xml version=\"1.0\" encoding=\"ISO-8859-1\"?>\n"
    return decl + text[start:end]


def split_spectra(text):
    """(prefix, count_str, body, spectra_blocks, suffix) for the single
    <spectrumList> in an mzML-only document (see mzml_only). `spectra_blocks`
    is the list of individual <spectrum>...</spectrum> strings in document
    order."""
    m = _SPECTRUM_LIST.search(text)
    if not m:
        raise ValueError("no <spectrumList> found")
    body = m.group(4)
    blocks = _SPECTRUM.findall(body)
    return text[:m.start()], m.group(1), m.group(3), blocks, text[m.end():]


def rebuild_mzml(prefix, open_attrs, close_attrs, blocks, suffix):
    """Reassemble an mzML document from split_spectra's pieces after
    filtering `blocks`, re-numbering each kept block's index="" attribute
    sequentially and updating spectrumList's count="" to match."""
    renumbered = []
    for i, b in enumerate(blocks):
        renumbered.append(_INDEX_ATTR.sub(r"\g<1>%d\g<2>" % i, b, count=1))
    new_list = "%s%d%s%s%s" % (open_attrs, len(blocks), close_attrs,
                               "".join(renumbered), "</spectrumList>")
    return prefix + new_list + suffix


def keep_spectra(src_path, dst_path, predicate):
    """Write dst_path as src_path's mzML with only the <spectrum> blocks for
    which predicate(index, block_text) is True, everything else (instrument
    metadata, cvParams, ...) preserved verbatim. Returns (kept, total)."""
    text = mzml_only(read_text(src_path))
    prefix, open_attrs, close_attrs, blocks, suffix = split_spectra(text)
    kept = [b for i, b in enumerate(blocks) if predicate(i, b)]
    write_text(dst_path, rebuild_mzml(prefix, open_attrs, close_attrs, kept, suffix))
    return len(kept), len(blocks)
