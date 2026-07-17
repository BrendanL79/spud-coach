"""Parse a Brotato `run.json` save artifact into the coach's vocabulary.

Pure logic: `parse_run` takes an already-parsed save dict and returns a
normalized build (character, weapons with 1-indexed tiers, items, realized
stats, run context). No file or dataset I/O — the server layer handles reading
the file and running the analyses.

Save-format notes (verified against a real v3 save; the format carries no
version field of its own, so we validate by structure and fail loudly on an
unrecognized shape rather than silently mis-reading):
- The build lives at `current_run_state.players_data[0]`.
- Weapon `tier` is a 0-indexed string; the coach uses 1-indexed tiers.
- The per-player `items` array also lists the character as a pseudo-item.
- Realized stats live in `effects`, keyed by Godot's djb2 string hash of the
  `stat_*` name rather than the name itself.
"""

from __future__ import annotations

import json

from brotato_coach.schemas import Stats


class RunFormatError(ValueError):
    """Raised when a save doesn't match the expected Brotato run structure."""


def godot_string_hash(s: str) -> int:
    """Godot 3's `String.hash()` (djb2: seed 5381, multiply by 33, uint32).

    Brotato keys a player's realized `effects` by this hash of each stat name,
    so we recompute it to look stats back up by their known names.
    """
    h = 5381
    for byte in s.encode("utf-8"):
        h = ((h << 5) + h + byte) & 0xFFFFFFFF
    return h


# short stat name (as the Stats schema / answer layer use) -> hashed effects key.
# `damage` is the game's stat_percent_damage; `level` is not an effects stat.
_IRREGULAR_STAT_NAMES = {"damage": "stat_percent_damage"}
_STAT_KEY_BY_SHORT = {
    short: str(godot_string_hash(_IRREGULAR_STAT_NAMES.get(short, f"stat_{short}")))
    for short in Stats.model_fields if short != "level"
}


def _player(run: dict) -> dict:
    if not isinstance(run, dict):
        raise RunFormatError("run save is not a JSON object")
    crs = run.get("current_run_state")
    if not isinstance(crs, dict):
        raise RunFormatError("missing current_run_state — not a Brotato run save")
    players = crs.get("players_data")
    if not isinstance(players, list) or not players:
        raise RunFormatError("current_run_state.players_data is empty or missing")
    return players[0]


def _weapons(player: dict) -> list[dict]:
    out = []
    for w in player.get("weapons", []) or []:
        wid = w.get("weapon_id")
        if not wid:
            continue
        out.append({"id": wid, "tier": int(w.get("tier", 0)) + 1})
    return out


def _items(player: dict) -> list[str]:
    # The items array also carries the character as a pseudo-item; keep only
    # true items (ids are prefixed `item_`).
    return [it["my_id"] for it in (player.get("items", []) or [])
            if str(it.get("my_id", "")).startswith("item_")]


def _stats(player: dict) -> dict:
    effects = player.get("effects", {}) or {}
    out = {short: effects[key]
           for short, key in _STAT_KEY_BY_SHORT.items()
           if key in effects}
    # level is not an effects stat — it lives on the player dict directly, but
    # the answer layer reads it from the stats block (stat_levels scaling).
    level = player.get("current_level")
    if level is not None:
        out["level"] = level
    return out


def _context(run: dict, player: dict) -> dict:
    crs = run["current_run_state"]
    return {
        "wave": crs.get("current_wave"),
        "danger": crs.get("current_difficulty"),
        "nb_of_waves": crs.get("nb_of_waves"),
        "endless": crs.get("is_endless_run"),
        "coop": crs.get("is_coop_run"),
        "health": player.get("current_health"),
        "gold": player.get("gold"),
        "level": player.get("current_level"),
    }


def load_run(*, path: str | None = None, run_json: str | None = None) -> dict:
    """Read a run save into a dict from exactly one source.

    `run_json` is the file's contents (e.g. an uploaded attachment); `path` is
    a location on disk (e.g. the player's Brotato save directory). This is the
    only I/O in this module — the server tool passes whichever the caller has.
    Raises RunFormatError on bad arguments, a missing file, or invalid JSON.
    """
    if (path is None) == (run_json is None):
        raise RunFormatError("provide exactly one of `path` or `run_json`")
    if run_json is None:
        try:
            with open(path, encoding="utf-8") as fh:
                run_json = fh.read()
        except (OSError, UnicodeDecodeError) as exc:
            # UnicodeDecodeError is a ValueError, not an OSError; catch it too
            # so a non-UTF-8 file still surfaces as the structured error.
            raise RunFormatError(f"could not read run file: {exc}") from exc
    try:
        return json.loads(run_json)
    except json.JSONDecodeError as exc:
        raise RunFormatError(f"run file is not valid JSON: {exc}") from exc


def parse_run(run: dict) -> dict:
    """Normalize a parsed Brotato save into a build description.

    Returns `{character, weapons, items, stats, context}`. Raises
    RunFormatError if the structure isn't a recognizable run save.
    """
    player = _player(run)
    character = player.get("current_character")
    if not character:
        raise RunFormatError("players_data[0] has no current_character")
    return {
        "character": character,
        "weapons": _weapons(player),
        "items": _items(player),
        "stats": _stats(player),
        "context": _context(run, player),
    }
