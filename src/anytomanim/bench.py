"""Benchmark runner: the same topic, across models, with and without the toolchain.

Both arms run in neutral temporary workspaces with fresh HOME/CODEX_HOME, no
user config, rules, skills or memories, and the same local voice. Only the login
file and its lock are linked to the original store (never copied or inspected).
An offline, synthetic-credential probe checks that Codex preserves those links.

macOS Seatbelt wraps the whole process tree, limits writes, and denies personal
agent directories and .env files. Direct additionally cannot read this checkout,
optional configured private trees, or benchmark results. It requires an external
Python without anytomanim (suite.direct_python or ANYTOMANIM_BENCH_DIRECT_PYTHON).
Tools always imports this checkout's src, including in child commands. Codex's
inner sandbox is disabled: the outer sandbox owns enforcement, without relying
on nested Seatbelt support. API networking remains available; web search is off.

Artifacts are moved back to root/<cell>; existing result.json resumes without
another model call. isolation records an event-log scan, not proof of every read.
Unsupported platforms, failed sandbox probes and contaminated Python fail closed.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from .env import REPO, tex_bin
from .files import atomic_output

TIMEOUT = 45 * 60
# The outer sandbox must allow the API, so commands can reach the network too.
NETWORK_COMMAND = re.compile(r"\b(curl|wget|git\s+clone|pip3?\s+install|uv\s+pip|brew\s+install)\b")

COMMON = """用繁體中文製作一支 3Blue1Brown 風格的旁白解說影片。

主題：{topic}
長度：{lo} 到 {hi} 秒。規格：1280×720。觀眾：懂高中數學的人。

交付 `final.mp4`，放在目前目錄，要含旁白音訊與燒錄字幕。結束前自行檢查成品。

環境：
- Python 與 manim：{python}（用 `-m manim` 執行）。不要安裝任何東西。
- LaTeX 與 ffmpeg 已在 PATH。
- 語音只能用 macOS 本機語音 `say -v Tingting`。不使用網路語音服務或付費 TTS。
- 不要上網查資料、下載程式碼或素材。

規則：只在目前目錄寫檔。絕不開啟任何 `.env`。
最後用三行以內回報：做了什麼、算繪幾次、還有什麼問題。
"""

ARMS = {
    "direct": """
做法：自己直接寫 Manim 程式完成，可以使用已安裝的 manim 與 manim_voiceover 套件。
""",
    "tools": """
做法：使用 AnyToManim 工具鏈。先讀 {repo}/skills/anytomanim/SKILL.md，依它的流程做。
CLI 在 {repo}/.venv/bin/anytomanim，所有產物都放在目前目錄。
ANYTOMANIM_TTS=draft 已設定，`tts` 會使用同一個本機語音；720p 用 `--quality qm`。
""",
}


def prompt_for(suite: dict, topic: dict, arm: str) -> str:
    lo, hi = suite["seconds"]
    python = direct_python(suite) if arm == "direct" else REPO / ".venv/bin/python"
    return COMMON.format(topic=topic["topic"], lo=lo, hi=hi,
                         python=python) + ARMS[arm].format(repo=REPO)


def direct_python(suite: dict) -> Path:
    value = os.environ.get("ANYTOMANIM_BENCH_DIRECT_PYTHON") or suite.get("direct_python")
    if not value or not Path(value).expanduser().is_absolute():
        raise ValueError("set direct_python (or ANYTOMANIM_BENCH_DIRECT_PYTHON) to an absolute path")
    # Keep the venv entry point: resolving bin/python would discard its pyvenv.cfg.
    return Path(value).expanduser().absolute()


def _within(path: Path, roots: list[Path]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def _private_roots() -> list[Path]:
    home = Path.home()
    return [home / ".agents", home / ".codex", home / ".claude",
            Path(os.environ.get("CODEX_HOME", home / ".codex")).resolve()]


def _direct_roots(root: Path) -> list[Path]:
    paths = [REPO, root]
    paths.extend(Path(p).expanduser() for p in
                 os.environ.get("ANYTOMANIM_BENCH_BLOCKED_ROOTS", "").split(os.pathsep) if p)
    return list({p for path in paths for p in (path.absolute(), path.resolve())})


def _clean_env(base: Path, arm: str) -> dict:
    # Do not inherit shell init, Python paths, host-agent state or secret env vars.
    env = {k: os.environ[k] for k in ("LANG", "LC_ALL", "LC_CTYPE", "SSL_CERT_FILE",
                                    "SSL_CERT_DIR", "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY")
           if k in os.environ}
    for name in ("home", "state", "tmp"):
        (base / name).mkdir()
    env.update(HOME=str(base / "home"), CODEX_HOME=str(base / "state"),
               TMPDIR=str(base / "tmp"), ZDOTDIR=str(base / "home"),
               XDG_CONFIG_HOME=str(base / "home/.config"),
               XDG_CACHE_HOME=str(base / "home/.cache"),
               PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1",
               PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin")
    tex = tex_bin()  # Discover TinyTeX using the real HOME before replacing it.
    if tex:
        env["PATH"] = f"{tex}:{env['PATH']}"
    if arm == "tools":
        env.update(ANYTOMANIM_TTS="draft", PYTHONPATH=str(REPO / "src"))
    return env


def _validate_python(python: Path, wd: Path, env: dict, forbidden: list[Path]):
    locations = [python, python.resolve(), python.parent.parent.resolve()]
    # Inspect intermediate links too: bin/python may ultimately resolve to a
    # system executable while passing through a forbidden venv/checkout.
    pending = python
    for _ in range(40):
        current = Path(pending.anchor)
        parts = pending.parts
        for index, part in enumerate(parts[1:], 1):
            current /= part
            if current.is_symlink():
                target = current.readlink()
                pending = Path(os.path.abspath(target if target.is_absolute() else current.parent / target))
                locations.append(pending)
                pending = pending.joinpath(*parts[index+1:])
                locations.append(pending)
                break
        else:
            break
    else:
        raise ValueError("direct_python has too many symlinks")
    for path in locations:
        if _within(path, forbidden) or "anytomanim" in str(path).lower():
            raise ValueError("direct_python must be outside the project, worktrees and benchmark root")
    # Probe outside Seatbelt too: a denied import must not disguise an installed package.
    probe = subprocess.run([str(python), "-c", "import anytomanim"], cwd=wd, env=env,
                           capture_output=True, text=True, timeout=30)
    if probe.returncode != 1 or "No module named 'anytomanim'" not in probe.stderr:
        raise ValueError("direct_python must fail to import anytomanim with ModuleNotFoundError")


def _link_login(codex: str, base: Path, env: dict) -> list[Path]:
    """Check symlink-safe credential writes using dummy data; never open real auth."""
    state = Path(env["CODEX_HOME"])
    with tempfile.TemporaryDirectory(prefix="login-", dir=base) as scratch:
        scratch = Path(scratch)
        store = scratch / "store"
        store.mkdir()
        target = scratch / "synthetic-credential.json"
        target.write_text("{}")
        (store / "auth.json").symlink_to(target)
        probe_env = dict(env, CODEX_HOME=str(store))
        check = subprocess.run([codex, "-c", 'cli_auth_credentials_store="file"',
                                "login", "--with-api-key"], input="offline-compatibility-probe\n",
                               cwd=scratch, env=probe_env, capture_output=True, text=True, timeout=30)
        if check.returncode or not (store / "auth.json").is_symlink() or target.read_text() == "{}":
            raise RuntimeError("Codex cannot safely share credential symlinks; refusing to copy login")
    original = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).resolve()
    auth = original / "auth.json"
    if not auth.is_file():
        raise RuntimeError("benchmark requires an existing file-backed Codex login; keyring is not copied")
    # Share the write lock as well as the canonical credential file across cells.
    for name in ("auth.json", "auth.lock"):
        (state / name).symlink_to(original / name)
    return [auth.resolve(), (original / "auth.lock").resolve()]


def _sandbox_profile(base: Path, blocked: list[Path], login: list[Path]) -> str:
    quote = lambda path: json.dumps(str(path), ensure_ascii=False)
    # Credential rotation uses a private .auth-* temporary file beside auth.json.
    auth_temp = f"(regex {quote('^' + re.escape(str(login[0].parent)) + '/[.]auth-[^/]+$')})"
    access = [f"(literal {quote(p)})" for p in login] + [auth_temp]
    writable = [f"(subpath {quote(base)})", '(literal "/dev/null")'] + access
    rules = ["(version 1)", "(allow default)", "(deny appleevent-send)",
             "(deny file-write* (require-not (require-any " + " ".join(writable) + ")))",
             '(deny file-read* (regex "(^|/)[.]env($|[./])"))',
             f"(deny file-read* (literal {quote(base / 'policy.sb')}))"]
    for path in sorted({p for b in blocked for p in (b.absolute(), b.resolve())}):
        # Permit metadata on the login directory for atomic refresh, not its listing.
        exceptions = access + [f"(literal {quote(p.parent)})" for p in login]
        rules.append(f"(deny file-read* (require-all (subpath {quote(path)}) "
                     "(require-not (require-any " + " ".join(exceptions) + "))))")
    for parent in {p.parent for p in login}:
        rules.append(f"(deny file-read-data (literal {quote(parent)}))")
    return "\n".join(rules)


def _sandbox_prefix(base: Path, wd: Path, env: dict, profile: str) -> tuple[list[str], bool]:
    if sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file():
        raise RuntimeError("isolated benchmarks require macOS sandbox-exec")
    policy = base / "policy.sb"
    policy.write_text(profile)
    prefix = ["/usr/bin/sandbox-exec", "-f", str(policy)]
    probe = subprocess.run(prefix + ["/usr/bin/true"], cwd=wd, env=env,
                           capture_output=True, timeout=30)
    if probe.returncode:
        reason = probe.stderr.decode(errors="replace").strip()
        raise RuntimeError("outer Seatbelt sandbox unavailable; refusing an unisolated benchmark: " + reason)
    # Safe canaries prove that the wrapper enforces reads and writes before any
    # model starts. No private files (especially credentials or .env) are opened.
    read = subprocess.run(prefix + ["/bin/cat", str(policy)], cwd=wd, env=env,
                          capture_output=True, timeout=30)
    with tempfile.NamedTemporaryFile(prefix="check-", dir="/private/tmp") as outside:
        write = subprocess.run(prefix + ["/usr/bin/touch", outside.name], cwd=wd, env=env,
                               capture_output=True, timeout=30)
    if read.returncode == 0 or write.returncode == 0:
        raise RuntimeError("outer Seatbelt failed read/write canaries; refusing an unisolated benchmark")
    nested = subprocess.run(prefix + ["/usr/bin/sandbox-exec", "-p",
                                      "(version 1)(allow default)", "/usr/bin/true"],
                            cwd=wd, env=env, capture_output=True, timeout=30)
    return prefix, nested.returncode == 0


def scan_isolation(events: Path, arm: str, root: Path) -> dict:
    """Flag command/output references, including denied attempts; never echo log content."""
    paths = _private_roots() + (_direct_roots(root) if arm == "direct" else [])
    needles = {str(p).lower() for b in paths for p in (b, b.resolve())}
    needles.update(("~/.agents", "~/.codex", "~/.claude", "$home/.agents",
                    "$home/.codex", "$home/.claude"))
    if arm == "direct":
        needles.update(("anytomanim", "$home/projects"))
    violations, malformed, network = [], 0, 0
    for number, line in enumerate(events.read_text(errors="replace").splitlines(), 1):
        try:
            event = json.loads(line)
        except ValueError:
            malformed += 1
            continue
        item = event.get("item") or {}
        if item.get("type") not in ("command_execution", "function_call", "function_call_output"):
            continue
        if NETWORK_COMMAND.search(str(item.get("command", ""))):
            network += 1
        content = json.dumps(item, ensure_ascii=False).lower().replace("\\/", "/")
        for needle in sorted(needles):
            if needle in content:
                violations.append({"line": number, "match": needle})
    return {"version": 1, "scan_status": "violations" if violations else
            "incomplete" if malformed else "clean", "violations": violations,
            "malformed_lines": malformed, "network_commands": network}


def usage_of(events: Path) -> dict:
    """Sum token usage and count commands from a `codex exec --json` log."""
    totals, commands = {}, 0
    for line in events.read_text(errors="replace").splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "turn.completed":
            for k, v in (ev.get("usage") or {}).items():
                if isinstance(v, (int, float)):
                    totals[k] = totals.get(k, 0) + v
        item = ev.get("item") or {}
        if ev.get("type") == "item.completed" and item.get("type") == "command_execution":
            commands += 1
    return {"tokens": totals, "commands": commands}


def run_cell(suite: dict, root: Path, topic: dict, model: dict, arm: str) -> dict:
    cell = f"{topic['id']}__{model['id']}__{arm}"
    wd = root / cell
    result_file = wd / "result.json"
    if result_file.exists():
        return json.loads(result_file.read_text())
    wd.mkdir(parents=True, exist_ok=True)
    codex = shutil.which("codex")
    if not codex:
        raise RuntimeError("codex is not installed")
    codex = str(Path(codex).resolve())
    started, status = time.time(), "ok"
    with tempfile.TemporaryDirectory(prefix="run-", dir="/private/tmp") as scratch:
        base = Path(scratch).resolve()
        work = base / "work"
        work.mkdir()
        env = _clean_env(base, arm)
        forbidden = _direct_roots(root.resolve())
        if arm == "direct":
            if _within(base, forbidden):
                raise ValueError("neutral workspace must be outside project and benchmark roots")
            _validate_python(direct_python(suite), work, env, forbidden + _private_roots())
        prompt = prompt_for(suite, topic, arm)
        if arm == "direct" and ("anytomanim" in prompt.lower() or
                                any(str(p).lower() in prompt.lower() for p in forbidden)):
            raise ValueError("direct prompt contains a project name or forbidden path")
        login = _link_login(codex, base, env)
        blocked = _private_roots() + (forbidden if arm == "direct" else [])
        prefix, nested = _sandbox_prefix(base, work, env, _sandbox_profile(base, blocked, login))
        cmd = prefix + [codex, "exec", "-C", str(work), "-m", model["model"],
                        "-c", f'model_reasoning_effort="{model["effort"]}"',
                        "-c", 'web_search="disabled"',
                        "-c", 'cli_auth_credentials_store="file"',
                        "-c", "project_doc_max_bytes=0",
                        "-c", "skills.bundled.enabled=false",
                        "-c", "skills.include_instructions=false",
                        "-c", 'shell_environment_policy.inherit="all"',
                        "-c", "shell_environment_policy.ignore_default_excludes=true",
                        "-c", "allow_login_shell=false",
                        "--ignore-user-config", "--ignore-rules",
                        "--disable", "plugins", "--disable", "apps",
                        "--disable", "memories", "--disable", "shell_snapshot",
                        "--enable", "skip_host_skill_discovery",
                        "--dangerously-bypass-approvals-and-sandbox",
                        "--skip-git-repo-check", "--ephemeral", "--json",
                        "-o", str(work / "report.md"), "-"]
        # Preserve unfinished-cell artifacts as well as completed-cell resume behavior.
        for artifact in wd.iterdir():
            shutil.move(str(artifact), work / artifact.name)
        try:
            with (work / "events.jsonl").open("w") as out, (work / "stderr.log").open("w") as err:
                with subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=out, stderr=err,
                                      text=True, cwd=work, env=env, start_new_session=True) as proc:
                    try:
                        proc.communicate(input=prompt, timeout=TIMEOUT)
                        if proc.returncode:
                            status = f"exit {proc.returncode}"
                    except subprocess.TimeoutExpired:
                        # Stop descendants before collecting artifacts or deleting the sandbox.
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.communicate()
                        status = "timeout"
        finally:
            for artifact in work.iterdir():
                shutil.move(str(artifact), wd / artifact.name)
    mp4 = wd / "final.mp4"
    isolation = scan_isolation(wd / "events.jsonl", arm, root.resolve())
    isolation.update(sandbox="seatbelt", nested_seatbelt_supported=nested,
                     inner_sandbox=False, clean_home=True, shared_login=True)
    result = {"cell": cell, "topic": topic["id"], "model": model["id"], "arm": arm,
              "effort": model["effort"], "status": status,
              "seconds": round(time.time() - started, 1),
              "delivered": mp4.is_file() and mp4.stat().st_size > 0,
              "isolation": isolation, **usage_of(wd / "events.jsonl")}
    _write_json(result_file, result)
    return result


def run_suite(suite_path: Path, root: Path, jobs: int = 3, only: dict | None = None) -> list[dict]:
    suite = json.loads(Path(suite_path).read_text())
    only = only or {}
    cells = [(t, m, a) for m in suite["models"] for t in suite["topics"]
             for a in suite["arms"]
             if (not only.get("topic") or t["id"] in only["topic"])
             and (not only.get("model") or m["id"] in only["model"])
             and (not only.get("arm") or a in only["arm"])]
    # Fail before starting *any* model if a pending direct cell is misconfigured.
    if any(a == "direct" and not (root / f"{t['id']}__{m['id']}__{a}/result.json").exists()
           for t, m, a in cells):
        with tempfile.TemporaryDirectory(prefix="check-", dir="/private/tmp") as scratch:
            base = Path(scratch)
            env = _clean_env(base, "direct")
            _validate_python(direct_python(suite), base, env,
                             _direct_roots(root.resolve()) + _private_roots())
    root.mkdir(parents=True, exist_ok=True)

    def work(cell):
        t, m, a = cell
        r = run_cell(suite, root, t, m, a)
        print(f"{r['cell']}: {r['status']} {r['seconds']}s delivered={r['delivered']} "
              f"tokens={r['tokens'].get('output_tokens')}", flush=True)
        return r

    with ThreadPoolExecutor(max_workers=jobs) as ex:
        return list(ex.map(work, cells))


def comparisons(suite: dict) -> list[dict]:
    """Pair tools (A) against direct (B), within each topic."""
    if not {"tools", "direct"}.issubset(suite["arms"]):
        return []
    models = {m["id"] for m in suite["models"]}
    pairs = []
    for topic in suite["topics"]:
        for model in suite["models"]:
            pairs.append({"topic": topic["id"], "kind": "same_model",
                          "a": f"{topic['id']}__{model['id']}__tools",
                          "b": f"{topic['id']}__{model['id']}__direct"})
        if "sol" in models:
            for model in ("luna", "terra"):
                if model in models:
                    pairs.append({"topic": topic["id"], "kind": "cheap_tools_vs_top_direct",
                                  "a": f"{topic['id']}__{model}__tools",
                                  "b": f"{topic['id']}__sol__direct"})
    return pairs


def _write_json(path: Path, data):
    with atomic_output(path) as staged:
        staged.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def report(suite_path, root, runs=2, jobs=3, judge_pairs=True,
           judge_model="gpt-6.1-sol", judge_effort="high", judge_fn=None) -> dict:
    """Collect diagnostics and resumable visual judgments, without an overall score.

    Criterion means weight each successful pair equally. Missing, skipped and
    failed pairs contribute neither wins nor scores.
    """
    from . import evaluate, judge

    if type(jobs) is not int or jobs < 1:
        raise ValueError("jobs must be a positive integer")
    if type(runs) is not int or runs < 1:
        raise ValueError("runs must be a positive integer")
    suite = json.loads(Path(suite_path).read_text())
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    judge_fn = judge_fn or judge.judge
    names = [(t["id"], m["id"], a) for t in suite["topics"]
             for m in suite["models"] for a in suite["arms"]]

    def measure(cell):
        topic, model, arm = cell
        name = f"{topic}__{model}__{arm}"
        record = {"cell": name, "topic": topic, "model": model, "arm": arm}
        result, video = root / name / "result.json", root / name / "final.mp4"
        try:
            missing = []
            if not result.is_file():
                missing.append("missing result.json")
            else:
                data = json.loads(result.read_text())
                record.update({k: data.get(k) for k in
                               ("status", "seconds", "delivered", "commands", "tokens")})
            if not video.is_file() or video.stat().st_size == 0:
                missing.append("missing or empty final.mp4")
            if missing:
                if "status" in record:
                    record["result_status"] = record["status"]
                record.update(status="missing", reason="; ".join(missing))
                return record
        except Exception as exc:
            record.update(status="error", error=str(exc))
            return record
        try:
            record["metrics"] = evaluate.evaluate_cached(video)
        except Exception as exc:
            record["metrics"] = {"error": str(exc)}
        return record

    # OCR is CPU-heavy; judge concurrency is configured separately below.
    with ThreadPoolExecutor(max_workers=min(jobs, 2)) as ex:
        cells = list(ex.map(measure, names))
    by_name = {c["cell"]: c for c in cells}
    topics = {t["id"]: t["topic"] for t in suite["topics"]}
    cache = root / f"_judged_v{judge.JUDGE_VERSION}"
    if judge_pairs:
        cache.mkdir(parents=True, exist_ok=True)

    def judge_pair(pair):
        record = dict(pair)
        unavailable = [f"{name}: {by_name[name].get('reason') or by_name[name]['error']}"
                       for name in (pair["a"], pair["b"])
                       if "reason" in by_name[name] or "error" in by_name[name]]
        if unavailable:
            return dict(record, status="skipped", reason="; ".join(unavailable))
        if not judge_pairs:
            return dict(record, status="skipped", reason="pairwise judging disabled (metrics-only)")
        name = f"{pair['a']}_VS_{pair['b']}"
        path = cache / f"{name}.json"
        seed = int.from_bytes(hashlib.sha256(name.encode()).digest()[:8], "big")
        try:
            cached = path.is_file()
            result = (json.loads(path.read_text()) if cached else
                      judge_fn(root / pair["a"] / "final.mp4", root / pair["b"] / "final.mp4",
                               topics[pair["topic"]], runs=runs, model=judge_model,
                               effort=judge_effort, seed=seed))
            wins = result["win_counts"]
            winner = "A" if wins["A"] > wins["B"] else "B" if wins["B"] > wins["A"] else "tie"
            # Validate the fields used by the summary before caching a success.
            for criterion in judge.CRITERIA:
                for side in ("A", "B"):
                    score = result["means"][side][criterion]
                    if type(score) not in (int, float) or not math.isfinite(score):
                        raise ValueError(f"invalid {side} {criterion} mean")
            if not cached:
                _write_json(path, result)
            record.update(status="ok", winner=winner, judge=result)
        except Exception as exc:
            record.update(status="error", error=str(exc))
        return record

    with ThreadPoolExecutor(max_workers=jobs) as ex:
        pairs = list(ex.map(judge_pair, comparisons(suite)))
    by_kind = {kind: {"tools_wins": 0, "direct_wins": 0, "ties": 0}
               for kind in ("same_model", "cheap_tools_vs_top_direct")}
    successful = [p for p in pairs if p["status"] == "ok"]
    for pair in successful:
        key = {"A": "tools_wins", "B": "direct_wins", "tie": "ties"}[pair["winner"]]
        by_kind[pair["kind"]][key] += 1
    by_criterion = {}
    for kind in by_kind:
        group = [p for p in successful if p["kind"] == kind]
        by_criterion[kind] = {
            c: {side: (sum(p["judge"]["means"][side][c] for p in group) / len(group)
                       if group else None) for side in ("A", "B")} for c in judge.CRITERIA}
    result = {"judge_version": judge.JUDGE_VERSION, "cells": cells, "pairs": pairs,
              "summary": {"by_kind": by_kind, "by_criterion": by_criterion}}
    _write_json(root / f"report_v{judge.JUDGE_VERSION}.json", result)
    return result
