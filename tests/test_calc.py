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
