import math

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
