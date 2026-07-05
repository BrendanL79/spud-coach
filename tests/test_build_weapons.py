import math

from brotato_coach.builders.weapons import build_weapon_record

STATS = """[gd_resource type="Resource" format=2]
[resource]
cooldown = 45
damage = 25
accuracy = 1.0
crit_chance = 0.03
crit_damage = 2.0
recoil_duration = 0.15
piercing = 3
nb_projectiles = 1
scaling_stats = [ [ "stat_ranged_damage", 0.5 ] ]
can_have_negative_knockback = false
knockback = 0
"""

DATA = """[gd_resource type="Resource" format=2]
[resource]
weapon_id = "weapon_shredder"
tier = 3
effects = [  ]
"""


def test_weapon_record_core_fields():
    rec = build_weapon_record(STATS, DATA, weapon_id="weapon_shredder",
                              name="Shredder", tier=4)
    assert rec["id"] == "weapon_shredder"
    assert rec["tier"] == 4
    assert rec["base_damage"] == 25
    assert rec["scaling_stats"] == [["stat_ranged_damage", 0.5]]
    assert rec["can_have_negative_knockback"] is False


def test_weapon_record_precomputed_dps_line():
    rec = build_weapon_record(STATS, DATA, weapon_id="weapon_shredder",
                              name="Shredder", tier=4)
    assert math.isclose(rec["cycle_time"], 1.05, rel_tol=1e-6)
    assert math.isclose(rec["dps_at_zero_rd"], 23.8095, rel_tol=1e-4)
    assert math.isclose(rec["dps_slope_per_rd"], 0.47619, rel_tol=1e-4)


def test_weapon_record_burst_folds_into_cycle_time():
    stats = ('[gd_resource type="Resource" format=2]\n[resource]\n'
             'cooldown = 11\ndamage = 40\naccuracy = 0.9\nrecoil_duration = 0.1\n'
             'scaling_stats = [ [ "stat_ranged_damage", 2.0 ] ]\n'
             'additional_cooldown_every_x_shots = 6\nadditional_cooldown_multiplier = 8.0\n')
    data = '[gd_resource type="Resource" format=2]\n[resource]\neffects = [  ]\n'
    rec = build_weapon_record(stats, data, weapon_id="w", name="W", tier=4)
    # Revolver T4 golden: cycle ~0.62778, dps0 ~57.35, slope ~2.8673
    assert abs(rec["cycle_time"] - 0.62778) < 1e-3
    assert abs(rec["dps_at_zero_rd"] - 57.35) < 1e-2


def test_weapon_record_rd_absent_slope_zero():
    stats = ('[gd_resource type="Resource" format=2]\n[resource]\n'
             'cooldown = 60\ndamage = 10\naccuracy = 1.0\nrecoil_duration = 0.0\n'
             'scaling_stats = [ [ "stat_elemental_damage", 1.0 ] ]\n')
    data = '[gd_resource type="Resource" format=2]\n[resource]\neffects = [  ]\n'
    rec = build_weapon_record(stats, data, weapon_id="w", name="W", tier=1)
    assert rec["dps_slope_per_rd"] == 0.0


def test_weapon_record_populates_effects_and_classes():
    effect = ('[gd_resource type="Resource" format=2]\n'
              '[ext_resource path="res://effects/weapons/exploding_effect.gd" type="Script" id=1]\n'
              '[resource]\nscript = ExtResource( 1 )\n'
              'key = "effect_explode_custom"\nchance = 0.5\nvalue = 0\n')
    rec = build_weapon_record(STATS, DATA, [effect], weapon_id="w", name="W",
                              tier=1, classes=["Gun", "Explosive"])
    assert rec["sets"] == ["Gun", "Explosive"]
    assert len(rec["effects"]) == 1
    e = rec["effects"][0]
    assert e["key"] == "effect_explode_custom" and e["chance"] == 0.5
    assert "__ext__" not in str(e)  # nested resource refs (script) dropped


def test_resolve_weapon_refs_follows_effect_and_set_ext_resources(tmp_path):
    from brotato_coach.builders import discover
    wdir = tmp_path / "weapons" / "ranged" / "shredder" / "1"
    wdir.mkdir(parents=True)
    (wdir / "shredder_effect.tres").write_text(
        '[gd_resource type="Resource" format=2]\n[resource]\n'
        'key = "effect_explode_custom"\nchance = 0.5\n', encoding="utf-8")
    data = wdir / "shredder_data.tres"
    data.write_text(
        '[gd_resource type="Resource" format=2]\n'
        '[ext_resource path="res://weapons/ranged/shredder/1/shredder_effect.tres" type="Resource" id=6]\n'
        '[ext_resource path="res://items/sets/gun/gun_set_data.tres" type="Resource" id=7]\n'
        '[ext_resource path="res://items/sets/explosive/explosive_set_data.tres" type="Resource" id=8]\n'
        '[resource]\neffects = [ ExtResource( 6 ) ]\n'
        'sets = [ ExtResource( 7 ), ExtResource( 8 ) ]\n', encoding="utf-8")
    effect_paths, classes = discover._resolve_weapon_refs(str(tmp_path), str(data))
    assert classes == ["Gun", "Explosive"]
    assert len(effect_paths) == 1 and effect_paths[0].endswith("shredder_effect.tres")


EXPLODE_EFFECT = ('[gd_resource type="Resource" format=2]\n[resource]\n'
                  'key = "effect_explode_custom"\nchance = 0.5\nvalue = 0\n')

PROC_MODEL = {"effect_explode_custom": {
    "damage_source": "weapon_damage",
    "damage_multiplier": 1.0,
    "default_enemies_hit": 1.0,
}}


def test_weapon_record_proc_line_from_model():
    rec = build_weapon_record(STATS, DATA, [EXPLODE_EFFECT], weapon_id="w",
                              name="W", tier=4, proc_models=PROC_MODEL)
    # base line (23.8095, 0.47619) x chance 0.5
    assert math.isclose(rec["proc_dps_at_zero_rd"], 11.90475, rel_tol=1e-4)
    assert math.isclose(rec["proc_dps_slope_per_rd"], 0.238095, rel_tol=1e-4)
    assert rec["unmodeled_effects"] == []


def test_weapon_record_unmodeled_effect_contributes_zero_and_is_listed():
    # effect_burning has no PROC_MODELS entry (unverified against recovered/
    # code) — unlike the exploding-effect keys, which are now modeled.
    burning_effect = EXPLODE_EFFECT.replace("effect_explode_custom", "effect_burning")
    rec = build_weapon_record(STATS, DATA, [burning_effect], weapon_id="w",
                              name="W", tier=4)
    assert rec["proc_dps_at_zero_rd"] == 0.0
    assert rec["proc_dps_slope_per_rd"] == 0.0
    assert rec["unmodeled_effects"] == ["effect_burning"]


def test_default_proc_models_cover_explode_keys():
    for key in ("effect_explode_custom", "effect_explode", "effect_explode_melee"):
        effect = EXPLODE_EFFECT.replace("effect_explode_custom", key)
        rec = build_weapon_record(STATS, DATA, [effect], weapon_id="w",
                                  name="W", tier=4)  # no injected models: real table
        assert rec["proc_dps_at_zero_rd"] > 0, key
        assert rec["unmodeled_effects"] == [], key


def test_weapon_record_no_effects_has_zero_proc_fields():
    rec = build_weapon_record(STATS, DATA, weapon_id="w", name="W", tier=4)
    assert rec["proc_dps_at_zero_rd"] == 0.0
    assert rec["unmodeled_effects"] == []


DATA_LOC = """[gd_resource type="Resource" format=2]
[resource]
weapon_id = "weapon_shredder"
name = "WEAPON_SHREDDER"
description = "WEAPON_SHREDDER_DESC"
effects = [  ]
"""
TR = {"WEAPON_SHREDDER": "Shredder (EN)",
      "WEAPON_SHREDDER_DESC": "Chance to explode."}


def test_weapon_record_resolves_display_name_and_description():
    rec = build_weapon_record(STATS, DATA_LOC, weapon_id="weapon_shredder",
                              name="Shredder", tier=4, tr=TR)
    assert rec["display_name"] == "Shredder (EN)"
    assert rec["description"] == "Chance to explode."


def test_weapon_record_falls_back_to_slug_name_without_translations():
    rec = build_weapon_record(STATS, DATA_LOC, weapon_id="weapon_shredder",
                              name="Shredder", tier=4)
    assert rec["display_name"] == "Shredder"
    assert rec["description"] == ""


BURNING_EFFECT = ('[gd_resource type="Resource" format=2]\n'
                  '[ext_resource path="res://effects/weapons/burning_effect.gd" type="Script" id=1]\n'
                  '[resource]\nscript = ExtResource( 1 )\n'
                  'key = "effect_burning"\nvalue = 0\n')

BURNING_DATA = ('[gd_resource type="Resource" format=2]\n[resource]\n'
                'chance = 1.0\ndamage = 3\nduration = 3\nspread = 0\n'
                'scaling_stats = [ [ "stat_elemental_damage", 1.0 ] ]\n'
                'is_global_burn = false\n')


def test_weapon_record_merges_burning_data_companion():
    rec = build_weapon_record(STATS, DATA, [BURNING_EFFECT], [BURNING_DATA],
                              weapon_id="w", name="W", tier=1)
    e = rec["effects"][0]
    assert e["key"] == "effect_burning"
    assert e["burning_data"] == {
        "chance": 1.0, "damage": 3, "duration": 3, "spread": 0,
        "scaling_stats": [["stat_elemental_damage", 1.0]],
        "is_global_burn": False,
    }


def test_weapon_record_effect_without_companion_has_no_burning_data_key():
    rec = build_weapon_record(STATS, DATA, [BURNING_EFFECT],
                              weapon_id="w", name="W", tier=1)
    assert "burning_data" not in rec["effects"][0]


def _burning_data(chance=1.0, damage=3, duration=3):
    return ('[gd_resource type="Resource" format=2]\n[resource]\n'
            f'chance = {chance}\ndamage = {damage}\nduration = {duration}\n'
            'spread = 0\nscaling_stats = [ [ "stat_elemental_damage", 1.0 ] ]\n'
            'is_global_burn = false\n')


def test_weapon_record_burn_dot_contributes_when_preconditions_hold():
    # Torch T1: cooldown 31 frames, recoil 0.1 -> cycle_time ~0.717s;
    # duration 3 ticks * 0.5s tick_interval = 1.5s window comfortably
    # sustains continuous uptime.
    stats = ('[gd_resource type="Resource" format=2]\n[resource]\n'
             'cooldown = 31\ndamage = 5\naccuracy = 1.0\nrecoil_duration = 0.1\n'
             'scaling_stats = [ [ "stat_melee_damage", 1.0 ] ]\n')
    rec = build_weapon_record(stats, DATA, [BURNING_EFFECT], [_burning_data()],
                              weapon_id="w", name="W", tier=1)
    assert math.isclose(rec["proc_dps_at_zero_rd"], 6.0)  # 3 damage / 0.5s
    assert rec["proc_dps_slope_per_rd"] == 0.0
    assert rec["unmodeled_effects"] == []


def test_weapon_record_burn_dot_falls_back_when_cycle_time_exceeds_window():
    # Hypothetical slow weapon: cooldown 600 frames (10s) vs. a 1.5s window.
    stats = ('[gd_resource type="Resource" format=2]\n[resource]\n'
             'cooldown = 600\ndamage = 5\naccuracy = 1.0\nrecoil_duration = 0.1\n'
             'scaling_stats = [ [ "stat_melee_damage", 1.0 ] ]\n')
    rec = build_weapon_record(stats, DATA, [BURNING_EFFECT], [_burning_data()],
                              weapon_id="w", name="W", tier=1)
    assert rec["proc_dps_at_zero_rd"] == 0.0
    assert rec["unmodeled_effects"] == ["effect_burning"]


def test_weapon_record_burn_dot_falls_back_when_chance_below_one():
    rec = build_weapon_record(STATS, DATA, [BURNING_EFFECT],
                              [_burning_data(chance=0.5)],
                              weapon_id="w", name="W", tier=1)
    assert rec["proc_dps_at_zero_rd"] == 0.0
    assert rec["unmodeled_effects"] == ["effect_burning"]


def test_weapon_record_burn_dot_falls_back_without_burning_data():
    rec = build_weapon_record(STATS, DATA, [BURNING_EFFECT],
                              weapon_id="w", name="W", tier=1)
    assert rec["proc_dps_at_zero_rd"] == 0.0
    assert rec["unmodeled_effects"] == ["effect_burning"]
