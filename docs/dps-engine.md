# Stat-aware DPS engine

Formula reference for `brotato_coach/calc.py`'s game-exact DPS evaluator —
the single source of DPS truth (`weapon_dps_profile` and its helpers).
Companion to `docs/cadence-mechanics.md` (timing detail), `docs/proc-mechanics.md`
(proc-line evidence), and `docs/stat-mechanics.md` (per-stat behavior).

## What this replaces

The previous model was a closed-form line in ranged damage,
`dps(rd) = dps_at_zero_rd + dps_slope_per_rd * rd`, precomputed at build time
and blind to melee/elemental/engineering scaling, `%damage`, attack speed, and
crit. That model is gone (`calc.dps_line`, `dps_at`, `sum_lines`,
`compare_lines`, and the build-time proc-line helpers were deleted in this
migration). In its place, `weapon_dps_profile(rec, stats, ...)` computes DPS
at query time from a full player `Stats` block, replicating the game's own
integer arithmetic instead of approximating it with a line. Answer-layer
functions that need DPS across a range of a stat (e.g. `compare_merge_paths`)
now get it by sweeping integer stat values and re-running the full profile at
each point — there is no closed form to sweep analytically.

## Pipeline overview

One landed hit's damage and a weapon's timing are computed independently,
then combined:

```
per_hit_damage      = A (flat scaling) -> B (percent bracket)
expected_hit_damage = per_hit_damage folded with crit as an expectation (C)
cycle_time          = D (attack-speed timing) -> E (ranged/melee shooting duration + cooldown)
dps                 = expected_hit_damage * accuracy / cycle_time, plus proc lines (F)
```

Every step below cites the decompiled source it was re-verified against in
`C:/Users/brend/src/brotato-exam/recovered/` at the time this document was
written (this worktree does not ship `recovered/`).

## A. Flat scaling

`calc.per_hit_damage`'s first stage, `weapon_service.gd:489`
(`apply_scaling_stats_to_damage`) and `weapon_service.gd:469`
(`sum_scaling_stat_values`):

```
d1 = max(1, base_damage + sum(stat_i * coef_i for each scaling_stats entry)) as int
```

`as int` is GDScript truncation toward zero, not rounding (`calc.game_int`).
One scaling name is irregular: `stat_levels` scales with the player's current
level rather than a stat (`weapon_service.gd:473-474`,
`sum_scaling_stat_values`'s `if scaling_stat[0] == Keys.stat_levels_hash`
branch) — `calc.stat_value` special-cases it.

## B. Percent bracket

`weapon_service.gd:239-249`:

```
d2 = max(1, round(d1 * (set_bonus_dmg + 1 + %damage/100 [+ explosion_damage/100 if exploding]))) as int
```

`round` is GDScript's half-away-from-zero rounding (`calc.game_round`), not
Python's banker's rounding. `set_bonus_dmg` accumulates weapon-class-bonus
percent-damage grants (`weapon_service.gd:167-177`, the `stat_h ==
Keys.stat_percent_damage_hash` branch inside the per-set-bonus loop) —
`calc.per_hit_damage` exposes it as `set_bonus_pct` but every caller in this
codebase passes 0 today (character class bonuses stay advisory; see "Not
modeled" below). Floor is 1 damage — `%damage` can go arbitrarily negative
without ever reducing a hit to 0.

## C. Crit (expectation, not a roll)

Total crit chance is the weapon's own base chance plus the player's stat,
capped: `weapon_service.gd:252-253` adds
`Utils.get_capped_stat(stat_crit_chance)/100` to the weapon's `crit_chance`.
`get_capped_stat` (`utils.gd:469-487`) looks up a per-stat cap key —
`stat_crit_chance` maps to `crit_chance_cap` — and returns `min(stat, cap)`.
The cap's *default* value is `LARGE_NUMBER` (99999999)
(`player_run_data.gd:436`, `Keys.crit_chance_cap_hash: Utils.LARGE_NUMBER`),
so in practice the player-stat term is uncapped until an item sets a real
ceiling. The coach still clamps the *combined* chance to `[0, 1]`
(`calc.expected_hit_damage`) because a probability cannot exceed certainty
even though the game's own cap on the stat is a no-op at default.

When a hit does crit, the game rolls it as a boolean
(`Utils.get_chance_success(crit_chance)`, `unit.gd:285`) and deals
`round(damage * crit_damage) as int` (`unit.gd:299-300`). Since DPS is a
long-run average, the engine does not roll — it folds crit into an expected
value instead of a separate burst line:

```
expected_hit_damage = (1 - cc) * d2 + cc * round(d2 * crit_damage)
cc = min(1, max(0, weapon_crit_chance + capped_player_crit_chance/100))
```

## D. Attack speed -> timing

`atk_spd = (stat_attack_speed + weapon.attack_speed_mod) / 100`
(`weapon_service.gd:221`). It feeds two independent things: cooldown and
(for ranged) recoil duration.

**Effective cooldown** (`weapon_service.gd:227-229` floors the base cooldown
at `MIN_COOLDOWN` = 2 frames first; `apply_attack_speed_mod_to_cooldown`,
`weapon_service.gd:570-573`, then applies attack speed and floors again):

```
cd = max(cooldown, 2)
effective_cooldown = max(2, cd / (1 + atk_spd)) as int   if atk_spd > 0
                    = max(2, cd * (1 + abs(atk_spd))) as int   if atk_spd < 0
                    = cd as int                                if atk_spd == 0
```

**Recoil** (`weapon_service.gd:230-232`): `if atk_spd > 0: recoil_duration /=
(1 + atk_spd)`. Negative attack speed does **not** lengthen recoil — the
asymmetry only ever helps.

## E. Cycle time

Cooldown ticks only while the weapon is not mid-swing (`weapon.gd:192-193`),
so `cycle_time = shooting_total_duration + effective_cooldown / 60`.
Ranged and melee weapons compute `shooting_total_duration` completely
differently — this is the mismodeling the old engine had (it applied the
ranged formula to melee swings).

**Ranged** (`ranged_shooting_data.gd:10-15`):

```
shooting = 2 * recoil_duration'
```

just the two symmetric recoil tweens (`ranged_weapon_shooting_behavior.gd:14-48`),
already attack-speed-adjusted per step D.

**Melee** (`melee_shooting_data.gd:17-28`):

```
back_duration = 0.2 / (1 + 3*atk_spd)   if atk_spd > 0   else 0.2
atk_duration   = max(0.01, 0.2 - atk_spd/10) + range_factor * 0.15
range_factor   = max(0, distance / clamp(70 * (1 + atk_spd/3), 70, 120))
shooting       = atk_duration/2 + back_duration + recoil_duration'
```

Melee has two attack-speed-sensitive terms beyond the shared cooldown
formula: `back_duration` (wind-down) only shrinks for positive attack speed,
and via a steeper, non-linear reduction than `atk_duration`'s (it divides by
`1 + 3*atk_spd` rather than a linear `atk_spd/10` subtraction — near
`atk_spd = 0` this makes `back_duration` fall roughly 6x faster per unit of
attack speed than `atk_duration` does); negative attack speed leaves
`back_duration` at its flat 0.2s floor, mirroring the recoil asymmetry in
step D. `atk_duration` also grows with `range_factor`, i.e. with how far
away the target is — a melee weapon takes longer to close and swing at a
target near its max range than at point-blank.

### Engagement distance (assumption constant)

`distance` in `range_factor` is not a fixed game value — it is how far the
target actually is when the swing starts, which depends on positioning the
coach cannot see. The engine defaults to
`distance = min(weapon.max_range, 70)` — a weapon is never credited with
reach beyond its own `max_range`, and 70 is the game's own `range_factor`
denominator floor (so a weapon whose max_range is at or above 70 gets
`range_factor` capped near 1 rather than growing unbounded). This is an
assumption constant of the same kind as `aoe_enemies_hit` — callers can
override it via `engagement_distance` when they know the real fight distance
for a build (e.g. a build that never lets enemies close in).

### Burst reload: replaces, not adds

Revolver (every 6 shots, all tiers) and Chain Gun (every 100 shots, T4) set
`additional_cooldown_every_x_shots`/`additional_cooldown_multiplier`. The
game's `get_next_cooldown` (`weapon.gd:337-339`) checks
`is_big_reload_active` (`weapon.gd:357-358`) first and, if the shot count
hits the trigger, **returns** `cooldown * multiplier` instead of the normal
`rand_range` draw — the reload cooldown *replaces* one ordinary draw, it does
not stack on top of it. The engine amortizes this per cycle as

```
effective_cooldown_amortized = effective_cooldown * ((every_x_shots - 1) + multiplier) / every_x_shots
```

(`calc.stat_aware_cycle_time`'s `burst` parameter) — `every_x_shots - 1`
ordinary cooldowns plus one `multiplier`-scaled reload cooldown, averaged
over the cycle count. `attacks_per_second` computed from this amortized cycle
time is a steady-state average, not the felt fast-then-reload rhythm
(`cadence_profile` flags these `burst_reload: true`; see
`docs/cadence-mechanics.md`).

## F. DPS

```
dps = expected_hit_damage * accuracy / cycle_time
```

plus proc lines, each re-run through the *same* stat-aware pipeline above
rather than frozen at a build-time baseline:

- **weapon_damage** (exploding): re-deals the weapon's own hit — literally
  `base_dps * chance * enemies_hit * aoe_enemies_hit * multiplier` — since the
  explosion inherits the weapon's already-stat-aware damage line.
- **burn_dot**: ticks every 0.5s for `per_hit_damage` of the burn's *own*
  `scaling_stats` (steps A+B only, no crit — a DoT tick doesn't roll crit) —
  so a burn that scales with elemental damage now genuinely grows with it,
  instead of reporting the old flat baseline number.
- **companion**: spawned projectiles (lightning, Cactus Mace, Sniper Gun,
  Thunder Sword) carry their own `damage`/`scaling_stats`/crit fields through
  steps A-C independently of the host weapon, then are divided by the *host's*
  `cycle_time` (they fire alongside the host's own shots).

`nb_projectiles` and `aoe_enemies_hit` semantics are unchanged from the old
model — see "Not modeled" for `nb_projectiles`.

### Companion pipeline verification (Task 4 finding)

The companion-projectile damage line was previously an assumption; this
migration verified it end-to-end against
`recovered/effects/weapons/projectiles_on_hit_effect.gd` (`get_args`
calls `WeaponService.init_ranged_stats(weapon_stats, player_index, true)` —
the third positional argument is `is_special_spawn`) and
`recovered/singletons/weapon_service.gd`'s `init_base_stats`: damage scaling
(`:237`) and the `%damage` bonus (`:239,249`) apply unconditionally to any
spawned stats object, and player crit chance is added (`:252-253`, gated
only on `not is_structure` — companions are not structures). So the full
stat-aware pipeline applies to companion projectiles exactly as it does to
the host weapon's own hits; no fallback or simplification was needed.

## Integer-arithmetic steppiness

Steps A and B truncate/round to whole numbers at every stage. A `+1` bump to
a scaling stat frequently changes `d1` or `d2` by exactly 0 (it gets absorbed
by truncation or rounding) and is therefore not representative of that
stat's real marginal value. This is why `answers.stat_gradient` defaults its
perturbation `step` to 10, not 1 — the doc-string spells this out
(`"the game's integer damage arithmetic makes a ±1 delta frequently zero and
unrepresentative"`) and every gradient response carries a `note` reminding
the caller that small steps are non-representative. Callers who want a
smaller step should pass one explicitly and sanity-check the result isn't
sitting on a rounding plateau.

## Not modeled

- **`nb_projectiles`** — multi-projectile weapons (shotguns, spread weapons)
  are not multiplied by their pellet count. Real DPS from these weapons
  depends on how many pellets actually land, which depends on enemy density
  and positioning with no closed form the engine can evaluate — folding in a
  flat `nb_projectiles` multiplier would silently overstate spread weapons
  against a single target. Tracked as a roadmap follow-up (an
  `aoe_enemies_hit`-style assumption constant, not a straight multiply).
- **Character class bonuses** (PR #16) stay advisory. `per_hit_damage`
  already has a `set_bonus_pct` parameter for weapon-class-bonus percent
  grants (`weapon_service.gd:167-177`), but no caller in this codebase feeds
  it a nonzero value yet — class bonuses are surfaced separately via
  `get_character`/`evaluate_run`'s `class_synergy` section, not consumed by
  `weapon_dps`. Graduating them into DPS is the natural next engine pass; see
  `docs/roadmap.md`.
- **Cooldown floor-skew** — the per-shot cooldown draw floors at 1 frame
  (`weapon.gd:337-349`), which skews the *mean* cooldown above its stated
  basis for fast weapons at high weapon counts (e.g. a 6x Minigun). This
  engine's `effective_cooldown`/`cycle_time` use the raw basis and do not
  model that skew, so nominal DPS modestly overstates such builds. See
  `docs/cadence-mechanics.md` and the roadmap.
- **Survivability** (armor, dodge, HP, regen, lifesteal) is entirely out of
  scope — this is a DPS engine, not a build evaluator. `stat_gradient` ranks
  DPS impact only; a stat that helps survivability but not DPS (e.g. armor)
  will never rank on its gradient, which is expected, not a bug.
