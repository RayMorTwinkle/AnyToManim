"""Offline continuity checks for the public storyboard JSON format.

Objects persist until removed, changed to another ID, or cleared. ``keep`` is an
explicit continuity claim, not an exhaustive inventory. References in keep,
change.from, add.from and remove.id use the beat-entry snapshot; focus uses the
beat-end snapshot. A nonempty clear_reason clears unmentioned entry objects,
retaining keep and change targets. Changes are simultaneous; additions follow.
Lifetimes count beat-end appearances of each ID (a renamed target is a new ID).
This checks declared plans, not whether rendered Manim scenes follow them.
"""
from __future__ import annotations


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def check_storyboard(storyboard: dict, beats: dict) -> list[dict[str, str]]:
    """Return {level, beat, message} errors/warnings without importing Manim.

    Missing arrays default to empty; card/focus/clear_reason default to null and
    camera defaults to "none". add.from must be explicit (null means no source).
    Empty-add beats break the ungrounded-addition streak. Warnings never fail CLI.
    """
    issues = []

    def report(level, beat, message):
        issues.append(dict(level=level, beat=beat, message=message))

    def error(beat, message):
        report("error", beat, message)

    def rows(document, label):
        if not isinstance(document, dict) or not isinstance(document.get("beats"), list):
            error("all", f"{label}.beats must be an array")
            return []
        if not document["beats"]:
            error("all", f"{label}.beats must not be empty")
        ids = []
        for i, row in enumerate(document["beats"]):
            if not isinstance(row, dict) or not _nonempty(row.get("id")):
                error(f"#{i+1}", f"{label}: id must be a nonempty string")
            else:
                ids.append(row["id"])
        if len(set(ids)) != len(ids):
            error("all", f"{label}: duplicate beat IDs")
        return document["beats"]

    board_rows = rows(storyboard, "storyboard")
    beat_rows = rows(beats, "beats.json")
    if issues:
        return issues
    actual = [b["id"] for b in board_rows]
    expected = [b["id"] for b in beat_rows]
    if actual != expected:
        for i in range(max(len(actual), len(expected))):
            a = actual[i] if i < len(actual) else "(missing)"
            e = expected[i] if i < len(expected) else "(extra)"
            if a != e:
                error(a if a != "(missing)" else e, f"ID/order mismatch: expected {e}, got {a}")

    # Validate shapes before using sets or interpreting lifecycle operations.
    for b in board_rows:
        bid = b["id"]
        for field in ("keep", "change", "add", "remove"):
            if not isinstance(b.get(field, []), list):
                error(bid, f"{field} must be an array")
        for field in ("card", "focus", "clear_reason"):
            if b.get(field) is not None and not _nonempty(b[field]):
                error(bid, f"{field} must be null or a nonempty string")
        if not _nonempty(b.get("camera", "none")):
            error(bid, "camera must be a nonempty string")
        keep = b.get("keep", [])
        if isinstance(keep, list):
            if any(not _nonempty(v) for v in keep):
                error(bid, "keep must contain object IDs")
            elif len(set(keep)) != len(keep):
                error(bid, "duplicate keep IDs")
        for field, required in (("change", ("from", "to", "how")),
                                ("add", ("id",)), ("remove", ("id", "reason"))):
            entries = b.get(field, [])
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    error(bid, f"{field} entries must be objects")
                    continue
                for key in required:
                    if not _nonempty(entry.get(key)):
                        error(bid, f"{field}.{key} must be a nonempty string")
                if field == "add" and ("from" not in entry or
                        (entry["from"] is not None and not _nonempty(entry["from"]))):
                    error(bid, "add.from must be an object ID or explicit null")
    if any(i["level"] == "error" for i in issues):
        return issues

    live = set()
    episodes = []  # Mutable [id, beat-end appearance count] for every lifetime.
    active = {}
    changes = 0
    ungrounded = []
    for b in board_rows:
        bid = b["id"]
        keep = set(b.get("keep", []))
        change = b.get("change", [])
        add = b.get("add", [])
        remove = b.get("remove", [])
        entry = live.copy()
        refs = [("keep", obj) for obj in keep]
        refs += [("change.from", c["from"]) for c in change]
        refs += [("add.from", a["from"]) for a in add if a["from"] is not None]
        refs += [("remove.id", r["id"]) for r in remove]
        for field, obj in refs:
            if obj not in entry:
                error(bid, f"{field} references absent object {obj}")
        if entry and not keep and not change and not b.get("clear_reason"):
            error(bid, "keep and change are empty with objects on stage; supply clear_reason")

        sources = [c["from"] for c in change]
        targets = [c["to"] for c in change]
        removed = [r["id"] for r in remove]
        additions = [a["id"] for a in add]
        for field, ids in (("change.from", sources), ("change.to", targets),
                           ("remove.id", removed), ("add.id", additions)):
            if len(set(ids)) != len(ids):
                error(bid, f"duplicate {field}")
        conflicting = (keep & set(removed)) | (set(sources) & set(removed)) | (keep & set(sources))
        if conflicting:
            error(bid, f"conflicting keep/change/remove: {', '.join(sorted(conflicting))}")
        retained = keep if b.get("clear_reason") else entry
        live = retained - set(sources) - set(removed)
        for obj in targets + additions:
            if obj in live:
                error(bid, f"target/add ID already on stage: {obj}")
            live.add(obj)
        focus = b.get("focus")
        if focus is not None and focus not in live:
            error(bid, f"focus references absent object {focus}")
        if len(live) > 3 and focus is None:
            report("warning", bid, f"{len(live)} objects on stage without focus")

        ended = (entry - retained) | set(removed) | {
            c["from"] for c in change if c["from"] != c["to"]}
        for obj in (set(active) - live) | (set(active) & ended):
            del active[obj]
        for obj in sorted(live):
            if obj not in active:
                active[obj] = [obj, 0]
                episodes.append(active[obj])
            active[obj][1] += 1
        changes += len(change)
        if add and all(a["from"] is None for a in add):
            ungrounded.append(bid)
            if len(ungrounded) == 4:
                report("warning", bid, f"ungrounded additions for >3 consecutive beats ({ungrounded[0]}–{bid})")
        else:
            ungrounded = []
    if not changes:
        report("warning", "all", "no change anywhere in the storyboard")
    if len(board_rows) >= 6 and all(b.get("camera", "none").strip() == "none"
                                    for b in board_rows):
        report("warning", "all", "no camera movement planned across >=6 beats (camera is none everywhere)")
    short = [obj for obj, duration in episodes if duration < 2]
    if episodes and len(short) > len(episodes) / 2:
        sample = ", ".join(short[:8]) + (", ..." if len(short) > 8 else "")
        report("warning", "all", f"{len(short)}/{len(episodes)} objects live <2 beats: {sample}")
    return issues
