from __future__ import annotations

import re

from brotato_coach.tres import parse_tres

_CAP_STAT_MAP = {
    "hp_cap": "stat_max_hp",
    "speed_cap": "stat_speed",
    "dodge_cap": "stat_dodge",
    "crit_chance_cap": "stat_crit_chance",
    "curse_cap": "stat_curse",
}

_DAMAGE_TAGS = ("stat_melee_damage", "stat_ranged_damage", "stat_elemental_damage")


def _effect_record(text: str) -> dict:
    r = parse_tres(text).resource
    return {
        "key": r.get("key", ""),
        "value": r.get("value", 0),
        "effect_sign": r.get("effect_sign", 0),
        "text_key": r.get("text_key", ""),
    }


def build_item_record(data_text: str, effect_texts: list[str], *, item_id: str,
                      name: str) -> dict:
    d = parse_tres(data_text).resource
    effects = [_effect_record(t) for t in effect_texts]
    tags = d.get("tags", []) or []

    archetype: list[str] = []
    frozen_stat = None
    scaling_stats: list[str] = []
    for eff in effects:
        key = str(eff["key"])
        text_key = str(eff["text_key"])
        is_cap = key.endswith("_cap") or bool(re.search(r"CAP_AT_CURRENT_VALUE", text_key))
        if is_cap:
            if "cap_at_current_value" not in archetype:
                archetype.append("cap_at_current_value")
            mapped = _CAP_STAT_MAP.get(key)
            if mapped is not None:
                frozen_stat = mapped
        if key.startswith("stat_") and key not in scaling_stats:
            scaling_stats.append(key)

    return {
        "id": item_id,
        "name": name,
        "tier": d.get("tier", 0),
        "value": d.get("value", 0),
        "tags": tags,
        "effects": effects,
        "archetype": archetype,
        "frozen_stat": frozen_stat,
        "scaling_stats": scaling_stats,
        "damage_tags": [t for t in tags if t in _DAMAGE_TAGS],
    }
