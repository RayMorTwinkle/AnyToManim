"""Storyboard lifecycle and CLI regressions: no rendering, credentials or network."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from anytomanim.cli import main
from anytomanim.storyboard import check_storyboard


def beat(bid, **kw):
    return dict(id=bid, card=None, keep=[], change=[], add=[], remove=[],
                focus=None, camera="none", clear_reason=None) | kw


def add(obj, source=None):
    return dict(id=obj, **{"from": source})


class StoryboardTests(unittest.TestCase):
    def check(self, rows, reference=None):
        return check_storyboard({"beats": rows}, {"beats": reference or [
            {"id": b["id"]} for b in rows]})

    def errors(self, rows):
        return [i for i in self.check(rows) if i["level"] == "error"]

    def valid_rows(self):
        return [beat("b01", add=[add("axes"), add("point")], focus="point"),
                beat("b02", keep=["axes"], change=[
                    {"from": "point", "to": "point", "how": "slide right"}], focus="point")]

    def test_valid_continuity_and_same_id_change(self):
        self.assertEqual(self.check(self.valid_rows()), [])

    def test_missing_extra_reordered_and_duplicate_beat_ids(self):
        ref = [{"id": "b01"}, {"id": "b02"}]
        for rows in ([beat("b01")], [beat("b01"), beat("b02"), beat("b03")],
                     [beat("b02"), beat("b01")], [beat("b01"), beat("b01")]):
            with self.subTest(rows=rows):
                self.assertTrue(any(i["level"] == "error" for i in self.check(rows, ref)))

    def test_all_reference_fields_check_stage_membership(self):
        bad = [dict(keep=["ghost"]), dict(change=[{"from": "ghost", "to": "x", "how": "morph"}]),
               dict(add=[add("x", "ghost")]), dict(remove=[{"id": "ghost", "reason": "done"}]),
               dict(focus="ghost")]
        for fields in bad:
            with self.subTest(fields=fields):
                self.assertTrue(any("absent object ghost" in i["message"]
                                    for i in self.errors([beat("b01", **fields)])))

    def test_remove_requires_nonblank_reason(self):
        for reason in (None, "", "   ", 3):
            r = {"id": "x"}
            if reason is not None:
                r["reason"] = reason
            rows = [beat("b01", add=[add("x")]),
                    beat("b02", remove=[r], clear_reason="finished")]
            self.assertTrue(any("remove.reason" in i["message"] for i in self.errors(rows)))

    def test_keep_or_change_required_when_previous_stage_nonempty(self):
        rows = [beat("b01", add=[add("x")]), beat("b02", add=[add("y")])]
        self.assertTrue(any("clear_reason" in i["message"] for i in self.errors(rows)))
        rows[1]["clear_reason"] = "start a new example"
        self.assertFalse(self.errors(rows))

    def test_clear_removes_unmentioned_but_keeps_declared_continuity(self):
        rows = [beat("b01", add=[add("a"), add("b"), add("c")]),
                beat("b02", keep=["a"], change=[{"from": "b", "to": "d", "how": "morph"}],
                     clear_reason="discard scaffolding", focus="d"),
                beat("b03", keep=["a", "d"], focus="c")]
        self.assertEqual(len(self.errors(rows)), 1)
        self.assertIn("absent object c", self.errors(rows)[0]["message"])

    def test_unmentioned_objects_persist_without_clear(self):
        rows = [beat("b01", add=[add("a"), add("b")]),
                beat("b02", keep=["a"]), beat("b03", keep=["b"], focus="b")]
        self.assertFalse(self.errors(rows))

    def test_consumed_sources_can_supply_copies_but_not_future_references(self):
        rows = [beat("b01", add=[add("a")]), beat("b02",
                change=[{"from": "a", "to": "b", "how": "morph"}],
                add=[add("copy", "a")], focus="b"), beat("b03", keep=["a"])]
        errors = self.errors(rows)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["beat"], "b03")

    def test_focus_uses_post_change_snapshot(self):
        rows = self.valid_rows()
        rows[1]["change"][0]["to"] = "new_point"
        rows[1]["focus"] = "new_point"
        self.assertFalse(self.errors(rows))
        rows[1]["focus"] = "point"
        self.assertTrue(self.errors(rows))

    def test_duplicate_creation_and_conflicting_operations(self):
        for fields in (dict(add=[add("a")], keep=["a"]),
                       dict(add=[add("b"), add("b")], keep=["a"]),
                       dict(keep=["a"], remove=[{"id": "a", "reason": "done"}]),
                       dict(keep=["a"], change=[{"from": "a", "to": "b", "how": "morph"}])):
            self.assertTrue(self.errors([beat("b01", add=[add("a")]), beat("b02", **fields)]))

    def test_focus_warning_threshold(self):
        for n in (3, 4):
            rows = [beat("b01", add=[add(str(i)) for i in range(n)])]
            issues = self.check(rows)
            self.assertEqual(any("without focus" in i["message"] for i in issues), n == 4)
            rows[0]["focus"] = "0"
            self.assertFalse(any("without focus" in i["message"] for i in self.check(rows)))

    def test_no_change_warning(self):
        self.assertTrue(any("no change" in i["message"] for i in self.check([beat("b01")])))
        self.assertFalse(any("no change" in i["message"] for i in self.check(self.valid_rows())))

    def test_camera_warning_requires_six_beats_and_no_movement(self):
        rows = [beat(f"b{i:02}") for i in range(1, 7)]
        def camera_warnings(rows):
            return [i for i in self.check(rows) if "no camera movement" in i["message"]]
        self.assertFalse(camera_warnings(rows[:5]))
        self.assertEqual(camera_warnings(rows)[0]["level"], "warning")
        self.assertEqual(camera_warnings(rows)[0]["beat"], "all")
        for row in rows:
            del row["camera"]
        self.assertTrue(camera_warnings(rows))
        rows[3]["camera"] = "zoom into the graph"
        self.assertFalse(camera_warnings(rows))

    def test_short_lifetimes_include_final_objects_and_strict_majority(self):
        rows = [beat("b01", add=[add("a"), add("b")]),
                beat("b02", keep=["a"], remove=[{"id": "b", "reason": "done"}])]
        self.assertFalse(any("live <2" in i["message"] for i in self.check(rows)))
        rows[1]["add"] = [add("c", "a")]
        self.assertTrue(any("2/3 objects live <2" in i["message"] for i in self.check(rows)))

    def test_ungrounded_streak_threshold_and_empty_add_reset(self):
        rows = [beat(f"b{i:02}", add=[add(f"x{i}")],
                     keep=[] if i == 1 else [f"x{i-1}"]) for i in range(1, 6)]
        warnings = [i for i in self.check(rows) if "consecutive" in i["message"]]
        self.assertEqual([i["beat"] for i in warnings], ["b04"])
        rows[2]["add"] = []
        rows[3]["keep"] = ["x2"]
        self.assertFalse(any("consecutive" in i["message"] for i in self.check(rows)))
        rows[2]["add"] = [add("x3", "x2")]
        rows[3]["keep"] = ["x3"]
        self.assertFalse(any("consecutive" in i["message"] for i in self.check(rows)))

    def test_malformed_input_returns_errors_without_crashing(self):
        cases = [None, [], {}, {"beats": []}, {"beats": [None]}, {"beats": [{"id": []}]},
                 {"beats": [beat("b01", keep=[[]])]}, {"beats": [beat("b01", change=[None])]},
                 {"beats": [beat("b01", add=[{"id": "x"}])]},
                 {"beats": [beat("b01", camera=None)]},
                 {"beats": [beat("b01", clear_reason=" ")]},
                 {"beats": [beat("b01", remove="x")]},
                 {"beats": [beat("b01", change=[{"from": [], "to": "x", "how": ""}])]}]
        for board in cases:
            with self.subTest(board=board):
                self.assertTrue(any(i["level"] == "error" for i in check_storyboard(
                    board, {"beats": [{"id": "b01"}]})))

    def test_checker_is_pure_and_accepts_optional_defaults(self):
        rows = self.valid_rows()
        before = deepcopy(rows)
        self.check(rows)
        self.assertEqual(rows, before)
        self.assertFalse(self.errors([{"id": "b01"}]))

    def test_cli_errors_fail_and_warnings_succeed(self):
        with tempfile.TemporaryDirectory() as tmp:
            board, ref = Path(tmp)/"storyboard.json", Path(tmp)/"beats.json"
            ref.write_text(json.dumps({"beats": [{"id": "b01"}]}))
            def run(value):
                board.write_text(json.dumps(value))
                out = io.StringIO()
                with patch.object(sys, "argv", ["anytomanim", "storyboard", str(board), "--beats", str(ref)]), \
                     redirect_stdout(out), redirect_stderr(out):
                    try:
                        main()
                    except SystemExit as exc:
                        return exc.code, out.getvalue()
                return 0, out.getvalue()
            code, output = run({"beats": [beat("b01")]})
            self.assertEqual(code, 0)
            self.assertIn("warning all", output)
            code, output = run({"beats": [beat("b01", focus="absent")]})
            self.assertNotEqual(code, 0)
            self.assertIn("error b01", output)
            board.write_text("{")
            result = subprocess.run([sys.executable, "-m", "anytomanim.cli", "storyboard", str(board),
                                     "--beats", str(ref)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)

    def test_schema_is_json_and_covers_all_beat_fields(self):
        path = Path(__file__).parents[1]/"src/anytomanim/guides/storyboard-schema.json"
        schema = json.loads(path.read_text())
        fields = schema["properties"]["beats"]["items"]["properties"]
        self.assertEqual(set(fields), set(beat("b01")))

    def test_clear_and_recreate_same_id_starts_a_new_lifetime(self):
        rows = [beat("b01", add=[add("x")]),
                beat("b02", clear_reason="new object, reused label", add=[add("x")])]
        self.assertFalse(self.errors(rows))
        self.assertTrue(any("2/2 objects live <2" in i["message"] for i in self.check(rows)))
