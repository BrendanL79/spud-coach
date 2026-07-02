from brotato_coach.builders.characters import build_character_record
from brotato_coach.builders.sets import build_set_record

RANGER_DATA = """[gd_resource type="Resource" format=2]
[resource]
tier = 0
"""

EFF_FLAT_RANGE = '[resource]\nkey = "stat_range"\nvalue = 50\neffect_sign = 3\n'
EFF_RD_GAIN = '[resource]\nkey = "effect_increase_stat_gains"\nvalue = 50\nstats_modified = [ "stat_ranged_damage" ]\n'
EFF_HP_GAIN = '[resource]\nkey = "effect_reduce_stat_gains"\nvalue = -25\nstats_modified = [ "stat_max_hp" ]\n'
EFF_NO_MELEE = '[resource]\nkey = "no_melee_weapons"\nvalue = 1\n'


def test_ranger_gain_modifiers():
    rec = build_character_record(
        RANGER_DATA, [EFF_FLAT_RANGE, EFF_RD_GAIN, EFF_HP_GAIN, EFF_NO_MELEE],
        char_id="character_ranger", name="Ranger",
        wanted_tags=["stat_ranged_damage", "stat_range"],
        banned_item_groups=["melee_damage"],
    )
    assert {"stat": "stat_ranged_damage", "pct": 50} in rec["gain_modifiers"]
    assert {"stat": "stat_max_hp", "pct": -25} in rec["gain_modifiers"]
    assert {"stat": "stat_range", "value": 50} in rec["flat_bonuses"]
    assert "no_melee_weapons" in rec["special_effects"]


def test_set_bonuses_sorted_by_count():
    set_data = '[gd_resource type="Resource" format=2]\n[resource]\nmy_id = "set_gun"\n'
    eff2 = '[resource]\nkey = "stat_range"\nvalue = 5\n'
    eff6 = '[resource]\nkey = "stat_range"\nvalue = 50\n'
    rec = build_set_record(set_data, {6: eff6, 2: eff2}, set_id="set_gun", name="Gun")
    assert [b["count"] for b in rec["bonuses"]] == [2, 6]
    assert rec["bonuses"][1]["effect"] == {"key": "stat_range", "value": 50}


def test_starting_weapon_grant_excluded_from_special_effects():
    from brotato_coach.builders.characters import build_character_record
    data = '[gd_resource type="Resource" format=2]\n[resource]\ntier = 0\n'
    weapon_grant = '[resource]\nkey = "weapon_pistol_1"\nvalue = 1\n'
    no_melee = '[resource]\nkey = "no_melee_weapons"\nvalue = 1\n'
    rec = build_character_record(data, [weapon_grant, no_melee], char_id="c", name="C",
                                 wanted_tags=[], banned_item_groups=[])
    assert "no_melee_weapons" in rec["special_effects"]
    assert "weapon_pistol_1" not in rec["special_effects"]
