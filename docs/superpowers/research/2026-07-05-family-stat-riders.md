# Stat riders — proc-worklist investigation dossier
Date: 2026-07-05. Game version: 1.1.15.4 (extracted/). Investigator: subagent.

## Keys covered

Full census (`grep -rl 'key = "<key>"' extracted/weapons/`) — confirms the brief's
list is complete, no additional shipped users found:

| key | weapon/tier | value | script attached | notes |
|---|---|---|---|---|
| `stat_speed` | jousting_lance 1/2/3/4 | 2/3/4/5 | `items/global/effect.gd` (plain), `storage_method=0` (SUM) | flat, permanent while held |
| `stat_percent_damage` | jousting_lance 1/2/3/4 | -10/-15/-20/-25 | plain `effect.gd`, `storage_method=1` (KEY_VALUE), `custom_key="temp_stats_while_not_moving"` | **conditional** — see Mechanic |
| `stat_percent_damage` | scythe 4 | 3 | plain `effect.gd`, `storage_method=1` (KEY_VALUE), `custom_key="temp_stats_on_hit"` | **conditional/reactive**, unrelated mechanic to jousting_lance's — see Mechanic |
| `stat_armor` | rock 2 | 1 | plain `effect.gd`, `storage_method=0` (SUM) | flat, permanent while held |
| `stat_armor` | rock 3 | 1 | plain `effect.gd`, `storage_method=0` (SUM) | flat, permanent while held |
| `stat_armor` | rock 4 | 2 | plain `effect.gd`, `storage_method=0` (SUM) | flat, permanent while held |
| `stat_armor` | excalibur 4 | -2 | plain `effect.gd`, `storage_method=1` (KEY_VALUE), `custom_key="additional_weapon_effects"` | **conditional** — see Mechanic |
| `stat_max_hp` | rock 3 | 2 | plain `effect.gd`, `storage_method=0` (SUM) | flat, permanent while held |
| `stat_max_hp` | rock 4 | 2 | plain `effect.gd`, `storage_method=0` (SUM) | flat, permanent while held |
| `stat_harvesting` | hand 1/2/3/4 | 3/6/12/25 | plain `effect.gd`, `storage_method=0` (SUM) | flat, permanent while held; economy passthrough (see `docs/stat-mechanics.md`'s existing `stat_harvesting` entry for payout mechanics) |
| `stat_lifesteal` | sharp_tooth 1/2/3/4 | 1 (all tiers) | `effects/items/gain_stat_for_every_stat_effect.gd`, `nb_stat_scaled=25/20/15/10`, `stat_scaled="percent_player_missing_health"` | **dynamic** — see Mechanic; the `.tres` `value=1` field is NOT the granted lifesteal amount |
| `stat_attack_speed` | drill 4 | 10 | `effects/items/temp_stats_per_interval_effect.gd`, `interval=5`, `reset_on_hit=false` | **unbounded time-accumulating** — see Mechanic |
| `xp_gain` | fighting_stick 1/2/3/4 | 2/5/9/15 | plain `effect.gd`, `storage_method=0` (SUM) | flat, permanent while held; economy passthrough |
| `knockback` | hammer 2/3/4 | 2/4/6 | plain `effect.gd`, `storage_method=0` (SUM) | flat, permanent while held; **player-wide** stat (applies to knockback of every weapon the player has, not just Hammer) — see Mechanic |

Adjacent effects seen in the same weapon dirs, NOT in our assigned key list (out
of scope, flagged for whichever family owns them): drill T4's `gold_on_crit_kill`
(`effects/weapons/null_effect.gd`); scythe T4's `lose_hp_per_second`
(plain `effect.gd`, flat HP drain, `storage_method=0`).

No companion resources (à la burn's `burning_data`) exist for any effect in this
family — every `.tres` above is fully self-contained (all fields are scalars or
the one `custom_args` sub-resource on excalibur's effect, which is text-display
only, see below). No other auxiliary `.tres` files beyond
`*_stats.tres`/`*_data.tres`/effect files were found in these weapon dirs.

## Mechanic (evidence)

### Common apply/unapply lifecycle for plain `effect.gd` (base class)

- `recovered/items/global/effect.gd:19`: `export(StorageMethod) var storage_method
  = StorageMethod.SUM` — default is plain SUM (add `value` directly to the
  player's `effects[key_hash]` dict entry). Enum at line 5: `{SUM, KEY_VALUE,
  REPLACE, APPEND_KEY, APPEND_KEY_VALUE}`.
- `recovered/items/global/effect.gd:62-83` (`apply`): for `storage_method ==
  SUM` (the `else` branch, line 81-82): `effects[key_hash] += value`. For
  `KEY_VALUE` (line 66-72): pushes/merges `[key_hash, value]` into
  `effects[custom_key_hash]` — a **named bucket list**, not the player's own
  stat directly. What happens to that bucket is entirely up to whatever
  consumer reads that specific `custom_key` (see per-key sections below) — the
  base `Effect` class does not itself turn a KEY_VALUE entry into a stat
  change.
- `recovered/singletons/run_data.gd:982-1004` (`add_weapon`) calls
  `apply_item_effects(new_weapon, player_index)` (line 989) on pickup/equip;
  `recovered/singletons/run_data.gd:1244-1256` (`apply_item_effects`) calls
  `effect.apply(player_index)` per weapon effect.
- `recovered/singletons/run_data.gd:1058-1085` (`remove_weapon_by_index` /
  `remove_weapon` / `after_weapon_removed`) calls `unapply_item_effects` (line
  1081), which calls `effect.unapply(player_index)`
  (`recovered/singletons/run_data.gd:1281-1284`) per weapon effect on
  sell/unequip/replace.
- Conclusion: for **plain SUM** effects, the player-stat grant/removal is tied
  exactly to holding the weapon — this confirms `stat_speed`, `stat_armor`
  (rock only), `stat_max_hp`, `stat_harvesting`, `xp_gain`, and `knockback`
  (hammer) are genuine flat while-held riders, no further nuance.

### `stat_percent_damage` — jousting_lance: conditional on standing still, NOT a flat rider

- `extracted/weapons/melee/jousting_lance/{1,2,3,4}/*_effect_2.tres`: `key =
  "stat_percent_damage"`, `custom_key = "temp_stats_while_not_moving"`,
  `storage_method = 1` (KEY_VALUE), `value = -10/-15/-20/-25`.
- `recovered/singletons/keys.gd:273`: `var
  temp_stats_while_not_moving_hash: = generate_hash("temp_stats_while_not_moving")`
  — confirms this custom_key is a recognized dedicated bucket, not an
  arbitrary string.
- `recovered/entities/units/player/player.gd:215-239`
  (`check_not_moving_stats`): reads the `temp_stats_while_not_moving` bucket
  (line 218) and only when the player **transitions to standing still**
  (`movement.x == 0 and movement.y == 0`, line 219) does it call
  `TempStats.add_stat(temp_stat[0], temp_stat[1], player_index)` for each
  bucket entry (line 227) — i.e. only THEN does the -10%/-15%/-20%/-25%
  damage penalty actually land on the player's `stat_percent_damage`. When the
  player starts moving again (line 230, `movement.x != 0 or movement.y !=
  0`), it calls `TempStats.remove_stat(...)` (line 238), reversing it.
- Conclusion: this is a **movement-gated debuff**, not a permanent stat. The
  weapon's damage output is the *base* line while moving/attacking-in-motion,
  and drops by 10-25% only while the player is standing completely still.
  This directly contradicts treating it as a flat "held weapon → stat" rider.

### `stat_percent_damage` — scythe T4: reactive buff on the PLAYER taking a hit (not on the weapon hitting an enemy)

- `extracted/weapons/melee/scythe/4/scythe_effect_2.tres`: `key =
  "stat_percent_damage"`, `text_key = "effect_on_hit"`, `custom_key =
  "temp_stats_on_hit"`, `storage_method = 1` (KEY_VALUE), `value = 3`.
- `recovered/singletons/keys.gd:279`: `var temp_stats_on_hit_hash: =
  generate_hash("temp_stats_on_hit")`.
- `recovered/entities/units/player/player.gd:412` (`func take_damage`) is the
  **player's own take-damage handler** (triggered when an enemy hits the
  player) — confirmed by its signature and the surrounding dodge/heal-on-dodge
  code (lines 442-466) which only makes sense for the player being hit.
  Inside it, at `player.gd:493-495`: `var temp_stats_on_hit_effect =
  RunData.get_player_effect(Keys.temp_stats_on_hit_hash, player_index); for
  temp_stat_on_hit in temp_stats_on_hit_effect: TempStats.add_stat(...)`. So
  "on hit" here means **the player getting hit by an enemy**, not the
  weapon landing a hit on an enemy.
- UNVERIFIED: I found no code path that ever calls `TempStats.remove_stat` for
  this specific `temp_stats_on_hit_hash` bucket (the nearby
  `_remove_temp_stats_on_hit` dict at `player.gd:500-503` is populated only by
  the *unrelated* `temp_stats_per_interval_effect.gd`'s `reset_on_hit` flag —
  see drill's `stat_attack_speed` below — not by this bucket). If that's
  accurate, each hit the player takes appears to permanently stack +3%
  damage for the rest of the run with no decay; I did not find or rule out a
  wave-transition reset. Flagging as `UNVERIFIED` rather than asserting
  either "permanent" or "resets."
- Conclusion either way: this is a **reactive, stacking, player-survivability-triggered**
  effect completely orthogonal to the weapon's own attack cycle — not a
  static "held weapon → stat" rider, and not something a per-weapon DPS
  formula (which has no notion of "hits the player has taken this run") can
  honestly represent.

### `stat_armor` — excalibur T4: scales with the player's total weapon count, not flat

- `extracted/weapons/melee/excalibur/4/excalibur_effect_1.tres`: `key =
  "stat_armor"`, `custom_key = "additional_weapon_effects"`, `storage_method =
  1` (KEY_VALUE), `value = -2`. Also carries one `custom_args` sub-resource
  (`arg_index=2, arg_sign=4 [FROM_ARG], arg_value=4, arg_format=0`) — this is
  purely a display-text/color argument (`Effect.get_text`/`get_arg_value` in
  `recovered/items/global/effect.gd:116-229`), not part of the gameplay
  math; noted for completeness but not modeled.
- `recovered/singletons/keys.gd:377`: `var additional_weapon_effects_hash: =
  generate_hash("additional_weapon_effects")`.
- `recovered/singletons/run_data.gd:1190-1203`
  (`update_additional_weapon_bonuses`): first reverses last cycle's grant
  (lines 1192-1196), then **for every weapon the player currently owns**
  (`for weapon in weapons:`, line 1198) it re-applies **all** entries in the
  `additional_weapon_effects` bucket (line 1200-1203): `effects[effect[0]] +=
  effect[1]`. So Excalibur's `-2 stat_armor` is applied **once per weapon
  slot filled**, not once for holding Excalibur itself.
- `recovered/singletons/run_data.gd:1162-1167`
  (`update_item_related_effects`) calls `update_additional_weapon_bonuses`
  (line 1164); this in turn is called from `add_weapon`/`after_weapon_removed`
  (lines 991/1083), so the total penalty is recomputed live as weapons are
  added/removed.
- Conclusion: total armor penalty = `-2 * (number of weapons owned)` while
  Excalibur T4 is held — build-size-dependent, not a fixed number. A 6-weapon
  loadout takes -12 armor; a 1-weapon (Excalibur-only) loadout takes -2.

### `stat_lifesteal` — sharp_tooth: dynamically scales with current missing HP%, not the `.tres` `value` field

- `extracted/weapons/melee/sharp_tooth/{1,2,3,4}/*_effect_0.tres`: script
  `effects/items/gain_stat_for_every_stat_effect.gd` (a `GainStatForEveryStatEffect`
  subclass of `Effect`, NOT the plain base script) — `key="stat_lifesteal"`,
  `value=1` (all tiers), `stat_scaled="percent_player_missing_health"`,
  `nb_stat_scaled=25/20/15/10` (T1→T4), `perm_stats_only=false`.
- `recovered/effects/items/gain_stat_for_every_stat_effect.gd:20-22`
  (`apply`): does NOT touch the player's stat directly — it registers a
  **stat link** tuple: `effects[Keys.stat_links_hash].push_back([key_hash,
  value, stat_scaled_hash, nb_stat_scaled, perm_stats_only])`.
- `recovered/singletons/linked_stats.gd:1-70` (`LinkedStats`, extends
  `TempStats`): `reset_player` (called on every stat recompute — e.g.
  `Utils.reset_stat_cache`, item add/remove) walks `stat_links_hash` entries;
  for `stat_scaled == percent_player_missing_health_hash` (line 49-53):
  `actual_nb_scaled = WeaponService.apply_inverted_health_bonus(1, 1,
  current_health, max_health)`, and flags
  `update_for_player_every_half_sec[player_index] = true` — i.e. this
  specific link is recomputed **every half second** (live), not just on
  equip.
- `recovered/singletons/weapon_service.gd:504-508`
  (`apply_inverted_health_bonus`): `percent_missing_health = max(0.0, 1.0 -
  current_health/max_health) * 100.0`; returns `round(value *
  (percent_missing_health / per_health_percent_amount))` — with `value=1,
  per_health_percent_amount=1` from the linked-stats call, this yields
  `percent_missing_health` itself (0-100).
- `recovered/singletons/run_data.gd:1972-2009` (`get_scaling_bonus`, the
  non-cached path used elsewhere for display text) confirms the same formula
  shape: `return int(value * (actual_nb_scaled / nb_stat_scaled))` — i.e. the
  final lifesteal grant = `value * percent_missing_health / nb_stat_scaled`.
  At T1 (`nb_stat_scaled=25`): `1 * percent_missing_health / 25` → +1
  lifesteal per 25% HP missing, capping at +4 near 0 HP. At T4
  (`nb_stat_scaled=10`): +1 per 10% missing, up to +10 near-death.
- Conclusion: **at full HP the grant is exactly 0**; it scales up only as the
  player takes damage, live, every half second. The `.tres` `value=1` is a
  per-unit multiplier in this formula, not the actual lifesteal amount — a
  builder that naively read `value` as "lifesteal granted" would be wrong at
  every tier. This is consistent with `docs/stat-mechanics.md`'s note that
  lifesteal is survivability rather than DPS, but the mechanism itself is
  fully dynamic/current-HP-dependent, reinforcing that no single static
  number is honest here.

### `stat_attack_speed` — drill T4: unbounded, time-accumulating (not a flat hold-time rider)

- `extracted/weapons/melee/drill/4/drill_effect_2.tres`: script
  `effects/items/temp_stats_per_interval_effect.gd` (a
  `TempStatsPerIntervalEffect` subclass, NOT the plain base script) —
  `key="stat_attack_speed"`, `value=10`, `custom_key="temp_stats_per_interval"`,
  `storage_method=1` (KEY_VALUE), `interval=5`, `reset_on_hit=false`.
- `recovered/effects/items/temp_stats_per_interval_effect.gd:12-18`
  (`apply`): registers `[key_hash, value, interval, reset_on_hit]` into the
  `temp_stats_per_interval` bucket (merging with an existing identical
  `(key,interval,reset_on_hit)` tuple by summing `value` if the weapon is
  merged/duplicated).
- `recovered/entities/units/player/player.gd:1084-1102`
  (`_on_OneSecondTimer_timeout`): every real-time second, increments
  `_one_second_timeouts`; for each registered bucket entry, `if
  _one_second_timeouts % interval == 0: TempStats.add_stat(stat_key, value,
  player_index)` (line 1095-1096) — so every 5 seconds (drill's `interval`),
  the player gains **another** +10 `stat_attack_speed`, unconditionally,
  forever, for as long as Drill T4 is held. Because `reset_on_hit=false`,
  the `if reset_on_hit == true:` branch (lines 1098-1102, which would
  schedule a later removal via `_remove_temp_stats_on_hit`) never fires for
  this weapon — nothing ever removes these increments except unequipping
  Drill (which only stops future ticks; already-granted `TempStats` values
  are not retroactively reversed by the base `KEY_VALUE` `unapply`, which
  only removes drill's own *registration* from the interval bucket, not the
  accumulated `TempStats.add_stat` calls already fired).
- Conclusion: this is **wall-clock-time-accumulating and unbounded** — the
  longer a wave (or a run held with Drill T4 equipped) runs, the larger the
  attack-speed bonus grows, with no ceiling evidenced in this code path. A
  static per-weapon number cannot honestly represent "keeps growing every 5
  seconds for as long as combat continues" — this is exactly the
  state-dependent case `docs/proc-mechanics.md`'s `Unmodelable-static`
  category exists for (analogous to "scales with kills this wave").

### `knockback` — hammer: confirmed genuine player-wide stat, not the weapon's own knockback field

- `extracted/weapons/melee/hammer/{2,3,4}/*_effect_0.tres`: `key =
  "knockback"`, `text_key = "effect_knockback"`, `storage_method = 0` (SUM),
  values 2/4/6 — plain flat player-stat SUM effect (per the common
  apply/unapply lifecycle above).
- `recovered/singletons/keys.gd:224`: `var knockback_hash: =
  generate_hash("knockback")` — distinct from a weapon's own `knockback`
  stats-field (already captured elsewhere in the dataset as
  `base_knockback`, from `*_stats.tres`'s `knockback` field, via
  `brotato_coach/builders/weapons.py:107`).
  `recovered/weapons/weapon_stats/weapon_stats.gd:222` shows `knockback` is
  also a genuine field name on `WeaponStats` — same string, different scope
  (per-weapon design stat vs. player-wide accumulated stat); this is exactly
  the ambiguity the brief flagged.
- `recovered/singletons/weapon_service.gd:263-275` (weapon stat computation,
  the function that turns `WeaponStats` design values into a player's live
  weapon stats): `var player_knockback = RunData.get_player_effect(
  Keys.knockback_hash, player_index)` (line 265); then `new_stats.knockback =
  clamp(new_stats.knockback + player_knockback, min_knockback,
  max_knockback)` (line 270) — the player's accumulated `knockback` stat is
  added to **every weapon's own knockback value**, clamped by that weapon's
  `can_have_negative_knockback`/`can_have_positive_knockback` flags (already
  captured in the dataset).
- Conclusion: Hammer's `knockback` effect is confirmed to be the **player
  stat**, applied to the knockback of the player's entire loadout (not just
  Hammer itself), while Hammer is held. It is pure crowd-control utility —
  zero interaction with damage/DPS math.

## Verdict

**One consistent classification is not possible for this family as originally
scoped** — the census correctly grouped these keys by superficial "looks like
a plain player-stat grant" appearance, but the actual mechanics split sharply:

- **Non-DPS rider (flat, while-held, no further nuance)**:
  - `stat_speed` (jousting_lance 1-4) — movement speed, held-weapon lifecycle.
  - `stat_armor` (rock 2-4 only) — defensive stat, held-weapon lifecycle.
  - `stat_max_hp` (rock 3-4) — survivability stat, held-weapon lifecycle.
  - `stat_harvesting` (hand 1-4) — economy passthrough, held-weapon lifecycle
    (payout formula already documented in `docs/stat-mechanics.md`).
  - `xp_gain` (fighting_stick 1-4) — economy passthrough, held-weapon
    lifecycle.
  - `knockback` (hammer 2-4) — CC utility, player-wide, held-weapon
    lifecycle. Confirmed genuinely a player stat, not the weapon's own
    knockback field (which the dataset already captures separately as
    `base_knockback`).
  - **Proposed dataset classification**: these six are safe to move out of
    `unmodeled_effects` into a "rider" bucket (schema shape is Phase 2's
    call) with their flat `value` surfaced as-is and no DPS contribution.

- **Unmodelable-static (state/build/time-dependent — no honest static number)**:
  - `stat_percent_damage` on **jousting_lance** (1-4) — damage penalty applies
    only while the player is standing completely still; zero effect while
    moving. A static DPS-at-zero-RD line cannot represent a playstyle-gated
    toggle; whether "always moving" (0 penalty) or "always still" (full
    penalty) is the more representative default is a judgment call for
    synthesis, not evidenced one way in the code.
  - `stat_percent_damage` on **scythe T4** — stacking buff triggered by the
    *player* taking a hit (not the weapon dealing one), evidence suggests
    permanent accumulation with no found removal path (flagged
    `UNVERIFIED` — no reset code found, none ruled out either). Either way,
    depends on "hits taken this run," which a static per-weapon formula has
    no way to represent.
  - `stat_armor` on **excalibur T4** — scales as `-2 * (weapons owned)`,
    i.e. depends on the player's build size, not a fixed number per Excalibur
    alone.
  - `stat_lifesteal` on **sharp_tooth** (1-4) — recomputed live every half
    second as a function of current missing HP%; exactly 0 at full HP,
    growing as the player takes damage. The `.tres` `value` field is a
    formula coefficient, not the granted amount — surfacing it as a flat
    "lifesteal: 1" in the dataset would be actively misleading.
  - `stat_attack_speed` on **drill T4** — grows indefinitely by +10 every 5
    seconds while held, with no evidenced ceiling or reset; genuinely
    unbounded over time, same category as "scales with kills this wave."
  - **Proposed dataset classification**: keep these five effect entries out
    of any DPS math (they already are), but do NOT bucket them with the
    flat riders above — surfacing a wrong flat number would be worse than
    the current `unmodeled_effects` treatment. Recommend either a distinct
    `conditional`/`dynamic` tag (schema call for Phase 2) or leaving them in
    `unmodeled_effects` with a documentation note (this dossier +
    `docs/stat-mechanics.md`) explaining why, rather than inventing a
    representative constant.

No `DPS-modelable` or `Delivery modifier` candidates were found in this
family — none of these nine keys touch the weapon's own damage-dealing hit
math (`_hitbox.damage`, pierce, bounce, projectile count, etc.); the
`stat_percent_damage`/`stat_attack_speed` feedback into DPS is indirect
(through the player's global multiplier, per `docs/stat-mechanics.md`'s
existing `stat_percent_damage` and `stat_attack_speed` entries) and is
explicitly out of scope per the brief ("note this for the synthesis phase, do
not model it yourself").

## Precondition verification table

Not applicable — no key in this family is proposed as DPS-modelable, so there
is no precondition table to fill in DPS-modelable's sense. For clarity, here is
the while-held/lifecycle verification for the six flat riders instead:

| weapon/tier | key | apply on equip? | unapply on unequip/sell? | evidence |
|---|---|---|---|---|
| jousting_lance 1-4 | stat_speed | yes (`add_weapon`→`apply_item_effects`) | yes (`remove_weapon`→`unapply_item_effects`) | `run_data.gd:989/1081`, `effect.gd:81-82` (SUM) |
| rock 2/3/4 | stat_armor | yes | yes | same as above |
| rock 3/4 | stat_max_hp | yes | yes | same as above |
| hand 1-4 | stat_harvesting | yes | yes | same as above |
| fighting_stick 1-4 | xp_gain | yes | yes | same as above |
| hammer 2/3/4 | knockback | yes | yes | same as above; also confirmed player-wide via `weapon_service.gd:265-270` |

## Open questions / UNVERIFIED items

- `UNVERIFIED`: scythe T4's `temp_stats_on_hit` (+3% damage per hit the
  player takes) — I found no code path that removes/decays this bucket's
  granted `TempStats` value. It may be permanent for the run, may reset at
  wave boundaries via a code path I didn't find (e.g. a global `TempStats`
  reset on wave start that I did not specifically search for), or may have
  some other bound. Needs a targeted search of wave-transition code
  (`main.gd`'s wave-start handler) before any classification stronger than
  "state-dependent, don't model" is made.
- Not investigated (out of this family's assigned key list, noted only
  because they co-occur in the same weapon `.tres` files): drill T4's
  `gold_on_crit_kill` (`null_effect.gd` — the script literally no-ops
  `apply`/`unapply`, so whatever consumes this key must dispatch on the key
  string directly, not the script class; worth flagging to whichever family
  owns `gold_on_crit_kill`) and scythe T4's `lose_hp_per_second`.
  `null_effect.gd`'s apply()/unapply() being empty no-ops is itself a small
  surprise worth relaying: it confirms `gold_on_crit_kill` (and any other key
  attached to `NullEffect`) is consumed elsewhere purely by key string
  lookup, exactly the caveat the brief raised about script-vs-key dispatch,
  just in the opposite direction (exploding effects share one script across
  keys; here one script — a no-op — is shared by keys that are actually read
  elsewhere by string).
- Did not verify whether `TempStats` (the underlying accumulator for several
  of these dynamic effects) resets at wave boundaries in general — relevant
  context for anyone modeling drill's `stat_attack_speed` or scythe's
  `stat_percent_damage` in a future session, but out of scope for this
  dossier's verdict (both are already headed to "don't model statically"
  regardless of the answer).
