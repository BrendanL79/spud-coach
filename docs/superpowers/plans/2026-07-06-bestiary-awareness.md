# Bestiary Awareness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface base-game (Crash Zone / `zone_1`) enemy stats and per-wave spawn composition through the spud-coach MCP server, and fold a threat-aware `wave_context` section into the run post-mortem.

**Architecture:** Follows the existing one-way data flow. New discovery + builder code reads `extracted/` `.tres`/`.tscn` and emits two new dataset arrays (`enemies`, `zone_1_waves`); a new pure-logic module (`bestiary.py`) computes effective per-wave stats and wave composition with no I/O; thin `server.py` tools wrap it. Spec: `docs/superpowers/specs/2026-07-06-bestiary-awareness-design.md`.

**Tech Stack:** Python 3.11+, uv, pytest, ruff, FastMCP. Godot 3 `.tres`/`.tscn` text resources.

## Global Constraints

- Python 3.11+, managed with **uv**: `uv run pytest`, `uv run ruff check .` (keep both green).
- **TDD**: write the failing test first, watch it fail, then implement.
- **Never commit the dataset or extracted game data** — `data/brotato.json`, `extracted/`, `recovered/` are gitignored and copyrighted. Regenerate locally; never `git add` them.
- **One-way data flow**: only the build step (`build_dataset.py` + `brotato_coach/builders/`) reads `extracted/`. The server and pure-logic layer read only `data/brotato.json`.
- **Honesty envelope** (verbatim from spec): report exact stats and exact base composition; compute effective per-wave stats as `base + increase_each_wave × (wave − 1)`; present movement speed as `speed ± speed_randomization`; label run-dependent counts (`number_of_enemies %`, co-op) and elite/horde presence as run-variance, never as guaranteed.
- Internal `difficulty` maps 1:1 to displayed Danger (D6 is a real unlockable tier); danger-gate a group when `min_difficulty <= danger <= max_difficulty`.
- Branch: `feature/bestiary-awareness`. Commit after every task.
- **Deviation from spec (intentional):** `enemy.zone_id` is omitted from the first cut — `appears_in` already carries provenance for the base-game scope. Bosses appear as records with `abilities: ["bespoke_kit_not_modeled"]`.

---

## File Structure

- Create: `brotato_coach/scene.py` — minimal `.tscn` node-section reader (`parse_scene_node`).
- Create: `brotato_coach/builders/enemies.py` — `build_enemy_record`.
- Create: `brotato_coach/builders/waves.py` — `build_wave_record`, `zone_roster_provenance`.
- Create: `brotato_coach/bestiary.py` — pure logic: effective stats, `get_enemy`, `list_enemies`, `wave_composition`, `wave_context`.
- Modify: `brotato_coach/builders/discover.py` — add `find_enemy_dirs`, `find_zone_waves`.
- Modify: `brotato_coach/dataset.py` — assemble/validate the two arrays; bump `DATASET_VERSION` to 4.
- Modify: `build_dataset.py` — wire enemy + wave records into the build.
- Modify: `brotato_coach/answers.py` — add `wave_context` to `evaluate_run`.
- Modify: `brotato_coach/server.py` — add 3 tools + extend `get_filter_options`.
- Modify: `brotato_coach/orientation.py` — add a bestiary section to `read_me`.
- Tests: `tests/test_scene.py`, `tests/test_build_enemies.py`, `tests/test_build_waves.py`, `tests/test_bestiary.py` (new); `tests/test_build_discover.py`, `tests/test_dataset.py`, `tests/test_run_report.py`, `tests/test_server.py`, `tests/test_orientation.py` (modified).

---

## Task 1: Scene-node parser (`scene.py`)

Reads a named `[node ...]` block from a Godot `.tscn` scene. `parse_tres` only reads the `[resource]` section, so numeric attack params in `[node name="AttackBehavior"]` need this. Reuses `_parse_value` from `tres.py` for Godot literal parsing.

**Files:**
- Create: `brotato_coach/scene.py`
- Test: `tests/test_scene.py`

**Interfaces:**
- Consumes: `brotato_coach.tres._parse_value`
- Produces: `parse_scene_node(text: str, node_name: str) -> dict[str, object]` — the KV dict of the first `[node name="<node_name>" ...]` section (empty dict if absent).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scene.py
from brotato_coach.scene import parse_scene_node

_SCENE = '''[gd_scene load_steps=2 format=2]

[ext_resource path="res://projectiles/bullet_enemy/enemy_projectile.tscn" type="PackedScene" id=4]

[node name="Enemy" index="0"]

[node name="AttackBehavior" parent="." index="7"]
projectile_scene = ExtResource( 4 )
projectile_speed = 600
damage = 1
damage_increase_each_wave = 0.75
number_projectiles = 1
spawn_projectiles_on_target = false
'''


def test_reads_named_node_kvs():
    node = parse_scene_node(_SCENE, "AttackBehavior")
    assert node["damage"] == 1
    assert node["damage_increase_each_wave"] == 0.75
    assert node["number_projectiles"] == 1
    assert node["projectile_speed"] == 600
    assert node["spawn_projectiles_on_target"] is False
    assert node["projectile_scene"] == {"__ext__": 4}


def test_missing_node_returns_empty():
    assert parse_scene_node(_SCENE, "NoSuchNode") == {}


def test_stops_at_next_section():
    # "Enemy" node has no KVs before AttackBehavior begins
    assert parse_scene_node(_SCENE, "Enemy") == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_scene.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'brotato_coach.scene'`

- [ ] **Step 3: Write minimal implementation**

```python
# brotato_coach/scene.py
"""Read a named [node ...] block from a Godot 3 .tscn scene.

parse_tres only captures the [resource] section; enemy attack parameters live
in a [node name="AttackBehavior"] section, so this small reader extracts one
named node's key/value block. Godot literals are parsed with tres._parse_value.
"""

from __future__ import annotations

import re

from brotato_coach.tres import _parse_value

_NODE_NAME_RE = re.compile(r'^\[node\s+.*\bname="([^"]+)"')


def parse_scene_node(text: str, node_name: str) -> dict[str, object]:
    result: dict[str, object] = {}
    in_target = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            if in_target:
                break  # a new section ends the target node
            m = _NODE_NAME_RE.match(stripped)
            in_target = bool(m and m.group(1) == node_name)
            continue
        if in_target and "=" in stripped:
            key, val = stripped.split("=", 1)
            result[key.strip()] = _parse_value(val.strip())
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_scene.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check brotato_coach/scene.py tests/test_scene.py
git add brotato_coach/scene.py tests/test_scene.py
git commit -m "feat(bestiary): .tscn named-node reader for enemy attack params"
```

---

## Task 2: Enemy discovery + builder

Enumerate enemy dirs (those with a `*_stats.tres`) and build one record per enemy: base stats, per-wave slopes, attack profile, ability tags.

**Files:**
- Modify: `brotato_coach/builders/discover.py` (add `find_enemy_dirs`)
- Create: `brotato_coach/builders/enemies.py`
- Test: `tests/test_build_discover.py` (add), `tests/test_build_enemies.py` (new)

**Interfaces:**
- Consumes: `brotato_coach.tres.parse_tres`, `brotato_coach.scene.parse_scene_node`, `brotato_coach.builders.localization.resolve_text`
- Produces:
  - `discover.find_enemy_dirs(extracted_root: str) -> list[dict]` — each `{enemy_id, name, folder, stats_path, scene_path (str|None)}`.
  - `enemies.build_enemy_record(stats_text: str, scene_text: str | None, *, enemy_id: str, name: str, tr: dict[str,str]|None=None) -> dict` — record with keys `id, name, display_name, base, per_wave, attack, abilities`.

- [ ] **Step 1: Write the failing test (builder)**

```python
# tests/test_build_enemies.py
from brotato_coach.builders.enemies import build_enemy_record

_BABY_STATS = '''[gd_resource type="Resource" load_steps=3 format=2]
[ext_resource path="res://entities/units/unit/stats.gd" type="Script" id=1]
[resource]
script = ExtResource( 1 )
health = 3
health_increase_each_wave = 2.0
speed = 250
speed_randomization = 50
damage = 1
damage_increase_each_wave = 0.6
attack_cd = 30.0
knockback_resistance = 0.0
armor = 0
armor_increase_each_wave = 0.0
'''

_SPITTER_SCENE = '''[gd_scene load_steps=2 format=2]
[ext_resource path="res://entities/units/enemies/attack_behaviors/shooting_attack_behavior.gd" type="Script" id=3]
[ext_resource path="res://projectiles/bullet_enemy/enemy_projectile.tscn" type="PackedScene" id=4]
[node name="AttackBehavior" parent="." index="7"]
projectile_scene = ExtResource( 4 )
damage = 1
damage_increase_each_wave = 0.75
number_projectiles = 1
'''

_BRUISER_SCENE = '''[gd_scene load_steps=2 format=2]
[ext_resource path="res://entities/units/enemies/attack_behaviors/charging_attack_behavior.gd" type="Script" id=3]
[node name="AttackBehavior" parent="." index="7"]
charge_speed = 700.0
'''


def test_contact_enemy_base_and_slopes():
    rec = build_enemy_record(_BABY_STATS, None, enemy_id="baby_alien", name="Baby Alien")
    assert rec["id"] == "baby_alien"
    assert rec["base"]["health"] == 3
    assert rec["base"]["speed"] == 250
    assert rec["base"]["speed_randomization"] == 50
    assert rec["per_wave"]["health"] == 2.0
    assert rec["per_wave"]["damage"] == 0.6
    assert rec["per_wave"]["armor"] == 0.0
    # no attack-behavior scene -> pure contact
    assert rec["attack"]["kind"] == "melee"
    assert rec["abilities"] == []


def test_ranged_enemy_attack_profile():
    rec = build_enemy_record(_BABY_STATS, _SPITTER_SCENE, enemy_id="spitter", name="Spitter")
    assert rec["attack"]["kind"] == "ranged"
    assert rec["attack"]["projectile_damage"] == 1
    assert rec["attack"]["projectile_dmg_per_wave"] == 0.75
    assert rec["attack"]["number_projectiles"] == 1


def test_charging_enemy_kind_and_ability():
    rec = build_enemy_record(_BABY_STATS, _BRUISER_SCENE, enemy_id="bruiser", name="Bruiser")
    assert rec["attack"]["kind"] == "charging"
    assert "charger" in rec["abilities"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_build_enemies.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'brotato_coach.builders.enemies'`

- [ ] **Step 3: Write minimal implementation**

```python
# brotato_coach/builders/enemies.py
from __future__ import annotations

from brotato_coach.builders.localization import resolve_text
from brotato_coach.scene import parse_scene_node
from brotato_coach.tres import parse_tres

# Attack-behavior script basename -> (attack kind, ability tag or None).
_BEHAVIOR_KIND = {
    "shooting_attack_behavior": ("ranged", None),
    "charging_attack_behavior": ("charging", "charger"),
    "spawning_attack_behavior": ("ranged", "spawner"),
}


def _num(d: dict, key: str, default: float = 0.0):
    v = d.get(key)
    return v if isinstance(v, (int, float)) else default


def _classify_attack(scene_text: str | None) -> tuple[str, list[str], dict]:
    """Return (kind, abilities, attack_params) from an enemy scene.

    kind/abilities derive from which *_attack_behavior.gd the scene references
    (available in ext_resources without a scene-node parse). Numeric params
    come from the AttackBehavior node. No behavior script -> pure contact melee.
    """
    if not scene_text:
        return "melee", [], {}
    doc = parse_tres(scene_text)
    kind, abilities = "melee", []
    for ext in doc.ext_resources.values():
        path = str(ext.get("path", ""))
        if path.endswith("_attack_behavior.gd"):
            base = path.rsplit("/", 1)[-1][: -len(".gd")]
            if base in _BEHAVIOR_KIND:
                k, ability = _BEHAVIOR_KIND[base]
                kind = k
                if ability:
                    abilities.append(ability)
    node = parse_scene_node(scene_text, "AttackBehavior")
    params: dict = {}
    if kind == "ranged":
        params = {
            "projectile_damage": _num(node, "damage"),
            "projectile_dmg_per_wave": _num(node, "damage_increase_each_wave"),
            "number_projectiles": int(_num(node, "number_projectiles", 1)),
        }
    return kind, abilities, params


def build_enemy_record(stats_text: str, scene_text: str | None, *, enemy_id: str,
                       name: str, tr: dict[str, str] | None = None) -> dict:
    s = parse_tres(stats_text).resource
    kind, abilities, attack_params = _classify_attack(scene_text)
    return {
        "id": enemy_id,
        "name": name,
        "display_name": resolve_text(tr, None, name),
        "base": {
            "health": _num(s, "health"),
            "speed": _num(s, "speed"),
            "speed_randomization": _num(s, "speed_randomization"),
            "damage": _num(s, "damage"),
            "armor": _num(s, "armor"),
            "attack_cd": _num(s, "attack_cd"),
            "knockback_resistance": _num(s, "knockback_resistance"),
        },
        "per_wave": {
            "health": _num(s, "health_increase_each_wave"),
            "damage": _num(s, "damage_increase_each_wave"),
            "armor": _num(s, "armor_increase_each_wave"),
        },
        "attack": {"kind": kind, **attack_params},
        "abilities": abilities,
    }
```

Note: `resolve_text(tr, None, name)` — confirm `resolve_text` returns the fallback `name` when the key is `None`. If its signature differs, pass the enemy's display key instead; enemies have no localized name key in stats, so falling back to `name` is correct.

- [ ] **Step 4: Run builder test**

Run: `uv run pytest tests/test_build_enemies.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Write the failing discovery test**

```python
# tests/test_build_discover.py  (append)
import os
from brotato_coach.builders import discover


def test_find_enemy_dirs(tmp_path):
    root = tmp_path
    d = root / "entities" / "units" / "enemies" / "baby_alien"
    d.mkdir(parents=True)
    (d / "baby_alien_stats.tres").write_text("[resource]\nhealth = 3\n", encoding="utf-8")
    (d / "baby_alien.tscn").write_text("[gd_scene]\n", encoding="utf-8")
    # a non-enemy sibling dir with no *_stats.tres must be skipped
    (root / "entities" / "units" / "enemies" / "attack_behaviors").mkdir()

    found = discover.find_enemy_dirs(str(root))
    assert len(found) == 1
    e = found[0]
    assert e["enemy_id"] == "baby_alien"
    assert e["name"] == "Baby Alien"
    assert os.path.basename(e["stats_path"]) == "baby_alien_stats.tres"
    assert os.path.basename(e["scene_path"]) == "baby_alien.tscn"
```

- [ ] **Step 6: Run discovery test to verify it fails**

Run: `uv run pytest tests/test_build_discover.py::test_find_enemy_dirs -v`
Expected: FAIL with `AttributeError: module 'brotato_coach.builders.discover' has no attribute 'find_enemy_dirs'`

- [ ] **Step 7: Implement `find_enemy_dirs`**

```python
# brotato_coach/builders/discover.py  (append; reuses existing _title, glob, os)
def find_enemy_dirs(extracted_root: str) -> list[dict]:
    results = []
    base = os.path.join(extracted_root, "entities", "units", "enemies")
    for d in sorted(glob.glob(os.path.join(base, "*"))):
        if not os.path.isdir(d):
            continue
        folder = os.path.basename(d)
        stats = glob.glob(os.path.join(d, "*_stats.tres"))
        if not stats:
            continue
        scene = os.path.join(d, f"{folder}.tscn")
        results.append({
            "enemy_id": folder,
            "name": _title(folder),
            "folder": folder,
            "stats_path": stats[0],
            "scene_path": scene if os.path.isfile(scene) else None,
        })
    return results
```

- [ ] **Step 8: Run discovery test to verify it passes**

Run: `uv run pytest tests/test_build_discover.py::test_find_enemy_dirs -v`
Expected: PASS

- [ ] **Step 9: Lint and commit**

```bash
uv run ruff check brotato_coach/builders/enemies.py brotato_coach/builders/discover.py tests/test_build_enemies.py tests/test_build_discover.py
git add brotato_coach/builders/enemies.py brotato_coach/builders/discover.py tests/test_build_enemies.py tests/test_build_discover.py
git commit -m "feat(bestiary): enemy discovery + record builder"
```

---

## Task 3: Wave discovery + builder (+ roster provenance)

Build one record per numbered zone_1 wave (1–20) by resolving each wave's `groups_data` → group `.tres` → unit `.tres` → enemy id. Also compute `appears_in` provenance from zone_1 data.

**Files:**
- Modify: `brotato_coach/builders/discover.py` (add `find_zone_waves`)
- Create: `brotato_coach/builders/waves.py`
- Test: `tests/test_build_waves.py` (new)

**Interfaces:**
- Consumes: `brotato_coach.tres.parse_tres`
- Produces:
  - `discover.find_zone_waves(extracted_root: str) -> list[dict]` — each `{wave: int, wave_path, group_paths: list[str], unit_paths_by_group: dict[str, list[str]]}` for waves 1–20 (excludes the "021 (test)" dir).
  - `waves.build_wave_record(wave_text, group_texts, unit_texts_by_group, *, wave: int) -> dict` — `{wave, wave_duration, max_enemies, groups: [...]}`.
  - `waves.enemy_id_from_unit_scene(scene_name: str) -> str` — `"baby_alien.tscn"` → `"baby_alien"`.

The unit `.tres` gives `unit_scene_name` (e.g. `"baby_alien.tscn"`) or a `unit_scene` ExtResource whose path basename is the scene file. Map that to the enemy folder id (basename without `.tscn`), which matches `find_enemy_dirs`' `enemy_id`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_build_waves.py
from brotato_coach.builders.waves import build_wave_record, enemy_id_from_unit_scene

_WAVE = '''[gd_resource type="Resource" load_steps=3 format=2]
[ext_resource path="res://zones/wave_data.gd" type="Script" id=1]
[ext_resource path="res://zones/zone_1/020/group_2.tres" type="Resource" id=4]
[resource]
script = ExtResource( 1 )
wave_duration = 90
max_enemies = 100
groups_data = [ ExtResource( 4 ) ]
conditional_groups_data = [  ]
'''

_GROUP = '''[gd_resource type="Resource" load_steps=3 format=2]
[ext_resource path="res://zones/wave_group_data.gd" type="Script" id=1]
[ext_resource path="res://zones/zone_1/020/unit_3.tres" type="Resource" id=2]
[resource]
script = ExtResource( 1 )
spawn_chance = 1.0
spawn_timing = 1
repeating = 5
repeating_interval = 3
area = -1
wave_units_data = [ ExtResource( 2 ) ]
is_boss = false
is_horde = false
is_loot = false
min_difficulty = 0
max_difficulty = 9999
'''

_UNIT = '''[gd_resource type="Resource" load_steps=3 format=2]
[ext_resource path="res://zones/wave_unit_data.gd" type="Script" id=1]
[ext_resource path="res://entities/units/enemies/baby_alien/baby_alien.tscn" type="PackedScene" id=2]
[resource]
script = ExtResource( 1 )
type = 1
unit_scene = ExtResource( 2 )
unit_scene_name = "baby_alien.tscn"
min_number = 5
max_number = 5
spawn_chance = 1.0
'''


def test_enemy_id_from_scene_name():
    assert enemy_id_from_unit_scene("baby_alien.tscn") == "baby_alien"


def test_wave_record_resolves_groups_units():
    rec = build_wave_record(_WAVE, [_GROUP], {"group_2.tres": [_UNIT]}, wave=20)
    assert rec["wave"] == 20
    assert rec["wave_duration"] == 90
    assert rec["max_enemies"] == 100
    assert len(rec["groups"]) == 1
    g = rec["groups"][0]
    assert g["enemy_id"] == "baby_alien"
    assert g["base_count"] == [5, 5]
    assert g["first_spawn_s"] == 1
    assert g["repeats"] == 5
    assert g["repeat_interval"] == 3
    assert g["min_danger"] == 0
    assert g["is_boss"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_build_waves.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'brotato_coach.builders.waves'`

- [ ] **Step 3: Write minimal implementation**

```python
# brotato_coach/builders/waves.py
from __future__ import annotations

import os

from brotato_coach.tres import parse_tres


def enemy_id_from_unit_scene(scene_name: str) -> str:
    return os.path.basename(scene_name).removesuffix(".tscn")


def _int(d: dict, key: str, default: int = 0) -> int:
    v = d.get(key)
    return int(v) if isinstance(v, (int, float)) else default


def _unit_enemy_id(unit_text: str) -> str:
    r = parse_tres(unit_text).resource
    name = r.get("unit_scene_name")
    if isinstance(name, str) and name:
        return enemy_id_from_unit_scene(name)
    # fall back to the unit_scene ExtResource path basename
    ref = r.get("unit_scene")
    if isinstance(ref, dict) and "__ext__" in ref:
        ext = parse_tres(unit_text).ext_resources.get(ref["__ext__"]) or {}
        return enemy_id_from_unit_scene(str(ext.get("path", "")))
    return ""


def _group_record(group_text: str, unit_texts: list[str]) -> list[dict]:
    g = parse_tres(group_text).resource
    common = {
        "first_spawn_s": _int(g, "spawn_timing", 1),
        "repeats": _int(g, "repeating", 0),
        "repeat_interval": _int(g, "repeating_interval", 0),
        "spawn_chance": g.get("spawn_chance", 1.0),
        "min_danger": _int(g, "min_difficulty", 0),
        "max_danger": _int(g, "max_difficulty", 9999),
        "is_horde": bool(g.get("is_horde", False)),
        "is_boss": bool(g.get("is_boss", False)),
        "is_loot": bool(g.get("is_loot", False)),
    }
    out = []
    for unit_text in unit_texts:
        u = parse_tres(unit_text).resource
        out.append({
            "enemy_id": _unit_enemy_id(unit_text),
            "base_count": [_int(u, "min_number", 1), _int(u, "max_number", 1)],
            **common,
        })
    return out


def build_wave_record(wave_text: str, group_texts: list[str],
                      unit_texts_by_group: dict[str, list[str]], *, wave: int) -> dict:
    w = parse_tres(wave_text).resource
    groups: list[dict] = []
    # group_texts are in wave order; map each to its units via the group's own
    # basename key in unit_texts_by_group when available, else positional.
    keys = list(unit_texts_by_group.keys())
    for i, gtext in enumerate(group_texts):
        units = unit_texts_by_group.get(keys[i]) if i < len(keys) else []
        groups.extend(_group_record(gtext, units or []))
    return {
        "wave": wave,
        "wave_duration": _int(w, "wave_duration", 60),
        "max_enemies": _int(w, "max_enemies", 100),
        "groups": groups,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_build_waves.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Write the failing discovery test**

```python
# tests/test_build_discover.py  (append)
def test_find_zone_waves_excludes_test_wave(tmp_path):
    z = tmp_path / "zones" / "zone_1"
    (z / "001").mkdir(parents=True)
    (z / "001" / "wave_1.tres").write_text(
        '[resource]\ngroups_data = [  ]\n', encoding="utf-8")
    test_dir = z / "021 (test)"
    test_dir.mkdir()
    (test_dir / "wave_21.tres").write_text(
        '[resource]\ngroups_data = [  ]\n', encoding="utf-8")

    waves = discover.find_zone_waves(str(tmp_path))
    assert [w["wave"] for w in waves] == [1]  # wave 21 (test) excluded
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/test_build_discover.py::test_find_zone_waves_excludes_test_wave -v`
Expected: FAIL with `AttributeError: ... has no attribute 'find_zone_waves'`

- [ ] **Step 7: Implement `find_zone_waves`**

`discover.py` currently imports only `glob` and `os` — add `import re` to the top of the module (verified: `re` is not yet imported there). `_res_url_to_path` already exists in the module; reuse it.

```python
# brotato_coach/builders/discover.py  — add to the top-of-file imports
import re

# brotato_coach/builders/discover.py  (append)
_WAVE_FILE_RE = re.compile(r"wave_(\d+)\.tres$")


def find_zone_waves(extracted_root: str) -> list[dict]:
    """Numbered zone_1 waves 1-20, resolving each wave's groups and their units.

    Excludes the "021 (test)" dir (wave number > 20). Each result carries the
    wave text path plus, per group, the group .tres path and its unit .tres
    paths, resolved through the ext_resource tables.
    """
    base = os.path.join(extracted_root, "zones", "zone_1")
    results = []
    for wave_path in sorted(glob.glob(os.path.join(base, "*", "wave_*.tres"))):
        m = _WAVE_FILE_RE.search(os.path.basename(wave_path))
        if not m:
            continue
        wave_no = int(m.group(1))
        if not (1 <= wave_no <= 20):
            continue
        wave_dir = os.path.dirname(wave_path)
        with open(wave_path, encoding="utf-8") as fh:
            wdoc = parse_tres(fh.read())
        group_paths, unit_paths_by_group = [], {}
        for entry in wdoc.resource.get("groups_data", []) or []:
            if not (isinstance(entry, dict) and "__ext__" in entry):
                continue
            gpath = _res_url_to_path(extracted_root,
                                     (wdoc.ext_resources.get(entry["__ext__"]) or {}).get("path"))
            if not (gpath and os.path.isfile(gpath)):
                continue
            group_paths.append(gpath)
            gkey = os.path.basename(gpath)
            with open(gpath, encoding="utf-8") as fh:
                gdoc = parse_tres(fh.read())
            units = []
            for uentry in gdoc.resource.get("wave_units_data", []) or []:
                if isinstance(uentry, dict) and "__ext__" in uentry:
                    upath = _res_url_to_path(
                        extracted_root,
                        (gdoc.ext_resources.get(uentry["__ext__"]) or {}).get("path"))
                    if upath and os.path.isfile(upath):
                        units.append(upath)
            unit_paths_by_group[gkey] = units
        results.append({
            "wave": wave_no, "wave_path": wave_path,
            "group_paths": group_paths, "unit_paths_by_group": unit_paths_by_group,
        })
    results.sort(key=lambda r: r["wave"])
    return results
```

Note: `_res_url_to_path` already exists in `discover.py`; reuse it. If `re` is already imported at the top of `discover.py`, drop the `import re as _re` alias and use `re`.

- [ ] **Step 8: Run test to verify it passes**

Run: `uv run pytest tests/test_build_discover.py::test_find_zone_waves_excludes_test_wave -v`
Expected: PASS

- [ ] **Step 9: Lint and commit**

```bash
uv run ruff check brotato_coach/builders/waves.py brotato_coach/builders/discover.py tests/test_build_waves.py tests/test_build_discover.py
git add brotato_coach/builders/waves.py brotato_coach/builders/discover.py tests/test_build_waves.py tests/test_build_discover.py
git commit -m "feat(bestiary): zone_1 wave discovery + record builder"
```

---

## Task 4: Dataset assembly, validation, schema v4

Thread the two arrays through `assemble_dataset`/`validate_dataset` and bump the schema version. Compute `appears_in: ["normal"]` for enemies referenced by any built wave (horde/elite/endless provenance is a documented follow-up; see spec boundaries).

**Files:**
- Modify: `brotato_coach/dataset.py`
- Test: `tests/test_dataset.py` (add)

**Interfaces:**
- Consumes: built `enemies` and `zone_1_waves` lists.
- Produces: `assemble_dataset(..., enemies: list, zone_1_waves: list)` includes both arrays and `schema_version == 4`; `validate_dataset` reports problems for missing/omitted arrays and dangling enemy references.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dataset.py  (append)
from brotato_coach import dataset


def _minimal(**over):
    base = dict(game_version="1.1.15.4", generated_at="x", weapons=[], items=[],
                characters=[], sets=[], enemies=[], zone_1_waves=[])
    base.update(over)
    return dataset.assemble_dataset(**base)


def test_schema_version_is_4():
    assert _minimal()["schema_version"] == 4


def test_enemies_and_waves_present_in_output():
    ds = _minimal(enemies=[{"id": "baby_alien", "name": "Baby Alien"}],
                  zone_1_waves=[{"wave": 1, "groups": [{"enemy_id": "baby_alien"}]}])
    assert ds["enemies"][0]["id"] == "baby_alien"
    assert ds["zone_1_waves"][0]["wave"] == 1
    assert dataset.validate_dataset(ds) == []


def test_validate_flags_dangling_enemy_reference():
    ds = _minimal(enemies=[{"id": "baby_alien", "name": "Baby Alien"}],
                  zone_1_waves=[{"wave": 1, "groups": [{"enemy_id": "ghost_unknown"}]}])
    problems = dataset.validate_dataset(ds)
    assert any("ghost_unknown" in p for p in problems)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dataset.py -k "schema_version_is_4 or enemies_and_waves or dangling" -v`
Expected: FAIL — `assemble_dataset() got an unexpected keyword argument 'enemies'`

- [ ] **Step 3: Implement dataset changes**

```python
# brotato_coach/dataset.py
DATASET_VERSION = 4  # was 3

def assemble_dataset(*, game_version: str, generated_at: str, weapons: list,
                     items: list, characters: list, sets: list,
                     enemies: list, zone_1_waves: list) -> dict:
    return {
        "schema_version": DATASET_VERSION,
        "game_version": game_version,
        "generated_at": generated_at,
        "stat_mechanics": STAT_MECHANICS,
        "weapons": weapons,
        "items": items,
        "characters": characters,
        "sets": sets,
        "enemies": enemies,
        "zone_1_waves": zone_1_waves,
    }
```

In `validate_dataset`, add `enemies` and `zone_1_waves` to the required top-level keys tuple, then append after the existing `sets` checks:

```python
    enemy_ids = {e.get("id") for e in dataset.get("enemies", [])}
    for e in dataset.get("enemies", []):
        if "id" not in e:
            problems.append(f"enemy missing id: {e.get('name', '<unknown>')}")
    for w in dataset.get("zone_1_waves", []):
        for g in w.get("groups", []):
            eid = g.get("enemy_id")
            if eid and eid not in enemy_ids:
                problems.append(
                    f"wave {w.get('wave', '?')} references unknown enemy '{eid}'")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_dataset.py -v`
Expected: PASS (all, including existing)

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check brotato_coach/dataset.py tests/test_dataset.py
git add brotato_coach/dataset.py tests/test_dataset.py
git commit -m "feat(bestiary): dataset schema v4 with enemies + zone_1_waves"
```

---

## Task 5: Wire into `build_dataset.py` and regenerate

Assemble enemy + wave records in the build and compute `appears_in`. Regenerate the local dataset and verify counts. (The regenerated `data/brotato.json` is gitignored — do NOT commit it.)

**Files:**
- Modify: `build_dataset.py`
- Test: manual regeneration + `tests/test_build_dataset_paths.py` if a pure helper is added (optional).

**Interfaces:**
- Consumes: `discover.find_enemy_dirs`, `discover.find_zone_waves`, `enemies.build_enemy_record`, `waves.build_wave_record`.
- Produces: `data/brotato.json` with populated `enemies` and `zone_1_waves`.

- [ ] **Step 1: Add build wiring**

```python
# build_dataset.py  — imports
from brotato_coach.builders.enemies import build_enemy_record
from brotato_coach.builders.waves import build_wave_record
```

```python
# build_dataset.py  — after `sets = [...]`, before assemble_dataset(...)
enemies = []
for e in discover.find_enemy_dirs(args.extracted):
    scene_text = _read(e["scene_path"]) if e.get("scene_path") else None
    enemies.append(build_enemy_record(
        _read(e["stats_path"]), scene_text,
        enemy_id=e["enemy_id"], name=e["name"], tr=tr))

zone_1_waves = []
enemy_ids_in_waves: set[str] = set()
for wv in discover.find_zone_waves(args.extracted):
    group_texts = [_read(p) for p in wv["group_paths"]]
    unit_texts_by_group = {
        gkey: [_read(p) for p in paths]
        for gkey, paths in wv["unit_paths_by_group"].items()
    }
    rec = build_wave_record(_read(wv["wave_path"]), group_texts,
                            unit_texts_by_group, wave=wv["wave"])
    for g in rec["groups"]:
        if g.get("enemy_id"):
            enemy_ids_in_waves.add(g["enemy_id"])
    zone_1_waves.append(rec)

# appears_in: "normal" for any enemy referenced by a numbered wave
for e in enemies:
    e["appears_in"] = ["normal"] if e["id"] in enemy_ids_in_waves else []
```

Update the `assemble_dataset(...)` call to pass `enemies=enemies, zone_1_waves=zone_1_waves`, and extend the final `print(...)` summary to include enemy/wave counts.

- [ ] **Step 2: Regenerate the dataset**

Run: `uv run python build_dataset.py`
Expected: prints a summary line including non-zero enemy and wave counts; exit 0 (no validation failures).

- [ ] **Step 3: Sanity-check the output (do not commit it)**

Run:
```bash
uv run python -c "import json; d=json.load(open('data/brotato.json')); print('schema', d['schema_version']); print('enemies', len(d['enemies'])); print('waves', [w['wave'] for w in d['zone_1_waves']]); print('baby_alien', next(e for e in d['enemies'] if e['id']=='baby_alien'))"
```
Expected: `schema 4`; enemies count > 30; waves `[1..20]`; baby_alien `per_wave.health == 2.0`, `base.health == 3`.

- [ ] **Step 4: Verify the full suite still passes**

Run: `uv run pytest -q`
Expected: PASS (existing + new). `tests/test_shipped_dataset.py:73` asserts `ds["schema_version"] == 3` — update it to `== 4` (and the comment on line 72) as part of this task.

- [ ] **Step 5: Commit (code only — dataset is gitignored)**

```bash
git add build_dataset.py tests/test_shipped_dataset.py
git commit -m "feat(bestiary): build enemies + zone_1 waves into the dataset"
```

---

## Task 6: Pure logic — effective stats, `get_enemy`, `list_enemies`

**Files:**
- Create: `brotato_coach/bestiary.py`
- Test: `tests/test_bestiary.py` (new)

**Interfaces:**
- Consumes: dataset dict with `enemies`, `zone_1_waves`; `brotato_coach.query.suggest`.
- Produces:
  - `effective_stats(enemy: dict, wave: int) -> dict` — `{health, damage, armor, speed_range: [lo, hi]}`.
  - `get_enemy(ds: dict, name: str, wave: int | None = None) -> dict`.
  - `list_enemies(ds: dict, *, appears_in=None, ability=None, attack_kind=None) -> list[dict]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bestiary.py
from brotato_coach import bestiary

_DS = {
    "enemies": [
        {"id": "baby_alien", "name": "Baby Alien", "display_name": "Baby Alien",
         "base": {"health": 3, "speed": 250, "speed_randomization": 50,
                  "damage": 1, "armor": 0, "attack_cd": 30.0,
                  "knockback_resistance": 0.0},
         "per_wave": {"health": 2.0, "damage": 0.6, "armor": 0.0},
         "attack": {"kind": "melee"}, "abilities": [], "appears_in": ["normal"]},
        {"id": "spitter", "name": "Spitter", "display_name": "Spitter",
         "base": {"health": 10, "speed": 200, "speed_randomization": 0,
                  "damage": 2, "armor": 0, "attack_cd": 60.0,
                  "knockback_resistance": 0.0},
         "per_wave": {"health": 4.0, "damage": 0.0, "armor": 0.0},
         "attack": {"kind": "ranged", "projectile_damage": 1,
                    "projectile_dmg_per_wave": 0.75, "number_projectiles": 1},
         "abilities": [], "appears_in": ["normal"]},
    ],
    "zone_1_waves": [],
}


def test_effective_stats_scale_with_wave():
    eff = bestiary.effective_stats(_DS["enemies"][0], wave=20)
    assert eff["health"] == 3 + 2.0 * 19   # 41
    assert eff["damage"] == 1 + 0.6 * 19   # 12.4
    assert eff["speed_range"] == [200, 300]  # 250 +/- 50


def test_get_enemy_without_wave_has_base_and_slopes():
    r = bestiary.get_enemy(_DS, "Baby Alien")
    assert r["base"]["health"] == 3
    assert r["per_wave"]["health"] == 2.0
    assert "effective" not in r


def test_get_enemy_with_wave_adds_effective():
    r = bestiary.get_enemy(_DS, "baby_alien", wave=20)
    assert r["effective"]["health"] == 41


def test_get_enemy_miss_suggests():
    r = bestiary.get_enemy(_DS, "baby alein")
    assert r["error"] == "not_found"
    assert "Baby Alien" in r["did_you_mean"]


def test_list_enemies_filters_by_attack_kind():
    out = bestiary.list_enemies(_DS, attack_kind="ranged")
    assert [e["id"] for e in out] == ["spitter"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_bestiary.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'brotato_coach.bestiary'`

- [ ] **Step 3: Write minimal implementation**

```python
# brotato_coach/bestiary.py
"""Pure logic over the bestiary dataset arrays. No I/O.

Effective per-wave stats use base + increase_each_wave * (wave - 1), matching
the game's (current_wave - 1) scaling. Movement speed is a range because the
game rolls speed +/- speed_randomization per spawn.
"""

from __future__ import annotations

from brotato_coach import query


def effective_stats(enemy: dict, wave: int) -> dict:
    base, slope = enemy["base"], enemy["per_wave"]
    n = wave - 1
    spd, rnd = base.get("speed", 0), base.get("speed_randomization", 0)
    return {
        "health": base.get("health", 0) + slope.get("health", 0) * n,
        "damage": base.get("damage", 0) + slope.get("damage", 0) * n,
        "armor": base.get("armor", 0) + slope.get("armor", 0) * n,
        "speed_range": [spd - rnd, spd + rnd],
    }


def _match(enemies: list[dict], name: str) -> dict | None:
    low = name.lower()
    for e in enemies:
        if low in (e.get("id", "").lower(), e.get("name", "").lower(),
                   e.get("display_name", "").lower()):
            return e
    return None


def get_enemy(ds: dict, name: str, wave: int | None = None) -> dict:
    enemies = ds.get("enemies", [])
    enemy = _match(enemies, name)
    if enemy is None:
        return {"error": "not_found", "did_you_mean": query.suggest(enemies, name)}
    if wave is None:
        return enemy
    return {**enemy, "effective": effective_stats(enemy, wave)}


def list_enemies(ds: dict, *, appears_in=None, ability=None, attack_kind=None) -> list[dict]:
    out = []
    for e in ds.get("enemies", []):
        if appears_in is not None and appears_in not in e.get("appears_in", []):
            continue
        if ability is not None and ability not in e.get("abilities", []):
            continue
        if attack_kind is not None and e.get("attack", {}).get("kind") != attack_kind:
            continue
        out.append({"id": e["id"], "name": e["name"],
                    "attack_kind": e.get("attack", {}).get("kind"),
                    "appears_in": e.get("appears_in", [])})
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_bestiary.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check brotato_coach/bestiary.py tests/test_bestiary.py
git add brotato_coach/bestiary.py tests/test_bestiary.py
git commit -m "feat(bestiary): effective-stat math + get_enemy/list_enemies"
```

---

## Task 7: Pure logic — `wave_composition` + `wave_context`

**Files:**
- Modify: `brotato_coach/bestiary.py`
- Test: `tests/test_bestiary.py` (add)

**Interfaces:**
- Consumes: dataset dict; `effective_stats`.
- Produces:
  - `wave_composition(ds, wave: int, danger: int | None = None) -> dict` — `{wave, wave_duration, max_enemies, base_enemies: [...], scales_with, elite_horde, notes}`. When `danger` is set, drop groups whose `[min_danger, max_danger]` excludes it.
  - `wave_context(ds, wave: int, danger: int | None = None) -> dict` — `{death_wave, composition, newly_introduced, effective_threat, elite_horde_note}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bestiary.py  (append)
_DS_WAVES = {
    "enemies": _DS["enemies"],
    "zone_1_waves": [
        {"wave": 12, "wave_duration": 60, "max_enemies": 100, "groups": [
            {"enemy_id": "baby_alien", "base_count": [5, 5], "first_spawn_s": 1,
             "repeats": 5, "repeat_interval": 3, "spawn_chance": 1.0,
             "min_danger": 0, "max_danger": 9999, "is_horde": False,
             "is_boss": False, "is_loot": False},
            {"enemy_id": "spitter", "base_count": [1, 2], "first_spawn_s": 5,
             "repeats": 999, "repeat_interval": 15, "spawn_chance": 1.0,
             "min_danger": 6, "max_danger": 9999, "is_horde": False,
             "is_boss": False, "is_loot": False},
        ]},
    ],
}


def test_wave_composition_danger_gates_groups():
    at0 = bestiary.wave_composition(_DS_WAVES, 12, danger=0)
    ids0 = [g["enemy_id"] for g in at0["base_enemies"]]
    assert ids0 == ["baby_alien"]           # spitter group is d6-only

    at6 = bestiary.wave_composition(_DS_WAVES, 12, danger=6)
    ids6 = [g["enemy_id"] for g in at6["base_enemies"]]
    assert set(ids6) == {"baby_alien", "spitter"}


def test_wave_composition_labels_run_variance():
    comp = bestiary.wave_composition(_DS_WAVES, 12)
    assert "number_of_enemies" in " ".join(comp["scales_with"])
    assert "per-run" in comp["elite_horde"].lower()


def test_wave_context_has_effective_threat_at_wave():
    ctx = bestiary.wave_context(_DS_WAVES, 12, danger=0)
    assert ctx["death_wave"] == 12
    threat = {t["enemy_id"]: t for t in ctx["effective_threat"]}
    # baby_alien effective HP at wave 12 = 3 + 2*11 = 25
    assert threat["baby_alien"]["health"] == 25
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_bestiary.py -k "danger_gates or run_variance or effective_threat" -v`
Expected: FAIL with `AttributeError: module 'brotato_coach.bestiary' has no attribute 'wave_composition'`

- [ ] **Step 3: Write minimal implementation**

```python
# brotato_coach/bestiary.py  (append)
_SCALES_WITH = ["number_of_enemies % (item/character modifier)",
                "co-op player count"]
_ELITE_HORDE_LABEL = ("elite/horde waves are scheduled per-run (randomized at "
                      "run start) — treat as possible on this wave, not guaranteed")


def _wave_record(ds: dict, wave: int) -> dict | None:
    for w in ds.get("zone_1_waves", []):
        if w.get("wave") == wave:
            return w
    return None


def wave_composition(ds: dict, wave: int, danger: int | None = None) -> dict:
    w = _wave_record(ds, wave)
    if w is None:
        return {"error": "not_found", "detail": f"no base-game wave {wave} (valid 1-20)"}
    groups = []
    for g in w.get("groups", []):
        if danger is not None and not (g["min_danger"] <= danger <= g["max_danger"]):
            continue
        groups.append(g)
    return {
        "wave": wave,
        "wave_duration": w.get("wave_duration"),
        "max_enemies": w.get("max_enemies"),
        "base_enemies": groups,
        "scales_with": _SCALES_WITH,
        "elite_horde": _ELITE_HORDE_LABEL,
        "notes": ["base_count and repeats are pre-modifier base values"],
    }


def wave_context(ds: dict, wave: int, danger: int | None = None) -> dict:
    comp = wave_composition(ds, wave, danger)
    if comp.get("error"):
        return comp
    by_id = {e["id"]: e for e in ds.get("enemies", [])}
    present_ids = [g["enemy_id"] for g in comp["base_enemies"]]

    # enemies first seen in the ~3 waves ending at `wave`
    recent = set()
    earlier = set()
    for w in ds.get("zone_1_waves", []):
        ids = {g["enemy_id"] for g in w.get("groups", [])}
        if w["wave"] < wave - 2:
            earlier |= ids
        elif w["wave"] <= wave:
            recent |= ids
    newly_introduced = sorted(recent - earlier)

    effective_threat = []
    for eid in dict.fromkeys(present_ids):  # de-dup, preserve order
        e = by_id.get(eid)
        if e is None:
            continue
        eff = effective_stats(e, wave)
        effective_threat.append({
            "enemy_id": eid,
            "attack_kind": e.get("attack", {}).get("kind"),
            "health": eff["health"],
            "damage": eff["damage"],
        })
    return {
        "death_wave": wave,
        "composition": comp,
        "newly_introduced": newly_introduced,
        "effective_threat": effective_threat,
        "elite_horde_note": (
            f"wave {wave} can roll an elite/horde (per-run, randomized); "
            "if you hit a wall here, that may be why"),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_bestiary.py -v`
Expected: PASS (all bestiary tests)

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check brotato_coach/bestiary.py tests/test_bestiary.py
git add brotato_coach/bestiary.py tests/test_bestiary.py
git commit -m "feat(bestiary): wave_composition + wave_context with danger gating"
```

---

## Task 8: MCP tools + `get_filter_options` extension

**Files:**
- Modify: `brotato_coach/server.py`
- Test: `tests/test_server.py` (add)

**Interfaces:**
- Consumes: `brotato_coach.bestiary`.
- Produces: MCP tools `get_enemy`, `list_enemies`, `wave_composition`; `get_filter_options` gains `enemy_abilities`, `attack_kinds`, `enemy_appears_in`.

- [ ] **Step 1: Write the failing test**

`test_server.py` builds a server from a dataset and calls tools. Follow the existing pattern in that file (inspect how current tests invoke tools — via the underlying `query`/`answers`/`bestiary` functions or the FastMCP tool objects). Add:

```python
# tests/test_server.py  (append; mirror the existing dataset fixture/style)
from brotato_coach import bestiary

def test_get_enemy_tool_returns_record():
    ds = {"enemies": [{"id": "baby_alien", "name": "Baby Alien",
                       "display_name": "Baby Alien",
                       "base": {"health": 3, "speed": 250, "speed_randomization": 50,
                                "damage": 1, "armor": 0, "attack_cd": 30.0,
                                "knockback_resistance": 0.0},
                       "per_wave": {"health": 2.0, "damage": 0.6, "armor": 0.0},
                       "attack": {"kind": "melee"}, "abilities": [],
                       "appears_in": ["normal"]}],
          "zone_1_waves": []}
    assert bestiary.get_enemy(ds, "Baby Alien", wave=20)["effective"]["health"] == 41
```

(If `test_server.py` exercises the actual FastMCP tool callables, add an equivalent that calls the registered `get_enemy` tool and asserts the same. Match the file's established approach rather than introducing a new one.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_server.py -k get_enemy_tool -v`
Expected: FAIL (import or assertion) until the tool exists / import added.

- [ ] **Step 3: Add the tools to `build_server`**

```python
# brotato_coach/server.py  — import
from brotato_coach import answers, bestiary, dataset, evaluate, orientation, query, runfile
```

```python
# brotato_coach/server.py  — inside build_server, alongside the other @mcp.tool()s
    @mcp.tool()
    def get_enemy(name: str, wave: int | None = None) -> dict[str, Any]:
        """Look up one enemy's record: base stats, per-wave stat slopes, attack
        profile, and ability tags.

        Enemy HP/damage/armor scale with the wave. Omit `wave` for base stats +
        slopes; pass `wave` (1-20) to also get `effective` stats resolved at that
        wave (speed is returned as a min-max range). On a miss: not_found +
        did_you_mean. Base-game (Crash Zone) roster.
        """
        return _safe(bestiary.get_enemy)(ds=ds, name=name, wave=wave)

    @mcp.tool()
    def list_enemies(appears_in: str | None = None, ability: str | None = None,
                     attack_kind: str | None = None) -> dict[str, Any]:
        """List enemy summaries, optionally filtered by `appears_in`
        (e.g. 'normal'), `ability` (e.g. 'charger', 'spawner'), or `attack_kind`
        ('melee', 'ranged', 'charging'). Call get_filter_options for valid
        values."""
        return _safe(lambda **kw: {"enemies": bestiary.list_enemies(ds, **kw)})(
            appears_in=appears_in, ability=ability, attack_kind=attack_kind)

    @mcp.tool()
    def wave_composition(wave: int, danger: int | None = None) -> dict[str, Any]:
        """Base-game composition for a Crash Zone wave (1-20): the enemy groups
        that spawn, their base counts, first-spawn timing, and repeats.

        `base_enemies` counts are pre-modifier base values; `scales_with` lists
        the run modifiers that change realized counts; `elite_horde` is labelled
        as per-run randomized (never guaranteed). Pass `danger` (displayed Danger
        number) to filter to the groups that danger tier admits.
        """
        return _safe(bestiary.wave_composition)(ds=ds, wave=wave, danger=danger)
```

Extend `get_filter_options`' `_compute()` return dict with:

```python
                "enemy_abilities": _uniq(a for e in ds.get("enemies", [])
                                         for a in e.get("abilities", [])),
                "attack_kinds": _uniq(e.get("attack", {}).get("kind")
                                      for e in ds.get("enemies", [])),
                "enemy_appears_in": _uniq(a for e in ds.get("enemies", [])
                                          for a in e.get("appears_in", [])),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_server.py -v`
Expected: PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check brotato_coach/server.py tests/test_server.py
git add brotato_coach/server.py tests/test_server.py
git commit -m "feat(bestiary): get_enemy/list_enemies/wave_composition MCP tools"
```

---

## Task 9: `evaluate_run` wave_context integration

**Files:**
- Modify: `brotato_coach/answers.py`
- Test: `tests/test_run_report.py` (add)

**Interfaces:**
- Consumes: `brotato_coach.bestiary.wave_context`; run context `ctx = build["context"]` with keys `wave`, `danger`.
- Produces: `evaluate_run(...)` output gains a `wave_context` key when `ctx["wave"]` is a base-game wave (1-20); otherwise the key is present with a short skip note (e.g. endless / unknown wave).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_run_report.py  (append; reuse the file's existing dataset + run fixtures)
def test_evaluate_run_includes_wave_context(coach_dataset, sample_run_wave12):
    # coach_dataset must contain enemies + a zone_1 wave 12; sample_run_wave12
    # is a run save with current_wave=12, current_difficulty=0.
    from brotato_coach import answers
    out = answers.evaluate_run(coach_dataset, sample_run_wave12)
    wc = out["wave_context"]
    assert wc["death_wave"] == 12
    assert "per-run" in wc["elite_horde_note"].lower()
    assert isinstance(wc["effective_threat"], list)
```

If the test file has no fixture with enemies/waves, add a minimal one in the test (a dataset dict with one wave-12 record and the referenced enemies, plus a run dict shaped like `runfile.parse_run` expects — check `tests/test_runfile.py` for the run JSON shape).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_run_report.py -k wave_context -v`
Expected: FAIL with `KeyError: 'wave_context'`

- [ ] **Step 3: Implement the integration**

```python
# brotato_coach/answers.py  — import
from brotato_coach import bestiary
```

```python
# brotato_coach/answers.py  — in evaluate_run, build the section before `return`
    wave_no = ctx.get("wave")
    if isinstance(wave_no, int) and any(
            w.get("wave") == wave_no for w in ds.get("zone_1_waves", [])):
        wave_ctx = bestiary.wave_context(ds, wave_no, ctx.get("danger"))
    else:
        wave_ctx = {"death_wave": wave_no,
                    "note": "no base-game wave data for this wave "
                            "(endless, or wave outside 1-20)"}
```

Add `"wave_context": wave_ctx,` to the returned dict.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_run_report.py -v`
Expected: PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check brotato_coach/answers.py tests/test_run_report.py
git add brotato_coach/answers.py tests/test_run_report.py
git commit -m "feat(bestiary): fold wave_context into evaluate_run post-mortem"
```

---

## Task 10: Orientation `read_me` bestiary section

**Files:**
- Modify: `brotato_coach/orientation.py`
- Test: `tests/test_orientation.py` (add)

**Interfaces:**
- Consumes: `orientation.read_me_payload(ds=...)` (existing).
- Produces: the payload includes a bestiary section describing per-wave scaling and the honesty envelope.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_orientation.py  (append; match the file's existing call style)
def test_read_me_mentions_bestiary_scaling():
    from brotato_coach import orientation
    payload = orientation.read_me_payload(ds={"enemies": [], "zone_1_waves": [],
                                              "game_version": "1.1.15.4",
                                              "generated_at": "x",
                                              "schema_version": 4})
    blob = str(payload).lower()
    assert "wave" in blob and "increase_each_wave" in blob or "per-wave" in blob
    assert "randomized" in blob  # honesty envelope for elite/horde
```

Inspect `orientation.read_me_payload`'s actual return shape first and assert against the specific field it uses for prose sections (match existing tests in this file rather than stringifying if a cleaner assertion exists).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_orientation.py -k bestiary -v`
Expected: FAIL (assertion — no bestiary prose yet)

- [ ] **Step 3: Add the section**

Add a short bestiary entry to the prose/sections `read_me_payload` returns. Content (adapt to the module's existing structure — a dict key, a list entry, or appended string):

```
Bestiary: enemy HP/damage/armor scale with the wave as
base + increase_each_wave * (wave - 1); movement speed is a range
(speed +/- speed_randomization). wave_composition gives the exact base-game
(Crash Zone) composition for waves 1-20; realized counts scale with run
modifiers (number_of_enemies %, co-op) and elite/horde waves are scheduled
per-run (randomized) — never report them as guaranteed.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_orientation.py -v`
Expected: PASS

- [ ] **Step 5: Full suite + lint, then commit**

Run: `uv run pytest -q && uv run ruff check .`
Expected: PASS, clean.

```bash
git add brotato_coach/orientation.py tests/test_orientation.py
git commit -m "docs(bestiary): read_me section on per-wave scaling + honesty envelope"
```

---

## Self-Review

**Spec coverage:**
- `enemies[]` array → Tasks 2, 4, 5. ✓
- `zone_1_waves[]` array → Tasks 3, 4, 5. ✓
- Schema v4 → Task 4. ✓
- Per-wave effective-stat math → Task 6. ✓
- Attack profile from `.tscn` (kind + numeric params) → Tasks 1, 2. ✓
- Danger gating (1:1 danger↔difficulty) → Task 7. ✓
- `get_enemy` / `list_enemies` / `wave_composition` tools → Task 8. ✓
- `get_filter_options` extension → Task 8. ✓
- `wave_context` in post-mortem → Tasks 7, 9. ✓
- `read_me` bestiary section → Task 10. ✓
- Honesty envelope (labelled run-variance, per-run elites) → Tasks 7, 10. ✓
- **Deviations, documented:** `zone_id` omitted (Global Constraints); `appears_in` first cut is `["normal"]` only, with horde/elite/endless/boss provenance deferred (Task 4 note + spec boundaries). Bosses carry a `bespoke_kit_not_modeled` tag — enforced by the `_BEHAVIOR_KIND` map leaving unrecognized behaviors as `melee`/empty; add the explicit boss tag when boss discovery lands (out of first-cut scope).

**Placeholder scan:** No TBD/TODO. Two steps say "match the file's existing style" for `test_server.py`, `test_run_report.py`, `test_orientation.py` — these are real existing files whose fixture conventions the implementer must follow; the assertion content is fully specified.

**Type consistency:** `enemy_id` used consistently (discover → waves → dataset validation → wave records). `effective_stats` returns `speed_range` (list) — consumed only for display, not re-computed. `wave_composition` returns `base_enemies` (list of group dicts) — `wave_context` reads `g["enemy_id"]` from them, matching the group record shape from Task 3. `per_wave`/`base` nested dicts consistent across Tasks 2, 6, 7.

**Verified against the codebase while writing this plan:**
- `resolve_text(tr, None, name)` returns `name` (key is non-str → fallback). Task 2 code is correct as written.
- `discover.py` does not import `re`; Task 3 adds it. `_res_url_to_path` exists and is reused.
- `test_shipped_dataset.py:73` asserts `schema_version == 3`; Task 5 bumps it to 4.

**Open verification for the implementer (cheap, do at the top of the relevant task):**
- Tasks 8–10: match each test file's existing fixture/invocation style (the assertion content is specified; only the harness idiom needs matching).
