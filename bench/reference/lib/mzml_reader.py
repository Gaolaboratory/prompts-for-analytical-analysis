#!/usr/bin/env python3
"""read_mzml(path) -> [spectrum dict, ...]. Std-lib only.

Encoding and compression cvParams are flags: presence of the accession is the
signal, never a non-empty `value` attribute. rt is always returned in seconds.
"""
import base64
import struct
import zlib
import xml.etree.ElementTree as ET

NS = "{http://psi.hupo.org/ms/mzml}"
MS_LEVEL, SCAN_TIME = "MS:1000511", "MS:1000016"
SEL_MZ, CHARGE = "MS:1000744", "MS:1000041"
MZ_ARRAY, INT_ARRAY = "MS:1000514", "MS:1000515"
F64, F32, ZLIB = "MS:1000523", "MS:1000521", "MS:1000574"
SECONDS, MINUTES = "UO:0000010", "UO:0000031"


def _params(el):
    return {c.get("accession"): c for c in el.iter(NS + "cvParam")}


def _decode(bda):
    acc = _params(bda)
    raw = base64.b64decode((bda.find(NS + "binary").text or "").strip() or "")
    if ZLIB in acc:
        raw = zlib.decompress(raw)
    if F32 in acc and F64 not in acc:
        return list(struct.unpack("<%df" % (len(raw) // 4), raw))
    return list(struct.unpack("<%dd" % (len(raw) // 8), raw))


def read_mzml(path):
    spectra = []
    for sp in ET.parse(path).getroot().iter(NS + "spectrum"):
        top = {c.get("accession"): c for c in sp.findall(NS + "cvParam")}
        out = {"id": sp.get("id"),
               "ms_level": int(top[MS_LEVEL].get("value")) if MS_LEVEL in top else None,
               "rt": None, "precursor_mz": None, "precursor_charge": None,
               "mz": [], "intensity": []}
        scan = sp.find("%sscanList/%sscan" % (NS, NS))
        if scan is not None:
            p = _params(scan)
            if SCAN_TIME in p:
                cv = p[SCAN_TIME]
                rt = float(cv.get("value"))
                out["rt"] = rt * 60.0 if cv.get("unitAccession") == MINUTES else rt
        ion = sp.find("%sprecursorList/%sprecursor/%sselectedIonList/%sselectedIon"
                      % (NS, NS, NS, NS))
        if ion is not None:
            p = _params(ion)
            if SEL_MZ in p:
                out["precursor_mz"] = float(p[SEL_MZ].get("value"))
            if CHARGE in p:
                out["precursor_charge"] = int(p[CHARGE].get("value"))
        for bda in sp.iter(NS + "binaryDataArray"):
            acc = _params(bda)
            if MZ_ARRAY in acc:
                out["mz"] = _decode(bda)
            elif INT_ARRAY in acc:
                out["intensity"] = _decode(bda)
        spectra.append(out)
    return spectra


if __name__ == "__main__":
    import sys
    # Default output is the one line examples/mass_reader/PROMPT.md mandates:
    #   spectra=<n> ms1=<n> ms2=<n> rt_first=<s> rt_last=<s> tic=<total>
    # grade_mass_reader_s grades it, and this file is what the conformant
    # fixture and the prebuilt stub install, so it has to conform.
    # The older track (examples/mass_reader/minimal_readers_prompt.md: "Give each
    # reader a main printing a one-line-per-spectrum summary") asks for the
    # per-spectrum listing instead, so that behaviour is kept behind a flag
    # rather than deleted.
    args = [a for a in sys.argv[1:] if a != "--per-spectrum"]
    spectra = read_mzml(args[0])
    if "--per-spectrum" in sys.argv[1:]:
        for s in spectra:
            print("%s ms%s rt=%s pmz=%s z=%s peaks=%d"
                  % (s["id"], s["ms_level"], s["rt"], s["precursor_mz"],
                     s["precursor_charge"], len(s["mz"])))
    else:
        rts = [s["rt"] for s in spectra if s["rt"] is not None]
        print("spectra=%d ms1=%d ms2=%d rt_first=%s rt_last=%s tic=%s"
              % (len(spectra),
                 sum(1 for s in spectra if s["ms_level"] == 1),
                 sum(1 for s in spectra if s["ms_level"] == 2),
                 rts[0] if rts else "", rts[-1] if rts else "",
                 sum(float(v) for s in spectra for v in s["intensity"])))
