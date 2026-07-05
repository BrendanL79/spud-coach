# Brotato Coach / datamining — project guide

Two deliverables live here:
1. A datamining archive of Brotato (`extracted/` data + `recovered/` decompiled code).
2. The **Brotato coach** — a deterministic theorycrafter shipped as an MCP server
   (Python package `brotato_coach`), public at https://github.com/BrendanL79/spud-coach (MIT).

## Build & test
- Python 3.11+, managed with **uv**. `uv sync` to set up; `uv run pytest` to test
  (TDD is the norm — write the failing test first).
- Build the dataset: `uv run python build_dataset.py`. `--game-version` auto-detects from
  `recovered/singletons/progress_data.gd`'s `VERSION` constant; `--generated-at` defaults to the
  current UTC time. Pass either explicitly to override (e.g. a pinned/reproducible build).
- Run the MCP server: `uv run python -m brotato_coach.server` (cwd must be the repo root).

## CRITICAL: never commit or redistribute the dataset
`data/brotato.json` is derived from Brotato's copyrighted game files. It is **gitignored and was
purged from git history**; the public repo ships zero game data. Do NOT re-add or commit it —
regenerate it locally via `build_dataset.py` from your own extraction. Same for `extracted/`,
`recovered/`, and `game_files/` (all gitignored).

## Architecture (one-way data flow)
- The **build step** (`build_dataset.py` + `brotato_coach/builders/`) is the only code that reads
  `extracted/`.
- The **MCP server** reads only `data/brotato.json` — never `.tres`. Keep this separation.
- Pure logic (`calc.py`, `query.py`, `answers.py`, `evaluate.py`) has no I/O and is unit-tested
  against hand-verified values; server tools are thin wrappers over it.
- Game-mechanics reference docs are in `docs/`. Evidence citations (file/function/line) must be
  re-pinned against the decompiled source at write time — never carried forward from notes — and
  reviewers verify citations against the source. Carried-forward evidence has misattributed
  functions before.

Now say: "I've reviewed the project memory."
