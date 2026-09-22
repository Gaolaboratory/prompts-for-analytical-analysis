#!/usr/bin/env python3
"""Idempotently merge the benchmark providers into ~/.pi/agent/models.json.

One provider entry per endpoint bench/specs.py's MODELS/_LOCAL_MIRRORS
actually names. As of commit 54d7ab0 (2026-09-11), "local" (llm-host)
is a single llama.cpp endpoint, not a mirrored pair: it used to be paired
with old-llm-host, but that host now serves an unrelated model
(MinerU2.5-Pro-2605-1.2B, a 1.2B document-parsing model) and specs.py's
_LOCAL_MIRRORS has had only one entry since that commit. Do not re-add a
"local-llamacpp-b" entry pointing at .78.67.29 unless specs.py's
_LOCAL_MIRRORS gains a second, genuinely-mirrored endpoint again -- registering
a stale mirror here is not cosmetic, since this script writes the user's real
~/.pi/agent/models.json.

The mirror MACHINERY itself (specs.model_mirrors(), run_bench.worker()'s
multi-thread dispatch across a model's mirrors, commit 73704ee) is not dead:
it is exercised by bench/tests/test_mirrors.py against fixture model keys,
and stays in the codebase so a future genuinely-mirrored topology (e.g. a
second host serving the same local model again) can register a "mirrors"
list on a MODELS entry and have it picked up with no code change. It is
simply dormant today: no live MODELS entry in bench/specs.py currently
carries a "mirrors" key, because "local" is presently a lone endpoint.
"""
import json, os

CFG = os.path.expanduser("~/.pi/agent/models.json")
PROVIDERS = {
    "local-llamacpp": {
        "baseUrl": "http://llm-host:35188/v1", "api": "openai-completions",
        "apiKey": "none",
        "models": [{"id": "/home/ygao/models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf", "contextWindow": 131072, "maxTokens": 65536}],
    },
    "remote-vllm": {
        "baseUrl": "http://vllm-host:8000/v1", "api": "openai-completions",
        "apiKey": "none",
        "models": [{"id": "Qwen/Qwen3.8-27B-FP8", "contextWindow": 131072, "maxTokens": 65536}],
    },
}

def main():
    cfg = {}
    if os.path.exists(CFG):
        with open(CFG) as fh:
            cfg = json.load(fh)
    cfg.setdefault("providers", {}).update(PROVIDERS)
    os.makedirs(os.path.dirname(CFG), exist_ok=True)
    with open(CFG, "w") as fh:
        json.dump(cfg, fh, indent=2)
    print("updated", CFG)

if __name__ == "__main__":
    main()
