# `read_me` orientation tool — design

Date: 2026-07-06
Status: approved pending user review

## Problem

A model connecting to spud-coach mid-conversation knows nothing about the
dataset's conventions: that DPS is served as RD-parameterized lines at a
zero-stat baseline, what `cycle_time` and `classified_effects` mean, which
assumptions (`enemies_hit` constants, crit unmodeled) are baked into the
numbers, or which of its own training-data beliefs about Brotato mechanics
the dataset supersedes. The server's `_INSTRUCTIONS` string covers only
"don't answer from memory" — it can't hold a primer, and many clients
surface server instructions poorly or not at all. Result: consumers misread
`dps_at_zero_rd` as realized DPS, quote proc numbers without their
assumptions, or re-derive stat mechanics from stale priors.

## Decision summary (approved 2026-07-06)

1. **Scope: verified facts + short game intro.** The primer carries the
   source-verified mechanics distillation and dataset conventions, plus a
   short (~10 line) waves/shop/economy orientation for models with weak
   Brotato priors. The intro is explicitly labeled as orientation-grade
   (training-data knowledge), not source-verified.
2. **Shape: single blob, no arguments.** One call returns the whole primer
   (~150–200 lines of markdown, roughly 1.5–2.5k tokens). No section
   parameter — session-start usage means the model should read everything;
   sectioning adds calls and a way to skip the assumptions.
3. **Home: package prose + live provenance.** The primer lives as a module
   constant in a new `brotato_coach/orientation.py`; the tool interpolates
   the loaded dataset's provenance (`game_version`, `schema_version`,
   `generated_at`) into the primer header at call time. This supersedes the
   roadmap note suggesting dataset-build-time distillation: the assumptions
   the primer documents (zero-stat baseline, RD lines, `enemies_hit`
   constants, category schema) are conventions of the builder/server *code*,
   which ships with the package — not of any one dataset. The one-way-flow
   rule protects game data (`extracted/` → dataset); the primer is our own
   MIT-licensed prose, so embedding it in the package violates nothing, and
   it stays correct against already-built datasets without a schema bump.

## Architecture

### New module: `brotato_coach/orientation.py`

- `PRIMER: str` — module-level markdown constant containing the full primer
  with a `{provenance}` placeholder in its header (str.format-style, single
  placeholder).
- `read_me_payload(ds: dict) -> dict` — pure function (no I/O), returns
  `{"primer": <str>}` with the provenance line rendered from
  `ds.get("game_version")`, `ds.get("schema_version")`,
  `ds.get("generated_at")`. Any missing key renders as `unknown` — never an
  error.

Provenance line format (exact):

```
Dataset: Brotato v{game_version} — schema v{schema_version}, generated {generated_at}.
```

### Server registration (`brotato_coach/server.py`)

- New `read_me()` tool, no parameters, thin `_safe` wrapper over
  `orientation.read_me_payload(ds)` — same pattern as the existing tools.
- Docstring is the discovery surface; it must open with the call-me-first
  contract. Exact docstring:

  > Return the orientation primer for this server: how Brotato's core loop
  > works, the source-verified stat mechanics, and — critically — what this
  > dataset's precomputed fields mean and which assumptions they bake in.
  >
  > Call this ONCE at the start of a session, before any other tool. Without
  > it you will misread the DPS fields (they are RD-parameterized lines at a
  > zero-stat baseline, not realized DPS) and miss the model's documented
  > assumptions.

- `_INSTRUCTIONS` gains one sentence directing clients to call `read_me`
  first, appended after the existing "never answer from memory" guidance:

  > Start each session by calling read_me once — it explains the dataset's
  > conventions and the assumptions behind every precomputed number.

## Primer content outline

The plan carries the full verbatim primer text; this spec fixes the outline,
sourcing rules, and required sentinel content. Sections, in order:

1. **Header** — what this server is (authoritative, built from the game's
   own data files, not training data) + the interpolated provenance line.
2. **Game basics** *(label verbatim: "Orientation only — general game
   knowledge, not source-verified.")* — waves and the between-wave shop;
   materials are simultaneously currency and XP; danger levels 0–5; 6 weapon
   slots; two same-tier copies of a weapon merge into one of the next tier;
   a standard run is 20 waves, then optional endless.
3. **Verified stat mechanics** (distilled from `docs/stat-mechanics.md`) —
   the 5 capped stats and which caps bind from wave 1 (dodge 60, curse 0;
   HP/speed/crit-chance caps are effectively infinite until an item sets
   one); positive curse scales enemy damage/HP (sqrt factor), negative curse
   is clamped harmless; negative armor and negative luck are asymmetrically
   punishing (amplification / division, not mirror-image subtraction);
   harvesting pays gold AND XP each wave, grows 5%/wave while positive,
   decays in endless, and drains gold when negative; attack_speed is a
   universal cooldown multiplier (never dead weight); hp_regeneration ≤ 0 is
   a harmless no-op (unlike negative lifesteal); percent_damage is a
   multiplicative global weapon-damage bonus (floor 1 damage); range adds
   flat range, melee weapons get half; character gain modifiers multiply the
   raw effects-sum at display time.
4. **Dataset conventions and model assumptions** — DPS is served as a line
   in ranged damage: `dps_at_zero_rd` + `dps_slope_per_rd` × RD, computed at
   a zero-stat baseline (all other stats 0, accuracy applied); `cycle_time`
   is seconds per attack including recoil; proc DPS lines exist for three
   damage sources — weapon_damage (exploding re-deals the weapon's own hit),
   burn_dot, companion_ranged_stats (spawned projectiles with their own
   stats); `enemies_hit` assumption constants: exploding assumes ONE *other*
   enemy in the blast (the direct target is excluded by the engine — the
   proc is worth zero against a lone enemy), sprays assume 1.0;
   `classified_effects` carries non-DPS effects in 9 categories —
   stat_rider, dynamic, economy, cc, delivery_modifier, drawback, execute,
   stack, structure — each with a one-line meaning; `unmodeled_effects` is
   empty dataset-wide (everything is modeled or classified); crit is NOT in
   any DPS line; the player-level `explosion_damage` stat is unmodeled.
5. **Tool usage notes** — call `get_filter_options` before passing filter
   values (case-sensitive exact match); API tiers are 1-indexed (1–4 weapons
   / 1–4 items); `stats` parameters use short names (e.g. `ranged_damage`,
   not `stat_ranged_damage`); `explain_stat`/`stat_display_value` take the
   `stat_`-prefixed form.

### Sourcing rules

- Sections 3–4 must be cross-checked claim-by-claim against
  `docs/stat-mechanics.md` and `docs/proc-mechanics.md` at write time (the
  project evidence rule; those docs remain the evidence record with
  `recovered/...` citations).
- The primer itself carries **no** `recovered/...` file:line citations — the
  MCP consumer can't read them; pointing at `explain_stat` for per-stat
  detail replaces them.
- No game data (`.tres` contents, extracted strings) appears in the primer —
  it is handwritten MIT prose about mechanics facts and our own conventions.

## Error handling

- `_safe` wrapper, like every other tool.
- Missing provenance keys → the literal string `unknown` in the provenance
  line; never an exception.

## Testing (TDD)

New `tests/test_orientation.py`:

1. `read_me_payload` with a fake ds (`game_version`, `schema_version`,
   `generated_at` set) → primer contains the exact rendered provenance line.
2. Fake ds missing all three keys → provenance line renders with `unknown`
   three times; no exception.
3. Sentinel-content assertions on the primer: each of the 9 category names;
   `dps_at_zero_rd`; `dps_slope_per_rd`; `zero-stat`; `cycle_time`; the
   verbatim "not source-verified" label; `get_filter_options`.
4. Server registration: `build_server(fake_ds)` exposes a `read_me` tool
   (matching the existing server-test pattern in `tests/test_server.py`),
   and calling it returns a payload whose `primer` is a non-empty string.

Shipped-dataset test (`tests/test_shipped_dataset.py`): calling
`read_me_payload` against the real loaded dataset renders a provenance line
with no `unknown`.

## Ship surface

- `site/index.html`: add `read_me` to the "What you get" section as its own
  one-item group titled "Start here", placed above "Data lookups":
  `read_me — session-start primer: game basics, verified mechanics, and
  what the precomputed fields mean`.
- `docs/roadmap.md` (post-merge): move the `read_me` backlog item into the
  Shipped paragraph, noting the package-prose decision superseding the
  build-time-distillation idea.

## Addendum (2026-07-06, post-approval): item-tier normalization

Fact-checking the primer's tier claim surfaced a pre-existing inconsistency:
weapon records ship tiers 1–4 (from directory names) while item records ship
the raw 0-indexed `.tres` field (0–3), and server docstrings claimed
"weapons 1–6". `runfile.py:12` already declares 1-indexed tiers as the
coach's convention, and 1-indexed (I–IV) is what the game UI shows.
Decision (Brendan): normalize item tiers to 1–4 at build time
(`items.py` tier+1), correct the docstrings, and bump `DATASET_VERSION`
to 3 — as a prerequisite task in this feature's plan, so the primer can
state one simple rule: "tiers everywhere are 1-indexed (1–4), matching the
in-game display." Item tier is only ever equality-filtered (no arithmetic),
so the change is contained to the builder, docstrings, and tests.

## Workflow

- Fresh worktree `read-me-tool`, branch `worktree-read-me-tool` off main
  (created 2026-07-06). PR at the end.
- Old `remaining-weapon-procs` worktree/branch cleaned up (directory itself
  is file-locked pending session exit; git registration and branch deleted).
