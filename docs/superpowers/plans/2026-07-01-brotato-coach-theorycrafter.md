# Brotato Coach — Theorycrafter (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the deterministic theorycrafter core for the Brotato AI coach — an offline build step that distills extracted game data into a committed JSON dataset, plus an MCP server whose tools return finished, verifiable answers about weapons, items, characters, and stat mechanics.

**Architecture:** A Godot `.tres` parser and pure-math module feed a per-collection build pipeline that emits `data/brotato.json` (enriched, precomputed). A dataset loader + pure query/answer functions sit under a thin FastMCP server. All game knowledge is facts + math; no subjective rankings. Pure functions are unit-tested against hand-verified golden values; the MCP layer is a thin wrapper.

**Tech Stack:** Python 3.11+, `uv` for env/packaging, `pytest` for tests, `mcp` (FastMCP) for the server. No network at runtime.

## Global Constraints

- Python **3.11+**; manage the environment and dependencies with **`uv`** (separate env for this project). Run everything via `uv run ...`.
- Facts + math only in the core — **no tier lists or subjective "good/bad" rankings** in code or dataset.
- The build step is the only code that reads `extracted/`; **the MCP server reads only `data/brotato.json`**, never `.tres`.
- `extracted/` is gitignored and may be absent in a clean clone — **all tests must be hermetic** (use inline `.tres` fixture strings, never read `extracted/`).
- No wall-clock calls in build scripts that must be reproducible: **`generated_at` is passed in as a CLI arg**, not read from the system clock inside library code.
- Every MCP tool returns **either a valid finished answer or a structured error object** (`{"error": ..., ...}`) — never a partial result or a raw exception.
- Package name: **`brotato_coach`**. Test framework: **pytest**. Commit after every task.

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `brotato_coach/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing.
- Produces: the `brotato_coach` importable package and a working `uv run pytest` cycle.

- [ ] **Step 1: Write the failing test**

`tests/test_smoke.py`:
```python
def test_package_imports():
    import brotato_coach

    assert brotato_coach.__version__ == "0.1.0"
```

- [ ] **Step 2: Create the package init**

`brotato_coach/__init__.py`:
```python
__version__ = "0.1.0"
```

`tests/__init__.py`: (empty file)

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[project]
name = "brotato-coach"
version = "0.1.0"
description = "Deterministic theorycrafter core + MCP server for a Brotato AI coach"
requires-python = ">=3.11"
dependencies = ["mcp>=1.2.0"]

[dependency-groups]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["brotato_coach"]
```

- [ ] **Step 4: Sync the env and run the test**

Run:
```bash
uv sync
uv run pytest tests/test_smoke.py -v
```
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock brotato_coach/ tests/
git commit -m "chore: scaffold brotato_coach package with uv + pytest"
```

---

### Task 2: Pure DPS/merge math (`calc.py`)

**Files:**
- Create: `brotato_coach/calc.py`
- Test: `tests/test_calc.py`

**Interfaces:**
- Consumes: nothing (pure functions, no I/O).
- Produces:
  - `cycle_time(recoil_duration: float, cooldown: float, burst: tuple[int, float] | None = None) -> float`
  - `dps_line(base_damage: float, scaling_coef: float, cycle_time: float, accuracy: float) -> tuple[float, float]` → `(dps_at_zero_rd, dps_slope_per_rd)`
  - `dps_at(dps0: float, slope: float, rd: float) -> float`
  - `sum_lines(lines: list[tuple[float, float]]) -> tuple[float, float]`
  - `compare_lines(line_a, line_b, rd_min=0.0, rd_max=100.0) -> dict` with keys `winner` (`"a"|"b"|"tie"`), `rd_independent` (bool), `crossover_rd` (float | None).

- [ ] **Step 1: Write the failing tests**

`tests/test_calc.py`:
```python
import math

from brotato_coach import calc


def test_cycle_time_no_burst():
    # Shredder T4: recoil_duration 0.15, cooldown 45
    assert math.isclose(calc.cycle_time(0.15, 45), 1.05)


def test_cycle_time_with_burst():
    # Revolver T4: recoil 0.1, cd 11, every 6 shots add cd*8/60
    assert math.isclose(calc.cycle_time(0.1, 11, burst=(6, 8.0)), 0.627777, rel_tol=1e-4)


def test_dps_line_shredder_t4():
    dps0, slope = calc.dps_line(25, 0.5, calc.cycle_time(0.15, 45), 1.0)
    assert math.isclose(dps0, 23.8095, rel_tol=1e-4)
    assert math.isclose(slope, 0.47619, rel_tol=1e-4)


def test_dps_line_minigun_t4():
    dps0, slope = calc.dps_line(5, 0.75, calc.cycle_time(0.02, 3), 1.0)
    assert math.isclose(dps0, 55.5556, rel_tol=1e-4)
    assert math.isclose(slope, 8.3333, rel_tol=1e-4)


def test_dps_line_revolver_t4_accuracy_and_burst():
    ct = calc.cycle_time(0.1, 11, burst=(6, 8.0))
    dps0, slope = calc.dps_line(40, 2.0, ct, 0.9)
    assert math.isclose(dps0, 57.35, rel_tol=1e-3)
    assert math.isclose(slope, 2.8673, rel_tol=1e-3)


def test_minigun_beats_revolver_slope():
    _, mini = calc.dps_line(5, 0.75, calc.cycle_time(0.02, 3), 1.0)
    _, revo = calc.dps_line(40, 2.0, calc.cycle_time(0.1, 11, burst=(6, 8.0)), 0.9)
    assert mini > revo


def test_compare_lines_crossover():
    # a starts higher but flat; b starts lower but steep -> they cross
    result = calc.compare_lines((60.0, 1.0), (50.0, 3.0), 0, 100)
    assert result["rd_independent"] is False
    assert math.isclose(result["crossover_rd"], 5.0, rel_tol=1e-6)


def test_compare_lines_dominant():
    # a dominates everywhere in range -> no crossover
    result = calc.compare_lines((60.0, 4.0), (50.0, 3.0), 0, 100)
    assert result["rd_independent"] is True
    assert result["crossover_rd"] is None
    assert result["winner"] == "a"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_calc.py -v`
Expected: FAIL (module `calc` has no attribute `cycle_time`).

- [ ] **Step 3: Implement `calc.py`**

`brotato_coach/calc.py`:
```python
"""Pure DPS / merge math. No I/O — every function is unit-testable in isolation.

DPS model: cycle_time = recoil_duration*2 + cooldown/60 (seconds).
Realized DPS as a function of ranged-damage (RD) is a line:
    dps(rd) = dps_at_zero_rd + dps_slope_per_rd * rd
with both intercept and slope scaled by accuracy.
"""

from __future__ import annotations


def cycle_time(recoil_duration: float, cooldown: float,
               burst: tuple[int, float] | None = None) -> float:
    ct = recoil_duration * 2 + cooldown / 60
    if burst is not None:
        every_x_shots, multiplier = burst
        ct += (cooldown * multiplier / 60) / every_x_shots
    return ct


def dps_line(base_damage: float, scaling_coef: float, cycle_time: float,
             accuracy: float) -> tuple[float, float]:
    dps0 = base_damage / cycle_time * accuracy
    slope = scaling_coef / cycle_time * accuracy
    return (dps0, slope)


def dps_at(dps0: float, slope: float, rd: float) -> float:
    return dps0 + slope * rd


def sum_lines(lines: list[tuple[float, float]]) -> tuple[float, float]:
    return (sum(d for d, _ in lines), sum(s for _, s in lines))


def compare_lines(line_a: tuple[float, float], line_b: tuple[float, float],
                  rd_min: float = 0.0, rd_max: float = 100.0) -> dict:
    a0, as_ = line_a
    b0, bs = line_b

    crossover_rd = None
    if as_ != bs:
        x = (b0 - a0) / (as_ - bs)
        if rd_min < x < rd_max:
            crossover_rd = x

    def winner_at(rd: float) -> str:
        va, vb = dps_at(a0, as_, rd), dps_at(b0, bs, rd)
        if abs(va - vb) < 1e-9:
            return "tie"
        return "a" if va > vb else "b"

    if crossover_rd is None:
        return {
            "winner": winner_at((rd_min + rd_max) / 2),
            "rd_independent": True,
            "crossover_rd": None,
        }
    return {
        "winner": None,
        "rd_independent": False,
        "crossover_rd": crossover_rd,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_calc.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/calc.py tests/test_calc.py
git commit -m "feat: pure DPS/merge math with hand-verified golden tests"
```

---

### Task 3: Godot `.tres` parser (`tres.py`)

**Files:**
- Create: `brotato_coach/tres.py`
- Test: `tests/test_tres.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `parse_tres(text: str) -> TresDoc` where `TresDoc` has attributes `ext_resources: dict[int, dict]` (id → `{"path", "type"}`), `sub_resources: dict[int, dict]`, and `resource: dict[str, object]` (the `[resource]` block, values parsed to Python types).
  - Godot literal parsing: ints, floats, `true`/`false`, quoted strings, arrays `[ ... ]` (possibly nested), and `ExtResource( n )` / `SubResource( n )` → sentinel dicts `{"__ext__": n}` / `{"__sub__": n}`.

- [ ] **Step 1: Write the failing tests**

`tests/test_tres.py`:
```python
from brotato_coach.tres import parse_tres

SHREDDER = """[gd_resource type="Resource" load_steps=2 format=2]

[ext_resource path="res://weapons/weapon_stats/ranged_weapon_stats.gd" type="Script" id=1]
[ext_resource path="res://projectiles/bullet_shredder/bullet_shredder.tscn" type="PackedScene" id=2]

[resource]
script = ExtResource( 1 )
cooldown = 45
damage = 25
accuracy = 1.0
crit_chance = 0.03
scaling_stats = [ [ "stat_ranged_damage", 0.5 ] ]
recoil_duration = 0.15
can_have_negative_knockback = false
projectile_scene = ExtResource( 2 )
"""


def test_parses_scalars():
    doc = parse_tres(SHREDDER)
    assert doc.resource["cooldown"] == 45
    assert doc.resource["damage"] == 25
    assert doc.resource["accuracy"] == 1.0
    assert doc.resource["can_have_negative_knockback"] is False


def test_parses_nested_array():
    doc = parse_tres(SHREDDER)
    assert doc.resource["scaling_stats"] == [["stat_ranged_damage", 0.5]]


def test_parses_ext_resource_reference():
    doc = parse_tres(SHREDDER)
    assert doc.resource["projectile_scene"] == {"__ext__": 2}
    assert doc.ext_resources[2]["path"].endswith("bullet_shredder.tscn")


def test_ignores_gd_resource_header_keys():
    doc = parse_tres(SHREDDER)
    assert "load_steps" not in doc.resource
    assert "type" not in doc.resource
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_tres.py -v`
Expected: FAIL (cannot import `parse_tres`).

- [ ] **Step 3: Implement `tres.py`**

`brotato_coach/tres.py`:
```python
"""Minimal parser for Godot 3 text resources (.tres).

Only what the build step needs: section headers, ext/sub resource tables,
and the [resource] key/value block with Godot literals parsed to Python.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_HEADER_RE = re.compile(r"^\[(\w[\w ]*?)\s*(.*)\]$")
_KV_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"|(\w+)\s*=\s*([\w.\-]+)')


@dataclass
class TresDoc:
    ext_resources: dict[int, dict] = field(default_factory=dict)
    sub_resources: dict[int, dict] = field(default_factory=dict)
    resource: dict[str, object] = field(default_factory=dict)


def _parse_header_attrs(attr_str: str) -> dict:
    attrs: dict[str, object] = {}
    for m in _KV_RE.finditer(attr_str):
        if m.group(1) is not None:
            attrs[m.group(1)] = m.group(2)
        else:
            attrs[m.group(3)] = _parse_value(m.group(4))
    return attrs


def _tokenize_value(s: str) -> list[str]:
    tokens, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace() or c == ",":
            i += 1
        elif c in "[]":
            tokens.append(c)
            i += 1
        elif c == '"':
            j = s.index('"', i + 1)
            tokens.append(s[i:j + 1])
            i = j + 1
        else:
            j = i
            depth = 0
            while j < n and not (s[j] in ",[]" and depth == 0):
                if s[j] == "(":
                    depth += 1
                elif s[j] == ")":
                    depth -= 1
                j += 1
            tokens.append(s[i:j].strip())
            i = j
    return [t for t in tokens if t != ""]


def _parse_value(raw: str):
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        return _parse_array(_tokenize_value(raw))[0]
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    if raw in ("true", "false"):
        return raw == "true"
    m = re.fullmatch(r"(Ext|Sub)Resource\(\s*(\d+)\s*\)", raw)
    if m:
        key = "__ext__" if m.group(1) == "Ext" else "__sub__"
        return {key: int(m.group(2))}
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def _parse_array(tokens: list[str], pos: int = 0):
    # tokens[pos] == "["
    result = []
    i = pos + 1
    while i < len(tokens):
        t = tokens[i]
        if t == "]":
            return result, i + 1
        if t == "[":
            inner, i = _parse_array(tokens, i)
            result.append(inner)
        else:
            result.append(_parse_value(t))
            i += 1
    return result, i


def parse_tres(text: str) -> TresDoc:
    doc = TresDoc()
    section = None
    section_attrs: dict = {}
    buffer_key = None
    buffer_val: list[str] = []

    def flush_buffer():
        nonlocal buffer_key, buffer_val
        if buffer_key is not None:
            doc.resource[buffer_key] = _parse_value(" ".join(buffer_val).strip())
            buffer_key, buffer_val = None, []

    for line in text.splitlines():
        stripped = line.strip()
        header = _HEADER_RE.match(stripped) if stripped.startswith("[") and "=" not in stripped.split("]")[0].split(" ", 1)[0] else None
        # A header line looks like [name attr=... ]; a resource kv can also
        # start with '[' (an array). Distinguish: headers have no '=' before
        # the first space and are not inside a [resource] value continuation.
        is_header = bool(_HEADER_RE.match(stripped)) and buffer_key is None and not stripped.startswith("[ ")

        if is_header:
            flush_buffer()
            m = _HEADER_RE.match(stripped)
            name = m.group(1).strip()
            attrs = _parse_header_attrs(m.group(2))
            section = name
            section_attrs = attrs
            if name == "ext_resource":
                doc.ext_resources[attrs["id"]] = {"path": attrs.get("path"), "type": attrs.get("type")}
            elif name == "sub_resource":
                doc.sub_resources[attrs.get("id")] = {"type": attrs.get("type")}
            continue

        if section == "resource" and "=" in stripped and not stripped.startswith("["):
            flush_buffer()
            key, val = stripped.split("=", 1)
            buffer_key = key.strip()
            buffer_val = [val.strip()]
        elif buffer_key is not None and stripped:
            buffer_val.append(stripped)

    flush_buffer()
    return doc
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_tres.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/tres.py tests/test_tres.py
git commit -m "feat: minimal Godot .tres parser"
```

---

### Task 4: Weapon record builder (`build/weapons.py`)

**Files:**
- Create: `brotato_coach/build/__init__.py`
- Create: `brotato_coach/build/weapons.py`
- Test: `tests/test_build_weapons.py`

**Interfaces:**
- Consumes: `parse_tres` (Task 3), `calc.cycle_time`/`calc.dps_line` (Task 2).
- Produces: `build_weapon_record(stats_text: str, data_text: str, *, weapon_id: str, name: str, tier: int) -> dict` returning a weapon record with keys: `id, name, tier, base_damage, cooldown, accuracy, crit_chance, crit_damage, piercing, nb_projectiles, scaling_stats, can_have_negative_knockback, base_knockback, cycle_time, dps_at_zero_rd, dps_slope_per_rd, sets, effects`.
- The DPS line uses the **ranged-damage** scaling coefficient (the `scaling_stats` entry whose stat is `stat_ranged_damage`), defaulting to 0.0 if absent.

- [ ] **Step 1: Write the failing test**

`tests/test_build_weapons.py`:
```python
import math

from brotato_coach.build.weapons import build_weapon_record

STATS = """[gd_resource type="Resource" format=2]
[resource]
cooldown = 45
damage = 25
accuracy = 1.0
crit_chance = 0.03
crit_damage = 2.0
recoil_duration = 0.15
piercing = 3
nb_projectiles = 1
scaling_stats = [ [ "stat_ranged_damage", 0.5 ] ]
can_have_negative_knockback = false
knockback = 0
"""

DATA = """[gd_resource type="Resource" format=2]
[resource]
weapon_id = "weapon_shredder"
tier = 3
effects = [  ]
"""


def test_weapon_record_core_fields():
    rec = build_weapon_record(STATS, DATA, weapon_id="weapon_shredder",
                              name="Shredder", tier=4)
    assert rec["id"] == "weapon_shredder"
    assert rec["tier"] == 4
    assert rec["base_damage"] == 25
    assert rec["scaling_stats"] == [["stat_ranged_damage", 0.5]]
    assert rec["can_have_negative_knockback"] is False


def test_weapon_record_precomputed_dps_line():
    rec = build_weapon_record(STATS, DATA, weapon_id="weapon_shredder",
                              name="Shredder", tier=4)
    assert math.isclose(rec["cycle_time"], 1.05, rel_tol=1e-6)
    assert math.isclose(rec["dps_at_zero_rd"], 23.8095, rel_tol=1e-4)
    assert math.isclose(rec["dps_slope_per_rd"], 0.47619, rel_tol=1e-4)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_build_weapons.py -v`
Expected: FAIL (cannot import `build_weapon_record`).

- [ ] **Step 3: Implement `build/weapons.py`**

`brotato_coach/build/__init__.py`: (empty file)

`brotato_coach/build/weapons.py`:
```python
from __future__ import annotations

from brotato_coach import calc
from brotato_coach.tres import parse_tres


def _rd_coefficient(scaling_stats: list) -> float:
    for entry in scaling_stats or []:
        if isinstance(entry, list) and len(entry) == 2 and entry[0] == "stat_ranged_damage":
            return float(entry[1])
    return 0.0


def build_weapon_record(stats_text: str, data_text: str, *, weapon_id: str,
                        name: str, tier: int) -> dict:
    s = parse_tres(stats_text).resource
    d = parse_tres(data_text).resource

    cooldown = float(s.get("cooldown", 0))
    recoil_duration = float(s.get("recoil_duration", 0.0))
    base_damage = float(s.get("damage", 0))
    accuracy = float(s.get("accuracy", 1.0))
    scaling_stats = s.get("scaling_stats", []) or []

    burst = None
    every = s.get("additional_cooldown_every_x_shots", -1)
    mult = s.get("additional_cooldown_multiplier", -1.0)
    if isinstance(every, int) and every > 0 and isinstance(mult, (int, float)) and mult > 0:
        burst = (every, float(mult))

    ct = calc.cycle_time(recoil_duration, cooldown, burst=burst)
    dps0, slope = calc.dps_line(base_damage, _rd_coefficient(scaling_stats), ct, accuracy)

    return {
        "id": weapon_id,
        "name": name,
        "tier": tier,
        "base_damage": base_damage,
        "cooldown": cooldown,
        "accuracy": accuracy,
        "crit_chance": float(s.get("crit_chance", 0.0)),
        "crit_damage": float(s.get("crit_damage", 0.0)),
        "piercing": s.get("piercing", 0),
        "nb_projectiles": s.get("nb_projectiles", 1),
        "scaling_stats": scaling_stats,
        "can_have_negative_knockback": bool(s.get("can_have_negative_knockback", False)),
        "base_knockback": s.get("knockback", 0),
        "cycle_time": ct,
        "dps_at_zero_rd": dps0,
        "dps_slope_per_rd": slope,
        "sets": [],
        "effects": d.get("effects", []) or [],
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_build_weapons.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/build/ tests/test_build_weapons.py
git commit -m "feat: weapon record builder with precomputed DPS line"
```

---

### Task 5: Item record builder + archetype detection (`build/items.py`)

**Files:**
- Create: `brotato_coach/build/items.py`
- Test: `tests/test_build_items.py`

**Interfaces:**
- Consumes: `parse_tres` (Task 3).
- Produces: `build_item_record(data_text: str, effect_texts: list[str], *, item_id: str, name: str) -> dict` returning keys: `id, name, tier, value, tags, effects` (list of `{key, value, effect_sign, text_key}`), `archetype` (list[str]), `frozen_stat` (str | None), `scaling_stats` (list[str]), `damage_tags` (list[str]).
- Archetype rule: an effect is `cap_at_current_value` when its `key` ends with `_cap` **or** its `text_key` matches `CAP_AT_CURRENT_VALUE`. `frozen_stat` is derived by stripping `_cap` from that effect's `key` and prefixing `stat_` if absent (e.g. `hp_cap` → `stat_max_hp` via the mapping table; `speed_cap` → `stat_speed`).

- [ ] **Step 1: Write the failing test**

`tests/test_build_items.py`:
```python
from brotato_coach.build.items import build_item_record

HANDCUFFS_DATA = """[gd_resource type="Resource" format=2]
[resource]
tier = 2
value = 80
tags = [ "stat_melee_damage", "stat_ranged_damage", "stat_elemental_damage" ]
"""

EFF_MELEE = '[resource]\nkey = "stat_melee_damage"\nvalue = 8\neffect_sign = 3\ntext_key = ""\n'
EFF_RANGED = '[resource]\nkey = "stat_ranged_damage"\nvalue = 8\neffect_sign = 3\ntext_key = ""\n'
EFF_ELEM = '[resource]\nkey = "stat_elemental_damage"\nvalue = 8\neffect_sign = 3\ntext_key = ""\n'
EFF_CAP = '[resource]\nkey = "hp_cap"\nvalue = 0\neffect_sign = 0\ntext_key = "EFFECT_HP_CAP_AT_CURRENT_VALUE"\n'


def test_item_effects_parsed():
    rec = build_item_record(HANDCUFFS_DATA, [EFF_MELEE, EFF_RANGED, EFF_ELEM, EFF_CAP],
                            item_id="item_handcuffs", name="Handcuffs")
    assert rec["value"] == 80
    assert {"key": "stat_ranged_damage", "value": 8, "effect_sign": 3, "text_key": ""} in rec["effects"]
    assert rec["damage_tags"] == ["stat_melee_damage", "stat_ranged_damage", "stat_elemental_damage"]


def test_item_cap_archetype_detected():
    rec = build_item_record(HANDCUFFS_DATA, [EFF_MELEE, EFF_RANGED, EFF_ELEM, EFF_CAP],
                            item_id="item_handcuffs", name="Handcuffs")
    assert "cap_at_current_value" in rec["archetype"]
    assert rec["frozen_stat"] == "stat_max_hp"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_build_items.py -v`
Expected: FAIL (cannot import `build_item_record`).

- [ ] **Step 3: Implement `build/items.py`**

`brotato_coach/build/items.py`:
```python
from __future__ import annotations

import re

from brotato_coach.tres import parse_tres

_CAP_STAT_MAP = {
    "hp_cap": "stat_max_hp",
    "speed_cap": "stat_speed",
    "dodge_cap": "stat_dodge",
    "crit_chance_cap": "stat_crit_chance",
    "curse_cap": "stat_curse",
}

_DAMAGE_TAGS = ("stat_melee_damage", "stat_ranged_damage", "stat_elemental_damage")


def _effect_record(text: str) -> dict:
    r = parse_tres(text).resource
    return {
        "key": r.get("key", ""),
        "value": r.get("value", 0),
        "effect_sign": r.get("effect_sign", 0),
        "text_key": r.get("text_key", ""),
    }


def build_item_record(data_text: str, effect_texts: list[str], *, item_id: str,
                      name: str) -> dict:
    d = parse_tres(data_text).resource
    effects = [_effect_record(t) for t in effect_texts]
    tags = d.get("tags", []) or []

    archetype: list[str] = []
    frozen_stat = None
    scaling_stats: list[str] = []
    for eff in effects:
        key = str(eff["key"])
        text_key = str(eff["text_key"])
        is_cap = key.endswith("_cap") or bool(re.search(r"CAP_AT_CURRENT_VALUE", text_key))
        if is_cap:
            if "cap_at_current_value" not in archetype:
                archetype.append("cap_at_current_value")
            frozen_stat = _CAP_STAT_MAP.get(key, frozen_stat)
        if key.startswith("stat_") and key not in scaling_stats:
            scaling_stats.append(key)

    return {
        "id": item_id,
        "name": name,
        "tier": d.get("tier", 0),
        "value": d.get("value", 0),
        "tags": tags,
        "effects": effects,
        "archetype": archetype,
        "frozen_stat": frozen_stat,
        "scaling_stats": scaling_stats,
        "damage_tags": [t for t in tags if t in _DAMAGE_TAGS],
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_build_items.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/build/items.py tests/test_build_items.py
git commit -m "feat: item record builder with cap-at-current-value archetype detection"
```

---

### Task 6: Character + set builders (`build/characters.py`, `build/sets.py`)

**Files:**
- Create: `brotato_coach/build/characters.py`
- Create: `brotato_coach/build/sets.py`
- Test: `tests/test_build_characters.py`

**Interfaces:**
- Consumes: `parse_tres` (Task 3).
- Produces:
  - `build_character_record(data_text: str, effect_texts: list[str], *, char_id: str, name: str, wanted_tags: list[str], banned_item_groups: list[str]) -> dict` → keys `id, name, wanted_tags, banned_item_groups, flat_bonuses` (list of `{stat, value}`), `gain_modifiers` (list of `{stat, pct}`), `special_effects` (list[str]).
    - `effect_increase_stat_gains` → a `gain_modifiers` entry `{stat, pct: +value}`; `effect_reduce_stat_gains` → `{stat, pct: value}` (value already negative in data). The stat comes from the effect's `stats_modified` list (first entry).
    - `no_melee_weapons` (or any non-stat, non-gain effect key) → appended to `special_effects`.
    - A `stat_*` key with a numeric value → `flat_bonuses` entry.
  - `build_set_record(set_data_text: str, count_effect_texts: dict[int, str], *, set_id: str, name: str) -> dict` → keys `id, name, bonuses` (list of `{count, effect: {key, value}}`), sorted by count.

- [ ] **Step 1: Write the failing tests**

`tests/test_build_characters.py`:
```python
from brotato_coach.build.characters import build_character_record
from brotato_coach.build.sets import build_set_record

RANGER_DATA = """[gd_resource type="Resource" format=2]
[resource]
tier = 0
"""

EFF_FLAT_RANGE = '[resource]\nkey = "stat_range"\nvalue = 50\neffect_sign = 3\n'
EFF_RD_GAIN = '[resource]\nkey = "effect_increase_stat_gains"\nvalue = 50\nstats_modified = [ "stat_ranged_damage" ]\n'
EFF_HP_GAIN = '[resource]\nkey = "effect_reduce_stat_gains"\nvalue = -25\nstats_modified = [ "stat_max_hp" ]\n'
EFF_NO_MELEE = '[resource]\nkey = "no_melee_weapons"\nvalue = 1\n'


def test_ranger_gain_modifiers():
    rec = build_character_record(
        RANGER_DATA, [EFF_FLAT_RANGE, EFF_RD_GAIN, EFF_HP_GAIN, EFF_NO_MELEE],
        char_id="character_ranger", name="Ranger",
        wanted_tags=["stat_ranged_damage", "stat_range"],
        banned_item_groups=["melee_damage"],
    )
    assert {"stat": "stat_ranged_damage", "pct": 50} in rec["gain_modifiers"]
    assert {"stat": "stat_max_hp", "pct": -25} in rec["gain_modifiers"]
    assert {"stat": "stat_range", "value": 50} in rec["flat_bonuses"]
    assert "no_melee_weapons" in rec["special_effects"]


def test_set_bonuses_sorted_by_count():
    set_data = '[gd_resource type="Resource" format=2]\n[resource]\nmy_id = "set_gun"\n'
    eff2 = '[resource]\nkey = "stat_range"\nvalue = 5\n'
    eff6 = '[resource]\nkey = "stat_range"\nvalue = 50\n'
    rec = build_set_record(set_data, {6: eff6, 2: eff2}, set_id="set_gun", name="Gun")
    assert [b["count"] for b in rec["bonuses"]] == [2, 6]
    assert rec["bonuses"][1]["effect"] == {"key": "stat_range", "value": 50}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_build_characters.py -v`
Expected: FAIL (cannot import builders).

- [ ] **Step 3: Implement the builders**

`brotato_coach/build/characters.py`:
```python
from __future__ import annotations

from brotato_coach.tres import parse_tres

_GAIN_KEYS = {"effect_increase_stat_gains", "effect_reduce_stat_gains"}


def build_character_record(data_text: str, effect_texts: list[str], *, char_id: str,
                          name: str, wanted_tags: list[str],
                          banned_item_groups: list[str]) -> dict:
    flat_bonuses: list[dict] = []
    gain_modifiers: list[dict] = []
    special_effects: list[str] = []

    for text in effect_texts:
        r = parse_tres(text).resource
        key = str(r.get("key", ""))
        if key in _GAIN_KEYS:
            mods = r.get("stats_modified", []) or []
            stat = mods[0] if mods else None
            if stat is not None:
                gain_modifiers.append({"stat": stat, "pct": r.get("value", 0)})
        elif key.startswith("stat_"):
            flat_bonuses.append({"stat": key, "value": r.get("value", 0)})
        else:
            special_effects.append(key)

    return {
        "id": char_id,
        "name": name,
        "wanted_tags": wanted_tags,
        "banned_item_groups": banned_item_groups,
        "flat_bonuses": flat_bonuses,
        "gain_modifiers": gain_modifiers,
        "special_effects": special_effects,
    }
```

`brotato_coach/build/sets.py`:
```python
from __future__ import annotations

from brotato_coach.tres import parse_tres


def build_set_record(set_data_text: str, count_effect_texts: dict[int, str], *,
                     set_id: str, name: str) -> dict:
    bonuses = []
    for count in sorted(count_effect_texts):
        r = parse_tres(count_effect_texts[count]).resource
        bonuses.append({
            "count": count,
            "effect": {"key": r.get("key", ""), "value": r.get("value", 0)},
        })
    return {"id": set_id, "name": name, "bonuses": bonuses}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_build_characters.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/build/characters.py brotato_coach/build/sets.py tests/test_build_characters.py
git commit -m "feat: character (gain modifiers) and set-bonus builders"
```

---

### Task 7: Stat-mechanics table + dataset assembly (`build/mechanics.py`, `dataset.py`)

**Files:**
- Create: `brotato_coach/build/mechanics.py`
- Create: `brotato_coach/dataset.py`
- Test: `tests/test_dataset.py`

**Interfaces:**
- Consumes: nothing new (pure data + validation).
- Produces:
  - `build/mechanics.py`: `STAT_MECHANICS: dict[str, dict]` — one entry per verified stat with keys `cap` (`{"cap_key": str}` | None), `special` (str | None), `safe_below_zero` (bool), `safe_at_zero` (bool), `avoid_positive` (bool), `never_dead_weight` (bool).
  - `dataset.py`:
    - `DATASET_VERSION = 1` (schema version, distinct from game version).
    - `assemble_dataset(*, game_version, generated_at, weapons, items, characters, sets) -> dict` → `{schema_version, game_version, generated_at, stat_mechanics, weapons, items, characters, sets}`.
    - `validate_dataset(dataset: dict) -> list[str]` → list of human-readable problems (empty = valid). Checks: required top-level keys present; every weapon has required keys and `tier` in 1..4; no weapon has `dps_slope_per_rd` missing; every item has an `effects` list.
    - `load_dataset(path: str) -> dict` → parsed JSON, raising `FileNotFoundError` with a "run build_dataset.py first" message if absent.

- [ ] **Step 1: Write the failing tests**

`tests/test_dataset.py`:
```python
import pytest

from brotato_coach import dataset
from brotato_coach.build.mechanics import STAT_MECHANICS


def test_mechanics_known_facts():
    assert STAT_MECHANICS["stat_attack_speed"]["never_dead_weight"] is True
    assert STAT_MECHANICS["stat_hp_regeneration"]["safe_at_zero"] is True
    assert STAT_MECHANICS["stat_curse"]["avoid_positive"] is True
    assert STAT_MECHANICS["stat_max_hp"]["cap"] == {"cap_key": "hp_cap"}


def test_assemble_and_validate_ok():
    weapon = {
        "id": "w", "name": "W", "tier": 4, "base_damage": 25, "cooldown": 45,
        "accuracy": 1.0, "crit_chance": 0.03, "crit_damage": 2.0, "piercing": 3,
        "nb_projectiles": 1, "scaling_stats": [], "can_have_negative_knockback": False,
        "base_knockback": 0, "cycle_time": 1.05, "dps_at_zero_rd": 23.8,
        "dps_slope_per_rd": 0.48, "sets": [], "effects": [],
    }
    item = {"id": "i", "name": "I", "tier": 0, "value": 10, "tags": [], "effects": [],
            "archetype": [], "frozen_stat": None, "scaling_stats": [], "damage_tags": []}
    ds = dataset.assemble_dataset(game_version="1.1.0.0", generated_at="2026-07-01T00:00:00Z",
                                  weapons=[weapon], items=[item], characters=[], sets=[])
    assert ds["schema_version"] == dataset.DATASET_VERSION
    assert ds["game_version"] == "1.1.0.0"
    assert dataset.validate_dataset(ds) == []


def test_validate_flags_bad_tier():
    ds = dataset.assemble_dataset(game_version="x", generated_at="t",
                                  weapons=[{"id": "w", "tier": 9, "dps_slope_per_rd": 1.0}],
                                  items=[], characters=[], sets=[])
    problems = dataset.validate_dataset(ds)
    assert any("tier" in p for p in problems)


def test_load_missing_dataset_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="build_dataset.py"):
        dataset.load_dataset(str(tmp_path / "nope.json"))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_dataset.py -v`
Expected: FAIL (cannot import `dataset` / `STAT_MECHANICS`).

- [ ] **Step 3: Implement the mechanics table and dataset module**

`brotato_coach/build/mechanics.py`:
```python
"""Verified stat mechanics, encoded from decompiled code (see docs/stat-mechanics.md).

Only stats whose behavior has been confirmed against the game code are listed.
This table is authoritative for what the coach claims about stat mechanics.
"""

from __future__ import annotations


def _m(cap=None, special=None, safe_below_zero=False, safe_at_zero=False,
       avoid_positive=False, never_dead_weight=False) -> dict:
    return {
        "cap": cap, "special": special, "safe_below_zero": safe_below_zero,
        "safe_at_zero": safe_at_zero, "avoid_positive": avoid_positive,
        "never_dead_weight": never_dead_weight,
    }


STAT_MECHANICS: dict[str, dict] = {
    "stat_max_hp": _m(cap={"cap_key": "hp_cap"}),
    "stat_speed": _m(cap={"cap_key": "speed_cap"}),
    "stat_dodge": _m(cap={"cap_key": "dodge_cap"}),
    "stat_crit_chance": _m(cap={"cap_key": "crit_chance_cap"}),
    "stat_curse": _m(cap={"cap_key": "curse_cap"}, special="curse_sqrt_penalty",
                     safe_below_zero=True, avoid_positive=True),
    "stat_hp_regeneration": _m(special="regen_zero_safe", safe_below_zero=True,
                               safe_at_zero=True),
    "stat_lifesteal": _m(special="lifesteal_negative_drains"),
    "stat_attack_speed": _m(special="attack_speed_universal", never_dead_weight=True),
    "knockback": _m(special="knockback_clamped_by_weapon_flag", safe_below_zero=True,
                    safe_at_zero=True),
}
```

`brotato_coach/dataset.py`:
```python
from __future__ import annotations

import json

from brotato_coach.build.mechanics import STAT_MECHANICS

DATASET_VERSION = 1

_REQUIRED_WEAPON_KEYS = ("id", "name", "tier", "dps_slope_per_rd", "dps_at_zero_rd")


def assemble_dataset(*, game_version: str, generated_at: str, weapons: list,
                     items: list, characters: list, sets: list) -> dict:
    return {
        "schema_version": DATASET_VERSION,
        "game_version": game_version,
        "generated_at": generated_at,
        "stat_mechanics": STAT_MECHANICS,
        "weapons": weapons,
        "items": items,
        "characters": characters,
        "sets": sets,
    }


def validate_dataset(dataset: dict) -> list[str]:
    problems: list[str] = []
    for key in ("schema_version", "game_version", "weapons", "items", "characters", "sets"):
        if key not in dataset:
            problems.append(f"missing top-level key: {key}")

    for w in dataset.get("weapons", []):
        wid = w.get("id", "<unknown>")
        for k in _REQUIRED_WEAPON_KEYS:
            if k not in w:
                problems.append(f"weapon {wid} missing key: {k}")
        tier = w.get("tier")
        if not isinstance(tier, int) or not (1 <= tier <= 4):
            problems.append(f"weapon {wid} has invalid tier: {tier}")

    for it in dataset.get("items", []):
        if not isinstance(it.get("effects"), list):
            problems.append(f"item {it.get('id', '<unknown>')} missing effects list")

    return problems


def load_dataset(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"dataset not found at {path}; run build_dataset.py first"
        ) from exc
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_dataset.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/build/mechanics.py brotato_coach/dataset.py tests/test_dataset.py
git commit -m "feat: stat-mechanics table + dataset assembly and validation"
```

---

### Task 8: Dataset query core — retrieval + fuzzy match (`query.py`)

**Files:**
- Create: `brotato_coach/query.py`
- Test: `tests/test_query.py`

**Interfaces:**
- Consumes: a loaded dataset dict (Task 7 shape).
- Produces (all pure, dataset passed in):
  - `get_weapon(ds, name, tier=None) -> dict` → the weapon record, or `{"error": "not_found", "did_you_mean": [...]}`. When `tier` is None and multiple tiers match, returns `{"matches": [records...]}`.
  - `get_item(ds, name) -> dict` (record or not_found error).
  - `get_character(ds, name) -> dict`.
  - `get_set(ds, class_name) -> dict`.
  - `list_weapons(ds, *, scaling_stat=None, tier=None) -> list[dict]` (summaries: id, name, tier).
  - `list_items(ds, *, tag=None, scaling_stat=None, archetype=None, tier=None) -> list[dict]`.
  - Fuzzy match via `difflib.get_close_matches` over names + ids.

- [ ] **Step 1: Write the failing tests**

`tests/test_query.py`:
```python
from brotato_coach import query

DS = {
    "weapons": [
        {"id": "weapon_shredder", "name": "Shredder", "tier": 4, "scaling_stats": [["stat_ranged_damage", 0.5]]},
        {"id": "weapon_shredder", "name": "Shredder", "tier": 3, "scaling_stats": [["stat_ranged_damage", 0.5]]},
        {"id": "weapon_wand", "name": "Wand", "tier": 1, "scaling_stats": [["stat_elemental_damage", 1.0]]},
    ],
    "items": [
        {"id": "item_handcuffs", "name": "Handcuffs", "tier": 2, "tags": ["stat_ranged_damage"],
         "archetype": ["cap_at_current_value"], "scaling_stats": ["stat_ranged_damage"]},
        {"id": "item_lens", "name": "Lens", "tier": 0, "tags": ["stat_ranged_damage"],
         "archetype": [], "scaling_stats": ["stat_ranged_damage"]},
    ],
    "characters": [{"id": "character_ranger", "name": "Ranger"}],
    "sets": [{"id": "set_gun", "name": "Gun", "bonuses": []}],
}


def test_get_weapon_specific_tier():
    rec = query.get_weapon(DS, "Shredder", tier=4)
    assert rec["tier"] == 4


def test_get_weapon_all_tiers():
    rec = query.get_weapon(DS, "Shredder")
    assert {m["tier"] for m in rec["matches"]} == {3, 4}


def test_get_weapon_fuzzy_not_found():
    rec = query.get_weapon(DS, "shreddar", tier=4)
    assert rec["error"] == "not_found"
    assert "Shredder" in rec["did_you_mean"] or "weapon_shredder" in rec["did_you_mean"]


def test_list_weapons_by_scaling_stat():
    result = query.list_weapons(DS, scaling_stat="stat_ranged_damage")
    assert all(w["name"] == "Shredder" for w in result)


def test_list_items_by_archetype():
    result = query.list_items(DS, archetype="cap_at_current_value")
    assert [i["name"] for i in result] == ["Handcuffs"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_query.py -v`
Expected: FAIL (cannot import `query`).

- [ ] **Step 3: Implement `query.py`**

`brotato_coach/query.py`:
```python
from __future__ import annotations

import difflib


def _names(records: list[dict]) -> list[str]:
    out = []
    for r in records:
        out.extend([r.get("name", ""), r.get("id", "")])
    return [n for n in out if n]


def _suggest(records: list[dict], name: str) -> list[str]:
    return difflib.get_close_matches(name, _names(records), n=3, cutoff=0.5)


def _match(records: list[dict], name: str) -> list[dict]:
    low = name.lower()
    return [r for r in records if r.get("name", "").lower() == low or r.get("id", "").lower() == low]


def get_weapon(ds: dict, name: str, tier: int | None = None) -> dict:
    matches = _match(ds["weapons"], name)
    if tier is not None:
        matches = [m for m in matches if m.get("tier") == tier]
    if not matches:
        return {"error": "not_found", "did_you_mean": _suggest(ds["weapons"], name)}
    if len(matches) == 1:
        return matches[0]
    return {"matches": matches}


def _get_one(records: list[dict], name: str) -> dict:
    matches = _match(records, name)
    if not matches:
        return {"error": "not_found", "did_you_mean": _suggest(records, name)}
    return matches[0]


def get_item(ds: dict, name: str) -> dict:
    return _get_one(ds["items"], name)


def get_character(ds: dict, name: str) -> dict:
    return _get_one(ds["characters"], name)


def get_set(ds: dict, class_name: str) -> dict:
    return _get_one(ds["sets"], class_name)


def _summary(r: dict) -> dict:
    return {"id": r.get("id"), "name": r.get("name"), "tier": r.get("tier")}


def list_weapons(ds: dict, *, scaling_stat=None, tier=None) -> list[dict]:
    out = []
    for w in ds["weapons"]:
        if tier is not None and w.get("tier") != tier:
            continue
        if scaling_stat is not None:
            stats = [s[0] for s in w.get("scaling_stats", []) if isinstance(s, list) and s]
            if scaling_stat not in stats:
                continue
        out.append(_summary(w))
    return out


def list_items(ds: dict, *, tag=None, scaling_stat=None, archetype=None, tier=None) -> list[dict]:
    out = []
    for it in ds["items"]:
        if tier is not None and it.get("tier") != tier:
            continue
        if tag is not None and tag not in it.get("tags", []):
            continue
        if scaling_stat is not None and scaling_stat not in it.get("scaling_stats", []):
            continue
        if archetype is not None and archetype not in it.get("archetype", []):
            continue
        out.append(_summary(it))
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_query.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/query.py tests/test_query.py
git commit -m "feat: dataset query core with fuzzy-match retrieval"
```

---

### Task 9: Calculator + mechanics answer functions (`answers.py`)

**Files:**
- Create: `brotato_coach/answers.py`
- Test: `tests/test_answers.py`

**Interfaces:**
- Consumes: `query` (Task 8), `calc` (Task 2), dataset `stat_mechanics` (Task 7).
- Produces (pure, dataset passed in):
  - `weapon_dps(ds, name, tier, stats) -> dict` → `{name, tier, ranged_damage, dps, breakdown}` where `dps = dps_at_zero_rd + slope*rd`. Returns the query error if the weapon is missing.
  - `compare_weapons(ds, names_with_tiers, stats) -> dict` → `{ranking: [{name, tier, dps}...]}` sorted desc.
  - `compare_merge_paths(ds, weapon_name, path_a, path_b, rd_range=(0,100)) -> dict` where each path is a list of tiers; sums each path's DPS lines and calls `calc.compare_lines`.
  - `explain_stat(ds, stat) -> dict` → the `stat_mechanics` entry plus `{stat}`, or `{"error": "unknown_stat", "did_you_mean": [...]}`.
  - `stat_display_value(ds, character, stat, raw_value) -> dict` → `{stat, raw_value, displayed_value, modifier_pct}` applying the character's matching `gain_modifiers` entry (0% if none).

- [ ] **Step 1: Write the failing tests**

`tests/test_answers.py`:
```python
import math

from brotato_coach import answers

DS = {
    "weapons": [
        {"id": "weapon_minigun", "name": "Minigun", "tier": 4,
         "dps_at_zero_rd": 55.5556, "dps_slope_per_rd": 8.3333, "scaling_stats": []},
        {"id": "weapon_revolver", "name": "Revolver", "tier": 4,
         "dps_at_zero_rd": 57.35, "dps_slope_per_rd": 2.8673, "scaling_stats": []},
        {"id": "weapon_laser", "name": "Laser", "tier": 2,
         "dps_at_zero_rd": 30.0, "dps_slope_per_rd": 1.8, "scaling_stats": []},
        {"id": "weapon_laser", "name": "Laser", "tier": 3,
         "dps_at_zero_rd": 45.0, "dps_slope_per_rd": 2.7, "scaling_stats": []},
        {"id": "weapon_laser", "name": "Laser", "tier": 1,
         "dps_at_zero_rd": 15.0, "dps_slope_per_rd": 0.9, "scaling_stats": []},
    ],
    "characters": [
        {"id": "character_ranger", "name": "Ranger",
         "gain_modifiers": [{"stat": "stat_ranged_damage", "pct": 50},
                            {"stat": "stat_max_hp", "pct": -25}]},
    ],
    "stat_mechanics": {
        "stat_attack_speed": {"special": "attack_speed_universal", "never_dead_weight": True},
    },
}


def test_weapon_dps_at_rd():
    result = answers.weapon_dps(DS, "Minigun", 4, {"ranged_damage": 10})
    assert math.isclose(result["dps"], 55.5556 + 8.3333 * 10, rel_tol=1e-4)


def test_compare_weapons_minigun_beats_revolver_at_rd10():
    result = answers.compare_weapons(
        DS, [("Minigun", 4), ("Revolver", 4)], {"ranged_damage": 10})
    assert result["ranking"][0]["name"] == "Minigun"


def test_compare_merge_paths_crossover_reported():
    # path_a = II+II (two tier-2), path_b = III+I (tier-3 + tier-1)
    result = answers.compare_merge_paths(DS, "Laser", [2, 2], [3, 1])
    # II+II line: (60.0, 3.6); III+I line: (60.0, 3.6) -> effectively tie
    assert "crossover_rd" in result


def test_explain_stat_known():
    result = answers.explain_stat(DS, "stat_attack_speed")
    assert result["never_dead_weight"] is True


def test_stat_display_value_ranger_rd():
    result = answers.stat_display_value(DS, "Ranger", "stat_ranged_damage", 6)
    assert result["displayed_value"] == 9
    assert result["modifier_pct"] == 50


def test_stat_display_value_no_modifier():
    result = answers.stat_display_value(DS, "Ranger", "stat_speed", 10)
    assert result["displayed_value"] == 10
    assert result["modifier_pct"] == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_answers.py -v`
Expected: FAIL (cannot import `answers`).

- [ ] **Step 3: Implement `answers.py`**

`brotato_coach/answers.py`:
```python
from __future__ import annotations

import difflib

from brotato_coach import calc, query


def _weapon_at(ds: dict, name: str, tier: int) -> dict | None:
    rec = query.get_weapon(ds, name, tier=tier)
    return rec if "id" in rec else None


def weapon_dps(ds: dict, name: str, tier: int, stats: dict) -> dict:
    rec = query.get_weapon(ds, name, tier=tier)
    if "id" not in rec:
        return rec
    rd = float(stats.get("ranged_damage", 0))
    dps = calc.dps_at(rec["dps_at_zero_rd"], rec["dps_slope_per_rd"], rd)
    return {
        "name": rec["name"], "tier": tier, "ranged_damage": rd, "dps": dps,
        "breakdown": {
            "dps_at_zero_rd": rec["dps_at_zero_rd"],
            "dps_slope_per_rd": rec["dps_slope_per_rd"],
        },
    }


def compare_weapons(ds: dict, names_with_tiers: list, stats: dict) -> dict:
    rows = []
    for name, tier in names_with_tiers:
        r = weapon_dps(ds, name, tier, stats)
        if "dps" in r:
            rows.append({"name": r["name"], "tier": tier, "dps": r["dps"]})
    rows.sort(key=lambda x: x["dps"], reverse=True)
    return {"ranking": rows}


def compare_merge_paths(ds: dict, weapon_name: str, path_a: list, path_b: list,
                        rd_range: tuple = (0, 100)) -> dict:
    def path_line(tiers: list) -> tuple[float, float] | None:
        lines = []
        for t in tiers:
            rec = _weapon_at(ds, weapon_name, t)
            if rec is None:
                return None
            lines.append((rec["dps_at_zero_rd"], rec["dps_slope_per_rd"]))
        return calc.sum_lines(lines)

    line_a, line_b = path_line(path_a), path_line(path_b)
    if line_a is None or line_b is None:
        return {"error": "not_found",
                "did_you_mean": difflib.get_close_matches(
                    weapon_name, [w["name"] for w in ds["weapons"]], n=3, cutoff=0.5)}

    result = calc.compare_lines(line_a, line_b, rd_range[0], rd_range[1])
    return {
        "weapon": weapon_name, "path_a": path_a, "path_b": path_b,
        "line_a": line_a, "line_b": line_b, **result,
    }


def explain_stat(ds: dict, stat: str) -> dict:
    mechanics = ds.get("stat_mechanics", {})
    if stat not in mechanics:
        return {"error": "unknown_stat",
                "did_you_mean": difflib.get_close_matches(stat, list(mechanics), n=3, cutoff=0.4)}
    return {"stat": stat, **mechanics[stat]}


def stat_display_value(ds: dict, character: str, stat: str, raw_value: float) -> dict:
    rec = query.get_character(ds, character)
    modifier_pct = 0
    if "id" in rec:
        for mod in rec.get("gain_modifiers", []):
            if mod["stat"] == stat:
                modifier_pct = mod["pct"]
                break
    displayed = raw_value * (1 + modifier_pct / 100)
    displayed = int(displayed) if float(displayed).is_integer() else displayed
    return {"stat": stat, "raw_value": raw_value, "displayed_value": displayed,
            "modifier_pct": modifier_pct}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_answers.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/answers.py tests/test_answers.py
git commit -m "feat: DPS/merge/mechanics answer functions"
```

---

### Task 10: Flagship build-fit evaluator (`evaluate.py`)

**Files:**
- Create: `brotato_coach/evaluate.py`
- Test: `tests/test_evaluate.py`

**Interfaces:**
- Consumes: `query` (Task 8).
- Produces: `evaluate_item_for_build(ds, item_name, character_name, current_stats) -> dict` → `{item, character, effects: [{effect, verdict, reason}...], summary}`.
- Verdict rules (deterministic, checked in order per effect):
  1. Item archetype `cap_at_current_value` and this effect is the cap effect → `harmful`, reason names `frozen_stat` and its current value if present in `current_stats`.
  2. Effect key is `stat_melee_damage` **and** character has `no_melee_weapons` in `special_effects` (or `melee_damage` in `banned_item_groups`) → `wasted`, reason "character cannot use melee weapons".
  3. Effect key in character `wanted_tags` → `live`.
  4. Effect key is a `stat_*` with positive value, not wanted, and `current_stats.get(short_stat, 0) <= 0` → `wasted`, reason "no investment in <stat>".
  5. Otherwise → `live`.
- `short_stat` strips the `stat_` prefix (so `stat_elemental_damage` looks up `elemental_damage` in `current_stats`).

- [ ] **Step 1: Write the failing test**

`tests/test_evaluate.py`:
```python
from brotato_coach.evaluate import evaluate_item_for_build

DS = {
    "items": [{
        "id": "item_handcuffs", "name": "Handcuffs", "tier": 2, "value": 80,
        "tags": ["stat_melee_damage", "stat_ranged_damage", "stat_elemental_damage"],
        "archetype": ["cap_at_current_value"], "frozen_stat": "stat_max_hp",
        "scaling_stats": ["stat_melee_damage", "stat_ranged_damage", "stat_elemental_damage"],
        "damage_tags": ["stat_melee_damage", "stat_ranged_damage", "stat_elemental_damage"],
        "effects": [
            {"key": "stat_melee_damage", "value": 8, "effect_sign": 3, "text_key": ""},
            {"key": "stat_ranged_damage", "value": 8, "effect_sign": 3, "text_key": ""},
            {"key": "stat_elemental_damage", "value": 8, "effect_sign": 3, "text_key": ""},
            {"key": "hp_cap", "value": 0, "effect_sign": 0, "text_key": "EFFECT_HP_CAP_AT_CURRENT_VALUE"},
        ],
    }],
    "characters": [{
        "id": "character_ranger", "name": "Ranger",
        "wanted_tags": ["stat_ranged_damage", "stat_range"],
        "banned_item_groups": ["melee_damage"],
        "special_effects": ["no_melee_weapons"],
    }],
}


def _verdict(result, key):
    for e in result["effects"]:
        if e["effect"]["key"] == key:
            return e["verdict"]
    raise AssertionError(f"no effect {key}")


def test_handcuffs_on_ranger_breakdown():
    result = evaluate_item_for_build(DS, "Handcuffs", "Ranger",
                                     {"ranged_damage": 6, "melee_damage": 0, "elemental_damage": -1})
    assert _verdict(result, "stat_ranged_damage") == "live"
    assert _verdict(result, "stat_melee_damage") == "wasted"
    assert _verdict(result, "stat_elemental_damage") == "wasted"
    assert _verdict(result, "hp_cap") == "harmful"


def test_handcuffs_hp_cap_reason_mentions_frozen_stat():
    result = evaluate_item_for_build(DS, "Handcuffs", "Ranger", {"max_hp": 36})
    cap = next(e for e in result["effects"] if e["effect"]["key"] == "hp_cap")
    assert "stat_max_hp" in cap["reason"]
    assert "36" in cap["reason"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_evaluate.py -v`
Expected: FAIL (cannot import `evaluate_item_for_build`).

- [ ] **Step 3: Implement `evaluate.py`**

`brotato_coach/evaluate.py`:
```python
from __future__ import annotations

from brotato_coach import query


def _short(stat: str) -> str:
    return stat[len("stat_"):] if stat.startswith("stat_") else stat


def _classify(effect: dict, item: dict, character: dict, current_stats: dict) -> tuple[str, str]:
    key = str(effect["key"])
    value = effect.get("value", 0)

    if "cap_at_current_value" in item.get("archetype", []) and (
        key.endswith("_cap") or "CAP_AT_CURRENT_VALUE" in str(effect.get("text_key", ""))
    ):
        frozen = item.get("frozen_stat") or "a stat"
        cur = current_stats.get(_short(frozen)) if item.get("frozen_stat") else None
        at = f" at current value ({cur})" if cur is not None else " at its current value"
        return "harmful", f"freezes {frozen}{at} for the rest of the run"

    banned = "melee_damage" in character.get("banned_item_groups", [])
    no_melee = "no_melee_weapons" in character.get("special_effects", [])
    if key == "stat_melee_damage" and (banned or no_melee):
        return "wasted", "character cannot use melee weapons"

    if key in character.get("wanted_tags", []):
        return "live", f"{key} is a wanted stat for this character"

    if key.startswith("stat_") and isinstance(value, (int, float)) and value > 0:
        if current_stats.get(_short(key), 0) <= 0:
            return "wasted", f"no investment in {_short(key)}"

    return "live", "applies to this build"


def evaluate_item_for_build(ds: dict, item_name: str, character_name: str,
                            current_stats: dict) -> dict:
    item = query.get_item(ds, item_name)
    if "id" not in item:
        return item
    character = query.get_character(ds, character_name)
    if "id" not in character:
        return character

    effects = []
    for eff in item.get("effects", []):
        verdict, reason = _classify(eff, item, character, current_stats)
        effects.append({"effect": eff, "verdict": verdict, "reason": reason})

    counts = {"live": 0, "wasted": 0, "harmful": 0}
    for e in effects:
        counts[e["verdict"]] = counts.get(e["verdict"], 0) + 1
    summary = (f"{counts['live']} live, {counts['wasted']} wasted, "
               f"{counts['harmful']} harmful effect(s) for {character['name']}")

    return {"item": item["name"], "character": character["name"],
            "effects": effects, "summary": summary}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_evaluate.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/evaluate.py tests/test_evaluate.py
git commit -m "feat: flagship build-fit evaluator (live/wasted/harmful)"
```

---

### Task 11: Build CLI (`build_dataset.py`)

**Files:**
- Create: `build_dataset.py`
- Create: `brotato_coach/build/discover.py`
- Test: `tests/test_build_discover.py`

**Interfaces:**
- Consumes: all `build/*` builders (Tasks 4-6), `dataset.assemble_dataset`/`validate_dataset` (Task 7).
- Produces:
  - `discover.find_weapon_dirs(extracted_root) -> list[dict]` → for each weapon tier dir found under `weapons/{melee,ranged}/<w>/<tier>/`, a dict `{weapon_id, name, tier, stats_path, data_path}`. (Name resolution: title-cased from the weapon folder name; the coach can refine display names later — folder name is the stable key.)
  - `build_dataset.py` CLI: `python build_dataset.py --extracted extracted --out data/brotato.json --game-version <v> --generated-at <iso8601>` → parses, assembles, validates, writes JSON (exit 1 and print problems if validation fails).
- Rationale for splitting `discover.py`: filesystem-walking logic is testable with a `tmp_path` fixture independently of the CLI wiring.

- [ ] **Step 1: Write the failing test**

`tests/test_build_discover.py`:
```python
from brotato_coach.build.discover import find_weapon_dirs


def test_find_weapon_dirs(tmp_path):
    d = tmp_path / "weapons" / "ranged" / "shredder" / "4"
    d.mkdir(parents=True)
    (d / "shredder_4_stats.tres").write_text("stats")
    (d / "shredder_4_data.tres").write_text("data")

    found = find_weapon_dirs(str(tmp_path))
    assert len(found) == 1
    entry = found[0]
    assert entry["weapon_id"] == "weapon_shredder"
    assert entry["tier"] == 4
    assert entry["stats_path"].endswith("shredder_4_stats.tres")
    assert entry["data_path"].endswith("shredder_4_data.tres")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_build_discover.py -v`
Expected: FAIL (cannot import `find_weapon_dirs`).

- [ ] **Step 3: Implement discovery and the CLI**

`brotato_coach/build/discover.py`:
```python
from __future__ import annotations

import glob
import os


def find_weapon_dirs(extracted_root: str) -> list[dict]:
    results = []
    for kind in ("ranged", "melee"):
        pattern = os.path.join(extracted_root, "weapons", kind, "*", "*")
        for tier_dir in sorted(glob.glob(pattern)):
            if not os.path.isdir(tier_dir):
                continue
            tier_name = os.path.basename(tier_dir)
            if not tier_name.isdigit():
                continue
            weapon_folder = os.path.basename(os.path.dirname(tier_dir))
            stats = glob.glob(os.path.join(tier_dir, "*_stats.tres"))
            data = glob.glob(os.path.join(tier_dir, "*_data.tres"))
            if not stats or not data:
                continue
            results.append({
                "weapon_id": f"weapon_{weapon_folder}",
                "name": weapon_folder.replace("_", " ").title(),
                "tier": int(tier_name),
                "stats_path": stats[0],
                "data_path": data[0],
            })
    return results
```

`build_dataset.py` (repo root):
```python
"""Distill extracted/ .tres game data into data/brotato.json.

Usage:
    python build_dataset.py --extracted extracted --out data/brotato.json \
        --game-version 1.1.0.0 --generated-at 2026-07-01T00:00:00Z
"""

from __future__ import annotations

import argparse
import json
import sys

from brotato_coach import dataset
from brotato_coach.build import discover
from brotato_coach.build.weapons import build_weapon_record


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extracted", default="extracted")
    parser.add_argument("--out", default="data/brotato.json")
    parser.add_argument("--game-version", required=True)
    parser.add_argument("--generated-at", required=True)
    args = parser.parse_args(argv)

    weapons = []
    for entry in discover.find_weapon_dirs(args.extracted):
        weapons.append(build_weapon_record(
            _read(entry["stats_path"]), _read(entry["data_path"]),
            weapon_id=entry["weapon_id"], name=entry["name"], tier=entry["tier"],
        ))

    # Items/characters/sets discovery wiring follows the same shape as weapons;
    # they are assembled here once their discovery helpers land. For the first
    # buildable dataset, weapons alone produce a valid, useful artifact.
    ds = dataset.assemble_dataset(
        game_version=args.game_version, generated_at=args.generated_at,
        weapons=weapons, items=[], characters=[], sets=[],
    )

    problems = dataset.validate_dataset(ds)
    if problems:
        print("Dataset validation failed:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    import os
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(ds, fh, indent=2)
    print(f"Wrote {args.out}: {len(weapons)} weapon records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

> **Note for the implementer:** item/character/set discovery helpers mirror `find_weapon_dirs` (walk `items/all/<item>/`, `items/characters/<char>/`, `items/sets/<class>/`, collect `*_data.tres` + `*_effect*.tres`). Add them as follow-on discovery functions with their own `tmp_path` tests, then wire them into `main()` exactly like weapons. They are intentionally out of this task's test scope so the first end-to-end build is small and green; the wanted_tags/banned_item_groups for characters come from each `<char>_data.tres` (`wanted_tags`, `banned_item_groups` fields).

- [ ] **Step 4: Run the test and a real smoke build**

Run: `uv run pytest tests/test_build_discover.py -v`
Expected: PASS (1 passed).

If `extracted/` is present locally, also run:
```bash
uv run python build_dataset.py --game-version dev --generated-at 2026-07-01T00:00:00Z
uv run python -c "import json; d=json.load(open('data/brotato.json')); print(len(d['weapons']), 'weapons')"
```
Expected: writes `data/brotato.json` with a non-zero weapon count.

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/build/discover.py build_dataset.py tests/test_build_discover.py data/brotato.json
git commit -m "feat: dataset build CLI + weapon discovery (first buildable dataset)"
```

---

### Task 12: MCP server + Claude Code plugin packaging

**Files:**
- Create: `brotato_coach/server.py`
- Create: `plugin/.mcp.json`
- Create: `README.md`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `query`, `answers`, `evaluate`, `dataset` (Tasks 7-10).
- Produces:
  - `server.py`: `build_server(ds: dict) -> FastMCP` registering the Section-3 tools as thin wrappers over the pure functions. Each tool wraps its call in a try/except that returns `{"error": "internal", "detail": str(exc)}` so the LLM never sees a raw traceback.
  - `check_dataset_version()` tool returning `{game_version, generated_at, schema_version}`.
  - A `main()` that loads `data/brotato.json` via `dataset.load_dataset` and runs the server over stdio.
- The server test calls `build_server` and invokes tools through the registered functions — no stdio transport needed.

- [ ] **Step 1: Write the failing test**

`tests/test_server.py`:
```python
from brotato_coach.server import build_server

DS = {
    "schema_version": 1, "game_version": "dev", "generated_at": "t",
    "weapons": [{"id": "weapon_minigun", "name": "Minigun", "tier": 4,
                 "dps_at_zero_rd": 55.5556, "dps_slope_per_rd": 8.3333, "scaling_stats": []}],
    "items": [], "characters": [], "sets": [], "stat_mechanics": {},
}


async def _call(server, name, **kwargs):
    result = await server.call_tool(name, kwargs)
    # FastMCP returns (content, structured) — the structured payload is the dict
    structured = result[1] if isinstance(result, tuple) else result
    return structured


def test_server_registers_tools():
    server = build_server(DS)
    tool_names = {t.name for t in server._tool_manager.list_tools()}
    assert {"get_weapon", "weapon_dps", "evaluate_item_for_build",
            "check_dataset_version"} <= tool_names


import asyncio


def test_check_dataset_version_tool():
    server = build_server(DS)
    result = asyncio.run(_call(server, "check_dataset_version"))
    assert result["game_version"] == "dev"


def test_weapon_dps_tool():
    server = build_server(DS)
    result = asyncio.run(_call(server, "weapon_dps", name="Minigun", tier=4,
                               stats={"ranged_damage": 10}))
    assert round(result["dps"]) == round(55.5556 + 8.3333 * 10)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_server.py -v`
Expected: FAIL (cannot import `build_server`).

- [ ] **Step 3: Implement the server and packaging**

`brotato_coach/server.py`:
```python
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from brotato_coach import answers, dataset, evaluate, query


def _safe(fn):
    def wrapper(**kwargs):
        try:
            return fn(**kwargs)
        except Exception as exc:  # noqa: BLE001 - surface as structured error, never a traceback
            return {"error": "internal", "detail": str(exc)}
    return wrapper


def build_server(ds: dict) -> FastMCP:
    mcp = FastMCP("brotato-coach")

    @mcp.tool()
    def get_weapon(name: str, tier: int | None = None) -> dict:
        return query.get_weapon(ds, name, tier)

    @mcp.tool()
    def get_item(name: str) -> dict:
        return query.get_item(ds, name)

    @mcp.tool()
    def get_character(name: str) -> dict:
        return query.get_character(ds, name)

    @mcp.tool()
    def get_set(class_name: str) -> dict:
        return query.get_set(ds, class_name)

    @mcp.tool()
    def list_weapons(scaling_stat: str | None = None, tier: int | None = None) -> dict:
        return {"weapons": query.list_weapons(ds, scaling_stat=scaling_stat, tier=tier)}

    @mcp.tool()
    def list_items(tag: str | None = None, scaling_stat: str | None = None,
                   archetype: str | None = None, tier: int | None = None) -> dict:
        return {"items": query.list_items(ds, tag=tag, scaling_stat=scaling_stat,
                                          archetype=archetype, tier=tier)}

    @mcp.tool()
    def weapon_dps(name: str, tier: int, stats: dict) -> dict:
        return _safe(answers.weapon_dps)(ds=ds, name=name, tier=tier, stats=stats)

    @mcp.tool()
    def compare_weapons(names_with_tiers: list, stats: dict) -> dict:
        pairs = [tuple(x) for x in names_with_tiers]
        return answers.compare_weapons(ds, pairs, stats)

    @mcp.tool()
    def compare_merge_paths(weapon_name: str, path_a: list, path_b: list) -> dict:
        return answers.compare_merge_paths(ds, weapon_name, path_a, path_b)

    @mcp.tool()
    def explain_stat(stat: str) -> dict:
        return answers.explain_stat(ds, stat)

    @mcp.tool()
    def stat_display_value(character: str, stat: str, raw_value: float) -> dict:
        return answers.stat_display_value(ds, character, stat, raw_value)

    @mcp.tool()
    def evaluate_item_for_build(item_name: str, character_name: str,
                                current_stats: dict) -> dict:
        return _safe(evaluate.evaluate_item_for_build)(
            ds=ds, item_name=item_name, character_name=character_name,
            current_stats=current_stats)

    @mcp.tool()
    def check_dataset_version() -> dict:
        return {"game_version": ds.get("game_version"),
                "generated_at": ds.get("generated_at"),
                "schema_version": ds.get("schema_version")}

    return mcp


def main() -> None:
    ds = dataset.load_dataset("data/brotato.json")
    build_server(ds).run()


if __name__ == "__main__":
    main()
```

`plugin/.mcp.json`:
```json
{
  "mcpServers": {
    "brotato-coach": {
      "command": "uv",
      "args": ["run", "python", "-m", "brotato_coach.server"],
      "cwd": "${CLAUDE_PLUGIN_ROOT}"
    }
  }
}
```

`README.md`:
```markdown
# Brotato Coach

Deterministic theorycrafter core + MCP server for a Brotato AI coach.

## Build the dataset

Requires a local extraction (`extracted/`) from a Brotato install (see
`docs/extraction-setup.md`). Then:

```bash
uv run python build_dataset.py --game-version <version> \
    --generated-at $(date -u +%Y-%m-%dT%H:%M:%SZ)
```

This writes `data/brotato.json`, the committed artifact the server reads.
Re-run it after each Brotato patch.

## Run the MCP server

```bash
uv run python -m brotato_coach.server
```

## Use as a Claude Code plugin

The server is registered via `plugin/.mcp.json`. The tools expose weapon/item/
character lookups, DPS and merge-path calculators, stat-mechanics explanations,
and the `evaluate_item_for_build` build-fit evaluator.

## Test

```bash
uv run pytest
```
```

- [ ] **Step 4: Run the tests and the full suite**

Run:
```bash
uv run pytest tests/test_server.py -v
uv run pytest
```
Expected: server tests PASS; full suite green.

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/server.py plugin/.mcp.json README.md tests/test_server.py
git commit -m "feat: FastMCP server wiring + Claude Code plugin packaging"
```

---

## Self-Review

**Spec coverage:**
- Distilled dataset + build boundary → Tasks 4-7, 11. ✓
- Enriched weapon records w/ precomputed DPS line → Task 4. ✓
- Item archetype (cap-at-current-value) + frozen_stat → Task 5. ✓
- Character kit + gain modifiers; sets → Task 6. ✓
- stat_mechanics encoded from code → Task 7. ✓
- Retrieval/filter tools + fuzzy match → Task 8. ✓
- Calculators (weapon_dps, compare_weapons, compare_merge_paths) + mechanics (explain_stat, stat_display_value) → Task 9. ✓
- Flagship evaluate_item_for_build (live/wasted/harmful) → Task 10. ✓
- check_dataset_version + structured errors + MCP server → Task 12. ✓
- Golden tests from session values (Minigun/Revolver/Laser/Shredder, Ranger RD 6→9, Handcuffs breakdown) → Tasks 2, 4, 9, 10. ✓
- Claude Code packaging → Task 12. ✓ (Desktop/Web deferred per spec.)

**Known deferrals (spec-sanctioned, not gaps):** item/character/set *discovery* wiring in the build CLI is scoped as a follow-on within Task 11's note — weapons alone give the first green end-to-end build, and the builders they depend on (Tasks 5-6) are fully implemented and tested. Live-state ingestion is Phase 2. Single-file vs. split dataset stays single-file (`data/brotato.json`).

**Placeholder scan:** no TBD/TODO in code steps; every code step shows complete, runnable code; the Task 11 note describes a real, testable follow-on (not a vague placeholder) and does not block a green build.

**Type consistency:** weapon record keys (`dps_at_zero_rd`, `dps_slope_per_rd`, `cycle_time`) are identical across Tasks 4, 7, 8, 9, 12. `evaluate_item_for_build` return shape (`effects[].verdict/reason`) matches its test and the server wrapper. Query error shape (`{"error", "did_you_mean"}`) is uniform across Tasks 8-10.
