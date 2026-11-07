"""Benchmark reports with fake diagnostics and injected judges; no live Codex."""
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from anytomanim import bench, cli, evaluate, judge


class BenchIsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="test-", dir="/private/tmp")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "results"
        self.suite = {"seconds": [60, 90], "direct_python": "/opt/neutral/bin/python"}
        self.topic = {"id": "topic", "topic": "梯度下降"}
        self.model = {"id": "model", "model": "fake", "effort": "high"}
        self.env_patch = patch.dict(os.environ, {}, clear=True)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.run = patch.object(bench.subprocess, "run").start()
        self.popen = patch.object(bench.subprocess, "Popen").start()
        self.addCleanup(patch.stopall)
        self.run.return_value = Mock(returncode=1, stderr="ModuleNotFoundError: No module named 'anytomanim'")
        patch.object(bench, "tex_bin", return_value="/Library/TeX/texbin").start()
        patch.object(bench.shutil, "which", return_value="/usr/local/bin/codex").start()
        self.login = patch.object(bench, "_link_login", return_value=[
            Path.home() / ".codex/auth.json", Path.home() / ".codex/auth.lock"]).start()
        self.sandbox = patch.object(bench, "_sandbox_prefix", return_value=(["sandbox"], False)).start()

    def cell(self, arm="direct"):
        return bench.run_cell(self.suite, self.root, self.topic, self.model, arm)

    def fake_process(self, commands=None, returncode=0, timeout=False):
        proc = Mock(returncode=returncode, pid=123456)
        proc.__enter__ = Mock(return_value=proc)
        proc.__exit__ = Mock(return_value=False)

        def start(cmd, **kwargs):
            wd = kwargs["cwd"]
            self.workspace = wd
            self.child_env = kwargs["env"]
            self.command = cmd

            def communicate(input=None, timeout=None):
                if input is None:  # reap after the mocked timeout
                    return
                self.prompt = input
                (wd / "final.mp4").write_bytes(b"fake video")
                (wd / "report.md").write_text("done")
                (wd / "media").mkdir(exist_ok=True)
                (wd / "media/frame.png").write_bytes(b"frame")
                events = [{"type": "item.completed", "item": {
                    "type": "command_execution", "command": command,
                    "aggregated_output": output}} for command, output in
                    (commands or [("python -m manim scene.py", "rendered")])]
                events.append({"type": "turn.completed", "usage": {"output_tokens": 7}})
                kwargs["stdout"].write("\n".join(json.dumps(e) for e in events) + "\n")
                kwargs["stdout"].flush()
                if timeout is not None and timeout_case:
                    raise subprocess.TimeoutExpired(cmd, timeout)

            timeout_case = timeout
            proc.communicate.side_effect = communicate
            return proc

        self.popen.side_effect = start
        return proc

    def test_direct_prompt_has_no_project_name_or_path(self):
        prompt = bench.prompt_for(self.suite, self.topic, "direct")
        self.assertNotIn(str(bench.REPO), prompt)
        self.assertNotIn("anytomanim", prompt.lower())
        self.assertNotIn("不要讀取", prompt)
        self.assertIn(self.suite["direct_python"], prompt)
        with patch.dict(os.environ, {"ANYTOMANIM_BENCH_DIRECT_PYTHON": "/opt/other/bin/python"}):
            self.assertIn("/opt/other/bin/python", bench.prompt_for(self.suite, self.topic, "direct"))

    def test_invalid_python_never_starts_codex(self):
        for value in (None, "relative/python", str(bench.REPO / ".venv/bin/python"),
                      str(bench.REPO / "other/.venv/bin/python")):
            with self.subTest(value=value):
                self.suite["direct_python"] = value
                with self.assertRaises(ValueError):
                    self.cell()
        self.popen.assert_not_called()
        self.login.assert_not_called()

    def test_installed_package_or_broken_python_never_starts_codex(self):
        for code, stderr in ((0, ""), (1, "No module named 'manim'"), (2, "bad Python")):
            self.run.return_value = Mock(returncode=code, stderr=stderr)
            with self.assertRaisesRegex(ValueError, "fail to import"):
                self.cell()
        self.popen.assert_not_called()
        self.login.assert_not_called()

    def test_symlink_into_checkout_rejected_before_import(self):
        python = Path(self.tmp.name) / "python"
        python.symlink_to(bench.REPO / ".venv/bin/python")
        self.suite["direct_python"] = str(python)
        with self.assertRaises(ValueError):
            self.cell()
        self.run.assert_not_called()
        self.popen.assert_not_called()

    def test_neutral_workspace_artifacts_and_resume(self):
        self.fake_process()
        result = self.cell()
        self.assertFalse(bench._within(self.workspace, [bench.REPO, self.root]))
        self.assertNotIn("anytomanim", str(self.workspace).lower())
        self.assertFalse(self.workspace.exists())
        wd = self.root / result["cell"]
        for name in ("final.mp4", "events.jsonl", "report.md", "stderr.log", "media/frame.png"):
            self.assertTrue((wd / name).is_file(), name)
        self.assertEqual(json.loads((wd / "result.json").read_text()), result)
        self.assertTrue(result["delivered"])
        self.assertEqual(result["commands"], 1)
        self.assertEqual(result["tokens"], {"output_tokens": 7})
        self.assertEqual(result["isolation"]["scan_status"], "clean")
        self.assertFalse(result["isolation"]["inner_sandbox"])
        self.assertEqual(self.cell(), result)
        self.assertEqual(self.popen.call_count, 1)

    def test_partial_artifacts_survive_and_nonzero_keeps_video(self):
        wd = self.root / "topic__model__direct"
        wd.mkdir(parents=True)
        (wd / "script.py").write_text("# keep unfinished work")
        self.fake_process(returncode=2)
        result = self.cell()
        self.assertEqual(result["status"], "exit 2")
        self.assertTrue(result["delivered"])
        self.assertTrue((wd / "script.py").exists())

    def test_timeout_kills_process_group_and_keeps_artifacts(self):
        self.fake_process(timeout=True)
        with patch.object(bench.os, "killpg") as kill:
            result = self.cell()
        kill.assert_called_once_with(123456, bench.signal.SIGKILL)
        self.assertEqual(result["status"], "timeout")
        self.assertTrue(result["delivered"])

    def test_direct_scan_flags_commands_and_outputs_without_deleting_video(self):
        self.fake_process(commands=[("cat ~/.agents/hidden/file", "Operation not permitted"),
                                    ("python scene.py", f"imported AnyToManim from {bench.REPO}"),
                                    ("ls ~/.claude", "denied")])
        result = self.cell()
        self.assertEqual(result["isolation"]["scan_status"], "violations")
        matches = {v["match"] for v in result["isolation"]["violations"]}
        self.assertTrue({"anytomanim", "~/.claude"} <= matches)
        self.assertTrue(result["delivered"])
        self.assertTrue((self.root / result["cell"] / "final.mp4").exists())

    def test_both_arms_clean_home_and_tools_child_src(self):
        with patch.dict(os.environ, {"PYTHONPATH": "/wrong/src", "VIRTUAL_ENV": "/old/env",
                                     "BASH_ENV": "/old/init", "CODEX_THREAD_ID": "old",
                                     "MIMO_API_KEY": "not-inherited"}):
            for arm in ("direct", "tools"):
                self.fake_process()
                self.cell(arm)
                env, cmd = self.child_env, self.command
                self.assertNotEqual(env["HOME"], str(Path.home()))
                self.assertNotEqual(env["CODEX_HOME"], str(Path.home() / ".codex"))
                for name in ("BASH_ENV", "VIRTUAL_ENV", "CODEX_THREAD_ID", "MIMO_API_KEY"):
                    self.assertNotIn(name, env)
                for flag in ("--ignore-user-config", "--ignore-rules", "--ephemeral",
                             "--dangerously-bypass-approvals-and-sandbox"):
                    self.assertIn(flag, cmd)
                for feature in ("plugins", "apps", "memories", "shell_snapshot"):
                    self.assertIn(["--disable", feature], [cmd[i:i+2] for i in range(len(cmd)-1)])
                self.assertIn('shell_environment_policy.inherit="all"', cmd)
                if arm == "tools":
                    self.assertEqual(env["PYTHONPATH"], str(bench.REPO / "src"))
                    self.assertEqual(env["ANYTOMANIM_TTS"], "draft")
                    self.assertIn(str(bench.REPO / ".venv/bin/python"), self.prompt)
                else:
                    self.assertNotIn("PYTHONPATH", env)
                    self.assertNotIn("ANYTOMANIM_TTS", env)

    def test_tools_scan_allows_project_but_flags_personal_agent_dirs(self):
        events = Path(self.tmp.name) / "events.jsonl"
        events.write_text(json.dumps({"item": {"type": "command_execution",
            "command": f"cat {bench.REPO}/skills/anytomanim/SKILL.md",
            "aggregated_output": "AnyToManim"}}))
        self.assertEqual(bench.scan_isolation(events, "tools", self.root)["scan_status"], "clean")
        events.write_text(json.dumps({"item": {"type": "command_execution",
            "command": "ls ~/.codex/skills", "aggregated_output": ""}}) + "\ninvalid json")
        scan = bench.scan_isolation(events, "tools", self.root)
        self.assertEqual(scan["scan_status"], "violations")
        self.assertEqual(scan["malformed_lines"], 1)

    def test_failed_sandbox_prevents_model_call(self):
        self.sandbox.side_effect = RuntimeError("outer Seatbelt sandbox unavailable")
        with self.assertRaisesRegex(RuntimeError, "sandbox unavailable"):
            self.cell()
        self.popen.assert_not_called()

    def test_sandbox_profile_blocks_fork_private_dirs_env_and_external_writes(self):
        base = Path(self.tmp.name)
        login = self.login.return_value
        profile = bench._sandbox_profile(base, bench._private_roots() + bench._direct_roots(self.root), login)
        for path in (bench.REPO, Path.home() / ".agents",
                     Path.home() / ".codex", Path.home() / ".claude", self.root):
            self.assertIn(f"(subpath {json.dumps(str(path))})", profile)
        self.assertIn("(deny file-write* (require-not", profile)
        self.assertIn("[.]env", profile)
        self.assertIn("[.]auth-", profile)
        for path in login:
            self.assertIn(f"(literal {json.dumps(str(path))})", profile)
        self.assertNotIn("deny network", profile)
        self.assertNotIn("TinyTeX", profile)
        tools = bench._sandbox_profile(base, bench._private_roots(), login)
        self.assertNotIn(f"(subpath {json.dumps(str(bench.REPO))})", tools)

    def test_sandbox_outer_failure_and_nested_probe(self):
        # Use the original helper while keeping all actual subprocesses mocked.
        helper = self._sandbox_helper
        base = Path(self.tmp.name)
        env = {"HOME": str(base)}
        with patch.object(bench.sys, "platform", "darwin"), \
                patch.object(Path, "is_file", return_value=True):
            self.run.return_value = Mock(returncode=71, stderr=b"sandbox_apply: Operation not permitted")
            with self.assertRaisesRegex(RuntimeError, "refusing an unisolated"):
                helper(base, base, env, "(version 1)(allow default)")
            self.run.side_effect = [Mock(returncode=0), Mock(returncode=1),
                                    Mock(returncode=1), Mock(returncode=71)]
            prefix, nested = helper(base, base, env, "(version 1)(allow default)")
        self.assertEqual(prefix[:2], ["/usr/bin/sandbox-exec", "-f"])
        self.assertFalse(nested)

    def test_sandbox_rejects_wrapper_that_does_not_enforce_restrictions(self):
        base = Path(self.tmp.name)
        with patch.object(bench.sys, "platform", "darwin"), \
                patch.object(Path, "is_file", return_value=True):
            for read, write in ((0, 1), (1, 0)):
                self.run.side_effect = [Mock(returncode=0), Mock(returncode=read), Mock(returncode=write)]
                with self.assertRaisesRegex(RuntimeError, "failed read/write canaries"):
                    self._sandbox_helper(base, base, {}, "(version 1)(allow default)")

    _sandbox_helper = staticmethod(bench._sandbox_prefix)
    _login_helper = staticmethod(bench._link_login)

    def test_login_compatibility_failure_never_links_real_credentials(self):
        base = Path(self.tmp.name)
        env = bench._clean_env(base, "direct")

        def replace_link(cmd, **kwargs):
            link = Path(kwargs["env"]["CODEX_HOME"]) / "auth.json"
            link.unlink()
            link.write_text('{"synthetic": true}')
            return Mock(returncode=0)

        self.run.side_effect = replace_link
        # Atomic replacement of the link would fork refresh tokens. Refuse it.
        with self.assertRaisesRegex(RuntimeError, "cannot safely share"):
            self._login_helper("codex", base, env)
        self.assertFalse((Path(env["CODEX_HOME"]) / "auth.json").exists())

    def test_login_links_store_and_lock_without_reading_or_copying(self):
        base = Path(self.tmp.name)
        env = bench._clean_env(base, "direct")
        original = base / "original"
        original.mkdir()
        (original / "auth.json").touch()  # synthetic fixture, never read

        def synthetic_login(cmd, **kwargs):
            link = Path(kwargs["env"]["CODEX_HOME"]) / "auth.json"
            link.write_text('{"synthetic": true}')
            return Mock(returncode=0)

        self.run.side_effect = synthetic_login
        with patch.dict(os.environ, {"CODEX_HOME": str(original)}):
            login = self._login_helper("codex", base, env)
        state = Path(env["CODEX_HOME"])
        for name in ("auth.json", "auth.lock"):
            self.assertTrue((state / name).is_symlink())
            self.assertEqual((state / name).readlink(), original / name)
        self.assertEqual(login, [original / "auth.json", original / "auth.lock"])

    def test_suite_preflight_fails_before_any_arm_starts(self):
        suite = dict(self.suite, topics=[self.topic], models=[self.model], arms=["tools", "direct"])
        path = Path(self.tmp.name) / "suite.json"
        path.write_text(json.dumps(suite))
        self.run.return_value = Mock(returncode=0)
        with patch.object(bench, "run_cell") as cell:
            with self.assertRaises(ValueError):
                bench.run_suite(path, self.root)
        cell.assert_not_called()

    def test_cached_legacy_result_resumes_without_requiring_new_python(self):
        wd = self.root / "topic__model__direct"
        wd.mkdir(parents=True)
        legacy = {"status": "ok", "delivered": True}
        (wd / "result.json").write_text(json.dumps(legacy))
        self.suite.pop("direct_python")
        self.assertEqual(self.cell(), legacy)
        self.popen.assert_not_called()
        self.run.assert_not_called()


class BenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.suite = json.loads((Path(__file__).parents[1] / "bench/suite.json").read_text())
        self.suite_path = self.root / "suite.json"
        self.suite_path.write_text(json.dumps(self.suite))
        for topic in self.suite["topics"]:
            for model in self.suite["models"]:
                for arm in self.suite["arms"]:
                    name = f"{topic['id']}__{model['id']}__{arm}"
                    wd = self.root / name
                    wd.mkdir()
                    (wd / "result.json").write_text(json.dumps({
                        "status": "ok", "seconds": 12.5, "delivered": True,
                        "commands": 4, "tokens": {"input_tokens": 100, "output_tokens": 20}}))
                    (wd / "final.mp4").write_bytes(b"fake video")
        metrics = patch.object(evaluate, "evaluate_cached", return_value={"meta": {"duration": 60}, "motion": {"still_share": 0.8, "mean_change": 0.01}})
        self.metrics = metrics.start()
        self.addCleanup(metrics.stop)
        for target in ("anytomanim.bench.subprocess.run", "anytomanim.judge.judge"):
            guard = patch(target, side_effect=AssertionError("no live Codex in bench tests"))
            guard.start()
            self.addCleanup(guard.stop)

    def judgment(self, a, b, topic, **kwargs):
        model = a.parent.name.split("__")[1]
        wins, scores = {"luna": ((2, 0), (5, 2)),
                        "terra": ((0, 2), (1, 4)),
                        "sol": ((1, 1), (3, 3))}[model]
        return {"win_counts": {"A": wins[0], "B": wins[1], "tie": 5},
                "means": {side: {c: scores[i] for c in judge.CRITERIA}
                          for i, side in enumerate(("A", "B"))}, "seed": kwargs["seed"]}

    def report(self, **kwargs):
        kwargs.setdefault("judge_fn", self.judgment)
        return bench.report(self.suite_path, self.root, **kwargs)

    def test_comparisons_counts_identity_and_tools_first(self):
        pairs = bench.comparisons(self.suite)
        self.assertEqual(len(pairs), 15)
        self.assertEqual(len({(p["a"], p["b"]) for p in pairs}), 15)
        for topic in self.suite["topics"]:
            group = [p for p in pairs if p["topic"] == topic["id"]]
            self.assertEqual(sum(p["kind"] == "same_model" for p in group), 3)
            cheap = [p for p in group if p["kind"] == "cheap_tools_vs_top_direct"]
            self.assertEqual({p["a"] for p in cheap},
                             {f"{topic['id']}__{m}__tools" for m in ("luna", "terra")})
            self.assertEqual({p["b"] for p in cheap}, {f"{topic['id']}__sol__direct"})
        self.assertTrue(all(p["a"].endswith("__tools") and p["b"].endswith("__direct")
                            for p in pairs))
        reduced = dict(self.suite, models=[self.suite["models"][0]])
        self.assertEqual(len(bench.comparisons(reduced)), 3)
        self.assertEqual(bench.comparisons(dict(self.suite, arms=["tools"])), [])

    def test_report_cells_summary_and_atomic_outputs(self):
        with patch.object(bench, "atomic_output", wraps=bench.atomic_output) as atomic:
            result = self.report()
        self.assertEqual(len(result["cells"]), 18)
        self.assertEqual(self.metrics.call_count, 18)
        for cell in result["cells"]:
            self.assertEqual(cell["status"], "ok")
            self.assertEqual(cell["seconds"], 12.5)
            self.assertTrue(cell["delivered"])
            self.assertEqual(cell["commands"], 4)
            self.assertEqual(cell["tokens"], {"input_tokens": 100, "output_tokens": 20})
            self.assertEqual(cell["metrics"], {"meta": {"duration": 60}, "motion": {"still_share": 0.8, "mean_change": 0.01}})
        self.assertEqual(result["summary"]["by_kind"], {
            "same_model": {"tools_wins": 3, "direct_wins": 3, "ties": 3},
            "cheap_tools_vs_top_direct": {"tools_wins": 3, "direct_wins": 3, "ties": 0}})
        self.assertEqual(result["summary"]["by_criterion"],
                         {kind: {c: {"A": a, "B": b} for c in judge.CRITERIA}
                          for kind, a, b in (("same_model", 3, 3),
                                             ("cheap_tools_vs_top_direct", 3, 3))})
        self.assertEqual(json.loads((self.root / f"report_v{judge.JUDGE_VERSION}.json").read_text()), result)
        self.assertEqual(atomic.call_count, 16)
        self.assertEqual(len(list((self.root / f"_judged_v{judge.JUDGE_VERSION}").glob("*.json"))), 15)
        self.assertFalse(list(self.root.rglob("*.tmp")))

    def test_missing_results_missing_and_empty_videos_skip_pairs(self):
        cases = {"gradient__luna__tools": "result.json",
                 "fourier__terra__direct": "final.mp4",
                 "hashtable__sol__direct": "final.mp4"}
        for name, file in cases.items():
            path = self.root / name / file
            if name.startswith("hashtable"):
                path.write_bytes(b"")
            else:
                path.unlink()
        fake = Mock(side_effect=self.judgment)
        result = self.report(judge_fn=fake)
        self.assertEqual({c["cell"] for c in result["cells"] if c["status"] == "missing"}, set(cases))
        self.assertEqual(self.metrics.call_count, 15)
        for pair in result["pairs"]:
            if pair["a"] in cases or pair["b"] in cases:
                self.assertEqual(pair["status"], "skipped")
                self.assertIn("missing", pair["reason"])
                self.assertTrue(any(name in pair["reason"] for name in cases))
            else:
                self.assertEqual(pair["status"], "ok")
        self.assertEqual(fake.call_count, 9)
        self.assertEqual(sum(sum(counts.values()) for counts in result["summary"]["by_kind"].values()), 9)

    def test_cached_judgments_resume_without_calling_judge(self):
        fake = Mock(side_effect=self.judgment)
        first = self.report(judge_fn=fake)
        self.assertEqual(fake.call_count, 15)
        fake.reset_mock()
        second = self.report(judge_fn=fake)
        fake.assert_not_called()
        self.assertEqual(first, second)
        pair = first["pairs"][0]
        path = self.root / f"_judged_v{judge.JUDGE_VERSION}" / f"{pair['a']}_VS_{pair['b']}.json"
        path.unlink()
        self.report(judge_fn=fake)
        self.assertEqual(fake.call_count, 1)

    def test_versioned_cache_preserves_v1_and_separates_criterion_kinds(self):
        old_cache = self.root / "_judged"
        old_cache.mkdir()
        old = old_cache / "sentinel.json"
        old.write_text('{"old": true}')
        old_report = self.root / "report.json"
        old_report.write_text('{"old": true}')
        def different_kinds(a, b, topic, **kwargs):
            cross = a.parent.name.split("__")[1] != b.parent.name.split("__")[1]
            result = self.judgment(a, b, topic, **kwargs)
            result["means"] = {side: {c: (5 if cross else 1) for c in judge.CRITERIA}
                               for side in ("A", "B")}
            return result
        result = self.report(judge_fn=different_kinds)
        for kind, score in (("same_model", 1), ("cheap_tools_vs_top_direct", 5)):
            self.assertEqual(result["summary"]["by_criterion"][kind],
                             {c: {"A": score, "B": score} for c in judge.CRITERIA})
        self.assertEqual(old.read_text(), '{"old": true}')
        self.assertEqual(old_report.read_text(), '{"old": true}')
        with patch.object(judge, "JUDGE_VERSION", judge.JUDGE_VERSION + 1):
            fake = Mock(side_effect=different_kinds)
            self.report(judge_fn=fake)
            self.assertEqual(fake.call_count, 15)
            self.assertTrue((self.root / f"report_v{judge.JUDGE_VERSION}.json").exists())

    def test_judge_error_is_not_cached_and_other_pairs_continue(self):
        def flaky(a, b, topic, **kwargs):
            if a.parent.name == "gradient__luna__tools":
                raise RuntimeError("judge unavailable")
            return self.judgment(a, b, topic, **kwargs)
        result = self.report(judge_fn=flaky)
        failures = [p for p in result["pairs"] if p["status"] == "error"]
        self.assertEqual(len(failures), 2)
        self.assertTrue(all(p["error"] == "judge unavailable" for p in failures))
        self.assertEqual(len(list((self.root / f"_judged_v{judge.JUDGE_VERSION}").glob("*.json"))), 13)
        self.assertEqual(sum(p["status"] == "ok" for p in result["pairs"]), 13)
        retry = Mock(side_effect=self.judgment)
        resumed = self.report(judge_fn=retry)
        self.assertEqual(retry.call_count, 2)
        self.assertTrue(all(p["status"] == "ok" for p in resumed["pairs"]))

    def test_metric_error_is_recorded_without_stopping_report(self):
        def metric(video):
            if video.parent.name == "gradient__luna__tools":
                raise RuntimeError("OCR failed")
            return {"meta": {"duration": 60}, "motion": {"still_share": 0.8, "mean_change": 0.01}}
        self.metrics.side_effect = metric
        result = self.report()
        errors = [c for c in result["cells"] if "error" in c.get("metrics", {})]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["metrics"]["error"], "OCR failed")
        self.assertEqual(len(result["pairs"]), 15)
        self.assertTrue((self.root / f"report_v{judge.JUDGE_VERSION}.json").is_file())

    def test_metrics_only_skips_judge_and_has_no_scores(self):
        fake = Mock(side_effect=AssertionError("metrics only"))
        result = self.report(judge_pairs=False, judge_fn=fake)
        fake.assert_not_called()
        self.assertEqual(self.metrics.call_count, 18)
        self.assertTrue(all(p["status"] == "skipped" and "metrics-only" in p["reason"]
                            for p in result["pairs"]))
        self.assertEqual(result["summary"]["by_criterion"],
                         {kind: {c: {"A": None, "B": None} for c in judge.CRITERIA}
                          for kind in ("same_model", "cheap_tools_vs_top_direct")})
        self.assertFalse((self.root / f"_judged_v{judge.JUDGE_VERSION}").exists())

    def test_judge_arguments_and_stable_sha256_seeds(self):
        fake = Mock(side_effect=self.judgment)
        self.report(judge_fn=fake, runs=4, judge_model="test-model", judge_effort="medium")
        topics = {t["id"]: t["topic"] for t in self.suite["topics"]}
        for call in fake.call_args_list:
            a, b, topic = call.args
            name = f"{a.parent.name}_VS_{b.parent.name}"
            expected_seed = int.from_bytes(hashlib.sha256(name.encode()).digest()[:8], "big")
            self.assertEqual(call.kwargs, {"runs": 4, "model": "test-model",
                                           "effort": "medium", "seed": expected_seed})
            self.assertEqual(topic, topics[a.parent.name.split("__")[0]])
            self.assertEqual(a.name, "final.mp4")
            self.assertEqual(b.name, "final.mp4")

    def test_worker_limits(self):
        lock = threading.Lock()
        active = {"metrics": 0, "judge": 0}
        peaks = dict(active)
        def work(kind, result):
            with lock:
                active[kind] += 1
                peaks[kind] = max(peaks[kind], active[kind])
            try:
                time.sleep(0.01)
                return result()
            finally:
                with lock:
                    active[kind] -= 1
        self.metrics.side_effect = lambda p: work("metrics", lambda: {})
        def fake(*args, **kwargs):
            return work("judge", lambda: self.judgment(*args, **kwargs))
        self.report(jobs=3, judge_fn=fake)
        self.assertEqual(peaks, {"metrics": 2, "judge": 3})

    def test_cli_bench_and_report_dispatch_and_defaults(self):
        output = io.StringIO()
        with patch.object(bench, "run_suite", return_value=[]) as run, \
                patch("sys.argv", ["anytomanim", "bench", "suite.json", "--root", "results",
                                   "--topic", "gradient", "--arm", "tools"]), redirect_stdout(output):
            cli.main()
        run.assert_called_once_with(Path("suite.json"), Path("results"), jobs=3,
                                    only={"topic": ["gradient"], "model": None, "arm": ["tools"]})
        for flags, runs, jobs, enabled in (([], 2, 3, True),
                                          (["--metrics-only", "--runs", "4", "--jobs", "1"], 4, 1, False)):
            with patch.object(bench, "report", return_value={}) as report, \
                    patch("sys.argv", ["anytomanim", "bench-report", "suite.json",
                                       "--root", "results"] + flags), redirect_stdout(output):
                cli.main()
            report.assert_called_once_with(Path("suite.json"), Path("results"), runs=runs,
                                           jobs=jobs, judge_pairs=enabled)


if __name__ == "__main__":
    unittest.main()
