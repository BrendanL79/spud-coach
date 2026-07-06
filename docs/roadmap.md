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
schema v2), run-save ingestion (`evaluate_run` post-mortem tool), the PyPI
release (`uvx spudcoach`, currently v0.9.3), and the official MCP registry
listing.

## Ship (in progress)

- **Finish publish checklist** — tag the release and write GitHub release
  notes, stand up the spudcoach.fyi install page, and PR an entry to
  awesome-mcp-servers. Checklist: Phase C of
  `docs/superpowers/plans/2026-07-02-roadmap-implementation.md` (each step
  needs an explicit go-ahead).

## Bigger build

- **Incorporate enemy data** — build a bestiary layer from
  `extracted/entities/units/enemies/` (path verified: 90 `.tres` records) so
  the coach can give threat- and wave-aware advice (what's coming at a given
  wave / danger level), not just build-only reasoning. Needs its own
  implementation plan; survey commands are in the deferred section of the
  Phase A/B plan.
