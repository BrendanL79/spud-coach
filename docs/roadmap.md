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
(`uvx spudcoach`, latest **v0.12.0**), the official MCP registry listing, and
the **stat-aware, game-exact DPS engine** (dataset schema v6, replacing the
old RD-only line model) — melee/elemental/engineering scaling, `%damage`,
attack speed, and crit chance now all move DPS correctly, a `stat_gradient`
tool ranks which stat to buy next, and `weapon_dps`/`compare_weapons` accept
a full stat block plus a `loadout` for set-bonus reasoning (see
`docs/dps-engine.md`).

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
- **`nb_projectiles` multiplication** — the stat-aware DPS engine does not
  multiply a weapon's direct-hit line by its pellet/projectile count. Real
  DPS from spread weapons depends on how many pellets actually land, which
  depends on enemy density and positioning with no closed form the engine
  can evaluate today; a flat multiply would overstate them against a single
  target. Needs an `aoe_enemies_hit`-style assumption constant, not a
  straight multiply. See `docs/dps-engine.md`'s "Not modeled" section.
- **Runtime-aware burn uptime** (deferred from CodeRabbit's PR #17 review) —
  burn-proc eligibility is a build-time gate in
  `brotato_coach/builders/weapons.py`: a burn ships as a `burn_dot` proc only
  if `chance == 1.0` and the weapon's ZERO-attack-speed cycle time fits inside
  the burn window (`duration * tick_interval`). Runtime attack speed never
  re-gates it, so (a) heavily negative-AS builds can stretch the cycle past
  the window and the static line overstates burn uptime, and (b) chance < 1.0
  burns are dropped entirely even when a fast weapon proccing at 50% sustains
  real burn DPS. A proper fix moves the gate into `calc.py` at query time:
  compute uptime from the stat-adjusted cycle time and expected re-ignition
  rate (`chance` per hit), scaling the burn line by
  `min(1, window / (cycle_time / chance))`-style coverage instead of a binary
  include/exclude. Deferred because it changes the proc descriptor schema
  (burn procs would need chance + window carried through) and deserves its
  own hand-verified test vectors; the primer's burn caveat covers the gap
  advisorily meanwhile.
- **Gradient steps for survivability** — `stat_gradient` ranks stats purely
  by DPS impact; a stat that matters for survival but not damage (armor,
  dodge, HP, regen, lifesteal) never appears on its gradient by design. A
  survivability-focused sibling metric (e.g. expected-damage-taken delta per
  stat point) would need its own model of incoming damage and enemy
  behavior — out of scope for this DPS-focused pass but a natural next
  "which stat should I buy" tool if demand appears.
- **Class-bonus fold-in as the engine's natural v2** — the engine can now
  consume per-set weapon-local stat grants via `set_bonus_pct` and stat
  adjustments (`docs/dps-engine.md`'s step B); `per_hit_damage` already
  exposes a `set_bonus_pct` parameter for weapon-class-bonus percent grants,
  just unfed by any caller today. PR #16's advisory character class bonuses
  (surfaced via `get_character`/`evaluate_run`'s `class_synergy`, e.g.
  Crazy's +100 range to Precise weapons) graduating from advisory text into
  actual DPS deltas is the natural next step now that the plumbing exists.
