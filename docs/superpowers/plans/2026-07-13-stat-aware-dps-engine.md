# Stat-Aware DPS Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the RD-only DPS line with a single query-time, game-exact evaluator over the full player stat block (spec: `docs/superpowers/specs/2026-07-13-stat-aware-dps-engine-design.md`).

**Architecture:** The dataset (schema v6) ships only raw per-weapon facts; `calc.py` gains a pure game-exact pipeline (scaling sum → percent bracket → expected crit → attack-speed-adjusted cycle time) evaluated at query time; `answers.py`/`server.py` consume full stat blocks and gain a `stat_gradient` tool. The old `(dps0, slope)` line fields and functions are deleted.

**Tech Stack:** Python 3.11+, uv, pytest, ruff, pydantic (existing `Stats`), FastMCP.

## Global Constraints

- Work on branch `feature/stat-aware-dps-engine`; large multi-commit feature → **merge commit** at the end (project convention).
- TDD: failing test first, then minimal implementation, for every task. `uv run pytest` and `uv run ruff check .` must be green at every commit.
- NEVER commit or redistribute `data/brotato.json`, `extracted/`, `recovered/`, `game_files/` (all gitignored).
- Worktree caveat: `extracted/`, `recovered/`, and `data/` are gitignored and ABSENT in a worktree. Tasks 7 and 14 (dataset rebuild, shipped-dataset tests) must either run in the main checkout (`C:\Users\brend\src\brotato-exam`) or pass `--extracted`/`--recovered` pointing at it and copy the rebuilt `data/brotato.json` into the worktree's `data/`.
- Evidence citations in code/docs must be re-verified against `recovered/` at write time (project rule). Citations in this plan were pinned 2026-07-13; re-check the quoted lines still match before writing them into docs.
- GDScript arithmetic notes used throughout: `round()` = half away from zero (NOT Python's banker's rounding); `as int` = truncate toward zero. Weapon `cooldown` is in frames @60fps.
- The in-game constant `MIN_COOLDOWN = 2` frames (`recovered/singletons/weapon_service.gd:5`).
- Player `attack_speed`, `crit_chance`, `%damage` stats are percentages (stat 25 → 0.25 as a fraction).
- Crit chance cap: defaults to `Utils.LARGE_NUMBER` (uncapped, `recovered/singletons/player_run_data.gd:436`); the engine only clamps total crit chance into [0, 1].
- `nb_projectiles` is intentionally NOT multiplied into DPS (matches the old model; spread/pierce hit-rates are unmodeled — documented in Task 13).

---

### Task 1: Game-exact rounding helpers + `effective_cooldown` in calc.py

**Files:**
- Modify: `brotato_coach/calc.py` (append; do not touch existing functions yet)
- Test: `tests/test_calc.py` (append)

**Interfaces:**
- Produces: `game_round(x: float) -> int`, `game_int(x: float) -> int`, `effective_cooldown(cooldown: float, attack_speed_frac: float) -> int` — used by Tasks 2–4.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_calc.py`)

```python
from brotato_coach.calc import game_round, game_int, effective_cooldown


def test_game_round_half_away_from_zero():
    # GDScript round(32.5) == 33, unlike Python's banker's rounding
    assert game_round(32.5) == 33
    assert game_round(62.5) == 63
    assert game_round(-0.5) == -1
    assert game_round(2.4) == 2


def test_game_int_truncates_toward_zero():
    assert game_int(25.8) == 25
    assert game_int(-3.7) == -3


def test_effective_cooldown_positive_as_divides():
    # weapon_service.gd:570-573 — max(MIN_COOLDOWN, cd / (1+as)) as int
    assert effective_cooldown(60, 0.5) == 40
    assert effective_cooldown(25, 0.12) == 22  # 22.32 truncates


def test_effective_cooldown_negative_as_multiplies():
    assert effective_cooldown(60, -0.5) == 90


def test_effective_cooldown_two_frame_floor():
    assert effective_cooldown(3, 2.0) == 2


def test_effective_cooldown_zero_as_passthrough():
    assert effective_cooldown(60, 0.0) == 60
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_calc.py -k "game_round or game_int or effective_cooldown" -v`
Expected: FAIL — `ImportError: cannot import name 'game_round'`

- [ ] **Step 3: Implement** (append to `brotato_coach/calc.py`; add `import math` at top)

```python
# --- Stat-aware game-exact engine -------------------------------------------
# Evidence: recovered/singletons/weapon_service.gd (init pipeline),
# recovered/weapons/shooting_behaviors/*.gd (timing), recovered/entities/
# units/unit/unit.gd:285-301 (crit roll). See docs/dps-engine.md.

GD_MIN_COOLDOWN = 2.0  # frames; weapon_service.gd:5


def game_round(x: float) -> int:
    """GDScript round(): half away from zero (round(32.5) == 33)."""
    return int(math.floor(x + 0.5)) if x >= 0 else int(math.ceil(x - 0.5))


def game_int(x: float) -> int:
    """GDScript `as int`: truncation toward zero."""
    return int(math.trunc(x))


def effective_cooldown(cooldown: float, attack_speed_frac: float) -> int:
    """Attack-speed-adjusted cooldown in frames, exactly as the game computes it.

    weapon_service.gd:227-229 floors the base cooldown at MIN_COOLDOWN first,
    then :570-573 divides by (1+AS) for positive AS or multiplies by (1+|AS|)
    for negative AS, floors at MIN_COOLDOWN again, and truncates to int.
    `attack_speed_frac` is (stat_attack_speed + attack_speed_mod)/100.
    """
    cd = max(cooldown, GD_MIN_COOLDOWN)
    if attack_speed_frac > 0:
        return game_int(max(GD_MIN_COOLDOWN, cd / (1 + attack_speed_frac)))
    if attack_speed_frac < 0:
        return game_int(max(GD_MIN_COOLDOWN, cd * (1 + abs(attack_speed_frac))))
    return game_int(cd)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_calc.py -v` — all pass; `uv run ruff check .` green.

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/calc.py tests/test_calc.py
git commit -m "feat(calc): game-exact rounding helpers and attack-speed cooldown"
```

---

### Task 2: `stat_aware_cycle_time` (ranged + melee + burst)

**Files:**
- Modify: `brotato_coach/calc.py`
- Test: `tests/test_calc.py`

**Interfaces:**
- Consumes: `effective_cooldown`, `game_int` (Task 1).
- Produces: `stat_aware_cycle_time(*, weapon_type: str, recoil_duration: float, cooldown: float, attack_speed_frac: float, max_range: float = 0.0, engagement_distance: float | None = None, burst: tuple[int, float] | None = None) -> float` and constant `DEFAULT_ENGAGEMENT_DISTANCE = 70.0`. Used by Task 4 and answers (Task 8).

**Verification step (source re-pin, do BEFORE writing code):** read `recovered/weapons/weapon.gd:332-358` and confirm the burst-reload draw REPLACES the normal cooldown (`get_next_cooldown` returns `cooldown * additional_cooldown_multiplier` when `is_big_reload_active()`), so the amortized average cooldown over `every` shots is `cd_eff * ((every - 1) + multiplier) / every`. This intentionally CORRECTS the old model (which added `cd*mult/every` on top, overstating the reload penalty by `cd/every` — Revolver/Chain Gun DPS rises slightly). Also re-pin `melee_shooting_data.gd` (whole file, 37 lines) and `ranged_shooting_data.gd:10-15`.

- [ ] **Step 1: Write the failing tests**

```python
from brotato_coach.calc import stat_aware_cycle_time


def test_ranged_cycle_pistol_t1_as0():
    # Pistol T1: recoil 0.1, cooldown 60 -> 2*0.1 + 60/60 = 1.2 (matches v5 dataset)
    assert stat_aware_cycle_time(
        weapon_type="ranged", recoil_duration=0.1, cooldown=60,
        attack_speed_frac=0.0) == pytest.approx(1.2)


def test_ranged_cycle_as_shrinks_recoil_and_cooldown():
    # AS +50%: recoil 0.1/1.5, cooldown max(2, 60/1.5)=40 -> 0.1333.. + 0.6667.. = 0.8
    assert stat_aware_cycle_time(
        weapon_type="ranged", recoil_duration=0.1, cooldown=60,
        attack_speed_frac=0.5) == pytest.approx(0.8)


def test_ranged_cycle_burst_reload_replaces_draw():
    # weapon.gd:337-339: every 6th draw is cd*mult INSTEAD of cd.
    # recoil 0.1, cd 12, every 6, mult 5: 0.2 + 12*((6-1)+5)/6/60 = 0.2 + 20/60
    assert stat_aware_cycle_time(
        weapon_type="ranged", recoil_duration=0.1, cooldown=12,
        attack_speed_frac=0.0, burst=(6, 5.0)) == pytest.approx(0.5333333333)


def test_melee_cycle_knife_t1_as0():
    # Knife T1: recoil 0.1, cd 25, max_range 150; default engagement min(150,70)=70
    # rf=70/70=1 -> atk=0.2+0.15=0.35; back=0.2; shooting=0.175+0.2+0.1=0.475
    # cycle = 0.475 + 25/60 = 0.891666..
    assert stat_aware_cycle_time(
        weapon_type="melee", recoil_duration=0.1, cooldown=25,
        attack_speed_frac=0.0, max_range=150) == pytest.approx(0.8916666667)


def test_melee_cycle_as100_triple_effect():
    # AS +100%: rf=70/clamp(70*(1+1/3),70,120)=0.75 -> atk=max(.01,.1)+0.1125=0.2125
    # back=0.2/4=0.05; recoil'=0.05; shooting=0.10625+0.05+0.05=0.20625
    # eff_cd=int(25/2)=12 -> cycle=0.20625+0.2=0.40625
    assert stat_aware_cycle_time(
        weapon_type="melee", recoil_duration=0.1, cooldown=25,
        attack_speed_frac=1.0, max_range=150) == pytest.approx(0.40625)


def test_melee_cycle_point_blank_override():
    # engagement_distance=0 -> rf=0 -> atk=0.2; shooting=0.1+0.2+0.1=0.4
    assert stat_aware_cycle_time(
        weapon_type="melee", recoil_duration=0.1, cooldown=25,
        attack_speed_frac=0.0, max_range=150,
        engagement_distance=0.0) == pytest.approx(0.8166666667)
```

- [ ] **Step 2: Run to verify failure** — ImportError.

- [ ] **Step 3: Implement**

```python
DEFAULT_ENGAGEMENT_DISTANCE = 70.0  # units; melee assumption constant (see spec)
MELEE_BASE_ATK_DURATION = 0.2      # melee_shooting_data.gd:4


def stat_aware_cycle_time(*, weapon_type: str, recoil_duration: float,
                          cooldown: float, attack_speed_frac: float,
                          max_range: float = 0.0,
                          engagement_distance: float | None = None,
                          burst: tuple[int, float] | None = None) -> float:
    """Seconds per attack cycle at a given attack speed, game-exact.

    The engine ticks cooldown only while not mid-swing (weapon.gd:193), so
    cycle = shooting_total_duration + effective_cooldown/60.
    Ranged shooting = 2*recoil_duration' (ranged_shooting_data.gd:10-15).
    Melee shooting = atk_duration/2 + back_duration + recoil_duration'
    (melee_shooting_data.gd:31-32) where atk/back have their own AS terms and
    atk_duration grows with distance-to-target (range_factor). The default
    engagement distance min(max_range, 70) is an assumption constant — enemies
    close in, and a weapon is never credited beyond its own reach.
    Positive AS divides recoil_duration (weapon_service.gd:230-232); negative
    AS does NOT lengthen it. Burst reload (Revolver/Chain Gun): every
    `every`-th cooldown draw is cd*multiplier INSTEAD of cd (weapon.gd:337-339),
    so the amortized cooldown is cd*((every-1)+multiplier)/every.
    """
    asf = attack_speed_frac
    recoil = recoil_duration / (1 + asf) if asf > 0 else recoil_duration
    cd = float(effective_cooldown(cooldown, asf))
    if burst is not None:
        every_x_shots, multiplier = burst
        cd = cd * ((every_x_shots - 1) + multiplier) / every_x_shots

    if weapon_type == "melee":
        dist = min(max_range, DEFAULT_ENGAGEMENT_DISTANCE) \
            if engagement_distance is None else engagement_distance
        # melee_shooting_data.gd:23-28
        range_factor = max(0.0, dist / min(max(70.0 * (1 + asf / 3), 70.0), 120.0))
        atk_duration = max(0.01, MELEE_BASE_ATK_DURATION - asf / 10) + range_factor * 0.15
        back_duration = MELEE_BASE_ATK_DURATION / (1 + 3 * asf) if asf > 0 \
            else MELEE_BASE_ATK_DURATION
        shooting = atk_duration / 2 + back_duration + recoil
    else:
        shooting = 2 * recoil

    return shooting + cd / 60
```

- [ ] **Step 4: Run tests** — pass; ruff green.
- [ ] **Step 5: Commit** — `feat(calc): stat-aware cycle time (ranged, melee, burst reload)`

---

### Task 3: `per_hit_damage` + `expected_hit_damage`

**Files:**
- Modify: `brotato_coach/calc.py`
- Test: `tests/test_calc.py`

**Interfaces:**
- Produces:
  - `stat_value(stats: dict, stat_name: str, level: float = 0.0) -> float` — maps a full `stat_*` scaling name to the short-name stats dict (`stat_percent_damage` → `damage`; `stat_levels` → level).
  - `per_hit_damage(base_damage: float, scaling_stats: list, stats: dict, *, level: float = 0.0, set_bonus_pct: float = 0.0) -> int`
  - `expected_hit_damage(per_hit: int, weapon_crit_chance: float, crit_damage: float, player_crit_chance: float = 0.0) -> float`
- Note: `set_bonus_pct` exists for formula fidelity (weapon_service.gd:249) but v1 always passes 0 — character class bonuses stay advisory (spec decision 7).

- [ ] **Step 1: Write the failing tests**

```python
from brotato_coach.calc import per_hit_damage, expected_hit_damage, stat_value


def test_stat_value_mapping():
    stats = {"melee_damage": 20, "damage": 30}
    assert stat_value(stats, "stat_melee_damage") == 20
    assert stat_value(stats, "stat_percent_damage") == 30  # irregular short name
    assert stat_value(stats, "stat_levels", level=7) == 7
    assert stat_value(stats, "stat_ranged_damage") == 0.0


def test_per_hit_damage_knife_t1_flat_scaling():
    # weapon_service.gd:489: max(1, 9 + 20*0.8) as int = 25
    assert per_hit_damage(9, [["stat_melee_damage", 0.8]],
                          {"melee_damage": 20}) == 25


def test_per_hit_damage_truncates_scaling_sum():
    # 9 + 21*0.8 = 25.8 -> truncates to 25 (same as md=20 — real steppiness)
    assert per_hit_damage(9, [["stat_melee_damage", 0.8]],
                          {"melee_damage": 21}) == 25


def test_per_hit_damage_percent_bracket_rounds_half_up():
    # d1=25; 25 * 1.30 = 32.5 -> GDScript round -> 33 (weapon_service.gd:249)
    assert per_hit_damage(9, [["stat_melee_damage", 0.8]],
                          {"melee_damage": 20, "damage": 30}) == 33


def test_per_hit_damage_floors_at_one():
    # d1=9; 9 * 0.2 = 1.8 -> round 2; and at -100%: max(1, 0) -> 1
    assert per_hit_damage(9, [["stat_melee_damage", 0.8]], {"damage": -80}) == 2
    assert per_hit_damage(9, [["stat_melee_damage", 0.8]], {"damage": -100}) == 1


def test_expected_hit_damage_crit_expectation():
    # cc = 0.2 + 10/100 = 0.3; crit dmg round(32*2.5)=80
    # (1-0.3)*32 + 0.3*80 = 22.4 + 24 = 46.4
    assert expected_hit_damage(32, 0.2, 2.5, player_crit_chance=10) == pytest.approx(46.4)


def test_expected_hit_damage_crit_clamped_to_certainty():
    # weapon 0.2 + player 200% -> clamp 1.0 -> always round(32*2.5)=80
    assert expected_hit_damage(32, 0.2, 2.5, player_crit_chance=200) == pytest.approx(80.0)
```

- [ ] **Step 2: Run to verify failure** — ImportError.

- [ ] **Step 3: Implement**

```python
# Scaling-stat names are the full stat_* identifiers from the .tres; the
# coach's stat blocks use short names (Stats schema). One irregular case:
# the game's stat_percent_damage displays as "% Damage" and the schema calls
# it `damage`.
_SHORT_BY_STAT_NAME = {"stat_percent_damage": "damage"}


def stat_value(stats: dict, stat_name: str, level: float = 0.0) -> float:
    """Player-stat value for a full `stat_*` scaling name (0.0 if absent).

    `stat_levels` scales with player level, not a stat
    (weapon_service.gd:473-474).
    """
    if stat_name == "stat_levels":
        return float(level)
    short = _SHORT_BY_STAT_NAME.get(stat_name, stat_name.removeprefix("stat_"))
    return float(stats.get(short, 0.0))


def per_hit_damage(base_damage: float, scaling_stats: list, stats: dict, *,
                   level: float = 0.0, set_bonus_pct: float = 0.0) -> int:
    """One landed hit's damage before crit, game-exact.

    Step A (weapon_service.gd:489,469): d1 = max(1, base + Σ stat_i*coef_i)
    truncated to int. Step B (:239-249): d2 = max(1, round(d1 * (set_bonus
    + 1 + %damage/100))) — GDScript round, half away from zero.
    `set_bonus_pct` is the weapon-class-bonus percent bucket; the coach passes
    0 (character class bonuses are advisory — see spec decision 7).
    """
    total = sum(stat_value(stats, entry[0], level) * float(entry[1])
                for entry in scaling_stats or [])
    d1 = game_int(max(1.0, base_damage + total))
    bracket = set_bonus_pct / 100 + 1 + stat_value(stats, "stat_percent_damage") / 100
    return game_int(max(1, game_round(d1 * bracket)))


def expected_hit_damage(per_hit: int, weapon_crit_chance: float,
                        crit_damage: float, player_crit_chance: float = 0.0) -> float:
    """Expected damage of one landed hit, folding crit as an expectation.

    Total crit chance = weapon base + player stat/100 (weapon_service.gd:253),
    clamped to [0, 1] (cap defaults to LARGE_NUMBER, player_run_data.gd:436 —
    effectively uncapped, but a chance saturates at certainty). A crit deals
    round(damage * crit_damage) (unit.gd:299-300).
    """
    cc = min(1.0, max(0.0, weapon_crit_chance + player_crit_chance / 100))
    return (1 - cc) * per_hit + cc * game_round(per_hit * crit_damage)
```

- [ ] **Step 4: Run tests** — pass; ruff green.
- [ ] **Step 5: Commit** — `feat(calc): game-exact per-hit damage and crit expectation`

---

### Task 4: `weapon_dps_profile` — the evaluator over a weapon record

**Files:**
- Modify: `brotato_coach/calc.py`
- Test: `tests/test_calc.py`

**Interfaces:**
- Consumes: everything from Tasks 1–3.
- Produces: `weapon_dps_profile(rec: dict, stats: dict, *, level: float = 0.0, aoe_enemies_hit: float = 1.0, engagement_distance: float | None = None) -> dict` returning keys `dps, base_dps, proc_dps, cycle_time, per_hit_damage, expected_hit_damage, crit_chance_total, effective_cooldown_frames, engagement_distance_used`.
- Consumes weapon-record fields produced by Task 6: `weapon_type, base_damage, cooldown, recoil_duration, attack_speed_mod, accuracy, crit_chance, crit_damage, max_range, scaling_stats, additional_cooldown_every_x_shots, additional_cooldown_multiplier, proc_effects`.
- `proc_effects` descriptor shapes (emitted by Task 6):
  - `{"kind": "weapon_damage", "chance": float, "enemies_hit": float, "multiplier": float}` — re-deals the weapon's own expected hit.
  - `{"kind": "burn_dot", "damage": float, "scaling_stats": [...], "tick_interval": 0.5}` — steady-state tick DPS; tick damage runs scaling + %damage (weapon_service.gd:328,332 → apply_damage_bonus :493-495), NO crit.
  - `{"kind": "companion", "damage": float, "scaling_stats": [...], "crit_chance": float, "crit_damage": float, "count": float, "enemies_hit": float}` — spawned projectiles with their own damage pipeline.

**Verification step (before implementing companion handling):** read `recovered/effects/weapons/` projectiles-on-hit effect and where companion `weapon_stats` are initialized; confirm companion stats run through the same `weapon_service` init (scaling + %damage + player crit added to companion base crit). Mirror exactly what the source does; if crit or %damage does NOT apply, drop that term and record the finding for Task 13's docs. The code below assumes the full pipeline applies.

- [ ] **Step 1: Write the failing tests**

```python
from brotato_coach.calc import weapon_dps_profile

KNIFE_T1 = {
    "weapon_type": "melee", "base_damage": 9.0, "cooldown": 25.0,
    "recoil_duration": 0.1, "attack_speed_mod": 0.0, "accuracy": 1.0,
    "crit_chance": 0.2, "crit_damage": 2.5, "max_range": 150.0,
    "scaling_stats": [["stat_melee_damage", 0.8]],
    "additional_cooldown_every_x_shots": -1, "additional_cooldown_multiplier": -1.0,
    "proc_effects": [],
}

PISTOL_T1 = {
    "weapon_type": "ranged", "base_damage": 12.0, "cooldown": 60.0,
    "recoil_duration": 0.1, "attack_speed_mod": 0.0, "accuracy": 0.9,
    "crit_chance": 0.1, "crit_damage": 2.0, "max_range": 400.0,
    "scaling_stats": [["stat_ranged_damage", 1.0]],
    "additional_cooldown_every_x_shots": -1, "additional_cooldown_multiplier": -1.0,
    "proc_effects": [],
}


def test_profile_knife_t1_melee_damage_20():
    # d2=25; expected = 0.8*25 + 0.2*round(62.5)=0.2*63 -> 32.6; ct=0.8916667
    p = weapon_dps_profile(KNIFE_T1, {"melee_damage": 20})
    assert p["per_hit_damage"] == 25
    assert p["expected_hit_damage"] == pytest.approx(32.6)
    assert p["cycle_time"] == pytest.approx(0.8916666667)
    assert p["dps"] == pytest.approx(36.5607476636)
    assert p["engagement_distance_used"] == 70.0


def test_profile_pistol_t1_rd10_accuracy():
    # d2=22; expected = 0.9*22 + 0.1*round(44)=24.2; dps = 24.2/1.2*0.9 = 18.15
    p = weapon_dps_profile(PISTOL_T1, {"ranged_damage": 10})
    assert p["dps"] == pytest.approx(18.15)
    assert p["engagement_distance_used"] is None


def test_profile_melee_dps_responds_to_melee_damage():
    lo = weapon_dps_profile(KNIFE_T1, {})["dps"]
    hi = weapon_dps_profile(KNIFE_T1, {"melee_damage": 50})["dps"]
    assert hi > lo  # the bug this project exists to fix


def test_profile_weapon_damage_proc():
    rec = dict(PISTOL_T1, proc_effects=[
        {"kind": "weapon_damage", "chance": 0.5, "enemies_hit": 1.0, "multiplier": 1.0}])
    p = weapon_dps_profile(rec, {"ranged_damage": 10}, aoe_enemies_hit=2.0)
    assert p["base_dps"] == pytest.approx(18.15)
    # proc = base_dps * chance * (enemies_hit * aoe factor): 18.15 * 0.5 * 2.0
    assert p["proc_dps"] == pytest.approx(18.15)
    assert p["dps"] == pytest.approx(36.30)


def test_profile_burn_scales_with_elemental():
    rec = dict(PISTOL_T1, proc_effects=[
        {"kind": "burn_dot", "damage": 3.0,
         "scaling_stats": [["stat_elemental_damage", 1.0]], "tick_interval": 0.5}])
    zero = weapon_dps_profile(rec, {})
    ele = weapon_dps_profile(rec, {"elemental_damage": 10})
    # tick dmg: max(1, 3+10)=13; %damage none -> 13/0.5 = 26 burn dps
    assert ele["proc_dps"] - zero["proc_dps"] == pytest.approx(26.0 - 6.0)


def test_profile_companion_proc():
    rec = dict(PISTOL_T1, proc_effects=[
        {"kind": "companion", "damage": 5.0,
         "scaling_stats": [["stat_elemental_damage", 1.0]],
         "crit_chance": 0.0, "crit_damage": 0.0, "count": 1.0, "enemies_hit": 2.0}])
    p = weapon_dps_profile(rec, {"elemental_damage": 5})
    # companion hit: max(1, 5+5)=10 -> expected 10 (no crit);
    # per host cycle (1.2s), accuracy 0.9 host hit-rate: 10*1*2/1.2*0.9 = 15
    assert p["proc_dps"] == pytest.approx(15.0)
```

- [ ] **Step 2: Run to verify failure** — ImportError.

- [ ] **Step 3: Implement**

```python
def weapon_dps_profile(rec: dict, stats: dict, *, level: float = 0.0,
                       aoe_enemies_hit: float = 1.0,
                       engagement_distance: float | None = None) -> dict:
    """Realized expected DPS of one weapon record at a full stat block.

    Direct line: expected_hit_damage * accuracy / cycle_time. Proc lines from
    `proc_effects` re-run the same pipeline (weapon_damage re-deals the
    weapon's own hit; burn ticks run scaling+%damage without crit; companion
    projectiles carry their own damage/scaling/crit). `aoe_enemies_hit`
    multiplies proc enemies-hit assumptions, as before.
    """
    asf = (stat_value(stats, "stat_attack_speed")
           + float(rec.get("attack_speed_mod", 0.0))) / 100
    burst = None
    every = rec.get("additional_cooldown_every_x_shots", -1)
    mult = rec.get("additional_cooldown_multiplier", -1.0)
    if isinstance(every, int) and every > 0 and mult and mult > 0:
        burst = (every, float(mult))
    is_melee = rec.get("weapon_type") == "melee"
    dist_used = (min(float(rec.get("max_range", 0.0)), DEFAULT_ENGAGEMENT_DISTANCE)
                 if engagement_distance is None else engagement_distance) if is_melee else None
    ct = stat_aware_cycle_time(
        weapon_type=rec.get("weapon_type", "ranged"),
        recoil_duration=float(rec.get("recoil_duration", 0.0)),
        cooldown=float(rec.get("cooldown", 0.0)),
        attack_speed_frac=asf,
        max_range=float(rec.get("max_range", 0.0)),
        engagement_distance=dist_used if is_melee else None,
        burst=burst)

    hit = per_hit_damage(float(rec["base_damage"]), rec.get("scaling_stats") or [],
                         stats, level=level)
    cc_total = min(1.0, max(0.0, float(rec.get("crit_chance", 0.0))
                            + stat_value(stats, "stat_crit_chance") / 100))
    expected = expected_hit_damage(hit, float(rec.get("crit_chance", 0.0)),
                                   float(rec.get("crit_damage", 0.0)),
                                   stat_value(stats, "stat_crit_chance"))
    accuracy = float(rec.get("accuracy", 1.0))
    base_dps = expected * accuracy / ct if ct > 0 else 0.0

    proc_dps = 0.0
    for eff in rec.get("proc_effects") or []:
        kind = eff.get("kind")
        if kind == "weapon_damage":
            proc_dps += (base_dps * float(eff["chance"])
                         * float(eff["enemies_hit"]) * aoe_enemies_hit
                         * float(eff.get("multiplier", 1.0)))
        elif kind == "burn_dot":
            tick = per_hit_damage(float(eff["damage"]),
                                  eff.get("scaling_stats") or [], stats, level=level)
            proc_dps += tick / float(eff["tick_interval"])
        elif kind == "companion":
            c_hit = per_hit_damage(float(eff["damage"]),
                                   eff.get("scaling_stats") or [], stats, level=level)
            c_expected = expected_hit_damage(
                c_hit, float(eff.get("crit_chance", 0.0)),
                float(eff.get("crit_damage", 0.0)),
                stat_value(stats, "stat_crit_chance"))
            proc_dps += (c_expected * float(eff["count"])
                         * float(eff["enemies_hit"]) * aoe_enemies_hit
                         / ct * accuracy) if ct > 0 else 0.0

    return {
        "dps": base_dps + proc_dps,
        "base_dps": base_dps,
        "proc_dps": proc_dps,
        "cycle_time": ct,
        "per_hit_damage": hit,
        "expected_hit_damage": expected,
        "crit_chance_total": cc_total,
        "effective_cooldown_frames": effective_cooldown(
            float(rec.get("cooldown", 0.0)), asf),
        "engagement_distance_used": dist_used,
    }
```

Note: burn `aoe_enemies_hit` is NOT applied (a burn is per-ignited-target steady state, matching the old model). Weapon-damage and companion procs keep the old model's aoe scaling.

- [ ] **Step 4: Run tests** — pass; ruff green.
- [ ] **Step 5: Commit** — `feat(calc): stat-aware weapon DPS profile with proc descriptors`

---

### Task 5: `Stats.level` + fix the save parser's %damage key

**Files:**
- Modify: `brotato_coach/schemas.py`, `brotato_coach/runfile.py:41-45`
- Test: `tests/test_runfile.py` (or wherever runfile tests live — check `ls tests/`)

**Interfaces:**
- Produces: `Stats.level: float | None`; parsed save stats now include `damage` (%damage).

**Background:** `_STAT_KEY_BY_SHORT` hashes `f"stat_{short}"`, but the game's stat is `stat_percent_damage` while the schema short is `damage` — so `stat_damage` is hashed today and %damage is silently absent from every parsed save. Cross-check against `tools/brotato_inspect.py` STATS list.

- [ ] **Step 1: Write the failing test**

```python
from brotato_coach.runfile import godot_string_hash, _STAT_KEY_BY_SHORT


def test_percent_damage_uses_real_stat_key():
    assert _STAT_KEY_BY_SHORT["damage"] == str(godot_string_hash("stat_percent_damage"))


def test_level_is_not_an_effects_stat():
    assert "level" not in _STAT_KEY_BY_SHORT
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement.** In `schemas.py`, add to `Stats` (after `harvesting`):

```python
    level: float | None = None  # player level, for stat_levels-scaling weapons
```

In `runfile.py`, replace the `_STAT_KEY_BY_SHORT` construction:

```python
# short stat name (as the Stats schema / answer layer use) -> hashed effects key.
# `damage` is the game's stat_percent_damage; `level` is not an effects stat.
_IRREGULAR_STAT_NAMES = {"damage": "stat_percent_damage"}
_STAT_KEY_BY_SHORT = {
    short: str(godot_string_hash(_IRREGULAR_STAT_NAMES.get(short, f"stat_{short}")))
    for short in Stats.model_fields if short != "level"
}
```

- [ ] **Step 4: Run the full suite** — `uv run pytest` (existing runfile/evaluate tests must stay green); ruff green.
- [ ] **Step 5: Commit** — `fix(runfile): parse %damage from saves; add Stats.level`

---

### Task 6: Builders emit raw fields + proc descriptors; drop precomputed lines

**Files:**
- Modify: `brotato_coach/builders/weapons.py`
- Test: `tests/test_build_weapons.py`

**Interfaces:**
- Produces weapon-record fields consumed by Task 4: `weapon_type` ("melee"/"ranged" from the stats script ext_resource basename — `melee_weapon_stats.gd`/`ranged_weapon_stats.gd`), `recoil_duration`, `max_range`, `attack_speed_mod`, `additional_cooldown_every_x_shots`, `additional_cooldown_multiplier`, `proc_effects` (descriptors, shapes in Task 4). Keeps `burst_reload` bool.
- Drops: `cycle_time`, `dps_at_zero_rd`, `dps_slope_per_rd`, `proc_dps_at_zero_rd`, `proc_dps_slope_per_rd`.
- Raises `ValueError` on a scaling stat the engine can't map (unknown-stat guard).

**Key changes in `build_weapon_record`:**
1. Detect type: `parse_tres(stats_text)` exposes `doc.ext_resources`; find the entry whose `path` ends in `weapon_stats.gd`; `weapon_type = "melee" if "melee_weapon_stats" in path else "ranged"`.
2. Read new scalars: `max_range = float(s.get("max_range", 0.0))`, `attack_speed_mod = float(s.get("attack_speed_mod", 0.0))`; emit `every`/`mult` raw (keep `burst_reload = burst is not None`).
3. Guard: for each `scaling_stats` entry, `calc.stat_value({}, name)` must not KeyError — concretely: `name == "stat_levels" or name in calc._SHORT_BY_STAT_NAME or name.removeprefix("stat_") in Stats.model_fields`, else `raise ValueError(f"unknown scaling stat {name!r} on {weapon_id}")`.
4. Replace the proc-line accumulation with descriptor emission (same gating logic, same preconditions — burn still requires `chance == 1.0` and `ct_at_zero_as <= duration window`, companion keeps the targeted/untargeted `enemies_hit` policy):
   - weapon_damage → `{"kind": "weapon_damage", "chance": float(eff.get("chance", 1.0)), "enemies_hit": model["default_enemies_hit"], "multiplier": model["damage_multiplier"]}`
   - burn_dot → `{"kind": "burn_dot", "damage": float(bd["damage"]), "scaling_stats": bd.get("scaling_stats") or [], "tick_interval": model["tick_interval"]}`
   - companion → `{"kind": "companion", "damage": float(ws["damage"]), "scaling_stats": ws.get("scaling_stats") or [], "crit_chance": float(ws.get("crit_chance", 0.0)), "crit_damage": float(ws.get("crit_damage", 0.0)), "count": count, "enemies_hit": enemies_hit}`
   - The burn cycle-time precondition uses `calc.stat_aware_cycle_time(...)` at zero AS with the weapon's own fields (replaces the old `calc.cycle_time`).
5. Delete `_rd_coefficient` and the `calc.dps_line` call.

- [ ] **Step 1: Write failing tests** — extend `tests/test_build_weapons.py` (reuse its existing `.tres` fixture text pattern; read the file first to follow its conventions):

```python
def test_record_carries_raw_timing_and_type_fields():
    rec = build_knife_t1()  # follow the file's existing fixture helper pattern
    assert rec["weapon_type"] == "melee"
    assert rec["recoil_duration"] == pytest.approx(0.1)
    assert rec["max_range"] == 150.0
    assert rec["attack_speed_mod"] == 0.0
    assert rec["additional_cooldown_every_x_shots"] == -1
    for dropped in ("cycle_time", "dps_at_zero_rd", "dps_slope_per_rd",
                    "proc_dps_at_zero_rd", "proc_dps_slope_per_rd"):
        assert dropped not in rec


def test_unknown_scaling_stat_fails_build():
    with pytest.raises(ValueError, match="unknown scaling stat"):
        build_weapon_with_scaling([["stat_bananas", 1.0]])
```

Plus descriptor tests for one weapon_damage, one burn (asserting `scaling_stats` present), one companion — mirror the existing proc tests in that file, asserting descriptors instead of precomputed lines.

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement per the key changes above.** Delete tests of the dropped behavior in the same commit.
- [ ] **Step 4: Run `uv run pytest tests/test_build_weapons.py -v`** — pass. Other test files may now fail (they use old fields) — that's expected until Tasks 7–8; do NOT commit broken; run `uv run pytest` and fix fixture fallout in `tests/test_answers.py`/`tests/test_evaluate.py`/`tests/test_run_report.py` mechanically (fixtures gain the new raw fields; see Task 8 fixture shapes) only as far as needed to keep the suite green, or mark the affected answer-layer tests with the Task 8 rewrite if you are executing tasks strictly in order (preferred: do Task 8 immediately after).
- [ ] **Step 5: Commit** — `feat(builders): emit raw stat-aware fields and proc descriptors, drop RD lines`

---

### Task 7: Schema v6 + dataset rebuild + validation

**Files:**
- Modify: `brotato_coach/dataset.py` (`DATASET_VERSION` → 6; extend `validate_dataset` to require `weapon_type` on every weapon)
- Test: `tests/test_dataset.py` (or wherever `validate_dataset`/version tests live)

- [ ] **Step 1: Failing test** — assert `DATASET_VERSION == 6` and that `validate_dataset` flags a weapon missing `weapon_type`.
- [ ] **Step 2: Verify failure. Step 3: Implement. Step 4: Suite green.**
- [ ] **Step 5: Rebuild the dataset** (MAIN CHECKOUT — see Global Constraints):

Run: `uv run python build_dataset.py`
Expected: `Wrote data/brotato.json: 202 weapon records, ...` with exit 0. If the unknown-scaling-stat guard fires, STOP and add the missing stat mapping (Task 3's `_SHORT_BY_STAT_NAME` or a new `Stats` field) — that's the guard working.

- [ ] **Step 6: Commit** — `feat(dataset): schema v6 — raw stat-aware weapon fields`

---

### Task 8: `answers.weapon_dps` / `compare_weapons` on the new engine

**Files:**
- Modify: `brotato_coach/answers.py:27-78`
- Test: `tests/test_answers.py`

**Interfaces:**
- Produces:
  - `weapon_dps(ds, name, tier, stats, aoe_enemies_hit=1.0, character=None, weapon_count=1, engagement_distance=None, loadout=None, apply_set_bonuses=False) -> dict` — response keys: `name, tier, dps, base_dps, proc_dps, unmodeled_effects, breakdown{per_hit_damage, expected_hit_damage, cycle_time, crit_chance_total, scaling_stats}, assumptions{aoe_enemies_hit, engagement_distance, set_bonuses_applied, active_set_bonuses}, cadence` (`engagement_distance`/`active_set_bonuses` only when applicable).
  - `compare_weapons(...)` same new params; row shape unchanged plus nothing new.
  - `_merge_set_bonus_stats(stats: dict, active: list[dict]) -> dict` (module-private helper).
- Consumes: `calc.weapon_dps_profile`, `loadout_set_bonuses` (existing).

**Fixture update (top of `tests/test_answers.py`):** replace the precomputed-line fixture weapons with raw-field records shaped exactly like Task 4's `KNIFE_T1`/`PISTOL_T1` plus the identity fields the answers layer needs (`id`, `name`, `tier`, `sets`, `effects: []`, `unmodeled_effects: []`, `classified_effects: []`, `burst_reload: False`, `nb_projectiles: 1`). Rewrite existing DPS assertions to the new goldens (Pistol T1 at rd10 → 18.15; Knife T1 at md20 → 36.5607476636).

- [ ] **Step 1: Write the failing tests** (representative — port the rest of the file's existing cases to the new shapes):

```python
def test_weapon_dps_stat_aware_melee():
    r = answers.weapon_dps(DS, "Knife", 1, {"melee_damage": 20})
    assert r["dps"] == pytest.approx(36.5607476636)
    assert r["breakdown"]["per_hit_damage"] == 25
    assert r["assumptions"]["engagement_distance"] == 70.0


def test_weapon_dps_engagement_override():
    close = answers.weapon_dps(DS, "Knife", 1, {}, engagement_distance=0.0)
    far = answers.weapon_dps(DS, "Knife", 1, {})
    assert close["dps"] > far["dps"]


def test_weapon_dps_loadout_reports_but_does_not_merge():
    r = answers.weapon_dps(DS, "Knife", 1, {}, loadout=["Knife", "Knife"])
    assert r["assumptions"]["set_bonuses_applied"] is False
    assert r["assumptions"]["active_set_bonuses"]  # Blade 2: +1 melee_damage
    base = answers.weapon_dps(DS, "Knife", 1, {})
    assert r["dps"] == base["dps"]


def test_weapon_dps_apply_set_bonuses_merges_stats():
    r = answers.weapon_dps(DS, "Knife", 1, {"melee_damage": 19},
                           loadout=["Knife", "Knife"], apply_set_bonuses=True)
    base = answers.weapon_dps(DS, "Knife", 1, {"melee_damage": 20})
    assert r["dps"] == pytest.approx(base["dps"])
```

(The fixture DS needs a Blade set record: `{"id": "set_blade", "name": "Blade", "display_name": "Blade", "bonuses": [{"count": 2, "effect": {"key": "stat_melee_damage", "value": 1}}]}` and Knife carrying `"sets": ["Blade"]`.)

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement:**

```python
def _merge_set_bonus_stats(stats: dict, active: list[dict]) -> dict:
    """Fold active set-bonus stat grants (full stat_* keys) into a short-name
    stat block. Only used when the caller opts in — screen/save stats already
    include these grants in-game."""
    out = dict(stats)
    for bonus in active:
        eff = bonus.get("effect") or {}
        key, value = eff.get("key"), eff.get("value")
        if not key or value is None:
            continue
        short = calc._SHORT_BY_STAT_NAME.get(key, str(key).removeprefix("stat_"))
        out[short] = float(out.get(short, 0)) + float(value)
    return out


def weapon_dps(ds: dict, name: str, tier: int, stats: dict,
               aoe_enemies_hit: float = 1.0, character: str | None = None,
               weapon_count: int = 1, engagement_distance: float | None = None,
               loadout: list[str] | None = None,
               apply_set_bonuses: bool = False) -> dict:
    rec = query.get_weapon(ds, name, tier=tier)
    if "id" not in rec:
        return rec
    if character is not None:
        stats = display_stats(ds, character, stats)

    active_bonuses: list[dict] = []
    if loadout:
        for cls in loadout_set_bonuses(ds, loadout)["classes"]:
            active_bonuses.extend(cls["active"])
        if apply_set_bonuses:
            stats = _merge_set_bonus_stats(stats, active_bonuses)

    profile = calc.weapon_dps_profile(
        rec, stats, level=float(stats.get("level", 0)),
        aoe_enemies_hit=aoe_enemies_hit,
        engagement_distance=engagement_distance)

    assumptions = {"aoe_enemies_hit": aoe_enemies_hit,
                   "set_bonuses_applied": bool(loadout and apply_set_bonuses)}
    if profile["engagement_distance_used"] is not None:
        assumptions["engagement_distance"] = profile["engagement_distance_used"]
    if loadout:
        assumptions["active_set_bonuses"] = active_bonuses

    result = {
        "name": rec["name"], "tier": tier,
        "dps": profile["dps"], "base_dps": profile["base_dps"],
        "proc_dps": profile["proc_dps"],
        "unmodeled_effects": rec.get("unmodeled_effects", []),
        "breakdown": {
            "per_hit_damage": profile["per_hit_damage"],
            "expected_hit_damage": profile["expected_hit_damage"],
            "cycle_time": profile["cycle_time"],
            "crit_chance_total": profile["crit_chance_total"],
            "scaling_stats": rec.get("scaling_stats", []),
        },
        "assumptions": assumptions,
    }
    if profile["cycle_time"] > 0:
        result["cadence"] = calc.cadence_profile(
            profile["cycle_time"], profile["dps"],
            float(profile["effective_cooldown_frames"]),
            weapon_count=weapon_count,
            burst_reload=bool(rec.get("burst_reload", False)))
    return result
```

`compare_weapons` passes the new params through (loadout/apply_set_bonuses/engagement_distance) and keeps its row/sort logic; convert stats via `display_stats` once, then call `weapon_dps` WITHOUT `character` (as today).

- [ ] **Step 4: Run `uv run pytest`** — whole suite green (this task also finishes any fixture fallout from Task 6). Ruff green.
- [ ] **Step 5: Commit** — `feat(answers): stat-aware weapon_dps/compare_weapons with assumptions block`

---

### Task 9: `compare_merge_paths` — numeric RD sweep

**Files:**
- Modify: `brotato_coach/answers.py:81-102`
- Test: `tests/test_answers.py`

**Interfaces:**
- Produces: `compare_merge_paths(ds, weapon_name, path_a, path_b, rd_range=(0, 100), stats=None) -> dict` — keys `weapon, path_a, path_b, winner, rd_independent, crossover_rd, dps_a_at_range_ends, dps_b_at_range_ends`. Crossover = first integer RD where the range-end winner weakly overtakes (game-exact DPS is a step function; document in the docstring).
- Deletes the `calc.sum_lines`/`calc.compare_lines` usage.

- [ ] **Step 1: Failing tests.** Do NOT reuse the Pistol fixture (its accuracy 0.9 / crit 0.1 back the Task 8 goldens). Add a dedicated two-tier fixture weapon "Laser": both tiers `weapon_type: "ranged"`, `cooldown: 60.0`, `recoil_duration: 0.1`, `accuracy: 1.0`, `crit_chance: 0.0`, `crit_damage: 0.0`, `scaling_stats: [["stat_ranged_damage", 1.0]]`, `proc_effects: []`; T1 `base_damage: 12.0`, T2 `base_damage: 30.0` (cycle_time 1.2 both):

```python
def test_merge_paths_crossover_at_rd6():
    # one T2 (base 30) vs two T1 (base 12), ct 1.2 both:
    # rd0: 25.0 vs 20.0 (A); rd6: 30.0 vs 30.0 (first B>=A); rd100: B wins
    r = answers.compare_merge_paths(DS, "Laser", [2], [1, 1])
    assert r["crossover_rd"] == 6
    assert r["rd_independent"] is False


def test_merge_paths_dominant_path():
    r = answers.compare_merge_paths(DS, "Laser", [1], [1, 1])
    assert r["winner"] == "b" and r["rd_independent"] is True
```

- [ ] **Step 2: Verify failure. Step 3: Implement:**

```python
def compare_merge_paths(ds: dict, weapon_name: str, path_a: list, path_b: list,
                        rd_range: tuple = (0, 100), stats: dict | None = None) -> dict:
    """Compare two tier-merge paths across the ranged-damage range at an
    otherwise-fixed stat block (default all-zero). Game-exact DPS is a step
    function of RD, so the crossover is the first integer RD in the range
    where the high-end winner weakly overtakes — not an algebraic intersection.
    """
    base_stats = dict(stats or {})

    def total(tiers: list, rd: int) -> float | None:
        s = dict(base_stats, ranged_damage=rd)
        acc = 0.0
        for t in tiers:
            rec = _weapon_at(ds, weapon_name, t)
            if rec is None:
                return None
            acc += calc.weapon_dps_profile(rec, s)["dps"]
        return acc

    lo, hi = int(rd_range[0]), int(rd_range[1])
    a_lo, b_lo = total(path_a, lo), total(path_b, lo)
    if a_lo is None or b_lo is None:
        return {"error": "not_found",
                "did_you_mean": query.suggest(ds["weapons"], weapon_name)}
    a_hi, b_hi = total(path_a, hi), total(path_b, hi)

    def _winner(a: float, b: float) -> str:
        if abs(a - b) < 1e-9:
            return "tie"
        return "a" if a > b else "b"

    result = {"weapon": weapon_name, "path_a": path_a, "path_b": path_b,
              "dps_a_at_range_ends": [a_lo, a_hi],
              "dps_b_at_range_ends": [b_lo, b_hi]}
    w_lo, w_hi = _winner(a_lo, b_lo), _winner(a_hi, b_hi)
    if w_lo == w_hi or w_lo == "tie":
        return {**result, "winner": w_hi, "rd_independent": True, "crossover_rd": None}
    for rd in range(lo + 1, hi + 1):
        a, b = total(path_a, rd), total(path_b, rd)
        overtaken = b >= a if w_hi == "b" else a >= b
        if overtaken:
            return {**result, "winner": None, "rd_independent": False, "crossover_rd": rd}
    return {**result, "winner": w_hi, "rd_independent": True, "crossover_rd": None}
```

- [ ] **Step 4: Suite + ruff green. Step 5: Commit** — `feat(answers): numeric merge-path crossover on the stat-aware engine`

**Follow-up in this task:** `calc.dps_line`, `dps_at`, `sum_lines`, `compare_lines`, `proc_line`, `burn_dps_line`, `companion_dps_line`, and `cycle_time` now have no consumers — delete them and their tests in a separate commit: `refactor(calc): delete the RD-line model` (grep first: `grep -rn "dps_line\|dps_at\|sum_lines\|compare_lines\|proc_line\|burn_dps_line\|companion_dps_line\|calc.cycle_time" brotato_coach/ tests/`).

---

### Task 10: `stat_gradient`

**Files:**
- Modify: `brotato_coach/answers.py` (new function)
- Test: `tests/test_answers.py`

**Interfaces:**
- Produces: `stat_gradient(ds, weapons: list, stats: dict, step: float = 10.0, character: str | None = None, aoe_enemies_hit: float = 1.0, engagement_distance: float | None = None) -> dict` — `weapons` is `[(name, tier), ...]`; returns `{"baseline_dps", "step", "gradient": [{"stat", "dps_after", "dps_delta", "dps_delta_per_point", "saturated"?}...] , "note"}` sorted by `dps_delta` desc.
- Default step is **10** (not 1): the game's integer truncation makes ±1 frequently a zero delta (Knife: melee_damage 20→21 changes nothing) — 10 is shop-scale and representative.

- [ ] **Step 1: Failing test** (goldens verified by hand this session):

```python
def test_stat_gradient_ranks_scaling_stat_first():
    r = answers.stat_gradient(DS, [("Knife", 1)], {"melee_damage": 20})
    assert r["baseline_dps"] == pytest.approx(36.5607476636)
    top = r["gradient"][0]
    assert top["stat"] == "melee_damage"
    # md30: d2=33, exp=43.0, dps=48.2242990654
    assert top["dps_delta"] == pytest.approx(48.2242990654 - 36.5607476636)
    by_stat = {g["stat"]: g for g in r["gradient"]}
    assert by_stat["attack_speed"]["dps_after"] == pytest.approx(41.8483864071)
    assert by_stat["crit_chance"]["dps_after"] == pytest.approx(40.8224299065)
    assert by_stat["damage"]["dps_after"] == pytest.approx(40.8224299065)


def test_stat_gradient_flags_saturated_crit():
    r = answers.stat_gradient(DS, [("Knife", 1)], {"crit_chance": 80})
    by_stat = {g["stat"]: g for g in r["gradient"]}
    assert by_stat["crit_chance"]["saturated"] is True
```

- [ ] **Step 2: Verify failure. Step 3: Implement:**

```python
_UNIVERSAL_GRADIENT_STATS = ("damage", "attack_speed", "crit_chance")


def stat_gradient(ds: dict, weapons: list, stats: dict, step: float = 10.0,
                  character: str | None = None, aoe_enemies_hit: float = 1.0,
                  engagement_distance: float | None = None) -> dict:
    """Rank stats by how much +`step` of each would raise the loadout's total
    DPS. Candidates = the union of the loadout's scaling stats plus the
    universal multipliers (%damage, attack speed, crit chance). The default
    step of 10 is deliberate: the game's integer damage arithmetic makes a
    ±1 delta frequently zero and unrepresentative.
    """
    if character is not None:
        stats = display_stats(ds, character, stats)
    recs = []
    for name, tier in weapons:
        rec = _weapon_at(ds, name, tier)
        if rec is None:
            return {"error": "not_found",
                    "did_you_mean": query.suggest(ds["weapons"], name)}
        recs.append(rec)

    def total(s: dict) -> float:
        return sum(calc.weapon_dps_profile(
            r, s, level=float(s.get("level", 0)),
            aoe_enemies_hit=aoe_enemies_hit,
            engagement_distance=engagement_distance)["dps"] for r in recs)

    candidates: list[str] = []
    for rec in recs:
        for entry in rec.get("scaling_stats") or []:
            name = entry[0]
            if name == "stat_levels":
                continue
            short = calc._SHORT_BY_STAT_NAME.get(name, name.removeprefix("stat_"))
            if short not in candidates:
                candidates.append(short)
    for short in _UNIVERSAL_GRADIENT_STATS:
        if short not in candidates:
            candidates.append(short)

    baseline = total(stats)
    rows = []
    for short in candidates:
        bumped = dict(stats)
        bumped[short] = float(bumped.get(short, 0)) + step
        after = total(bumped)
        row = {"stat": short, "dps_after": after,
               "dps_delta": after - baseline,
               "dps_delta_per_point": (after - baseline) / step}
        if short == "crit_chance":
            row["saturated"] = all(
                calc.weapon_dps_profile(r, stats)["crit_chance_total"] >= 1.0
                for r in recs)
        rows.append(row)
    rows.sort(key=lambda x: x["dps_delta"], reverse=True)
    return {"baseline_dps": baseline, "step": step, "gradient": rows,
            "note": "delta per +{} of each stat; integer game arithmetic makes "
                    "small steps non-representative".format(step)}
```

- [ ] **Step 4: Suite + ruff green. Step 5: Commit** — `feat(answers): stat_gradient — which stat point helps most`

---

### Task 11: `evaluate_run` on the new engine

**Files:**
- Modify: `brotato_coach/answers.py:181-256` (minimal — the ranking call already passes full stats)
- Test: `tests/test_run_report.py` / `tests/test_evaluate.py` fixtures

**Changes:**
1. `compare_weapons` call: no signature change needed (save stats already include set bonuses — never pass `apply_set_bonuses`). Add `stat_gradient` output: `"stat_gradient": stat_gradient(ds, [(w["id"], w["tier"]) for w in build["weapons"]], stats)["gradient"][:5]` under a `top_stat_gradient` key — the post-mortem's "what to buy next".
2. Update the docstring line about "RD-scaling model" to "stat-aware DPS engine".
3. Test: extend the existing run-report fixture test to assert `top_stat_gradient` is present, non-empty, and sorted desc by `dps_delta`, and that a melee-weapon save's ranking responds to `melee_damage` (two parses differing only in melee_damage effects give different ranking DPS).

- [ ] Steps: failing test → verify → implement → suite+ruff green → commit `feat(answers): evaluate_run gains top_stat_gradient; stat-aware ranking`

---

### Task 12: MCP tool surface + orientation primer

**Files:**
- Modify: `brotato_coach/server.py` (tools `weapon_dps`, `compare_weapons`, `compare_merge_paths`, `get_weapon` docstring; new `stat_gradient` tool), `brotato_coach/orientation.py`
- Test: `tests/test_server.py`

**server.py changes:**
- `weapon_dps`/`compare_weapons` gain `engagement_distance: float | None = None, loadout: list[str] | None = None, apply_set_bonuses: bool = False` and pass through. Docstrings: DPS is now realized stat-aware DPS (all scaling stats + %damage + attack speed + expected crit); melee assumes engagement at `min(max_range, 70)` unless overridden; `loadout` reports active set bonuses, `apply_set_bonuses=True` merges them ONLY for stat blocks that don't already include them (screen/save stats DO); stats must still be DISPLAYED values.
- `compare_merge_paths` gains `stats: Stats | None = None` (`stats=stats.as_dict() if stats else None`); docstring notes the crossover is the first integer RD where the better path flips (step function).
- New tool:

```python
    @mcp.tool()
    def stat_gradient(weapons: list[tuple[str, int]], stats: Stats,
                      step: float = 10.0, character: str | None = None,
                      aoe_enemies_hit: float = 1.0,
                      engagement_distance: float | None = None) -> dict[str, Any]:
        """Rank stats by how much +`step` of each would raise the loadout's
        total DPS — 'which stat should I buy next'. `weapons` is [name, tier]
        pairs for the CURRENT loadout; `stats` the current DISPLAYED stats
        (pass `character` to convert raw values). Candidates are the loadout's
        scaling stats plus %damage / attack speed / crit chance. Default
        step=10 is shop-scale; the game's integer damage arithmetic makes ±1
        deltas unrepresentative. crit rows carry `saturated: true` when crit
        chance is already at certainty. Survivability stats are out of scope —
        this is a DPS gradient only.
        """
        return _safe(lambda **kw: answers.stat_gradient(
            ds, [tuple(x) for x in kw["weapons"]], kw["stats"], kw["step"],
            kw["character"], kw["aoe_enemies_hit"], kw["engagement_distance"]))(
            weapons=weapons, stats=stats.as_dict(), step=step,
            character=character, aoe_enemies_hit=aoe_enemies_hit,
            engagement_distance=engagement_distance)
```

**orientation.py:** replace the "What the precomputed numbers mean" section (lines 74-143) with "How the DPS engine works" covering, in this order: (1) DPS is realized expected DPS at YOUR stat block — every scaling stat, %damage, attack speed (incl. the melee-specific triple-strength back-swing effect), and expected crit are modeled game-exactly (integer truncation/rounding included, so small stat steps can be zero-delta — see stat_gradient's default step); (2) assumptions surfaced per call: aoe_enemies_hit, melee engagement_distance (default min(max_range,70)), set bonuses opt-in (screen/save stats already include them); (3) proc modeling unchanged in spirit (weapon_damage / burn_dot — now genuinely scaling with elemental — / companion), keep the existing explosion_damage/explosion_size and classified_effects/unmodeled_effects prose; (4) what is still NOT modeled: nb_projectiles multiplication (spread/pierce hit rates), character class bonuses (advisory via class_synergy), cooldown floor-skew jitter bias, survivability. Update the "Crit is NOT modeled" bullet (delete), the cycle_time bullet (now stat-aware), and the "Class bonuses are build context" bullet (still true — keep, reworded to cite the new engine). Keep the cadence and bestiary sections as-is.

- [ ] Steps: failing server test (new tool listed, weapon_dps result carries `assumptions`) → verify → implement → suite+ruff green → commit `feat(server): stat-aware tool surface + stat_gradient; rewrite primer`

---

### Task 13: Documentation

**Files:**
- Create: `docs/dps-engine.md`
- Modify: `docs/roadmap.md` (move "DPS engine beyond ranged damage" to shipped; add follow-ups: nb_projectiles multiplication, gradient steps for survivability), `docs/cadence-mechanics.md` (cycle_time formula now stat-aware; melee formula differs from ranged), `docs/stat-mechanics.md` (crit_chance cap note: default LARGE_NUMBER ⇒ uncapped, engine clamps to [0,1]; %damage bracket interaction with set_bonus/explosion already partially documented — cross-link)
- Modify: `brotato_coach/builders/mechanics.py` — the dataset's `stat_mechanics` dict (served by explain_stat) gains: on `stat_crit_chance`, the cap semantics (cap effect defaults to LARGE_NUMBER = uncapped, `player_run_data.gd:436`; the coach clamps total chance to [0,1]) and that crit is now folded into DPS as an expectation; on `stat_attack_speed`, the melee-specific extras (back-swing shrinks by 1+3·AS, swing wind-up by AS/10 — `melee_shooting_data.gd:17-28`). Follow the file's existing entry structure and evidence-citation format; this changes dataset content, so re-run `uv run python build_dataset.py` (main checkout) and keep `tests/test_shipped_dataset.py` green.

**docs/dps-engine.md content:** the full formula chain from the spec's "Game formulas" section (steps A–F), each with its citation **re-verified against recovered/ at write time** (project rule — do not copy line numbers from this plan without re-reading them), plus: the burst-reload "replaces, not adds" correction (weapon.gd:337-339,356-358); the melee timing model and the engagement-distance assumption; the companion-pipeline verification finding from Task 4; the integer-arithmetic steppiness note and its consequence for stat_gradient's default step; explicitly-not-modeled list (nb_projectiles, class bonuses, floor-skew).

- [ ] Steps: write docs → `uv run ruff check .` (docs don't lint, but run the suite once more) → commit `docs: dps-engine formula reference; roadmap/mechanics updates`

---

### Task 14: End-to-end verification + release prep

**Files:**
- Modify: `pyproject.toml` (minor version bump — breaking dataset schema + tool response shapes), `tests/test_shipped_dataset.py`

- [ ] **Step 1: Shipped-dataset invariants** (failing first, MAIN CHECKOUT — needs `data/brotato.json`):

```python
def test_every_weapon_has_type_and_raw_timing():
    for w in DS["weapons"]:
        assert w["weapon_type"] in ("melee", "ranged")
        assert "recoil_duration" in w and "max_range" in w


def test_precise_weapons_respond_to_melee_damage():
    # THE headline fix: every Precise weapon's DPS moves with melee damage —
    # except Crossbow, which scales ranged_damage 0.5 + range 0.1.
    from brotato_coach import calc
    for w in DS["weapons"]:
        if "Precise" not in (w.get("sets") or []):
            continue
        lo = calc.weapon_dps_profile(w, {})["dps"]
        hi = calc.weapon_dps_profile(w, {"melee_damage": 50})["dps"]
        if w["id"] == "weapon_crossbow":
            assert hi == lo
        else:
            assert hi > lo, w["id"]


def test_burn_weapons_respond_to_elemental():
    burn = [w for w in DS["weapons"]
            if any(p["kind"] == "burn_dot" for p in w.get("proc_effects", []))]
    assert burn  # Torch/Fireball/etc. exist
    from brotato_coach import calc
    for w in burn:
        assert (calc.weapon_dps_profile(w, {"elemental_damage": 20})["dps"]
                > calc.weapon_dps_profile(w, {})["dps"]), w["id"]
```

Update the existing v5 assertions (schema_version == 6; delete `dps_slope_per_rd` invariants including the old 35/36 Precise check — it is superseded by the above).

- [ ] **Step 2: Full verification.** `uv run pytest` (all green), `uv run ruff check .` (green), then live smoke: `uv run python -m brotato_coach.server` starts cleanly against the rebuilt dataset (Ctrl+C), and a REPL sanity call:

```
uv run python -c "import json; from brotato_coach import answers; ds=json.load(open('data/brotato.json')); print(answers.stat_gradient(ds, [('Knife',4),('Knife',4)], {'melee_damage':25,'attack_speed':20})['gradient'][:3])"
```

Expected: three rows, melee_damage plausibly first, no exceptions. Also invoke the repo `/verify` skill if executing interactively.

- [ ] **Step 3: Version bump** in `pyproject.toml` (e.g. 0.x → 0.(x+1).0 — check current value; `tests/` reads it dynamically so no literal updates).
- [ ] **Step 4: Commit** — `chore: bump version; shipped-dataset invariants for the stat-aware engine`
- [ ] **Step 5: Finish the branch** per superpowers:finishing-a-development-branch — PR to main, **merge commit** (multi-commit feature). PR body summarizes: engine replacement, schema v6, the burst-reload and save-%damage fixes, new stat_gradient tool.
- [ ] **Step 6 (post-merge, Brendan):** acceptance per spec — converse with the MCP-enabled agent against the rebuilt dataset (melee/crit builds get real answers; stat_gradient recommendations make in-game sense).

---

## Self-review checklist (done at write time)

- Spec coverage: engine core (T1–4), schema v6 + builders (T6–7), Stats.level (T5), answers/API (T8–11), server+primer (T12), docs (T13), invariants+release (T14). Set-bonus opt-in (T8), gradient (T10), save path (T5+T11). ✓
- No placeholders; two explicitly-marked source-verification steps (T2 burst, T4 companion) with default code shown. ✓
- Type consistency: `weapon_dps_profile` keys used in T8/T10 match T4; `proc_effects` shapes in T6 match T4; `stat_value`/`_SHORT_BY_STAT_NAME` shared by T3/T8/T10. ✓
