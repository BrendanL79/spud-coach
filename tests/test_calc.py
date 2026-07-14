import math

import pytest

from brotato_coach import calc


def test_cycle_time_no_burst():
    # Shredder T4: recoil_duration 0.15, cooldown 45
    assert math.isclose(calc.cycle_time(0.15, 45), 1.05)


def test_cycle_time_with_burst():
    # Revolver T4: recoil 0.1, cd 11, every 6 shots add cd*8/60
    assert math.isclose(calc.cycle_time(0.1, 11, burst=(6, 8.0)), 0.627777, rel_tol=1e-4)


def test_dps_line_shredder_t4():
    dps0, slope = calc.dps_line(25, 0.5, calc.cycle_time(0.15, 45), 1.0)
    assert math.isclose(dps0, 23.8095, rel_tol=1e-4)
    assert math.isclose(slope, 0.47619, rel_tol=1e-4)


def test_dps_line_minigun_t4():
    dps0, slope = calc.dps_line(5, 0.75, calc.cycle_time(0.02, 3), 1.0)
    assert math.isclose(dps0, 55.5556, rel_tol=1e-4)
    assert math.isclose(slope, 8.3333, rel_tol=1e-4)


def test_dps_line_revolver_t4_accuracy_and_burst():
    ct = calc.cycle_time(0.1, 11, burst=(6, 8.0))
    dps0, slope = calc.dps_line(40, 2.0, ct, 0.9)
    assert math.isclose(dps0, 57.35, rel_tol=1e-3)
    assert math.isclose(slope, 2.8673, rel_tol=1e-3)


def test_minigun_beats_revolver_slope():
    _, mini = calc.dps_line(5, 0.75, calc.cycle_time(0.02, 3), 1.0)
    _, revo = calc.dps_line(40, 2.0, calc.cycle_time(0.1, 11, burst=(6, 8.0)), 0.9)
    assert mini > revo


def test_compare_lines_crossover():
    # a starts higher but flat; b starts lower but steep -> they cross
    result = calc.compare_lines((60.0, 1.0), (50.0, 3.0), 0, 100)
    assert result["rd_independent"] is False
    assert math.isclose(result["crossover_rd"], 5.0, rel_tol=1e-6)


def test_compare_lines_dominant():
    # a dominates everywhere in range -> no crossover
    result = calc.compare_lines((60.0, 4.0), (50.0, 3.0), 0, 100)
    assert result["rd_independent"] is True
    assert result["crossover_rd"] is None
    assert result["winner"] == "a"


def test_proc_line_shredder_explode():
    # Shredder T4 base line (23.8095, 0.47619); 50% chance to re-deal weapon damage
    p0, ps = calc.proc_line(23.8095, 0.47619, chance=0.5, enemies_hit=1.0)
    assert math.isclose(p0, 11.90475, rel_tol=1e-4)
    assert math.isclose(ps, 0.238095, rel_tol=1e-4)


def test_proc_line_scales_with_enemies_hit_and_multiplier():
    p0, ps = calc.proc_line(20.0, 0.4, chance=0.5, enemies_hit=3.0, multiplier=0.5)
    assert math.isclose(p0, 15.0)
    assert math.isclose(ps, 0.3)


def test_burn_dps_line_typical():
    dps0, slope = calc.burn_dps_line(3.0, 0.5)
    assert math.isclose(dps0, 6.0)
    assert slope == 0.0


def test_burn_dps_line_default_tick_interval():
    dps0, slope = calc.burn_dps_line(5.0)
    assert math.isclose(dps0, 10.0)
    assert slope == 0.0


def test_burn_dps_line_zero_damage():
    dps0, slope = calc.burn_dps_line(0.0)
    assert dps0 == 0.0
    assert slope == 0.0


def test_companion_dps_line_lightning_shiv_t1_golden():
    # companion damage 5, elemental scaling (rd_coef 0), host cycle 0.65s,
    # 1 spawn, chain of 1 (bounce 0)
    dps0, slope = calc.companion_dps_line(5.0, 0.0, 0.65, 1.0, 1.0)
    assert math.isclose(dps0, 7.6923, rel_tol=1e-4)
    assert slope == 0.0


def test_companion_dps_line_cactus_mace_t1_golden():
    # companion damage 1, stat_ranged_damage 0.6, host cycle 1.25s,
    # 3 spawns per hit, spray assumption 1.0
    dps0, slope = calc.companion_dps_line(1.0, 0.6, 1.25, 3.0, 1.0)
    assert math.isclose(dps0, 2.4)
    assert math.isclose(slope, 1.44)


def test_companion_dps_line_zero_count_is_zero():
    dps0, slope = calc.companion_dps_line(10.0, 1.0, 1.0, 0.0, 1.0)
    assert dps0 == 0.0
    assert slope == 0.0


def test_cooldown_jitter_slow_weapon_single():
    # Shredder-like basis 45 frames, N=1: delta=min(45/5, 5)=5 -> [40, 50]
    lo, hi = calc.cooldown_jitter(45, 1)
    assert math.isclose(lo, 40.0)
    assert math.isclose(hi, 50.0)


def test_cooldown_jitter_slow_weapon_six_weapons():
    # basis 45, N=6: delta=min(6*45/5=54, 6*5=30)=30 -> [15, 75]
    lo, hi = calc.cooldown_jitter(45, 6)
    assert math.isclose(lo, 15.0)
    assert math.isclose(hi, 75.0)


def test_cooldown_jitter_fast_weapon_floors_at_one():
    # Minigun-like basis 3, N=6: delta=min(3.6, 30)=3.6; basis-delta=-0.6 -> floored to 1
    lo, hi = calc.cooldown_jitter(3, 6)
    assert math.isclose(lo, 1.0)
    assert math.isclose(hi, 6.6)


def test_cooldown_jitter_clamps_weapon_count_to_six():
    assert calc.cooldown_jitter(45, 99) == calc.cooldown_jitter(45, 6)


def test_cooldown_jitter_degenerate_basis_never_inverts():
    # No base-game weapon has a sub-1-frame cooldown, but a basis < 1 must not
    # yield an inverted (lo > hi) range once the low bound floors at 1.
    lo, hi = calc.cooldown_jitter(0, 6)
    assert lo <= hi
    assert lo == 1.0


def test_cadence_profile_minigun_sustained():
    # Minigun T4: cycle 0.09s, total_dps 55.5556 at rd0, basis 3 frames
    p = calc.cadence_profile(0.09, 55.5556, 3, weapon_count=1)
    assert math.isclose(p["attacks_per_second"], 1 / 0.09, rel_tol=1e-9)
    assert math.isclose(p["seconds_between_attacks"], 0.09)
    assert math.isclose(p["damage_per_attack"], 5.0, rel_tol=1e-4)  # base_damage 5
    assert p["cadence"] == "sustained"
    assert p["burst_reload"] is False
    # recoil_term = 0.09 - 3/60 = 0.04; N=1 jitter (2.4, 3.6)
    assert math.isclose(p["gap_range_s"][0], 0.04 + 2.4 / 60.0, rel_tol=1e-6)
    assert math.isclose(p["gap_range_s"][1], 0.04 + 3.6 / 60.0, rel_tol=1e-6)


def test_cadence_profile_shredder_bursty_and_invariant():
    # Shredder T4: cycle 1.05s, total_dps 23.8095 at rd0, basis 45 frames
    p = calc.cadence_profile(1.05, 23.8095, 45, weapon_count=1)
    assert p["cadence"] == "bursty"  # ~0.952 atk/s < 1
    assert math.isclose(p["damage_per_attack"], 25.0, rel_tol=1e-4)  # base_damage 25
    # Invariant: damage_per_attack * attacks_per_second == total_dps
    assert math.isclose(
        p["damage_per_attack"] * p["attacks_per_second"], 23.8095, rel_tol=1e-9)


def test_cadence_profile_moderate_label_boundary():
    # cycle 0.5s -> exactly 2 atk/s -> moderate
    assert calc.cadence_profile(0.5, 10.0, 30)["cadence"] == "moderate"
    # cycle exactly 1/3s -> 3 atk/s -> sustained (>= 3)
    assert calc.cadence_profile(1 / 3, 10.0, 20)["cadence"] == "sustained"


def test_cadence_profile_gap_range_widens_with_weapon_count():
    narrow = calc.cadence_profile(1.05, 23.8095, 45, weapon_count=1)["gap_range_s"]
    wide = calc.cadence_profile(1.05, 23.8095, 45, weapon_count=6)["gap_range_s"]
    assert wide[0] < narrow[0]
    assert wide[1] > narrow[1]


def test_cadence_profile_passes_burst_reload_flag():
    assert calc.cadence_profile(0.63, 90.0, 11, burst_reload=True)["burst_reload"] is True


def test_game_round_half_away_from_zero():
    # GDScript round(32.5) == 33, unlike Python's banker's rounding
    assert calc.game_round(32.5) == 33
    assert calc.game_round(62.5) == 63
    assert calc.game_round(-0.5) == -1
    assert calc.game_round(2.4) == 2


def test_game_int_truncates_toward_zero():
    assert calc.game_int(25.8) == 25
    assert calc.game_int(-3.7) == -3


def test_effective_cooldown_positive_as_divides():
    # weapon_service.gd:570-573 — max(MIN_COOLDOWN, cd / (1+as)) as int
    assert calc.effective_cooldown(60, 0.5) == 40
    assert calc.effective_cooldown(25, 0.12) == 22  # 22.32 truncates


def test_effective_cooldown_negative_as_multiplies():
    assert calc.effective_cooldown(60, -0.5) == 90


def test_effective_cooldown_two_frame_floor():
    assert calc.effective_cooldown(3, 2.0) == 2


def test_effective_cooldown_zero_as_passthrough():
    assert calc.effective_cooldown(60, 0.0) == 60


def test_ranged_cycle_pistol_t1_as0():
    # Pistol T1: recoil 0.1, cooldown 60 -> 2*0.1 + 60/60 = 1.2 (matches v5 dataset)
    assert calc.stat_aware_cycle_time(
        weapon_type="ranged", recoil_duration=0.1, cooldown=60,
        attack_speed_frac=0.0) == pytest.approx(1.2)


def test_ranged_cycle_as_shrinks_recoil_and_cooldown():
    # AS +50%: recoil 0.1/1.5, cooldown max(2, 60/1.5)=40 -> 0.1333.. + 0.6667.. = 0.8
    assert calc.stat_aware_cycle_time(
        weapon_type="ranged", recoil_duration=0.1, cooldown=60,
        attack_speed_frac=0.5) == pytest.approx(0.8)


def test_ranged_cycle_burst_reload_replaces_draw():
    # weapon.gd:337-339: every 6th draw is cd*mult INSTEAD of cd.
    # recoil 0.1, cd 12, every 6, mult 5: 0.2 + 12*((6-1)+5)/6/60 = 0.2 + 20/60
    assert calc.stat_aware_cycle_time(
        weapon_type="ranged", recoil_duration=0.1, cooldown=12,
        attack_speed_frac=0.0, burst=(6, 5.0)) == pytest.approx(0.5333333333)


def test_melee_cycle_knife_t1_as0():
    # Knife T1: recoil 0.1, cd 25, max_range 150; default engagement min(150,70)=70
    # rf=70/70=1 -> atk=0.2+0.15=0.35; back=0.2; shooting=0.175+0.2+0.1=0.475
    # cycle = 0.475 + 25/60 = 0.891666..
    assert calc.stat_aware_cycle_time(
        weapon_type="melee", recoil_duration=0.1, cooldown=25,
        attack_speed_frac=0.0, max_range=150) == pytest.approx(0.8916666667)


def test_melee_cycle_as100_triple_effect():
    # AS +100%: rf=70/clamp(70*(1+1/3),70,120)=0.75 -> atk=max(.01,.1)+0.1125=0.2125
    # back=0.2/4=0.05; recoil'=0.05; shooting=0.10625+0.05+0.05=0.20625
    # eff_cd=int(25/2)=12 -> cycle=0.20625+0.2=0.40625
    assert calc.stat_aware_cycle_time(
        weapon_type="melee", recoil_duration=0.1, cooldown=25,
        attack_speed_frac=1.0, max_range=150) == pytest.approx(0.40625)


def test_melee_cycle_point_blank_override():
    # engagement_distance=0 -> rf=0 -> atk=0.2; shooting=0.1+0.2+0.1=0.4
    assert calc.stat_aware_cycle_time(
        weapon_type="melee", recoil_duration=0.1, cooldown=25,
        attack_speed_frac=0.0, max_range=150,
        engagement_distance=0.0) == pytest.approx(0.8166666667)


def test_stat_value_mapping():
    stats = {"melee_damage": 20, "damage": 30}
    assert calc.stat_value(stats, "stat_melee_damage") == 20
    assert calc.stat_value(stats, "stat_percent_damage") == 30  # irregular short name
    assert calc.stat_value(stats, "stat_levels", level=7) == 7
    assert calc.stat_value(stats, "stat_ranged_damage") == 0.0


def test_per_hit_damage_knife_t1_flat_scaling():
    # weapon_service.gd:489: max(1, 9 + 20*0.8) as int = 25
    assert calc.per_hit_damage(9, [["stat_melee_damage", 0.8]],
                               {"melee_damage": 20}) == 25


def test_per_hit_damage_truncates_scaling_sum():
    # 9 + 21*0.8 = 25.8 -> truncates to 25 (same as md=20 — real steppiness)
    assert calc.per_hit_damage(9, [["stat_melee_damage", 0.8]],
                               {"melee_damage": 21}) == 25


def test_per_hit_damage_percent_bracket_rounds_half_up():
    # d1=25; 25 * 1.30 = 32.5 -> GDScript round -> 33 (weapon_service.gd:249)
    assert calc.per_hit_damage(9, [["stat_melee_damage", 0.8]],
                               {"melee_damage": 20, "damage": 30}) == 33


def test_per_hit_damage_floors_at_one():
    # d1=9; 9 * 0.2 = 1.8 -> round 2; and at -100%: max(1, 0) -> 1
    assert calc.per_hit_damage(9, [["stat_melee_damage", 0.8]], {"damage": -80}) == 2
    assert calc.per_hit_damage(9, [["stat_melee_damage", 0.8]], {"damage": -100}) == 1


def test_expected_hit_damage_crit_expectation():
    # cc = 0.2 + 10/100 = 0.3; crit dmg round(32*2.5)=80
    # (1-0.3)*32 + 0.3*80 = 22.4 + 24 = 46.4
    assert calc.expected_hit_damage(32, 0.2, 2.5, player_crit_chance=10) == pytest.approx(46.4)


def test_expected_hit_damage_crit_clamped_to_certainty():
    # weapon 0.2 + player 200% -> clamp 1.0 -> always round(32*2.5)=80
    assert calc.expected_hit_damage(32, 0.2, 2.5, player_crit_chance=200) == pytest.approx(80.0)
