# Class-bonus capture, surfacing & advisory — design

**Date:** 2026-07-13
**Status:** Approved (Option A)
**Scope:** Capture the `ClassBonusEffect` character kits the build step currently
drops, surface them, and reason about them advisorily — **without** changing any
computed DPS number.

## Problem

The Crazy character card shows "+100 Range with Precise weapons", but a coach
session evaluating Crazy never sees it. The MCP server reads only
`data/brotato.json`, and that file has no representation of the bonus — just an
opaque token `special_effects: ["effect_weapon_class_bonus"]`.

### Root cause

The six affected characters carry a `ClassBonusEffect`
(`res://effects/items/class_bonus_effect.gd`): a conditional stat bonus applied
to weapons of a given set. Its `.tres` payload carries `value`, `set_id`,
`stat_name`, and `stat_displayed_name` (e.g. `crazy_effect_1.tres`:
`value=100`, `set_id="set_precise"`, `stat_name="max_range"`,
`stat_displayed_name="stat_range"`).

`brotato_coach/builders/characters.py:28-30` classifies effects into
`gain_modifiers`, `stat_*` `flat_bonuses`, or a bare-string `special_effects`
catch-all. A `ClassBonusEffect` matches none of the first two, so it falls into
the catch-all, which appends **only the effect `key`** and discards the entire
payload.

The parser already exposes the dropped fields — confirmed:
`parse_tres(crazy_effect_1).resource` includes `set_id`, `stat_name`,
`stat_displayed_name`, `value`. Only the builder discards them.

### Blast radius — all six `ClassBonusEffect` characters

| Character | value | `set_id` | `stat_name` | `stat_displayed_name` | Card text |
|---|---|---|---|---|---|
| Crazy | 100 | set_precise | max_range | stat_range | +100 Range with Precise weapons |
| Artificer | 100 | set_tool | stat_percent_damage | stat_percent_damage | +100% Damage with Tool weapons |
| Brawler | 50 | set_unarmed | attack_speed_mod | stat_attack_speed | +50 Attack Speed with Unarmed weapons |
| Doctor | 200 | set_medical | attack_speed_mod | stat_attack_speed | +200 Attack Speed with Medical weapons |
| Ghost | 10 | set_ethereal | damage | stat_damage | +10 Damage with Ethereal weapons |
| Wildling | 30 | set_primitive | lifesteal | stat_lifesteal | +30 Lifesteal with Primitive weapons |

The effect `key` field is cased inconsistently in source (`effect_weapon_class_bonus`
for Crazy/Artificer, `EFFECT_WEAPON_CLASS_BONUS` for the other four); both are the
same `class_bonus_effect.gd` script.

## Why "apply to matching-set weapons" is advisory, not DPS math

The coach's DPS engine is **ranged-damage-only**. `builders/weapons.py` builds each
weapon's line via `calc.dps_line(base_damage, _rd_coefficient(scaling_stats), ct,
accuracy)` — parameterized solely by RD. `answers.weapon_dps` evaluates
`dps(rd) = dps_at_zero_rd + dps_slope_per_rd * rd`; the character enters only through
`display_stats` (stat-gain modifiers). It consumes **none** of the five class-bonus
stats (range, attack-speed, lifesteal, percent-damage, flat damage).

Consequence, verified against the dataset: **35 of 36 Precise weapons have a zero RD
slope** (29 melee-scaling, 1 ranged). For a melee/crit character like Crazy the
`dps(rd)` lines are near-flat constants, and the `max_range` bonus has literally zero
consequence in the model. Folding class bonuses into DPS is therefore either a no-op
(range/lifesteal) or requires first teaching the engine to consume melee/percent/
elemental scaling — a much larger change that sits *underneath* this gap and is
deferred to its own work (see Roadmap seed below). This spec captures and reasons
about the effect honestly without misrepresenting the math.

## Design

### 1. Schema — `class_bonuses` (bump `DATASET_VERSION` v4 → v5)

Every character record gains a `class_bonuses` list (empty for characters without
one). The six affected characters get one entry:

```json
"class_bonuses": [
  {"set_id": "set_precise", "set_name": "Precise",
   "stat": "max_range", "stat_displayed": "stat_range", "value": 100}
]
```

- `stat` = raw `stat_name` (the engine stat); `stat_displayed` = `stat_displayed_name`
  (the localization/display key). Both retained: `stat` is the join key to mechanics,
  `stat_displayed` reproduces the card wording.
- The `effect_weapon_class_bonus` / `EFFECT_WEAPON_CLASS_BONUS` token is **removed**
  from `special_effects` — it is now structured data, not an opaque flag.

### 2. Builder — `builders/characters.py`

Add a branch before the catch-all `else`:

- Discriminator: the parsed effect resource has a non-empty `set_id`
  (case-insensitive `key == "effect_weapon_class_bonus"` as a secondary guard).
- Emit a `class_bonuses` entry `{set_id, set_name, stat, stat_displayed, value}`
  instead of appending to `special_effects`.
- `set_name` resolved via a `set_names: dict[str, str]` map passed in from
  `build_dataset.py` (sets are built before characters), with a title-cased
  fallback (`set_precise` → `Precise`). Mirrors the existing optional `tr` param —
  keeps the function pure and unit-testable.

`build_dataset.py` threads the built sets' `{id: name}` map into the character
builder call.

### 3. Advisory reasoning — `answers.py` + `evaluate_run`

New pure helper:

```
character_class_synergy(ds, character, weapon_names) ->
  {"bonuses": [ {set_id, set_name, stat, stat_displayed, value,
                 matched_weapons: [names in that set]} ], ...}
```

For each of the character's `class_bonuses`, report which of `weapon_names` belong
to the set and the bonus they receive. Pure, no I/O, unit-tested.

`evaluate_run` gains a `class_synergy` section built from the parsed loadout — e.g.
a Crazy post-mortem reports *"Precise weapons (Knife, Dagger, …) get +100 Range on
this character."* No DPS number changes.

### 4. Surfacing — `server.py`

- `get_character` returns `class_bonuses` automatically; update its docstring to
  list the new field.
- Update the `read_me` primer to mention class bonuses **and** state the caveat:
  range / attack-speed / lifesteal bonuses are build context, **not** folded into
  the RD-only DPS line.

No new MCP tool — `character_class_synergy` reaches sessions through `evaluate_run`,
and static kit data through `get_character`. (A dedicated tool is YAGNI until asked.)

### 5. Roadmap seed — `docs/roadmap.md`

New "Bigger build" entry for the deferred B work: extend the DPS engine beyond RD to
consume melee / percent / elemental scaling. Record the origin (the RD-only model
was built while grinding Ranger) and the evidence (35/36 Precise weapons have zero RD
slope, so melee-character DPS lines are near-flat today, and class bonuses on those
stats cannot enter the line).

## Testing (TDD — failing tests first)

- **Builder** (`tests/` for `build_character_record`): each of the six characters
  produces the correct single `class_bonuses` entry; a non-class character yields
  `[]`; the opaque token no longer appears in `special_effects`; `set_name`
  resolves correctly (map hit and title-case fallback).
- **Answers**: `character_class_synergy` matches Crazy's equipped Precise weapons and
  reports +100 range; ignores non-matching weapons; empty for a character with no
  class bonus. `evaluate_run` output includes a `class_synergy` section.
- **Schema**: bump assertion if a schema-version test exists.

After green: rebuild `data/brotato.json` via `uv run python build_dataset.py`, then
`uv run ruff check .` and `uv run pytest` both clean.

## Out of scope (deferred to the B session)

- Any change to computed DPS.
- Folding percent-damage / flat-damage into the DPS line (would move Artificer/Ghost
  numbers).
- Re-parameterizing the engine by range / attack-speed / lifesteal.

## Evidence citations (re-pin against source at implementation time)

- `extracted/effects/items/class_bonus_effect.gd` — `ClassBonusEffect.apply` /
  `get_args` (card text = `[value, tr(stat_displayed_name), tr(set.name)]`).
- `extracted/items/characters/crazy/crazy_effect_1.tres` (and the five siblings) —
  per-character payloads.
- `brotato_coach/builders/characters.py:28-30` — the discarding catch-all.
- `brotato_coach/builders/weapons.py` (`_rd_coefficient`, `build_weapon_record`) and
  `brotato_coach/calc.py` (`dps_line`), `brotato_coach/answers.py` (`weapon_dps`) —
  the RD-only DPS model.
