# Roadmap Implementation Plan — near-term batch, localization, ship prep

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `docs/roadmap.md` backlog: proc-aware DPS, loadout set-bonus reasoning, full `explain_stat` coverage, localized names/descriptions, and PyPI ship prep (`uvx spudcoach`).

**Architecture:** All features follow the repo's one-way data flow: builders distill `.tres`/CSV into `data/brotato.json` at build time; pure logic in `calc.py`/`answers.py`/`query.py` reads only the dataset; MCP tools in `server.py` are thin wrappers. Proc DPS reuses the linear DPS-line model (a proc contribution is itself a `(dps0, slope)` line). New game facts are encoded only with decompiled-code evidence, mirroring `builders/mechanics.py`; unverifiable effects contribute zero and are surfaced as `unmodeled_effects` so rankings stay honest.

**Tech Stack:** Python 3.11+, uv, pytest, `mcp` (FastMCP), hatchling.

## Global Constraints

- **NEVER commit or redistribute game data**: `data/brotato.json`, `extracted/`, `recovered/`, `game_files/` are gitignored and must stay out of git (CLAUDE.md).
- TDD is the norm — write the failing test first. Run tests with `uv run pytest`.
- Dataset builds require both args verbatim: `uv run python build_dataset.py --game-version <ver> --generated-at <iso8601>` (never read a clock).
- One-way data flow: only `build_dataset.py` + `brotato_coach/builders/` read `extracted/`/`recovered/`; the MCP server reads only `data/brotato.json`.
- Pure logic (`calc.py`, `query.py`, `answers.py`, `evaluate.py`) has no I/O.
- Game-mechanics claims must be backed by decompiled-code evidence (the `builders/mechanics.py` standard). Encode nothing you cannot cite.
- Commit after every task; work on a feature branch (suggested: `roadmap-near-term`), PR to `main`.

## Execution environments — READ THIS FIRST

This checkout (and any machine without the game) has **no** `extracted/`, `recovered/`, or `data/brotato.json`. That is normal:

- **Phase A (Tasks 1–11)** runs anywhere. Every test uses synthetic inline fixtures, exactly like the existing suite.
- **Phase B (Tasks 12–14)** requires a machine with a Brotato install where `extracted/` + `recovered/` have been regenerated per `docs/extraction-setup.md`. These tasks turn decompiled-code evidence into encoded facts and rebuild the dataset.
- **Phase C (publish)** is outward-facing — every step needs explicit user go-ahead.

---

## Phase A — features over existing data (runs anywhere)

### Task 1: `calc.proc_line` — expected proc DPS as a line

**Files:**
- Modify: `brotato_coach/calc.py`
- Test: `tests/test_calc.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `calc.proc_line(dps0: float, slope: float, chance: float, enemies_hit: float, multiplier: float = 1.0) -> tuple[float, float]` — used by Task 2.

Key insight: a proc that re-deals the weapon's own damage (e.g. Shredder's exploding shot) has expected DPS `chance × enemies_hit × multiplier × (base + coef×RD)/cycle_time × accuracy` — i.e. a constant times the weapon's existing DPS line. So the proc contribution is itself a `(dps0, slope)` line and every downstream linear tool (crossover analysis, merge paths) keeps working.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_calc.py`:

```python
def test_proc_line_shredder_explode():
    # Shredder T4 base line (23.8095, 0.47619); 50% chance to re-deal weapon damage
    p0, ps = calc.proc_line(23.8095, 0.47619, chance=0.5, enemies_hit=1.0)
    assert math.isclose(p0, 11.90475, rel_tol=1e-4)
    assert math.isclose(ps, 0.238095, rel_tol=1e-4)


def test_proc_line_scales_with_enemies_hit_and_multiplier():
    p0, ps = calc.proc_line(20.0, 0.4, chance=0.5, enemies_hit=3.0, multiplier=0.5)
    assert math.isclose(p0, 15.0)
    assert math.isclose(ps, 0.3)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_calc.py -v`
Expected: FAIL with `AttributeError: module 'brotato_coach.calc' has no attribute 'proc_line'`

- [ ] **Step 3: Implement** — append to `brotato_coach/calc.py`:

```python
def proc_line(dps0: float, slope: float, chance: float, enemies_hit: float,
              multiplier: float = 1.0) -> tuple[float, float]:
    """Expected DPS line added by a weapon-damage proc (e.g. exploding shot).

    The proc re-deals the weapon's own damage line with probability `chance`
    per hit, against `enemies_hit` enemies, scaled by `multiplier`. Expected
    value is linear in RD, so the contribution is itself a (dps0, slope) line.
    """
    f = chance * enemies_hit * multiplier
    return (dps0 * f, slope * f)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_calc.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/calc.py tests/test_calc.py
git commit -m "feat(calc): expected proc DPS as a (dps0, slope) line"
```

---

### Task 2: proc model table + builder wiring

**Files:**
- Create: `brotato_coach/builders/procs.py`
- Modify: `brotato_coach/builders/weapons.py`
- Test: `tests/test_build_weapons.py`

**Interfaces:**
- Consumes: `calc.proc_line` (Task 1).
- Produces: `PROC_MODELS: dict[str, dict]` in `brotato_coach/builders/procs.py` (ships **empty**; Task 12 adds verified entries). `build_weapon_record` gains keyword-only `proc_models: dict | None = None` (None → `PROC_MODELS`) and its record gains `proc_dps_at_zero_rd: float`, `proc_dps_slope_per_rd: float`, `unmodeled_effects: list[str]` — consumed by Task 3.

The table ships empty on purpose: this repo only encodes game facts with decompiled-code evidence, and `recovered/` isn't on this machine. All machinery is built and tested now via injected synthetic models; Task 12 fills in the verified Shredder entry.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_build_weapons.py`:

```python
EXPLODE_EFFECT = ('[gd_resource type="Resource" format=2]\n[resource]\n'
                  'key = "effect_explode_custom"\nchance = 0.5\nvalue = 0\n')

PROC_MODEL = {"effect_explode_custom": {
    "damage_source": "weapon_damage",
    "damage_multiplier": 1.0,
    "default_enemies_hit": 1.0,
}}


def test_weapon_record_proc_line_from_model():
    rec = build_weapon_record(STATS, DATA, [EXPLODE_EFFECT], weapon_id="w",
                              name="W", tier=4, proc_models=PROC_MODEL)
    # base line (23.8095, 0.47619) x chance 0.5
    assert math.isclose(rec["proc_dps_at_zero_rd"], 11.90475, rel_tol=1e-4)
    assert math.isclose(rec["proc_dps_slope_per_rd"], 0.238095, rel_tol=1e-4)
    assert rec["unmodeled_effects"] == []


def test_weapon_record_unmodeled_effect_contributes_zero_and_is_listed():
    # default PROC_MODELS ships empty until verified against recovered/ code
    rec = build_weapon_record(STATS, DATA, [EXPLODE_EFFECT], weapon_id="w",
                              name="W", tier=4)
    assert rec["proc_dps_at_zero_rd"] == 0.0
    assert rec["proc_dps_slope_per_rd"] == 0.0
    assert rec["unmodeled_effects"] == ["effect_explode_custom"]


def test_weapon_record_no_effects_has_zero_proc_fields():
    rec = build_weapon_record(STATS, DATA, weapon_id="w", name="W", tier=4)
    assert rec["proc_dps_at_zero_rd"] == 0.0
    assert rec["unmodeled_effects"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_build_weapons.py -v`
Expected: new tests FAIL with `KeyError: 'proc_dps_at_zero_rd'` (existing tests still pass)

- [ ] **Step 3: Create `brotato_coach/builders/procs.py`**:

```python
"""Expected-damage models for weapon on-hit proc effects.

A model may only be added here with decompiled-code evidence from recovered/
(the builders/mechanics.py standard) — record the evidence in
docs/proc-mechanics.md. Effects without a model contribute zero DPS and are
listed in the weapon record's `unmodeled_effects`, so rankings stay honest
about what they ignore.

Model schema, keyed by effect `key`:
    damage_source: "weapon_damage" — the proc re-deals the weapon's own damage
        line (base + scaling), scaled by damage_multiplier.
    damage_multiplier: fraction of the weapon's damage line the proc deals.
    default_enemies_hit: assumed average enemies caught per proc (AoE). The
        softest number in the model; answers surface it as an assumption and
        let callers override it.
"""

from __future__ import annotations

PROC_MODELS: dict[str, dict] = {}
```

- [ ] **Step 4: Wire into `brotato_coach/builders/weapons.py`** — add the import, extend the signature, compute the proc line, and replace the return's `effects` entry. The full new `build_weapon_record` body from the `ct = ...` line down:

```python
from brotato_coach import calc
from brotato_coach.builders.procs import PROC_MODELS
from brotato_coach.tres import parse_tres
```

```python
def build_weapon_record(stats_text: str, data_text: str,
                        effect_texts: list[str] | None = None, *,
                        weapon_id: str, name: str, tier: int,
                        classes: list[str] | None = None,
                        proc_models: dict | None = None) -> dict:
```

```python
    ct = calc.cycle_time(recoil_duration, cooldown, burst=burst)
    dps0, slope = calc.dps_line(base_damage, _rd_coefficient(scaling_stats), ct, accuracy)

    effects = [_weapon_effect_record(t) for t in (effect_texts or [])]
    models = PROC_MODELS if proc_models is None else proc_models
    proc0 = proc_slope = 0.0
    unmodeled: list[str] = []
    for eff in effects:
        model = models.get(str(eff.get("key", "")))
        if model is not None and model["damage_source"] == "weapon_damage":
            p0, ps = calc.proc_line(dps0, slope, float(eff.get("chance", 1.0)),
                                    model["default_enemies_hit"],
                                    model["damage_multiplier"])
            proc0 += p0
            proc_slope += ps
        elif eff.get("key"):
            unmodeled.append(str(eff["key"]))
```

In the returned dict, replace the trailing `"effects": ...` entry (and its stale NOTE comment) with:

```python
        "sets": list(classes or []),
        # On-hit effects (e.g. exploding projectile), resolved from the data
        # .tres `effects` ext_resources. Effects with a verified PROC_MODELS
        # entry contribute the proc_dps_* expected line; the rest are listed
        # in unmodeled_effects.
        "effects": effects,
        "proc_dps_at_zero_rd": proc0,
        "proc_dps_slope_per_rd": proc_slope,
        "unmodeled_effects": unmodeled,
```

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add brotato_coach/builders/procs.py brotato_coach/builders/weapons.py tests/test_build_weapons.py
git commit -m "feat(build): proc model table + expected proc DPS line on weapon records"
```

---

### Task 3: proc-aware answers (`weapon_dps`, `compare_weapons`, `compare_merge_paths`)

**Files:**
- Modify: `brotato_coach/answers.py`
- Test: `tests/test_answers.py`

**Interfaces:**
- Consumes: weapon-record fields `proc_dps_at_zero_rd`, `proc_dps_slope_per_rd`, `unmodeled_effects` (Task 2) — always via `.get(..., 0.0)` so records built before this feature (or hand-made test fixtures) still work.
- Produces: `answers.weapon_dps(ds, name, tier, stats, aoe_enemies_hit: float = 1.0)` returning `dps` (**total**, base + proc), `base_dps`, `proc_dps`, `unmodeled_effects`; `answers.compare_weapons(ds, names_with_tiers, stats, aoe_enemies_hit: float = 1.0)` ranking by total `dps`. Consumed by Task 4.

Design decision: `dps` becomes the total so every existing consumer (ranking, server tool) automatically ranks proc weapons honestly — the roadmap's goal. The old guaranteed-only number is preserved as `base_dps`.

- [ ] **Step 1: Write the failing tests** — in `tests/test_answers.py`, add to `DS["weapons"]` (do NOT touch the Minigun/Revolver entries — existing exact-value asserts depend on them):

```python
        {"id": "weapon_shredder", "name": "Shredder", "tier": 4,
         "dps_at_zero_rd": 23.8095, "dps_slope_per_rd": 0.47619,
         "proc_dps_at_zero_rd": 11.9048, "proc_dps_slope_per_rd": 0.238095,
         "unmodeled_effects": [], "scaling_stats": []},
```

and give the existing Laser tier-1 entry proc fields:

```python
        {"id": "weapon_laser", "name": "Laser", "tier": 1,
         "dps_at_zero_rd": 15.0, "dps_slope_per_rd": 0.9,
         "proc_dps_at_zero_rd": 3.0, "proc_dps_slope_per_rd": 0.1,
         "scaling_stats": []},
```

then append the tests:

```python
def test_weapon_dps_adds_expected_proc_contribution():
    result = answers.weapon_dps(DS, "Shredder", 4, {"ranged_damage": 10})
    # base 23.8095 + 0.47619*10 = 28.5714; proc 11.9048 + 0.238095*10 = 14.2857
    assert math.isclose(result["base_dps"], 28.5714, rel_tol=1e-4)
    assert math.isclose(result["proc_dps"], 14.2857, rel_tol=1e-4)
    assert math.isclose(result["dps"], 42.8571, rel_tol=1e-4)


def test_weapon_dps_aoe_scales_proc_term_only():
    result = answers.weapon_dps(DS, "Shredder", 4, {"ranged_damage": 10},
                                aoe_enemies_hit=3.0)
    assert math.isclose(result["proc_dps"], 3 * 14.2857, rel_tol=1e-4)
    assert math.isclose(result["base_dps"], 28.5714, rel_tol=1e-4)


def test_weapon_dps_records_without_proc_fields_still_work():
    result = answers.weapon_dps(DS, "Minigun", 4, {"ranged_damage": 10})
    assert result["proc_dps"] == 0.0
    assert math.isclose(result["dps"], result["base_dps"])


def test_compare_merge_paths_includes_proc_lines():
    result = answers.compare_merge_paths(DS, "Laser", [2, 2], [3, 1])
    # path_b = T3 (45, 2.7) + T1 (15+3, 0.9+0.1) = (63.0, 3.7)
    assert math.isclose(result["line_b"][0], 63.0)
    assert math.isclose(result["line_b"][1], 3.7)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_answers.py -v`
Expected: new tests FAIL with `KeyError: 'base_dps'` / line mismatch

- [ ] **Step 3: Implement** — replace `weapon_dps`, `compare_weapons`, and `path_line`'s append in `brotato_coach/answers.py`:

```python
def weapon_dps(ds: dict, name: str, tier: int, stats: dict,
               aoe_enemies_hit: float = 1.0) -> dict:
    rec = query.get_weapon(ds, name, tier=tier)
    if "id" not in rec:
        return rec
    rd = float(stats.get("ranged_damage", 0))
    base = calc.dps_at(rec["dps_at_zero_rd"], rec["dps_slope_per_rd"], rd)
    proc = aoe_enemies_hit * calc.dps_at(rec.get("proc_dps_at_zero_rd", 0.0),
                                         rec.get("proc_dps_slope_per_rd", 0.0), rd)
    return {
        "name": rec["name"], "tier": tier, "ranged_damage": rd,
        "dps": base + proc, "base_dps": base, "proc_dps": proc,
        "unmodeled_effects": rec.get("unmodeled_effects", []),
        "breakdown": {
            "dps_at_zero_rd": rec["dps_at_zero_rd"],
            "dps_slope_per_rd": rec["dps_slope_per_rd"],
            "proc_dps_at_zero_rd": rec.get("proc_dps_at_zero_rd", 0.0),
            "proc_dps_slope_per_rd": rec.get("proc_dps_slope_per_rd", 0.0),
            "aoe_enemies_hit": aoe_enemies_hit,
        },
    }


def compare_weapons(ds: dict, names_with_tiers: list, stats: dict,
                    aoe_enemies_hit: float = 1.0) -> dict:
    rows = []
    for name, tier in names_with_tiers:
        r = weapon_dps(ds, name, tier, stats, aoe_enemies_hit)
        if "dps" in r:
            rows.append({"name": r["name"], "tier": tier, "dps": r["dps"],
                         "proc_dps": r["proc_dps"]})
    rows.sort(key=lambda x: x["dps"], reverse=True)
    return {"ranking": rows}
```

In `compare_merge_paths`'s inner `path_line`, replace the `lines.append(...)` with:

```python
            lines.append((rec["dps_at_zero_rd"] + rec.get("proc_dps_at_zero_rd", 0.0),
                          rec["dps_slope_per_rd"] + rec.get("proc_dps_slope_per_rd", 0.0)))
```

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest -v`
Expected: all PASS (the pre-existing `test_weapon_dps_at_rd` passes because Minigun has no proc fields)

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/answers.py tests/test_answers.py
git commit -m "feat(answers): fold expected proc DPS into weapon_dps/compare/merge-paths"
```

---

### Task 4: proc-aware server tools

**Files:**
- Modify: `brotato_coach/server.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `answers.weapon_dps` / `answers.compare_weapons` with `aoe_enemies_hit` (Task 3).
- Produces: MCP tools `weapon_dps(name, tier, stats, aoe_enemies_hit: float = 1.0)` and `compare_weapons(names_with_tiers, stats, aoe_enemies_hit: float = 1.0)`.

- [ ] **Step 1: Write the failing test** — append to `tests/test_server.py`:

```python
def test_weapon_dps_tool_reports_proc_fields():
    ds = {**DS, "weapons": [{**DS["weapons"][0],
          "proc_dps_at_zero_rd": 5.0, "proc_dps_slope_per_rd": 0.5,
          "unmodeled_effects": ["effect_burning"]}]}
    result = asyncio.run(_call(build_server(ds), "weapon_dps", name="Minigun",
                               tier=4, stats={"ranged_damage": 10}))
    assert round(result["proc_dps"], 4) == 10.0
    assert result["unmodeled_effects"] == ["effect_burning"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_server.py -v`
Expected: FAIL with `KeyError: 'proc_dps'`

- [ ] **Step 3: Implement** — in `brotato_coach/server.py` replace the `weapon_dps` and `compare_weapons` tools:

```python
    @mcp.tool()
    def weapon_dps(name: str, tier: int, stats: Stats,
                   aoe_enemies_hit: float = 1.0) -> dict[str, Any]:
        """Compute one weapon's realized DPS for a given build, with a breakdown.

        `dps` = guaranteed line (`base_dps`) + expected on-hit proc damage
        (`proc_dps`, e.g. exploding projectiles — chance x effect damage).
        `aoe_enemies_hit` scales the proc term for AoE procs (default 1 enemy,
        conservative). Effect keys the model can't yet value are listed in
        `unmodeled_effects` — mention them when the number matters. `stats` is
        the player's current run stats (short names, e.g. ranged_damage); DPS
        scales linearly with ranged_damage. For ranking several weapons, use
        compare_weapons; for merge-order questions, use compare_merge_paths.
        """
        return _safe(answers.weapon_dps)(ds=ds, name=name, tier=tier,
                                         stats=stats.as_dict(),
                                         aoe_enemies_hit=aoe_enemies_hit)

    @mcp.tool()
    def compare_weapons(names_with_tiers: list[tuple[str, int]], stats: Stats,
                        aoe_enemies_hit: float = 1.0) -> dict[str, Any]:
        """Rank several weapons by realized DPS (guaranteed + expected proc
        damage) at the SAME build stats.

        `names_with_tiers` is a list of [name, tier] pairs, e.g.
        [["Minigun", 4], ["SMG", 6]]. `aoe_enemies_hit` scales proc terms for
        AoE procs (default 1). Returns `{"ranking": [...]}` sorted by total DPS
        descending. Use when the player asks 'which of these hits hardest'.
        """
        return _safe(lambda **kw: answers.compare_weapons(
            ds, [tuple(x) for x in kw["names_with_tiers"]], kw["stats"],
            kw["aoe_enemies_hit"]))(
            names_with_tiers=names_with_tiers, stats=stats.as_dict(),
            aoe_enemies_hit=aoe_enemies_hit)
```

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/server.py tests/test_server.py
git commit -m "feat(server): surface proc DPS + aoe_enemies_hit on DPS tools"
```

---

### Task 5: `answers.loadout_set_bonuses`

**Files:**
- Modify: `brotato_coach/answers.py`
- Test: `tests/test_answers.py`

**Interfaces:**
- Consumes: weapon records' `sets: list[str]` (already built), set records `{"id", "name", "bonuses": [{"count", "effect": {"key", "value"}}]}` (already built), `query.get_weapon`/`query.get_set`.
- Produces: `answers.loadout_set_bonuses(ds: dict, weapon_names: list[str]) -> dict` returning `{"classes": [{"class", "count", "active": [...], "next": {...,"needs": int} | None}], "unknown_weapons": [{"name", "did_you_mean"}]}`. Consumed by Task 6.

Counting rule: every equipped weapon counts toward each of its classes, **duplicates included** (six SMGs = six Gun weapons). Tier is irrelevant to class membership, so lookups are by name only.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_answers.py`:

```python
SETS_DS = {
    "weapons": [
        {"id": "weapon_smg", "name": "SMG", "tier": 1, "sets": ["Gun"]},
        {"id": "weapon_pistol", "name": "Pistol", "tier": 2, "sets": ["Gun", "Precise"]},
        {"id": "weapon_knife", "name": "Knife", "tier": 1, "sets": ["Blade", "Precise"]},
    ],
    "sets": [
        {"id": "set_gun", "name": "Gun", "bonuses": [
            {"count": 2, "effect": {"key": "stat_range", "value": 10}},
            {"count": 4, "effect": {"key": "stat_range", "value": 20}}]},
        {"id": "set_precise", "name": "Precise", "bonuses": [
            {"count": 2, "effect": {"key": "stat_crit_chance", "value": 5}}]},
        {"id": "set_blade", "name": "Blade", "bonuses": [
            {"count": 2, "effect": {"key": "stat_lifesteal", "value": 2}}]},
    ],
}


def test_loadout_set_bonuses_counts_duplicates_and_reports_next():
    result = answers.loadout_set_bonuses(SETS_DS, ["SMG", "SMG", "Pistol", "Knife"])
    by_class = {c["class"]: c for c in result["classes"]}
    gun = by_class["Gun"]  # SMG x2 + Pistol = 3
    assert gun["count"] == 3
    assert gun["active"] == [{"count": 2, "effect": {"key": "stat_range", "value": 10}}]
    assert gun["next"]["count"] == 4 and gun["next"]["needs"] == 1


def test_loadout_set_bonuses_maxed_class_has_no_next():
    result = answers.loadout_set_bonuses(SETS_DS, ["Pistol", "Knife"])
    by_class = {c["class"]: c for c in result["classes"]}
    assert by_class["Precise"]["count"] == 2
    assert by_class["Precise"]["next"] is None
    assert len(by_class["Precise"]["active"]) == 1


def test_loadout_set_bonuses_below_first_threshold():
    result = answers.loadout_set_bonuses(SETS_DS, ["Knife"])
    by_class = {c["class"]: c for c in result["classes"]}
    assert by_class["Blade"]["active"] == []
    assert by_class["Blade"]["next"]["needs"] == 1


def test_loadout_set_bonuses_unknown_weapon_suggested():
    result = answers.loadout_set_bonuses(SETS_DS, ["Knifee"])
    assert result["classes"] == []
    assert result["unknown_weapons"][0]["name"] == "Knifee"
    assert "Knife" in result["unknown_weapons"][0]["did_you_mean"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_answers.py -v`
Expected: FAIL with `AttributeError: module 'brotato_coach.answers' has no attribute 'loadout_set_bonuses'`

- [ ] **Step 3: Implement** — append to `brotato_coach/answers.py`:

```python
def loadout_set_bonuses(ds: dict, weapon_names: list[str]) -> dict:
    counts: dict[str, int] = {}
    unknown: list[dict] = []
    for name in weapon_names:
        rec = query.get_weapon(ds, name)
        if "matches" in rec:
            rec = rec["matches"][0]  # class membership is tier-independent
        if "id" not in rec:
            unknown.append({"name": name,
                            "did_you_mean": rec.get("did_you_mean", [])})
            continue
        for cls in rec.get("sets", []):
            counts[cls] = counts.get(cls, 0) + 1  # duplicates count in-game

    classes = []
    for cls in sorted(counts):
        n = counts[cls]
        set_rec = query.get_set(ds, cls)
        bonuses = set_rec.get("bonuses", []) if "id" in set_rec else []
        active = [b for b in bonuses if b["count"] <= n]
        upcoming = [b for b in bonuses if b["count"] > n]
        nxt = None
        if upcoming:
            first = min(upcoming, key=lambda b: b["count"])
            nxt = {**first, "needs": first["count"] - n}
        classes.append({"class": cls, "count": n, "active": active, "next": nxt})
    return {"classes": classes, "unknown_weapons": unknown}
```

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/answers.py tests/test_answers.py
git commit -m "feat(answers): loadout set-bonus progress (active + next threshold)"
```

---

### Task 6: server tool `loadout_set_bonuses`

**Files:**
- Modify: `brotato_coach/server.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `answers.loadout_set_bonuses` (Task 5).
- Produces: MCP tool `loadout_set_bonuses(weapon_names: list[str])`.

- [ ] **Step 1: Write the failing test** — append to `tests/test_server.py`:

```python
def test_loadout_set_bonuses_tool():
    ds = {**DS,
          "weapons": [{"id": "weapon_smg", "name": "SMG", "tier": 1,
                       "sets": ["Gun"], "dps_at_zero_rd": 0.0,
                       "dps_slope_per_rd": 0.0, "scaling_stats": []}],
          "sets": [{"id": "set_gun", "name": "Gun", "bonuses": [
              {"count": 2, "effect": {"key": "stat_range", "value": 10}}]}]}
    result = asyncio.run(_call(build_server(ds), "loadout_set_bonuses",
                               weapon_names=["SMG", "SMG"]))
    assert result["classes"][0]["class"] == "Gun"
    assert result["classes"][0]["count"] == 2
    assert result["classes"][0]["active"][0]["effect"]["value"] == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_server.py -v`
Expected: FAIL — `Unknown tool: loadout_set_bonuses`

- [ ] **Step 3: Implement** — add to `build_server` in `brotato_coach/server.py` (after `get_weapon_class_set`):

```python
    @mcp.tool()
    def loadout_set_bonuses(weapon_names: list[str]) -> dict[str, Any]:
        """Report weapon-class set progress for a whole loadout: per class, how
        many equipped weapons count toward it, which set bonuses are ACTIVE
        now, and the NEXT threshold with how many more weapons it needs.

        `weapon_names` is the loadout as weapon names; tiers don't matter for
        class membership and duplicates count (six SMGs = six Gun weapons).
        Use when the player asks 'what set bonuses do I have / what should I
        add to hit the next bonus'. Unknown names come back under
        `unknown_weapons` with did_you_mean suggestions. For one class's full
        bonus table, use get_weapon_class_set instead.
        """
        return _safe(answers.loadout_set_bonuses)(ds=ds, weapon_names=weapon_names)
```

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest -v`
Expected: all PASS (including `test_all_tools_have_descriptions`)

- [ ] **Step 5: Update README tool count/diagram if it enumerates tools** (README mentions a 14-tool surface; it becomes 15). Check with `grep -n "14" README.md` and update the count/tool list accordingly.

- [ ] **Step 6: Commit**

```bash
git add brotato_coach/server.py tests/test_server.py README.md
git commit -m "feat(server): loadout_set_bonuses tool (set-progress reasoning)"
```

---

### Task 7: stat mechanics — summaries + the four weapon-scaling stats

**Files:**
- Modify: `brotato_coach/builders/mechanics.py`
- Test: `tests/test_mechanics.py` (create)

**Interfaces:**
- Consumes: nothing new.
- Produces: `STAT_MECHANICS` entries gain a `summary: str` field; new entries `stat_ranged_damage`, `stat_melee_damage`, `stat_elemental_damage`, `stat_engineering` with `special="weapon_scaling_stat"`. `answers.explain_stat` needs no change (it spreads the dict).

Evidence discipline: these four are verifiable **now** — the weapon-scaling mechanism is this repo's own hand-verified DPS model (`docs/weapon-merge-dps-methodology.md`, golden tests in `tests/test_calc.py`). The remaining five displayed stats (`percent_damage`, `armor`, `luck`, `harvesting`, `range`) need `recovered/` evidence → Task 13. Note: vanilla Brotato has exactly 16 displayed stats; there is no `stat_xp_gain` or `stat_pickup_range`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_mechanics.py`:

```python
from brotato_coach.builders.mechanics import STAT_MECHANICS


def test_weapon_scaling_damage_stats_encoded():
    for stat in ("stat_ranged_damage", "stat_melee_damage",
                 "stat_elemental_damage", "stat_engineering"):
        assert STAT_MECHANICS[stat]["special"] == "weapon_scaling_stat", stat


def test_every_entry_has_a_summary():
    missing = [s for s, m in STAT_MECHANICS.items() if not m.get("summary")]
    assert missing == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_mechanics.py -v`
Expected: FAIL with `KeyError: 'stat_ranged_damage'`

- [ ] **Step 3: Implement** — replace `brotato_coach/builders/mechanics.py` with:

```python
"""Verified stat mechanics, encoded from decompiled code (see docs/stat-mechanics.md).

Only stats whose behavior has been confirmed against the game code are listed.
This table is authoritative for what the coach claims about stat mechanics.
"""

from __future__ import annotations


def _m(cap=None, special=None, safe_below_zero=False, safe_at_zero=False,
       avoid_positive=False, never_dead_weight=False, summary=None) -> dict:
    return {
        "cap": cap, "special": special, "safe_below_zero": safe_below_zero,
        "safe_at_zero": safe_at_zero, "avoid_positive": avoid_positive,
        "never_dead_weight": never_dead_weight, "summary": summary,
    }


_WEAPON_SCALING = ("Weapon scaling stat: each weapon whose scaling_stats lists "
                   "it adds coefficient x stat to that weapon's damage per hit; "
                   "it does nothing for weapons without a matching entry — check "
                   "the weapon record's scaling_stats.")

STAT_MECHANICS: dict[str, dict] = {
    "stat_max_hp": _m(cap={"cap_key": "hp_cap"},
                      summary="Capped via hp_cap; cap-at-current-value items "
                              "(Handcuffs) can freeze it for the run."),
    "stat_speed": _m(cap={"cap_key": "speed_cap"},
                     summary="Capped via speed_cap; freezable by Shackles "
                             "(cap-at-current-value)."),
    "stat_dodge": _m(cap={"cap_key": "dodge_cap"},
                     summary="Capped via dodge_cap (utils.gd get_capped_stat)."),
    "stat_crit_chance": _m(cap={"cap_key": "crit_chance_cap"},
                           summary="Capped via crit_chance_cap (utils.gd "
                                   "get_capped_stat)."),
    "stat_curse": _m(cap={"cap_key": "curse_cap"}, special="curse_sqrt_penalty",
                     safe_below_zero=True, avoid_positive=True,
                     summary="Positive curse scales enemy damage/HP by a "
                             "sqrt(curse) factor (entity_service.gd) — avoid. "
                             "Negative curse is clamped to zero benefit: "
                             "harmless, but not a defensive gain."),
    "stat_hp_regeneration": _m(special="regen_zero_safe", safe_below_zero=True,
                               safe_at_zero=True,
                               summary="At or below 0 it is a harmless no-op — "
                                       "player.gd just stops the regen timer."),
    "stat_lifesteal": _m(special="lifesteal_negative_drains",
                         summary="Negative lifesteal actively drains HP on hit "
                                 "(unlike regen, which no-ops at or below 0)."),
    "stat_attack_speed": _m(special="attack_speed_universal", never_dead_weight=True,
                            summary="Universal cooldown-reducing multiplier, "
                                    "applied identically to ranged and melee "
                                    "weapons — never dead weight."),
    "knockback": _m(special="knockback_clamped_by_weapon_flag", safe_below_zero=True,
                    safe_at_zero=True,
                    summary="Clamped to non-negative per weapon unless the "
                            "weapon sets can_have_negative_knockback."),
    # Weapon scaling-damage stats — mechanism verified by this repo's own
    # hand-verified DPS model (docs/weapon-merge-dps-methodology.md).
    "stat_ranged_damage": _m(special="weapon_scaling_stat", summary=_WEAPON_SCALING),
    "stat_melee_damage": _m(special="weapon_scaling_stat", summary=_WEAPON_SCALING),
    "stat_elemental_damage": _m(special="weapon_scaling_stat", summary=_WEAPON_SCALING),
    "stat_engineering": _m(special="weapon_scaling_stat", summary=_WEAPON_SCALING),
}
```

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/builders/mechanics.py tests/test_mechanics.py
git commit -m "feat(mechanics): summaries on all entries + weapon-scaling damage stats"
```

---

### Task 8: translations CSV parser

**Files:**
- Create: `brotato_coach/builders/localization.py`
- Test: `tests/test_build_localization.py` (create)

**Interfaces:**
- Consumes: nothing new. The real CSV lives at `recovered/.assets/resources/translations/translations.csv` (per `docs/extraction-setup.md`); Godot 3.x convention: first column = key, one column per locale (`en`, `fr`, …).
- Produces: `parse_translations_csv(text: str, locale: str = "en") -> dict[str, str]` and `resolve_text(tr: dict | None, key: object, fallback: str = "") -> str`. Consumed by Task 9.

- [ ] **Step 1: Write the failing tests** — create `tests/test_build_localization.py`:

```python
from brotato_coach.builders.localization import parse_translations_csv, resolve_text

CSV = ('keys,en,fr\n'
       'WEAPON_SHREDDER,Shredder,Broyeur\n'
       'WEAPON_SHREDDER_DESC,"Chance to explode, hitting nearby enemies",Explose\n'
       ',skipme,\n')


def test_parse_translations_picks_locale_column():
    tr = parse_translations_csv(CSV)
    assert tr["WEAPON_SHREDDER"] == "Shredder"
    tr_fr = parse_translations_csv(CSV, locale="fr")
    assert tr_fr["WEAPON_SHREDDER"] == "Broyeur"


def test_parse_translations_handles_quoted_commas():
    tr = parse_translations_csv(CSV)
    assert tr["WEAPON_SHREDDER_DESC"] == "Chance to explode, hitting nearby enemies"


def test_parse_translations_skips_blank_keys_and_unknown_locale():
    assert "" not in parse_translations_csv(CSV)
    assert parse_translations_csv(CSV, locale="xx") == {}


def test_resolve_text_falls_back():
    tr = {"WEAPON_SHREDDER": "Shredder"}
    assert resolve_text(tr, "WEAPON_SHREDDER", "slug") == "Shredder"
    assert resolve_text(tr, "MISSING_KEY", "slug") == "slug"
    assert resolve_text(None, "WEAPON_SHREDDER", "slug") == "slug"
    assert resolve_text(tr, None) == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_build_localization.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'brotato_coach.builders.localization'`

- [ ] **Step 3: Implement** — create `brotato_coach/builders/localization.py`:

```python
"""Resolve Godot translation-CSV strings so records carry human-readable text.

The decompiled CSV (recovered/.assets/resources/translations/translations.csv)
follows Godot 3.x convention: first column is the key, one column per locale.
Resolution is best-effort — a missing table or key falls back to the
slug-derived name so builds without recovered/ still work.
"""

from __future__ import annotations

import csv
import io


def parse_translations_csv(text: str, locale: str = "en") -> dict[str, str]:
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header or locale not in header:
        return {}
    loc_col = header.index(locale)
    out: dict[str, str] = {}
    for row in reader:
        if row and row[0] and len(row) > loc_col:
            out[row[0]] = row[loc_col]
    return out


def resolve_text(tr: dict[str, str] | None, key: object, fallback: str = "") -> str:
    if tr and isinstance(key, str) and key in tr:
        return tr[key]
    return fallback
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_build_localization.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/builders/localization.py tests/test_build_localization.py
git commit -m "feat(build): Godot translations-CSV parser + resolve_text"
```

---

### Task 9: wire `display_name`/`description` through the builders and build step

**Files:**
- Modify: `brotato_coach/builders/weapons.py`, `brotato_coach/builders/items.py`, `brotato_coach/builders/characters.py`, `brotato_coach/builders/sets.py`, `build_dataset.py`
- Test: `tests/test_build_weapons.py`, `tests/test_build_items.py`

**Interfaces:**
- Consumes: `resolve_text` (Task 8). Data `.tres` resources are expected to carry `name`/`description` fields holding translation keys (confirmed in Task 14; until then `resolve_text` falls back safely to the slug name / empty string).
- Produces: every record gains `display_name: str` (localized name, falling back to the slug-derived `name`) and `description: str` (falling back to `""`); item effect records gain `text: str` (resolved `text_key`). `build_dataset.py` gains `--translations` (default `recovered/.assets/resources/translations/translations.csv`). Consumed by Task 10 and Task 14.

Compatibility rule: the existing `name` field keeps its slug-derived value — lookups, goldens, and old datasets keep working; `display_name` is additive.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_build_weapons.py`:

```python
DATA_LOC = """[gd_resource type="Resource" format=2]
[resource]
weapon_id = "weapon_shredder"
name = "WEAPON_SHREDDER"
description = "WEAPON_SHREDDER_DESC"
effects = [  ]
"""
TR = {"WEAPON_SHREDDER": "Shredder (EN)",
      "WEAPON_SHREDDER_DESC": "Chance to explode."}


def test_weapon_record_resolves_display_name_and_description():
    rec = build_weapon_record(STATS, DATA_LOC, weapon_id="weapon_shredder",
                              name="Shredder", tier=4, tr=TR)
    assert rec["display_name"] == "Shredder (EN)"
    assert rec["description"] == "Chance to explode."


def test_weapon_record_falls_back_to_slug_name_without_translations():
    rec = build_weapon_record(STATS, DATA_LOC, weapon_id="weapon_shredder",
                              name="Shredder", tier=4)
    assert rec["display_name"] == "Shredder"
    assert rec["description"] == ""
```

and append to `tests/test_build_items.py` (reuse that file's existing `DATA`-style fixture constants; add `name`/`description` keys the same way):

```python
DATA_LOC = ('[gd_resource type="Resource" format=2]\n[resource]\n'
            'name = "ITEM_HANDCUFFS"\ndescription = "ITEM_HANDCUFFS_DESC"\n'
            'tier = 2\nvalue = 40\ntags = [ "stat_ranged_damage" ]\n')
EFF_TR = '[resource]\nkey = "hp_cap"\nvalue = 0\neffect_sign = 0\ntext_key = "EFFECT_HP_CAP_AT_CURRENT_VALUE"\n'
ITEM_TR = {"ITEM_HANDCUFFS": "Handcuffs (EN)",
           "ITEM_HANDCUFFS_DESC": "Freezes Max HP.",
           "EFFECT_HP_CAP_AT_CURRENT_VALUE": "Max HP is capped at its current value"}


def test_item_record_resolves_display_name_description_and_effect_text():
    rec = build_item_record(DATA_LOC, [EFF_TR], item_id="item_handcuffs",
                            name="Handcuffs", tr=ITEM_TR)
    assert rec["display_name"] == "Handcuffs (EN)"
    assert rec["description"] == "Freezes Max HP."
    assert rec["effects"][0]["text"] == "Max HP is capped at its current value"


def test_item_record_falls_back_without_translations():
    rec = build_item_record(DATA_LOC, [EFF_TR], item_id="item_handcuffs",
                            name="Handcuffs")
    assert rec["display_name"] == "Handcuffs"
    assert rec["effects"][0]["text"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_build_weapons.py tests/test_build_items.py -v`
Expected: FAIL with `TypeError: ... unexpected keyword argument 'tr'`

- [ ] **Step 3: Implement the four builders.**

`brotato_coach/builders/weapons.py` — add the import, `tr` param, parse `data_text`, and two record fields:

```python
from brotato_coach.builders.localization import resolve_text
```

```python
def build_weapon_record(stats_text: str, data_text: str,
                        effect_texts: list[str] | None = None, *,
                        weapon_id: str, name: str, tier: int,
                        classes: list[str] | None = None,
                        proc_models: dict | None = None,
                        tr: dict[str, str] | None = None) -> dict:
    s = parse_tres(stats_text).resource
    d = parse_tres(data_text).resource
```

and in the returned dict, right after `"name": name,`:

```python
        "display_name": resolve_text(tr, d.get("name"), name),
        "description": resolve_text(tr, d.get("description")),
```

`brotato_coach/builders/items.py` — same import; `_effect_record` gains `tr`:

```python
def _effect_record(text: str, tr: dict[str, str] | None = None) -> dict:
    r = parse_tres(text).resource
    return {
        "key": r.get("key", ""),
        "value": r.get("value", 0),
        "effect_sign": r.get("effect_sign", 0),
        "text_key": r.get("text_key", ""),
        "text": resolve_text(tr, r.get("text_key")),
    }
```

`build_item_record(data_text, effect_texts, *, item_id, name, tr=None)`: pass `tr` through (`effects = [_effect_record(t, tr) for t in effect_texts]`) and add to the returned dict after `"name": name,`:

```python
        "display_name": resolve_text(tr, d.get("name"), name),
        "description": resolve_text(tr, d.get("description")),
```

`brotato_coach/builders/characters.py` — same import; signature gains `tr: dict[str, str] | None = None`; add `d = parse_tres(data_text).resource` at the top of the function and the same two `display_name`/`description` lines after `"name": name,`.

`brotato_coach/builders/sets.py` — same import; `build_set_record(set_data_text, count_effect_texts, *, set_id, name, tr=None)`; add `d = parse_tres(set_data_text).resource` and return:

```python
    return {"id": set_id, "name": name,
            "display_name": resolve_text(tr, d.get("name"), name),
            "description": resolve_text(tr, d.get("description")),
            "bonuses": bonuses}
```

- [ ] **Step 4: Wire `build_dataset.py`** — add the import and CLI arg, load the table, pass `tr=tr` to all four `build_*_record` calls:

```python
from brotato_coach.builders.localization import parse_translations_csv
```

```python
    parser.add_argument(
        "--translations",
        default="recovered/.assets/resources/translations/translations.csv",
        help="decompiled Godot translations CSV; skipped if absent")
```

after `args = parser.parse_args(argv)`:

```python
    tr: dict[str, str] = {}
    if os.path.isfile(args.translations):
        tr = parse_translations_csv(_read(args.translations))
```

add `tr=tr` to each of the four `build_*_record(...)` calls, and extend the final print:

```python
    print(f"Wrote {args.out}: {len(weapons)} weapon records, {len(items)} item records, "
          f"{len(characters)} character records, {len(sets)} set records "
          f"({'localized' if tr else 'NO translations found — slug names only'})")
```

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add brotato_coach/builders/ build_dataset.py tests/test_build_weapons.py tests/test_build_items.py
git commit -m "feat(build): resolve display_name/description/effect text from translations"
```

---

### Task 10: name lookups match `display_name`

**Files:**
- Modify: `brotato_coach/query.py`
- Test: `tests/test_query.py`

**Interfaces:**
- Consumes: records' optional `display_name` (Task 9).
- Produces: `query._match`/`query._names` treat `display_name` as a match/suggestion candidate, so every lookup tool (`get_weapon`, `get_item`, …) accepts in-game names.

- [ ] **Step 1: Write the failing test** — append to `tests/test_query.py`:

```python
def test_get_weapon_matches_display_name():
    ds = {"weapons": [{"id": "weapon_smg", "name": "Smg",
                       "display_name": "SMG Mk. II", "tier": 1}]}
    assert query.get_weapon(ds, "smg mk. ii")["id"] == "weapon_smg"


def test_suggestions_include_display_names():
    ds = {"weapons": [{"id": "weapon_smg", "name": "Smg",
                       "display_name": "SMG Mk. II", "tier": 1}]}
    rec = query.get_weapon(ds, "smg mk 2")
    assert rec["error"] == "not_found"
    assert "SMG Mk. II" in rec["did_you_mean"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_query.py -v`
Expected: FAIL (`not_found` on the first test)

- [ ] **Step 3: Implement** — in `brotato_coach/query.py` replace `_names` and `_match`:

```python
def _names(records: list[dict]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for r in records:
        for v in (r.get("name", ""), r.get("display_name", ""), r.get("id", "")):
            if v and v not in seen:
                seen.add(v)
                out.append(v)
    return out


def _match(records: list[dict], name: str) -> list[dict]:
    low = name.lower()
    return [r for r in records
            if low in (r.get("name", "").lower(),
                       r.get("display_name", "").lower(),
                       r.get("id", "").lower())]
```

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/query.py tests/test_query.py
git commit -m "feat(query): match and suggest localized display_name"
```

---

### Task 11: ship prep — dataset path flag + `spudcoach` packaging

**Files:**
- Modify: `brotato_coach/server.py`, `pyproject.toml`, `README.md`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `server._data_path(argv: list[str] | None = None) -> str` (precedence: `--data` flag > `SPUDCOACH_DATA` env > `data/brotato.json`); console script `spudcoach`; PyPI distribution renamed `spudcoach` v0.2.0 (import package stays `brotato_coach`).

Why: `uvx spudcoach` installs an empty-handed server (the dataset is never distributed — CLAUDE.md), so users must point it at their own built dataset; a cwd-relative hardcoded path can't do that. `plugin/.mcp.json` keeps working (it sets cwd to the repo root, where the default relative path resolves).

- [ ] **Step 1: Write the failing tests** — append to `tests/test_server.py`:

```python
def test_data_path_default():
    from brotato_coach import server
    assert server._data_path([]) == "data/brotato.json"


def test_data_path_flag_overrides():
    from brotato_coach import server
    assert server._data_path(["--data", "/x/y.json"]) == "/x/y.json"


def test_data_path_env_fallback(monkeypatch):
    from brotato_coach import server
    monkeypatch.setenv("SPUDCOACH_DATA", "/env/brotato.json")
    assert server._data_path([]) == "/env/brotato.json"
    assert server._data_path(["--data", "/flag.json"]) == "/flag.json"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_server.py -v`
Expected: FAIL with `AttributeError: ... has no attribute '_data_path'`

- [ ] **Step 3: Implement** — in `brotato_coach/server.py`, add imports `argparse`, `os` and replace `main`:

```python
def _data_path(argv: list[str] | None = None) -> str:
    parser = argparse.ArgumentParser(prog="spudcoach")
    parser.add_argument(
        "--data", default=os.environ.get("SPUDCOACH_DATA", "data/brotato.json"),
        help="path to brotato.json built by build_dataset.py "
             "(also settable via SPUDCOACH_DATA)")
    return parser.parse_args(argv).data


def main() -> None:
    ds = dataset.load_dataset(_data_path())
    build_server(ds).run()
```

- [ ] **Step 4: Update `pyproject.toml`** — rename the distribution and add the script + URLs (package dir stays `brotato_coach`):

```toml
[project]
name = "spudcoach"
version = "0.2.0"
description = "Deterministic Brotato theorycrafter core + MCP server (spud coach)"
requires-python = ">=3.11"
license = { text = "MIT" }
classifiers = [
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
]
dependencies = ["mcp>=1.2.0"]

[project.scripts]
spudcoach = "brotato_coach.server:main"

[project.urls]
Homepage = "https://spudcoach.fyi"
Repository = "https://github.com/BrendanL79/spud-coach"
```

(keep the existing `[dependency-groups]`, `[tool.pytest.ini_options]`, `[build-system]`, and `[tool.hatch.build.targets.wheel]` sections unchanged)

- [ ] **Step 5: Verify** — run the suite plus a sync (the rename changes the installed project):

Run: `uv sync && uv run pytest -v && uv run spudcoach --data /nonexistent.json`
Expected: tests PASS; the `spudcoach` command fails with `FileNotFoundError: dataset not found at /nonexistent.json; run build_dataset.py first` (a traceback is fine — it proves the entry point and the flag work).

- [ ] **Step 6: Update README** — in the install/run section, document:

```markdown
## Run

    uvx spudcoach --data /path/to/brotato.json

The dataset is never distributed — build your own from your Brotato install:
`uv run python build_dataset.py --game-version <ver> --generated-at <iso8601>`
(see docs/extraction-setup.md). `SPUDCOACH_DATA` works as an env-var alternative
to `--data`.
```

- [ ] **Step 7: Commit**

```bash
git add brotato_coach/server.py pyproject.toml uv.lock README.md tests/test_server.py
git commit -m "feat(ship): spudcoach entry point + --data/SPUDCOACH_DATA dataset path"
```

---

## Phase B — evidence tasks (require a machine with `extracted/` + `recovered/`)

Prerequisite for all three tasks: regenerate the trees per `docs/extraction-setup.md` (`unpack_pck.py` on `game_files/Brotato.pck`, gdre_tools for `recovered/`). None of these directories may ever be committed.

Carried from the Phase A final review, to decide with evidence in hand:
- Task 12: when adding the first PROC_MODELS entry, decide whether a modeled effect with a missing `chance` field should error rather than default to 1.0 (a silent 100%-proc claim).
- Task 12: extract the proc-aggregation loop from `build_weapon_record` into `procs.aggregate_proc_dps(effects, dps0, slope, models)` when adding the second `damage_source` branch (CodeRabbit suggestion on PR #3, deferred — pure churn until the loop grows).
- Task 14: decide whether answer payloads should surface `display_name` alongside slug `name`, and whether to bump `schema_version` for the proc-aware/localized dataset.

### Task 12: verify the explode proc and add the first `PROC_MODELS` entry

**Files:**
- Create: `docs/proc-mechanics.md`
- Modify: `brotato_coach/builders/procs.py`
- Test: `tests/test_build_weapons.py`, `tests/test_shipped_dataset.py`

**Interfaces:**
- Consumes: the `PROC_MODELS` schema (Task 2).
- Produces: a verified `"effect_explode_custom"` model entry; `docs/proc-mechanics.md` recording the evidence.

- [ ] **Step 1: Gather evidence** — run and read:

```bash
find extracted recovered -iname '*explod*'
grep -rn "effect_explode" recovered/ extracted/ --include='*.gd' --include='*.tres' | head -30
cat recovered/effects/weapons/exploding_effect.gd   # or the path find reported
```

Answer from the code: (a) what damage does the explosion deal — the weapon's damage line, a scene-defined flat value, or a multiplier of the hit? (b) does it scale with the weapon's scaling stats? (c) is there an in-code AoE radius/enemy count?

- [ ] **Step 2: Record the evidence** — create `docs/proc-mechanics.md` in the style of `docs/stat-mechanics.md`: one bullet per verified fact, each citing the `.gd`/`.tres` file and quoting the relevant line(s). Also list the distinct effect `key` values across all weapon effect `.tres` files (`grep -rh '^key = ' extracted/weapons/ | sort | uniq -c`) so future model entries have a worklist.

- [ ] **Step 3: Encode** — add the entry to `PROC_MODELS` in `brotato_coach/builders/procs.py`, with the multiplier the code showed (expected shape, adjust to evidence):

```python
PROC_MODELS: dict[str, dict] = {
    # Shredder-style exploding shot: 50% chance per hit to re-deal the weapon's
    # damage as an explosion. Evidence: docs/proc-mechanics.md
    # (recovered/effects/weapons/exploding_effect.gd).
    "effect_explode_custom": {
        "damage_source": "weapon_damage",
        "damage_multiplier": 1.0,
        "default_enemies_hit": 1.0,  # conservative single-target assumption
    },
}
```

If the evidence contradicts `damage_source: "weapon_damage"` (e.g. the explosion uses a flat scene-defined damage), extend the builder loop in `weapons.py` with a `"flat"` branch (`p0 = chance * enemies_hit * damage * accuracy / ct`, slope contribution 0) — TDD it exactly like Task 2.

- [ ] **Step 4: Test** — in `tests/test_build_weapons.py`, add:

```python
def test_default_proc_models_cover_explode():
    rec = build_weapon_record(STATS, DATA, [EXPLODE_EFFECT], weapon_id="w",
                              name="W", tier=4)  # no injected models: real table
    assert rec["proc_dps_at_zero_rd"] > 0
    assert rec["unmodeled_effects"] == []
```

and in `tests/test_shipped_dataset.py` (inside the skipif-guarded test), append:

```python
    # proc weapons carry a nonzero expected proc line
    sh = query.get_weapon(ds, "Shredder", tier=1)
    assert sh["proc_dps_at_zero_rd"] > 0
```

- [ ] **Step 5: Rebuild the dataset and run everything**

```bash
uv run python build_dataset.py --game-version <ver> --generated-at <iso8601>
uv run pytest -v
```

Expected: all PASS including `test_shipped_dataset_is_complete`.

- [ ] **Step 6: Commit** (code + docs only — never the dataset)

```bash
git add brotato_coach/builders/procs.py docs/proc-mechanics.md tests/test_build_weapons.py tests/test_shipped_dataset.py
git commit -m "feat(procs): verified effect_explode_custom model from decompiled code"
```

### Task 13: research + encode the five remaining displayed stats

**Files:**
- Modify: `docs/stat-mechanics.md`, `brotato_coach/builders/mechanics.py`
- Test: `tests/test_mechanics.py`

**Interfaces:**
- Consumes: `_m(..., summary=...)` (Task 7).
- Produces: `STAT_MECHANICS` entries for `stat_percent_damage`, `stat_armor`, `stat_luck`, `stat_harvesting`, `stat_range` — completing all 16 displayed stats (plus the already-covered hidden `stat_curse`/`knockback`).

- [ ] **Step 1: Gather evidence** — the files that hold each formula:

```bash
grep -n "get_capped_stat\|get_max_capped_stat" -r recovered/           # which stats cap, and ceilings
grep -rn "armor\|damage_reduction" recovered/ --include='*.gd' | head  # armor curve + negative armor
grep -rn "luck" recovered/ --include='*.gd' | head                     # loot/roll effects
grep -rn "harvesting" recovered/ --include='*.gd' | head               # end-of-wave payout + growth
grep -rn "percent_damage\|stat_damage" recovered/ --include='*.gd' | head
grep -rn "stat_range" recovered/ --include='*.gd' | head
```

Read the hits (expect `utils.gd`, `player.gd`/`entity.gd` take_damage, `run_data.gd`, `*_shooting_data.gd`).

- [ ] **Step 2: Record** — append one evidence-cited bullet per stat to `docs/stat-mechanics.md` (formula, cap or explicit "not in utils.gd's cap list", negative-value behavior).

- [ ] **Step 3: Write the failing coverage test** — append to `tests/test_mechanics.py`:

```python
DISPLAYED_STATS = (
    "stat_armor", "stat_attack_speed", "stat_crit_chance", "stat_dodge",
    "stat_elemental_damage", "stat_engineering", "stat_harvesting",
    "stat_hp_regeneration", "stat_lifesteal", "stat_luck", "stat_max_hp",
    "stat_melee_damage", "stat_percent_damage", "stat_range",
    "stat_ranged_damage", "stat_speed",
)


def test_all_displayed_stats_have_mechanics():
    missing = [s for s in DISPLAYED_STATS if s not in STAT_MECHANICS]
    assert missing == []
```

Run: `uv run pytest tests/test_mechanics.py -v` — expected FAIL listing the five missing stats.

- [ ] **Step 4: Encode** — add the five `_m(...)` entries with evidence-backed `summary` strings (and `cap=`/`safe_below_zero=`/etc. flags as the code shows). Do not encode anything the code didn't show.

- [ ] **Step 5: Run the full suite** — `uv run pytest -v`, expected all PASS.

- [ ] **Step 6: Commit**

```bash
git add docs/stat-mechanics.md brotato_coach/builders/mechanics.py tests/test_mechanics.py
git commit -m "feat(mechanics): verified entries for armor/luck/harvesting/percent_damage/range"
```

### Task 14: confirm the translation key scheme + rebuild with localized text

**Files:**
- Modify (only if the survey contradicts the `name`/`description` field assumption): `brotato_coach/builders/weapons.py`, `items.py`, `characters.py`, `sets.py`
- Test: `tests/test_shipped_dataset.py`

**Interfaces:**
- Consumes: Task 9's wiring (reads `name`/`description` translation keys off each data `.tres`).
- Produces: a rebuilt local `data/brotato.json` with real localized `display_name`/`description`/effect `text`.

- [ ] **Step 1: Survey the real data**:

```bash
head -3 recovered/.assets/resources/translations/translations.csv
grep -n '^name\|^description' extracted/weapons/ranged/shredder/1/*_data.tres
grep -n '^name\|^description' extracted/items/all/handcuffs/handcuffs_data.tres
```

Confirm: (a) the CSV header's key + `en` columns; (b) the data `.tres` field names that hold the translation keys. If the fields are named differently (e.g. `text_key` on the data resource), change the `d.get("name")`/`d.get("description")` reads in the four builders to the real field names — the tests from Task 9 pin the behavior, so only the field-name strings in fixtures and builders change together.

- [ ] **Step 2: Rebuild and spot-check**:

```bash
uv run python build_dataset.py --game-version <ver> --generated-at <iso8601>
uv run python -c "import json; ds=json.load(open('data/brotato.json')); w=[x for x in ds['weapons'] if x['id']=='weapon_shredder'][0]; print(w['display_name'], '|', w['description'][:60])"
```

Expected: the build prints `(localized)` and Shredder shows its real in-game name and a non-empty description.

- [ ] **Step 3: Pin it in the shipped-dataset test** — append inside `test_shipped_dataset_is_complete`:

```python
    # localization resolved real in-game text
    sh = query.get_weapon(ds, "Shredder", tier=1)
    assert sh["display_name"] == "Shredder"
    assert sh["description"] != ""
```

- [ ] **Step 4: Run the full suite** — `uv run pytest -v`, expected all PASS.

- [ ] **Step 5: Commit** (builders/tests only — never `data/brotato.json`)

```bash
git add tests/test_shipped_dataset.py brotato_coach/builders/
git commit -m "feat(l10n): confirm translation key scheme against real extraction"
```

---

## Phase C — publish checklist (every step needs explicit user go-ahead)

These are outward-facing, mostly one-time manual actions — not TDD tasks. Do **not** run any of them without the user's confirmation.

- [ ] Confirm PyPI name `spudcoach` is free (https://pypi.org/project/spudcoach/), create the project via PyPI **trusted publishing** from the GitHub repo (or a token), then:

```bash
uv build          # builds sdist+wheel from pyproject (dist name spudcoach)
uv publish        # uploads; needs the credentials above
```

- [ ] Smoke-test the published package from a clean directory: `uvx spudcoach --data /path/to/brotato.json` connects over stdio (e.g. via `npx @modelcontextprotocol/inspector uvx spudcoach --data ...`).
- [ ] Tag and push the release: `git tag v0.2.0 && git push origin v0.2.0`; write GitHub release notes summarizing the roadmap features.
- [ ] Stand up spudcoach.fyi: a single static install page (GitHub Pages is enough) — install command, MCP client config snippet, dataset-build disclaimer (no game data distributed).
- [ ] Submit to the official MCP registry (https://github.com/modelcontextprotocol/registry) and PR an entry to awesome-mcp-servers. Both PRs need the user's sign-off on wording.

---

## Deferred to a separate plan: bestiary (enemy data)

Deliberately not planned here (per plan-scoping rules — it's an independent subsystem and its data schema is unverified). The roadmap's `entities/units/enemies/` path is an assumption not confirmed by `docs/extraction-setup.md`. Before writing that plan, run this survey on the extraction machine and paste the results into the new plan's spec:

```bash
find extracted -type d -path '*enem*' | head -20
find extracted -path '*entities/units*' -name '*.tres' | head -20
grep -rliE 'wave|danger|spawn' extracted --include='*.tres' | head -20
grep -rn "danger\|difficulty" recovered/ --include='*.gd' | grep -i "enem\|spawn\|wave" | head -20
sed -n 1,60p recovered/**/entity_service.gd   # confirmed to hold enemy HP/damage scaling (curse sqrt factor)
```

The bestiary plan should mirror the existing pattern: `discover.find_enemy_dirs()` → `builders/enemies.py:build_enemy_record()` → dataset `"enemies"` key → `get_enemy`/`list_enemies`/wave-threat answer functions → MCP tools. Save-file vocabulary for wave context: `current_wave`, `current_difficulty` (danger), `current_zone`, `bosses_spawn` (see `tools/brotato_inspect.py:53-56`).
