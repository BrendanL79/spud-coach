# spud-coach — Roadmap

Coarse, high-level next steps — a shared backlog, not committed timelines.
Ordered by priority.

Shipped: proc-aware DPS with verified exploding/burning/companion-projectile
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

## Backlog (successors from shipped work)

- **`read_me` orientation tool** — an MCP tool that returns a primer on the
  game's basic mechanics and this dataset's conventions, meant to be called
  once at the start of a session before any other tool: how stats/waves/shops
  work at a high level, what the precomputed fields mean
  (`dps_at_zero_rd`/`proc_dps_*` as RD-parameterized lines, `cycle_time`,
  `classified_effects` categories), and the model's documented assumptions
  (zero-stat baseline, `enemies_hit` constants, crit unmodeled). Source the
  content from `docs/stat-mechanics.md`/`docs/proc-mechanics.md` distillations
  at dataset-build time rather than hardcoding prose in the server, keeping
  the one-way data flow.
