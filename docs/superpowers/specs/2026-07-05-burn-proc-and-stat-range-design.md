# Burn proc model + stat_range projectile-speed nuance

Two roadmap backlog items, addressed together since the second is small
enough to fold in: the top entry of the unmodeled-proc worklist
(`effect_burning`, 19 weapon effects) and the `stat_range` projectile-speed
docs gap.

## Goal

Model `effect_burning`'s expected DPS contribution so burn weapons
(Torch, Fireball, Wand, Flamethrower, Particle Accelerator, Flaming
Knuckles) rank honestly instead of showing zero proc DPS. Generalize the
builder's proc-aggregation loop so this and future non-`weapon_damage` proc
types share one dispatch point (the `aggregate_proc_dps` extraction flagged
in the roadmap). Separately, close the `stat_range` mechanics-doc gap for
`increase_projectile_speed_with_range`.

## Why this scope

Only `effect_burning` has been fully evidenced against `recovered/` so far.
The other ~14 unmodeled keys (`effect_gain_stat_every_killed_enemies`,
`effect_lightning_on_hit`, etc.) each need their own decompiled-source
investigation before a model can be proposed; they stay in
`unmodeled_effects` until a future round does that work.

## Evidence: how burn actually works

- `recovered/entities/units/unit/unit.tscn:51-52`: `BurningTimer` node,
  `wait_time = 0.5` — burn ticks every 0.5s. This is an engine constant, not
  per-weapon.
- `recovered/entities/units/unit/unit.gd:581-583`: on a landed hit, `if
  hitbox.burning_data != null and
  Utils.get_chance_success(hitbox.burning_data.chance) ...:
  apply_burning(hitbox.burning_data)` — chance is rolled once per landed
  hit, not per tick.
- `recovered/entities/units/unit/unit.gd:618-648` (`apply_burning`):
  re-application while already burning refreshes via `max()` on
  chance/damage/duration/spread — it does not stack additively. The
  `_burning_timer` only (re)starts if the unit wasn't already burning.
- `recovered/entities/units/unit/unit.gd:660-706` (burn tick handler):
  deals `_burning.damage` flat damage via `take_damage`, then `_burning.duration
  -= 1`; burn ends when `duration <= 0`. So total ticks = the current
  `duration` value at time of last refresh, and each tick deals a flat
  `damage` value — not re-derived from the weapon's own current hit damage
  the way exploding procs are.
- `recovered/singletons/weapon_service.gd:290-332` (`init_burning_data`):
  `damage` is scaled by `apply_scaling_stats_to_damage` against the burn's
  own `scaling_stats` (default `[["stat_elemental_damage", 1.0]]` per
  `recovered/effects/burning_data.gd:8`) and then `apply_damage_bonus`
  (`stat_percent_damage`). At zero `stat_elemental_damage` and zero
  `stat_percent_damage` — the same "at-zero" baseline the rest of the
  dataset uses — this reduces to `max(1, base_damage)`, i.e. the `damage`
  field straight from the weapon's `burning_data.tres`.
- Verified empirically (`extracted/weapons/**/*_burning_data.tres` and
  matching `*_stats.tres`, all tiers): every shipped burn weapon has
  `chance = 1.0`, and every one has `cycle_time <= duration × 0.5s`
  (comfortable margin in all 15 tier variants checked — e.g. Particle
  Accelerator T3 is the tightest at cycle_time≈1.95s vs. a 4s window).
  Consequence: continuous attacking never lets a shipped weapon's burn
  expire, so steady-state uptime is effectively 100% for all of them.

### `chance`/`damage`/`duration` live in a separate file, not the effect record

A weapon's `effect_burning` `.tres` (e.g.
`extracted/weapons/melee/flaming_knuckles/2/flaming_knuckles_2_effect_1.tres`)
carries none of the gameplay numbers itself — `chance`, `damage`, `duration`,
`spread`, and `scaling_stats` all live on a **separate** `BurningData`
resource, referenced only as `burning_data = ExtResource( 2 )`. Contrast
with the exploding effect, where `chance` is an inline scalar on the same
file. `_weapon_effect_record` (`brotato_coach/builders/weapons.py:16-25`)
currently drops any field that's an ext/sub-resource reference — so today a
burn weapon's effect record carries no usable data at all. This requires
resolving and merging that companion file, not just adding a calc model:
see the plumbing changes below.

`recovered/effects/burning_data.gd:4`: `export (float) var chance: = 0.0` —
note this defaults to **0.0**, not `exploding_effect.gd`'s `1.0` default. No
shipped weapon relies on the default (all set `chance = 1.0` explicitly),
but the fallback value in code must match burn's own engine default, not be
copy-pasted from the exploding model.

## Model

New `damage_source: "burn_dot"` in `procs.py`'s model schema, alongside the
existing `"weapon_damage"`:

```
burn_dps0 = damage_per_tick / 0.5   # tick_interval, engine constant
burn_slope = 0.0                    # scales off stat_elemental_damage, not RD
```

Applied only when, for that specific weapon:
1. `effect.chance == 1.0`, and
2. `weapon's own cycle_time <= duration * 0.5`

Both conditions hold for every shipped burn weapon (see evidence above). If
a future weapon violates either, the effect stays in `unmodeled_effects`
rather than falling back to an unverified formula — no shipped weapon
exercises the chance<1 or slow-cycle case, so no math is written to cover
it.

This deliberately does not attempt a general duty-cycle/renewal-process
model for `chance < 1.0`. That would be speculative math with nothing in
`extracted/` to verify it against, which conflicts with the project's
evidence-only rule for `docs/` (`CLAUDE.md`: "Evidence citations ... must be
re-pinned against the decompiled source at write time").

## Plumbing: resolving the `burning_data` companion file

`brotato_coach/builders/discover.py::_resolve_weapon_refs` currently
resolves a weapon's `effects` ext_resource list into `effect_paths:
list[str]`. This stays as-is (no shape change, no existing caller breaks).
A new, additive step: for each resolved effect path, peek at that file's own
`ext_resources` table for a `burning_data` field reference, and — if
present — resolve it to a path the same way (`_res_url_to_path`). Return it
as a new, separate dict on the weapon entry: `"effect_burning_data_paths":
{effect_path: burning_data_path}` (only populated for effects that have
one). This is purely additive: existing keys/shapes are untouched, so no
other discover.py consumer (items/characters/sets, which don't have this
nested reference) is affected.

`build_dataset.py`'s weapon-building loop reads the companion file's text
where present (`None` otherwise) and passes it alongside the primary effect
texts as a new, optional, index-aligned parameter.

`brotato_coach/builders/weapons.py::_weapon_effect_record` gains an optional
second argument (the companion file's raw text, or `None`). When present, it
parses that file too and nests its resource dict under a `burning_data` key
on the effect record (e.g. `eff["burning_data"] = {"chance": 1.0, "damage":
10, "duration": 5, "spread": 0, "scaling_stats": [...], "is_global_burn":
False}`) rather than flattening it — avoids field-name collisions with the
outer effect record (both have unrelated `value`/`custom_key` boilerplate).

## `aggregate_proc_dps` refactor

Today `build_weapon_record` (`brotato_coach/builders/weapons.py:56-65`)
hardcodes a single `if model["damage_source"] == "weapon_damage"` branch
calling `calc.proc_line(...)`. This generalizes into a small dispatch so
`burn_dot` (and future proc types) plug in without another rewrite:

- `brotato_coach/calc.py`: new `burn_dps_line(damage_per_tick: float,
  tick_interval: float = 0.5) -> tuple[float, float]`, returning `(dps0,
  0.0)` — same `(dps0, slope)` tuple shape as `proc_line`/`dps_line`, so
  `sum_lines` keeps working unmodified.
- `brotato_coach/builders/procs.py`: new entry for `effect_burning`:
  `{"damage_source": "burn_dot", "tick_interval": 0.5}`. Unlike
  `_EXPLODE_MODEL`, this model has no weapon-specific numbers baked in — the
  per-weapon `damage`/`duration`/`chance` come from that weapon's own
  `burning_data` sub-record (see plumbing above), not from the model dict.
- `brotato_coach/builders/weapons.py`: the proc loop dispatches on
  `damage_source`:
  - `"weapon_damage"` → existing `calc.proc_line(...)` path, unchanged.
  - `"burn_dot"` → read `bd = eff.get("burning_data") or {}`; `chance =
    bd.get("chance", 0.0)` (burn's own engine default — not exploding's
    `1.0`); check the two preconditions above using this weapon's own
    computed `ct` (cycle_time) and `bd["damage"]`/`bd["duration"]`; on pass,
    call `calc.burn_dps_line(bd["damage"], model["tick_interval"])` and fold
    into `proc0`/`proc_slope`; on fail (including `chance == 0.0`, i.e. no
    `burning_data` resolved at all), append to `unmodeled` (same as an
    effect with no model).
- No dataset schema change: `proc_dps_at_zero_rd`/`proc_dps_slope_per_rd`
  stay the two existing fields — `sum_lines` doesn't care which
  `damage_source` a contribution came from.

## `stat_range` projectile-speed nuance

Docs-only addition, no calc/schema change.

- `recovered/singletons/weapon_service.gd:113-116`
  (`_set_common_ranged_stats`): `if from_stats.increase_projectile_speed_with_range:
  ... new_stats.projectile_speed = clamp(from_stats.projectile_speed +
  (from_stats.projectile_speed / 300.0) * stat_range, 50, 6000) as int`.
- Verified: only Flamethrower T2–T4 ship with
  `increase_projectile_speed_with_range = true`
  (`grep -rl "increase_projectile_speed_with_range = true" extracted/weapons/`).
  Every other weapon's projectile speed is unaffected by `stat_range`.
- Add one clause to `brotato_coach/builders/mechanics.py`'s `stat_range`
  entry and the matching bullet in `docs/stat-mechanics.md`, citing the line
  above and the flag-gated weapon list.

## Testing (TDD)

- `calc.burn_dps_line`: pure unit tests (zero damage, typical damage,
  default vs. custom tick_interval).
- `discover.py`: a fixture effect file referencing a `burning_data`
  ext_resource resolves to the right companion path in
  `effect_burning_data_paths`; an effect with no such reference (e.g. an
  exploding effect) produces no entry.
- `_weapon_effect_record`: with a companion text given, the returned effect
  dict nests the companion's fields under `burning_data`; with no companion
  text (existing callers), behavior is unchanged.
- `procs.py`'s `effect_burning` entry: assert `damage_source == "burn_dot"`
  and the model dict shape.
- `weapons.py` builder: a synthetic weapon with a `burning_data`-shaped
  effect that satisfies both preconditions (contributes to
  `proc_dps_at_zero_rd`) and one that violates the cycle_time precondition
  (falls back to `unmodeled_effects`), plus a `chance < 1.0` case and a
  missing-`burning_data` case (both fall back).
- `test_mechanics.py`: `stat_range`'s summary text mentions
  `increase_projectile_speed_with_range`.
- Regenerate `docs/proc-mechanics.md` with a new "Burning effect" section,
  evidenced the same way as the existing "Exploding effect" section.
- `uv run python build_dataset.py` locally to confirm the six shipped burn
  weapons now show nonzero `proc_dps_at_zero_rd` and empty
  `unmodeled_effects` for the burn key specifically (not committed — dataset
  is gitignored).
