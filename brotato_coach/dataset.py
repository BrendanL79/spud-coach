from __future__ import annotations

import json

from brotato_coach.builders.mechanics import STAT_MECHANICS

DATASET_VERSION = 3

_REQUIRED_WEAPON_KEYS = ("id", "name", "tier", "dps_slope_per_rd", "dps_at_zero_rd")


def assemble_dataset(*, game_version: str, generated_at: str, weapons: list,
                     items: list, characters: list, sets: list) -> dict:
    return {
        "schema_version": DATASET_VERSION,
        "game_version": game_version,
        "generated_at": generated_at,
        "stat_mechanics": STAT_MECHANICS,
        "weapons": weapons,
        "items": items,
        "characters": characters,
        "sets": sets,
    }


def validate_dataset(dataset: dict) -> list[str]:
    problems: list[str] = [
        f"missing top-level key: {key}"
        for key in ("schema_version", "game_version", "weapons", "items", "characters", "sets")
        if key not in dataset
    ]

    for w in dataset.get("weapons", []):
        wid = w.get("id", "<unknown>")
        problems.extend(f"weapon {wid} missing key: {k}" for k in _REQUIRED_WEAPON_KEYS if k not in w)
        tier = w.get("tier")
        if not isinstance(tier, int) or not (1 <= tier <= 4):
            problems.append(f"weapon {wid} has invalid tier: {tier}")

    for it in dataset.get("items", []):
        if not isinstance(it.get("effects"), list):
            problems.append(f"item {it.get('id', '<unknown>')} missing effects list")
        if "id" not in it:
            problems.append(f"item missing id: {it.get('name', '<unknown>')}")
    for ch in dataset.get("characters", []):
        if "id" not in ch:
            problems.append(f"character missing id: {ch.get('name', '<unknown>')}")
        if not isinstance(ch.get("gain_modifiers"), list):
            problems.append(f"character {ch.get('id', '<unknown>')} missing gain_modifiers list")
    problems.extend(
        f"set {st.get('id', '<unknown>')} missing bonuses list"
        for st in dataset.get("sets", [])
        if not isinstance(st.get("bonuses"), list)
    )

    return problems


def load_dataset(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"dataset not found at {path}; run build_dataset.py first"
        ) from exc
