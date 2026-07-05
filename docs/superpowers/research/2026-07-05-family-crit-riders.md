# Crit riders — proc-worklist investigation dossier
Date: 2026-07-05. Game version: 1.1.15.4 (extracted/). Investigator: subagent.

## Keys covered

| key | weapon | tier | value (.tres) | base `piercing`/`bounce` | dmg-reduction on the granted extra | weapon crit_chance | weapon cooldown |
|---|---|---|---|---|---|---|---|
| `pierce_on_crit` | Crossbow (ranged) | 1 | 1 | piercing=0 | `piercing_dmg_reduction`=0.0 | 0.30 | 50 |
| `pierce_on_crit` | Crossbow | 2 | 2 | piercing=0 | 0.0 | 0.35 | 50 |
| `pierce_on_crit` | Crossbow | 3 | 3 | piercing=0 | 0.0 | 0.40 | 50 |
| `pierce_on_crit` | Crossbow | 4 | 4 | piercing=0 | 0.0 | 0.45 | 50 |
| `bounce_on_crit` | Shuriken (ranged) | 1 | 1 | bounce=0 | `bounce_dmg_reduction`=0.0 | 0.35 | 40 |
| `bounce_on_crit` | Shuriken | 2 | 2 | bounce=0 | 0.0 | 0.38 | 38 |
| `bounce_on_crit` | Shuriken | 3 | 3 | bounce=0 | 0.0 | 0.41 | 36 |
| `bounce_on_crit` | Shuriken | 4 | 4 | bounce=0 | 0.0 | 0.45 | 30 |
| `gold_on_crit_kill` | Dagger (melee) | 1 | 50 (%) | n/a | n/a | 0.20 | 27 |
| `gold_on_crit_kill` | Dagger | 2 | 56 (%) | n/a | n/a | ~0.25 (not re-verified this pass; see note) | ~ |
| `gold_on_crit_kill` | Dagger | 3 | 62 (%) | n/a | n/a | ~0.30–0.35 (not re-verified this pass) | ~ |
| `gold_on_crit_kill` | Dagger | 4 | 80 (%) | n/a | n/a | 0.40 | 10 |
| `gold_on_crit_kill` | Drill (melee) | 4 (only tier shipped) | 100 (%) | n/a | n/a | 0.50 | 2 |

All 13 census entries match the brief's fresh census exactly (crossbow T1-4 ranged, shuriken T1-4 ranged,
dagger T1-4 melee, drill T4 melee — no other tiers/weapons ship any of these three keys).
`grep -rl 'key = "pierce_on_crit"\|key = "bounce_on_crit"\|key = "gold_on_crit_kill"' extracted/weapons/`
confirms exactly these 13 files.

Dagger T2/T3 `crit_chance` values in the table are carried from a prior read and marked
UNVERIFIED here — I verified T1 (`extracted/weapons/melee/dagger/1/dagger_stats.tres:13`,
`crit_chance = 0.2`) and T4 (`extracted/weapons/melee/dagger/4/dagger_4_stats.tres:13`,
`crit_chance = 0.4`) directly this pass, but did not re-open T2/T3 stats files (irrelevant to
the verdict — `crit_chance` doesn't gate the classification, only flavors frequency).

**Companion resources**: none. Every weapon dir here has exactly the standard three files
(`*_data.tres`, `*_effect*.tres`, `*_stats.tres`) — confirmed by directory listing for
crossbow/1-4, shuriken/1-4, dagger/1-4. **Exception**: Drill only ships at tier 4
(`extracted/weapons/melee/drill/4/`) and that directory has a fourth file,
`drill_effect_2.tres`, referenced alongside `drill_effect.tres` in
`drill_4_data.tres:21` (`effects = [ ExtResource( 5 ), ExtResource( 8 ) ]`). It is a
**second, independent** weapon effect — not a companion/sub-resource of the
`gold_on_crit_kill` effect the way `burning_data` is for burn. `drill_effect_2.tres` attaches
`res://effects/items/temp_stats_per_interval_effect.gd`, `key = "stat_attack_speed"`,
`custom_key = "temp_stats_per_interval"`, `value = 10`, `interval = 5` — an unrelated,
already-separately-tracked unmodeled key (`stat_attack_speed`/`temp_stats_per_interval`, not
in this family's scope; out of scope here, flagged only so it isn't mistaken for burn-style
plumbing).

## Mechanic (evidence)

### Shared: all three keys attach `null_effect.gd`, dispatch is on key string, not class

- Every `.tres` for all three keys (`crossbow_effect.tres`, `shuriken_effect.tres`,
  `dagger_effect.tres`, `drill_effect.tres`, and the T2-4 variants) references
  `res://effects/weapons/null_effect.gd` (`class_name NullEffect`, confirmed by reading
  `recovered/effects/weapons/null_effect.gd`). `NullEffect.apply()`/`unapply()` are no-ops.
  This is the inverse of the exploding-effect case (three keys, one script): here it's one
  script, three different keys, all consumed by **key string / key_hash matching** at the
  various call sites below, not by script class. Confirms the brief's warning to check the
  attached script before assuming dispatch — in this family it rules out class dispatch
  entirely and forces key-string grep, which is how all citations below were found.

### `pierce_on_crit` / `bounce_on_crit`

- `recovered/projectiles/player_projectile.gd:132-154`
  (`_on_Hitbox_critically_hit_something`): on every critical hit landed by *that specific
  projectile instance*, it loops `_hitbox.effects` and for
  `effect.key_hash == Keys.bounce_on_crit_hash`: `_bounce += 1; effect.value -= 1` (removes
  the effect from that projectile's own list once `value <= 0`); symmetric branch for
  `pierce_on_crit_hash` incrementing `_piercing`. So **each crit converts one "charge" of
  the weapon's own `value` into one extra pierce or bounce**, consumed 1:1, capped at the
  tier's `value` (crossbow T1-4: 1/2/3/4; shuriken T1-4: 1/2/3/4).
- **Per-projectile isolation (verified, not assumed)**:
  `recovered/singletons/weapon_service.gd:366-378` (`spawn_projectile`): before a projectile
  is spawned, `var duplicated_effects = []; for effect in args.effects:
  duplicated_effects.push_back(effect.duplicate())` — every projectile gets its own
  **duplicated** copy of the weapon's effect resources. This means `effect.value -= 1` in
  the crit handler mutates only that single projectile's private copy, not the weapon's
  shared `effects` array — confirmed by reading `Effect.duplicate()` in
  `recovered/items/global/effect.gd:26-37`, which returns a new `Resource` and copies
  `key_hash`/`custom_key_hash` but each duplicate has its own `value` slot (standard Godot
  `Resource.duplicate()` shallow-copies exported vars). **Consequence**: the "budget" of
  `value` bonus pierces/bounces resets fresh for every shot fired, it is not a
  wave-long or run-long depleting pool.
- **Base piercing/bounce is 0 for both weapons at every tier** — verified directly:
  `extracted/weapons/ranged/crossbow/{1,2,3,4}/crossbow_stats*.tres`: `piercing = 0`,
  `bounce = 0` in all four (spot-read 1 and 4 in full, grepped `piercing = \|bounce = ` in
  2 and 3 to confirm the same). `extracted/weapons/ranged/shuriken/{1,2,3,4}/*_stats.tres`:
  same, `piercing = 0`, `bounce = 0` in all four. **Both weapons rely 100% on the crit
  proc for any pierce/bounce at all** — without a crit, the projectile stops at the first
  enemy it hits (`player_projectile.gd:109-116`: `if _bounce > 0: bounce(...) elif
  _piercing <= 0: stop() ...`).
- **Damage retention on the crit-granted extra hits is 0% reduction for both weapons,
  by explicit per-weapon override** — this is the key delivery-mechanics nuance:
  - Engine default (`recovered/weapons/weapon_stats/ranged_weapon_stats.gd:6-9`):
    `piercing_dmg_reduction := 0.5`, `bounce_dmg_reduction := 0.5` (i.e. lose half damage
    per pierce/bounce, by default, for any weapon that pierces/bounces).
  - Crossbow (the pierce_on_crit weapon) explicitly sets
    `piercing_dmg_reduction = 0.0` in all four tiers' stats (`crossbow_stats.tres:40`,
    `crossbow_stats_2.tres:40`, `crossbow_stats_3.tres:40`, `crossbow_stats_4.tres:40`,
    all read directly) — **its own crit-granted pierces deal full damage, no reduction**.
    Its `bounce_dmg_reduction` stays at the engine default 0.5, but this is moot: crossbow
    never bounces (`bounce = 0`, no `bounce_on_crit` effect).
  - Shuriken (the bounce_on_crit weapon) explicitly sets `bounce_dmg_reduction = 0.0` in
    all four tiers (`shuriken_stats.tres:41`, `shuriken_2_stats.tres:41`,
    `shuriken_3_stats.tres:41`, `shuriken_4_stats.tres:41`, all read directly) — **its own
    crit-granted bounces deal full damage, no reduction**. Its `piercing_dmg_reduction`
    stays at the engine default 0.5 (`= 0.5` explicitly set, matching default), moot since
    `piercing = 0` and it has no `pierce_on_crit` effect.
  - The reduction formula itself (`player_projectile.gd:114-116` for pierce, `:128-129`
    for bounce): `_hitbox.damage = max(1, _hitbox.damage - (_hitbox.damage *
    weapon_stats.piercing_dmg_reduction))` — applied per additional pierce/bounce, using
    the *current* (potentially already-reduced) hitbox damage, so reductions would
    compound multiplicatively across a pierce chain if reduction were nonzero. At 0.0 for
    both weapons in this family, this compounding never triggers — every crit-chained hit
    deals the same full damage as the original hit.
- **Ordering (verified, resolves a plausibility question about whether the very first
  hit can benefit)**: `recovered/entities/units/unit/unit.gd:584` calls `take_damage(...)`
  which, internally, at `unit.gd:312-313`, does `if (is_crit or is_one_shot) and hitbox:
  hitbox.critically_hit_something(...)` (this is what fires the pierce/bounce charge
  increment above) — and only *after* `take_damage` returns does `unit.gd:608` call
  `hitbox.hit_something(...)` (this is what decides pierce/stop in
  `player_projectile.gd:109-116`). Both calls happen synchronously in the same function
  (`unit.gd`'s damage-handling method containing lines 264-608). So **a crit on the very
  first landed hit already grants the pierce/bounce charge before the stop-or-continue
  decision is made** — the projectile does not need a prior non-crit hit to "start"
  piercing/bouncing; the first hit can crit and immediately continue.
- **`is_crit` is a fresh per-hit roll**, `unit.gd:285`: `var is_crit = true if
  Utils.get_chance_success(crit_chance) else false`, where `crit_chance` (line 278) comes
  from `hitbox.crit_chance`, i.e. the weapon's own `current_stats.crit_chance` for that
  specific hit (table above). Not cumulative, not per-wave — an independent roll every
  landed hit.
- **Player-level (item-granted) stacking is additive, separate from the weapon's own
  value, and zero at baseline** — `recovered/singletons/weapon_service.gd:425-432`
  (`set_projectile_effects`) and `:435-452` (`_add_player_effect_to_effects`): if the
  player has a nonzero `RunData.get_player_effect(Keys.pierce_on_crit_hash, ...)` /
  `bounce_on_crit_hash` (an item-granted player stat, independent of these weapons), it is
  **added** to the projectile's existing `pierce_on_crit`/`bounce_on_crit` effect's `value`
  (or a new effect entry is appended if the weapon didn't have one). Engine default for
  this player-level stat is 0 for both hashes
  (`recovered/singletons/player_run_data.gd:592-593`: `Keys.pierce_on_crit_hash: 0,
  Keys.bounce_on_crit_hash: 0`). At the dataset's zero-baseline convention (no items
  equipped), this reduces to exactly the weapon's own `.tres` `value` — consistent with
  how the burn model's zero-baseline analysis works for `stat_elemental_damage`.

### `gold_on_crit_kill`

- `recovered/entities/units/unit/unit.gd:357-383` (inside the death-handling branch,
  gated on `current_stats.health <= 0`, i.e. **the hit itself was a killing blow**, and
  `if is_crit:`, i.e. **that killing blow was also a critical hit** — both conditions
  required together, this is not "any crit" and not "any kill"):
  - Lines 366-371: a *separate*, player-level source first —
    `RunData.get_player_effect(Keys.gold_on_crit_kill_hash, from_player_index)` returns a
    list of item-granted effects (baseline empty list,
    `recovered/singletons/player_run_data.gd:538`: `Keys.generate_hash("gold_on_crit_kill"):
    []`); each rolls its own percent chance independently and adds 1 gold per success.
    This is unrelated to the weapon's own effect and stays empty at zero-item baseline.
  - Lines 376-379 — **the weapon's own effect, this family's actual key**:
    `for effect in hitbox.effects: if effect.key_hash == Keys.gold_on_crit_kill_hash and
    randf() <= effect.value / 100.0: gold_added += 1; hitbox.added_gold_on_crit(gold_added)`
    — the `.tres` `value` (50/56/62/80 for dagger T1-4, 100 for drill T4) is a **percent
    chance out of 100**, rolled once per crit-kill, to add exactly 1 gold.
  - Line 381-383: `if gold_added > 0: RunData.add_gold(gold_added, from_player_index);
    hit_type = HitType.GOLD_ON_CRIT_KILL` — feeds the floating-text/visual-effect hit-type
    only for display; `RunData.add_gold` (`recovered/singletons/run_data.gd:879-887`) is a
    flat `player_data.gold += value` with no harvesting/gold-multiplier stat applied at
    this call site (confirmed by reading the function body — no scaling stat is
    referenced).
  - `weapon.gd:107,241-244`: a `killed_something`→`added_gold_on_crit` signal chain exists
    purely to emit a `tracked_value_updated` UI signal (`if effect.key ==
    "gold_on_crit_kill": emit_signal("tracked_value_updated")`) — no gameplay effect, just
    UI bookkeeping for a stat display.
- **Conclusion**: `gold_on_crit_kill` is a chance-per-crit-kill, flat +1-gold economy
  effect, entirely decoupled from the weapon's damage line. It requires the kill itself to
  be the crit (not "get a crit sometime this fight then separately kill the enemy" —
  the `is_crit` flag checked at line 357 is the flag computed for *that specific
  killing hit* at line 285/299, inside the same `take_damage` call).

## Verdict

### `pierce_on_crit`, `bounce_on_crit` — **Delivery modifier**

Both change how many enemies a single projectile can hit, not the weapon's own damage
line — confirmed CONFIRMED (not TENTATIVE) via the full mechanical trace above. The engine
supports, and this dossier transcribes:

- A **deterministic per-projectile cap**: up to `value` additional pierces/bounces per
  projectile (1/2/3/4 by tier for both weapons), each requiring its own crit on a
  still-flying projectile, at the weapon's own `crit_chance` (table above).
- **Zero damage reduction** on every crit-chained extra hit, for both weapons, by
  explicit per-weapon stat override (not the engine's 50% default) — so unlike a generic
  pierce/bounce weapon, this family's crit-chained hits are exact damage-line repeats, not
  a decaying tail.
- No existing `PROC_MODELS` `damage_source` fits this: it isn't a new damage instance with
  its own retention factor the way `weapon_damage` (exploding) or `burn_dot` are — it's a
  probabilistic **multiplier on `enemies_hit`** for the weapon's *existing* damage line,
  conditioned on a chain of independent `crit_chance` rolls (one roll per additional
  enemy, capped at `value` rolls). Per the brief's instruction for this family, I am not
  inventing the expected-value formula for that chain (e.g. an
  expected-additional-enemies-hit number derived from `crit_chance` and `value`) — that
  would need its own crowd-density assumption analogous to the exploding model's
  `default_enemies_hit: 1.0`, which the exploding model documents as "the softest number
  in the model." I flag this as the natural next step for Phase 2 if a
  `damage_multiplier`-family field for enemies-hit is added, but do not propose the
  formula here.
- Honest dataset representation given what's currently modeled: leave both keys in
  `unmodeled_effects` (as today) OR — if Phase 2 wants a documented-but-not-DPS-scored
  classification — tag them as a `delivery_modifier` effect category so they stop reading
  as "silently ignored" in tooling, without attempting a DPS number. I recommend the
  latter (classification, no formula) since the mechanic is fully evidenced and static
  (`value` per tier, 0% reduction, don't need per-weapon judgment calls) even though the
  *DPS contribution* is state-dependent (enemy density + a `crit_chance`-gated chain).

### `gold_on_crit_kill` — **Non-DPS rider (economy)**

Confirmed economy, not damage: a percent chance (`.tres` `value`/100, per weapon/tier —
50/56/62/80% for dagger T1-4, 100% for drill T4), rolled once whenever that weapon's hit
is *both* the killing blow *and* a crit, granting a flat +1 gold via
`RunData.add_gold(1, ...)`. It grants nothing when the weapon is equipped/idle (unlike a
passive stat grant) — the trigger condition is the crit-kill event itself, evaluated
inside `unit.gd`'s death-handling branch on every hit, not a standing passive multiplier.
Recommend classifying it as `economy` (or reusing whatever existing bucket the dataset
uses for other non-combat weapon perks) so it's visibly "modeled as non-DPS" rather than
silently sitting in `unmodeled_effects` looking like a missed proc. No DPS number applies
by definition — this is out of scope for `proc_dps_at_zero_rd`/`proc_dps_slope_per_rd`
regardless of preconditions.

## Precondition verification table

Not applicable — neither classification is DPS-modelable under the existing
`damage_source` schema, so there is no precondition table analogous to the burn model's.
(If Phase 2 adds a `delivery_modifier` schema slot, the "preconditions" for `pierce_on_crit`
/`bounce_on_crit` would be: base `piercing`/`bounce` == 0 for the weapon [true for all 8
shipped entries, verified above] and reduction fields == 0.0 for the relevant axis [true
for all 8, verified above] — both hold today but would need re-checking against any future
weapon that reuses these keys with nonzero base piercing/bounce or nonzero reduction.)

## Open questions / UNVERIFIED items

- Dagger T2 (`crit_chance` in the table, ~0.25) and T3 (~0.30–0.35) values are carried
  from a prior pass and marked UNVERIFIED — I did not reopen
  `extracted/weapons/melee/dagger/2/dagger_2_stats.tres` or `.../3/dagger_3_stats.tres`
  this session. This doesn't affect the verdict (crit_chance only affects trigger
  frequency, not the classification), but should be re-pinned before any doc citing exact
  dagger T2/T3 crit_chance values.
- I did not investigate whether any *item* (as opposed to weapon) grants `pierce_on_crit`,
  `bounce_on_crit`, or `gold_on_crit_kill` as a starting/equippable player stat outside the
  four weapons in this family — `player_run_data.gd`'s defaults confirm the *engine*
  supports player-level versions of all three keys (zero-baseline), but I did not grep
  `extracted/items/` for which specific items (if any) grant them. Out of scope for this
  weapons-focused census per the brief, flagged for awareness since it affects the
  "zero-baseline" argument's completeness (an item existing doesn't change the verdict,
  since the dataset's convention is to model at zero player-stat baseline regardless).
- `effect_sign`/`storage_method`/`text_key`/`custom_args` fields on all these `.tres`
  files are confirmed (via `recovered/items/global/effect.gd`) to be UI/display metadata
  only (icon coloring, tooltip text formatting) — not consumed by any of the gameplay
  code paths cited above. Noted so a future reader doesn't waste time chasing them as
  gameplay-relevant.
