# Weapon Cadence Reporting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface source-verified attack cadence (rate of fire, per-attack burst, dead-window gap range, streakiness) alongside DPS on the coach's weapon-efficacy reports, without changing any DPS value or ranking.

**Architecture:** Pure math added to `calc.py`; thin reporting wrappers in `answers.py` attach a `cadence` object to `weapon_dps` / `compare_weapons` / `evaluate_run`. One additive `burst_reload` boolean on the weapon record flags bimodal reload weapons. Docs capture the verified attack-timer model. No dataset schema-version bump.

**Tech Stack:** Python 3.11+, `uv`, pytest, ruff. Deterministic; hand-verified test values with `math.isclose`.

## Global Constraints

- Python 3.11+, managed with `uv`. Test: `uv run pytest`. Lint: `uv run ruff check .` must stay green.
- TDD: write the failing test first, watch it fail, then implement.
- Never commit `data/brotato.json`, `extracted/`, `recovered/` (gitignored, copyrighted).
- No change to any `dps`, `dps_at_zero_rd`, `dps_slope_per_rd`, proc-line value, or ranking sort order. These are regression boundaries — existing tests must stay green untouched.
- Evidence citations in docs must be re-pinned against `recovered/` at write time and verified, not copied from this plan.
- Verified constants (from `recovered/weapons/weapon.gd`): cooldown counts down only while not shooting (`:192-193`); on shoot `_current_cooldown = get_next_cooldown()` (`:323`); `get_next_cooldown` returns `rand_range(max(1, basis-Δ), basis+Δ)` (`:337-349`); `Δ = min(N·basis/5, N·5)` frames, `N = min(nb_weapons, 6)` (`:352-354`). Cooldown units are frames at 60 fps.

---

### Task 1: `calc.cooldown_jitter` — verified per-shot cooldown range

**Files:**
- Modify: `brotato_coach/calc.py`
- Test: `tests/test_calc.py`

**Interfaces:**
- Consumes: nothing (pure).
- Produces: `cooldown_jitter(cooldown_basis_frames: float, weapon_count: int) -> tuple[float, float]` returning `(min_frames, max_frames)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_calc.py`:

```python
def test_cooldown_jitter_slow_weapon_single():
    # Shredder-like basis 45 frames, N=1: delta=min(45/5, 5)=5 -> [40, 50]
    lo, hi = calc.cooldown_jitter(45, 1)
    assert math.isclose(lo, 40.0)
    assert math.isclose(hi, 50.0)


def test_cooldown_jitter_slow_weapon_six_weapons():
    # basis 45, N=6: delta=min(6*45/5=54, 6*5=30)=30 -> [15, 75]
    lo, hi = calc.cooldown_jitter(45, 6)
    assert math.isclose(lo, 15.0)
    assert math.isclose(hi, 75.0)


def test_cooldown_jitter_fast_weapon_floors_at_one():
    # Minigun-like basis 3, N=6: delta=min(3.6, 30)=3.6; basis-delta=-0.6 -> floored to 1
    lo, hi = calc.cooldown_jitter(3, 6)
    assert math.isclose(lo, 1.0)
    assert math.isclose(hi, 6.6)


def test_cooldown_jitter_clamps_weapon_count_to_six():
    assert calc.cooldown_jitter(45, 99) == calc.cooldown_jitter(45, 6)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_calc.py -k cooldown_jitter -v`
Expected: FAIL with `AttributeError: module 'brotato_coach.calc' has no attribute 'cooldown_jitter'`

- [ ] **Step 3: Implement**

Add to `brotato_coach/calc.py` (after `cycle_time`):

```python
def cooldown_jitter(cooldown_basis_frames: float, weapon_count: int) -> tuple[float, float]:
    """Per-shot cooldown range (frames) from the engine's anti-sync randomization.

    Each shot draws cooldown uniformly from [max(1, basis - Δ), basis + Δ],
    Δ = min(N·basis/5, N·5), N = min(weapon_count, 6) (weapon.gd:337-354). The
    spread grows with weapon count, de-synchronizing volleys. Mean = basis, so
    expected DPS is unaffected.
    """
    n = min(max(weapon_count, 1), 6)
    delta = min(n * cooldown_basis_frames / 5.0, n * 5.0)
    return (max(1.0, cooldown_basis_frames - delta), cooldown_basis_frames + delta)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_calc.py -k cooldown_jitter -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/calc.py tests/test_calc.py
git commit -m "feat(coach): add verified cooldown_jitter cadence primitive"
```

---

### Task 2: `calc.cadence_profile` — assemble the cadence descriptors

**Files:**
- Modify: `brotato_coach/calc.py`
- Test: `tests/test_calc.py`

**Interfaces:**
- Consumes: `cooldown_jitter` (Task 1).
- Produces: `cadence_profile(cycle_time: float, total_dps: float, cooldown_basis_frames: float, weapon_count: int = 1, burst_reload: bool = False) -> dict` with keys `attacks_per_second`, `seconds_between_attacks`, `damage_per_attack`, `cadence`, `gap_range_s` (a `[min, max]` list), `burst_reload`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_calc.py`:

```python
def test_cadence_profile_minigun_sustained():
    # Minigun T4: cycle 0.09s, total_dps 55.5556 at rd0, basis 3 frames
    p = calc.cadence_profile(0.09, 55.5556, 3, weapon_count=1)
    assert math.isclose(p["attacks_per_second"], 1 / 0.09, rel_tol=1e-9)
    assert math.isclose(p["seconds_between_attacks"], 0.09)
    assert math.isclose(p["damage_per_attack"], 5.0, rel_tol=1e-4)  # base_damage 5
    assert p["cadence"] == "sustained"
    assert p["burst_reload"] is False
    # recoil_term = 0.09 - 3/60 = 0.04; N=1 jitter (2.4, 3.6)
    assert math.isclose(p["gap_range_s"][0], 0.04 + 2.4 / 60.0, rel_tol=1e-6)
    assert math.isclose(p["gap_range_s"][1], 0.04 + 3.6 / 60.0, rel_tol=1e-6)


def test_cadence_profile_shredder_bursty_and_invariant():
    # Shredder T4: cycle 1.05s, total_dps 23.8095 at rd0, basis 45 frames
    p = calc.cadence_profile(1.05, 23.8095, 45, weapon_count=1)
    assert p["cadence"] == "bursty"  # ~0.952 atk/s < 1
    assert math.isclose(p["damage_per_attack"], 25.0, rel_tol=1e-4)  # base_damage 25
    # Invariant: damage_per_attack * attacks_per_second == total_dps
    assert math.isclose(
        p["damage_per_attack"] * p["attacks_per_second"], 23.8095, rel_tol=1e-9)


def test_cadence_profile_moderate_label_boundary():
    # cycle 0.5s -> exactly 2 atk/s -> moderate
    assert calc.cadence_profile(0.5, 10.0, 30)["cadence"] == "moderate"
    # cycle exactly 1/3s -> 3 atk/s -> sustained (>= 3)
    assert calc.cadence_profile(1 / 3, 10.0, 20)["cadence"] == "sustained"


def test_cadence_profile_gap_range_widens_with_weapon_count():
    narrow = calc.cadence_profile(1.05, 23.8095, 45, weapon_count=1)["gap_range_s"]
    wide = calc.cadence_profile(1.05, 23.8095, 45, weapon_count=6)["gap_range_s"]
    assert wide[0] < narrow[0]
    assert wide[1] > narrow[1]


def test_cadence_profile_passes_burst_reload_flag():
    assert calc.cadence_profile(0.63, 90.0, 11, burst_reload=True)["burst_reload"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_calc.py -k cadence_profile -v`
Expected: FAIL with `AttributeError: module 'brotato_coach.calc' has no attribute 'cadence_profile'`

- [ ] **Step 3: Implement**

Add to `brotato_coach/calc.py` (after `cooldown_jitter`):

```python
def cadence_profile(cycle_time: float, total_dps: float,
                    cooldown_basis_frames: float, weapon_count: int = 1,
                    burst_reload: bool = False) -> dict:
    """Per-weapon cadence descriptors decomposing DPS into rate x burst, plus
    the verified dead-window gap range. See docs/cadence-mechanics.md.

    Invariant: damage_per_attack * attacks_per_second == total_dps.
    The gap range derives from cooldown_jitter; the recoil portion of the
    cycle is common to both bounds and cancels, so no separate recoil value
    is needed. Caller must ensure cycle_time > 0.
    """
    aps = 1.0 / cycle_time
    lo_f, hi_f = cooldown_jitter(cooldown_basis_frames, weapon_count)
    recoil_term = cycle_time - cooldown_basis_frames / 60.0
    if aps >= 3.0:
        label = "sustained"
    elif aps >= 1.0:
        label = "moderate"
    else:
        label = "bursty"
    return {
        "attacks_per_second": aps,
        "seconds_between_attacks": cycle_time,
        "damage_per_attack": total_dps * cycle_time,
        "cadence": label,
        "gap_range_s": [recoil_term + lo_f / 60.0, recoil_term + hi_f / 60.0],
        "burst_reload": burst_reload,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_calc.py -k cadence_profile -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/calc.py tests/test_calc.py
git commit -m "feat(coach): add cadence_profile primitive"
```

---

### Task 3: Attach `cadence` to `answers.weapon_dps`

**Files:**
- Modify: `brotato_coach/answers.py:27-49` (`weapon_dps`)
- Test: `tests/test_answers.py`

**Interfaces:**
- Consumes: `calc.cadence_profile` (Task 2).
- Produces: `weapon_dps(ds, name, tier, stats, aoe_enemies_hit=1.0, character=None, weapon_count=1)` — return dict gains a `cadence` key **only when** `rec["cycle_time"] > 0`.

- [ ] **Step 1: Update the test fixture and write the failing test**

In `tests/test_answers.py`, add `cycle_time` and `cooldown` to the Minigun record in `DS` (leave the others as-is to prove graceful degradation). Change the Minigun line to:

```python
        {"id": "weapon_minigun", "name": "Minigun", "tier": 4,
         "dps_at_zero_rd": 55.5556, "dps_slope_per_rd": 8.3333,
         "cycle_time": 0.09, "cooldown": 3, "scaling_stats": []},
```

Then append this test:

```python
def test_weapon_dps_includes_cadence_when_cycle_time_present():
    result = answers.weapon_dps(DS, "Minigun", 4, {"ranged_damage": 0})
    cad = result["cadence"]
    assert cad["cadence"] == "sustained"
    assert math.isclose(cad["attacks_per_second"], 1 / 0.09, rel_tol=1e-9)
    # Invariant holds against the report's own dps
    assert math.isclose(
        cad["damage_per_attack"] * cad["attacks_per_second"], result["dps"], rel_tol=1e-9)


def test_weapon_dps_omits_cadence_when_cycle_time_absent():
    # Laser T2 fixture has no cycle_time -> no cadence, dps unchanged
    result = answers.weapon_dps(DS, "Laser", 2, {"ranged_damage": 0})
    assert "cadence" not in result
    assert math.isclose(result["dps"], 30.0, rel_tol=1e-4)
```

- [ ] **Step 2: Run tests to verify the new one fails**

Run: `uv run pytest tests/test_answers.py -k cadence -v`
Expected: FAIL — `KeyError: 'cadence'` on the first new test.

- [ ] **Step 3: Implement**

In `brotato_coach/answers.py`, change the `weapon_dps` signature and append cadence before returning. Replace the function body's signature line and return:

```python
def weapon_dps(ds: dict, name: str, tier: int, stats: dict,
               aoe_enemies_hit: float = 1.0, character: str | None = None,
               weapon_count: int = 1) -> dict:
    rec = query.get_weapon(ds, name, tier=tier)
    if "id" not in rec:
        return rec
    if character is not None:
        stats = display_stats(ds, character, stats)
    rd = float(stats.get("ranged_damage", 0))
    base = calc.dps_at(rec["dps_at_zero_rd"], rec["dps_slope_per_rd"], rd)
    proc = aoe_enemies_hit * calc.dps_at(rec.get("proc_dps_at_zero_rd", 0.0),
                                         rec.get("proc_dps_slope_per_rd", 0.0), rd)
    result = {
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
    ct = float(rec.get("cycle_time", 0.0) or 0.0)
    if ct > 0:
        result["cadence"] = calc.cadence_profile(
            ct, base + proc, float(rec.get("cooldown", 0.0)),
            weapon_count=weapon_count,
            burst_reload=bool(rec.get("burst_reload", False)))
    return result
```

- [ ] **Step 4: Run the full answers suite to verify pass + no regression**

Run: `uv run pytest tests/test_answers.py -v`
Expected: PASS (all existing tests plus the two new ones; DPS assertions unchanged).

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/answers.py tests/test_answers.py
git commit -m "feat(coach): attach cadence to weapon_dps"
```

---

### Task 4: Thread `weapon_count` + cadence rows through `compare_weapons`

**Files:**
- Modify: `brotato_coach/answers.py:52-64` (`compare_weapons`)
- Test: `tests/test_answers.py`

**Interfaces:**
- Consumes: `weapon_dps` with `weapon_count` (Task 3).
- Produces: `compare_weapons(ds, names_with_tiers, stats, aoe_enemies_hit=1.0, character=None, weapon_count=1)` — each ranking row gains a `cadence` key when its weapon record supplies `cycle_time`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_answers.py`:

```python
def test_compare_weapons_rows_carry_cadence():
    result = answers.compare_weapons(
        DS, [("Minigun", 4), ("Laser", 2)], {"ranged_damage": 0}, weapon_count=2)
    rows = {r["name"]: r for r in result["ranking"]}
    # Minigun fixture has cycle_time -> cadence present
    assert rows["Minigun"]["cadence"]["cadence"] == "sustained"
    # Laser fixture lacks cycle_time -> no cadence key, but still ranked
    assert "cadence" not in rows["Laser"]
    # Sort order still DPS-descending, unchanged
    assert result["ranking"][0]["name"] == "Minigun"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_answers.py::test_compare_weapons_rows_carry_cadence -v`
Expected: FAIL — `KeyError: 'cadence'` on the Minigun row.

- [ ] **Step 3: Implement**

Replace `compare_weapons` in `brotato_coach/answers.py`:

```python
def compare_weapons(ds: dict, names_with_tiers: list, stats: dict,
                    aoe_enemies_hit: float = 1.0, character: str | None = None,
                    weapon_count: int = 1) -> dict:
    if character is not None:
        stats = display_stats(ds, character, stats)
    rows = []
    for name, tier in names_with_tiers:
        r = weapon_dps(ds, name, tier, stats, aoe_enemies_hit,
                       weapon_count=weapon_count)
        if "dps" in r:
            row = {"name": r["name"], "tier": tier, "dps": r["dps"],
                   "base_dps": r["base_dps"], "proc_dps": r["proc_dps"],
                   "unmodeled_effects": r["unmodeled_effects"]}
            if "cadence" in r:
                row["cadence"] = r["cadence"]
            rows.append(row)
    rows.sort(key=lambda x: x["dps"], reverse=True)
    return {"ranking": rows}
```

- [ ] **Step 4: Run the full answers suite**

Run: `uv run pytest tests/test_answers.py -v`
Expected: PASS (all, including the new row-cadence test).

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/answers.py tests/test_answers.py
git commit -m "feat(coach): carry cadence + weapon_count through compare_weapons"
```

---

### Task 5: `evaluate_run` computes cadence at the run's real weapon count

**Files:**
- Modify: `brotato_coach/answers.py:173-174` (inside `evaluate_run`)
- Test: `tests/test_run_report.py`

**Interfaces:**
- Consumes: `compare_weapons` with `weapon_count` (Task 4).
- Produces: `evaluate_run`'s `weapon_dps_ranking` rows carry cadence computed at `weapon_count = len(build["weapons"])`.

- [ ] **Step 1: Update the run-report fixture and write the failing test**

In `tests/test_run_report.py`, add `cycle_time` + `cooldown` to both weapons in `DS`:

```python
        {"id": "weapon_smg", "name": "SMG", "tier": 1, "sets": ["Gun"],
         "dps_at_zero_rd": 10.0, "dps_slope_per_rd": 1.0,
         "cycle_time": 0.3, "cooldown": 12, "scaling_stats": []},
        {"id": "weapon_pistol", "name": "Pistol", "tier": 1, "sets": ["Gun"],
         "dps_at_zero_rd": 5.0, "dps_slope_per_rd": 0.5,
         "cycle_time": 0.6, "cooldown": 30, "scaling_stats": []},
```

Then append:

```python
def test_evaluate_run_ranking_has_cadence_at_loadout_count():
    report = answers.evaluate_run(DS, _run())
    ranking = report["weapon_dps_ranking"]
    assert all("cadence" in row for row in ranking)
    # Two weapons in the loadout -> jitter computed at N=2, not N=1.
    smg = next(r for r in ranking if r["name"] == "SMG")
    n1 = answers.compare_weapons(
        DS, [("SMG", 1)], {"ranged_damage": 8}, weapon_count=1)["ranking"][0]
    assert smg["cadence"]["gap_range_s"] != n1["cadence"]["gap_range_s"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_run_report.py::test_evaluate_run_ranking_has_cadence_at_loadout_count -v`
Expected: FAIL — either `KeyError: 'cadence'` or the gap ranges compare equal (weapon_count not threaded).

- [ ] **Step 3: Implement**

In `brotato_coach/answers.py`, change the `compare_weapons` call inside `evaluate_run` (currently at `:173-174`):

```python
    ranking = compare_weapons(
        ds, [(w["id"], w["tier"]) for w in build["weapons"]], stats,
        weapon_count=len(build["weapons"]))["ranking"]
```

- [ ] **Step 4: Run the run-report suite**

Run: `uv run pytest tests/test_run_report.py -v`
Expected: PASS (existing tests unchanged; new cadence test passes).

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/answers.py tests/test_run_report.py
git commit -m "feat(coach): evaluate_run computes cadence at real weapon count"
```

---

### Task 6: Additive `burst_reload` field on the weapon record

**Files:**
- Modify: `brotato_coach/builders/weapons.py:133-162` (the returned record dict)
- Test: `tests/test_build_weapons.py`

**Interfaces:**
- Consumes: the `burst` local already computed at `weapons.py:63-67`.
- Produces: `build_weapon_record(...)` output gains `"burst_reload": bool`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_build_weapons.py`:

```python
def test_weapon_record_marks_burst_reload_false_for_normal_weapon():
    rec = build_weapon_record(STATS, DATA, weapon_id="weapon_shredder",
                              name="Shredder", tier=4)
    assert rec["burst_reload"] is False


def test_weapon_record_marks_burst_reload_true_for_revolver():
    stats = ('[gd_resource type="Resource" format=2]\n[resource]\n'
             'cooldown = 11\ndamage = 40\naccuracy = 0.9\nrecoil_duration = 0.1\n'
             'scaling_stats = [ [ "stat_ranged_damage", 2.0 ] ]\n'
             'additional_cooldown_every_x_shots = 6\nadditional_cooldown_multiplier = 8.0\n')
    data = '[gd_resource type="Resource" format=2]\n[resource]\neffects = [  ]\n'
    rec = build_weapon_record(stats, data, weapon_id="w", name="W", tier=4)
    assert rec["burst_reload"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_build_weapons.py -k burst_reload -v`
Expected: FAIL — `KeyError: 'burst_reload'`.

- [ ] **Step 3: Implement**

In `brotato_coach/builders/weapons.py`, add one line to the returned record dict (place it next to `cooldown`, `:140`):

```python
        "burst_reload": burst is not None,
```

- [ ] **Step 4: Run the build-weapons suite**

Run: `uv run pytest tests/test_build_weapons.py -v`
Expected: PASS (existing tests plus the two new ones).

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/builders/weapons.py tests/test_build_weapons.py
git commit -m "feat(coach): flag burst-reload weapons on the weapon record"
```

---

### Task 7: Expose `weapon_count` + cadence on the server tools

**Files:**
- Modify: `brotato_coach/server.py:126-168` (`weapon_dps` and `compare_weapons` tools)
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `answers.weapon_dps` / `answers.compare_weapons` with `weapon_count` (Tasks 3-4).
- Produces: both MCP tools accept optional `weapon_count: int = 1` and forward it; docstrings describe the `cadence` object.

- [ ] **Step 1: Update the server fixture and write the failing test**

In `tests/test_server.py`, add `cycle_time` + `cooldown` to the Minigun record in `DS`:

```python
    "weapons": [{"id": "weapon_minigun", "name": "Minigun", "tier": 4,
                 "dps_at_zero_rd": 55.5556, "dps_slope_per_rd": 8.3333,
                 "cycle_time": 0.09, "cooldown": 3, "scaling_stats": []}],
```

Then append:

```python
def test_weapon_dps_tool_returns_cadence_and_honors_weapon_count():
    server = build_server(DS)
    r1 = asyncio.run(_call(server, "weapon_dps", name="Minigun", tier=4,
                           stats={"ranged_damage": 10}, weapon_count=1))
    r6 = asyncio.run(_call(server, "weapon_dps", name="Minigun", tier=4,
                           stats={"ranged_damage": 10}, weapon_count=6))
    assert r1["cadence"]["cadence"] == "sustained"
    # gap range widens with weapon count
    assert r6["cadence"]["gap_range_s"][1] > r1["cadence"]["gap_range_s"][1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_server.py::test_weapon_dps_tool_returns_cadence_and_honors_weapon_count -v`
Expected: FAIL — `TypeError` (unexpected `weapon_count`) or `KeyError: 'cadence'`.

- [ ] **Step 3: Implement**

In `brotato_coach/server.py`, update the `weapon_dps` tool (`:126-148`): add the param and forward it, and append a line to the docstring.

```python
    def weapon_dps(name: str, tier: int, stats: Stats,
                   aoe_enemies_hit: float = 1.0,
                   character: str | None = None,
                   weapon_count: int = 1) -> dict[str, Any]:
```

Add to that docstring (before the closing `"""`):

```
        `cadence` decomposes DPS into rate x burst: attacks_per_second,
        damage_per_attack, a cadence label (sustained/moderate/bursty),
        seconds_between_attacks, and gap_range_s — the verified dead-window
        range between volleys. gap_range_s widens with `weapon_count` (the
        engine randomizes cooldowns to de-sync volleys, harder with more
        weapons); pass your actual equipped count for a real range.
        burst_reload flags bimodal reload weapons (Revolver, Chain Gun) whose
        averaged rate hides the fast-then-reload rhythm.
```

Change the forwarding call to include `weapon_count=weapon_count`:

```python
        return _safe(answers.weapon_dps)(ds=ds, name=name, tier=tier,
                                         stats=stats.as_dict(),
                                         aoe_enemies_hit=aoe_enemies_hit,
                                         character=character,
                                         weapon_count=weapon_count)
```

Update the `compare_weapons` tool (`:151-168`): add `weapon_count: int = 1` to the signature, forward it, and add a one-line docstring note.

```python
    def compare_weapons(names_with_tiers: list[tuple[str, int]], stats: Stats,
                        aoe_enemies_hit: float = 1.0,
                        character: str | None = None,
                        weapon_count: int = 1) -> dict[str, Any]:
```

Add to its docstring (before closing `"""`):

```
        Each row carries a `cadence` object (see weapon_dps). Pass
        `weapon_count` = your equipped weapon count so the gap range reflects
        the engine's weapon-count-scaled cooldown jitter.
```

Change the forwarding lambda to thread `weapon_count`:

```python
        return _safe(lambda **kw: answers.compare_weapons(
            ds, [tuple(x) for x in kw["names_with_tiers"]], kw["stats"],
            kw["aoe_enemies_hit"], kw["character"], kw["weapon_count"]))(
            names_with_tiers=names_with_tiers, stats=stats.as_dict(),
            aoe_enemies_hit=aoe_enemies_hit, character=character,
            weapon_count=weapon_count)
```

- [ ] **Step 4: Run the server suite**

Run: `uv run pytest tests/test_server.py -v`
Expected: PASS (all, including the new cadence-tool test and `test_all_tools_have_descriptions`).

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/server.py tests/test_server.py
git commit -m "feat(coach): expose cadence + weapon_count on server tools"
```

---

### Task 8: Rewrite the `read_me` primer caveat

**Files:**
- Modify: `brotato_coach/orientation.py:88-100`
- Test: `tests/test_orientation.py`

**Interfaces:**
- Consumes: nothing (static primer text).
- Produces: the primer string replaces the "Attack-timing synchronization is NOT modeled" block with the verified cadence story.

- [ ] **Step 1: Write the failing test**

Look at `tests/test_orientation.py` for how the primer is fetched (a function returning the primer text/dict). Append a test asserting the new content and the removal of the misleading claim. If the primer is exposed as `orientation.read_me()` returning a dict with a text field, adapt the accessor accordingly:

```python
def test_primer_describes_verified_cadence_not_unmodeled_sync():
    text = str(orientation.read_me())
    assert "attacks_per_second" in text
    assert "randomizes cooldowns" in text
    # The old misleading blanket claim is gone.
    assert "Attack-timing synchronization is NOT modeled" not in text
```

(If `read_me` needs a dataset argument in this module, pass the existing test's fixture — mirror the current `tests/test_orientation.py` calling convention.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_orientation.py -k cadence -v`
Expected: FAIL — the new phrases are absent / the old phrase still present.

- [ ] **Step 3: Implement**

In `brotato_coach/orientation.py`, replace the bullet at `:92-100` (the "Attack-timing synchronization is NOT modeled" block) with:

```python
- **Cadence IS surfaced; cross-weapon sync is intentionally not scored.**
  dps is a steady-state AVERAGE. weapon_dps / compare_weapons / evaluate_run
  now also return a `cadence` object per weapon: attacks_per_second,
  damage_per_attack (burst size), a sustained/moderate/bursty label, and
  gap_range_s — the verified dead-window range between volleys. Slow weapons
  have long dead windows every cycle (a horde can close during one), and the
  average hides that; read the cadence, not just the DPS. The engine
  randomizes each shot's cooldown (rand_range around the base, jitter growing
  with weapon count) to DE-synchronize volleys — so a loadout of similar
  weapons does NOT reliably volley in unison, and no cross-weapon
  "synchronization risk" score is offered (it would mislead). gap_range_s
  already reflects that weapon-count-scaled jitter.
- **Burst-reload weapons are bimodal.** Revolver (every 6 shots) and Chain Gun
  (every 100) fire fast then take a long reload; `burst_reload: true` marks
  them. attacks_per_second is the average, not the felt fast-then-reload
  rhythm — flag this when it matters.
```

- [ ] **Step 4: Run the orientation suite**

Run: `uv run pytest tests/test_orientation.py -v`
Expected: PASS (existing primer tests plus the new one).

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/orientation.py tests/test_orientation.py
git commit -m "docs(coach): primer describes verified cadence, drops sync-unmodeled claim"
```

---

### Task 9: Cadence mechanics doc + roadmap amendment

**Files:**
- Create: `docs/cadence-mechanics.md`
- Modify: `docs/roadmap.md:36-50` (the "Loadout timing/consistency modeling" entry)

**Interfaces:** none (documentation).

- [ ] **Step 1: Re-verify citations against the source**

Open `recovered/weapons/weapon.gd` and `recovered/weapons/shooting_behaviors/ranged_weapon_shooting_behavior.gd`. Confirm each line reference below still points at the cited code (the build may have shifted line numbers): cooldown ticks only while not shooting; `get_next_cooldown` randomization; `get_max_rand_cooldown` weapon-count scaling; wave-start 180-frame cap; the `set_shooting(true/false)` recoil bracket. Correct any drifted line numbers before writing.

- [ ] **Step 2: Write `docs/cadence-mechanics.md`**

```markdown
# Attack cadence mechanics

How the coach models a weapon's *timing*, verified against the decompiled
source. Companion to `docs/stat-mechanics.md` and `docs/proc-mechanics.md`.

## The attack cycle

On fire, projectiles spawn immediately, then the weapon enters its recoil
animation: `set_shooting(true)`, two tweens of `recoil_duration` each, then
`set_shooting(false)` (`ranged_weapon_shooting_behavior.gd:14-48`). Cooldown
counts down **only while not shooting** (`weapon.gd:192-193`). So:

    cycle_time = 2 * recoil_duration + cooldown / 60   (seconds; cooldown in frames @60fps)

matching `calc.cycle_time`. Burst-reload weapons add an amortized reload term.

## Cooldown is randomized (anti-synchronization)

On each shot, `_current_cooldown = get_next_cooldown()` (`weapon.gd:323`),
which returns `rand_range(max(1, basis - Δ), basis + Δ)` (`weapon.gd:337-349`):

    Δ = min(N * basis / 5, N * 5)   frames,   N = min(nb_weapons, 6)

(`weapon.gd:352-354`). The spread GROWS with weapon count — the engine
deliberately de-synchronizes volleys, harder the more weapons you carry. The
first cooldown of a wave uses a basis capped at 180 frames if basis >= 180
(`weapon.gd:344-345`). The draw is symmetric around basis, so E[cooldown] =
basis and expected DPS is unaffected **except when the low bound floors at 1**
(`max(1, basis - Δ)`, i.e. basis - Δ < 1 — fast weapons at high weapon counts,
e.g. a 6x Minigun at basis 3 draws from [1, 6.6], mean 3.8 not 3). There the
mean skews above basis: those weapons fire slightly slower than basis implies
and nominal DPS modestly overstates them. The coach's `cycle_time` uses raw
basis and does not model this floor-skew (see the roadmap).

## Consequences the coach reports

- `attacks_per_second`, `seconds_between_attacks` — rate of fire.
- `damage_per_attack = dps * cycle_time` — burst size; the invariant
  `damage_per_attack * attacks_per_second == dps` always holds.
- `cadence` label: sustained (>= 3/s), moderate (1-3/s), bursty (< 1/s).
- `gap_range_s` — the verified min/max seconds between volleys at a given
  weapon count. Streakiness is a PER-WEAPON property: slow weapons have Δ
  capped at N*5 frames (<= 0.5s), so their long dead window barely jitters,
  while fast weapons get jitter exceeding their whole cooldown (fully
  smoothed). No cross-weapon "synchronization risk" score is offered — the
  randomization above shows unison is actively prevented, so such a score
  would mislead.

## Known limitation: burst-reload weapons

Revolver (every 6 shots, tiers 2-4) and Chain Gun (every 100, tier 4) — the
only base-game weapons with `additional_cooldown_every_x_shots` set — have a
bimodal cadence (fast, then a long reload). `cycle_time` amortizes the reload,
so `attacks_per_second` is an average, not the felt rhythm; `burst_reload:
true` marks them.
```

- [ ] **Step 3: Amend the roadmap entry**

In `docs/roadmap.md`, replace the "Loadout timing/consistency modeling" entry (`:36-50`) with a corrected version:

```markdown
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
```

Also add the floor-skew as a bullet under `docs/cadence-mechanics.md`'s
"Consequences the coach reports" section (after the `gap_range_s` bullet):

```markdown
- **Floor-skew caveat.** When `basis - Δ < 1` the cooldown draw floors at 1,
  lifting the mean above basis (fast weapons at high weapon counts). Those
  weapons fire slightly slower than basis implies; `cycle_time`/DPS use raw
  basis and do not model this — nominal DPS modestly overstates such builds.
  See the roadmap.
```

- [ ] **Step 4: Verify the docs render and links resolve**

Run: `uv run ruff check .`
Expected: PASS (docs don't affect lint, but confirm nothing else broke).
Manually confirm `docs/cadence-mechanics.md` exists and the roadmap no longer proposes the refuted heuristic.

- [ ] **Step 5: Commit**

```bash
git add docs/cadence-mechanics.md docs/roadmap.md
git commit -m "docs(coach): add cadence-mechanics, correct loadout-timing roadmap entry"
```

---

### Task 10: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the entire test suite**

Run: `uv run pytest`
Expected: PASS — all tests, including every pre-existing DPS/ranking test unchanged.

- [ ] **Step 2: Lint**

Run: `uv run ruff check .`
Expected: PASS (green).

- [ ] **Step 3: End-to-end smoke against the real dataset**

Rebuild so `burst_reload` populates, then confirm cadence surfaces live and the invariant holds on a real weapon:

Run:
```bash
uv run python build_dataset.py
uv run python -c "import json, brotato_coach.answers as a; ds=json.load(open('data/brotato.json')); r=a.weapon_dps(ds,'Minigun',4,{'ranged_damage':20},weapon_count=6); c=r['cadence']; print(c['cadence'], round(c['attacks_per_second'],2), 'gap', [round(x,3) for x in c['gap_range_s']]); assert abs(c['damage_per_attack']*c['attacks_per_second']-r['dps'])<1e-6; rev=a.weapon_dps(ds,'Revolver',4,{'ranged_damage':0}); print('revolver burst_reload:', rev['cadence']['burst_reload'])"
```
Expected: prints a `sustained` label for Minigun with a non-trivial gap range, the invariant assertion passes, and `revolver burst_reload: True`.

- [ ] **Step 4: Final commit (if the smoke revealed nothing to change)**

No code change expected; if Step 3 surfaced a fix, commit it with a descriptive message.

---

## Self-Review

**Spec coverage:**
- Metrics table (attacks_per_second, seconds_between_attacks, damage_per_attack, cadence label, gap_range_s) → Task 2. ✓
- New calc primitives (`cooldown_jitter`, `cadence_profile`) → Tasks 1-2. ✓
- `weapon_dps` / `compare_weapons` cadence + `weapon_count` → Tasks 3-4. ✓
- `evaluate_run` at real weapon count → Task 5. ✓
- Server `weapon_count` param + docstrings → Task 7. ✓
- Graceful degradation when `cycle_time` absent → Tasks 3-4 (tested explicitly). ✓
- `burst_reload` additive builder field + bimodal caveat → Task 6; surfaced in cadence output via Task 2/3, primer Task 8, doc Task 9. ✓
- `read_me` primer rewrite → Task 8. ✓
- `docs/cadence-mechanics.md` + roadmap correction → Task 9. ✓
- No DPS/ranking change, no schema bump → enforced by Global Constraints + no-regression full-suite run in Task 10. ✓
- Consistency invariant `damage_per_attack × attacks_per_second == dps` → Tasks 2, 3, 10. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every command has expected output. The only conditional is Task 8 Step 1 ("mirror the current calling convention") — bounded because the implementer reads the existing `tests/test_orientation.py` in the same task. ✓

**Type consistency:** `cooldown_jitter -> tuple[float, float]` consumed by `cadence_profile` (Task 2) as `lo_f, hi_f`. ✓ `cadence_profile(...)-> dict` keys (`attacks_per_second`, `damage_per_attack`, `gap_range_s`, `cadence`, `burst_reload`) referenced identically in Tasks 3, 4, 5, 7, 8. ✓ `weapon_count: int` default 1 consistent across `weapon_dps`, `compare_weapons`, and both server tools. ✓ `burst_reload` bool produced in Task 6, consumed via `rec.get("burst_reload", False)` in Task 3. ✓
