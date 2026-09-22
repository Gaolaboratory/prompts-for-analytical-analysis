#!/usr/bin/env python3
"""The interpreter the short-prompt track runs on.

Prompts in this track allow numpy, pandas and scipy. The `python3` on PATH is
Homebrew's, which has none of them, so the harness builds a pinned venv and
puts it first on PATH for the agent session, the graders, and the re-executed
tool commands alike. Versions are pinned because the expected values in
data/*/README.md were computed against them (mass_stats cites scipy 1.18.1).
"""
import json, os, subprocess, sys

BENCH = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BENCH)
VENV_DIR = os.path.join(REPO, ".venv-bench")
REQUIREMENTS = os.path.join(BENCH, "requirements-bench.txt")
PYTHON_VERSION = "3.13"
UV_TIMEOUT = 600            # generous; the point is that it is not infinite
PROBE_TIMEOUT = 120


def venv_python():
    return os.path.join(VENV_DIR, "bin", "python3")


def pinned_versions():
    """{import name: version} from requirements-bench.txt.

    Every requirement must be pinned with `==`; the import name equals the
    distribution name for the three packages here (numpy, pandas, scipy), which
    is what lets the probe below check them by importing.
    """
    pins = {}
    with open(REQUIREMENTS) as fh:
        for raw in fh:
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            if "==" not in line:
                raise RuntimeError("requirement is not == pinned: %r" % line)
            name, version = line.split("==", 1)
            pins[name.strip()] = version.strip()
    return pins


def _stack_ok(py):
    """True iff `py` has EXACTLY the pinned versions installed.

    Importability is not enough. The venv is first on PATH for agent sessions,
    graders and re-executed tool commands, so anything that pip-installs into it
    can silently repin the interpreter that every expected value in
    data/*/README.md was computed against (mass_stats cites scipy 1.18.1). A
    version mismatch therefore counts as "needs rebuild", not as "fine".
    """
    if not os.path.isfile(py):
        return False
    pins = pinned_versions()
    probe = ("import json, importlib\n"
             "print(json.dumps({m: importlib.import_module(m).__version__ "
             "for m in %r}))" % sorted(pins))
    try:
        proc = subprocess.run([py, "-c", probe], capture_output=True, text=True,
                              timeout=PROBE_TIMEOUT)
    except (subprocess.TimeoutExpired, OSError):
        return False
    if proc.returncode != 0:
        return False
    try:
        got = json.loads(proc.stdout or "{}")
    except ValueError:
        return False
    return got == pins


def _uv(args, what):
    """Run a uv command with a timeout and a diagnosable failure.

    Both calls sit on run_bench.main()'s critical path via activate_path(); with
    no timeout a hung uv hangs the whole benchmark with no output at all.
    """
    try:
        subprocess.run(args, check=True, capture_output=True, text=True,
                       timeout=UV_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise RuntimeError("%s timed out after %d s: %s"
                           % (what, UV_TIMEOUT, " ".join(args)))
    except FileNotFoundError:
        raise RuntimeError("%s failed: `uv` is not on PATH" % what)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("%s failed (exit %d): %s\n%s"
                           % (what, exc.returncode, " ".join(args),
                              (exc.stderr or exc.stdout or "").strip()))


def ensure_venv():
    """Build the venv if it is absent, incomplete or off its pins. Idempotent."""
    py = venv_python()
    if _stack_ok(py):
        return py
    # --clear rebuilds in place if VENV_DIR exists but is broken, partial or
    # repinned (interrupted install, manual tinkering, an agent pip-installing
    # into it, a version bump); uv venv otherwise refuses to touch an existing
    # venv directory.
    _uv(["uv", "venv", "--python", PYTHON_VERSION, "--clear", VENV_DIR],
        "creating the bench venv")
    _uv(["uv", "pip", "install", "--python", py, "-r", REQUIREMENTS],
        "installing the pinned bench requirements")
    if not _stack_ok(py):
        raise RuntimeError(
            "venv built but does not hold the pinned versions %s: %s"
            % (pinned_versions(), py))
    return py


def activate_path():
    """Prepend the venv's bin to PATH so `python3` means the bench interpreter."""
    ensure_venv()
    binned = os.path.join(VENV_DIR, "bin")
    parts = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p != binned]
    os.environ["PATH"] = os.pathsep.join([binned] + parts)
    return os.environ["PATH"]


if __name__ == "__main__":
    print(ensure_venv())
