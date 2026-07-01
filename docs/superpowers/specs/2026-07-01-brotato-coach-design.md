# Brotato AI Coach — Design (Phase 1: Theorycrafter)

**Date:** 2026-07-01
**Status:** Approved design, pre-implementation

## Vision

An AI Brotato coach delivered as a **plugin**, usable from Claude Code and (ideally) Claude Desktop and Web. The coach is *chattable* — a conversational frontend — but its value comes from a **deterministic core**: scripts and reference material holding the game's ground truth (weapon/item/character data, formulas, stat mechanics), so the LLM consults verifiable facts instead of re-deriving them mid-conversation and drifting.

**Guiding principle:** maximize value delivered via actual computation. Anything checkable against the game data or a formula belongs in the deterministic core, so that advice reduces to a simple retrieval/tool call with minimal LLM processing. Subjective rankings (tier lists, "is this good") stay with the LLM, guided by prose reference docs.

## Phasing

1. **Phase 1 — Theorycrafter (this spec).** Reference + math core, no live game state. Answers "what does X do," "compare these," "does this fit my build," "what stats matter." Runs identically on all surfaces (state-free). This is the deterministic foundation the other coaching moments stand on.
2. **Phase 2 — Live coaching (future).** Adds live run/shop state ingestion for in-the-moment "buy or recycle / what to pick" advice. Reuses the Phase 1 core; the `evaluate_item_for_build` tool is the designed seam (feed it *live* stats instead of hypothetical ones).

## Facts-vs-opinion boundary

The core holds **only verifiable computation**: game data, DPS/merge/scaling math, stat caps, and fact-*derived* heuristics (e.g. "does this item's `scaling_stats` match invested stats"). It holds **no subjective rankings**. This is what stops the LLM from re-deriving/drifting, and keeps the core from ever being "wrong about opinions" — it holds none.

## Chosen approach

**Distilled dataset + answer-shaped MCP tools.** An offline build step parses the raw extracted game data once into a single committed, enriched dataset; the MCP server loads that dataset and exposes tools that return finished structured answers. Chosen over (a) a runtime `.tres` parser — disqualified because it requires `extracted/` on disk, breaking Web/Desktop portability and recomputing facts every call; and (b) a SQLite + query-tool design — rejected because LLM-composed queries reintroduce exactly the "re-deriving" fuzziness we want to eliminate, and the dataset is small enough that JSON + typed tools suffices.

## Architecture

Three layers with one build-time boundary:

```
extracted/  (gitignored, regenerable)          ← raw .tres game data
     │
     ▼   build_dataset.py   [run offline, on each Brotato patch]
data/brotato.json  (committed, enriched)        ← THE deterministic core artifact
     │
     ▼   loaded at startup
MCP server (tools: retrieval / calculators / mechanics)
     │
     ▼   connected as a plugin
Claude Code · Desktop · Web                      ← chat frontend(s)
```

The hard boundary is the build step: raw `extracted/` never ships and is never read at runtime; committed `data/brotato.json` is the only thing the server touches. This makes the core portable to Web (self-contained) and reduces patch upkeep to a one-command regeneration.

### Repo layout

```
build_dataset.py          # extracted/ .tres  →  data/brotato.json
data/brotato.json         # committed enriched dataset (the core)
mcp/
  server.py               #   tool registration + startup load
  tools/                  #   one module per tool group (weapons, items, characters, mechanics)
  calc.py                 #   pure DPS / merge / scaling math (no I/O — unit-testable)
docs/                     # reference material (started already)
tools/brotato_inspect.py  # existing run/save inspector (feeds Phase 2 live coaching)
tests/
plugin/                   # packaging manifests for Code / Desktop / Web
```

**Deliberate choice:** `calc.py` is pure functions with zero I/O — the DPS/merge/scaling formulas live there and are directly unit-testable against known values. MCP tools are thin wrappers: load data + call `calc` + shape a finished answer. Verifiable math stays isolated and provable.

## Dataset schema (`data/brotato.json`)

The build step parses every `.tres` and emits enriched records — raw fields **plus** precomputed derivations, so tools are lookups. Five collections:

**`weapons`** — one record per weapon×tier:
```
id, name, tier(1-4), class/sets, base_damage, cooldown, crit_chance/damage,
accuracy, piercing, nb_projectiles, scaling_stats[[stat,coef]...],
burst_mechanic{every_x_shots, multiplier},          # revolver-style reload tax
# precomputed:
cycle_time,                                          # recoil_duration*2 + cooldown/60
dps_at_zero_rd, dps_slope_per_rd,                    # realized (accuracy-adjusted) DPS line
effects[]                                            # data.tres effects (turret/landmine/etc.)
```
The `dps_at_zero_rd` + `dps_slope_per_rd` pair precomputes the whole DPS line — a comparison becomes "read two numbers each," no formula eval unless a specific RD is supplied.

**`items`** — one record per item:
```
id, name, tier, value, tags[],
effects[{key, value, effect_sign, text_key}],
# precomputed flags:
archetype[],            # e.g. "cap_at_current_value" when key~/_cap/ & text_key~/CAP_AT_CURRENT_VALUE/
frozen_stat,            # e.g. Handcuffs → stat_max_hp
scaling_stats[], damage_tags[]
```

**`characters`** — one record per character:
```
id, name, wanted_tags[], banned_item_groups[],
flat_bonuses[{stat, value}],        # Ranger +50 range
gain_modifiers[{stat, pct}],        # Ranger +50% RD, -25% max_hp
special_effects[]                   # no_melee_weapons, etc.
```

**`sets`** — set bonuses by equipped-count (gun 2/3/4/5/6, etc.), each with its effect.

**`stat_mechanics`** — facts from `docs/stat-mechanics.md` encoded as data:
```
per stat: { cap: {stat, cap_key} | null,
            special: "curse_sqrt_penalty" | "regen_zero_safe" | "attack_speed_universal" | ... | null,
            neglectable: bool, never_negative: bool }
```
This lets a tool *answer* mechanics questions ("is attack_speed ever dead weight?" → no; "safe to let regen hit 0?" → yes) instead of the LLM recalling them.

**Provenance:** the build stamps the dataset with `game_version` + `generated_at` so a stale dataset vs. a patched game is detectable. `generated_at` is passed in (sandbox blocks wall-clock calls in scripts).

Every field is objective/computed — no tier lists, no good/bad.

## MCP tool surface (v1)

Every tool returns a **finished structured answer**, never raw rows to reassemble. Signatures illustrative.

**Retrieval / filter** (lookups over the dataset):
- `get_weapon(name, tier?)` → full record incl. precomputed DPS line
- `get_item(name)` → effects, tags, archetype flags, frozen_stat
- `get_character(name)` → kit (wanted/banned tags, gain modifiers, flat bonuses)
- `get_set(class)` → bonuses by equipped count
- `list_weapons(class?|scaling_stat?|tier?)` / `list_items(tag?|scaling_stat?|archetype?|tier?)` → filtered summaries

**Calculators** (parametric math — the only place a runtime variable enters):
- `weapon_dps(name, tier, stats{ranged_damage, ...})` → realized DPS + breakdown
- `compare_merge_paths(weapon, pathA, pathB, rd_range?)` → winner, RD-independence, crossover RD if lines cross
- `compare_weapons(names[], stats{})` → ranked DPS table at the given stats

**Mechanics** (encoded ground-truth from `stat_mechanics`):
- `explain_stat(stat)` → cap, special behavior, neglectable/never-negative flags
- `stat_display_value(character, stat, raw_value)` → applies character gain modifiers (raw RD 6 → displayed 9 for Ranger)

**Flagship — build-fit evaluator:**
- `evaluate_item_for_build(item, character, current_stats{})` → structured verdict computing, per effect, **live / wasted / harmful** and *why*. Handcuffs on Ranger returns: `+8 ranged → live`; `+8 melee → wasted (character banned from melee)`; `+8 elemental → wasted (0 investment)`; `hp_cap → freezes stat_max_hp at current value (harmful, survivability)`. The full hand analysis, as one deterministic call. This tool is the Phase 2 seam.

**Dataset introspection:**
- `check_dataset_version()` → `game_version` + `generated_at`, for freshness confirmation after a patch.

## Error handling

The tools face an LLM, so failures must be legible:
- *Unknown name* → structured "not found" with fuzzy suggestions (`did_you_mean`), so the LLM self-corrects instead of hallucinating.
- *Missing/uninitialized dataset* → server fails fast at startup with "run `build_dataset.py` first."
- *Stale dataset* → tools surface `game_version`; `check_dataset_version` confirms freshness.
- *Bad parametric input* (negative tier, unknown stat key) → validation error naming the offending field.
- **Principle:** every tool returns either a valid finished answer or a structured error object — never a partial/ambiguous result the LLM might narrate as fact.

## Testing (pytest)

The facts-only design makes everything verifiable:
- **`calc.py` unit tests against this session's hand-computed golden values**: Minigun-vs-Revolver slopes; LaserGun II+II vs III+I near-coinflip; Shredder/Laser/Minigun T4 DPS table; Ranger raw-RD-6 → displayed-9. Code disagreeing with hand-verified numbers fails the test.
- **Dataset build validation**: after `build_dataset.py`, assert schema completeness (record counts in expected ranges, no null required fields, every weapon has all game-present tiers) — malformed extraction caught at build time, not query time.
- **Tool integration tests**: golden input→output for `evaluate_item_for_build` (Handcuffs-on-Ranger must yield the live/wasted/harmful breakdown produced by hand).

## Scope

**In (v1):** build step, committed dataset, MCP server, the Section-3 tool set, tests, and packaging for at least Claude Code (Desktop/Web packaging follows once the core proves out).

**Out (→ Phase 2 live coaching):** reading live `run_v3_0.json`, screenshot/shop OCR, "what should I pick right now," any real-time loop. `evaluate_item_for_build` is the seam — Phase 2 feeds it live stats instead of hypotheticals, reusing the same core.

## Open questions / deferred decisions

- **Web/Desktop state ingestion** (Phase 2): local surfaces can read the save file; Web cannot. Resolution deferred to Phase 2 (likely paste/upload of run state).
- **Desktop/Web packaging** (MCP connector vs. Desktop Extension): deferred until the Claude Code core proves out.
- **Dataset split**: single `brotato.json` vs. per-collection files — decide at implementation based on size; not load-bearing for the design.
