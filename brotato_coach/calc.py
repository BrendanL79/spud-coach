"""Pure DPS / merge math. No I/O — every function is unit-testable in isolation.

DPS model: cycle_time = recoil_duration*2 + cooldown/60 (seconds).
Realized DPS as a function of ranged-damage (RD) is a line:
    dps(rd) = dps_at_zero_rd + dps_slope_per_rd * rd
with both intercept and slope scaled by accuracy.
"""

from __future__ import annotations


def cycle_time(recoil_duration: float, cooldown: float,
               burst: tuple[int, float] | None = None) -> float:
    ct = recoil_duration * 2 + cooldown / 60
    if burst is not None:
        every_x_shots, multiplier = burst
        ct += (cooldown * multiplier / 60) / every_x_shots
    return ct


def cooldown_jitter(cooldown_basis_frames: float, weapon_count: int) -> tuple[float, float]:
    """Per-shot cooldown range (frames) from the engine's anti-sync randomization.

    Each shot draws cooldown uniformly from [max(1, basis - Δ), basis + Δ],
    Δ = min(N·basis/5, N·5), N = min(max(weapon_count, 1), 6) (weapon.gd:337-354).
    The spread grows with weapon count, de-synchronizing volleys. The mean equals
    basis EXCEPT when the low bound floors at 1 (basis - Δ < 1 — fast weapons at
    high weapon counts): there the mean skews above basis, so those weapons fire
    slightly slower than basis implies and nominal DPS modestly overstates them.
    The coach's cycle_time uses raw basis and does not model this skew (see
    docs/roadmap.md).
    """
    n = min(max(weapon_count, 1), 6)
    delta = min(n * cooldown_basis_frames / 5.0, n * 5.0)
    lo = max(1.0, cooldown_basis_frames - delta)
    # Clamp hi >= lo so the degenerate basis < 1 case (no base-game weapon has
    # a sub-1-frame cooldown) can't return an inverted range.
    return (lo, max(lo, cooldown_basis_frames + delta))


def cadence_profile(cycle_time: float, total_dps: float,
                    cooldown_basis_frames: float, weapon_count: int = 1,
                    *, burst_reload: bool = False) -> dict:
    """Per-weapon cadence descriptors decomposing DPS into rate x burst, plus
    the verified dead-window gap range. See docs/cadence-mechanics.md.

    Invariant: damage_per_attack * attacks_per_second == total_dps.
    The gap range derives from cooldown_jitter; the recoil portion of the
    cycle is common to both bounds and cancels, so no separate recoil value
    is needed. Caller must ensure cycle_time > 0.
    """
    aps = 1.0 / cycle_time
    lo_f, hi_f = cooldown_jitter(cooldown_basis_frames, weapon_count)
    # gap_range_s builds on cycle_time, which for burst-reload weapons already
    # amortizes the long reload — so their range is average-based, not the felt
    # fast-then-reload rhythm (flagged via burst_reload; see docs/cadence-mechanics.md).
    recoil_term = cycle_time - cooldown_basis_frames / 60.0
    if aps >= 3.0:
        label = "sustained"
    elif aps >= 1.0:
        label = "moderate"
    else:
        label = "bursty"
    return {
        "attacks_per_second": aps,
        "seconds_between_attacks": cycle_time,
        "damage_per_attack": total_dps * cycle_time,
        "cadence": label,
        "gap_range_s": [recoil_term + lo_f / 60.0, recoil_term + hi_f / 60.0],
        "burst_reload": burst_reload,
    }


def dps_line(base_damage: float, scaling_coef: float, cycle_time: float,
             accuracy: float) -> tuple[float, float]:
    dps0 = base_damage / cycle_time * accuracy
    slope = scaling_coef / cycle_time * accuracy
    return (dps0, slope)


def dps_at(dps0: float, slope: float, rd: float) -> float:
    return dps0 + slope * rd


def sum_lines(lines: list[tuple[float, float]]) -> tuple[float, float]:
    return (sum(d for d, _ in lines), sum(s for _, s in lines))


def proc_line(dps0: float, slope: float, chance: float, enemies_hit: float,
              multiplier: float = 1.0) -> tuple[float, float]:
    """Expected DPS line added by a weapon-damage proc (e.g. exploding shot).

    The proc re-deals the weapon's own damage line with probability `chance`
    per hit, against `enemies_hit` enemies, scaled by `multiplier`. Expected
    value is linear in RD, so the contribution is itself a (dps0, slope) line.
    """
    f = chance * enemies_hit * multiplier
    return (dps0 * f, slope * f)


def burn_dps_line(damage_per_tick: float, tick_interval: float = 0.5) -> tuple[float, float]:
    """Expected DPS line from a sustained burn (damage-over-time) proc.

    Assumes steady-state: once ignited, the burn is kept continuously
    refreshed by the weapon's own attacks (verified true for every shipped
    burn weapon — see docs/proc-mechanics.md). Burn damage scales off
    stat_elemental_damage, not RD, so slope is always 0 in this dataset's
    RD-parameterized model.
    """
    return (damage_per_tick / tick_interval, 0.0)


def companion_dps_line(damage: float, rd_coef: float, host_cycle_time: float,
                       count: float, enemies_hit: float) -> tuple[float, float]:
    """Expected DPS line from a spawn-projectiles-on-hit proc.

    Each landed host hit unconditionally spawns `count` projectiles whose
    damage line lives on a companion RangedWeaponStats resource, independent
    of the host weapon's own damage (see docs/proc-mechanics.md,
    "Companion-projectile procs"). `enemies_hit` is the assumed expected hits
    per volley/chain — an assumption constant, like proc_line's enemies_hit.
    """
    f = count * enemies_hit / host_cycle_time
    return (damage * f, rd_coef * f)


def compare_lines(line_a: tuple[float, float], line_b: tuple[float, float],
                  rd_min: float = 0.0, rd_max: float = 100.0) -> dict:
    a0, as_ = line_a
    b0, bs = line_b

    crossover_rd = None
    if as_ != bs:
        x = (b0 - a0) / (as_ - bs)
        if rd_min < x < rd_max:
            crossover_rd = x

    def winner_at(rd: float) -> str:
        va, vb = dps_at(a0, as_, rd), dps_at(b0, bs, rd)
        if abs(va - vb) < 1e-9:
            return "tie"
        return "a" if va > vb else "b"

    if crossover_rd is None:
        return {
            "winner": winner_at((rd_min + rd_max) / 2),
            "rd_independent": True,
            "crossover_rd": None,
        }
    return {
        "winner": None,
        "rd_independent": False,
        "crossover_rd": crossover_rd,
    }
