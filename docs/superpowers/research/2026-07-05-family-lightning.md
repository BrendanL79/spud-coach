# Lightning — proc-worklist investigation dossier
Date: 2026-07-05. Game version: 1.1.15.4 (extracted/). Investigator: subagent.

## Keys covered

`effect_lightning_on_hit` — 5 shipped users, all confirmed via
`grep -rl 'effect_lightning_on_hit' extracted/weapons/`:

| Weapon | Tier | `.tres` (effect) | `value` (spawn count) | `auto_target_enemy` |
|---|---|---|---|---|
| lightning_shiv | 1 | `extracted/weapons/melee/lightning_shiv/1/lightning_shiv_effect_1.tres` | 1 | true |
| lightning_shiv | 2 | `extracted/weapons/melee/lightning_shiv/2/lightning_shiv_2_effect_1.tres` | 1 | true |
| lightning_shiv | 3 | `extracted/weapons/melee/lightning_shiv/3/lightning_shiv_3_effect_1.tres` | 1 | true |
| lightning_shiv | 4 | `extracted/weapons/melee/lightning_shiv/4/lightning_shiv_4_effect_1.tres` | 1 | true |
| dextroyer | 4 (effect_2, alongside its `effect_explode_melee`) | `extracted/weapons/melee/dextroyer/4/dextroyer_4_effect_2.tres` | 1 | true |

**Companion resource required**: every `effect_lightning_on_hit` `.tres` has
`weapon_stats = ExtResource( N )` pointing at a *second* `.tres` that carries
all the real gameplay numbers (own damage, crit, scaling stats, bounce). This
is the burn-style "numbers live on a companion file" pattern flagged in the
brief — the effect `.tres` itself has no numeric fields beyond `value`
(spawn count, see Mechanic section) and `auto_target_enemy`.

Companion-resource params (all read directly from each file, all fields
explicit — no defaults exercised for damage/crit/scaling/bounce):

| Weapon/tier | companion path | `damage` | `crit_chance` | `crit_damage` | `scaling_stats` | `bounce` | `bounce_dmg_reduction` | `accuracy` |
|---|---|---|---|---|---|---|---|---|
| lightning_shiv 1 | `.../1/lightning_shiv_projectile.tres` | 5 | 0.04 | 2.0 | `[["stat_elemental_damage", 0.8]]` | 0 | 0.0 | 1.0 |
| lightning_shiv 2 | `.../2/lightning_shiv_projectile_2.tres` | 6 | 0.06 | 2.0 | `[["stat_elemental_damage", 0.8]]` | 1 | 0.0 | 1.0 |
| lightning_shiv 3 | `.../3/lightning_shiv_projectile_3.tres` | 8 | 0.08 | 2.0 | `[["stat_elemental_damage", 0.8]]` | 2 | 0.0 | 1.0 |
| lightning_shiv 4 | `.../4/lightning_shiv_projectile_4.tres` | 11 | 0.10 | 2.0 | `[["stat_elemental_damage", 0.8]]` | 3 | 0.0 | 1.0 |
| dextroyer 4 | `.../4/dextroyer_4_effect_2_projectile.tres` | 30 | 0.03 | 2.0 | `[["stat_elemental_damage", 1.0]]` | 4 | 0.0 | 1.0 |

All five companion resources attach `res://weapons/weapon_stats/ranged_weapon_stats.gd`
(a full `RangedWeaponStats` resource, script id confirmed in each file), reuse
`res://projectiles/bullet_lightning/lightning_projectile.tscn` as
`projectile_scene`, and set `can_bounce = true`, `nb_projectiles = 1`,
`piercing = 0`. `cooldown` (60 on every file) is present but **not consumed**
for firing rate (see Mechanic) — it is inert boilerplate on this
special-spawn resource.

Host-weapon stats (for cycle_time context only — the proc's own damage/crit
are fully independent of these; only the host weapon's attack rate matters):

| Weapon/tier | `.tres` | `cooldown` (ticks) | `recoil_duration` | `cycle_time = recoil_duration*2 + cooldown/60` |
|---|---|---|---|---|
| lightning_shiv 1 | `.../1/lightning_shiv_stats.tres` | 27 | 0.1 | 0.65s |
| lightning_shiv 2 | `.../2/lightning_shiv_2_stats.tres` | 22 | 0.1 | 0.5667s |
| lightning_shiv 3 | `.../3/lightning_shiv_3_stats.tres` | 18 | 0.1 | 0.5s |
| lightning_shiv 4 | `.../4/lightning_shiv_4_stats.tres` | 13 | 0.1 | 0.4167s |
| dextroyer 4 | `.../4/dextroyer_4_stats.tres` | 30 | 0.1 | 0.7s |

No other auxiliary `.tres` files exist in these weapon dirs beyond the
already-discovered `*_stats.tres` / `*_data.tres` / effect / companion-
projectile files (checked `ls` of both weapon dirs across all tiers).
Naming pattern to note for the builder: the companion file is named
`<weapon>_projectile[.g_N].tres` for lightning_shiv (sibling to the effect
file, not glob-matched by `*_stats.tres`/`*_data.tres`) and
`<weapon>_<tier>_effect_2_projectile.tres` for dextroyer (i.e. the pattern is
`<effect-file-stem>_projectile.tres`, not a fixed suffix — a builder glob for
this companion type should follow the effect's own `weapon_stats` ext_resource
reference rather than pattern-match a filename, exactly as burn's
`burning_data` companion is already resolved).

## Mechanic (evidence)

**Dispatch is by script class, not key string** (per brief's warning,
confirmed the same way it was for exploding effects). The `.tres` script is
`res://effects/weapons/projectiles_on_hit_effect.gd`
(`class_name ProjectilesOnHitEffect`,
`recovered/effects/weapons/projectiles_on_hit_effect.gd:1-2`). This class is
**shared by four differently-keyed effects** across the dataset — confirmed
by grepping `projectiles_on_hit` in `recovered/` and reading each `.tres`:
`effect_lightning_on_hit` (lightning_shiv/dextroyer, `auto_target_enemy =
true`), `EFFECT_SLOW_PROJECTILES_ON_HIT` (thunder_sword,
`recovered/weapons/melee/thunder_sword/4/thunder_sword_4_effect.tres:8`,
`auto_target_enemy = false`), `EFFECT_PROJECTILES_ON_HIT` (sniper_gun,
`recovered/weapons/ranged/sniper_gun/4/sniper_gun_4_effect.tres:8`,
`value = 8`), and `effect_projectiles_on_hit` (cactus_mace,
`recovered/weapons/melee/cactus_mace/4/cactus_mace_4_effect_1.tres:8`,
`value = 6`). **So "lightning" is really one configuration
(`auto_target_enemy=true` + the lightning projectile scene) of a generic
"spawn N on-hit projectiles" mechanism** — not a lightning-specific chain
script. This dossier only covers the `effect_lightning_on_hit` key/config;
the other three keys are out of scope but share the same consumption code
path (documented here so the synthesis phase knows a future
`EFFECT_PROJECTILES_ON_HIT`/`EFFECT_SLOW_PROJECTILES_ON_HIT`/
`effect_projectiles_on_hit` dossier can mostly reuse this mechanic writeup).

**No chance gate exists.** The `Effect` base class exports
`key`/`value`/`text_key`/`custom_key`/`storage_method`/`effect_sign`/
`custom_args` (`recovered/items/global/effect.gd:7-23`); `ProjectilesOnHitEffect`
adds only `weapon_stats` and `auto_target_enemy`
(`recovered/effects/weapons/projectiles_on_hit_effect.gd:4-5`). There is no
`chance` field anywhere in this schema, and the consumption code (below) never
calls `Utils.get_chance_success` for this effect — unlike `ExplodingEffect`
and `BurningEffect`, which do. **`value` is not a probability — it's a spawn
count**, consumed as a literal loop bound.

**Effect init → per-hit spawn, traced end to end:**

1. `recovered/weapons/weapon.gd:146-149` (`init_stats`, called once per
   weapon-stats recompute, not per-hit):
   ```
   for effect in effects:
       if effect is ProjectilesOnHitEffect:
           var weapon_stats = WeaponService.init_ranged_stats(effect.weapon_stats, player_index, true, on_hit_args)
           _hitbox.projectiles_on_hit = [effect.value, weapon_stats, effect.auto_target_enemy]
   ```
   `on_hit_args` is a **fresh, empty** `WeaponServiceInitStatsArgs.new()`
   (`weapon.gd:145`) — its `.sets`/`.effects` are never populated. This means,
   inside `init_base_stats` (see next point), the `args.sets`/`args.effects`
   loops (weapon-class-set bonuses, `BurningEffect`/`WeaponStackEffect`
   pass-through, etc.) are all inert for the companion weapon_stats — they
   simply have nothing to iterate.
2. `recovered/singletons/weapon_service.gd:34-44` (`init_ranged_stats`) is
   called with `is_special_spawn = true`. Inside
   `init_base_stats` (`weapon_service.gd:119-277`), `is_special_spawn` gates
   OFF `_apply_weapon_scaling_stat_effects` (`weapon_service.gd:207`:
   `if not is_structure and not is_special_spawn or (is_structure and
   is_pet):` — false for this call) — i.e. flat per-scaling-stat item
   bonuses (a separate item-effect system) don't apply to the lightning
   companion stats. Everything else in `init_base_stats` runs unconditionally
   on `is_special_spawn`: `stat_percent_damage` bonus (line 239-249,
   additive with `set_bonus_dmg`/`exploding_dmg_bonus`, both 0 here since
   `args.sets`/`is_exploding` are empty/false), player global crit-chance
   stat added to the companion's own `crit_chance` (line 252-253,
   unconditional), player `accuracy` stat added (line 256), player
   `lifesteal` stat added (line 259-260, non-structure only), and — crucially
   — `apply_scaling_stats_to_damage` (line 237,
   `weapon_service.gd:489-490`: `damage + sum_scaling_stat_values(...)`,
   additive) applies the companion's own `scaling_stats`
   (`stat_elemental_damage`, coefficient 0.8 or 1.0 above) to its own base
   `damage` field. **At the dataset's zero-stat baseline this reduces to the
   companion's raw `damage` field**, same simplification burn already uses.
3. **Per landed hit** — `recovered/entities/units/unit/unit.gd:536-608`
   (`hurt_area_entered_deferred`, on the `Unit`/enemy being hit):
   ```
   if hitbox.projectiles_on_hit.size() > 0:
       for i in hitbox.projectiles_on_hit[0]:
           ...
           var projectile = WeaponService.manage_special_spawn_projectile(
               self,                        # the enemy JUST hit — becomes the spawn origin
               hitbox.projectiles_on_hit[1],  # the pre-computed companion weapon_stats
               rand_range(-PI, PI),           # fallback random direction
               hitbox.projectiles_on_hit[2],  # auto_target_enemy
               _entity_spawner_ref, from, _spawn_projectile_args)
           ...
           projectile.set_ignored_objects([self])
   ```
   (`unit.gd:586-603`). This runs **unconditionally on every landed hit** —
   `value` (1 for all 5 lightning users) new independent projectile(s) spawn
   from the *position of the enemy that was just hit*, each dealing its own
   damage/crit roll when it later collides with something.
4. **Target selection excludes the directly-hit enemy.**
   `recovered/singletons/weapon_service.gd:339-363`
   (`manage_special_spawn_projectile`): if `auto_target_enemy`, `target =
   entity_spawner_ref.get_rand_enemy(entity_from)` where `entity_from` is the
   just-hit enemy (`weapon_service.gd:353-354`).
   `recovered/global/entity_spawner.gd:485-495` (`get_rand_enemy`): picks a
   **uniformly random** enemy from all live enemies, explicitly excluding
   `ignore_unit` (re-rolls until it isn't the ignored unit; returns `null` if
   `enemies.size() <= 1`). **This is random targeting, not "nearest enemy"
   chaining** — the family assignment's phrasing ("chains ... to nearby
   enemies") is not quite right; it's chain-to-a-random-other-enemy. If no
   other enemy exists, `target == null` and the projectile just fires in the
   `rand_range(-PI, PI)` fallback direction from the hit enemy's position
   (`manage_special_spawn_projectile` doesn't override `direction` when
   `target` is null, `weapon_service.gd:356-358`) — it still spawns, but has
   no guided target and, additionally, `unit.gd:601`
   (`projectile.set_ignored_objects([self])`) means it **can never hit the
   enemy it came from** even if it somehow curved back. **Net effect against
   a lone enemy: the chain projectile always spawns but can deal zero
   additional damage** (same "spawns but hits nothing" shape as the exploding
   effect's lone-target case in `docs/proc-mechanics.md`).
5. **Bounce chaining reuses the same random-target logic.**
   `recovered/projectiles/player_projectile.gd:119-129` (`bounce`):
   ```
   func bounce(thing_hit: Node) -> void:
       _bounce -= 1
       var target = thing_hit._entity_spawner_ref.get_rand_enemy(thing_hit)
       var direction = (target.global_position - global_position).angle() if target != null else rand_range(-PI, PI)
       ...
       if _hitbox.damage > 0:
           _hitbox.damage = max(1, _hitbox.damage - (_hitbox.damage * _weapon_stats.bounce_dmg_reduction))
   ```
   Triggered from `player_projectile.gd:103-110`
   (`_on_Hitbox_hit_something`): `if _bounce > 0: bounce(thing_hit)`. Every
   shipped lightning companion sets `bounce_dmg_reduction = 0.0` explicitly
   (engine default is `0.5`,
   `recovered/weapons/weapon_stats/ranged_weapon_stats.gd:9`) — **no damage
   falloff across bounces** for any shipped user. `bounce` is tier-scaled: 0
   (T1) / 1 (T2) / 2 (T3) / 3 (T4) / 4 (dextroyer T4). **UNVERIFIED /
   caveat**: `get_rand_enemy` is only told to exclude the *immediately
   preceding* hit unit, not the full history of enemies already hit by this
   same chain (the projectile's own `ignored_objects` list, appended to on
   every hit at `player_projectile.gd:107`, does accumulate all prior hits —
   but `get_rand_enemy`'s random pick can still re-select an already-hit
   enemy; the projectile would then simply fail to register a hit on it,
   silently "wasting" that bounce with no damage and no further chaining).
   This means the *nominal* bounce count is an upper bound on realized chain
   length in sparse fields, not a guarantee.
6. **Crit applies to each spawned projectile's own hit independently.**
   When the chain projectile itself lands on an enemy, that enemy's
   `hurt_area_entered_deferred` → `take_damage`
   (`recovered/entities/units/unit/unit.gd:262-285`) reads `hitbox.crit_damage`/
   `hitbox.crit_chance` from *that projectile's own hitbox* (i.e. the
   companion's `crit_chance`/`crit_damage`, boosted by the player's global
   crit-chance stat per step 2 above) — `is_crit =
   Utils.get_chance_success(crit_chance)` (`unit.gd:285`). This dataset's
   existing `calc.dps_line`/`calc.proc_line`/`calc.burn_dps_line` do **not**
   model crit anywhere (no crit term in any formula in `brotato_coach/calc.py`)
   — this is a pre-existing, dataset-wide simplification, not something
   specific to this proc. Noted for consistency, not proposed as a gap to
   close here.
7. **The chain projectile carries no further on-hit effects** — it's spawned
   via `_spawn_projectile_args = WeaponServiceSpawnProjectileArgs.new()`
   (`unit.gd:49`) with only `from_player_index` set; `.effects` is left at
   its default (empty), so a lightning chain cannot itself re-trigger
   burning/exploding/another on-hit spawn. No recursion concern.

## Verdict

**DPS-modelable**, but it needs a **new `damage_source`** distinct from both
existing models — call it e.g. `"companion_ranged_stats"` — because unlike
`exploding_effect` (which re-deals the *host weapon's own* current hit
damage, `damage_source: "weapon_damage"`), this proc's damage is **entirely
independent**: its own flat `damage` field, its own `scaling_stats`
coefficient (always `stat_elemental_damage` for every shipped user, never
`stat_ranged_damage`), and its own crit stats, all defined on the companion
`weapon_stats` resource — much closer in spirit to burn's "independent damage
line" than to exploding's "re-deal the host's line."

Proposed formula, in terms the builder already has (`calc.py`'s
`(dps0, slope)` line convention):

```
proc_dps0   = (companion_damage / host_cycle_time) * value * expected_enemies_hit
proc_slope  = (companion_rd_scaling_coef / host_cycle_time) * value * expected_enemies_hit
```
where:
- `companion_damage` = the companion `.tres`'s raw `damage` field (5/6/8/11/30
  above) — this dataset's existing zero-stat-baseline convention (matches how
  `burn_dps_line` uses the raw `burning_data.damage` field, per
  `docs/proc-mechanics.md`).
- `companion_rd_scaling_coef` = the coefficient attached to
  `"stat_ranged_damage"` in the companion's `scaling_stats`, via the same
  `_rd_coefficient()` helper already in `builders/weapons.py:9-13`. **For
  every one of the 5 shipped users this is 0** (their only scaling entry is
  `stat_elemental_damage`), so `proc_slope = 0` for all 5 today — exactly the
  same "slope always 0 in this RD-parameterized dataset" situation
  `docs/proc-mechanics.md` already documents for burn.
- `host_cycle_time` = the *host weapon's own* `calc.cycle_time(...)` (already
  computed for the base weapon record) — the proc fires once per landed host
  hit, at the host's own attack rate, not at the companion's inert `cooldown`
  field.
- `value` = the companion-spawn count from the effect `.tres` (1 for every
  shipped lightning user; the shared-script survey above shows other
  `ProjectilesOnHitEffect` keys use 4/6/8 — out of scope here).
- `expected_enemies_hit` — **the soft, assumption-flagged parameter**,
  directly analogous to the exploding model's `default_enemies_hit`. The
  mechanic (steps 4-5 above) is a chain of up to `bounce + 1` random-enemy
  hits (first hit + `bounce` chained hits), each of which requires another
  live enemy to exist and each of which can fizzle if `get_rand_enemy`
  re-picks an already-chained enemy. Proposing `expected_enemies_hit = 1 +
  bounce` (i.e. assume the full nominal chain connects) as the default,
  **flagged exactly like exploding's note**: optimistic in crowded waves that
  actually have `bounce + 1` other enemies nearby, and **wrong (true value 0)
  against a lone enemy** since even the very first chain hop has no valid
  target. This is a genuine judgment call for Phase 2 (schema/UX), not
  resolved here — recorded as the assumption to surface to callers, same as
  exploding's `default_enemies_hit: 1.0` caveat.

Every field the formula consumes, with engine default (for gating on absence,
mirroring the burn PR's "ungated `damage` field" catch):

| Field | Source | Engine default if missing | Note |
|---|---|---|---|
| `weapon_stats` (companion ref) | effect `.tres` | none — `export (Resource)`, unset ⇒ `null`, and `WeaponService.init_ranged_stats(null, ...)` would fail | **required**; gate on presence |
| `value` | effect `.tres` | `0` (`Effect.value`, `items/global/effect.gd:12`) | 0 ⇒ no spawn at all; must gate `value > 0` |
| `auto_target_enemy` | effect `.tres` | `false` (`projectiles_on_hit_effect.gd:5`) | if `false`, targeting is a pure random direction, not chain-to-enemy — different mechanic, must gate `== true` for this model (all 5 lightning users have it explicit `true`) |
| `damage` | companion `.tres` | `1` (`WeaponStats.damage`, `weapon_stats/weapon_stats.gd:5`) | all 5 explicit |
| `scaling_stats` | companion `.tres` | `[["stat_melee_damage", 1.0]]` (`weapon_stats.gd:16`) | all 5 explicit, all `stat_elemental_damage` |
| `bounce` | companion `.tres` | `0` (`ranged_weapon_stats.gd:8`) | all 5 explicit (0/1/2/3/4) |
| `bounce_dmg_reduction` | companion `.tres` | `0.5` (`ranged_weapon_stats.gd:9`) | all 5 explicit `0.0` — **must gate this**, since a future weapon relying on the engine default would need a decaying-bounce formula this model doesn't have |
| `can_bounce` | companion `.tres` | `true` (`ranged_weapon_stats.gd:10`) | all 5 explicit `true`; if `false`, `bounce` is force-zeroed at `weapon_service.gd:105-108` (`_set_common_ranged_stats`) — gate or handle |
| `accuracy` | companion `.tres` | `1.0` (`weapon_stats.gd:6`) | all 5 explicit `1.0`; not otherwise used in the proposed formula, but a lower value would mean the chain projectile can whiff even with a valid target — undocumented/unverified how that composes, moot since always 1.0 today |
| `crit_chance`/`crit_damage` | companion `.tres` | `0.03`/`1.5` (`weapon_stats.gd:7-8`) | present on all 5; **not modeled** (dataset-wide crit omission, see Mechanic §6) |

## Precondition verification table

| Weapon/tier | `weapon_stats` present | `value>0` | `auto_target_enemy==true` | `bounce_dmg_reduction==0.0` explicit | `can_bounce==true` explicit | Result |
|---|---|---|---|---|---|---|
| lightning_shiv 1 | yes | yes (1) | yes | yes | yes | model applies, `bounce=0` ⇒ `expected_enemies_hit=1` |
| lightning_shiv 2 | yes | yes (1) | yes | yes | yes | model applies, `expected_enemies_hit=2` |
| lightning_shiv 3 | yes | yes (1) | yes | yes | yes | model applies, `expected_enemies_hit=3` |
| lightning_shiv 4 | yes | yes (1) | yes | yes | yes | model applies, `expected_enemies_hit=4` |
| dextroyer 4 | yes | yes (1) | yes | yes | yes | model applies, `expected_enemies_hit=5` |

All 5 shipped users pass every precondition — no fallback-to-`unmodeled_effects`
case is exercised today for this key.

## Open questions / UNVERIFIED items

- `expected_enemies_hit = 1 + bounce` is a **proposed default, not derived
  from evidence** — it is the "assume the nominal chain fully connects"
  choice, symmetric to the exploding model's `default_enemies_hit` softness.
  A more conservative alternative (e.g. `1.0`, ignoring bounce entirely, or a
  wave-density-weighted expectation) is equally defensible from the evidence
  alone; this is a Phase 2 design call, not resolved here.
- UNVERIFIED: whether `get_rand_enemy`'s "re-picks if it equals the single
  `ignore_unit` parameter" can still return an enemy already `ignored_objects`
  from an earlier hop in the *same* chain (the code only excludes the
  *immediately preceding* hit unit, not the full ignored-objects list) — I
  read the code and believe this is possible (a bounce could target-and-then-
  silently-whiff on an already-hit enemy), but did not trace whether the
  physical collision layer would actually let the projectile "pass through" a
  currently-`ignored_objects` enemy without visibly redirecting again; flagged
  as a mechanic nuance, not load-bearing for the proposed formula (it only
  means realized `expected_enemies_hit` may run below the `1+bounce` ceiling
  in practice, which the "optimistic" caveat already covers).
- Not investigated: the other three `ProjectilesOnHitEffect`-keyed weapons
  (thunder_sword `EFFECT_SLOW_PROJECTILES_ON_HIT`, sniper_gun
  `EFFECT_PROJECTILES_ON_HIT`, cactus_mace `effect_projectiles_on_hit`) — out
  of scope for the "lightning" family assignment, but documented here since
  they share this exact consumption code path and a future dossier for those
  keys can reuse most of the Mechanic section (modulo `auto_target_enemy =
  false` changing the targeting semantics — those three all have it `false`,
  meaning pure random-direction spray, not random-enemy chaining).
- Builder plumbing gap (not this phase's job to fix, but noting per brief):
  today's `_weapon_effect_record` in `brotato_coach/builders/weapons.py:16-34`
  strips all `ext_resource`-typed fields, so the `weapon_stats` companion
  reference is currently silently dropped from the effect record — same
  category of gap burn's `burning_data` needed a dedicated `extra_text`
  parameter for. This key cannot be modeled without equivalent plumbing added
  to resolve and nest the companion `.tres` under something like
  `effects[i].weapon_stats`.
