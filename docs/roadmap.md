# spud-coach — Roadmap

Coarse, high-level next steps — a shared backlog, not committed timelines.
Ordered by priority; the first three are a near-term batch over the data we
already have.

## Near-term (quick wins over existing data)

- **Factor procs into DPS** — `weapon_dps` computes only the guaranteed
  base-damage line and ignores on-hit chance effects. (A *proc* = "programmed
  random occurrence" — e.g. the Shredder's 50% exploding projectile.) Model the
  expected proc contribution (roughly chance × effect damage × enemies hit) so
  proc/AoE weapons rank honestly.
- **Set-bonus awareness** — weapons now carry class membership (`sets`); add
  loadout set-progress reasoning (e.g. "3 Gun weapons → +20 range at 4
  equipped") and surface active/next set bonuses.
- **Fill `explain_stat` gaps** — only 9 stats currently have mechanics encoded;
  add `stat_ranged_damage` and the other vanilla stats.

## Then

- **Resolve localization / descriptions** — `text_key` fields are unresolved
  pointers, so records carry no human-readable names/descriptions. Wire the
  localization strings so the coach can speak in real in-game item text.

## Bigger build

- ~~**Ingest run saves**~~ — **done.** The `evaluate_run` MCP tool parses a
  real Brotato `run.json` (uploaded inline or read from a path) and returns a
  one-call post-mortem: run context, realized stats, weapon-DPS ranking, set
  progress, and per-item verdicts. Save-format details (the djb2-hashed
  `effects` keys, 0-indexed weapon tiers, character-as-pseudo-item) live in
  `brotato_coach/runfile.py`; the parser validates by structure and fails
  loudly on an unrecognized shape. Feeds the reasoning in
  `docs/run-postmortem-methodology.md`.
- **Incorporate enemy data** — build a bestiary layer from the extracted
  `entities/units/enemies/` tree so the coach can give threat- and wave-aware
  advice (what's coming at a given wave / danger level), not just build-only
  reasoning.

## Ship

- **Ship it** — publish to PyPI (`uvx spudcoach`), stand up the spudcoach.fyi
  install page, and list in the official MCP registry + awesome-mcp-servers.
