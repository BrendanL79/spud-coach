# `read_me` Orientation Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a no-argument `read_me` MCP tool that returns a session-start
primer (game basics, source-verified stat mechanics, dataset conventions and
model assumptions), and make the tier convention it documents true by
normalizing item tiers to 1-indexed.

**Architecture:** The primer lives as a markdown constant in a new
`brotato_coach/orientation.py` with a pure `read_me_payload(ds)` function
that interpolates dataset provenance at call time; `server.py` registers a
thin `_safe` wrapper. A prerequisite task normalizes item tiers from the raw
0-indexed `.tres` field to the 1-indexed convention the game UI shows and
the coach already claims (`runfile.py:12`), bumping `DATASET_VERSION` to 3.

**Tech Stack:** Python 3.11+, uv, pytest, FastMCP (`mcp.server.fastmcp`).

**Spec:** `docs/superpowers/specs/2026-07-06-read-me-tool-design.md`

## Global Constraints

- Work ONLY in the worktree `C:\Users\brend\src\brotato-exam\.claude\worktrees\read-me-tool`
  (branch `worktree-read-me-tool`). Before your first commit, run
  `git rev-parse --show-toplevel` and verify it prints exactly that path;
  if it does not, STOP and report NEEDS_CONTEXT — do not commit anywhere else.
- NEVER commit `data/brotato.json`, `extracted/`, `recovered/`, or
  `game_files/` — they are gitignored, derived from copyrighted game files,
  and were purged from history. `git status` must never show them staged.
- One-way data flow: the MCP server reads only `data/brotato.json`, never
  `extracted/` or `recovered/`. Only `build_dataset.py` + `brotato_coach/builders/`
  read game files.
- All test commands run as `uv run pytest ...`; lint with `uv run ruff check .`
  before each commit and fix what it reports.
- The primer text in Task 2 is copy-paste-grade: transcribe it VERBATIM.
  Do not paraphrase, reorder, or "improve" it — its claims were cross-checked
  against `docs/stat-mechanics.md` and `docs/proc-mechanics.md` at plan time.
- The primer must contain no `recovered/...` file citations (MCP consumers
  can't read them).
- Exact strings that must appear verbatim (tests assert them):
  provenance format `Dataset: Brotato v{game_version} — schema v{schema_version}, generated {generated_at}.`
  and the label `Orientation only — general game knowledge, not source-verified.`

---

### Task 1: Normalize item tiers to 1-indexed, fix tier docstrings, bump schema to v3

Item records currently ship the raw 0-indexed `.tres` `tier` field (0–3)
while weapons ship 1–4 (from directory names) and the game UI shows I–IV.
`runfile.py:12` already declares "the coach uses 1-indexed tiers". Make that
true for items, correct the wrong tier ranges in server docstrings
(weapons are 1–4, not 1–6), and bump the dataset schema version since field
semantics changed.

**Files:**
- Modify: `brotato_coach/builders/items.py:57`
- Modify: `brotato_coach/dataset.py:7`
- Modify: `brotato_coach/server.py:45` (get_weapon docstring), `:93`
  (list_weapons docstring), `:136` (compare_weapons docstring example)
- Test: `tests/test_build_items.py`, `tests/test_shipped_dataset.py:72-73`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: item records whose `tier` is 1–4; `DATASET_VERSION == 3`;
  a rebuilt `data/brotato.json` in the worktree (needed by Task 3's
  shipped-dataset test).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_build_items.py` (bottom of file):

```python
def test_item_tier_is_one_indexed():
    # Raw .tres tiers are 0-indexed (0-3); records must ship the 1-indexed
    # tier the game UI displays (I-IV), matching weapons and runfile.py.
    rec = build_item_record(HANDCUFFS_DATA, [], item_id="item_handcuffs",
                            name="Handcuffs")
    assert rec["tier"] == 3  # raw `tier = 2` in the fixture
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_build_items.py::test_item_tier_is_one_indexed -v`
Expected: FAIL with `assert 2 == 3`

- [ ] **Step 3: Implement the normalization**

In `brotato_coach/builders/items.py` line 57, change:

```python
        "tier": d.get("tier", 0),
```

to:

```python
        # Raw .tres tiers are 0-indexed; ship the 1-indexed tier the game
        # UI displays (I-IV), matching weapon records and runfile.py.
        "tier": int(d.get("tier", 0)) + 1,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_build_items.py -v`
Expected: all tests in the file PASS

- [ ] **Step 5: Bump the dataset schema version**

In `brotato_coach/dataset.py` line 7, change:

```python
DATASET_VERSION = 2
```

to:

```python
DATASET_VERSION = 3
```

In `tests/test_shipped_dataset.py` lines 72–73, change:

```python
    # schema_version 2 = proc-aware + localized dataset
    assert ds["schema_version"] == 2
```

to:

```python
    # schema_version 3 = 1-indexed item tiers (2 was proc-aware + localized)
    assert ds["schema_version"] == 3
```

- [ ] **Step 6: Correct the tier ranges in server docstrings**

In `brotato_coach/server.py`, three edits:

Line 45 (get_weapon docstring), change:

```
        Weapons exist at multiple tiers (1-6). Omit `tier` to get every tier that
```

to:

```
        Weapons exist at multiple tiers (1-4). Omit `tier` to get every tier that
```

Line 93 (list_weapons docstring), change:

```
        `scaling_stat` (a stat the weapon scales with) and/or `tier` (1-6).
```

to:

```
        `scaling_stat` (a stat the weapon scales with) and/or `tier` (1-4).
```

Line 136 (compare_weapons docstring), change:

```
        [["Minigun", 4], ["SMG", 6]]. `aoe_enemies_hit` scales proc terms for
```

to:

```
        [["Minigun", 4], ["SMG", 4]]. `aoe_enemies_hit` scales proc terms for
```

(If the exact text at line 136 differs, find the docstring example
`["SMG", 6]` in `compare_weapons` and change the 6 to 4. The list_items
docstring at line 103 says `tier` (1-4) — that is now TRUE; leave it.)

- [ ] **Step 7: Rebuild the dataset in the worktree**

The worktree has no `data/brotato.json` and no `extracted/`/`recovered/`
of its own; point the builder at the main checkout's copies:

Run:
```bash
uv run python build_dataset.py \
  --extracted /c/Users/brend/src/brotato-exam/extracted \
  --recovered /c/Users/brend/src/brotato-exam/recovered
```

Expected: exits 0, writes `data/brotato.json` (gitignored — verify
`git status --porcelain` does NOT list it).

Then verify normalization end-to-end:

```bash
uv run python -c "
import json
ds = json.load(open('data/brotato.json', encoding='utf-8'))
print('schema', ds['schema_version'])
print('item tiers', sorted({i['tier'] for i in ds['items'] if i.get('tier') is not None}))
print('weapon tiers', sorted({w['tier'] for w in ds['weapons']}))
"
```

Expected output:
```
schema 3
item tiers [1, 2, 3, 4]
weapon tiers [1, 2, 3, 4]
```

- [ ] **Step 8: Run the full suite and lint**

Run: `uv run pytest` — Expected: all tests PASS (the shipped-dataset tests
now run against the rebuilt v3 dataset).
Run: `uv run ruff check .` — Expected: no findings.

- [ ] **Step 9: Commit**

```bash
git add brotato_coach/builders/items.py brotato_coach/dataset.py brotato_coach/server.py tests/test_build_items.py tests/test_shipped_dataset.py
git commit -m "fix: normalize item tiers to the 1-indexed UI convention (schema v3)

Item records shipped the raw 0-indexed .tres tier (0-3) while weapons ship
1-4 and the game UI shows I-IV; runfile.py already declared 1-indexed tiers
as the coach's convention. Also corrects server docstrings that claimed
weapon tiers 1-6.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `orientation.py` — primer constant and payload function

**Files:**
- Create: `brotato_coach/orientation.py`
- Test: `tests/test_orientation.py` (new)

**Interfaces:**
- Consumes: item tiers 1–4 and `DATASET_VERSION == 3` from Task 1 (the
  primer's tier claim depends on it).
- Produces: `orientation.PRIMER: str` (markdown with a literal
  `{provenance}` placeholder) and
  `orientation.read_me_payload(ds: dict) -> dict` returning
  `{"primer": <rendered str>}`. Task 3's server tool calls
  `read_me_payload(ds)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_orientation.py` with exactly:

```python
from brotato_coach import orientation

FAKE_DS = {"game_version": "9.9.9", "schema_version": 3,
           "generated_at": "2026-07-06T00:00:00Z"}


def test_payload_renders_provenance():
    primer = orientation.read_me_payload(FAKE_DS)["primer"]
    assert ("Dataset: Brotato v9.9.9 — schema v3, "
            "generated 2026-07-06T00:00:00Z.") in primer
    assert "{provenance}" not in primer


def test_payload_missing_provenance_renders_unknown():
    primer = orientation.read_me_payload({})["primer"]
    assert ("Dataset: Brotato vunknown — schema vunknown, "
            "generated unknown.") in primer


def test_primer_contains_required_sentinels():
    primer = orientation.read_me_payload(FAKE_DS)["primer"]
    for sentinel in [
        # every classification category, by exact name
        "stat_rider", "dynamic", "economy", "cc", "delivery_modifier",
        "drawback", "execute", "stack", "structure",
        # dataset-convention vocabulary
        "dps_at_zero_rd", "dps_slope_per_rd", "zero-stat", "cycle_time",
        "classified_effects", "unmodeled_effects", "enemies_hit",
        # the game-basics disclaimer, verbatim per spec
        "Orientation only — general game knowledge, not source-verified.",
        # tool pointers
        "get_filter_options",
    ]:
        assert sentinel in primer, f"primer missing sentinel: {sentinel}"


def test_payload_shape():
    payload = orientation.read_me_payload(FAKE_DS)
    assert set(payload) == {"primer"}
    assert isinstance(payload["primer"], str) and len(payload["primer"]) > 2000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_orientation.py -v`
Expected: FAIL with `ModuleNotFoundError` / `ImportError` (no
`brotato_coach.orientation`)

- [ ] **Step 3: Create `brotato_coach/orientation.py`**

Create the file with exactly this content. The `PRIMER` text is
copy-paste-grade — transcribe verbatim; its claims were cross-checked
against `docs/stat-mechanics.md` and `docs/proc-mechanics.md` at plan time.

````python
"""Session-start orientation primer served by the read_me tool.

The primer is our own MIT-licensed prose about mechanics facts and this
project's modeling conventions — it contains no game data. Claims in the
"verified" sections must stay in sync with docs/stat-mechanics.md and
docs/proc-mechanics.md (the evidence record); update both together.
Rendering uses str.replace, not str.format, so the markdown may safely
contain braces anywhere except the one {provenance} placeholder.
"""
from __future__ import annotations

PRIMER = """\
# Spud Coach — read me first

This server is the authoritative source for Brotato facts: it is built from
a versioned, fan-extracted copy of the game's own data files, not from
training data. Training-data knowledge of Brotato is frequently stale or
wrong for the loaded game version — prefer these tools over memory for any
weapon/item/character/mechanics claim.

{provenance}

## Game basics

Orientation only — general game knowledge, not source-verified.

- A run is a series of waves (20 in a standard run, then optional endless)
  at a difficulty chosen up front (Danger 0-5; higher = harder, better loot).
- Enemies drop materials, which are simultaneously money and XP: every
  material picked up counts toward both the shop budget and level-ups
  (a level-up offers a choice of stat upgrades).
- Between waves you visit the shop: buy weapons and items, reroll offers,
  or lock an offer for later.
- A character holds up to 6 weapons (character-dependent). Buying a copy of
  a weapon you already own at the same tier merges the two into one weapon
  of the next tier, in place — merging never costs an extra slot.
- Tiers everywhere in this dataset and API are 1-indexed (1-4), matching
  the in-game display (I-IV).

## Verified stat mechanics

Source-verified against the game's decompiled code (details per stat via
the explain_stat tool).

- **Caps.** Exactly 5 stats have caps: max_hp, speed, dodge, curse, and
  crit_chance. Only two bind from wave 1: dodge (60) and curse (0). The
  HP/speed/crit caps default to effectively infinite until an item sets a
  real one (e.g. Handcuffs freezes Max HP, Shackles freezes Speed at their
  current values).
- **Curse.** Positive curse scales enemy damage and HP (a sqrt factor) —
  a drawback stat. Negative curse is clamped: harmless, but no benefit.
- **Armor.** Diminishing returns: percent damage taken is 10/(10+armor/1.5),
  and damage taken never drops below 1. NEGATIVE armor is asymmetric — it
  amplifies damage taken above 100%, worse than the mirror image of the
  positive curve.
- **Luck.** A drop-chance multiplier. NEGATIVE luck divides drop chances
  rather than subtracting — a diminishing-returns penalty, not symmetric.
- **Harvesting.** Pays at end of each wave: one point of harvesting grants
  one material AND one XP. While positive it grows ~5% per wave; in endless
  it decays 20% per wave; NEGATIVE harvesting actively drains gold each
  wave (not a no-op).
- **Attack speed.** A universal cooldown multiplier applied identically to
  melee and ranged weapons — never dead weight.
- **HP regeneration.** At or below 0 it is a harmless no-op. (Unlike
  negative lifesteal, which actively drains HP on hit.)
- **% Damage.** A multiplicative global weapon-damage bonus (1 + stat/100),
  uncapped; final damage is floored at 1.
- **Range.** Adds flat range; melee weapons receive only HALF the stat.
  Uncapped.
- **Gain modifiers.** Character stat-gain modifiers (e.g. Ranger's +50%
  ranged-damage gains) multiply the raw sum of collected bonuses at display
  time: raw +6 ranged damage shows as +9. Use stat_display_value to convert.

## What the precomputed numbers mean

The DPS model is deliberately narrow and honest about it:

- **DPS is a line in ranged damage (RD).** Each weapon record carries
  dps_at_zero_rd and dps_slope_per_rd; realized base DPS at a build is
  dps_at_zero_rd + dps_slope_per_rd x RD. The slope is specifically the
  weapon's stat_ranged_damage scaling coefficient — weapons that scale
  with OTHER stats (melee damage, elemental, engineering, ...) have slope
  0 and their scaling lives only in scaling_stats; the served DPS number
  does NOT grow with those stats. Check scaling_stats before comparing
  across scaling types.
- **Baseline.** dps_at_zero_rd is computed at a zero-stat baseline — ALL
  player stats at zero; the weapon's own accuracy is already folded in.
- **cycle_time** is seconds per attack cycle: recoil_duration x 2 +
  cooldown/60, plus any burst-reload amortization.
- **Crit is NOT modeled.** crit_chance and crit_damage appear on the record
  but are not folded into any DPS line.
- **Proc lines.** proc_dps_at_zero_rd / proc_dps_slope_per_rd add expected
  on-hit proc damage from three verified damage sources:
  - weapon_damage (exploding): the explosion re-deals the weapon's own
    damage line. The engine EXCLUDES the directly-hit enemy from the blast,
    so the model's enemies_hit default of 1.0 means "one OTHER enemy is
    caught" — the proc is worth ZERO against a lone target (bosses!);
    override enemies_hit down for single-target reasoning, up for crowds.
  - burn_dot: burns tick every 0.5s for the burn's flat damage; re-ignition
    refreshes (max-based), never stacks. The line assumes steady-state
    (continuous attacking keeps the burn up).
  - companion_ranged_stats (lightning/spawned projectiles): spawned
    projectiles carry their OWN damage and scaling, independent of the host
    weapon. Targeted chains assume the nominal chain fully connects
    (enemies_hit = 1 + bounce; also zero against a lone target); untargeted
    sprays assume 1.0 expected hit per volley — an assumption constant, not
    a measurement.
  - The player-level explosion_damage stat is unmodeled: builds stacking it
    out-damage the static exploding proc line.
- **classified_effects.** Non-DPS effects are classified, with metadata,
  into 9 categories: stat_rider (flat stat granted while held), dynamic
  (state/time-dependent, no honest static number), economy (gold
  generation), cc (slows/crowd control), delivery_modifier (pierce/bounce
  on crit), drawback (self-damage etc.), execute (chance to deal
  current-HP damage), stack (bonus per extra copy owned), structure
  (spawns mines/turrets).
- **unmodeled_effects** is empty across the shipped dataset; if you ever
  see an entry, it strictly means "uninvestigated" — mention it when the
  number matters.

## Using the tools

- Call get_filter_options BEFORE passing filter values to list_weapons /
  list_items / get_weapon_class_set — filters are case-sensitive exact
  matches.
- `stats` parameters take short names (e.g. ranged_damage); explain_stat
  and stat_display_value take the stat_-prefixed form (stat_ranged_damage).
- weapon_dps / compare_weapons rank by the RD line above — for merge-order
  questions use compare_merge_paths; for whole-run post-mortems pass the
  run.json to evaluate_run.
"""


def read_me_payload(ds: dict) -> dict:
    """Render the primer with the loaded dataset's provenance interpolated."""
    def _field(key: str) -> str:
        val = ds.get(key)
        return "unknown" if val is None else str(val)

    provenance = (f"Dataset: Brotato v{_field('game_version')} — "
                  f"schema v{_field('schema_version')}, "
                  f"generated {_field('generated_at')}.")
    return {"primer": PRIMER.replace("{provenance}", provenance)}
````

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_orientation.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Lint and commit**

Run: `uv run ruff check .` — fix anything it reports in the new files.

```bash
git add brotato_coach/orientation.py tests/test_orientation.py
git commit -m "feat: add orientation primer module for the read_me tool

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Register the `read_me` tool and update server instructions

**Files:**
- Modify: `brotato_coach/server.py` (import block ~line 9, `_INSTRUCTIONS`
  ~lines 22-34, first tool registration inside `build_server` ~line 40)
- Test: `tests/test_server.py`, `tests/test_shipped_dataset.py`

**Interfaces:**
- Consumes: `orientation.read_me_payload(ds: dict) -> dict` from Task 2.
- Produces: MCP tool `read_me()` (no parameters) returning
  `{"primer": str}`; used by Task 4's docs only.

- [ ] **Step 1: Write the failing tests**

In `tests/test_server.py`, extend the existing registration assertion —
change:

```python
    assert {"get_weapon", "weapon_dps", "evaluate_item_for_build",
            "check_dataset_version"} <= tool_names
```

to:

```python
    assert {"read_me", "get_weapon", "weapon_dps", "evaluate_item_for_build",
            "check_dataset_version"} <= tool_names
```

and add at the bottom of the file:

```python
def test_read_me_tool_returns_rendered_primer():
    result = asyncio.run(_call(build_server(DS), "read_me"))
    # DS fixture: game_version "dev", schema_version 1, generated_at "t"
    assert "Dataset: Brotato vdev — schema v1, generated t." in result["primer"]


def test_instructions_point_to_read_me():
    assert "read_me" in build_server(DS).instructions
```

In `tests/test_shipped_dataset.py`, add at the bottom:

```python
@pytest.mark.skipif(not os.path.exists(DATA), reason="dataset not built")
def test_read_me_provenance_complete_on_shipped_dataset():
    from brotato_coach import orientation

    ds = json.load(open(DATA, encoding="utf-8"))
    primer = orientation.read_me_payload(ds)["primer"]
    line = next(ln for ln in primer.splitlines()
                if ln.startswith("Dataset: Brotato v"))
    assert "unknown" not in line
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_server.py tests/test_shipped_dataset.py -v`
Expected: `test_server_registers_tools`,
`test_read_me_tool_returns_rendered_primer`, and
`test_instructions_point_to_read_me` FAIL (unknown tool `read_me`);
`test_read_me_provenance_complete_on_shipped_dataset` PASSES already
(orientation module exists since Task 2) — that is fine.

- [ ] **Step 3: Register the tool and update `_INSTRUCTIONS`**

In `brotato_coach/server.py`:

(a) change the import line:

```python
from brotato_coach import answers, dataset, evaluate, query, runfile
```

to:

```python
from brotato_coach import answers, dataset, evaluate, orientation, query, runfile
```

(b) append one sentence to `_INSTRUCTIONS` — change its final lines:

```python
present. Call check_dataset_version if you need to confirm which game
version these facts are from.
"""
```

to:

```python
present. Call check_dataset_version if you need to confirm which game
version these facts are from. Start each session by calling read_me once —
it explains the dataset's conventions and the assumptions behind every
precomputed number.
"""
```

(c) register `read_me` as the FIRST tool inside `build_server`, immediately
after `mcp = FastMCP(...)` and before `get_weapon`:

```python
    @mcp.tool()
    def read_me() -> dict[str, Any]:
        """Return the orientation primer for this server: how Brotato's core
        loop works, the source-verified stat mechanics, and — critically —
        what this dataset's precomputed fields mean and which assumptions
        they bake in.

        Call this ONCE at the start of a session, before any other tool.
        Without it you will misread the DPS fields (they are RD-parameterized
        lines at a zero-stat baseline, not realized DPS) and miss the model's
        documented assumptions.
        """
        return _safe(orientation.read_me_payload)(ds=ds)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_server.py tests/test_shipped_dataset.py tests/test_orientation.py -v`
Expected: all PASS

- [ ] **Step 5: Full suite, lint, commit**

Run: `uv run pytest` — Expected: all PASS.
Run: `uv run ruff check .` — Expected: no findings.

```bash
git add brotato_coach/server.py tests/test_server.py tests/test_shipped_dataset.py
git commit -m "feat: serve the session-start primer as the read_me tool

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Ship surface — landing page and roadmap

**Files:**
- Modify: `site/index.html:66-73` ("What you get" section)
- Modify: `docs/roadmap.md` (Shipped paragraph, lines 6-14; Backlog
  section, lines 33-44)

**Interfaces:**
- Consumes: tool name `read_me` from Task 3. Nothing produced for later
  tasks (this is the last task).

- [ ] **Step 1: Add the "Start here" group to the landing page**

In `site/index.html`, directly after the line `<h2>What you get</h2>`
(line 66) and before the line `<h3>Data lookups</h3>`, insert:

```html
      <h3>Start here</h3>
      <ul>
        <li><code>read_me</code> — session-start primer: game basics, verified mechanics, and what the precomputed fields mean</li>
      </ul>
```

Verify: `grep -n "read_me" site/index.html` shows the new line between
`<h2>What you get</h2>` and `<h3>Data lookups</h3>`.

- [ ] **Step 2: Update the roadmap**

In `docs/roadmap.md`:

(a) In the Shipped paragraph, change:

```
Shipped: proc-aware DPS with verified exploding/burning/companion-projectile
```

(and its continuation) so the paragraph's opening reads:

```
Shipped: the `read_me` session-orientation primer (package prose + live
dataset provenance, superseding the build-time-distillation idea),
1-indexed item tiers matching the in-game display (dataset schema v3),
proc-aware DPS with verified exploding/burning/companion-projectile
```

(leave the rest of the paragraph unchanged).

(b) Delete the entire `## Backlog (successors from shipped work)` section
(the header line and the whole `read_me` bullet, lines 33-44) — it is now
shipped and the section has no other entries.

- [ ] **Step 3: Commit**

```bash
git add site/index.html docs/roadmap.md
git commit -m "docs(site,roadmap): list read_me tool; mark it and item-tier normalization shipped

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Verification (whole branch)

- `uv run pytest` green; `uv run ruff check .` clean.
- `git log --oneline main..HEAD` shows the spec commit plus 4 task commits.
- `git status --porcelain` shows no `data/`, `extracted/`, or `recovered/`
  entries staged.
- Manual smoke: `uv run python -c "import json; from brotato_coach import orientation; print(orientation.read_me_payload(json.load(open('data/brotato.json', encoding='utf-8')))['primer'][:400])"`
  prints the primer header with a fully-populated provenance line.
