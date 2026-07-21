"""Diff two brotato.json datasets to triage a game/DLC update.

Usage:
    python tools/diff_dataset.py OLD.json NEW.json [--json]

Neither file is committed (both are gitignored, copyright-derived data). Keep a
base-only build as OLD (e.g. data/brotato.base.json, regenerable from the
backed-up base extraction) and diff the post-update build against it.
"""
from __future__ import annotations

import argparse
import json

_COLLECTIONS = ("weapons", "items", "characters", "sets", "enemies")
_SCALAR = (int, float, str, bool)


def _by_id(records: list) -> dict:
    return {r.get("id"): r for r in records if r.get("id") is not None}


def _scalar_field_changes(old: dict, new: dict) -> dict:
    changes: dict = {}
    for k in sorted(set(old) | set(new)):
        ov, nv = old.get(k), new.get(k)
        if ov == nv:
            continue
        if isinstance(ov, _SCALAR) and isinstance(nv, _SCALAR):
            changes[k] = [ov, nv]
        else:
            changes[k] = "<complex field changed>"
    return changes


def diff_collection(old: list, new: list) -> dict:
    o, n = _by_id(old), _by_id(new)
    changed = {}
    for cid in sorted(set(o) & set(n)):
        ch = _scalar_field_changes(o[cid], n[cid])
        if ch:
            changed[cid] = ch
    return {"added": sorted(set(n) - set(o)),
            "removed": sorted(set(o) - set(n)),
            "changed": changed}


def _all_unmodeled(ds: dict) -> set[str]:
    keys: set[str] = set()
    for coll in _COLLECTIONS:
        for r in ds.get(coll, []):
            keys.update(str(k) for k in r.get("unmodeled_effects", []) or [])
    return keys


def diff_datasets(old: dict, new: dict) -> dict:
    result: dict = {coll: diff_collection(old.get(coll, []), new.get(coll, []))
                    for coll in _COLLECTIONS}
    result["new_sources"] = sorted(set(new.get("content_sources", []))
                                   - set(old.get("content_sources", [])))
    result["new_unmodeled_effects"] = sorted(_all_unmodeled(new) - _all_unmodeled(old))
    result["game_version"] = [old.get("game_version"), new.get("game_version")]
    result["schema_version"] = [old.get("schema_version"), new.get("schema_version")]
    return result


def format_report(diff: dict) -> str:
    gv = diff.get("game_version", [None, None])
    sv = diff.get("schema_version", [None, None])
    lines = [f"game_version: {gv[0]} -> {gv[1]}",
             f"schema_version: {sv[0]} -> {sv[1]}"]
    if diff.get("new_sources"):
        lines.append(f"new content_sources: {', '.join(diff['new_sources'])}")
    for coll in _COLLECTIONS:
        d = diff[coll]
        lines.append(f"\n{coll}: +{len(d['added'])} / -{len(d['removed'])} / ~{len(d['changed'])}")
        if d["added"]:
            lines.append(f"  added: {', '.join(d['added'])}")
        if d["removed"]:
            lines.append(f"  removed: {', '.join(d['removed'])}")
        for cid, ch in d["changed"].items():
            lines.append(f"  changed {cid}: {ch}")
    nu = diff.get("new_unmodeled_effects") or []
    lines.append(f"\nnew unmodeled effects ({len(nu)}): {', '.join(nu) if nu else '(none)'}")
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Diff two brotato.json datasets.")
    p.add_argument("old")
    p.add_argument("new")
    p.add_argument("--json", action="store_true", help="emit the diff as JSON")
    args = p.parse_args(argv)
    with open(args.old, encoding="utf-8") as fh:
        old = json.load(fh)
    with open(args.new, encoding="utf-8") as fh:
        new = json.load(fh)
    diff = diff_datasets(old, new)
    print(json.dumps(diff, indent=2) if args.json else format_report(diff))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
