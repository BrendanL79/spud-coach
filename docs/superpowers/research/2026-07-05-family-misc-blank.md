# Miscellaneous + blank-key effects — proc-worklist investigation dossier
Date: 2026-07-05. Game version: 1.1.15.4 (extracted/). Investigator: subagent.

## Keys covered

| key | weapon | tier(s) | script (recovered/) | value(s) |
|---|---|---|---|---|
| `burning_spread` | Torch | 3, 4 | `items/global/effect.gd` (generic `Effect`) | 1, 1 |
| `consumable_heal` | Chopper | 1, 2, 3 (shared root file), 4 (own file) | `items/global/effect.gd` (generic `Effect`) | 1, 1, 1, 2 |
| `lose_hp_per_second` | Scythe | 4 (only tier; legendary-only weapon) | `items/global/effect.gd` (generic `Effect`) | 3 |
| *(blank key `""`)* | Vorpal Sword | 2, 3, 4 (no tier 1 ships) | `effects/weapons/one_shot_on_hit_effect.gd` (`OneShotOnHitEffect`) | 1, 2, 3 |
| *(blank key `""`)* | Screwdriver | 1, 2, 3, 4 | `effects/items/structure_effect.gd` (`StructureEffect`) | spawn_cooldown 12, 9, 6, 3 (all value=1) |
| *(blank key `""`)* | Pruner | **1, 2, 3, 4 — census correction, see below** | `effects/items/turret_effect.gd` (`TurretEffect`, extends `StructureEffect`) | spawn_cooldown(frames) 900, 840, 720, 600 (all value=1) |

**Census correction:** the brief's fresh census listed pruner as tiers 2-4 only. Pruner
tier 1 (`extracted/weapons/melee/pruner/1/pruner_data.tres`, `my_id =
"weapon_pruner_1"`, `tier = 0`) also carries a blank-key effect — it references a
*shared, non-weapon-specific* file, `extracted/items/all/garden/garden_effect_1.tres`
(same `turret_effect.gd` script, `key = ""`), rather than its own
`pruner_1_effect_*.tres`. This is why a naive per-weapon-dir grep would miss it: the
effect file lives outside `weapons/melee/pruner/` entirely. All four pruner tiers
carry the same blank-key Garden mechanic; only the spawn cooldown changes.

**Non-assigned effect noted for context, not analyzed here:** Scythe T4 also carries
a second effect, `stat_percent_damage` (`extracted/weapons/melee/scythe/4/
scythe_effect_2.tres`, `custom_key = "temp_stats_on_hit"`, `storage_method = 1`
i.e. `KEY_VALUE`) — an on-hit stacking self-buff. This key belongs to a different
family's worklist item (`stat_percent_damage`, 5 occurrences); flagging only so the
synthesis phase knows it lives on the same weapon.

## Mechanic (evidence)

### `burning_spread` — Torch T3/T4 (also Snake item, out of weapon scope)

Both Torch T3 and T4 ship two effects: `effect_burning` (already modeled,
`torch_3_effect_1.tres` / `torch_4_effect_1.tres`, script
`effects/weapons/burning_effect.gd`) plus a second effect,
`torch_3_effect_2.tres` / `torch_4_effect_2.tres`:
```
script = ExtResource( 1 )   # res://items/global/effect.gd
key = "burning_spread"
value = 1
storage_method = 0   # StorageMethod.SUM
effect_sign = 3
```
This is the **generic** `Effect` class (`recovered/items/global/effect.gd`), not a
bespoke script — per the brief's recipe, that means the key string itself (via its
hash) is what a consumer keys off, not a script class.

- `recovered/singletons/keys.gd:216`: `var burning_spread_hash: =
  generate_hash("burning_spread")`.
- **Apply-time (equip), not hit-time**: `recovered/singletons/run_data.gd:982-989`
  (`add_weapon`) calls `apply_item_effects(new_weapon, player_index)` (line 989),
  which at `run_data.gd:1244-1263` iterates `item_data.effects` and calls
  `effect.apply(player_index)` for each — for the generic `Effect` class this is
  `effect.gd:62-83`: `else: effects[key_hash] += value` (the `StorageMethod.SUM`
  branch). So equipping Torch T3/T4 sums `+1` into
  `RunData.get_player_effects(player_index)[burning_spread_hash]`, once, at pickup
  time — a **global, additive, account-wide** stat, not a per-hit proc.
- **Consumption**: `recovered/singletons/weapon_service.gd:334` (inside
  `init_burning_data`, the same function documented in
  `docs/proc-mechanics.md`'s Burning section): `new_burning_data.spread +=
  RunData.get_player_effect(Keys.burning_spread_hash, player_index)`. This runs for
  **every weapon's** burn application on the player, not just Torch's own hits —
  the stat is global.
- **What `spread` actually does**:
  `recovered/entities/units/unit/unit.gd:651-652`: after a unit starts/refreshes
  burning, `if _burning.spread > 0: _burning_particles.activate_spread()` — arms a
  `SpreadArea` collision shape (`recovered/particles/burning/
  burning_particles.gd:9-10,72-73`).
  `burning_particles.gd:38-45` (`_physics_process`): while armed and a
  non-burning body is inside the area, it does:
  ```
  burning_data.spread = max(0, burning_data.spread - 1)
  body.apply_burning(burning_data)   # ignites the nearby enemy with a duplicate
  burning_data.spread = 0            # then forces the ORIGINAL body's spread to 0
  deactivate_spread()
  break
  ```
  Since `burning_data.spread` is decremented **before** being handed to the newly
  ignited body, a spread value ≥2 (only reachable by stacking multiple sources,
  e.g. Torch + the Snake item, both `burning_spread` value=1) lets the burn chain to
  a second, third, etc. victim; with only Torch's own `+1`, it is strictly a
  **single one-hop spread to one additional enemy**, then stops
  (`unit.gd:705-706`: `elif _burning.spread <= 0: _burning_particles.deactivate_spread()`).
- Base `BurningData.spread` default is `0`
  (`recovered/effects/burning_data.gd:7`), and every shipped burn weapon's
  `*_burning_data.tres` sets `spread = 0` explicitly (verified for Torch T3/T4
  above) — so without a `burning_spread` source, burns never propagate at all.

### `consumable_heal` — Chopper T1-T4

All four Chopper tiers ship a single generic `Effect`
(`items/global/effect.gd`): T1/T2/T3 share the weapon-root file
`extracted/weapons/melee/chopper/chopper_effect.tres` (`value = 1`); T4 has its own
`chopper_4_effect.tres` (`value = 2`). Same apply-at-equip mechanism as
`burning_spread` above (`run_data.gd:1244-1263`, `StorageMethod.SUM`, summed into
`RunData.get_player_effects()[consumable_heal_hash]`
(`recovered/singletons/keys.gd:213`)).

- **Consumption — healing consumables**:
  `recovered/effects/consumables/consumable_healing_effect.gd:5-16`
  (`ConsumableHealingEffect.apply`, used by Fruit, Weird Food, Lemonade, Legendary
  Item Box, per `recovered/singletons/item_service.gd:79`'s
  `"consumable_heal": ["item_jerky", "item_weird_food", "item_lemonade",
  "item_fruit_basket"]` group and the matching `*_effect*.tres` files under
  `recovered/items/all/`): `var consumable_heal_effect =
  RunData.get_player_effect(Keys.consumable_heal_hash, player_index); var
  total_healing = max(0, value + consumable_heal_effect)` — Chopper's held bonus
  is added straight onto every healing consumable's heal amount when eaten.
- **Consumption — damage consumables**:
  `recovered/effects/consumables/consumable_damage_effect.gd:5-8`
  (`ConsumableDamageEffect.apply`): `var damage_value = value +
  RunData.get_player_effect(Keys.consumable_heal_hash, player_index)` — the same
  stat also nets against consumables that deal the player damage (mitigating them),
  same sign convention.
- No combat/on-hit involvement anywhere; `NullEffect`/hitbox code never reads this
  hash. This is a passive, held, account-wide consumable-outcome buff — entirely
  independent of Chopper's own attacks.

### `lose_hp_per_second` — Scythe T4 (only tier)

`extracted/weapons/melee/scythe/4/scythe_effect.tres`: generic `Effect`, `key =
"lose_hp_per_second"`, `value = 3`, `effect_sign = 1` (NEGATIVE — UI-only sign, does
not affect magnitude). Same apply-at-equip mechanism (`run_data.gd:1244-1263`,
`StorageMethod.SUM`) sums `+3` into
`RunData.get_player_effects()[lose_hp_per_second_hash]`
(`recovered/singletons/keys.gd:228`).

- `recovered/entities/units/player/player.gd:125-126`: on player init, `if
  RunData.get_player_effect(Keys.lose_hp_per_second_hash, player_index) > 0:
  _lose_health_timer.start()`.
- `recovered/entities/units/player/player.gd:844-850`
  (`_on_LoseHealthTimer_timeout`): `_take_damage_args.dodgeable = false;
  _take_damage_args.armor_applied = false; _take_damage_args.bypass_invincibility =
  true; ...; var lose_hp_per_second =
  RunData.get_player_effect(Keys.lose_hp_per_second_hash, player_index); var
  _dmg_taken = take_damage(lose_hp_per_second, _take_damage_args)` — flat,
  unarmored, undodgeable, i-frame-ignoring self-damage.
- Timer interval: `recovered/entities/units/player/player.tscn:1377`
  (`LoseHealthTimer` node) has no `wait_time` override, so it uses Godot's `Timer`
  engine default of **1.0 second** — consistent with the key's own name
  (`lose_hp_per_second`). This is an engine default, not something pinned in a
  `.tres`; flagging as `UNVERIFIED:` only in the sense that it relies on knowing
  Godot 3's `Timer.wait_time` default rather than an explicit project value, but the
  key's own name and the absence of any override strongly corroborate it.
- Net effect: Scythe T4 costs the holder **3 HP/second, continuously, for as long
  as it's equipped** (not gated on attacking). This is purely a survivability cost,
  paid against enemies as zero damage.

### Blank key `""` — Vorpal Sword T2-T4 (`OneShotOnHitEffect`)

`extracted/weapons/melee/vorpal_sword/{2,3,4}/vorpal_sword_{N}_effect_0.tres`:
script `res://effects/weapons/one_shot_on_hit_effect.gd`, `key = ""`, `value = 1 /
2 / 3` for T2/T3/T4 respectively (plus `sound_one_shot`, `particles_one_shot`
sub/ext-resources dropped by the builder's existing filter).

- `recovered/effects/weapons/one_shot_on_hit_effect.gd`:
  `class_name OneShotOnHitEffect extends NullEffect` — only exports
  `sound_one_shot`/`particles_one_shot`; no `key` is ever needed because dispatch
  is by **script class**, exactly the nuance the brief warns about.
- `recovered/weapons/weapon.gd:158`: `_hitbox.effects = effects` — the weapon's
  effects list (including this one) is attached to every hit's hitbox.
- `recovered/entities/units/unit/unit.gd:285-295` (inside `take_damage`):
  ```
  var is_one_shot = false
  if hitbox:
      for effect in hitbox.effects:
          ...
          elif effect is OneShotOnHitEffect:
              if Utils.get_chance_success(effect.value / 100.0):
                  is_one_shot = true
                  _on_one_shotted(effect)
              else: is_one_shot = false
  ```
  `effect.value / 100.0` is the **execute chance per hit** — 1% / 2% / 3% for
  T2/T3/T4.
- `unit.gd:303-305`: `var dmg_value_result = get_damage_value(...); if
  is_one_shot: dmg_value_result.value = max(current_stats.health,
  dmg_value_result.value)` — on success, the hit's damage is forced to at least
  the target's **current HP**, i.e. an unconditional kill regardless of Vorpal
  Sword's own (fairly low) damage roll.
- This is a real, currently 100%-invisible mechanic (Vorpal Sword's entire
  identity as an execute weapon is silently dropped by the builder today) — but
  the "damage" it deals is defined as *the target's current HP*, an unbounded,
  run-state-dependent quantity with no static representative value in
  `extracted/`.

### Blank key `""` — Screwdriver T1-T4 (`StructureEffect`, spawns Landmine)

`extracted/weapons/melee/screwdriver/{1,2,3,4}/screwdriver_{N}_effect.tres`:
script `res://effects/items/structure_effect.gd`, `key = ""`, `value = 1` (all
tiers — number of mines spawned per cooldown tick), `spawn_cooldown = 12 / 9 / 6 /
3` (T1-T4), `scene = res://entities/structures/landmine/landmine.tscn`, `stats =
res://items/all/landmines/landmine_stats.tres` (**same file for all four tiers**),
`effects = [res://items/all/landmines/landmine_exploding_effect.tres]`.

**Companion resources** (outside the weapon's own dir — not caught by a
`weapons/melee/screwdriver/*` glob at all, unlike the burn case):
- `extracted/items/all/landmines/landmine_stats.tres`: `RangedWeaponStats`,
  `cooldown = 2`, `damage = 10`, `scaling_stats = [["stat_engineering", 1.0]]`.
  **Identical across all four Screwdriver tiers** — tier only changes
  `spawn_cooldown` (mine spawn rate), never the mine's own damage.
- `extracted/items/all/landmines/landmine_exploding_effect.tres`: script
  `res://effects/items/item_exploding_effect.gd` (`ItemExplodingEffect extends
  ExplodingEffect`), `chance = 1.0`, `key = ""`, `text_key = ""` — this file has no
  `stats` field set at all (only the landmine entity's own `stats` — the
  `landmine_stats.tres` above — carries the damage the explosion actually deals;
  see `landmine.gd` below).

**Spawn cadence** (`recovered/global/entity_spawner.gd:531-556`,
`_on_StructureTimer_timeout`, engine-global structure timer):
```
var cur_time = (_wave_timer.wait_time - _wave_timer.time_left) as int   # whole seconds elapsed this wave
...
for struct in player_structures:
    var spawn_cd = WeaponService.apply_structure_attack_speed_effects(struct.spawn_cooldown, player_index)
    if (spawn_cd != -1 and cur_time % spawn_cd == 0) or not _base_structures_spawned:
        for _i in struct.value:
            ... queue a landmine spawn at a (semi-)random position ...
```
- `struct.spawn_cooldown` (12/9/6/3) is compared against **whole elapsed seconds**
  (`cur_time` is `int`), confirming these are literal seconds, unlike weapon
  `cooldown` fields (which are frame-based, divided by 60 elsewhere). At the
  zero-baseline `structure_attack_speed` stat,
  `recovered/singletons/weapon_service.gd:553-558`
  (`get_structure_attack_speed`) reads `Utils.get_stat(Keys.
  structure_attack_speed_hash, player_index)` which is 0 with no items, so
  `apply_structure_attack_speed_effects` (`weapon_service.gd:562-567`) returns
  `spawn_cooldown` unmodified.
- **No concurrency cap for landmines specifically**: `_restrict_turret_count`
  (`entity_spawner.gd:512-528`) only trims structures where
  `EntityService.is_considered_turret(structure)` is true
  (`recovered/singletons/entity_service.gd:78-82`: `structure_effect is
  TurretEffect and ...`). Screwdriver's effect is a plain `StructureEffect`, not a
  `TurretEffect`, so it is never subject to `max_turret_count`. Landmines simply
  accumulate over time, one batch of `struct.value` (=1) every `spawn_cd` seconds,
  with no cap other than the game's general entity limits (not investigated).

**Trigger + damage** (`recovered/entities/structures/landmine/landmine.gd`):
```
func _on_Area2D_body_entered(_body): ...  # arms (visual "pressed" sprite only)
func _on_Area2D_body_exited(_body): call_deferred("explode")
func explode():
    if dead or effects.size() <= 0: return
    var explosion_effect = effects[0]
    _explode_args_landmine.damage = stats.damage          # = 10 (landmine_stats.tres, all tiers)
    _explode_args_landmine.scaling_stats = stats.scaling_stats  # stat_engineering x1.0
    ...
    var _inst = WeaponService.explode(explosion_effect, _explode_args_landmine)
    die()   # mine is consumed, one-shot
```
- **The explosion triggers only when an enemy body *exits* the Area2D**, not on
  entry/contact — an enemy must step onto the mine, then step off it, for it to
  detonate. `UNVERIFIED:` whether an enemy that dies while standing on the mine
  (rather than walking off) reliably fires `body_exited` — this depends on Godot
  Area2D/physics-body-removal semantics not confirmed from the decompiled GDScript
  alone.
- `_explode_args_landmine` (a `WeaponServiceExplodeArgs`,
  `recovered/singletons/weapon_service_explode_args.gd:15`: `var ignored_objects:
  Array = []` by default) is **never given an `ignored_objects` override** in
  `landmine.gd:explode()` — unlike the weapon on-hit exploding effect
  (`weapon.gd:435`, which explicitly excludes the just-hit enemy). So a landmine's
  blast **can** hit the very enemy that triggered it, plus any others caught in
  the radius — different AoE semantics than the already-modeled exploding proc.
- Damage per detonation: `10 × (scaled by stat_engineering, 0 at baseline ⇒
  max(1, 10) per the same `apply_scaling_stats_to_damage`/`apply_damage_bonus`
  convention used for burn)`, **identical for all four Screwdriver tiers** — tier
  only buys faster mine production, not stronger mines.

### Blank key `""` — Pruner T1-T4 (`TurretEffect`, spawns Garden)

All four tiers (see census correction above) carry a blank-key `TurretEffect`
(`recovered/effects/items/turret_effect.gd`, extends `StructureEffect`) whose
scene is `res://entities/structures/turret/garden/garden.tscn` and whose `stats`
resolve to a **healing-only** `RangedWeaponStats`:

| tier | garden stats file | `cooldown` (frames) | `damage` | `is_healing` |
|---|---|---|---|---|
| 1 | `entities/structures/turret/garden/garden_stats.tres` (shared, not weapon dir) | 900 (=15s) | 0 | true |
| 2 | `weapons/melee/pruner/2/pruner_2_garden_stats.tres` | 840 (=14s) | 0 | true |
| 3 | `weapons/melee/pruner/3/pruner_3_garden_stats.tres` | 720 (=12s) | 0 | true |
| 4 | `weapons/melee/pruner/4/pruner_4_garden_stats.tres` | 600 (=10s) | 0 | true |

(Frame→second conversion by analogy with `TurretEffect.get_args`,
`turret_effect.gd:22-24`: `spawn_cd / 60.0` — the same 60fps convention used
elsewhere in this codebase, e.g. weapon `recoil_duration`.)

- `recovered/entities/structures/turret/garden/garden.gd`:
  ```
  class_name Garden extends Turret
  func shoot(): emit_signal("wanted_to_spawn_fruit", global_position)
  func should_shoot(): return _cooldown <= 0 and not _is_shooting
  ```
  The Garden structure's only action is periodically emitting a
  `wanted_to_spawn_fruit` signal (a `Structure` base signal,
  `recovered/entities/structures/structure.gd:4`) at its own cooldown — it never
  deals damage (`damage = 0` on every tier's stats, explicitly).
- `entity_service.gd:78-82` (`is_considered_turret`) excludes anything with
  `text_key == "effect_garden"` from turret classification, so Garden is also
  exempt from `max_turret_count` — but it is irrelevant here since it has no
  offensive role at all.
- This is unambiguously a **pure healing/utility support structure** ("plant a
  garden that periodically spawns healing fruit pickups"), with `damage = 0`
  explicitly confirmed on every tier — no DPS relevance whatsoever.

## Verdict

| key/weapon | verdict | rationale |
|---|---|---|
| `burning_spread` (Torch T3/T4) | **TENTATIVE**: Non-DPS rider vs. DPS-modelable-with-assumption | See discussion below. Leaning Non-DPS rider. |
| `consumable_heal` (Chopper) | **Non-DPS rider** | Passive, held, account-wide bonus to consumable healing (and consumable self-damage mitigation). Zero combat/DPS involvement. Propose: classify out of `unmodeled_effects` as a utility/economy stat grant; expose `value` as e.g. `consumable_heal_bonus` metadata rather than folding into any DPS line. |
| `lose_hp_per_second` (Scythe T4) | **Non-DPS rider** (drawback) | Confirmed flat, continuous, unmitigated self-damage (3 HP/s) while equipped — a survivability cost paid by the player, contributes nothing to enemy damage. Propose: surface as a drawback stat (e.g. `self_damage_per_second`) alongside Scythe's dps lines, not merged into them. |
| Vorpal Sword T2-T4 (blank key, `OneShotOnHitEffect`) | **Unmodelable-static** (with a strong recommendation to still surface it as metadata) | Damage-on-proc equals the target's *current HP* — an unbounded, run-state-dependent quantity impossible to give a static per-weapon expected-DPS number without inventing an enemy-HP distribution (exactly the kind of speculative math the brief prohibits). The *chance* (1%/2%/3%) is a clean, static number, though, and this weapon's entire "execute" identity is currently invisible — recommend the dataset at minimum expose `instakill_chance_per_hit` (or similar) as classification/UI metadata even though it stays out of the `proc_dps_*` totals. |
| Screwdriver T1-T4 (blank key, `StructureEffect`/Landmine) | **TENTATIVE**: Unmodelable-static vs. DPS-modelable-with-steady-state-assumption | See discussion below. Leaning Unmodelable-static given the enter-then-exit trigger condition is a spatial/AI-pathing dependency, not a timer or on-hit chance. |
| Pruner T1-T4 (blank key, `TurretEffect`/Garden) | **Non-DPS rider** | `damage = 0` explicitly on every tier's garden stats — confirmed zero DPS by the engine's own data, not an inference. It is a periodic healing-fruit spawner. Propose: classify as a utility/economy structure (e.g. surface `garden_fruit_interval_s` metadata), definitely remove from any future `unmodeled_effects`-driven "this weapon might have hidden damage" flagging since the zero is confirmed, not merely unknown. |

### Discussion: `burning_spread` TENTATIVE reasoning

**For Non-DPS rider**: the effect is applied at equip-time to a *global,
account-wide* player stat (`weapon_service.gd:334` reads it inside
`init_burning_data`, which every burning source shares — not scoped to Torch's own
attacks). It also composes with other sources (confirmed: the Snake item grants
the same `burning_spread` key, `recovered/items/all/snake/snake_effect_1.tres`),
so "how much spread does Torch grant" isn't even a well-defined per-weapon
question once a build has multiple sources — the per-weapon dataset schema has no
natural slot for a global, stacking, cross-weapon stat like this (the same shape
of problem as `explosion_damage`, already documented as an accepted known
limitation in `docs/proc-mechanics.md`).

**For DPS-modelable-with-assumption**: the existing exploding-effect model already
established the project's convention of assuming a fixed `default_enemies_hit`
(1.0, "assume one other enemy is caught") for a state-dependent AoE outcome. One
could similarly assume "the Torch's own burn always finds exactly one nearby
non-burning enemy to spread to," turning a Torch-with-burning-spread into
"2x the already-modeled `burn_dot` line" as an optimistic-but-precedented
approximation. This is weaker evidence than the exploding case, though: exploding
fires on *every qualifying hit* (bounded by `chance`), whereas spread additionally
requires an eligible body physically inside the `SpreadArea` at the moment
`_physics_process` polls it — a continuously-re-checked spatial condition with no
single trigger point to reason about the way "did this hit connect" works for
exploding.

Recording both candidates per the brief's TENTATIVE guidance rather than forcing
a choice.

### Discussion: Screwdriver landmine TENTATIVE reasoning

**For Unmodelable-static**: the trigger condition (`body_entered` then
`body_exited`) is a spatial/pathing dependency on enemy movement, not a timer or a
per-hit chance roll — nothing in `extracted/` bounds how often, or whether at all,
a given spawned mine ever gets stepped on and off. Mine damage also does not scale
with weapon tier at all (fixed `10`, only spawn rate changes), and mines
accumulate without bound over a wave's duration, making "expected DPS" a function
of wave length, enemy density, and enemy pathing AI — none of which the static
dataset models elsewhere.

**For DPS-modelable-with-steady-state-assumption**: by analogy with the burn
model's accepted "continuous attacking ⇒ effectively 100% uptime" steady-state
assumption, one could assume "every spawned mine eventually triggers exactly
once" and compute `dps ≈ (10 × stat_engineering scaling) / spawn_cd_seconds`
(effectively identical algebraic shape to `burn_dps_line`). Unlike burn's
precondition (`cycle_time <= duration × 0.5`, directly checkable against shipped
`.tres` values with no gameplay-behavior assumption), this "eventually triggers"
premise is not checkable against any static file — it is a claim about enemy AI
behavior over a wave, which is exactly the category of "speculative math" the
brief says is worse than no math.

Recording both candidates; leaning Unmodelable-static given the AI-pathing
dependency has no evidence trail in `extracted/` to verify against, but noting the
formula shape is a straightforward reuse of `calc.burn_dps_line` if the synthesis
phase decides the assumption is acceptable.

## Precondition verification table (N/A — no key here reached a clean DPS-modelable verdict)

Not applicable: no key in this family produced an unconditional DPS-modelable
verdict. See per-key TENTATIVE discussion above for the closest analogues
(Torch's `burning_spread`, Screwdriver's landmine) and their unmet preconditions.

## Open questions / UNVERIFIED items

- `UNVERIFIED:` Landmine's `_on_Area2D_body_exited` firing behavior when the
  triggering enemy dies while standing on the mine (rather than walking off) —
  could not confirm from GDScript alone whether Godot's `Area2D` reliably emits
  `body_exited` when a body is freed/removed vs. only on physical movement out of
  the shape.
- `UNVERIFIED:` `LoseHealthTimer`'s 1.0s tick interval relies on Godot 3's `Timer`
  default (no `wait_time` override found in `player.tscn`) rather than an explicit
  project value — very likely correct given the key's own name, but not pinned to
  an explicit numeric literal the way most other citations in this dossier are.
- Not investigated (out of this family's scope, flagged only for cross-reference):
  Scythe T4's second effect, `stat_percent_damage` with `custom_key =
  "temp_stats_on_hit"` — an on-hit stacking self-buff that belongs to the
  `stat_percent_damage` worklist entry, not this family.
- Re-ran the census grep precisely (anchored, to avoid `text_key = ""` false
  positives that an unanchored `key = ""` search picks up):
  `grep -rl '^key = ""$' extracted/weapons/` returns exactly 10 files — Vorpal
  Sword T2-T4 (3), Screwdriver T1-T4 (4), Pruner T2-T4 (3) — matching
  `docs/proc-mechanics.md`'s worklist count of 10 exactly. Pruner T1's blank-key
  file is *not* among these 10 because it lives outside `extracted/weapons/`
  entirely (`extracted/items/all/garden/garden_effect_1.tres`), so the original
  grep (scoped to `extracted/weapons/`) correctly wouldn't have counted it — this
  is a genuinely new, previously-uncounted instance of the same mechanic, not a
  discrepancy in the count of 10.
- Not investigated: whether any OTHER weapon besides Torch/Chopper/Scythe/Vorpal
  Sword/Screwdriver/Pruner ships a blank-key effect sourced from outside
  `extracted/weapons/` the way Pruner T1 does (i.e., a weapon `effects` array
  entry pointing at a shared `extracted/items/all/*` file) — this dossier only
  found Pruner T1's case incidentally while resolving its tier-upgrade chain, not
  via an exhaustive cross-directory search.
