from __future__ import annotations

from brotato_coach.builders.localization import resolve_text
from brotato_coach.tres import parse_tres

_GAIN_KEYS = {"effect_increase_stat_gains", "effect_reduce_stat_gains"}


def build_character_record(data_text: str, effect_texts: list[str], *, char_id: str,
                          name: str, wanted_tags: list[str],
                          banned_item_groups: list[str],
                          tr: dict[str, str] | None = None) -> dict:
    d = parse_tres(data_text).resource
    flat_bonuses: list[dict] = []
    gain_modifiers: list[dict] = []
    special_effects: list[str] = []

    for text in effect_texts:
        r = parse_tres(text).resource
        key = str(r.get("key", ""))
        if key in _GAIN_KEYS:
            mods = r.get("stats_modified", []) or []
            stat = mods[0] if mods else None
            if stat is not None:
                gain_modifiers.append({"stat": stat, "pct": r.get("value", 0)})
        elif key.startswith("stat_"):
            flat_bonuses.append({"stat": key, "value": r.get("value", 0)})
        else:
            if not key.startswith("weapon_"):
                special_effects.append(key)

    return {
        "id": char_id,
        "name": name,
        "display_name": resolve_text(tr, d.get("name"), name),
        "description": resolve_text(tr, d.get("description")),
        "wanted_tags": wanted_tags,
        "banned_item_groups": banned_item_groups,
        "flat_bonuses": flat_bonuses,
        "gain_modifiers": gain_modifiers,
        "special_effects": special_effects,
    }
