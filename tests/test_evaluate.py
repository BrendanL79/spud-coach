from brotato_coach.evaluate import evaluate_item_for_build

DS = {
    "items": [{
        "id": "item_handcuffs", "name": "Handcuffs", "tier": 2, "value": 80,
        "tags": ["stat_melee_damage", "stat_ranged_damage", "stat_elemental_damage"],
        "archetype": ["cap_at_current_value"], "frozen_stat": "stat_max_hp",
        "scaling_stats": ["stat_melee_damage", "stat_ranged_damage", "stat_elemental_damage"],
        "damage_tags": ["stat_melee_damage", "stat_ranged_damage", "stat_elemental_damage"],
        "effects": [
            {"key": "stat_melee_damage", "value": 8, "effect_sign": 3, "text_key": ""},
            {"key": "stat_ranged_damage", "value": 8, "effect_sign": 3, "text_key": ""},
            {"key": "stat_elemental_damage", "value": 8, "effect_sign": 3, "text_key": ""},
            {"key": "hp_cap", "value": 0, "effect_sign": 0, "text_key": "EFFECT_HP_CAP_AT_CURRENT_VALUE"},
        ],
    }],
    "characters": [{
        "id": "character_ranger", "name": "Ranger",
        "wanted_tags": ["stat_ranged_damage", "stat_range"],
        "banned_item_groups": ["melee_damage"],
        "special_effects": ["no_melee_weapons"],
    }],
}


def _verdict(result, key):
    for e in result["effects"]:
        if e["effect"]["key"] == key:
            return e["verdict"]
    raise AssertionError(f"no effect {key}")


def test_handcuffs_on_ranger_breakdown():
    result = evaluate_item_for_build(DS, "Handcuffs", "Ranger",
                                     {"ranged_damage": 6, "melee_damage": 0, "elemental_damage": -1})
    assert _verdict(result, "stat_ranged_damage") == "live"
    assert _verdict(result, "stat_melee_damage") == "wasted"
    assert _verdict(result, "stat_elemental_damage") == "wasted"
    assert _verdict(result, "hp_cap") == "harmful"


def test_handcuffs_hp_cap_reason_mentions_frozen_stat():
    result = evaluate_item_for_build(DS, "Handcuffs", "Ranger", {"max_hp": 36})
    cap = next(e for e in result["effects"] if e["effect"]["key"] == "hp_cap")
    assert "stat_max_hp" in cap["reason"]
    assert "36" in cap["reason"]


def test_rule5_default_live_for_uninvested_but_present_effect():
    # a stat_ effect with value <= 0 (not wanted, not melee, not cap) falls through to live
    ds = {
        "items": [{"id": "item_x", "name": "X", "tags": [], "archetype": [],
                   "frozen_stat": None,
                   "effects": [{"key": "stat_armor", "value": 0, "effect_sign": 3, "text_key": ""}]}],
        "characters": [{"id": "character_c", "name": "C", "wanted_tags": [],
                        "banned_item_groups": [], "special_effects": []}],
    }
    r = evaluate_item_for_build(ds, "X", "C", {})
    assert r["effects"][0]["verdict"] == "live"


def test_missing_item_returns_error():
    ds = {"items": [], "characters": [{"id": "character_c", "name": "C"}]}
    r = evaluate_item_for_build(ds, "Nope", "C", {})
    assert r["error"] == "not_found"
