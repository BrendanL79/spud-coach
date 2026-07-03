"""Distill extracted/ .tres game data into data/brotato.json.

Usage:
    python build_dataset.py --extracted extracted --out data/brotato.json \
        --game-version 1.1.0.0 --generated-at 2026-07-01T00:00:00Z
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from brotato_coach import dataset
from brotato_coach.builders import discover
from brotato_coach.builders.weapons import build_weapon_record
from brotato_coach.builders.items import build_item_record
from brotato_coach.builders.characters import build_character_record
from brotato_coach.builders.sets import build_set_record
from brotato_coach.builders.localization import parse_translations_csv
from brotato_coach.tres import parse_tres


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extracted", default="extracted")
    parser.add_argument("--out", default="data/brotato.json")
    parser.add_argument("--game-version", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument(
        "--translations",
        default="recovered/.assets/resources/translations/translations.csv",
        help="decompiled Godot translations CSV; skipped if absent")
    args = parser.parse_args(argv)

    tr: dict[str, str] = {}
    if os.path.isfile(args.translations):
        tr = parse_translations_csv(_read(args.translations))

    weapons = []
    for entry in discover.find_weapon_dirs(args.extracted):
        weapons.append(build_weapon_record(
            _read(entry["stats_path"]), _read(entry["data_path"]),
            [_read(p) for p in entry.get("effect_paths", [])],
            weapon_id=entry["weapon_id"], name=entry["name"], tier=entry["tier"],
            classes=entry.get("classes", []), tr=tr,
        ))

    items = []
    for e in discover.find_item_dirs(args.extracted):
        items.append(build_item_record(
            _read(e["data_path"]), [_read(p) for p in e["effect_paths"]],
            item_id=e["item_id"], name=e["name"], tr=tr))

    characters = []
    for e in discover.find_character_dirs(args.extracted):
        data_text = _read(e["data_path"])
        res = parse_tres(data_text).resource
        characters.append(build_character_record(
            data_text, [_read(p) for p in e["effect_paths"]],
            char_id=e["char_id"], name=e["name"],
            wanted_tags=res.get("wanted_tags", []) or [],
            banned_item_groups=res.get("banned_item_groups", []) or [], tr=tr))

    sets = []
    for e in discover.find_set_dirs(args.extracted):
        sets.append(build_set_record(
            _read(e["set_data_path"]),
            {c: _read(p) for c, p in e["count_effect_paths"].items()},
            set_id=e["set_id"], name=e["name"], tr=tr))

    ds = dataset.assemble_dataset(
        game_version=args.game_version, generated_at=args.generated_at,
        weapons=weapons, items=items, characters=characters, sets=sets)

    problems = dataset.validate_dataset(ds)
    if problems:
        print("Dataset validation failed:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(ds, fh, indent=2)
    print(f"Wrote {args.out}: {len(weapons)} weapon records, {len(items)} item records, "
          f"{len(characters)} character records, {len(sets)} set records "
          f"({'localized' if tr else 'NO translations found — slug names only'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
