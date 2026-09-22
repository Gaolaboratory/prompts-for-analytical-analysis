# bench — harness, graders, tests

## Running the tests

Use the pinned bench venv's interpreter, **not** the `python3` on PATH:

```sh
cd bench/tests && ../../.venv-bench/bin/python3 -m unittest discover -s . -t .
```

The short-track graders (`grade_pca_s.py`, `grade_features_s.py`,
`grade_titration_s.py`) and their fixtures import numpy/pandas, which the
Homebrew `python3` does not have — running the suite with plain
`python3 -m unittest discover` fails with `ModuleNotFoundError: numpy` in every
test that touches them.

If `.venv-bench/` is missing, build it first (pinned versions from
`requirements-bench.txt`, and `venv_setup._stack_ok` refuses a venv whose
versions differ from those pins):

```sh
python3 bench/venv_setup.py       # prints the interpreter path
```

`run_bench.main()` calls `venv_setup.activate_path()` itself, so `python3`
inside an agent session, inside a grader, and inside a re-executed tool command
all mean this interpreter.

## Layout

- `run_bench.py` — one fresh agent session per cell, then offline re-execution
  of the pinned commands and external grading. Cells live in
  `bench/runs/<tool>[_<mode>]/<model>/<rep>/`; the `_<mode>` segment appears only
  for specs that declare more than one entry in `modes`, so the two dependency
  resolution modes cannot overwrite each other.
- `graders/` — one external grader per tool; `graders/_grading.py` holds the
  shared PASS/FAIL/summary helpers and `num_field()`, the single implementation
  of "read `key=<number>` from a tool's stdout".
- `reference/` — reference implementations. `reference/lib/` is imported by both
  tracks; `reference/short/` holds the short-track references the graders
  recompute their expectations from.
- `tests/fixtures.py` — conformant artifacts per tool (what a correct submission
  looks like) plus the `--dry-run` stubs. A dry-run cell records
  `"dry_run": true` in `meta.json` and is excluded from `report.py`.
