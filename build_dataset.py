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


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extracted", default="extracted")
    parser.add_argument("--out", default="data/brotato.json")
    parser.add_argument("--game-version", required=True)
    parser.add_argument("--generated-at", required=True)
    args = parser.parse_args(argv)

    weapons = []
    for entry in discover.find_weapon_dirs(args.extracted):
        weapons.append(build_weapon_record(
            _read(entry["stats_path"]), _read(entry["data_path"]),
            weapon_id=entry["weapon_id"], name=entry["name"], tier=entry["tier"],
        ))

    # Items/characters/sets discovery wiring follows the same shape as weapons;
    # they are assembled here once their discovery helpers land. For the first
    # buildable dataset, weapons alone produce a valid, useful artifact.
    ds = dataset.assemble_dataset(
        game_version=args.game_version, generated_at=args.generated_at,
        weapons=weapons, items=[], characters=[], sets=[],
    )

    problems = dataset.validate_dataset(ds)
    if problems:
        print("Dataset validation failed:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(ds, fh, indent=2)
    print(f"Wrote {args.out}: {len(weapons)} weapon records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
