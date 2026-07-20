"""Distill extracted/ .tres game data into data/brotato.json.

Usage:
    python build_dataset.py --extracted extracted --recovered recovered --out data/brotato.json

--game-version and --generated-at are both optional: game version auto-detects from
--version-file (default <recovered>/singletons/progress_data.gd), and generated_at defaults
to the current UTC time. Pass either explicitly to override, e.g. for a pinned/reproducible
build. Running from outside the repo root (e.g. a worktree) needs only --extracted and
--recovered pointed at the real game-data checkout.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, UTC

from brotato_coach import dataset
from brotato_coach.builders import discover
from brotato_coach.builders.weapons import build_weapon_record
from brotato_coach.builders.items import build_item_record
from brotato_coach.builders.characters import build_character_record
from brotato_coach.builders.sets import build_set_record
from brotato_coach.builders.enemies import build_enemy_record
from brotato_coach.builders.waves import build_wave_record
from brotato_coach.builders.localization import parse_translations_csv
from brotato_coach.builders.version import parse_game_version
from brotato_coach.builders.timestamps import format_generated_at
from brotato_coach.builders.provenance import detect_source
from brotato_coach.tres import parse_tres


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def resolve_recovered_paths(recovered: str, version_file: str | None,
                            translations: str | None) -> tuple[str, str]:
    """Derive the decompiled-source input paths from the recovered/ root.

    Explicit --version-file/--translations values win; otherwise both derive
    from --recovered, so a build run outside the repo root needs two path
    flags (--extracted/--recovered), not four.
    """
    return (
        version_file or os.path.join(recovered, "singletons", "progress_data.gd"),
        translations or os.path.join(recovered, ".assets", "resources",
                                     "translations", "translations.csv"),
    )


def _coverage_report_lines(coverage: dict, unmodeled_by_source: dict) -> list[str]:
    lines: list[str] = []
    for label, key in (("new content trees", "unclaimed_trees"),
                       ("new weapon kinds", "unknown_weapon_kinds"),
                       ("new/unmodeled zones", "unmodeled_zones")):
        vals = coverage.get(key) or []
        if vals:
            lines.append(f"  {label}: {', '.join(vals)}")
    for src, keys in (unmodeled_by_source or {}).items():
        if keys:
            shown = ", ".join(keys[:8]) + ("…" if len(keys) > 8 else "")
            lines.append(f"  unmodeled effects [{src}]: {len(keys)} ({shown})")
    return lines


def _has_blocking_issues(coverage: dict, unmodeled_by_source: dict) -> bool:
    if any(coverage.get(k) for k in
           ("unclaimed_trees", "unknown_weapon_kinds", "unmodeled_zones")):
        return True
    return any(bool(v) for v in (unmodeled_by_source or {}).values())


def _stamp_sources(*record_lists) -> None:
    """Tag every built record with its content origin. Today detect_source
    returns "base" for all; on DLC day it learns the real signal (see
    provenance.py) and this stamps records without further plumbing changes."""
    for records in record_lists:
        for rec in records:
            rec["source"] = detect_source(record=rec)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extracted", default="extracted")
    parser.add_argument(
        "--recovered", default="recovered",
        help="decompiled-code root; --version-file and --translations derive "
             "from it unless passed explicitly")
    parser.add_argument("--out", default="data/brotato.json")
    parser.add_argument(
        "--game-version", default=None,
        help="override the auto-detected version; auto-detected from --version-file if omitted")
    parser.add_argument(
        "--generated-at", default=None,
        help="override the build timestamp; defaults to the current UTC time if omitted")
    parser.add_argument(
        "--version-file", default=None,
        help="decompiled Godot singleton providing the VERSION constant; "
             "used when --game-version is omitted "
             "(default: <recovered>/singletons/progress_data.gd)")
    parser.add_argument(
        "--translations", default=None,
        help="decompiled Godot translations CSV; skipped if absent "
             "(default: <recovered>/.assets/resources/translations/translations.csv)")
    parser.add_argument(
        "--strict", action="store_true",
        help="fail the build (exit 1, no write) if coverage finds new content "
             "trees/weapon-kinds/zones or any unmodeled effect")
    args = parser.parse_args(argv)
    version_file, translations = resolve_recovered_paths(
        args.recovered, args.version_file, args.translations)

    game_version = args.game_version
    if game_version is None:
        if os.path.isfile(version_file):
            game_version = parse_game_version(_read(version_file))
        if game_version is None:
            parser.error(
                f"could not detect game version from {version_file}; "
                "pass --game-version explicitly")

    generated_at = args.generated_at
    if generated_at is None:
        generated_at = format_generated_at(datetime.now(UTC))

    tr: dict[str, str] = {}
    if os.path.isfile(translations):
        tr = parse_translations_csv(_read(translations))

    weapons = []
    for entry in discover.find_weapon_dirs(args.extracted):
        effect_paths = entry.get("effect_paths", [])
        companion_paths = entry.get("effect_companion_paths", {})
        effect_companion_texts = [
            {field: _read(path) for field, path in companion_paths[p].items()}
            if p in companion_paths else None
            for p in effect_paths
        ]
        weapons.append(build_weapon_record(
            _read(entry["stats_path"]), _read(entry["data_path"]),
            [_read(p) for p in effect_paths], effect_companion_texts,
            weapon_id=entry["weapon_id"], name=entry["name"], tier=entry["tier"],
            classes=entry.get("classes", []), tr=tr,
        ))

    items = [
        build_item_record(
            _read(e["data_path"]), [_read(p) for p in e["effect_paths"]],
            item_id=e["item_id"], name=e["name"], tr=tr)
        for e in discover.find_item_dirs(args.extracted)
    ]

    sets = [
        build_set_record(
            _read(e["set_data_path"]),
            {c: _read(p) for c, p in e["count_effect_paths"].items()},
            set_id=e["set_id"], name=e["name"], tr=tr)
        for e in discover.find_set_dirs(args.extracted)
    ]
    set_names = {s["id"]: s["display_name"] for s in sets}

    characters = []
    for e in discover.find_character_dirs(args.extracted):
        data_text = _read(e["data_path"])
        res = parse_tres(data_text).resource
        characters.append(build_character_record(
            data_text, [_read(p) for p in e["effect_paths"]],
            char_id=e["char_id"], name=e["name"],
            wanted_tags=res.get("wanted_tags", []) or [],
            banned_item_groups=res.get("banned_item_groups", []) or [],
            tr=tr, set_names=set_names))

    enemies = []
    for e in discover.find_enemy_dirs(args.extracted):
        scene_text = _read(e["scene_path"]) if e.get("scene_path") else None
        enemies.append(build_enemy_record(
            _read(e["stats_path"]), scene_text,
            enemy_id=e["enemy_id"], name=e["name"], tr=tr))

    zone_1_waves = []
    enemy_ids_in_waves: set[str] = set()
    for wv in discover.find_zone_waves(args.extracted):
        group_texts = [_read(p) for p in wv["group_paths"]]
        unit_texts_by_group = {
            gkey: [_read(p) for p in paths]
            for gkey, paths in wv["unit_paths_by_group"].items()
        }
        rec = build_wave_record(_read(wv["wave_path"]), group_texts,
                                unit_texts_by_group, wave=wv["wave"])
        for g in rec["groups"]:
            if g.get("enemy_id"):
                enemy_ids_in_waves.add(g["enemy_id"])
        zone_1_waves.append(rec)

    # appears_in: "normal" for any enemy referenced by a numbered wave
    for e in enemies:
        e["appears_in"] = ["normal"] if e["id"] in enemy_ids_in_waves else []

    _stamp_sources(weapons, items, characters, sets, enemies, zone_1_waves)

    ds = dataset.assemble_dataset(
        game_version=game_version, generated_at=generated_at,
        weapons=weapons, items=items, characters=characters, sets=sets,
        enemies=enemies, zone_1_waves=zone_1_waves)

    problems = dataset.validate_dataset(ds)
    if problems:
        print("Dataset validation failed:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    coverage = discover.coverage_report(args.extracted)
    unmodeled = dataset.aggregate_unmodeled_effects(ds)
    report_lines = _coverage_report_lines(coverage, unmodeled)
    if report_lines:
        print("Coverage / unmodeled-content report:", file=sys.stderr)
        for line in report_lines:
            print(line, file=sys.stderr)
        if args.strict and _has_blocking_issues(coverage, unmodeled):
            print("Build failed (--strict): un-triaged content above; "
                  "triage or extend the baseline before shipping.", file=sys.stderr)
            return 1

    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(ds, fh, indent=2)
    print(f"Wrote {args.out}: {len(weapons)} weapon records, {len(items)} item records, "
          f"{len(characters)} character records, {len(sets)} set records, "
          f"{len(enemies)} enemy records, {len(zone_1_waves)} zone_1 wave records "
          f"({'localized' if tr else 'NO translations found — slug names only'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
