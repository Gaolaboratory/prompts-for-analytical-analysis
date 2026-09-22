"""Per-tool run specs, transcribed from each TEST_PLAN.md tier (a) section.

seed      files copied into the fresh workspace before the agent starts. Since
          Phase 1 the data generators ship beside their prompts rather than
          inline, so the harness must place them; the agent runs them.
deps      tool names whose modules this prompt imports. Mirrors the prompt's
          ## Dependencies table; test_specs asserts the two agree.
modes     "solo"     -> the agent builds any missing dependency from its prompt
          "prebuilt" -> tested modules are seeded and must be reused unedited
artifacts files the AGENT must produce. Seeded files are excluded on purpose:
          a seeded generator would satisfy the check without the agent doing
          anything.
data      real input files copied into the fresh workspace, replacing gen_cmd for
          short-track prompts. A spec has gen_cmd xor data. Never name a file that
          holds the answer -- see ANSWER_FILES.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# "local" is served by two identical llama.cpp instances that expose the same
# model file under different absolute paths, so each needs its own provider
# entry and its own model id -- there is no single (provider, model) pair that
# resolves on both. _LOCAL_MIRRORS lists them; MODELS["local"]'s own
# provider/model/endpoint are set to the first mirror (rather than duplicated
# by hand) so the two can never drift apart, and so any caller that is not
# mirror-aware (run_tier_c.py, or run_bench.run_cell with no mirror passed)
# keeps using the one mirror that has been confirmed to work end-to-end.
# 2026-09-11: .16 now serves the Q4_K quantisation, and .78.67.29 serves an entirely
# different model (MinerU2.5-Pro-1.2B), so it is no longer a mirror of this one.
_LOCAL_MIRRORS = [
    {"provider": "local-llamacpp", "model": "/home/ygao/models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf",
     "endpoint": "http://llm-host:35188/v1"},
]

MODELS = {
    "local": dict(_LOCAL_MIRRORS[0]),
    "openrouter_gemma": {"provider": "openrouter", "model": "google/gemma-4-26b-a4b-it:free",
                         "endpoint": "https://openrouter.ai/api/v1", "provider_flag": True},
    "openrouter": {"provider": "openrouter", "model": "minimax/minimax-m3:free",
                   "endpoint": "https://openrouter.ai/api/v1", "provider_flag": True},
    "remote": {"provider": "remote-vllm", "model": "Qwen/Qwen3.8-27B-FP8",
               "endpoint": "http://vllm-host:8000/v1"},
}

def model_mirrors(model_key):
    """The interchangeable endpoints for a model key, each shaped like
    {"provider", "model", "endpoint"}. A model with no "mirrors" entry (e.g.
    "remote") gets a single-element list built from its own provider/model/
    endpoint, so a caller always sees at least one endpoint and the mirrored
    and unmirrored cases share one code path -- with exactly one mirror,
    dispatch across "all mirrors" is dispatch across the one endpoint that
    already existed, which is the behaviour-preserving case the mirrors
    feature must not disturb."""
    m = MODELS[model_key]
    if "mirrors" in m:
        return list(m["mirrors"])
    d = {"provider": m["provider"], "model": m["model"], "endpoint": m["endpoint"]}
    if m.get("provider_flag"):
        d["provider_flag"] = True
    return [d]

def _p(directory, name):
    return os.path.join(REPO, "examples", directory, name)

ANSWER_FILES = frozenset([
    "README.md", "expected_stats.tsv", "dad1_ref.csv",
    "analyze_chrom.py", "reference_features.py", "parse_dad1_uv.py",
])

def _d(tool, name):
    """Absolute path of a real input file under data/<tool>/."""
    return os.path.join(REPO, "data", tool, name)

SPECS = {
    "calibration": {
        "prompt": _p("calibration", "minimal_calibration_prompt.md"),
        "gen_cmd": "python3 make_cal_data.py",
        "run_cmd": "python3 calibrate.py standards.csv unknowns.csv -o results.tsv > stdout.txt",
        "grader": "grade_calibration.py",
        "grader_args": ["stdout.txt", "results.tsv", "{cell}/session.jsonl"],
        "artifacts": ['calibrate.py'],
        "seed": [_p("calibration", "make_cal_data.py")],
        "deps": [],
        "modes": ["solo"],
    },
    "chrom": {
        "prompt": _p("chrom_integration", "minimal_chrom_integration_prompt.md"),
        "gen_cmd": "python3 make_chrom_data.py",
        "run_cmd": "python3 chrom_integrate.py chrom.csv --noise 0 25 -o peaks.tsv > stdout.log",
        "grader": "grade_chrom.py",
        "grader_args": ["peaks.tsv", "stdout.log", "{cell}/session.jsonl"],
        "artifacts": ['chrom_integrate.py'],
        "seed": [_p("chrom_integration", "make_chrom_data.py")],
        "deps": [],
        "modes": ["solo"],
    },
    "nmr": {
        "prompt": _p("nmr_1d", "minimal_nmr_1d_prompt.md"),
        "gen_cmd": "python3 make_fid.py",
        "run_cmd": "python3 nmr_1d.py fid.csv -o multiplets.tsv > stdout.log 2> stderr.log",
        "grader": "grade_nmr_1d.py",
        "grader_args": ["multiplets.tsv", "stdout.log", "stderr.log"],
        "artifacts": ['nmr_1d.py'],
        "seed": [_p("nmr_1d", "make_fid.py")],
        "deps": [],
        "modes": ["solo"],
    },
    "pca": {
        "prompt": _p("pca_untargeted", "minimal_pca_prompt.md"),
        "gen_cmd": "python3 make_test_data.py",
        "run_cmd": "python3 pca.py features.csv -o scores.tsv --loadings loadings.tsv > stdout.txt",
        "grader": "grade_pca.py",
        "grader_args": [],
        "artifacts": ['pca.py'],
        "seed": [_p("pca_untargeted", "make_test_data.py")],
        "deps": [],
        "modes": ["solo"],
    },
    "uvvis": {
        "prompt": _p("uvvis_spectrum", "minimal_uvvis_prompt.md"),
        "gen_cmd": "python3 make_uvvis_data.py",
        "run_cmd": "python3 uvvis.py sample.csv -o peaks.tsv > stdout.txt 2> stderr.txt",
        "grader": "grade_uvvis.py",
        "grader_args": ["peaks.tsv", "stdout.txt", "stderr.txt"],
        "artifacts": ['uvvis.py'],
        "seed": [_p("uvvis_spectrum", "make_uvvis_data.py")],
        "deps": [],
        "modes": ["solo"],
    },
    "spectral": {
        "prompt": _p("spectral_library", "minimal_spectral_library_prompt.md"),
        "gen_cmd": "python3 make_test_data.py",
        "run_cmd": "python3 libsearch.py queries.txt library.txt -o results.tsv > stdout.log",
        "grader": "grade_spectral_library.py",
        "grader_args": ["results.tsv", "stdout.log"],
        "artifacts": ['libsearch.py'],
        "seed": [_p("spectral_library", "make_test_data.py")],
        "deps": [],
        "modes": ["solo"],
    },
    "formula": {
        "prompt": _p("formula_finder", "minimal_formula_finder_prompt.md"),
        "gen_cmd": "python3 make_test_data.py",
        "run_cmd": "python3 formula_finder.py measured.tsv -o ranked.tsv > stdout.log",
        "grader": "grade_formula_finder.py",
        "grader_args": ["measured.tsv", "ranked.tsv", "stdout.log"],
        "artifacts": ['formula_finder.py'],
        "seed": [_p("formula_finder", "make_test_data.py")],
        "deps": [],
        "modes": ["solo"],
    },
    "titration": {
        "prompt": _p("titration", "minimal_titration_prompt.md"),
        "gen_cmd": "python3 make_test_data.py",
        "run_cmd": "python3 titration.py titration.csv -o results.tsv > stdout.log",
        "grader": "grade_titration.py",
        "grader_args": ["."],
        "artifacts": ['titration.py'],
        "seed": [_p("titration", "make_test_data.py")],
        "deps": [],
        "modes": ["solo"],
    },
    "nmr_quad": {
        "prompt": _p("nmr_1d", "minimal_nmr_quad_prompt.md"),
        "gen_cmd": "python3 make_fid_quad.py",
        "run_cmd": "python3 nmr_quad.py fid_quad.csv -o multiplets.tsv > stdout.log 2> stderr.log",
        "grader": "grade_nmr_quad.py",
        "grader_args": ["multiplets.tsv", "stdout.log", "stderr.log"],
        "artifacts": ['nmr_quad.py'],
        "seed": [_p("nmr_1d", "make_fid_quad.py")],
        "deps": [],
        "modes": ["solo"],
    },
    "dda_v2": {
        "prompt": _p("database_search", "minimal_dda_search_v2_prompt.md"),
        "gen_cmd": "python3 make_search_data.py",
        "run_cmd": "python3 search.py bench.fasta bench.mgf -o psms.tsv > stdout.log 2> stderr.log",
        "grader": "grade_dda_v2.py",
        "grader_args": ["psms.tsv", "stdout.log"],
        "artifacts": ['search.py'],
        "seed": [_p("database_search", "make_search_data.py")],
        "deps": [],
        "modes": ["solo"],
    },
    "mass_reader_s": {
        "prompt": _p("mass_reader", "PROMPT.md"),
        "run_cmd": "python3 mzml_reader.py bsa_orbitrap_first40.mzML > stdout.log 2> stderr.log",
        "grader": "grade_mass_reader_s.py",
        "grader_args": [],
        "artifacts": ["fasta_reader.py", "mzml_reader.py"],
        "data": [_d("mass_reader", "ecoli_k12_48.fasta"),
                 _d("mass_reader", "bsa_orbitrap_first40.mzML"),
                 _d("mass_reader", "thermo_small_raw.mzML")],
        "deps": [],
        "modes": ["solo"],
    },
    "titration_s": {
        "prompt": _p("titration", "PROMPT.md"),
        "run_cmd": "python3 titration.py acetic_acid_naoh.csv -o results.tsv > stdout.log 2> stderr.log",
        "grader": "grade_titration_s.py",
        "grader_args": ["."],
        "artifacts": ["titration.py"],
        "data": [_d("titration", "acetic_acid_naoh.csv")],
        "deps": [],
        "modes": ["solo"],
    },
    "mass_stats_s": {
        "prompt": _p("mass_stats", "PROMPT.md"),
        "run_cmd": "python3 stats.py quant_mtbls14397_pos.csv groups.tsv -o stats.tsv > stdout.log 2> stderr.log",
        "grader": "grade_mass_stats_s.py",
        "grader_args": ["stats.tsv", "stdout.log"],
        "artifacts": ["stats.py"],
        "data": [_d("mass_stats", "quant_mtbls14397_pos.csv"),
                 _d("mass_stats", "groups.tsv")],
        "deps": [],
        "modes": ["solo"],
    },
    "pca_s": {
        "prompt": _p("pca_untargeted", "PROMPT.md"),
        "run_cmd": "python3 pca.py features.csv groups.csv -o scores.tsv > stdout.log 2> stderr.log",
        "grader": "grade_pca_s.py",
        "grader_args": ["scores.tsv", "stdout.log"],
        "artifacts": ["pca.py"],
        "data": [_d("pca", "features.csv"), _d("pca", "groups.csv")],
        "deps": [],
        "modes": ["solo"],
    },
    "features_s": {
        "prompt": _p("feature_extraction", "PROMPT.md"),
        "run_cmd": "python3 features.py BSA1_F1.mzML -o features.tsv > stdout.log 2> stderr.log",
        "grader": "grade_features_s.py",
        "grader_args": ["features.tsv", "stdout.log"],
        "artifacts": ["features.py"],
        "data": [_d("feature_extraction", "BSA1_F1.mzML")],
        "deps": ["mass_reader_s"],
        "modes": ["solo", "prebuilt"],
    },
    "calibration_s": {
        "prompt": _p("calibration", "PROMPT.md"),
        "run_cmd": "python3 calibrate.py norris.csv -o results.tsv > stdout.log 2> stderr.log",
        "grader": "grade_calibration_s.py",
        "grader_args": ["."],
        "artifacts": ["calibrate.py"],
        "data": [_d("calibration", "norris.csv")],
        "deps": [],
        "modes": ["solo"],
    },
    "uvvis_s": {
        "prompt": _p("uvvis_spectrum", "PROMPT.md"),
        "run_cmd": "python3 uvvis.py 4-nitrophenol.csv -o bands.tsv > stdout.log 2> stderr.log",
        "grader": "grade_uvvis_s.py",
        "grader_args": ["."],
        "artifacts": ["uvvis.py"],
        "data": [_d("uvvis", "4-nitrophenol.csv")],
        "deps": [],
        "modes": ["solo"],
    },
    "formula_s": {
        "prompt": _p("formula_finder", "PROMPT.md"),
        "run_cmd": "python3 formula_finder.py measured_caffeine.tsv -o ranked.tsv > stdout.log 2> stderr.log",
        "grader": "grade_formula_s.py",
        "grader_args": ["ranked.tsv", "stdout.log"],
        "artifacts": ["formula_finder.py"],
        "data": [_d("formula", "measured_caffeine.tsv")],
        "deps": [],
        "modes": ["solo"],
    },
    "spectral_s": {
        "prompt": _p("spectral_library", "PROMPT.md"),
        "run_cmd": "python3 libsearch.py queries.txt library.txt -o results.tsv > stdout.log 2> stderr.log",
        "grader": "grade_spectral_s.py",
        "grader_args": ["results.tsv", "stdout.log"],
        "artifacts": ["libsearch.py"],
        "data": [_d("spectral", "queries.txt"), _d("spectral", "library.txt")],
        "deps": [],
        "modes": ["solo"],
    },
    "chrom_s": {
        "prompt": _p("chrom_integration", "PROMPT.md"),
        "run_cmd": "python3 chrom_integrate.py chrom.csv -o peaks.tsv > stdout.log 2> stderr.log",
        "grader": "grade_chrom_s.py",
        "grader_args": ["."],
        "artifacts": ["chrom_integrate.py"],
        "data": [_d("chrom", "chrom.csv")],
        "deps": [],
        "modes": ["solo"],
    },
    "nmr_s": {
        "prompt": _p("nmr_1d", "PROMPT.md"),
        "run_cmd": "python3 nmr.py fid_complex.csv -o multiplets.tsv > stdout.log 2> stderr.log",
        "grader": "grade_nmr_s.py",
        "grader_args": ["multiplets.tsv", "stdout.log"],
        "artifacts": ["nmr.py"],
        "data": [_d("nmr", "fid_complex.csv")],
        "deps": [],
        "modes": ["solo"],
    },
    "dda_s": {
        "prompt": _p("database_search", "PROMPT.md"),
        "run_cmd": "python3 search.py yeast_pe1_plus_ups.fasta ups1_yeast_dda_first1200.mgf -o psms.tsv > stdout.log 2> stderr.log",
        "grader": "grade_dda_s.py",
        "grader_args": ["psms.tsv", "stdout.log"],
        "artifacts": ["search.py"],
        "data": [_d("database_search", "yeast_pe1_plus_ups.fasta"),
                 _d("database_search", "ups1_yeast_dda_first1200.mgf")],
        "deps": ["mass_reader_s"],
        "modes": ["solo", "prebuilt"],
    },
}
