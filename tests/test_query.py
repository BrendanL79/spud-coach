from brotato_coach import query

DS = {
    "weapons": [
        {"id": "weapon_shredder", "name": "Shredder", "tier": 4, "scaling_stats": [["stat_ranged_damage", 0.5]]},
        {"id": "weapon_shredder", "name": "Shredder", "tier": 3, "scaling_stats": [["stat_ranged_damage", 0.5]]},
        {"id": "weapon_wand", "name": "Wand", "tier": 1, "scaling_stats": [["stat_elemental_damage", 1.0]]},
    ],
    "items": [
        {"id": "item_handcuffs", "name": "Handcuffs", "tier": 2, "tags": ["stat_ranged_damage"],
         "archetype": ["cap_at_current_value"], "scaling_stats": ["stat_ranged_damage"]},
        {"id": "item_lens", "name": "Lens", "tier": 0, "tags": ["stat_ranged_damage"],
         "archetype": [], "scaling_stats": ["stat_ranged_damage"]},
    ],
    "characters": [{"id": "character_ranger", "name": "Ranger"}],
    "sets": [{"id": "set_gun", "name": "Gun", "bonuses": []}],
}


def test_get_weapon_specific_tier():
    rec = query.get_weapon(DS, "Shredder", tier=4)
    assert rec["tier"] == 4


def test_get_weapon_all_tiers():
    rec = query.get_weapon(DS, "Shredder")
    assert {m["tier"] for m in rec["matches"]} == {3, 4}


def test_get_weapon_fuzzy_not_found():
    rec = query.get_weapon(DS, "shreddar", tier=4)
    assert rec["error"] == "not_found"
    assert "Shredder" in rec["did_you_mean"] or "weapon_shredder" in rec["did_you_mean"]


def test_list_weapons_by_scaling_stat():
    result = query.list_weapons(DS, scaling_stat="stat_ranged_damage")
    assert all(w["name"] == "Shredder" for w in result)


def test_list_items_by_archetype():
    result = query.list_items(DS, archetype="cap_at_current_value")
    assert [i["name"] for i in result] == ["Handcuffs"]


def test_get_weapon_matches_display_name():
    ds = {"weapons": [{"id": "weapon_smg", "name": "Smg",
                       "display_name": "SMG Mk. II", "tier": 1}]}
    assert query.get_weapon(ds, "smg mk. ii")["id"] == "weapon_smg"


def test_suggestions_include_display_names():
    ds = {"weapons": [{"id": "weapon_smg", "name": "Smg",
                       "display_name": "SMG Mk. II", "tier": 1}]}
    rec = query.get_weapon(ds, "smg mk 2")
    assert rec["error"] == "not_found"
    assert "SMG Mk. II" in rec["did_you_mean"]
