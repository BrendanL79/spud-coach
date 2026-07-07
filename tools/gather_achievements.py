#!/usr/bin/env python3
"""Gather Brotato achievement (challenge) data into a standalone JSON file.

Not wired into build_dataset.py yet — a separate prep step for possible later
integration into data/brotato.json. Reads only extracted/ (challenges/*.tres
+ tools/output/achievementLocalizations.csv), matching build_dataset.py's
"only extracted/ read by the build step" rule.

Usage:
    uv run python tools/gather_achievements.py --extracted extracted --out data/achievements.json
"""

from __future__ import annotations

import argparse
import json
import os

from brotato_coach.builders.achievements import (
    build_achievement_record,
    merge_achievement_records,
    parse_achievement_localizations_csv,
)
from brotato_coach.builders.discover import find_challenge_paths


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def gather(extracted_root: str, loc_csv_path: str) -> list[dict]:
    tres_records = [
        build_achievement_record(_read(path))
        for path in find_challenge_paths(extracted_root)
    ]
    loc_by_id = parse_achievement_localizations_csv(_read(loc_csv_path))
    return merge_achievement_records(tres_records, loc_by_id)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extracted", default="extracted")
    parser.add_argument(
        "--loc-csv", default=None,
        help="defaults to <extracted>/tools/output/achievementLocalizations.csv")
    parser.add_argument("--out", default="data/achievements.json")
    args = parser.parse_args(argv)

    loc_csv = args.loc_csv or os.path.join(
        args.extracted, "tools", "output", "achievementLocalizations.csv")
    achievements = gather(args.extracted, loc_csv)
    missing_tres = sum(1 for a in achievements if not a["has_tres"])

    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(
            {"count": len(achievements), "achievements": achievements},
            fh, indent=2, ensure_ascii=False)

    print(f"Wrote {len(achievements)} achievements to {args.out} "
          f"({missing_tres} without .tres data in this extraction)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
