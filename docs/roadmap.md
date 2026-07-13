# spud-coach — Roadmap

Coarse, high-level next steps — a shared backlog, not committed timelines.
Ordered by priority.

Shipped: the `read_me` session-orientation primer (package prose + live
dataset provenance, superseding the build-time-distillation idea),
1-indexed item tiers matching the in-game display (dataset schema v3),
proc-aware DPS with verified exploding/burning/companion-projectile
models, the full proc-worklist triage (every shipped effect modeled or
classified — `unmodeled_effects` is empty dataset-wide; 9-category
`classified_effects` with metadata like Vorpal's execute chance), loadout
set-bonus reasoning, the complete 16-stat mechanics table (incl. the
`stat_range` projectile-speed nuance), localized names/effect text (dataset
schema v2), run-save ingestion (`evaluate_run` post-mortem tool),
**bestiary awareness** (enemy records with per-wave stat scaling, attack
profile, and ability tags; base-game Crash Zone per-wave spawn composition
via `get_enemy` / `list_enemies` / `wave_composition`; and a `wave_context`
section in `evaluate_run` — dataset **schema v4**), **per-weapon cadence
reporting** (verified `cooldown_jitter` model — attacks/sec, damage/attack,
cadence label, and gap range surfaced on `weapon_dps`, `compare_weapons`, and
`evaluate_run`, with burst-reload weapons flagged), the PyPI release
(`uvx spudcoach`, latest **v0.12.0**), and the official MCP registry listing.

## Bigger build

- **Wire achievements into the dataset** — the achievement/challenge builder
  (`brotato_coach/builders/achievements.py`) and its gather script
  (`tools/gather_achievements.py`) are merged (#12) as prep, but nothing in
  `build_dataset.py` references them yet: achievement records aren't in the
  dataset. Next step is folding them into the build (and deciding on an MCP
  surface — e.g. "what does this character/item unlock").
- **Bestiary follow-ups** — extend past base-game Zone 1: DLC zones 2/3
  (Abyssal Terrors) wave data; boss/elite multi-phase kits (currently flagged
  `bespoke_kit_not_modeled` rather than modeled); and richer `appears_in`
  provenance so horde/elite/endless-only enemies carry a label instead of an
  empty list. Deferred test-hardening minors are logged in the bestiary
  implementation plan/review notes.
- **Loadout timing/consistency modeling** — the 2026-07-08 player-reported
  hypothesis (similar-`cycle_time` weapons volley in near-unison; propose a
  cycle_time-spread "synchronization risk" score) is **refuted by source**:
  the engine randomizes each shot's cooldown with jitter that grows with
  weapon count, deliberately de-syncing volleys (`weapon.gd:337-354`; see
  `docs/cadence-mechanics.md`). A spread heuristic would advise backwards.
  Per-weapon cadence shipped 2026-07-09 (attacks_per_second, damage_per_attack,
  cadence label, verified gap_range_s). A genuine loadout-level metric would
  require statistically superposing N independent randomized cooldown streams
  (expected fraction of time with zero weapons firing / longest expected gap)
  — a Monte-Carlo estimate, not a spread heuristic — and remains a possible
  future item if demand appears.
- **Cooldown floor-skew (nominal DPS overstates fast multi-weapon builds)** —
  the per-shot cooldown is drawn from `rand_range(max(1, basis - Δ), basis + Δ)`
  (`weapon.gd:337-349`). When `basis - Δ < 1` the low bound floors at 1, skewing
  the mean cooldown above basis, so the weapon fires slightly slower than basis
  implies. This binds for fast weapons at high weapon counts (e.g. 6x Minigun,
  basis 3 -> mean 3.8, ~13% slower). The coach's `cycle_time`/DPS use raw basis
  and do not model this, so nominal DPS modestly overstates those builds. Small
  and situational; a corrected effective-cooldown model could fold `E[cooldown]
  = (1 + basis + Δ)/2` in the floor-binding regime if it proves to matter.
- **DPS engine beyond ranged damage** — the DPS model is RD-only
  (`calc.dps_line` + `builders/weapons.py:_rd_coefficient`): it consumes only
  ranged_damage, ignoring melee / percent / elemental damage scaling. Origin:
  it was built while grinding Ranger. Consequence: 35 of 36 Precise weapons
  have a zero RD slope (melee-scaling; verified against the shipped dataset —
  `dps_slope_per_rd == 0` for 35 of the 36 weapons whose `sets` include
  Precise), so for melee/crit characters like Crazy
  the `dps(rd)` lines are near-flat constants and class-bonus stats (range,
  attack-speed, lifesteal) cannot enter the line at all. A stat-aware DPS model
  would parameterize by the weapon's real scaling stat and fold in flat/percent
  damage — a larger change that touches every weapon number; its own spec.
