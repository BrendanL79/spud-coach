# Stat-aware DPS engine — design

**Date:** 2026-07-13
**Status:** approved (design review with Brendan, this session)
**Replaces:** the RD-only DPS line model (`calc.dps_line` + `builders/weapons.py:_rd_coefficient`)
**Roadmap origin:** docs/roadmap.md "DPS engine beyond ranged damage"

## Context

The shipped DPS model is a line in ranged damage: `dps(rd) = dps_at_zero_rd +
dps_slope_per_rd · rd`, precomputed at build time. It ignores melee/elemental/
engineering scaling, %damage, attack speed, and crit entirely. Consequence: 35 of 36
Precise weapons have a zero RD slope, so for melee/crit characters the model is a
flat constant and cannot answer "what should I buy next". Burn procs are hardcoded
slope-0 because their elemental scaling has no axis to live on. Melee cycle time is
also mismodeled (the ranged formula is applied to melee swings).

This spec replaces the model with a single query-time, game-exact evaluator over the
full player stat block.

## Decisions (from design review)

1. **Stat input:** tools accept an explicit `Stats` block *and* the save-derived path
   (`evaluate_run` / `runfile.parse_run`) feeds real run stats through the same engine.
2. **Single engine:** the stat-aware evaluator is the only source of DPS truth.
   RD-sweep UX (merge-path crossovers) is re-derived from it numerically. The old
   line fields and `calc.dps_line`/`dps_at`/`compare_lines` are removed.
3. **Game-exact arithmetic:** replicate the game's integer truncation, `round()`,
   `max(1, …)` floors, and the 2-frame cooldown floor. Crit and accuracy layer on
   top as expectations (DPS is an expected value; per-hit damage is exact).
4. **Set bonuses:** weapon-set count bonuses are stat grants in the dataset
   (`sets[].bonuses`: count → `{key, value}`). When a loadout is supplied, active
   damage-typed grants merge into the stat block before evaluation. Non-damage
   grants (armor, dodge, …) remain advisory.
5. **Gradient tool ships in v1** (`stat_gradient`): ranks stats by ΔDPS per
   shop-realistic step against the current loadout.
6. **Melee engagement distance:** default `distance = min(max_range, 70)` (so
   `range_factor ≤ 1`), overridable via an `engagement_distance` parameter —
   an assumption constant like `aoe_enemies_hit`.
7. **Character class bonuses** (PR #16) stay advisory — unchanged by this work.

## Game formulas (evidence re-pinned 2026-07-13)

All citations verified against `recovered/` this session; the implementer re-verifies
when writing `docs/dps-engine.md`.

**A. Flat scaling** — `weapon_service.gd:489` (`apply_scaling_stats_to_damage`),
`:469` (`sum_scaling_stat_values`):
`d1 = max(1, base_damage + Σ stat_i·coef_i) as int` (GDScript `as int` truncates);
`stat_levels` uses player level instead of a stat.

**B. Percent bracket** — `weapon_service.gd:239-249`:
`d2 = max(1, round(d1 · (set_bonus_dmg + 1 + %damage/100 [+ explosion/100 if exploding])))`.
`set_bonus_dmg` accumulation: `weapon_service.gd:167-177` (implementer verifies which
set effects land here vs. as plain stat grants).

**C. Crit** — weapon crit chance gains `+ capped(stat_crit_chance)/100`
(`weapon_service.gd:252-253`; cap via `utils.gd:469-482` `get_capped_stat`,
`crit_chance_cap` — pin the default cap value during implementation). Rolled at hit
time, `unit.gd:285,299-300`: `dmg = round(d2 · crit_damage) as int`.
Expected hit damage: `(1−cc)·d2 + cc·round(d2·crit_damage)` with
`cc = min(1, weapon_crit + capped_player_crit/100)`.

**D. Attack speed → timing** — `atk_spd = (stat_attack_speed + weapon.attack_speed_mod)/100`
(`weapon_service.gd:221`). Cooldown: `max(2, cd/(1+as)) as int` if `as>0`,
`max(2, cd·(1+|as|)) as int` if `as<0` (`weapon_service.gd:570-573`, `MIN_COOLDOWN=2`
at `:5`). If `as>0`, `recoil_duration /= (1+as)` (`:230-232`); negative AS does NOT
lengthen recoil.

**E. Cycle time** — cooldown ticks only while not shooting (`weapon.gd:193`), so
`cycle = shooting_total_duration + eff_cooldown/60`:
- **Ranged** (`ranged_shooting_data.gd:10-15`): `shooting = 2·recoil_duration'`.
- **Melee** (`melee_shooting_data.gd`): `shooting = atk_duration/2 + back_duration + recoil_duration'`
  where `atk_duration = max(0.01, 0.2 − as/10) + range_factor·0.15`,
  `back_duration = 0.2/(1+3·as)` if `as>0` else `0.2`,
  `range_factor = max(0, distance / clamp(70·(1+as/3), 70, 120))`.
- Burst reload (Revolver/Chain Gun): amortize `eff_cooldown·(multiplier−1)/every_x_shots`
  extra per cycle, as today (`weapon.gd:337-339`).

**F. DPS** — `dps = expected_hit_damage · accuracy / cycle_time`, plus proc lines
re-based on this evaluator: `proc_line` re-deals the weapon's stat-aware damage;
`burn` evaluates its own `scaling_stats` (finally scaling with elemental damage);
`companion` projectiles evaluate their own damage + scaling. `nb_projectiles` and
`aoe_enemies_hit` semantics unchanged.

Out of scope (stays on roadmap): cooldown floor-skew / per-shot jitter DPS bias.

## Architecture (Approach A — query-time engine)

One-way data flow preserved: builders read `.tres`, emit raw facts; the engine reads
only `data/brotato.json`.

### calc.py (pure, no I/O)
New: `effective_cooldown`, `stat_aware_cycle_time` (weapon_type-aware, takes
`engagement_distance`), `per_hit_damage` (steps A+B), `expected_hit_damage` (step C),
`stat_aware_dps` (step F, incl. proc descriptor evaluation).
Deleted after migration: `dps_line`, `dps_at`, `sum_lines`, `compare_lines`,
build-time proc-line helpers. Cadence functions (`cadence_profile`, `cooldown_jitter`)
survive, fed the stat-aware cycle time.

### Dataset — schema v6 (`builders/weapons.py`, `build_dataset.py`)
Weapon records **add**: `recoil_duration`, `weapon_type` ("melee"/"ranged"),
`max_range`, `attack_speed_mod`, raw burst params
(`additional_cooldown_every_x_shots`, `additional_cooldown_multiplier`), and
structured proc descriptors on `classified_effects` (proc chance/multiplier, burn
tick damage + interval + scaling_stats, companion damage + scaling_stats + count).
**Drop**: `dps_at_zero_rd`, `dps_slope_per_rd`, `proc_dps_at_zero_rd`,
`proc_dps_slope_per_rd`, `cycle_time`.
Builder guard: fail the build on any `scaling_stats` stat name the engine can't map
to a `Stats` field (spirit of the `unmodeled_effects` guard).
Characters/items/sets/enemies/waves unchanged; `stat_mechanics` gains crit-cap and
melee-timing entries.

### schemas.py
`Stats` already covers the needed stats (`damage` = %damage). Add optional `level`.

### answers.py
- `weapon_dps` / `compare_weapons`: full stat block; keep `aoe_enemies_hit`,
  `character` (gain-modifier conversion unchanged), `weapon_count`; add
  `engagement_distance` and optional `loadout` (owned weapons → active set-bonus
  stat grants merged into stats). Response keeps cadence, adds an `assumptions`
  block (engagement distance, enemies hit, set bonuses applied).
- `compare_merge_paths`: same crossover UX, computed by integer-grid RD sweep with
  the rest of the stat block held fixed; crossover = first RD where B ≥ A.
- New `stat_gradient(ds, weapons, stats, step_per_stat)`: perturb each relevant stat
  (union of loadout scaling stats + %damage, attack speed, crit chance, elemental)
  by +1 default, rank by total-loadout ΔDPS; flag capped stats.
- `evaluate_run`: save stats + character + actual loadout (set bonuses) through the
  new path.

### server.py / orientation.py
Updated tool signatures; new `stat_gradient` tool; `get_weapon` returns raw v6
fields. Primer rewritten: crit/melee timing/%damage now modeled, assumption
constants listed, class bonuses still advisory.

## Error handling
- Unknown stat names in a caller's stat block: accepted (`extra="allow"`), ignored by
  the engine unless a weapon scales with them.
- Unknown scaling stat in game data: build-time failure (guard above), so the server
  never sees one.
- Stale dataset: server already validates `schema_version`; bump the expected value
  to 6 so a v5 file fails loudly at startup.

## Testing (TDD, hand-verified goldens)
- `test_calc.py`: per-stage goldens — flat scaling truncation/floor, percent-bracket
  rounding (incl. negative %damage floor at 1), crit expectation, effective cooldown
  (positive/negative AS, 2-frame floor), ranged vs melee cycle time at AS=0 and
  AS=100%, burst amortization, proc/burn/companion re-based lines.
- `test_answers.py`: fixture weapons gain raw fields; stat-block evaluation, loadout
  set-bonus merge, merge-path numeric crossover, gradient ranking, assumptions block.
- `test_build_weapons.py`: goldens for new raw fields on real weapons.
- `test_shipped_dataset.py`: schema v6; new invariant — every Precise weapon's DPS
  responds to melee_damage — except Crossbow, which responds to ranged damage and
  range (`scaling_stats` = RD 0.5 + range 0.1) — the bug this work exists to fix;
  burn weapons respond to elemental damage.
- `test_server.py`: tool signatures, `stat_gradient` happy path.
- Expected numeric drift vs the old model (crit, melee timing, rounding) is
  intentional; goldens are recomputed by hand, not carried forward.

## Migration / release
- Rebuild the local dataset at schema v6 (current local file is fresh — v5,
  game_version 1.1.15.4 — it just predates the schema change).
- Version bump: minor (breaking dataset schema + tool response shape changes).
- Large multi-commit feature → merge commit per project convention.
