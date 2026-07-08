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
section in `evaluate_run` — dataset **schema v4**), the PyPI release
(`uvx spudcoach`, latest **v0.11.0**), and the official MCP registry listing.

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
- **Loadout timing/consistency modeling** — player-reported (2026-07-08, not
  yet source-verified): a loadout of similar-`cycle_time` weapons (e.g.
  several copies of the same weapon) tends to volley in near-unison, dealing
  damage in bursts with a shared dead window between; a loadout with
  staggered `cycle_time`s interleaves attacks for steadier output. Two
  loadouts with identical summed DPS can play very differently, and
  `weapon_dps`/`compare_weapons`/`evaluate_run` currently rank by summed DPS
  alone (see the `read_me` primer's "Attack-timing synchronization is NOT
  modeled" caveat). Possible shape for a future metric: something like a
  variance/spread measure over equipped weapons' `cycle_time` (all weapon
  records already carry it), surfaced as a loadout-level "damage
  consistency" or "synchronization risk" score alongside the DPS ranking —
  needs a source-verified model of how per-weapon attack timers actually
  interact (do they start staggered, sync on reload, etc.) before it can be
  more than a heuristic.
