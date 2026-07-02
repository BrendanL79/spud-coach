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
