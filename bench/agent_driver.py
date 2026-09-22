#!/usr/bin/env python3
"""Minimal, auditable agentic driver for an OpenAI-compatible endpoint.

Replaces the `pi` harness the earlier measurements used, which is not public and
is absent from this machine. Being publishable is a feature, not a concession:
a study whose harness cannot be inspected cannot be reproduced, and the
manuscript's own reporting checklist asks for exactly what this file records.

Contract (docs/CROSS_HARNESS_TEST_PACK.md §2), enforced here rather than trusted:

  * one fresh workspace per cell, supplied by the caller; cwd of every tool call
  * the prompt is sent verbatim as the single user message; an operator wrapper,
    if any, goes in the system message and is hashed separately
  * exactly one tool, `bash`. One tool keeps transcripts comparable across models
    and keeps the tool-call surface identical between harnesses
  * no network for the agent: proxy vars cleared, egress commands refused, and
    the attempt recorded as `network_attempted` rather than silently allowed
  * every cap that fires is recorded in `failure_mode`, never silently absorbed
  * usage is summed from ONE source (the per-response `usage` dict). The p3 sweep
    published a doubled token count because two files carried the same dict

Exit code is 0 whenever the session ran to a definite end, including a capped or
refused one; the caller distinguishes outcomes by reading meta.json, not by rc.
"""
import argparse, calendar, hashlib, json, os, re, shlex, signal, subprocess, sys, time, urllib.error, urllib.request

TOOLS = [{
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Run a shell command in the working directory and return its combined "
                       "stdout and stderr. The working directory persists between calls.",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string", "description": "The shell command to run"}},
            "required": ["command"],
        },
    },
}]

# Commands that would reach the network. The prompts are self-contained; a model
# that pip-installs pyopenms has not done the task. Matched on the command's
# words so that a filename containing "curl" does not trip it.
EGRESS = frozenset("curl wget nc ncat telnet ssh scp sftp rsync ftp pip pip3 "
                   "uv conda apt apt-get yum dnf brew npm npx yarn git".split())
# `pip install` is refused; `python3 -m pip` is caught by the module form below.
EGRESS_PHRASES = (re.compile(r"\bpython3?\s+-m\s+(pip|venv|ensurepip)\b"),
                  re.compile(r"\burllib\.request\b"),
                  re.compile(r"\brequests\.(get|post)\b"),
                  re.compile(r"\bsocket\.(create_connection|socket)\b"))

# llama.cpp, vLLM and the proxies in front of them each phrase this
# differently; match on the shared vocabulary rather than on one server's text.
_OVERFLOW_PAT = re.compile(
    r"context (?:window|length|size)|exceed\w* .{0,40}context|maximum context|"
    r"n_ctx|too (?:many|long).{0,30}token|ContextWindowExceeded|"
    r"reduce the length of the messages", re.I)


def _is_context_overflow(detail):
    return bool(_OVERFLOW_PAT.search(detail or ""))


# The server rejecting the MODEL's own tool call, because the arguments it
# emitted are not valid JSON. Seen only on dda_s, the tool whose program is
# largest: at ~11 kB of argument string the model's quoting breaks and
# llama.cpp returns HTTP 500. That is a property of the model under this
# prompt, not of the endpoint, so it must not be voided as infrastructure --
# doing so would delete the evidence that the heaviest tool is the one whose
# tool calls exceed what the model can emit correctly.
_MALFORMED_PAT = re.compile(
    r"failed to parse tool call|tool call arguments as JSON|"
    r"invalid (?:tool call|function call) arguments", re.I)


def _is_malformed_tool_call(detail):
    return bool(_MALFORMED_PAT.search(detail or ""))


class _MalformedToolCall(Exception):
    """The model emitted tool-call arguments the server could not parse."""


class _ContextOverflow(Exception):
    """The conversation no longer fits the server's context window."""


class _Terminated(Exception):
    """SIGTERM/SIGHUP, raised so the session unwinds and records itself."""


TOOL_OUTPUT_BUDGET = 10000      # chars returned to the model per tool call
TOOL_TIMEOUT = 600              # s per individual command


def sha256_text(s):
    return hashlib.sha256(s.encode()).hexdigest()


def egress_attempt(command):
    """The reason this command is refused, or None. Conservative by design: a
    false refusal is visible in the transcript and costs one turn; a missed one
    silently invalidates the cell."""
    for pat in EGRESS_PHRASES:
        if pat.search(command):
            return "matched %s" % pat.pattern
    try:
        words = shlex.split(command)
    except ValueError:
        words = command.split()
    for w in words:
        base = os.path.basename(w)
        if base in EGRESS:
            return "invokes %s" % base
    return None


def run_bash(command, workspace, env):
    """Execute one tool call. Returns (text_for_model, record_dict)."""
    refused = egress_attempt(command)
    if refused:
        msg = ("REFUSED: this session has no network access (%s). The task is "
               "self-contained; use only the standard library, numpy, pandas and "
               "scipy, which are already installed." % refused)
        return msg, {"command": command, "refused": refused, "rc": None}
    t0 = time.time()
    try:
        p = subprocess.run(["bash", "-lc", command], cwd=workspace, env=env,
                           capture_output=True, text=True, timeout=TOOL_TIMEOUT,
                           errors="replace")
        out, rc = (p.stdout or "") + (p.stderr or ""), p.returncode
    except subprocess.TimeoutExpired as exc:
        out = ((exc.stdout or b"").decode("utf-8", "replace")
               + (exc.stderr or b"").decode("utf-8", "replace")
               + "\n[command timed out after %d s]" % TOOL_TIMEOUT)
        rc = None
    dt = time.time() - t0
    full_len = len(out)
    if full_len > TOOL_OUTPUT_BUDGET:
        head = TOOL_OUTPUT_BUDGET * 2 // 3
        out = (out[:head] + "\n\n[... %d characters elided ...]\n\n"
               % (full_len - TOOL_OUTPUT_BUDGET) + out[-(TOOL_OUTPUT_BUDGET - head):])
    text = out if out.strip() else "[no output]"
    if rc is not None:
        text += "\n[exit code %d]" % rc
    return text, {"command": command, "rc": rc, "seconds": round(dt, 2),
                  "output_chars": full_len, "truncated": full_len > TOOL_OUTPUT_BUDGET}


# LiteLLM reports a token-budget 429 with the wall-clock time the window reopens.
# Parsing it is what turns a quota stall into a wait instead of a void cell:
# treating "you have used your tokens for this hour" as a model failure would
# silently score the endpoint's billing policy as though it were the model's
# competence, which is exactly the class of mistake the void rule exists to stop.
RESET_RE = re.compile(r"Limit resets at:\s*([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2})")


def _seconds_until_reset(detail, cap):
    m = RESET_RE.search(detail)
    if not m:
        return None
    try:
        reset = time.mktime(time.strptime(m.group(1) + " UTC", "%Y-%m-%d %H:%M:%S %Z"))
        reset -= time.timezone if time.daylight == 0 else time.timezone
    except (ValueError, OverflowError):
        return None
    # time.mktime interprets in local time; correct back to UTC explicitly.
    reset = calendar.timegm(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"))
    wait = reset - time.time() + 5
    if wait <= 0:
        return 5.0
    return min(wait, cap)


def post(endpoint, key, body, timeout, retries=3, throttle_budget=3900.0, log=None):
    """One chat-completions call.

    Transport errors get a short exponential backoff. A token-quota 429 is
    different in kind: nothing is wrong, the budget window simply has not
    reopened, so the call waits for the stated reset and retries without
    consuming one of the transport attempts. `throttle_budget` bounds the total
    time a single call may spend waiting, so a misconfigured key cannot stall a
    grid forever -- it fails the cell with a diagnosable message instead.
    Every other 4xx is a configuration error and is raised unretried.
    """
    url = endpoint.rstrip("/") + "/chat/completions"
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    last, waited, attempt = None, 0.0, 0
    while attempt < retries:
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as fh:
                return json.loads(fh.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:600]
            if exc.code == 429:
                wait = _seconds_until_reset(detail, throttle_budget - waited)
                if wait is not None and wait > 0:
                    if log:
                        log("throttled", {"wait_s": round(wait, 1), "detail": detail})
                    time.sleep(wait)
                    waited += wait
                    continue          # deliberately not an attempt: nothing failed
                last = "HTTP 429 (quota, no parsable reset): %s" % detail
            elif _is_malformed_tool_call(detail):
                raise _MalformedToolCall(detail)
            elif _is_context_overflow(detail):
                # Checked BEFORE the generic 4xx branch, which would otherwise
                # swallow it: llama.cpp reports an overrun window as a plain
                # HTTP 400. Not a transport fault and not the model's fault --
                # the conversation outgrew the window, which is a result about
                # whether this prompt fits this model, not an error to retry.
                raise _ContextOverflow(detail)
            elif 400 <= exc.code < 500 and exc.code not in (408,):
                raise RuntimeError("HTTP %d (not retried): %s" % (exc.code, detail))
            else:
                last = "HTTP %d: %s" % (exc.code, detail)
        except Exception as exc:                      # transport, timeout, decode
            last = "%s: %s" % (type(exc).__name__, exc)
        attempt += 1
        if attempt < retries:
            time.sleep(2 ** attempt)
    raise RuntimeError("endpoint unreachable after %d attempts (%.0f s throttled): %s"
                       % (retries, waited, last))


def assistant_for_history(msg):
    """The assistant message as it goes back to the server: role, content and
    tool_calls only. `reasoning_content` is deliberately dropped -- it is kept in
    the transcript for diagnosis, but replaying it inflates every subsequent
    request and some servers reject it."""
    out = {"role": "assistant", "content": msg.get("content") or ""}
    if msg.get("tool_calls"):
        out["tool_calls"] = [{"id": tc["id"], "type": "function",
                              "function": {"name": tc["function"]["name"],
                                           "arguments": tc["function"]["arguments"]}}
                             for tc in msg["tool_calls"]]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--key", default=os.environ.get("AGENT_API_KEY", ""))
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--wrapper-file", default=None,
                    help="operator wrapper, sent as the system message")
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--max-iters", type=int, default=80)
    ap.add_argument("--max-wall", type=float, default=2700.0)
    ap.add_argument("--max-output-tokens", type=int, default=400000,
                    help="cumulative cap across the session; guards the reasoning "
                         "spiral the p3 sweep saw in ~4%% of remote cells")
    ap.add_argument("--max-tokens", type=int, default=16384,
                    help="per-response cap sent to the server")
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--request-timeout", type=float, default=900.0)
    ap.add_argument("--expect-served", default=None,
                    help="substring the served model name must contain; use when "
                         "the server echoes a file path rather than an alias")
    ap.add_argument("--disable-fallbacks", action="store_true",
                    help="ask the proxy not to fall back to another model "
                         "(unverified; the served-model check is the guarantee)")
    ap.add_argument("--allow-substitution", action="store_true",
                    help="do not abort when the proxy serves a different model "
                         "than requested; the substitution is still recorded")
    ap.add_argument("--single-shot", action="store_true",
                    help="no tools, one turn: the model must emit the program blind")
    args = ap.parse_args()

    prompt = open(args.prompt_file).read()
    wrapper = open(args.wrapper_file).read() if args.wrapper_file else ""
    os.makedirs(args.workspace, exist_ok=True)

    # The agent's shell: pinned interpreter first on PATH, proxies stripped.
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    venv_bin = os.path.join(repo, ".venv-bench", "bin")
    env = {k: v for k, v in os.environ.items()
           if k.lower() not in ("http_proxy", "https_proxy", "all_proxy", "ftp_proxy")}
    env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")
    for var in ("AGENT_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_BASE_URL"):
        env.pop(var, None)

    messages = ([{"role": "system", "content": wrapper}] if wrapper else []) \
        + [{"role": "user", "content": prompt}]

    meta = {
        "endpoint": args.endpoint, "model": args.model,
        "prompt_sha256": sha256_text(prompt),
        "wrapper_sha256": sha256_text(wrapper) if wrapper else None,
        "arm": "single_shot" if args.single_shot else "agentic",
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "max_iters": args.max_iters, "max_wall": args.max_wall,
        "max_output_tokens": args.max_output_tokens, "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "iterations": 0, "assistant_turns": 0,
        "tokens": {"input": 0, "output": 0},
        "tool_calls": 0, "refused_commands": 0,
        "failure_mode": None, "finish_reasons": [], "throttled_s": 0.0,
        # What actually answered, as opposed to what was asked for. These are
        # not bookkeeping: the proxy in front of these models is configured with
        # silent fallbacks (gemma4 -> qwen3.8-27b-gptq -> openrouter-free, and
        # the reverse), so a request for one model can be served by another with
        # a 200 and no warning. A study whose own reporting checklist asks for
        # "model and version" cannot take the requested name as the answer.
        "served_models": [], "fingerprints": [], "model_substituted": False,
    }

    tr = open(args.transcript, "w")

    def log(kind, payload):
        if kind == "throttled":
            meta["throttled_s"] += payload.get("wait_s", 0.0)
        tr.write(json.dumps({"t": round(time.time() - t0, 3), "kind": kind,
                             "payload": payload}) + "\n")
        tr.flush()

    # A SIGTERM must unwind through the `finally` below rather than killing the
    # process where it stands. Without this, a terminated cell leaves a
    # transcript but no meta.json, and downstream that is indistinguishable
    # from "the model produced nothing" -- which is how several cells of the
    # cross-model arm came to be scored 0/6 for an infrastructure event.
    def _on_term(signum, frame):
        raise _Terminated()
    for _sig in (signal.SIGTERM, signal.SIGHUP):
        try:
            signal.signal(_sig, _on_term)
        except (ValueError, OSError):
            pass

    t0 = time.time()
    log("config", {k: v for k, v in vars(args).items() if k != "key"})
    log("messages_initial", messages)

    try:
        while True:
            if time.time() - t0 - meta["throttled_s"] > args.max_wall:
                meta["failure_mode"] = "wall_clock_cap"
                break
            if meta["assistant_turns"] >= args.max_iters:
                meta["failure_mode"] = "iteration_cap"
                break
            if meta["tokens"]["output"] >= args.max_output_tokens:
                meta["failure_mode"] = "output_token_cap"
                break

            body = {"model": args.model, "messages": messages,
                    "max_tokens": args.max_tokens}
            if args.disable_fallbacks:
                # Best-effort only, and deliberately NOT relied upon: it could
                # not be verified, because the only way to test it is to make
                # the requested model unavailable, and a request that returns
                # the right model proves nothing about whether a fallback was
                # disabled or simply never needed. The guarantee remains the
                # served-model check below, which has caught real substitutions.
                body["disable_fallbacks"] = True
            if not args.single_shot:
                body["tools"] = TOOLS
            if args.temperature is not None:
                body["temperature"] = args.temperature

            try:
                resp = post(args.endpoint, args.key, body, args.request_timeout, log=log)
            except _MalformedToolCall as exc:
                meta["failure_mode"] = "malformed_tool_call"
                meta["error"] = str(exc)[:400]
                log("malformed_tool_call", {"turn": meta["assistant_turns"],
                                            "detail": str(exc)[:300]})
                break
            except _ContextOverflow as exc:
                meta["failure_mode"] = "context_overflow"
                meta["error"] = str(exc)[:400]
                log("context_overflow", {"turn": meta["assistant_turns"],
                                         "detail": str(exc)[:300]})
                break
            except RuntimeError as exc:
                meta["failure_mode"] = "endpoint_error"
                meta["error"] = str(exc)
                log("endpoint_error", str(exc))
                break

            served = resp.get("model")
            fp = resp.get("system_fingerprint")
            if served and served not in meta["served_models"]:
                meta["served_models"].append(served)
            if fp and fp not in meta["fingerprints"]:
                meta["fingerprints"].append(fp)
            # LiteLLM echoes the requested alias when it serves that model, and
            # the BACKEND's own name when a fallback fires. A mismatch is
            # therefore a substitution, and a substituted cell is not a
            # measurement of the model it was supposed to test.
            # What counts as "the right model" depends on what is being talked
            # to. A LiteLLM route echoes the requested alias; a raw llama.cpp
            # server echoes the path of the gguf it loaded. --expect-served
            # names the identity to assert in the latter case, as a substring,
            # so the check stays meaningful when the served string is a path
            # rather than an alias.
            expected = args.expect_served or args.model
            ok = (expected in served) if args.expect_served else (served == expected)
            if served and not ok and not args.allow_substitution:
                meta["model_substituted"] = True
                meta["failure_mode"] = "model_substituted"
                meta["substitution"] = ("expected %r, served %r"
                                        % (expected, served))
                log("model_substituted", meta["substitution"])
                break

            usage = resp.get("usage") or {}
            meta["tokens"]["input"] += usage.get("prompt_tokens", 0) or 0
            meta["tokens"]["output"] += usage.get("completion_tokens", 0) or 0
            meta["assistant_turns"] += 1

            choice = (resp.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            finish = choice.get("finish_reason")
            meta["finish_reasons"].append(finish)
            log("assistant", {"finish_reason": finish, "usage": usage,
                              "content": msg.get("content"),
                              "reasoning_content": msg.get("reasoning_content"),
                              "tool_calls": msg.get("tool_calls")})

            messages.append(assistant_for_history(msg))
            calls = msg.get("tool_calls") or []

            if args.single_shot:
                meta["single_shot_reply"] = msg.get("content") or ""
                break
            if not calls:
                # A clean stop with no tool call. If the model never called a tool
                # at all, that is the reasoning-spiral signature, not completion.
                if meta["tool_calls"] == 0 and finish != "stop":
                    meta["failure_mode"] = "reasoning_spiral"
                elif meta["tool_calls"] == 0:
                    meta["failure_mode"] = "no_tool_calls"
                break
            if finish == "length":
                meta["failure_mode"] = "response_truncated"

            for tc in calls:
                meta["tool_calls"] += 1
                meta["iterations"] += 1
                name = tc["function"]["name"]
                raw = tc["function"]["arguments"] or "{}"
                try:
                    cmd = json.loads(raw).get("command", "")
                except ValueError:
                    cmd = ""
                if name != "bash" or not cmd:
                    text, rec = ("ERROR: call bash with a non-empty `command` string.",
                                 {"command": raw, "rc": None, "malformed": True})
                else:
                    text, rec = run_bash(cmd, args.workspace, env)
                if rec.get("refused"):
                    meta["refused_commands"] += 1
                    meta["failure_mode"] = meta["failure_mode"] or "network_attempted"
                log("tool", rec)
                log("tool_result", {"id": tc["id"], "chars": len(text)})
                messages.append({"role": "tool", "tool_call_id": tc["id"],
                                 "content": text})
    except _Terminated:
        meta["failure_mode"] = "terminated"
    except KeyboardInterrupt:
        meta["failure_mode"] = "interrupted"
    finally:
        meta["wall_clock_elapsed_s"] = round(time.time() - t0, 1)
        meta["wall_clock_agent_s"] = round(time.time() - t0 - meta["throttled_s"], 1)
        meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        log("meta", meta)
        tr.close()
        with open(args.meta, "w") as fh:
            json.dump(meta, fh, indent=1)
    print(json.dumps({k: meta[k] for k in
                      ("failure_mode", "iterations", "assistant_turns",
                       "wall_clock_agent_s", "tokens")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
