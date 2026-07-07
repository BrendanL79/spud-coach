# Bestiary Awareness — Design

**Date:** 2026-07-06
**Status:** Approved (brainstorming), pending implementation plan
**Scope:** Base-game (Crash Zone / `zone_1`) enemy + wave-spawn data surfaced through the
spud-coach MCP server, plus threat-aware run post-mortem. Likely the last major pre-1.0 task.

## Motivation

The coach today reasons about builds only — weapons, items, characters, stats. It has no
awareness of what the game throws at the player. The decompiled game data makes enemy and
per-wave spawn behaviour fully legible and deterministic, so we can add a "bestiary" layer that
answers "what's coming at wave N / danger D, and how hard does it hit" — and fold that context
into the existing run post-mortem. This matches the roadmap's "Incorporate enemy data" item.

## Honesty envelope (the spine of the design)

The project's identity is "facts and math, not guesses." Everything this feature reports is
classified as exact, exact-math, exact-range, or explicitly-labelled run-variance. Nothing is
invented precision.

| Facet | Certainty | Presentation |
|---|---|---|
| Enemy identity, base stats, attack profile | Exact | Verbatim from `*_stats.tres` + attack behavior |
| Effective HP / damage / armor at wave N | Exact math | `base + increase_each_wave × (N − 1)` |
| Movement speed | Exact range | `speed ± speed_randomization` |
| Wave composition (types, base counts, timing, repeats) | Exact base | From `zone_1` wave/group/unit `.tres` |
| Realized enemy counts | Run-scaled | Base × documented modifiers (`number_of_enemies %`, co-op) — labelled |
| Elite / horde presence on a given wave | Per-run randomized | Shown as "possible", never guaranteed |

Source basis for per-wave scaling (verified at design time):
`entities/units/enemies/baby_alien/baby_alien_stats.tres` carries
`health_increase_each_wave`, `damage_increase_each_wave`, `armor_increase_each_wave`, and
`speed_randomization`; the `(current_wave - 1)` scaling form appears in `enemies/enemy.gd`
(attack-damage growth). Effective stat at wave N = `base + increase_each_wave × (N − 1)`.

> Note: a bespoke evidence citation (file/function/line) must be re-pinned against the
> decompiled source at write time per the project's docs convention — the paths above are
> orientation, not final citations.

## Dataset schema additions

Bumps `DATASET_VERSION` 3 → 4. Two new top-level arrays in `data/brotato.json`.

### `enemies[]` — full roster

Follows the established "include everything extracted" precedent (the dataset already ships DLC
characters). Every enemy dir under `entities/units/enemies/` that contains a `*_stats.tres`
(this filters out non-enemy entries in that tree, e.g. `attack_behaviors/`, `enemy.gd`,
`patrolling_enemy.gd`). Each record:

```
id, name, display_name, zone_id,
base:     { health, speed, speed_randomization, damage, armor, attack_cd, knockback_resistance },
per_wave: { health, damage, armor },          # the *_increase_each_wave fields
attack:   { kind: melee|charging|ranged|none,
            projectile_damage, projectile_dmg_per_wave, range, ... },
abilities: [ spawner | healer | buffer | exploder | charger | ... ],   # tag list
appears_in: [ normal | horde | elite | endless | boss ]                # provenance (zone_1 base game)
```

Bosses are included as records with base stats + an `abilities: ["bespoke_kit_not_modeled"]`
flag (multi-phase / bullet-hell logic is out of scope — see boundaries).

### `zone_1_waves[]` — base game only

One record per wave 1–20:

```
wave, wave_duration, max_enemies,
groups: [ { enemy_id, base_count (min..max), first_spawn_s, repeats, repeat_interval,
            spawn_chance, min_danger, max_danger, is_horde, is_elite, is_boss, is_loot } ]
```

## Build & discovery

Follows the existing one-way data-flow pattern exactly: `discover` walks `extracted/`, builders
parse `.tres` text into records, `build_dataset.py` wires them in, `dataset.assemble_dataset` /
`validate_dataset` gain the two arrays. Only the build step reads `extracted/`; the server reads
only `data/brotato.json`.

- `discover.find_enemy_dirs(extracted_root)` — enumerate `entities/units/enemies/*`.
- `discover.find_zone_waves(extracted_root)` — enumerate `zones/zone_1/NNN/wave_*.tres` and
  resolve each wave's group → unit chain, mapping `unit_scene` filenames to enemy ids.
- `builders/enemies.py::build_enemy_record(...)`
- `builders/waves.py::build_wave_record(...)`

### Implementation risk (resolve in the plan with a spike)

The attack profile lives in the enemy **`.tscn` scene** (which references an attack-behavior
`.gd` script + params), not in `*_stats.tres`. `.tscn` is the same Godot format as `.tres` but
adds `[node ...]` sections; the current `tres.py` may need a small extension to parse it.
Resolving `unit_scene` filenames → enemy ids for the wave layer is straightforward and low-risk.

**Fallback:** if full `.tscn` node-param parsing proves gnarly, classify attack `kind` from
*which* attack-behavior script the scene references (a cheap string match on the ext_resource
path — e.g. `charging_attack_behavior.gd`, `shooting_attack_behavior.gd`) rather than fully
parsing node parameters. Numeric projectile params degrade gracefully to null when unparsed.

## Pure logic layer

New `bestiary.py` (mirroring `calc.py` / `query.py` — no I/O, unit-tested against hand-verified
values):

- effective-stat resolution at a wave (`base + slope × (N − 1)`, speed as a range),
- danger-gating filter over wave groups,
- `wave_composition` assembly.

## New MCP tools (thin wrappers, matching every existing tool)

- **`get_enemy(name, wave=None)`** — one enemy's record. `wave` omitted → base stats + per-wave
  slopes. `wave` set → also effective stats at that wave (hp/damage/armor resolved, speed as a
  range). Miss → `not_found` + `did_you_mean`.
- **`list_enemies(appears_in=None, ability=None, attack_kind=None)`** — filtered roster
  summaries. Filter values surfaced via `get_filter_options`.
- **`wave_composition(wave, danger=None)`** — flagship reference tool. Base-game composition for
  the wave: per type the base count, first-spawn timing, repeats, danger-gating; the
  `scales_with` modifier list; and `elite_horde: "possible, per-run randomized"`. With `danger`
  set, filters groups by their `min/max_difficulty` gates.
- **`get_filter_options`** gains `enemy_abilities`, `attack_kinds`, `enemy_appears_in`.

## Post-mortem integration

`evaluate_run` gains a `wave_context` section. Given the save's character, danger, and wave
reached:

```
wave_context: {
  death_wave,
  composition:      <wave_composition(death_wave, danger)>,
  newly_introduced: [ enemies first appearing in the ~3 waves before death ],
  effective_threat: [ per present type: effective hp / damage at death_wave ],
  elite_horde_note: "wave N can roll an elite/horde (per-run); if you hit a wall here, that may be why"
}
```

Descriptive (facts about the wave), not prescriptive — consistent with how `evaluate_run`
already reports rather than lectures.

## Orientation

The `read_me` primer gains a short bestiary section: how per-wave scaling works and the one-line
honesty envelope (exact stats, exact base composition, labelled run-variance), so a model reading
it doesn't over-claim elite schedules or realized counts.

## Testing (TDD, per project norm)

- **Builder tests** — hand-verify Baby Alien's `3 + 2×(N−1)` HP curve; a ranged type's attack
  profile; one full wave's group → unit resolution against the `.tres`.
- **Pure-layer tests** (`bestiary.py`) — effective-stat math at several waves; danger-gating;
  `wave_composition` shape.
- **Post-mortem test** — a fixture run save → assert `wave_context` present, correct death-wave
  composition, and that the elite/horde note is a label, not a claim.
- **Dataset validation** — `validate_dataset` gains checks: both arrays present, waves 1–20
  present, every `enemy_id` referenced by a wave resolves to an enemy record.

## Scope boundaries (YAGNI — explicitly out)

- DLC zones 2 / 3 (Abyssal Terrors) — reference-roster enemies may be included per the
  "everything extracted" precedent, but no DLC *wave* modelling.
- Boss multi-phase kits and bullet-hell emission patterns — bosses are records with base stats +
  a "bespoke kit — not modeled" flag.
- Endless-mode `get_endless_factor` scaling beyond wave 20.
- Any prescriptive build advice derived from threat — the post-mortem stays descriptive.
