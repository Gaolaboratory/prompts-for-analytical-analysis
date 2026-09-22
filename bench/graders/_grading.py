"""Shared grader helpers: uniform PASS/FAIL lines, k/n summary, exit code."""
import json, os, re, sys


def num_field(text, key):
    """Value of a `key=<number>` field in `text` as a float, or None.

    The one implementation of "read `key=<number>` from a tool's stdout", shared
    by every grader that has to do it (three divergent copies existed before).
    Four behaviours are load-bearing and each has a mutation test:

    - an absent key yields None;
    - a present-but-empty value ("Veq= ") yields None, because at least one
      numeric character is required;
    - a present-but-non-numeric value ("ms1_scans=many") yields None;
    - a longer field that merely *ends with* the searched key ("npoints=19"
      searched for "points", "total_ms1_scans=" for "ms1_scans") does not
      satisfy it: the left lookbehind anchors the key at a field boundary.
    """
    m = re.search(r"(?<![A-Za-z0-9_])" + re.escape(key) + r"=([-+0-9.eE]+)",
                  text or "")
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None

def require_files(*paths):
    missing = [p for p in paths if not os.path.isfile(p)]
    for p in missing:
        print("FAIL missing artifact %s" % p)
    if missing:
        sys.exit(1)

def session_text_excluding_user(path):
    """Concatenated text of NON-user messages in a pi session JSONL transcript.

    pi sessions open with the user message = the benchmark prompt, so a
    whole-file scan passes vacuously on the prompt echo. This collects the
    text content of assistant/toolResult records only (agent-side evidence).
    Unparseable lines are skipped; a missing/unreadable file yields "".
    Also tolerates the events.jsonl variant ("message_end" wrapping a
    "message" object) so both transcript flavours can be scanned.
    """
    try:
        fh = open(path, errors="replace")
    except OSError:
        return ""
    parts = []
    with fh:
        for line in fh:
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if not isinstance(obj, dict) or obj.get("type") not in ("message", "message_end"):
                continue
            msg = obj.get("message")
            if not isinstance(msg, dict) or msg.get("role") == "user":
                continue
            content = msg.get("content")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for p in content:
                    if isinstance(p, dict) and p.get("type") == "text":
                        parts.append(str(p.get("text", "")))
    return "\n".join(parts)

def finish(checks):
    for name, ok in checks:
        print(("PASS" if ok else "FAIL"), name)
    passed = sum(1 for _, ok in checks if ok)
    print("%d/%d passed" % (passed, len(checks)))
    sys.exit(0 if passed == len(checks) else 1)
