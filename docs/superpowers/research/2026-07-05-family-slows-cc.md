# Slows / crowd control — proc-worklist investigation dossier
Date: 2026-07-05. Game version: 1.1.15.4 (extracted/). Investigator: subagent.

## Keys covered

Three distinct keys, **two entirely different mechanisms** despite the shared
"slow" theme:

| Key | Script (`[ext_resource]` in the effect `.tres`) | Shipped users |
|---|---|---|
| `EFFECT_WEAPON_SLOW_ON_HIT` | `res://effects/weapons/weapon_slow_on_hit_effect.gd` (`WeaponSlowOnHitEffect`) | particle_accelerator T3, T4 |
| `EFFECT_SLOW_PROJECTILES_ON_HIT` | `res://effects/weapons/projectiles_on_hit_effect.gd` (`ProjectilesOnHitEffect`) | thunder_sword T3, T4 |
| `effect_slow_in_zone` | `res://effects/weapons/slow_in_zone_effect.gd` (`SlowInZoneEffect`) | taser (untiered `.tres` at weapon root, shared by taser T1-T4) |

Census confirmed via `grep -rl` for each key against `extracted/weapons/` (each
hit re-opened and its script line read):
- `extracted/weapons/ranged/particle_accelerator/3/particle_accelerator_3_effect_2.tres:16`
- `extracted/weapons/ranged/particle_accelerator/4/particle_accelerator_4_effect_2.tres:16`
- `extracted/weapons/melee/thunder_sword/3/thunder_sword_3_effect.tres:8`
- `extracted/weapons/melee/thunder_sword/4/thunder_sword_4_effect.tres:8`
- `extracted/weapons/ranged/taser/taser_effect_1.tres:7` (root-dir, untiered —
  confirmed the single file is `ExtResource`-referenced by all four
  `extracted/weapons/ranged/taser/{1,2,3,4}/taser*_data.tres` → `effects = [
  ExtResource( 5 ) ]`, same resource id/path in every tier's data file)

### `EFFECT_WEAPON_SLOW_ON_HIT` parameters (particle_accelerator)

| Weapon/tier | `.tres` | `value` | `scaling_stat` | `effect_sign` |
|---|---|---|---|---|
| particle_accelerator 3 | `.../3/particle_accelerator_3_effect_2.tres` | 1 | `stat_engineering` | 3 |
| particle_accelerator 4 | `.../4/particle_accelerator_4_effect_2.tres` | 2 | `stat_engineering` | 3 |

Both weapons also carry an `effect_1` (`key = "effect_burning"`,
`burning_data = ExtResource(...)`, e.g.
`extracted/weapons/ranged/particle_accelerator/3/particle_accelerator_3_effect_1.tres:15`)
— out of scope here (already covered by the burn spec/model), noted only so
the effects-array count (2 entries) isn't mysterious. Companion files present
in the weapon dirs beyond `*_stats.tres`/`*_data.tres`/effect files:
`particle_accelerator_{3,4}_burning_data.tres` (the already-fixed burn
companion pattern from commit 25f8ca2 — not this key's concern, just noted
per the brief's "list other auxiliary files" instruction).

Host weapon stats (particle_accelerator, both `.gd`-script `ranged_weapon_stats.gd`):

| Weapon/tier | `cooldown` | `damage` | `piercing` | `scaling_stats` |
|---|---|---|---|---|
| particle_accelerator 3 | 100 | 60 | 99 | `[["stat_elemental_damage",1.0],["stat_engineering",1.0]]` |
| particle_accelerator 4 | 80 | 120 | 99 | `[["stat_elemental_damage",1.0],["stat_engineering",1.0]]` |

No companion resource is needed for the slow itself — `WeaponSlowOnHitEffect`
carries its own numbers (`value`, `scaling_stat`) directly on the effect
`.tres`; it is **not** a "numbers live on a companion file" pattern like burn
or lightning.

### `EFFECT_SLOW_PROJECTILES_ON_HIT` parameters (thunder_sword)

| Weapon/tier | `.tres` | `value` (spawn count) | `auto_target_enemy` |
|---|---|---|---|
| thunder_sword 3 | `.../3/thunder_sword_3_effect.tres` | 2 | `false` |
| thunder_sword 4 | `.../4/thunder_sword_4_effect.tres` | 4 | `false` |

**Companion resource required**: both `.tres` files set `weapon_stats =
ExtResource(1)` → `res://weapons/melee/thunder_sword/thunder_sword_projectile_stats.tres`
(a single shared, untiered companion — same file for both T3 and T4). Read
directly (`recovered/weapons/melee/thunder_sword/thunder_sword_projectile_stats.tres`):
`script = res://weapons/weapon_stats/ranged_weapon_stats.gd` (a full
`RangedWeaponStats`), `damage = 1`, `crit_chance = 0.03`, `crit_damage = 2.0`,
`scaling_stats = [["stat_elemental_damage", 1.0]]`, `bounce = 0`,
`bounce_dmg_reduction = 0.5` (engine default, **not** zeroed out unlike
lightning's companions), `can_bounce = true`, `nb_projectiles = 1`,
`piercing = 0`, `projectile_speed = 2000`, and —
the key finding — **`projectile_scene = ExtResource(1) =
res://projectiles/bullet_taser/taser_projectile.tscn`** — the *exact same
projectile scene taser itself fires*. thunder_sword's effects array has only
this one entry (`recovered/weapons/melee/thunder_sword/3/thunder_sword_3_data.tres:21`,
`.../4/thunder_sword_4_data.tres`, both `effects = [ ExtResource(N) ]` with N
pointing only at this effect) — no separate burning effect on thunder_sword.
Host weapon stats: T3 `cooldown=36, damage=40`; T4 `cooldown=27, damage=75`
(both `melee_weapon_stats.gd`, `scaling_stats=[["stat_melee_damage",1.25 or
1.5],["stat_elemental_damage",1.25 or 1.5]]`) — for cycle_time context only.

No other auxiliary `.tres` files exist in the thunder_sword dirs beyond
`*_stats.tres`/`*_data.tres`/effect/companion-projectile-stats files (checked
full `find` listing of both tier dirs and the weapon root).

### `effect_slow_in_zone` parameters (taser)

| Weapon/tier | `.tres` (weapon stats) | `damage` | `scaling_stats` | `nb_projectiles` | `projectile_scene` |
|---|---|---|---|---|---|
| taser 1 | `.../1/taser_stats.tres` | 7 | `[["stat_elemental_damage",0.8]]` | 1 | `taser_projectile.tscn` |
| taser 2 | `.../2/taser_2_stats.tres` | 7 | `[["stat_elemental_damage",0.7]]` | 2 | `taser_projectile.tscn` |
| taser 3 | `.../3/taser_3_stats.tres` | 7 | `[["stat_elemental_damage",0.6]]` | 3 | `taser_projectile.tscn` |
| taser 4 | `.../4/taser_4_stats.tres` | 14 | `[["stat_elemental_damage",0.5]]` | 4 | `taser_projectile.tscn` |

The effect `.tres` itself (`extracted/weapons/ranged/taser/taser_effect_1.tres`)
carries **zero numeric fields relevant to the slow** — `value=1`,
`custom_args=[]`, no `chance`, no magnitude. All four tiers' `weapon_data.tres`
(`.../1/taser_data.tres` through `.../4/taser_4_data.tres`) reference this
exact same `.tres` (`ExtResource` path
`res://weapons/ranged/taser/taser_effect_1.tres` in every one) — confirmed by
reading each `_data.tres`.

## Mechanic (evidence)

**Two unrelated mechanisms share the "slow" vocabulary. Neither is
chance-gated; both apply on every relevant landed hit.**

### 1. `EFFECT_WEAPON_SLOW_ON_HIT` — scaling percent-speed debuff, applied via the *host weapon's own hitbox*

`WeaponSlowOnHitEffect` (`recovered/effects/weapons/weapon_slow_on_hit_effect.gd:1-13`)
extends `NullEffect` (whose `apply`/`unapply` are no-ops,
`recovered/effects/global` — confirmed `NullEffect.apply()`/`unapply()` at
`recovered/effects/weapons/../global`-style `pass` bodies), so this effect
does **nothing** through the generic `RunData.get_player_effects` / `Effect.apply()`
storage path (`recovered/items/global/effect.gd:60-78`) — it is entirely
dispatched by **script class check**, exactly the pattern the brief warns
about:

```gdscript
# recovered/effects/weapons/weapon_slow_on_hit_effect.gd:20-21
func get_speed_percent_modifier(player_index: int) -> int:
    return - max(Utils.get_stat(scaling_stat_hash, player_index), 0) as int * value
```

Consumption, traced end to end:

1. `recovered/weapons/weapon.gd:131-134` (`init_stats`): `args.effects =
   effects` — the host weapon's own `effects` array (which contains this
   `WeaponSlowOnHitEffect` instance for particle_accelerator T3/T4) feeds
   `WeaponServiceInitStatsArgs`.
2. `recovered/singletons/weapon_service.gd:185-191` (`init_base_stats`, effects
   loop):
   ```gdscript
   elif effect is WeaponSlowOnHitEffect:
       new_stats.speed_percent_modifier += effect.get_speed_percent_modifier(player_index)
   ```
   This runs **unconditionally whenever the weapon's stats are recomputed**
   (each wave, on relevant stat changes) — not gated by any chance roll.
   `new_stats.speed_percent_modifier` starts at `from_stats.speed_percent_modifier`
   (line 148), which is `0` on every shipped weapon's base `.tres`
   (`export(int) var speed_percent_modifier := 0`,
   `recovered/weapons/weapon_stats/weapon_stats.gd:26`) — so the additive
   modifier is purely this effect's contribution.
3. `recovered/weapons/weapon.gd:157` (`init_stats`, after stats recompute):
   `_hitbox.speed_percent_modifier = current_stats.speed_percent_modifier` —
   every hitbox the weapon fires carries this modifier baked in (for ranged,
   also propagated onto the fired projectile at
   `recovered/projectiles/player_projectile.gd:63`:
   `_hitbox.speed_percent_modifier = p_weapon_stats.speed_percent_modifier`).
4. **Per landed hit**, `recovered/entities/units/unit/unit.gd:605-606`
   (`hurt_area_entered_deferred`, the enemy being hit):
   ```gdscript
   if hitbox.speed_percent_modifier != 0:
       add_decaying_speed((get_base_speed_value_for_pct_based_decrease() * hitbox.speed_percent_modifier / 100.0) as int)
   ```
   `get_base_speed_value_for_pct_based_decrease()` returns `current_stats.speed`
   (`unit.gd:614-615`) — **the hit enemy's own current speed stat**. So the
   applied slow amount is `enemy_speed * modifier_percent / 100` (negative),
   i.e. a genuine percent-of-current-speed reduction, not a flat number. This
   fires on **every landed hit** from this weapon while `stat_engineering >
   0` — no `Utils.get_chance_success` call anywhere in this path (confirmed
   by reading the whole `WeaponSlowOnHitEffect` class and the two consumption
   sites above — neither references a `chance` field, and none exists on this
   class's exports).
5. **Magnitude depends entirely on the player's `stat_engineering` stat**,
   which is *not* the dataset's RD (raw-damage) scaling axis — at the
   dataset's zero-stat baseline (RD=0), `Utils.get_stat(stat_engineering,...)`
   is presumably also 0 for a fresh calculation not otherwise supplied by this
   codebase's convention, meaning the modeled "zero-baseline" value of this
   effect is 0 (no slow) and it scales with a stat this dataset doesn't
   parameterize elsewhere. UNVERIFIED: I did not trace `Utils.get_stat`'s
   default-absent behavior in depth (out of scope — the point stands
   regardless of the exact zero value, since this mechanic doesn't scale with
   RD at all).
6. **Decay/clamp mechanics** (`add_decaying_speed`,
   `recovered/entities/units/unit/unit.gd:729-740`): a single call is clamped
   to at most `-90%` of the enemy's current speed
   (`value = max(value, -current_stats.speed * 0.9)`, line 738); if the
   enemy's cumulative `decaying_bonus_speed` already sits below `-70%` of
   speed, further additions are dropped entirely (line 733-734); between
   `-45%` and `-70%` new additions are divided by 20 (line 735-736, steep
   diminishing returns). Negative `decaying_bonus_speed` recovers toward 0 at
   `60*delta*5 = 300` units/sec (`unit.gd:160-161`). This is a soft-capped,
   stacking, self-recovering slow — not a fixed-duration debuff with a
   discrete "duration" field.

### 2. `EFFECT_SLOW_PROJECTILES_ON_HIT` and `effect_slow_in_zone` — hardcoded flat slow baked into a shared projectile *scene*, unrelated to the Effect resource's own fields

Per the sibling lightning dossier
(`docs/superpowers/research/2026-07-05-family-lightning.md`), `EFFECT_SLOW_PROJECTILES_ON_HIT`
dispatches via the shared `ProjectilesOnHitEffect` script
(`recovered/effects/weapons/projectiles_on_hit_effect.gd`), consumed at
`recovered/weapons/weapon.gd:146-149` → `recovered/entities/units/unit/unit.gd:586-603`
→ `recovered/singletons/weapon_service.gd:339-363` exactly as documented
there. thunder_sword's config has `auto_target_enemy = false`
(`extracted/weapons/melee/thunder_sword/3/thunder_sword_3_effect.tres:16`,
`.../4/thunder_sword_4_effect.tres:16`) — confirmed **pure random-direction
spawn**, not chain-to-random-enemy (the lightning dossier's Mechanic §4
already documents this distinction for `auto_target_enemy=false`
configurations of the same script).

**The actual slow does not come from any field on this effect `.tres` at
all.** It comes from the *scene* the companion `weapon_stats.projectile_scene`
points to. Read directly:

- `recovered/weapons/melee/thunder_sword/thunder_sword_projectile_stats.tres:40`:
  `projectile_scene = ExtResource( 1 )` → `res://projectiles/bullet_taser/taser_projectile.tscn`
  (confirmed via the file's own `[ext_resource path="res://projectiles/bullet_taser/taser_projectile.tscn" ... id=1]` header line).
- `recovered/weapons/ranged/taser/{1,2,3,4}/taser*_stats.tres` all set
  `projectile_scene = ExtResource( 2 )` → the same
  `res://projectiles/bullet_taser/taser_projectile.tscn` (confirmed in all
  four tier files).

**So thunder_sword's chain-spawned projectile and taser's own primary
projectile are literally the same scene.** That scene
(`recovered/projectiles/bullet_taser/taser_projectile.tscn:56-68`) has a
second Area2D child, `SlowHitbox` (`instance=res://overlap/hitbox.tscn`),
distinct from the primary `Hitbox`:
```
[node name="SlowHitbox" parent="." index="5" instance=ExtResource( 2 )]
collision_layer = 8
deals_damage = false
[node name="Collision" parent="SlowHitbox" index="0"]
shape = SubResource( 3 )   # CircleShape2D radius = 133.5
[connection signal="hit_something" from="SlowHitbox" to="." method="_on_SlowHitbox_hit_something"]
```
and the attached script (`recovered/projectiles/bullet_taser/taser_projectile.gd:1-15`):
```gdscript
func _on_SlowHitbox_hit_something(thing_hit: Node, _damage_dealt: int) -> void :
    thing_hit.add_decaying_speed( - 200)
```
This is a **flat, hardcoded `-200`** call to the same `add_decaying_speed`
described above — **no `chance`, no per-tier scaling, no stat dependency, no
data field anywhere** (not on the effect `.tres`, not on the weapon stats
`.tres`). It is identical for every taser tier and both thunder_sword tiers.
Given `add_decaying_speed`'s single-call clamp
(`value = max(value, -current_stats.speed*0.9)`,
`unit.gd:738`), a raw `-200` will clamp to `-90%` of current speed for any
enemy with `speed < 222` — i.e. functionally an instant near-full stop for
ordinary enemy speeds, subject to the same 300-units/sec recovery and
diminishing-returns stacking rules as mechanism 1 above.

`taser_projectile.gd`'s companion, `recovered/projectiles/bullet_taser/delayed_taser_projectile.gd`
(used by `res://projectiles/bullet_taser/delayed_taser_projectile.tscn`, **not**
referenced by any weapon in this census — grep of `extracted/weapons/`
and `recovered/weapons/` for `delayed_taser_projectile` found no hits outside
the scene/script files themselves) has the identical `SlowHitbox` /
`add_decaying_speed(-200)` pattern; noted for completeness but not a shipped
user of either key today.

**The `SlowHitbox` is a second, independent Area2D — not gated by the
projectile's own piercing/`ignored_objects` bookkeeping.** `player_projectile.gd`
only appends hit targets to `ignored_objects` for its own `_hitbox` (the
"Hitbox" node) — `recovered/projectiles/player_projectile.gd:103-107`
(`_on_Hitbox_hit_something`). `SlowHitbox` has no equivalent connection to
that bookkeeping (only `hit_something → _on_SlowHitbox_hit_something` is
wired). This means the slow zone can, in principle, re-trigger on enemies the
main Hitbox has already "used up" pierce/ignore budget on, and/or slow
enemies the main projectile's damage never actually lands on (the `SlowHitbox`
collision shape, radius 133.5, is roughly 11x the default `Hitbox` scene's own
12-radius default seen in `recovered/overlap/hitbox.tscn` — i.e. it is a
deliberately oversized "slow field" riding along with the bullet, not a
simple duplicate of the damage hitbox). UNVERIFIED: I did not trace the exact
Area2D monitoring/collision-layer wiring far enough to state precisely how
many enemies it can hit per flight (this is a physics/engine-collision
question, not a data question) — recorded as a mechanic nuance, not load
bearing for the CC-vs-DPS classification below.

**Incidental note — thunder_sword's use of this key is *not* purely CC.** The
companion `weapon_stats` (`thunder_sword_projectile_stats.tres`) has its own
`damage = 1`, `scaling_stats = [["stat_elemental_damage", 1.0]]`, and a
regular (`deals_damage=true` by default) primary `Hitbox` on the same
`taser_projectile.tscn` scene. Per the sibling lightning dossier's shared
"companion_ranged_stats" model (out of scope to fully re-derive here, but the
mechanism is the exact same `ProjectilesOnHitEffect` → companion
`RangedWeaponStats` path already fully traced there), thunder_sword's
`EFFECT_SLOW_PROJECTILES_ON_HIT` proc **also deals 1 point of
`stat_elemental_damage`-scaled incidental damage per spawned projectile that
lands**, entirely separate from the slow. This dossier's family assignment is
CC/slows, so the damage sub-component is flagged here for the synthesis phase
and cross-referenced to the lightning dossier's future note about the other
`ProjectilesOnHitEffect`-keyed weapons — **not** modeled or scored here.
taser's own primary attack (its `damage`/`scaling_stats` in the census table
above) is already the weapon's normal, already-modeled base DPS line and
carries no separate "proc" beyond the CC riding along on the same bullet.

## Verdict

**Non-DPS rider (CC/utility)** for the slow behavior of all three keys —
consistent with the family's expected verdict, verified rather than assumed:

- **`EFFECT_WEAPON_SLOW_ON_HIT`** (particle_accelerator T3/T4): grants a
  percent-of-current-enemy-speed movement debuff on every landed hit, scaling
  with the player's `stat_engineering` stat (value=1 or 2 multiplier) and
  decaying back over ~0.3-3s depending on magnitude (see decay-rate math
  above). Deals zero damage; the mechanism modifies `Unit.decaying_bonus_speed`
  only. Proposed dataset classification: tag as a CC/utility effect
  (`slow_percent_scaling` or similar), record `value` and `scaling_stat` for
  documentation/UI purposes, and exclude from all `*_dps*` fields — schema
  naming is Phase 2's call per the brief.
- **`EFFECT_SLOW_PROJECTILES_ON_HIT`** (thunder_sword T3/T4): the *slow*
  component is a hardcoded, non-data-driven `-200` flat speed reduction baked
  into the shared `taser_projectile.tscn` scene's `SlowHitbox`, independent of
  the effect `.tres`'s own fields (which only govern spawn count/targeting,
  per the lightning dossier's shared mechanic). This is CC exactly like
  taser's. **However**, the same proc's companion projectile also deals 1
  point of incidental `stat_elemental_damage`-scaled damage per landed spawn —
  a DPS-relevant sliver that is out of scope for this "slows" family (it's the
  generic `ProjectilesOnHitEffect`/companion-damage pattern the lightning
  dossier already modeled the formula for). Recommend the synthesis phase
  treat thunder_sword's key as **two rows**: a CC tag (this dossier) plus a
  tiny DPS contribution using the lightning dossier's already-derived
  `companion_ranged_stats` formula with `auto_target_enemy=false` (meaning
  `expected_enemies_hit` should almost certainly default lower/differently
  than lightning's chain assumption, since there is no targeting at all — a
  genuine judgment call, not resolved here).
- **`effect_slow_in_zone`** (taser, all tiers): the effect `.tres` itself is
  **inert** — `SlowInZoneEffect extends NullEffect`, no override of
  `apply`/`unapply`/any per-hit hook, `get_args()` returns `[]`. It exists
  purely to (a) attach the tooltip text key `weapon_slow_in_zone` for the
  in-game description and (b) mark the weapon_data's `effects` array so the
  UI shows a slow icon/description. The actual slow (identical `SlowHitbox` /
  `add_decaying_speed(-200)` mechanism) is a property of taser's projectile
  *scene*, which fires on every shot regardless of this effect resource's
  presence — i.e. even if this key were absent from the `.tres`, the slow
  would still happen, because it's compiled into the scene/script, not gated
  by the Effect system at all. Proposed dataset classification: tag as CC
  (taser is "the slow weapon"), zero DPS contribution from this key, and flag
  for the builder that no numeric field on this key's `.tres` is meaningful —
  the true magnitude (`-200` flat, clamped to `-90%` of enemy speed) lives in
  engine code (`recovered/projectiles/bullet_taser/taser_projectile.gd:15`),
  not in extracted data, so it cannot be varied by future dataset versions
  without decompiling again.

None of the three keys pass any precondition for a `DPS-modelable`
classification for the slow itself (no damage field is touched by any of
them); no precondition-verification table is included per the dossier format
(only required for `DPS-modelable` verdicts).

## Precondition verification table

Not applicable — verdict is Non-DPS rider for all three keys' slow
components (no DPS formula proposed for the slow itself).

## Open questions / UNVERIFIED items

- UNVERIFIED: exact `Utils.get_stat(stat_engineering_hash, player_index)`
  zero-baseline behavior for `EFFECT_WEAPON_SLOW_ON_HIT` — not traced in
  depth since it's moot for a non-DPS classification, but worth noting for
  Phase 2 if the dataset ever wants to surface "slow strength at N
  engineering" as a documentation value.
- UNVERIFIED: precise Area2D collision/monitoring semantics of `SlowHitbox`
  (how many enemies it can slow per projectile flight, whether it re-triggers
  on the same enemy multiple times mid-flight) — a physics-engine question,
  not resolved by reading `.tres`/`.gd` alone; flagged as a mechanic nuance,
  not load-bearing for the CC classification.
- **thunder_sword's `EFFECT_SLOW_PROJECTILES_ON_HIT` is a compound key**: CC
  (this dossier, confidently) + a small DPS sliver (out of scope, formula
  already exists in the lightning dossier for the same script/pattern, but
  `auto_target_enemy=false` changes the `expected_enemies_hit` assumption and
  was not re-derived here). Flagging explicitly per the brief's instruction
  to mark compound/ambiguous cases rather than force a single classification
  — the CC half is unambiguous; the DPS half is a separate, not-yet-decided
  judgment call for whoever picks up the `ProjectilesOnHitEffect`-family
  follow-up the lightning dossier already flagged as future work.
- Not investigated: `delayed_taser_projectile.tscn`/`.gd` — same mechanism,
  zero shipped users found in this census, noted only for completeness.
