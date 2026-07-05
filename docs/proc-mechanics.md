# Brotato proc mechanics

Reference facts derived from decompiled code, for judging weapon on-hit proc
effects without re-deriving from scratch. Companion to `docs/stat-mechanics.md`.
Each entry in `brotato_coach/builders/procs.py`'s `PROC_MODELS` must cite the
evidence recorded here.

## Exploding effect (`ExplodingEffect`, `recovered/effects/weapons/exploding_effect.gd`)

Three weapon-effect `key` values all attach the same `exploding_effect.gd`
script and are therefore the same mechanic at runtime, since the game
dispatches on script class, not on the key string:

- `effect_explode_custom` — Shredder T1/T2/T3 (`chance` 0.5 / 0.65 / 0.8)
- `effect_explode` — Fireball, Nuclear Launcher T3/T4, Rocket Launcher (all
  `chance` 1.0), Shredder T4 (`chance` 1.0)
- `effect_explode_melee` — Plank T1–T4 (0.25 / 0.3 / 0.4 / 0.5), Power Fist
  T3/T4 (0.25 / 0.5), Plasma Sledgehammer T3/T4 (0.25 / 0.5), Dextroyer T4
  (0.5)

All three keys get the same `PROC_MODELS` entry (see below).

### Damage dealt

- `recovered/weapons/weapon.gd:419-436`, `_on_Hitbox_hit_something`: for each
  weapon effect, `if effect is ExplodingEffect and
  Utils.get_chance_success(effect.chance):` spawns an explosion with
  `_explosion_args.damage = _hitbox.damage` (line 427) — the weapon's own
  *current* hit damage (base + scaling stats, post-crit-chance/accuracy
  setup) — and forwards `accuracy`, `crit_chance`, `crit_damage`, and
  `scaling_stats` from the same hitbox (lines 428-431).
- Conclusion: the explosion re-deals the weapon's own damage line, unscaled
  beyond what the weapon already applies. `damage_source: "weapon_damage"`,
  `damage_multiplier: 1.0` is CONFIRMED, not an assumption.

### Enemies-hit semantics (AoE nuance)

- `recovered/weapons/weapon.gd:435`: `_explosion_args.ignored_objects =
  [thing_hit]` — the enemy that was just hit by the direct attack is
  explicitly excluded from the explosion's own hit list. The explosion can
  therefore only damage *other* enemies caught in its blast radius.
- Consequence: against a lone enemy, the exploding proc adds **zero**
  additional damage — the explosion has nothing left to hit. The
  `default_enemies_hit: 1.0` in the model means "assume one *other* enemy is
  caught in the blast," which is conservative for crowded waves (undercounts
  actual value against 3+ enemies) and optimistic against a single target
  (overcounts — the true value there is 0). Callers evaluating single-target
  scenarios (e.g. boss waves) should override `enemies_hit` down.

### Chance default

- `recovered/effects/weapons/exploding_effect.gd:4`: `export (float, 0.0,
  1.0, 0.01) var chance: = 1.0` — the engine's own default for a missing
  `chance` field is 1.0 (always triggers), not some lower value.
- This confirms the builder's existing `eff.get("chance", 1.0)` fallback is
  correct engine behavior, not a silent bug, resolving the carry-over
  question from the original plan.
- Empirically moot either way: all 17 `.tres` files across the three
  exploding-effect keys set `chance` explicitly (verified via `grep -rl
  'key = "effect_explode' extracted/weapons/ | xargs grep chance`), so the
  default never actually fires for a shipped weapon today.

### Known limitation: `explosion_damage` player stat (unmodeled)

- `recovered/singletons/weapon_service.gd:245-249`: weapons flagged
  `is_exploding` get an *additional* multiplicative damage bonus from the
  player's `explosion_damage` stat (`Keys.explosion_damage_hash`), folded
  into `new_stats.damage` alongside `stat_percent_damage`:
  `exploding_dmg_bonus = Utils.get_stat(Keys.explosion_damage_hash,
  player_index) / 100.0`.
- This stat is zero at base (no starting items grant it as a flat weapon
  stat; it only exists as a player-accumulated stat from items), so it does
  not change the weapon's *base* precomputed proc line and is intentionally
  left out of the static dataset. Documented here as a known limitation:
  builds that stack `explosion_damage`-granting items will out-DPS the
  dataset's static `proc_dps_at_zero_rd` line for exploding weapons — callers
  reasoning about such builds should account for this manually.
- `recovered/singletons/weapon_service.gd:511`, `func explode(effect:
  ExplodingEffect, args: WeaponServiceExplodeArgs) -> Node`: spawns the
  explosion scene and applies `args` (the damage + scaling stats captured in
  weapon.gd above) to the explosion's own hitbox — no separate flat damage
  value is defined on the scene itself.

## Burning effect (`BurningEffect`, `recovered/effects/weapons/burning_effect.gd`)

Unlike the exploding effect, `effect_burning`'s gameplay numbers
(`chance`/`damage`/`duration`/`spread`/`scaling_stats`) are **not** on the
weapon-effect `.tres` itself — they live on a separate `BurningData`
resource, referenced only as `burning_data = ExtResource( N )`. The
build pipeline resolves and merges this companion file (`discover.py`'s
`_resolve_effect_burning_data`, `weapons.py`'s `_weapon_effect_record`).

### Tick mechanics

- `recovered/entities/units/unit/unit.tscn:51-52`: `BurningTimer` node,
  `wait_time = 0.5` — burns tick every 0.5s. This is an engine constant,
  not per-weapon.
- `recovered/entities/units/unit/unit.gd:581-583`: on a landed hit,
  `if hitbox.burning_data != null and
  Utils.get_chance_success(hitbox.burning_data.chance) ...:
  apply_burning(hitbox.burning_data)` — chance is rolled once per landed
  hit, not per tick.
- `recovered/entities/units/unit/unit.gd:618-648` (`apply_burning`):
  re-applying while already burning refreshes via `max()` on
  chance/damage/duration/spread — it does not stack additively.
- `recovered/entities/units/unit/unit.gd:660-706` (burn tick handler):
  each tick deals a flat `_burning.damage`, then `_burning.duration -= 1`;
  burn ends at `duration <= 0`.
- `recovered/singletons/weapon_service.gd:290-332` (`init_burning_data`):
  `damage` is scaled by the burn's own `scaling_stats` (default
  `[["stat_elemental_damage", 1.0]]`, `recovered/effects/burning_data.gd:8`)
  then by `stat_percent_damage`. At zero of both — this dataset's baseline —
  it reduces to `max(1, base_damage)`, i.e. the `.tres` `damage` field
  as-is.
- `recovered/effects/burning_data.gd:4`: `export (float) var chance: = 0.0`
  — burn's own missing-field default is **0.0**, unlike the exploding
  effect's default of `1.0`.

### Damage dealt

- `damage_source: "burn_dot"`, modeled as
  `dps0 = damage_per_tick / 0.5`, `slope = 0.0` (`calc.burn_dps_line`).
  Assumes steady-state: continuous attacking keeps the burn refreshed from
  ignition onward, so uptime is effectively 100%.

### Verified precondition (not a general model)

Empirically checked across every shipped burn weapon and tier
(`extracted/weapons/**/*_burning_data.tres` + matching `*_stats.tres`):
every one has `chance = 1.0`, and every one has
`cycle_time <= duration × 0.5s` (tightest margin: Particle Accelerator T3,
cycle_time≈1.95s vs. a 4s window). The model in `builders/weapons.py`
enforces both conditions per-weapon and falls back to `unmodeled_effects`
if either fails, rather than extrapolating an unverified duty-cycle formula
for `chance < 1.0` or a slower-cycling weapon — no shipped weapon exercises
either case.

## Unmodeled effect-key worklist

Effect `key` values found across `extracted/weapons/*.tres`
(`grep -rh '^key = ' extracted/weapons/ | sort | uniq -c`), for future
`PROC_MODELS` entries. Only the exploding-effect and burning keys above are
modeled so far; everything else here contributes zero to `proc_dps_at_zero_rd` and shows
up in a weapon record's `unmodeled_effects` list (except the *(blank key)* row —
a falsy `key` is silently dropped by the builder, not listed):

| count | key |
|---|---|
| 19 | `effect_burning` (modeled) |
| 12 | `effect_gain_stat_every_killed_enemies` |
| 10 | *(blank key)* |
| 9  | `effect_explode_melee` (modeled) |
| 5  | `stat_percent_damage` |
| 5  | `gold_on_crit_kill` |
| 5  | `effect_lightning_on_hit` |
| 5  | `effect_explode` (modeled) |
| 4  | `xp_gain` |
| 4  | `stat_speed` |
| 4  | `stat_lifesteal` |
| 4  | `stat_harvesting` |
| 4  | `stat_armor` |
| 4  | `pierce_on_crit` |
| 4  | `effect_projectiles_on_hit` |
| 4  | `effect_no_hit_boost` |
| 4  | `bounce_on_crit` |
| 4  | `EFFECT_WEAPON_STACK` |
| 3  | `knockback` |
| 3  | `effect_explode_custom` (modeled) |

(plus assorted single-count `stat_*` passthroughs not itemized above)
