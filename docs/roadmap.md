# spud-coach — Roadmap

Coarse, high-level next steps — a shared backlog, not committed timelines.
Ordered by priority.

Shipped (#3, #4): proc-aware DPS with verified exploding-effect models,
loadout set-bonus reasoning, the complete 16-stat mechanics table, and
localized names/effect text (dataset schema v2).

## Ship (code-complete, publish pending)

- **Publish** — the `spudcoach` 0.2.0 distribution and `uvx spudcoach` entry
  point are ready; remaining are the outward-facing steps: PyPI release, the
  spudcoach.fyi install page, and MCP registry + awesome-mcp-servers listings.
  Checklist: Phase C of
  `docs/superpowers/plans/2026-07-02-roadmap-implementation.md` (each step
  needs an explicit go-ahead).

## Bigger build

- **Incorporate enemy data** — build a bestiary layer from
  `extracted/entities/units/enemies/` (path verified: 91 `.tres` records) so
  the coach can give threat- and wave-aware advice (what's coming at a given
  wave / danger level), not just build-only reasoning. Needs its own
  implementation plan; survey commands are in the deferred section of the
  Phase A/B plan.

## Backlog (successors from shipped work)

- **Model the rest of the proc worklist** — only exploding procs carry
  expected DPS today; every other on-hit effect contributes zero and is
  surfaced in `unmodeled_effects`. `docs/proc-mechanics.md` holds the
  evidence-gated worklist (`effect_burning` ×19 is the top entry). The first
  non-`weapon_damage` model also triggers the deferred `aggregate_proc_dps`
  extraction.
- **stat_range projectile-speed nuance** — `weapon_service.gd::
  _set_common_ranged_stats:115` scales projectile speed off `stat_range`, but
  only for weapons with `increase_projectile_speed_with_range` (clamped
  50–6000). Verify and encode with the flag condition.
