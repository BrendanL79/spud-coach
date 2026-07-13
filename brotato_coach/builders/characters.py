from __future__ import annotations

from brotato_coach.builders.localization import resolve_text
from brotato_coach.tres import parse_tres

_GAIN_KEYS = {"effect_increase_stat_gains", "effect_reduce_stat_gains"}


def _set_name(set_id: str, set_names: dict[str, str]) -> str:
    name = set_names.get(set_id)
    if name:
        return name
    slug = set_id[len("set_"):] if set_id.startswith("set_") else set_id
    return slug.replace("_", " ").title()


def build_character_record(data_text: str, effect_texts: list[str], *, char_id: str,
                          name: str, wanted_tags: list[str],
                          banned_item_groups: list[str],
                          tr: dict[str, str] | None = None,
                          set_names: dict[str, str] | None = None) -> dict:
    d = parse_tres(data_text).resource
    flat_bonuses: list[dict] = []
    gain_modifiers: list[dict] = []
    special_effects: list[str] = []
    class_bonuses: list[dict] = []
    set_names = set_names or {}

    for text in effect_texts:
        r = parse_tres(text).resource
        key = str(r.get("key", ""))
        set_id = r.get("set_id")
        if key in _GAIN_KEYS:
            mods = r.get("stats_modified", []) or []
            stat = mods[0] if mods else None
            if stat is not None:
                gain_modifiers.append({"stat": stat, "pct": r.get("value", 0)})
        elif set_id:
            class_bonuses.append({
                "set_id": str(set_id),
                "set_name": _set_name(str(set_id), set_names),
                "stat": str(r.get("stat_name", "")),
                "stat_displayed": str(r.get("stat_displayed_name", "")),
                "value": r.get("value", 0),
            })
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
        "class_bonuses": class_bonuses,
    }
