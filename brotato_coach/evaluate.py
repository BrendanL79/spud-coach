from __future__ import annotations

from brotato_coach import query


def _short(stat: str) -> str:
    return stat[len("stat_"):] if stat.startswith("stat_") else stat


def _classify(effect: dict, item: dict, character: dict, current_stats: dict) -> tuple[str, str]:
    key = str(effect["key"])
    value = effect.get("value", 0)

    if "cap_at_current_value" in item.get("archetype", []) and (
        key.endswith("_cap") or "CAP_AT_CURRENT_VALUE" in str(effect.get("text_key", ""))
    ):
        frozen = item.get("frozen_stat") or "a stat"
        cur = current_stats.get(_short(frozen)) if item.get("frozen_stat") else None
        at = f" at current value ({cur})" if cur is not None else " at its current value"
        return "harmful", f"freezes {frozen}{at} for the rest of the run"

    banned = "melee_damage" in character.get("banned_item_groups", [])
    no_melee = "no_melee_weapons" in character.get("special_effects", [])
    if key == "stat_melee_damage" and (banned or no_melee):
        return "wasted", "character cannot use melee weapons"

    if key in character.get("wanted_tags", []):
        return "live", f"{key} is a wanted stat for this character"

    if key.startswith("stat_") and isinstance(value, (int, float)) and value > 0 \
            and current_stats.get(_short(key), 0) <= 0:
        return "wasted", f"no investment in {_short(key)}"

    return "live", "applies to this build"


def evaluate_item_for_build(ds: dict, item_name: str, character_name: str,
                            current_stats: dict) -> dict:
    item = query.get_item(ds, item_name)
    if "id" not in item:
        return item
    character = query.get_character(ds, character_name)
    if "id" not in character:
        return character

    effects = []
    for eff in item.get("effects", []):
        verdict, reason = _classify(eff, item, character, current_stats)
        effects.append({"effect": eff, "verdict": verdict, "reason": reason})

    counts = {"live": 0, "wasted": 0, "harmful": 0}
    for e in effects:
        counts[e["verdict"]] = counts.get(e["verdict"], 0) + 1
    summary = (f"{counts['live']} live, {counts['wasted']} wasted, "
               f"{counts['harmful']} harmful effect(s) for {character['name']}")

    return {"item": item["name"], "character": character["name"],
            "effects": effects, "summary": summary}
