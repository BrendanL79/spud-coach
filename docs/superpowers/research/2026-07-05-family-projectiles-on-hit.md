# Projectiles-on-hit — proc-worklist investigation dossier
Date: 2026-07-05. Game version: 1.1.15.4 (extracted/). Investigator: subagent.

## Relationship to the lightning dossier

This family shares its entire consumption mechanism with
`docs/superpowers/research/2026-07-05-family-lightning.md` (`effect_lightning_on_hit`,
lightning_shiv/dextroyer): the same script,
`recovered/effects/weapons/projectiles_on_hit_effect.gd`
(`class_name ProjectilesOnHitEffect`), and the same end-to-end code path
(`weapon.gd::init_stats` → `Hitbox.projectiles_on_hit` →
`unit.gd::hurt_area_entered_deferred` → `WeaponService.manage_special_spawn_projectile`).
I re-opened and re-verified every citation below myself rather than carrying
them forward (per project rule); line numbers match the lightning dossier's
because it is literally the same code. This dossier does **not** repeat the
full mechanic derivation — it documents the census for `cactus_mace`
(`effect_projectiles_on_hit`) and `sniper_gun` (`EFFECT_PROJECTILES_ON_HIT`),
and focuses on what genuinely **differs**: `auto_target_enemy = false` for
every shipped user of both keys, `bounce = 0` for every shipped user (no
chaining at all), and a companion-file naming pattern the lightning dossier
hadn't seen yet.

## Keys covered

`effect_projectiles_on_hit` (lowercase) — 4 shipped users, all confirmed by
opening every tier dir under `extracted/weapons/melee/cactus_mace/`:

| Weapon | Tier | Effect `.tres` | `value` | `auto_target_enemy` |
|---|---|---|---|---|
| cactus_mace | 1 | `extracted/weapons/melee/cactus_mace/1/cactus_mace_effect_1.tres` | 3 | false |
| cactus_mace | 2 | `extracted/weapons/melee/cactus_mace/2/cactus_mace_2_effect_1.tres` | 4 | false |
| cactus_mace | 3 | `extracted/weapons/melee/cactus_mace/3/cactus_mace_3_effect_1.tres` | 5 | false |
| cactus_mace | 4 | `extracted/weapons/melee/cactus_mace/4/cactus_mace_4_effect_1.tres` | 6 | false |

`EFFECT_PROJECTILES_ON_HIT` (uppercase) — 2 shipped users (only tiers 3-4
exist under `extracted/weapons/ranged/sniper_gun/` — no tier-1/2 dirs, and no
untiered root files; `ls` of the weapon dir confirms this):

| Weapon | Tier | Effect `.tres` | `value` | `auto_target_enemy` |
|---|---|---|---|---|
| sniper_gun | 3 | `extracted/weapons/ranged/sniper_gun/3/sniper_gun_3_effect.tres` | 5 | false |
| sniper_gun | 4 | `extracted/weapons/ranged/sniper_gun/4/sniper_gun_4_effect.tres` | 8 | false |

Each weapon's `_data.tres` (`cactus_mace_data.tres` / `cactus_mace_2_data.tres`
/ `_3_`/`_4_`, and `sniper_gun_3_data.tres`/`sniper_gun_4_data.tres`) carries a
single-element `effects = [ ExtResource( N ) ]` array — **this is the only
on-hit effect either weapon has, at any surveyed tier**; no crit/exploding/burn
effect is stacked alongside it (unlike dextroyer's lightning + explode combo
in the sibling dossier).

**Companion resource required, same "numbers live on a second `.tres`"
pattern as lightning/burn**: every effect `.tres` here has
`weapon_stats = ExtResource( N )` pointing at a second `.tres` carrying the
real gameplay numbers. The effect `.tres` itself has only `value`
(spawn count) and `auto_target_enemy` beyond the common `Effect` base fields.

**Naming-pattern divergence (new, not seen in the lightning dossier) — matters
for the builder's glob**:
- `cactus_mace`: companion is `<weapon>[_tier]_projectile.tres`
  (`cactus_mace_projectile.tres`, `cactus_mace_2_projectile.tres`, ...) —
  same pattern as lightning_shiv's companion.
- `sniper_gun`: companion is `<weapon>_<tier>_proj_stats.tres`
  (`sniper_gun_3_proj_stats.tres`, `sniper_gun_4_proj_stats.tres`) — **a third
  distinct naming convention** (`_proj_stats` instead of `_projectile`). A
  builder glob keyed on a fixed suffix would miss this. Confirms the sibling
  dossier's recommendation: resolve the companion via the effect's own
  `weapon_stats` `ext_resource` reference, not by filename pattern.

No other auxiliary `.tres` files exist in either weapon's tier dirs beyond
`*_stats.tres` / `*_data.tres` / effect file / companion file (confirmed via
full directory listing of both weapon trees — only non-`.tres` extras are
`.tscn`/`.png.import` art assets).

Companion-resource params (all read directly from each file; every field
listed is explicit in the file, no defaults exercised unless noted):

| Weapon/tier | companion path | `damage` | `crit_chance` | `crit_damage` | `scaling_stats` | `bounce` | `bounce_dmg_reduction` | `can_bounce` | `accuracy` | `piercing` |
|---|---|---|---|---|---|---|---|---|---|---|
| cactus_mace 1 | `.../1/cactus_mace_projectile.tres` | 1 | 0.03 | 2.0 | `[["stat_ranged_damage", 0.6]]` | 0 | 0.5 | true | 1.0 | 0 |
| cactus_mace 2 | `.../2/cactus_mace_2_projectile.tres` | 2 | 0.03 | 2.0 | `[["stat_ranged_damage", 0.7]]` | 0 | 0.5 | true | 1.0 | 0 |
| cactus_mace 3 | `.../3/cactus_mace_3_projectile.tres` | 3 | 0.03 | 2.0 | `[["stat_ranged_damage", 0.8]]` | 0 | 0.5 | true | 1.0 | 0 |
| cactus_mace 4 | `.../4/cactus_mace_4_projectile.tres` | 4 | 0.03 | 2.0 | `[["stat_ranged_damage", 1.0]]` | 0 | 0.5 | true | 1.0 | 0 |
| sniper_gun 3 | `.../3/sniper_gun_3_proj_stats.tres` | 5 | 0.2 | 3.0 | `[["stat_range", 0.1]]` | 0 | 0.5 | true | 1.0 | 0 |
| sniper_gun 4 | `.../4/sniper_gun_4_proj_stats.tres` | 5 | 0.2 | 4.0 | `[["stat_range", 0.15]]` | 0 | 0.5 | true | 1.0 | 0 |

Notable divergences from the lightning dossier's table, both worth flagging
to Phase 2:

1. **`bounce = 0` for every single shipped user of both keys** (unlike
   lightning's tier-scaled 0/1/2/3/4). There is no chaining at all for this
   family — each `value` spawn is a one-shot projectile with no bounce.
   `bounce_dmg_reduction = 0.5` is left at the **engine default**
   (`ranged_weapon_stats.gd:9`) rather than explicitly zeroed like every
   lightning user — moot since `bounce = 0` means the reduction formula never
   executes (`player_projectile.gd`'s `bounce()` only runs when
   `_bounce > 0`, gated at `player_projectile.gd:103-110`), but it means a
   gate on "`bounce_dmg_reduction == 0.0` explicit" (as lightning's model
   uses) would **fail** for every user here — the model must gate on
   `bounce == 0` directly instead, not that field.
2. **`cactus_mace`'s companion scales off `stat_ranged_damage`, not
   `stat_elemental_damage`** — despite cactus_mace being a *melee* weapon
   (`weapons/weapon_stats/melee_weapon_stats.gd`-typed host stats, confirmed
   below), its on-hit-spawn companion is a `RangedWeaponStats` resource whose
   `scaling_stats` entry is `stat_ranged_damage` at 0.6/0.7/0.8/1.0 across
   tiers 1-4. Since `brotato_coach/builders/weapons.py:9-13`'s
   `_rd_coefficient()` extracts exactly this stat name, **this proc's slope
   would be nonzero** in the RD-parameterized model — unlike lightning
   (always `stat_elemental_damage`, slope always 0) and unlike burn. This is
   the opposite of what a naive "melee weapon → melee-scaling proc" guess
   would produce; verified per-tier from the raw file text above, not
   inferred.
3. **`sniper_gun`'s companion scales off `stat_range`, not
   `stat_ranged_damage`** (`0.1` T3, `0.15` T4) — a *third* scaling stat
   choice this proc family exhibits (elemental for lightning, ranged-damage
   for cactus_mace, range for sniper_gun). `stat_range` is not
   `stat_ranged_damage`, so `_rd_coefficient()` returns `0.0` for sniper_gun's
   companion — slope is 0 for this key, same "always 0 in this dataset" shape
   as lightning, but for a different underlying reason (wrong stat name, not
   wrong element type).

Host-weapon stats (for `cycle_time` context — the proc's own damage/crit are
independent of these; only the host's attack rate matters):

| Weapon/tier | `.tres` | host stats script | `cooldown` (ticks) | `recoil_duration` | `cycle_time = recoil_duration*2 + cooldown/60` |
|---|---|---|---|---|---|
| cactus_mace 1 | `.../1/cactus_mace_stats.tres` | `melee_weapon_stats.gd` | 63 | 0.1 | 1.25s |
| cactus_mace 2 | `.../2/cactus_mace_2_stats.tres` | `melee_weapon_stats.gd` | 58 | 0.1 | 1.1667s |
| cactus_mace 3 | `.../3/cactus_mace_3_stats.tres` | `melee_weapon_stats.gd` | 54 | 0.1 | 1.1s |
| cactus_mace 4 | `.../4/cactus_mace_4_stats.tres` | `melee_weapon_stats.gd` | 45 | 0.1 | 0.95s |
| sniper_gun 3 | `.../3/sniper_gun_3_stats.tres` | `ranged_weapon_stats.gd` | 120 | 0.2 | 2.4s |
| sniper_gun 4 | `.../4/sniper_gun_4_stats.tres` | `ranged_weapon_stats.gd` | 120 | 0.2 | 2.4s |

(host weapon's own `scaling_stats`, for completeness, not consumed by the
proc formula: cactus_mace host uses `stat_melee_damage` at
0.8/0.85/0.9/1.0 across tiers 1-4 — the *host* correctly scales off melee
damage even though its companion spawn does not; sniper_gun host uses
`[["stat_ranged_damage", 1.0], ["stat_range", 0.2 or 0.3]]`.)

## Mechanic (evidence) — re-verified citations, differences only

Re-opened and confirmed personally (all match the lightning dossier's line
numbers exactly, since it's shared code):

- `recovered/weapons/weapon.gd:131-159` (`init_stats`): the
  `for effect in effects: if effect is ProjectilesOnHitEffect:` block is at
  `weapon.gd:146-149`, building `_hitbox.projectiles_on_hit = [effect.value,
  weapon_stats, effect.auto_target_enemy]` from a fresh, empty
  `on_hit_args` (`weapon.gd:145`).
- `recovered/entities/units/unit/unit.gd:586-603`
  (`hurt_area_entered_deferred`): `for i in hitbox.projectiles_on_hit[0]:
  ... WeaponService.manage_special_spawn_projectile(self,
  hitbox.projectiles_on_hit[1], rand_range(-PI, PI),
  hitbox.projectiles_on_hit[2], ...)` — confirmed the direction argument
  passed in is **always** `rand_range(-PI, PI)` regardless of
  `auto_target_enemy`; that flag only affects what happens next.
- `recovered/singletons/weapon_service.gd:339-364`
  (`manage_special_spawn_projectile`):
  ```
  if auto_target_enemy:
      var target = entity_spawner_ref.get_rand_enemy(entity_from)
      if target != null and is_instance_valid(target):
          direction = (target.global_position - pos).angle()
  ```
  (`weapon_service.gd:353-357`). **This is the load-bearing divergence for
  this family.** When `auto_target_enemy == false` (every shipped user of
  both my keys), this entire block is skipped — `direction` is never
  overwritten and stays exactly the caller's `rand_range(-PI, PI)` value. The
  projectile is fired in a **uniformly random compass direction from the
  position of the enemy that was just hit, with zero bias toward any other
  enemy's position**. Contrast lightning's `auto_target_enemy == true` case,
  where the spawned projectile's direction is deterministically aimed at a
  specific (randomly chosen, but real) enemy.
- `recovered/singletons/weapon_service.gd:92-118`
  (`_set_common_ranged_stats`) and `:119-260` (`init_base_stats`): re-read in
  full; confirms the same zero-stat-baseline reduction the lightning dossier
  used (`new_stats.damage = apply_scaling_stats_to_damage(...)` then
  `new_stats.damage = max(1, round(new_stats.damage * (set_bonus_dmg +
  percent_dmg_bonus + exploding_dmg_bonus)))` where at baseline
  `percent_dmg_bonus == 1.0` and the other two terms are `0`) — reduces to
  the companion's raw `damage` field at RD=0, same simplification burn and
  lightning already use. Also re-confirms `if from_stats.can_bounce: new_stats.bounce
  = from_stats.bounce + <player bounce effect>` (`weapon_service.gd:105-106`)
  — at baseline the player bounce effect is 0, so `new_stats.bounce` stays at
  the companion's own `bounce` field (0 for every user here).
- `recovered/weapons/weapon_stats/weapon_stats.gd:1-20` and
  `recovered/weapons/weapon_stats/ranged_weapon_stats.gd:1-16`: re-read in
  full; engine defaults `damage=1` (`weapon_stats.gd:5`), `accuracy=1.0`
  (`:6`), `crit_chance=0.03` (`:7`), `crit_damage=1.5` (`:8`),
  `scaling_stats=[["stat_melee_damage",1.0]]` (`:16`), `bounce=0`
  (`ranged_weapon_stats.gd:8`), `bounce_dmg_reduction=0.5` (`:9`),
  `can_bounce=true` (`:10`) — all match the lightning dossier's citations.

**No chance gate, `value` is a spawn count not a probability, crit rolls per
spawned projectile independently, the chain projectile carries no further
on-hit effects** — all re-verified true here too (same `Effect` base class,
same `ProjectilesOnHitEffect` export list, same absence of
`Utils.get_chance_success` anywhere in this effect's own consumption path).

## Verdict: TENTATIVE

The damage/scaling/gating shell of the model is identical in shape to
lightning's proposed `"companion_ranged_stats"` `damage_source` — this part
is **not** in question:

```
proc_dps0   = (companion_damage / host_cycle_time) * value * expected_enemies_hit
proc_slope  = (companion_rd_scaling_coef / host_cycle_time) * value * expected_enemies_hit
```

with `companion_damage`/`companion_rd_scaling_coef`/`value`/`host_cycle_time`
all read exactly as in the lightning dossier (see table above for the actual
numbers — note `companion_rd_scaling_coef` is **nonzero** for cactus_mace,
`0.0` for sniper_gun, per the divergence noted above).

What's genuinely unresolved is `expected_enemies_hit`. Lightning's dossier
proposed `1 + bounce`, justified because `auto_target_enemy == true` means
the spawn is aimed at an actual randomly-chosen enemy — the only failure mode
is "no other enemy exists" (a clean, evidenced binary gate). **That
justification does not transfer here.** With `auto_target_enemy == false`
and `bounce == 0` for every shipped user of both keys:

- There is no target selection at all (the `if auto_target_enemy:` branch at
  `weapon_service.gd:353` never runs).
- The projectile's fate is governed purely by `rand_range(-PI, PI)` — a
  uniformly random direction — combined with whatever enemies happen to lie
  along that ray within the projectile's travel distance before it leaves
  play. None of `min_range`/`max_range`/`projectile_speed`/arena size/enemy
  density/hitbox radius are fields this effect or its companion expose in a
  way that yields a hit-probability number; assigning any nonzero
  `expected_enemies_hit` here would be **invented**, not derived, in a way
  lightning's "assume the target exists" default was not.
- There is no bounce to extend the guess either way (`bounce == 0`
  everywhere), so unlike lightning there's no "+bounce" term to even debate —
  the only open question is the base single-shot hit probability of a
  random-direction spawn, which this dossier has no evidence for.

Two candidates for Phase 2, neither picked here:

- **(A) DPS-modelable**, reusing the `"companion_ranged_stats"` shape above,
  with `expected_enemies_hit` supplied as an explicit, clearly-labeled
  assumption constant (e.g. following the exploding-effect precedent of
  `default_enemies_hit: 1.0` in `brotato_coach/builders/procs.py:29-37`) —
  Phase 2 would need to decide what that constant should be (candidates
  include `1.0` for consistency with the exploding default, or something
  lower to reflect that this spray has *no* aim at all, unlike exploding's
  "excludes only the one enemy just hit" case). This dossier does not derive
  or endorse a number.
- **(B) Unmodelable-static (for the enemies-hit factor specifically)** —
  argue that because there is no targeting mechanism whatsoever to anchor a
  default on (contrast exploding/lightning, where the *existence* of a target
  is a real binary condition derivable from wave state), any
  `expected_enemies_hit` constant here is fabricated rather than a documented
  simplification, and the effect should stay in `unmodeled_effects` until/
  unless a future data source (e.g. observed playtest hit-rates) grounds a
  number.

Both candidates share the same damage/scaling math above; they differ only
on whether to multiply it by an invented constant or leave it in
`unmodeled_effects`. Recorded as the judgment call for Phase 2, per the
brief's instruction not to force a choice here.

## Precondition verification table

Preconditions for candidate (A)'s formula shell (everything except the
`expected_enemies_hit` judgment call, which applies uniformly since `bounce
== 0` and `auto_target_enemy == false` for every row — there is no
per-weapon variation to gate on for that part):

| Weapon/tier | `weapon_stats` present | `value>0` | `auto_target_enemy==false` (this family's config) | `bounce==0` | `can_bounce==true` explicit | Companion `scaling_stats` stat | `_rd_coefficient` result |
|---|---|---|---|---|---|---|---|
| cactus_mace 1 | yes | yes (3) | yes | yes | yes | `stat_ranged_damage` | 0.6 |
| cactus_mace 2 | yes | yes (4) | yes | yes | yes | `stat_ranged_damage` | 0.7 |
| cactus_mace 3 | yes | yes (5) | yes | yes | yes | `stat_ranged_damage` | 0.8 |
| cactus_mace 4 | yes | yes (6) | yes | yes | yes | `stat_ranged_damage` | 1.0 |
| sniper_gun 3 | yes | yes (5) | yes | yes | yes | `stat_range` (not RD) | 0.0 |
| sniper_gun 4 | yes | yes (8) | yes | yes | yes | `stat_range` (not RD) | 0.0 |

All 6 shipped users pass every structural precondition (companion present,
`value>0`, no bounce complications). The only open gate is the
`expected_enemies_hit` judgment call in the Verdict section — no shipped user
exercises a case this dossier can resolve on its own.

## Open questions / UNVERIFIED items

- **`expected_enemies_hit` for a random-direction (non-targeted), non-bouncing
  spawn is not derived anywhere in this dossier** — this is the central open
  question, deliberately left to Phase 2 (see Verdict). No number is
  proposed; inventing one from the fields available (projectile speed, huge
  but finite `max_range`, unknown arena size/enemy density) would be
  speculation the brief explicitly asks investigators to avoid.
- UNVERIFIED: whether the huge `max_range` values (9999 cactus_mace, 10000
  sniper_gun) versus the base game's arena dimensions make it likely a
  random-direction shot eventually exits the playable area before it could
  hit anything, or whether `projectile_speed = 3000` (matching every other
  ranged companion surveyed so far) makes this irrelevant in practice — not
  investigated; would require reading arena/camera code and player_projectile
  despawn logic (`recovered/projectiles/player_projectile.gd`,
  `recovered/projectiles/projectile.gd`), which this dossier did not do
  (out of scope per the brief's "don't invent a hit-probability model"
  instruction — pulling in despawn-radius evidence still wouldn't yield a
  hit-probability number without also knowing typical enemy density, which
  no `.tres` file encodes).
- Re-confirmed (not carried forward) that `is_special_spawn == true` for this
  proc's own `init_ranged_stats` call means `_apply_weapon_scaling_stat_effects`
  (flat per-scaling-stat item bonuses, a separate item-effect system) is
  gated OFF for the companion stats: `weapon_service.gd:207` reads
  `if not is_structure and not is_special_spawn or (is_structure and
  is_pet):` — false for this call, so that item-bonus pass is skipped and the
  companion's `scaling_stats` array passes through unmodified into
  `apply_scaling_stats_to_damage`. This matches the lightning dossier's
  finding, but it is more consequential here: because cactus_mace's companion
  scales off `stat_ranged_damage` (nonzero `_rd_coefficient`), any future
  item that grants a flat `stat_ranged_damage` scaling-stat bonus (as opposed
  to the player-wide `stat_ranged_damage` *value*, which does still apply via
  `sum_scaling_stat_values`) would silently not augment this proc's
  coefficient — worth Phase 2 double-checking if a future model tries to be
  more precise than the RD-line convention already accepts.
- Crit is not modeled (dataset-wide simplification, same as lightning
  dossier's §6) — companion `crit_chance`/`crit_damage` values are listed for
  completeness but not proposed for use in the DPS formula.
- Builder plumbing gap (same as lightning dossier, not this phase's job):
  `_weapon_effect_record` in `brotato_coach/builders/weapons.py:16-34` strips
  `ext_resource`-typed fields, so `weapon_stats` is currently dropped from the
  effect record for both keys here too. Additionally, because sniper_gun's
  companion uses a genuinely different filename suffix (`_proj_stats` vs.
  `_projectile`), any future plumbing must resolve the companion via the
  effect's `weapon_stats` ext_resource reference (already recommended by the
  lightning dossier) rather than a filename convention — this dossier adds a
  second, different real-world counterexample to that recommendation.
