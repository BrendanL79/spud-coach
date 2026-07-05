# Conditional / stacking buffs — proc-worklist investigation dossier
Date: 2026-07-05. Game version: 1.1.15.4 (extracted/). Investigator: subagent.

## Keys covered

| key | script (`recovered/effects/weapons/`) | weapon | tiers | param values |
|---|---|---|---|---|
| `effect_no_hit_boost` | `player_no_hit_effect.gd` (`PlayerNoHitEffect`) | Rail Gun (ranged) | T1–T4 | `value` = 3/4/5/6, `interval` = 5 (all tiers) |
| `effect_gain_stat_every_killed_enemies` | `gain_stat_every_killed_enemies_effect.gd` (`GainStatEveryKilledEnemiesEffect`) | Ghost Axe (melee) | T1–T4 | `value` (kill modulus) = 20/18/16/12, `stat` = `stat_percent_damage`, `stat_nb` = 1 |
| " | " | Ghost Flint (melee) | T1–T4 | `value` = 20/18/16/12, `stat` = `stat_attack_speed`, `stat_nb` = 1 |
| " | " | Ghost Scepter (ranged) | T1–T4 | `value` = 20/18/16/12, `stat` = `stat_max_hp`, `stat_nb` = 1 |
| `EFFECT_WEAPON_STACK` | `weapon_stack_effect.gd` (`WeaponStackEffect`) | Stick (melee) | T1–T4 | `value` = 4/6/8/10, `stat_name` = `"damage"`, `weapon_stacked_id` = `"weapon_stick"` (self-referential, all tiers) |

Census re-verified via `grep -rl "<key>" extracted/weapons/` — matches the brief's fresh census exactly (4+12+4 = 20 `.tres` files across 5 weapons, 4 tiers each). No untiered/root-dir files for any of the three keys — all five weapons have a full `1/2/3/4` tier layout.

No companion resource files (no `*_burning_data.tres`-style side files) in any of the five weapon directories — each ships only the standard `*_stats.tres` / `*_data.tres` / `*_effect*.tres` trio per tier, confirmed by listing `extracted/weapons/{melee,ranged}/{stick,rail_gun,ghost_axe,ghost_flint,ghost_scepter}/**`. The Stick effect file additionally references a `SubResource` of type `CustomArg` (`recovered/items/global/custom_arg.gd`), but that is inherited from the base `Effect` class purely for tooltip-text formatting (`recovered/items/global/effect.gd:23-27,124-128`) — not consumed by any gameplay code path (verified: `grep -rn custom_args recovered/ --include=*.gd` shows only tooltip/description sites, none in `weapon.gd`/`weapon_service.gd`).

All three effect classes extend `NullEffect` (`recovered/effects/weapons/null_effect.gd:1-14`), whose `apply()`/`unapply()` are no-ops (`null_effect.gd:9-14`) — same pattern as `BurningEffect`/`ExplodingEffect`. Gameplay is dispatched by **script class**, not by the `.tres` `key` string, confirmed for all three (their `static func get_id()` strings — `"effect_no_hit_boost"`, `"weapon_gain_stat_every_killed_enemies"`, `"weapon_stack"` — don't even match the `.tres` `key` fields for two of the three; irrelevant either way since dispatch never reads `key`).

## Mechanic (evidence)

### `effect_no_hit_boost` (Rail Gun) — time-without-being-hit damage ramp

Rail Gun has its own weapon subclass, `recovered/weapons/ranged/rail_gun/railgun.gd` (`class_name RailGun extends RangedWeapon`), which is what actually reads `PlayerNoHitEffect`:

- `railgun.gd:6-8`: `onready var _one_second_timer: Timer = $OneSecondTimer`, `var _one_second_timeouts := 0`.
- `railgun.gd:82-99` (`_on_OneSecondTimer_timeout`): every 1 real second, `_one_second_timeouts += 1`. Then for the weapon's `PlayerNoHitEffect`: `if _one_second_timeouts % interval == 0: interval_count = _one_second_timeouts / interval; bonus_damage = value * interval_count; init_stats(false)`. With `interval = 5` (all tiers), this fires every 5s, each time incrementing `interval_count` by 1 and setting `bonus_damage = value * interval_count` — i.e. **`bonus_damage` grows by a flat `value` every 5 uninterrupted seconds, unbounded** (no cap or ceiling in this function).
- `railgun.gd:39` (`init_stats`): `duplicated_stats.damage = base_damage + bonus_damage` — the accumulated bonus is added directly to the weapon's own base damage, then run through the normal `WeaponService.init_ranged_stats` pipeline (same RD-scaling + `percent_dmg_bonus` multiply as every other ranged weapon — see `weapon_service.gd:237,249` below).
- `railgun.gd:69-80` (`_player_took_damage`, connected to the player's `took_damage` signal in `_ready` at line 20): `if _is_protected or _is_dodge: return` — otherwise **any landed, non-dodged, non-armor-protected hit on the player resets `_one_second_timeouts = 0`, `bonus_damage = 0`, `interval_count = 0`** and calls `init_stats(false)` again, dropping the weapon's damage back to baseline.
- No cap or ceiling on `bonus_damage`/`interval_count` was found anywhere in `railgun.gd` or its callers.

Net mechanic: Rail Gun's damage climbs by a flat amount every 5 seconds the player goes without taking a landed hit, and fully resets to zero bonus the instant the player is hit (dodge/armor-block doesn't count as a hit for this purpose). This is a pure function of **elapsed wall-clock time since the player's last landed hit**, which is itself a function of enemy density/aggression, player positioning/dodge/armor stats, and wave duration — none of which the static dataset has any handle on. There is no steady-state to compute an "expected uptime" the way burn's cycle_time-vs-duration check does, because the state that resets it (getting hit) is not attached to this weapon's own attack cycle at all — it's attached to enemies hitting the *player*, a completely independent, unbounded-variance process.

### `effect_gain_stat_every_killed_enemies` (Ghost Axe/Flint/Scepter) — per-weapon kill-count stat ratchet

Consumed directly in the generic weapon hit/kill handler, not a per-weapon subclass:

- `recovered/weapons/weapon.gd:57`: `var _enemies_killed_this_wave_count := 0` — a per-**weapon-instance** counter (each equipped copy of a weapon tracks its own count).
- `weapon.gd:211-232` (`on_killed_something`, called whenever this weapon instance's hit kills something): `_enemies_killed_this_wave_count += 1`; then `for effect in effects: if effect is GainStatEveryKilledEnemiesEffect and _enemies_killed_this_wave_count % effect.value == 0: RunData.add_stat(effect.stat_hash, effect.stat_nb, player_index)`. So every `value`-th kill scored **by this specific weapon**, the player permanently gains `stat_nb` (always `1` for all three weapons/tiers surveyed) of the named stat (`stat_percent_damage` for Ghost Axe, `stat_attack_speed` for Ghost Flint, `stat_max_hp` for Ghost Scepter).
- `run_data.gd:1478-1484` (`add_stat`): `effects[stat_hsh] += value` — a plain, uncapped, permanent additive accumulation into the player's stat pool (no clamp in this function).
- UNVERIFIED: despite the variable's name, no reset of `_enemies_killed_this_wave_count` to 0 at wave boundaries was found anywhere in `recovered/` (`grep -rn "_enemies_killed_this_wave_count" recovered/` returns only the declaration at `weapon.gd:57` and the two uses at `weapon.gd:227,229` — no assignment back to 0). It's plausible wave-start re-triggers `add_weapon` (which instantiates a fresh weapon scene, `entities/units/player/player.gd:371-388`, naturally zeroing the counter) for every equipped weapon each wave, but I did not find the call site that would prove this, and the shop/wave-transition code that would confirm or refute it is outside this family's scope to fully trace. Either way — whether the counter resets every wave or accumulates for the whole run — the number of kills a specific weapon has scored is unbounded, monotonically increasing, and entirely a function of *how the run has gone so far* (spawn density, wave count survived, whether the player is even using that weapon to land killing blows vs. other weapons/explosions finishing enemies off). A near-identical Builder-only variant of this same check exists at `recovered/entities/structures/turret/builder_turret.gd:39,310-312` (not relevant to this dataset's weapon-record model, noted only because it shares the exact per-instance-kill-count pattern).

Net mechanic: this is a per-weapon, kill-count-gated, permanent player-stat ratchet with no cap and no way to know in advance how many kills that weapon will score in a given run.

### `EFFECT_WEAPON_STACK` (Stick) — per-copy-owned flat damage stacking

Consumed in the shared ranged/melee stat-init pipeline, dispatched by class:

- `recovered/singletons/weapon_service.gd:192-197`: `elif effect is WeaponStackEffect: var nb_same_weapon = 0; for checked_weapon in RunData.get_player_weapons_ref(player_index): if checked_weapon.weapon_id_hash == effect.weapon_stacked_id_hash: nb_same_weapon += 1; new_stats.set(effect.stat_name, new_stats.get(effect.stat_name) + (effect.value * max(0.0, nb_same_weapon - 1)))`.
  - `nb_same_weapon` counts **every currently-equipped weapon slot** whose `weapon_id` is `"weapon_stick"` — across **all tiers** (the check is on `weapon_id_hash`, not tier), including the Stick instance being evaluated itself.
  - The bonus is `value * max(0, N-1)`, i.e. **zero extra flat damage for the first copy owned, then +`value` per additional copy** (T1=4, T2=6, T3=8, T4=10 per the owning instance's own tier — a mixed-tier stack of e.g. one T1 + one T3 Stick gives the T1 instance `+4` and the T3 instance `+8`, each computed from `N=2`).
  - `effect.stat_name = "damage"` for all four tiers (`extracted/weapons/melee/stick/{1,2,3,4}/stick*_effect_1.tres`) — the bonus is added directly to that Stick instance's own `WeaponStats.damage` field.
- Confirmed this addition lands in the *same place* the dataset's existing `dps_line` base-damage term does, and **before** RD-scaling and the flat percent-damage multiplier are applied, i.e. it behaves exactly like additional base weapon damage:
  - `weapon_service.gd:237`: `new_stats.damage = apply_scaling_stats_to_damage(new_stats.damage, new_stats.scaling_stats, player_index)`, where `apply_scaling_stats_to_damage` (`weapon_service.gd:489-490`) is `max(1, damage + sum_scaling_stat_values(...))` — **additive**, not a multiply on `damage`, so the RD-scaling contribution is independent of the stack bonus's magnitude.
  - `weapon_service.gd:249`: `new_stats.damage = max(1, round(new_stats.damage * (set_bonus_dmg + percent_dmg_bonus + exploding_dmg_bonus)))` — the *entire* running sum (base + stack bonus + RD contribution) gets multiplied by `(1 + stat_percent_damage/100)` at the end. At this dataset's zero-baseline convention (`stat_percent_damage = 0`), `percent_dmg_bonus = 1`, so this multiply is a no-op at baseline — consistent with how the rest of the dataset's `dps0` already assumes zero accumulated player stats.
  - Net: the stack bonus is a pure additive term to the intercept (`dps0`), contributing **zero slope** (it doesn't scale with RD at all — `sum_scaling_stat_values` doesn't take `damage` as an input, so the stack bonus and the RD contribution are fully independent additive terms).
- Owning multiple Sticks without merging them is a real, intended game state, not an edge case: `recovered/ui/menus/shop/base_shop.gd:607-620` (`buy_weapon`) only force-merges a duplicate purchase into the existing weapon (`_combine_weapon`) when `not RunData.has_weapon_slot_available(...)` (i.e., no free slot) — with an open slot, buying a second Stick adds a **separate, independent instance** (`RunData.add_weapon`, `base_shop.gd:620`), and both count toward `nb_same_weapon`. `RunData.has_weapon_slot_available` (`run_data.gd:1340-1357`) gates on `Keys.weapon_slot_hash`, itself a player stat (base value not verified in this investigation, UNVERIFIED — commonly known as 6 but not re-derived from `recovered/` here since it's not needed for the formula's correctness, only for its practical N-range).

Net mechanic: this is a clean, build-composition-dependent (not time/RNG-dependent) flat damage bonus, structurally identical to how the dataset already treats `base_damage` — the only "new" input is `N` (copies of `weapon_stick` currently equipped, any tier), which the player chooses at shop time and which stays fixed for the rest of that state (until sold/merged), the same way RD is chosen at build time and stays fixed as an axis in `dps_slope_per_rd`.

## Verdict

- **`effect_no_hit_boost` (Rail Gun) → Unmodelable-static.** The bonus is a monotonic function of uninterrupted wall-clock survival time since the player's last landed (non-dodged, non-armor-blocked) hit, uncapped, and reset by an event (being hit) that has no relationship to this weapon's own attack cycle. There is no steady-state/duty-cycle argument available the way burn's `cycle_time ≤ duration×tick` check works, because what resets it isn't attached to the weapon at all. The dataset's existing floor (0 unmodeled contribution) is exactly the guaranteed value at t=0 or immediately after any hit, so leaving it unmodeled is already the honest floor — not a compromise.
- **`effect_gain_stat_every_killed_enemies` (Ghost Axe/Flint/Scepter) → Unmodelable-static.** Matches the brief's own canonical example ("scales with kills this wave") almost exactly — here it's kills scored specifically by that weapon instance, uncapped, permanently added to a player stat via `RunData.add_stat`. No static number is defensible: 0 kills → 0 bonus is the correct floor, and any nonzero number would require assuming a kill count the dataset cannot know. This is also arguably a "Non-DPS rider" in the sense that it grants a *player stat* rather than re-dealing weapon damage — but unlike a fixed passive grant, the value it grants has no ceiling and no fixed trigger condition (kills-per-run is not a build parameter), so a Phase 2 schema tag ("kill-gated player-stat ratchet, no static value") could still classify it out of a generic `unmodeled_effects` bucket even though no number is ever attached. Flagging this nuance rather than picking silently.
- **`EFFECT_WEAPON_STACK` (Stick) → DPS-modelable, but requires a new build-composition axis the schema doesn't have today.** The formula is fully derived and verified from `recovered/`:
  - `stack_dps0(N) = value_tier * max(0, N-1) / cycle_time_tier * accuracy_tier` (added to the weapon's existing `dps_at_zero_rd`)
  - `stack_slope = 0` (independent of RD, proven via `apply_scaling_stats_to_damage`'s additive-not-multiplicative structure, see evidence above)
  - where `N` = total number of currently-equipped `weapon_stick` copies (any tier), and `value_tier`/`cycle_time_tier`/`accuracy_tier` are the evaluating instance's own tier's values.
  - Example (T1: `damage=8`, `cooldown=42`, `recoil_duration=0.1`, `accuracy=1.0` → `cycle_time = 0.1*2 + 42/60 = 0.9s`): at `N=3` owned, `stack_dps0 = 4*(3-1)/0.9*1.0 ≈ 8.9` added on top of the base `8/0.9 ≈ 8.9` — i.e. a T1 Stick's DPS roughly **doubles** at 3 copies owned, before any RD.
  - Why this doesn't slot into today's per-weapon-tier `(dps_at_zero_rd, dps_slope_per_rd)` two-number model: `N` (copies owned) is not RD and not a per-tier constant — it's a *loadout composition* choice, exactly analogous to how RD is a build-time free variable, but the dataset has no second free-variable axis today (every other proc/model in `procs.py` only ever varies with RD or is a flat constant). Modeling this honestly requires either (a) a new dataset field alongside `dps_at_zero_rd`/`dps_slope_per_rd` — e.g. `dps_slope_per_stick_copy` — with the query layer accepting an `N` parameter the same way it accepts RD, or (b) deferring this to answer-time logic in `answers.py`/`query.py` that knows the caller's full loadout composition (which the dataset builder does not have visibility into — it builds one weapon record at a time, not a hypothetical loadout). Either path is a Phase 2 schema decision; the math itself is fully verified and not in question.

## Precondition verification table (Stick only — the DPS-modelable key)

| weapon/tier | `stat_name` targets `damage`? | additive-before-RD-scaling confirmed? | `weapon_stacked_id` self-referential (`"weapon_stick"`)? | value |
|---|---|---|---|---|
| Stick T1 | yes (`stick_effect_1.tres:26`) | yes (`weapon_service.gd:197,237,249`) | yes (`stick_effect_1.tres:23-24`) | 4 |
| Stick T2 | yes (`stick_2_effect_1.tres:26`) | yes | yes | 6 |
| Stick T3 | yes (`stick_3_effect_1.tres:26`) | yes | yes | 8 |
| Stick T4 | yes (`stick_4_effect_1.tres:26`) | yes | yes | 10 |

All four tiers pass identically — this is a single shared mechanic with only `value` varying by tier, not a case where some tiers need a fallback.

No precondition table for `effect_no_hit_boost`/`effect_gain_stat_every_killed_enemies` since both are Unmodelable-static (no formula to gate).

## Open questions / UNVERIFIED items

- UNVERIFIED: whether `_enemies_killed_this_wave_count` (`weapon.gd:57`) resets at wave boundaries or accumulates for the whole run. Does not change the verdict either way (both are unbounded/unknowable at build time), but would matter if a future synthesis phase wants to bound the *maximum* plausible value for documentation purposes.
- UNVERIFIED: the base value of `Keys.weapon_slot_hash` (commonly known as 6 slots, not re-derived from `recovered/` in this investigation) — only relevant to bounding the practical range of `N` for Stick's formula, not to the formula's correctness.
- UNVERIFIED: whether Rail Gun's `_one_second_timer` keeps running (and thus `bonus_damage` keeps accumulating) during any game-paused states (e.g. shop phase) — doesn't change the verdict (still unbounded/hit-reset-dependent during combat either way) but would matter if someone later tried to argue for a "typical wave-start value."
- The Ghost-weapon family is fully homogeneous in mechanic (all three weapons share one script and one dispatch site) but each targets a **different** player stat (`stat_percent_damage` / `stat_attack_speed` / `stat_max_hp`) — worth calling out explicitly since a future reader skimming just the key name might assume they all grant the same stat type.
