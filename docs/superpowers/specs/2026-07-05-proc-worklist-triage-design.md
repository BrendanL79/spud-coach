# Proc-worklist triage: model, classify, or document every remaining weapon effect

Full triage of every weapon-effect key still contributing zero to
`proc_dps_at_zero_rd` after the burn model (PR #8 / 25f8ca2). Unlike the burn
round (one key, one model), this round's honest outcome is mostly *verdicts*:
two new DPS models, one delivery-modifier classification, and a category
system that empties `unmodeled_effects` of everything that is not actually a
missed damage proc.

## Inputs

Seven evidence dossiers under `docs/superpowers/research/` (all citations
spot-verified against `recovered/`/`extracted/` during synthesis review):

- `2026-07-05-family-lightning.md` — `effect_lightning_on_hit`
- `2026-07-05-family-projectiles-on-hit.md` — `effect_projectiles_on_hit`, `EFFECT_PROJECTILES_ON_HIT`
- `2026-07-05-family-crit-riders.md` — `pierce_on_crit`, `bounce_on_crit`, `gold_on_crit_kill`
- `2026-07-05-family-conditional-buffs.md` — `effect_no_hit_boost`, `effect_gain_stat_every_killed_enemies`, `EFFECT_WEAPON_STACK`
- `2026-07-05-family-stat-riders.md` — 9 `stat_*`/`xp_gain`/`knockback` keys
- `2026-07-05-family-slows-cc.md` — `EFFECT_WEAPON_SLOW_ON_HIT`, `EFFECT_SLOW_PROJECTILES_ON_HIT`, `effect_slow_in_zone`
- `2026-07-05-family-misc-blank.md` — `burning_spread`, `consumable_heal`, `lose_hp_per_second`, and the three blank-key mechanics (Vorpal execute, Screwdriver landmines, Pruner garden)

Decisions made with Brendan (2026-07-05): full triage (not DPS-only);
per-effect **category tags** in the dataset; spray procs modeled with an
explicit `enemies_hit = 1.0` assumption (exploding-effect precedent);
special mechanics exposed as **structured metadata**, not folded into DPS.

## Rulings on the dossiers' TENTATIVE verdicts

- **Projectiles-on-hit spray (cactus_mace, sniper_gun, thunder_sword)** →
  **model** with `expected_enemies_hit = 1.0`, documented as an assumption
  exactly like exploding's `default_enemies_hit`. Rationale: the project
  already accepts one invented enemies-hit constant when the rest of the
  formula is fully evidenced; dropping cactus_mace's real RD slope
  (companion scales off `stat_ranged_damage` 0.6→1.0) is a worse error than
  an optimistic constant. Callers can override downward as with exploding.
- **`burning_spread` (Torch T3/T4)** → **stat_rider** classification, no DPS
  change to the burn model. It is a global, equip-time, cross-weapon player
  stat (`weapon_service.gd:334` consumes it for *every* burning source);
  "2× burn dps" would mis-scope a global stat to one weapon and rests on a
  spatial condition (`SpreadArea` body presence) with no evidence anchor.
- **Screwdriver landmines** → **structure** classification with metadata, no
  DPS number. The "every mine eventually triggers" premise is an enemy-AI
  claim with nothing in `extracted/` to verify it against (contrast burn's
  precondition, checkable from `.tres` values alone). Mine params surface as
  metadata: spawn cadence, flat damage 10, `stat_engineering` scaling.
- **Stick `EFFECT_WEAPON_STACK`** → **stack** classification with metadata
  (`bonus_per_extra_copy`), no proc-DPS folding. The formula
  `stack_dps0(N) = value·(N−1)/cycle_time·accuracy` is verified, but `N`
  (copies owned) is a loadout axis the schema doesn't have; metadata lets
  `answers.py`/callers compute it at question time. Adding a second
  free-variable axis to the dataset is deferred until a real question needs
  it (YAGNI).

## Schema change: `classified_effects` + shrunken `unmodeled_effects`

Weapon records gain one new list field, `classified_effects`. Each entry is a
small dict: `{"key": <effect key or script-derived name>, "category": <one of
the vocabulary below>, ...category-specific metadata fields}`. The proc loop's
disposition per effect becomes:

1. Key has a `PROC_MODELS` entry and passes its gates → contributes to
   `proc_dps_at_zero_rd`/`proc_dps_slope_per_rd` (as today).
2. Else, `classify_effect()` recognizes it → appended to
   `classified_effects`, NOT to `unmodeled_effects`.
3. Else → `unmodeled_effects` (now meaning: genuinely uninvestigated). Blank
   keys are no longer dropped silently: an unrecognized effect with an empty
   key is listed by its script basename so future hidden mechanics surface.

Category vocabulary (fixed set, asserted in tests):

| category | meaning | metadata fields |
|---|---|---|
| `stat_rider` | flat player-stat grant while held (SUM storage) | `value` |
| `dynamic` | state/build/time-dependent grant — no honest static number | — |
| `economy` | gold/xp event effects | `gold_chance_on_crit_kill` where applicable |
| `cc` | slows/crowd control, no damage | — |
| `delivery_modifier` | changes the weapon's own hit delivery (crit-gated pierce/bounce) | `on_crit_extra_hits_max` |
| `drawback` | self-damage cost | `self_damage_per_second` |
| `execute` | chance to force hit damage = target's current HP | `execute_chance_per_hit` |
| `stack` | per-extra-copy flat weapon-stat bonus | `stat_name`, `bonus_per_extra_copy` |
| `structure` | spawns a persistent structure (mines, garden) | `spawn_cooldown` (raw engine value), `structure_damage`, `structure_scaling_stats` |

Classification is **mechanism-based**, not a hardcoded weapon list, per the
stat-riders dossier's key finding that identical key strings hide different
mechanics:

- Effects whose `script` is a known special (`one_shot_on_hit_effect.gd`,
  `weapon_stack_effect.gd`, `structure_effect.gd`, `turret_effect.gd`,
  `gain_stat_for_every_stat_effect.gd`, `temp_stats_per_interval_effect.gd`,
  `gain_stat_every_killed_enemies_effect.gd`, `player_no_hit_effect.gd`,
  `weapon_slow_on_hit_effect.gd`, `slow_in_zone_effect.gd`) classify by
  script regardless of key (dispatch in the engine is by script class for
  most of these — and `key = ""` for three of them).
- `storage_method == 1` (KEY_VALUE — the engine's conditional-bucket path:
  `temp_stats_while_not_moving`, `temp_stats_on_hit`,
  `additional_weapon_effects`, per `effect.gd:62-83`) → `dynamic`. This
  catches jousting_lance's stand-still damage penalty, scythe T4's
  on-player-hit stack, and excalibur's per-weapon-owned armor penalty
  without naming weapons.
- Plain SUM effects with a `stat_*` key, or `xp_gain`/`knockback`/
  `consumable_heal`/`burning_spread` → `stat_rider` (evidence: the shared
  `add_weapon → apply_item_effects → effect.apply` / `remove_weapon →
  unapply_item_effects` lifecycle, `run_data.gd:989/1081`).
- `pierce_on_crit`/`bounce_on_crit` → `delivery_modifier`;
  `gold_on_crit_kill` → `economy`; `lose_hp_per_second` → `drawback` (all
  key-string dispatched in the engine — they attach no-op `NullEffect`/plain
  `Effect` scripts).

To make script-based classification possible, effect records gain a
`"script"` field (basename of the effect's script ext_resource, e.g.
`"one_shot_on_hit_effect.gd"`), resolved by `_weapon_effect_record`.

## New DPS model: `companion_ranged_stats`

One model covers all four `ProjectilesOnHitEffect` keys
(`effect_lightning_on_hit`, `effect_projectiles_on_hit`,
`EFFECT_PROJECTILES_ON_HIT`, `EFFECT_SLOW_PROJECTILES_ON_HIT`) — the engine
dispatches on the shared script class, so one model entry per key pointing at
one shared dict mirrors the exploding-effect precedent.

Mechanic (fully evidenced in the lightning + projectiles-on-hit dossiers):
each landed host hit unconditionally spawns `value` projectiles (no chance
roll — `value` is a count) whose damage/crit/scaling live on a companion
`RangedWeaponStats` resource referenced as `weapon_stats = ExtResource(N)`.
At the dataset's zero-stat baseline the companion's raw `damage` field is the
per-hit damage (`weapon_service.gd` `init_ranged_stats(…, is_special_spawn=true)`
reduction, same argument as burn).

```
proc_dps0  = companion_damage  * value * enemies_hit / host_cycle_time
proc_slope = companion_rd_coef * value * enemies_hit / host_cycle_time
```

`companion_rd_coef` runs through the existing `_rd_coefficient()` — nonzero
only for cactus_mace (`stat_ranged_damage`); lightning
(`stat_elemental_damage`), sniper_gun (`stat_range`), thunder_sword
(`stat_elemental_damage`) all get slope 0.

`enemies_hit` policy, dispatched on the effect's own `auto_target_enemy`:

- **`true` (targeted chain — lightning_shiv, dextroyer):** `1 + bounce`
  (companion's `bounce` field), valid only when `can_bounce == true` and
  `bounce_dmg_reduction == 0.0` (all 5 shipped users, verified) — the model
  has no decaying-bounce math, so a nonzero reduction with nonzero bounce
  falls back to `unmodeled_effects`. Assumption flag: nominal chain fully
  connects; true value is 0 against a lone enemy (spawn excludes the
  triggering enemy via `get_rand_enemy(entity_from)` +
  `set_ignored_objects([self])`).
- **`false` (untargeted spray — cactus_mace, sniper_gun, thunder_sword):**
  `1.0` per volley (NOT per projectile), valid only when `bounce == 0`
  (all 6 shipped users; note their `bounce_dmg_reduction` sits at the engine
  default 0.5, so gating on the reduction field — as the targeted branch
  does — would wrongly fail them). Assumption flag: a random-direction
  volley lands one expected hit; there is no evidence anchor, this is the
  exploding-`default_enemies_hit` precedent applied deliberately.

Gates common to both branches: companion present, `damage` field present
(burn-PR lesson: every consumed field gated), `value > 0`. On any gate
failure the key goes to `unmodeled_effects`.

All 11 shipped users pass (per-dossier precondition tables): lightning_shiv
T1-4, dextroyer T4 (targeted); cactus_mace T1-4, sniper_gun T3-4,
thunder_sword T3-4 (spray). thunder_sword's slow rides the same projectile
(hardcoded −200 in `taser_projectile.gd:15`) and is additionally noted in
docs; its damage sliver (companion damage=1) is what this model scores.

## Plumbing: generalized companion resolution

Burn's `burning_data` plumbing generalizes to N companion fields. Known
companion-bearing effect fields: `burning_data` (BurningData),
`weapon_stats` (RangedWeaponStats, the projectile procs), `stats`
(structure/turret stats — needed for landmine/garden metadata; note these
live *outside* the weapon dir, e.g. `items/all/landmines/landmine_stats.tres`,
so resolution must follow the ext_resource URL, never a directory glob —
three distinct companion filename conventions were found, and the burn glob
collision (25f8ca2) already showed filename patterns are a trap).

- `discover.py`: `_resolve_effect_burning_data` generalizes to
  `_resolve_effect_companions(extracted_root, effect_paths) ->
  dict[str, dict[str, str]]` (effect path → {field: companion path}),
  scanning the three field names above. `find_weapon_dirs` entries carry it
  as `"effect_companion_paths"`, replacing `"effect_burning_data_paths"`.
- `weapons.py`: `_weapon_effect_record(text, companions: dict[str, str] |
  None = None)` — each companion's parsed scalars nest under its field name
  (so `eff["burning_data"]` keeps its exact current shape; `eff["weapon_stats"]`
  and `eff["stats"]` are new). `build_weapon_record`'s
  `effect_extra_texts: list[str | None]` parameter becomes
  `effect_companion_texts: list[dict[str, str] | None]` (same position).
  Also extracts the `"script"` basename here.
- `build_dataset.py`: reads each companion path's text into the per-effect
  dict. Same-branch callers/tests updated; no external consumers exist.

## Out of scope (recorded, not addressed)

- Weapons whose data files sit at the weapon root with no numeric tier dir
  (rocket_launcher; fireball T1; chopper untiered file) are skipped by
  `find_weapon_dirs`'s existing tier-dir walk — pre-existing dataset gap,
  independent of this change.
- Crit is not modeled anywhere in the dataset (companion crit fields are
  carried in effect records but unused) — pre-existing, dataset-wide.
- The `dynamic` category deliberately carries no numbers. Jousting lance's
  stand-still penalty, Rail Gun's ramp, ghost-weapon ratchets, sharp_tooth's
  missing-HP lifesteal, drill's unbounded attack speed: all documented in
  `docs/proc-mechanics.md` with citations instead.
- Stick's copies-owned DPS axis: metadata only this round (see ruling).

## Testing

TDD per task, mirroring the burn plan's granularity: pure `calc` unit tests;
`discover` companion-resolution fixtures (one per companion field, plus a
no-companion effect); `_weapon_effect_record` nesting + script extraction;
model gate tests (targeted pass / targeted with lossy bounce falls back /
spray pass / spray with bounce falls back / missing damage falls back);
classification tests (one per category, including storage_method-driven
`dynamic` vs `stat_rider` discrimination and blank-key script naming);
builder integration (classified effects leave `unmodeled_effects`); a
shipped-dataset test asserting lightning_shiv T1 and cactus_mace T1 carry
nonzero proc lines (cactus_mace with nonzero slope), Stick/Vorpal/Screwdriver
carry their classified metadata, and no weapon record has a non-empty
`unmodeled_effects` (the worklist is fully triaged).
