#!/usr/bin/env python3
"""read_mgf(path) -> [spectrum dict, ...] — same shape read_mzml returns."""


def read_mgf(path):
    spectra, cur = [], None
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        if line == "BEGIN IONS":
            cur = {"id": None, "ms_level": 2, "rt": None, "precursor_mz": None,
                   "precursor_charge": None, "mz": [], "intensity": []}
        elif line == "END IONS":
            if cur is not None:
                spectra.append(cur)
            cur = None
        elif cur is None:
            continue
        elif "=" in line and not line[0].isdigit():
            key, _, val = line.partition("=")
            key, val = key.upper(), val.strip()
            if key == "TITLE" and cur["id"] is None:
                cur["id"] = val
            elif key == "SCANS":
                cur["id"] = "scan=%s" % val.split()[0]
            elif key == "RTINSECONDS":
                cur["rt"] = float(val.split()[0])
            elif key == "PEPMASS":
                cur["precursor_mz"] = float(val.split()[0])
            elif key == "CHARGE":
                cur["precursor_charge"] = int(val.rstrip("+-") or 0) or None
        else:
            parts = line.split()
            if len(parts) >= 2:
                try:
                    mz, it = float(parts[0]), float(parts[1])
                except ValueError:
                    continue
                cur["mz"].append(mz)
                cur["intensity"].append(it)
    return spectra


if __name__ == "__main__":
    import sys
    for s in read_mgf(sys.argv[1]):
        print("%s ms%d rt=%s pmz=%s z=%s peaks=%d"
              % (s["id"], s["ms_level"], s["rt"], s["precursor_mz"],
                 s["precursor_charge"], len(s["mz"])))
