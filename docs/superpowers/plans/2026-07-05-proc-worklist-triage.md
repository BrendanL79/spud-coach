# Proc-worklist triage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Triage every remaining unmodeled weapon-effect key: add the `companion_ranged_stats` DPS model (lightning + projectile-spray procs), classify all non-DPS effects into a category system with structured metadata, and shrink `unmodeled_effects` to genuinely-uninvestigated keys only (empty for the shipped dataset).

**Architecture:** Generalize burn's companion-file plumbing (`burning_data`) to N companion fields (`weapon_stats`, `stats`); add one new `damage_source` branch to the proc loop backed by pure `calc.companion_dps_line`; add a new `classifications.py` whose `classify_effect()` is mechanism-based (script basename + `storage_method` + key), feeding a new `classified_effects` weapon-record field. Design + evidence: `docs/superpowers/specs/2026-07-05-proc-worklist-triage-design.md` and the seven dossiers under `docs/superpowers/research/`.

**Tech Stack:** Python 3.11+, `uv`, `pytest`. No new dependencies.

## Global Constraints

- TDD is the norm: write the failing test first (`CLAUDE.md`).
- Run tests with `uv run pytest`.
- Evidence citations must be re-pinned against `recovered/`/`extracted/` at write time — every citation in this plan was re-verified during synthesis (see the spec).
- `data/brotato.json` is gitignored and must never be committed; end-to-end effects are only visible by running `build_dataset.py` locally.
- Baseline before Task 1: `uv run pytest -q` → 139 passed, 1 skipped.

---

### Task 1: `calc.companion_dps_line`

**Files:**
- Modify: `brotato_coach/calc.py` (append after `burn_dps_line`, which ends at line 57)
- Test: `tests/test_calc.py` (append)

**Interfaces:**
- Produces: `calc.companion_dps_line(damage: float, rd_coef: float, host_cycle_time: float, count: float, enemies_hit: float) -> tuple[float, float]` — returns `(dps0, slope)`. Used by Task 5.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_calc.py`:

```python
def test_companion_dps_line_lightning_shiv_t1_golden():
    # companion damage 5, elemental scaling (rd_coef 0), host cycle 0.65s,
    # 1 spawn, chain of 1 (bounce 0)
    dps0, slope = calc.companion_dps_line(5.0, 0.0, 0.65, 1.0, 1.0)
    assert math.isclose(dps0, 7.6923, rel_tol=1e-4)
    assert slope == 0.0


def test_companion_dps_line_cactus_mace_t1_golden():
    # companion damage 1, stat_ranged_damage 0.6, host cycle 1.25s,
    # 3 spawns per hit, spray assumption 1.0
    dps0, slope = calc.companion_dps_line(1.0, 0.6, 1.25, 3.0, 1.0)
    assert math.isclose(dps0, 2.4)
    assert math.isclose(slope, 1.44)


def test_companion_dps_line_zero_count_is_zero():
    dps0, slope = calc.companion_dps_line(10.0, 1.0, 1.0, 0.0, 1.0)
    assert dps0 == 0.0 and slope == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_calc.py -k companion_dps_line -v`
Expected: FAIL with `AttributeError: module 'brotato_coach.calc' has no attribute 'companion_dps_line'`

- [ ] **Step 3: Implement**

Append to `brotato_coach/calc.py` after `burn_dps_line`:

```python


def companion_dps_line(damage: float, rd_coef: float, host_cycle_time: float,
                       count: float, enemies_hit: float) -> tuple[float, float]:
    """Expected DPS line from a spawn-projectiles-on-hit proc.

    Each landed host hit unconditionally spawns `count` projectiles whose
    damage line lives on a companion RangedWeaponStats resource, independent
    of the host weapon's own damage (see docs/proc-mechanics.md,
    "Companion-projectile procs"). `enemies_hit` is the assumed expected hits
    per volley/chain — an assumption constant, like proc_line's enemies_hit.
    """
    f = count * enemies_hit / host_cycle_time
    return (damage * f, rd_coef * f)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_calc.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/calc.py tests/test_calc.py
git commit -m "feat(calc): add companion_dps_line for spawn-projectile procs"
```

---

### Task 2: `discover.py` — generalize companion resolution

**Files:**
- Modify: `brotato_coach/builders/discover.py` (replace `_resolve_effect_burning_data`, lines 48-66, and its use in `find_weapon_dirs`, lines 86 and 94)
- Test: `tests/test_build_discover.py` (rewrite the three `burning_data` tests, append two new)

**Interfaces:**
- Produces: `discover._resolve_effect_companions(extracted_root: str, effect_paths: list[str]) -> dict[str, dict[str, str]]` — effect path → `{field_name: companion_path}` for `field_name` in `("burning_data", "weapon_stats", "stats")`; effects with no companion are omitted.
- `find_weapon_dirs` entries: the `"effect_burning_data_paths"` key is REPLACED by `"effect_companion_paths": dict[str, dict[str, str]]`. Task 4 consumes it; the burn behavior is preserved because `burning_data` is one of the scanned fields.

- [ ] **Step 1: Rewrite/append the tests**

In `tests/test_build_discover.py`, the three existing tests from the burn round reference `_resolve_effect_burning_data` and `effect_burning_data_paths`:
`test_resolve_effect_burning_data_finds_companion_resource`,
`test_resolve_effect_burning_data_skips_effects_without_one`,
`test_find_weapon_dirs_includes_burning_data_paths`.
Rewrite them (same fixtures, new function/keys) and add a `weapon_stats` case and a `stats` case:

```python
def test_resolve_effect_companions_finds_burning_data(tmp_path):
    from brotato_coach.builders import discover
    wdir = tmp_path / "weapons" / "melee" / "torch" / "1"
    wdir.mkdir(parents=True)
    effect_path = wdir / "torch_effect_1.tres"
    effect_path.write_text(
        '[gd_resource type="Resource" format=2]\n'
        '[ext_resource path="res://effects/weapons/burning_effect.gd" type="Script" id=1]\n'
        '[ext_resource path="res://weapons/melee/torch/1/torch_burning_data.tres" type="Resource" id=2]\n'
        '[resource]\nscript = ExtResource( 1 )\nkey = "effect_burning"\n'
        'burning_data = ExtResource( 2 )\n', encoding="utf-8")
    (wdir / "torch_burning_data.tres").write_text(
        '[gd_resource type="Resource" format=2]\n[resource]\n'
        'chance = 1.0\ndamage = 3\nduration = 3\n', encoding="utf-8")

    result = discover._resolve_effect_companions(str(tmp_path), [str(effect_path)])
    assert list(result.keys()) == [str(effect_path)]
    assert result[str(effect_path)]["burning_data"].endswith("torch_burning_data.tres")


def test_resolve_effect_companions_finds_weapon_stats(tmp_path):
    from brotato_coach.builders import discover
    wdir = tmp_path / "weapons" / "melee" / "lightning_shiv" / "1"
    wdir.mkdir(parents=True)
    effect_path = wdir / "lightning_shiv_effect_1.tres"
    effect_path.write_text(
        '[gd_resource type="Resource" format=2]\n'
        '[ext_resource path="res://effects/weapons/projectiles_on_hit_effect.gd" type="Script" id=1]\n'
        '[ext_resource path="res://weapons/melee/lightning_shiv/1/lightning_shiv_projectile.tres" type="Resource" id=2]\n'
        '[resource]\nscript = ExtResource( 1 )\nkey = "effect_lightning_on_hit"\n'
        'value = 1\nweapon_stats = ExtResource( 2 )\nauto_target_enemy = true\n',
        encoding="utf-8")
    (wdir / "lightning_shiv_projectile.tres").write_text(
        '[gd_resource type="Resource" format=2]\n[resource]\ndamage = 5\n',
        encoding="utf-8")

    result = discover._resolve_effect_companions(str(tmp_path), [str(effect_path)])
    assert result[str(effect_path)]["weapon_stats"].endswith("lightning_shiv_projectile.tres")


def test_resolve_effect_companions_finds_structure_stats_outside_weapon_dir(tmp_path):
    from brotato_coach.builders import discover
    wdir = tmp_path / "weapons" / "melee" / "screwdriver" / "1"
    wdir.mkdir(parents=True)
    mines = tmp_path / "items" / "all" / "landmines"
    mines.mkdir(parents=True)
    (mines / "landmine_stats.tres").write_text(
        '[gd_resource type="Resource" format=2]\n[resource]\ndamage = 10\n',
        encoding="utf-8")
    effect_path = wdir / "screwdriver_effect.tres"
    effect_path.write_text(
        '[gd_resource type="Resource" format=2]\n'
        '[ext_resource path="res://effects/items/structure_effect.gd" type="Script" id=1]\n'
        '[ext_resource path="res://items/all/landmines/landmine_stats.tres" type="Resource" id=3]\n'
        '[resource]\nscript = ExtResource( 1 )\nkey = ""\nvalue = 1\n'
        'spawn_cooldown = 12\nstats = ExtResource( 3 )\n', encoding="utf-8")

    result = discover._resolve_effect_companions(str(tmp_path), [str(effect_path)])
    assert result[str(effect_path)]["stats"].endswith("landmine_stats.tres")


def test_resolve_effect_companions_skips_effects_without_any(tmp_path):
    from brotato_coach.builders import discover
    wdir = tmp_path / "weapons" / "ranged" / "shredder" / "1"
    wdir.mkdir(parents=True)
    effect_path = wdir / "shredder_effect.tres"
    effect_path.write_text(
        '[gd_resource type="Resource" format=2]\n[resource]\n'
        'key = "effect_explode_custom"\nchance = 0.5\n', encoding="utf-8")

    result = discover._resolve_effect_companions(str(tmp_path), [str(effect_path)])
    assert result == {}


def test_find_weapon_dirs_includes_companion_paths(tmp_path):
    from brotato_coach.builders.discover import find_weapon_dirs
    wdir = tmp_path / "weapons" / "melee" / "torch" / "1"
    wdir.mkdir(parents=True)
    (wdir / "torch_stats.tres").write_text("stats")
    effect_path = wdir / "torch_effect_1.tres"
    effect_path.write_text(
        '[gd_resource type="Resource" format=2]\n'
        '[ext_resource path="res://effects/weapons/burning_effect.gd" type="Script" id=1]\n'
        '[ext_resource path="res://weapons/melee/torch/1/torch_burning_data.tres" type="Resource" id=2]\n'
        '[resource]\nscript = ExtResource( 1 )\nkey = "effect_burning"\n'
        'burning_data = ExtResource( 2 )\n', encoding="utf-8")
    (wdir / "torch_burning_data.tres").write_text(
        '[gd_resource type="Resource" format=2]\n[resource]\n'
        'chance = 1.0\ndamage = 3\nduration = 3\n', encoding="utf-8")
    (wdir / "torch_data.tres").write_text(
        '[gd_resource type="Resource" format=2]\n'
        '[ext_resource path="res://weapons/melee/torch/1/torch_effect_1.tres" type="Resource" id=1]\n'
        '[resource]\neffects = [ ExtResource( 1 ) ]\n', encoding="utf-8")

    found = find_weapon_dirs(str(tmp_path))
    assert len(found) == 1
    companions = found[0]["effect_companion_paths"]
    assert len(companions) == 1
    only = list(companions.values())[0]
    assert only["burning_data"].endswith("torch_burning_data.tres")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_build_discover.py -k companion -v`
Expected: FAIL with `AttributeError: module 'brotato_coach.builders.discover' has no attribute '_resolve_effect_companions'`

- [ ] **Step 3: Implement**

In `brotato_coach/builders/discover.py`, replace the whole `_resolve_effect_burning_data` function (lines 48-66) with:

```python
# Effect fields whose value is an ext_resource reference to a companion .tres
# carrying the real gameplay numbers. Resolution follows the reference URL —
# never a filename glob: three distinct companion naming conventions ship
# (`*_burning_data`, `*_projectile`, `*_proj_stats`), and structure stats live
# outside the weapon dir entirely (items/all/landmines/). A filename-based
# approach already caused the *_data.tres glob collision fixed in 25f8ca2.
_COMPANION_FIELDS = ("burning_data", "weapon_stats", "stats")


def _resolve_effect_companions(extracted_root: str, effect_paths: list[str]) -> dict[str, dict[str, str]]:
    """Resolve each effect's companion-resource references, if any.

    Returns effect path -> {field name: companion path}, omitting effects
    that reference no companion.
    """
    result: dict[str, dict[str, str]] = {}
    for effect_path in effect_paths:
        with open(effect_path, encoding="utf-8") as fh:
            doc = parse_tres(fh.read())
        companions: dict[str, str] = {}
        for field in _COMPANION_FIELDS:
            ref = doc.resource.get(field)
            if isinstance(ref, dict) and "__ext__" in ref:
                ext = doc.ext_resources.get(ref["__ext__"]) or {}
                path = _res_url_to_path(extracted_root, ext.get("path"))
                if path and os.path.isfile(path):
                    companions[field] = path
        if companions:
            result[effect_path] = companions
    return result
```

Then in `find_weapon_dirs`, replace:

```python
            burning_data_paths = _resolve_effect_burning_data(extracted_root, effect_paths)
```

with:

```python
            companion_paths = _resolve_effect_companions(extracted_root, effect_paths)
```

and replace the entry line:

```python
                "effect_burning_data_paths": burning_data_paths,
```

with:

```python
                "effect_companion_paths": companion_paths,
```

- [ ] **Step 4: Run the discover tests**

Run: `uv run pytest tests/test_build_discover.py -v`
Expected: PASS (all — the rewritten tests replace the old burning_data ones, so no references to the removed function remain)

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/builders/discover.py tests/test_build_discover.py
git commit -m "feat(discover): generalize companion resolution to weapon_stats and stats refs"
```

(Note: `uv run pytest -q` will FAIL at this point only if `build_dataset.py` is executed — the test suite itself doesn't exercise the renamed key until Task 4 wires it. If any test outside test_build_discover.py fails on the removed key name, fix that reference in this task.)

---

### Task 3: `_weapon_effect_record` — companions dict + `script` field

**Files:**
- Modify: `brotato_coach/builders/weapons.py` (`_weapon_effect_record` lines 16-34; `build_weapon_record` signature line 37-43 and effects-building lines 62-64)
- Test: `tests/test_build_weapons.py` (append new tests; update existing burn-companion tests)

**Interfaces:**
- Produces: `_weapon_effect_record(text: str, companion_texts: dict[str, str] | None = None) -> dict` — each companion's parsed scalars nest under its field name (`eff["burning_data"]` keeps its exact current shape; `eff["weapon_stats"]`/`eff["stats"]` are new). The record gains a `"script"` key (script ext_resource basename, e.g. `"burning_effect.gd"`) when the effect has one.
- `build_weapon_record`'s 4th positional parameter `effect_extra_texts: list[str | None]` is RENAMED/RETYPED to `effect_companion_texts: list[dict[str, str] | None] | None = None` (same position). Task 4 passes it; Tasks 5-6 read `eff["weapon_stats"]`/`eff["stats"]`/`eff["script"]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_build_weapons.py`:

```python
def test_weapon_effect_record_carries_script_basename():
    effect = ('[gd_resource type="Resource" format=2]\n'
              '[ext_resource path="res://effects/weapons/one_shot_on_hit_effect.gd" type="Script" id=1]\n'
              '[resource]\nscript = ExtResource( 1 )\nkey = ""\nvalue = 1\n')
    rec = build_weapon_record(STATS, DATA, [effect], weapon_id="w", name="W", tier=2)
    assert rec["effects"][0]["script"] == "one_shot_on_hit_effect.gd"


def test_weapon_effect_record_nests_weapon_stats_companion():
    effect = ('[gd_resource type="Resource" format=2]\n'
              '[ext_resource path="res://effects/weapons/projectiles_on_hit_effect.gd" type="Script" id=1]\n'
              '[resource]\nscript = ExtResource( 1 )\nkey = "effect_lightning_on_hit"\n'
              'value = 1\nauto_target_enemy = true\n')
    companion = ('[gd_resource type="Resource" format=2]\n[resource]\n'
                 'damage = 5\nbounce = 0\nbounce_dmg_reduction = 0.0\ncan_bounce = true\n'
                 'scaling_stats = [ [ "stat_elemental_damage", 0.8 ] ]\n')
    rec = build_weapon_record(STATS, DATA, [effect], [{"weapon_stats": companion}],
                              weapon_id="w", name="W", tier=1)
    ws = rec["effects"][0]["weapon_stats"]
    assert ws["damage"] == 5 and ws["bounce"] == 0
```

Then update the existing burn-companion tests, which pass raw text lists as the 4th positional argument — wrap each non-None element in a `{"burning_data": ...}` dict:

- `test_weapon_record_merges_burning_data_companion`: `[BURNING_DATA]` → `[{"burning_data": BURNING_DATA}]`
- `test_weapon_record_burn_dot_contributes_when_preconditions_hold`: `[_burning_data()]` → `[{"burning_data": _burning_data()}]`
- `test_weapon_record_burn_dot_falls_back_when_cycle_time_exceeds_window`: same wrap
- `test_weapon_record_burn_dot_falls_back_when_chance_below_one`: `[_burning_data(chance=0.5)]` → `[{"burning_data": _burning_data(chance=0.5)}]`
- `test_weapon_record_burn_dot_falls_back_when_damage_missing`: same wrap for its companion text
- Tests that pass no 4th argument (`..._without_companion...`, `..._without_burning_data`) are unchanged.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_build_weapons.py -v`
Expected: the two new tests FAIL (`KeyError: 'script'` / `TypeError` or `KeyError: 'weapon_stats'`); the updated burn tests FAIL (dict passed where str expected) until Step 3.

- [ ] **Step 3: Implement**

In `brotato_coach/builders/weapons.py`, replace `_weapon_effect_record` (lines 16-34) with:

```python
def _weapon_effect_record(text: str, companion_texts: dict[str, str] | None = None) -> dict:
    """A weapon's on-hit effect as plain scalar fields.

    Drops nested resource references (script, explosion_scene, …) and keeps the
    gameplay scalars — e.g. the Shredder's `key="effect_explode_custom"` with
    `chance=0.5`. The script ext_resource's basename is kept as `script`, since
    the engine dispatches many effects on script class (and blank-key effects
    have nothing else identifying them). Some effects keep their real numbers
    on companion resources instead of inline (burning_data / weapon_stats /
    stats); each given companion's scalar fields nest under its own field name
    rather than flattening, since the files carry unrelated same-named
    boilerplate (e.g. `value`).
    """
    doc = parse_tres(text)
    r = doc.resource
    record = {k: v for k, v in r.items()
              if not (isinstance(v, dict) and ("__ext__" in v or "__sub__" in v))}
    script_ref = r.get("script")
    if isinstance(script_ref, dict) and "__ext__" in script_ref:
        ext = doc.ext_resources.get(script_ref["__ext__"]) or {}
        script_path = str(ext.get("path", ""))
        if script_path:
            record["script"] = script_path.rsplit("/", 1)[-1]
    for field, extra_text in (companion_texts or {}).items():
        extra = parse_tres(extra_text).resource
        record[field] = {k: v for k, v in extra.items()
                        if not (isinstance(v, dict) and ("__ext__" in v or "__sub__" in v))}
    return record
```

Update `build_weapon_record`'s signature — replace:

```python
                        effect_extra_texts: list[str | None] | None = None, *,
```

with:

```python
                        effect_companion_texts: list[dict[str, str] | None] | None = None, *,
```

And replace the effects-building lines (62-64):

```python
    extras = effect_extra_texts or [None] * len(effect_texts or [])
    effects = [_weapon_effect_record(t, e)
               for t, e in zip(effect_texts or [], extras, strict=True)]
```

with:

```python
    companions = effect_companion_texts or [None] * len(effect_texts or [])
    effects = [_weapon_effect_record(t, c)
               for t, c in zip(effect_texts or [], companions, strict=True)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_build_weapons.py tests/test_build_discover.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/builders/weapons.py tests/test_build_weapons.py
git commit -m "feat(weapons): generalize effect companions and capture script basename"
```

---

### Task 4: Wire `build_dataset.py`

**Files:**
- Modify: `build_dataset.py` (weapon loop, lines 75-88)

**Interfaces:** None new — glue. Consumes Task 2's `effect_companion_paths` and Task 3's `effect_companion_texts`.

- [ ] **Step 1: Update the weapon-building loop**

In `build_dataset.py`, replace:

```python
    weapons = []
    for entry in discover.find_weapon_dirs(args.extracted):
        effect_paths = entry.get("effect_paths", [])
        burning_data_paths = entry.get("effect_burning_data_paths", {})
        effect_extra_texts = [
            _read(burning_data_paths[p]) if p in burning_data_paths else None
            for p in effect_paths
        ]
        weapons.append(build_weapon_record(
            _read(entry["stats_path"]), _read(entry["data_path"]),
            [_read(p) for p in effect_paths], effect_extra_texts,
            weapon_id=entry["weapon_id"], name=entry["name"], tier=entry["tier"],
            classes=entry.get("classes", []), tr=tr,
        ))
```

with:

```python
    weapons = []
    for entry in discover.find_weapon_dirs(args.extracted):
        effect_paths = entry.get("effect_paths", [])
        companion_paths = entry.get("effect_companion_paths", {})
        effect_companion_texts = [
            {field: _read(path) for field, path in companion_paths[p].items()}
            if p in companion_paths else None
            for p in effect_paths
        ]
        weapons.append(build_weapon_record(
            _read(entry["stats_path"]), _read(entry["data_path"]),
            [_read(p) for p in effect_paths], effect_companion_texts,
            weapon_id=entry["weapon_id"], name=entry["name"], tier=entry["tier"],
            classes=entry.get("classes", []), tr=tr,
        ))
```

- [ ] **Step 2: Verify the build still works end-to-end (burn behavior unchanged)**

```bash
uv run python build_dataset.py
uv run pytest tests/test_shipped_dataset.py -v
```

Expected: build succeeds; shipped-dataset tests PASS (Torch T1 still shows nonzero `proc_dps_at_zero_rd`, i.e. burn plumbing survived the generalization). `data/brotato.json` is gitignored — do not commit it.

- [ ] **Step 3: Commit**

```bash
git add build_dataset.py
git commit -m "feat(build): pass generalized effect companions into weapon records"
```

---

### Task 5: `companion_ranged_stats` model + dispatch

**Files:**
- Modify: `brotato_coach/builders/procs.py` (append model + 4 `PROC_MODELS` keys; extend module docstring)
- Modify: `brotato_coach/builders/weapons.py` (add a branch to the proc loop)
- Test: `tests/test_build_weapons.py` (append)

**Interfaces:**
- Consumes: `calc.companion_dps_line` (Task 1), `eff["weapon_stats"]` (Task 3).
- Produces: `PROC_MODELS` entries for `effect_lightning_on_hit`, `effect_projectiles_on_hit`, `EFFECT_PROJECTILES_ON_HIT`, `EFFECT_SLOW_PROJECTILES_ON_HIT`, all `{"damage_source": "companion_ranged_stats"}`. No new dataset fields.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_build_weapons.py`:

```python
def _projectile_effect(key="effect_lightning_on_hit", value=1, auto_target="true"):
    return ('[gd_resource type="Resource" format=2]\n'
            '[ext_resource path="res://effects/weapons/projectiles_on_hit_effect.gd" type="Script" id=1]\n'
            '[resource]\nscript = ExtResource( 1 )\n'
            f'key = "{key}"\nvalue = {value}\nauto_target_enemy = {auto_target}\n')


def _companion_stats(damage=5, scaling='[ [ "stat_elemental_damage", 0.8 ] ]',
                     bounce=0, bounce_dmg_reduction=0.0, can_bounce="true"):
    return ('[gd_resource type="Resource" format=2]\n[resource]\n'
            f'damage = {damage}\nscaling_stats = {scaling}\n'
            f'bounce = {bounce}\nbounce_dmg_reduction = {bounce_dmg_reduction}\n'
            f'can_bounce = {can_bounce}\n')


# Host: cooldown 27, recoil 0.1 -> cycle_time 0.65s (lightning_shiv T1)
LIGHTNING_HOST = ('[gd_resource type="Resource" format=2]\n[resource]\n'
                  'cooldown = 27\ndamage = 5\naccuracy = 1.0\nrecoil_duration = 0.1\n'
                  'scaling_stats = [ [ "stat_melee_damage", 1.0 ] ]\n')


def test_weapon_record_targeted_companion_proc_counts_chain():
    # bounce 3 (lightning_shiv T4-style chain) -> enemies_hit 1+3
    rec = build_weapon_record(LIGHTNING_HOST, DATA, [_projectile_effect()],
                              [{"weapon_stats": _companion_stats(bounce=3)}],
                              weapon_id="w", name="W", tier=1)
    # 5 dmg * 1 spawn * 4 enemies / 0.65s
    assert math.isclose(rec["proc_dps_at_zero_rd"], 30.7692, rel_tol=1e-4)
    assert rec["proc_dps_slope_per_rd"] == 0.0
    assert rec["unmodeled_effects"] == []


def test_weapon_record_targeted_falls_back_on_lossy_bounce():
    rec = build_weapon_record(
        LIGHTNING_HOST, DATA, [_projectile_effect()],
        [{"weapon_stats": _companion_stats(bounce=2, bounce_dmg_reduction=0.5)}],
        weapon_id="w", name="W", tier=1)
    assert rec["proc_dps_at_zero_rd"] == 0.0
    assert rec["unmodeled_effects"] == ["effect_lightning_on_hit"]


def test_weapon_record_spray_companion_proc_has_rd_slope():
    # cactus_mace T1: 3 spawns, damage 1, stat_ranged_damage 0.6, host ct 1.25s
    host = ('[gd_resource type="Resource" format=2]\n[resource]\n'
            'cooldown = 63\ndamage = 15\naccuracy = 1.0\nrecoil_duration = 0.1\n'
            'scaling_stats = [ [ "stat_melee_damage", 0.8 ] ]\n')
    rec = build_weapon_record(
        host, DATA,
        [_projectile_effect(key="effect_projectiles_on_hit", value=3, auto_target="false")],
        [{"weapon_stats": _companion_stats(
            damage=1, scaling='[ [ "stat_ranged_damage", 0.6 ] ]',
            bounce=0, bounce_dmg_reduction=0.5)}],
        weapon_id="w", name="W", tier=1)
    assert math.isclose(rec["proc_dps_at_zero_rd"], 2.4, rel_tol=1e-6)
    assert math.isclose(rec["proc_dps_slope_per_rd"], 1.44, rel_tol=1e-6)
    assert rec["unmodeled_effects"] == []


def test_weapon_record_spray_falls_back_when_bouncing():
    rec = build_weapon_record(
        LIGHTNING_HOST, DATA,
        [_projectile_effect(key="EFFECT_PROJECTILES_ON_HIT", value=8, auto_target="false")],
        [{"weapon_stats": _companion_stats(bounce=1, bounce_dmg_reduction=0.5)}],
        weapon_id="w", name="W", tier=3)
    assert rec["proc_dps_at_zero_rd"] == 0.0
    assert rec["unmodeled_effects"] == ["EFFECT_PROJECTILES_ON_HIT"]


def test_weapon_record_companion_proc_falls_back_without_companion():
    rec = build_weapon_record(LIGHTNING_HOST, DATA, [_projectile_effect()],
                              weapon_id="w", name="W", tier=1)
    assert rec["proc_dps_at_zero_rd"] == 0.0
    assert rec["unmodeled_effects"] == ["effect_lightning_on_hit"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_build_weapons.py -k "companion_proc or targeted or spray" -v`
Expected: the "contributes"/"slope" tests FAIL on `proc_dps_at_zero_rd` (0.0 vs expected); fallback tests may pass by accident — re-run after Step 3.

- [ ] **Step 3: Implement**

In `brotato_coach/builders/procs.py`, append before `PROC_MODELS`:

```python
# Companion-projectile procs (ProjectilesOnHitEffect): every landed host hit
# unconditionally spawns `value` projectiles (no chance roll — value is a
# count) whose damage/crit/scaling live on a companion RangedWeaponStats
# resource (`weapon_stats = ExtResource(N)` on the effect .tres). One script
# class serves four keys, so all four share this model (same pattern as the
# exploding trio). Evidence: docs/proc-mechanics.md "Companion-projectile
# procs" + research dossiers 2026-07-05-family-{lightning,projectiles-on-hit,
# slows-cc}.md. The enemies-hit policy and precondition gates live in
# builders/weapons.py: targeted chains (auto_target_enemy=true) count
# 1+bounce, gated on lossless bounce; untargeted sprays count 1.0 per volley,
# gated on bounce==0 — the 1.0 is an assumption constant per the exploding
# model's default_enemies_hit precedent (optimistic vs. a lone enemy, where
# the true value is 0 — the spawn excludes the enemy that triggered it).
_COMPANION_PROJECTILE_MODEL = {
    "damage_source": "companion_ranged_stats",
}
```

and replace the `PROC_MODELS` dict with:

```python
PROC_MODELS: dict[str, dict] = {
    "effect_explode_custom": _EXPLODE_MODEL,
    "effect_explode": _EXPLODE_MODEL,
    "effect_explode_melee": _EXPLODE_MODEL,
    "effect_burning": _BURN_MODEL,
    "effect_lightning_on_hit": _COMPANION_PROJECTILE_MODEL,
    "effect_projectiles_on_hit": _COMPANION_PROJECTILE_MODEL,
    "EFFECT_PROJECTILES_ON_HIT": _COMPANION_PROJECTILE_MODEL,
    "EFFECT_SLOW_PROJECTILES_ON_HIT": _COMPANION_PROJECTILE_MODEL,
}
```

In `brotato_coach/builders/weapons.py`, in the proc loop, insert a new branch after the `elif source == "burn_dot":` block (i.e. before the final `elif eff.get("key"):`):

```python
        elif source == "companion_ranged_stats":
            ws = eff.get("weapon_stats") or {}
            damage = ws.get("damage")
            count = float(eff.get("value", 0))
            bounce = int(ws.get("bounce", 0)) if bool(ws.get("can_bounce", True)) else 0
            ok = damage is not None and count > 0
            if bool(eff.get("auto_target_enemy", False)):
                # Targeted chain: assume the nominal chain fully connects.
                # No decaying-bounce math exists — lossy bounces fall back.
                ok = ok and (bounce == 0 or float(ws.get("bounce_dmg_reduction", 0.5)) == 0.0)
                enemies_hit = 1.0 + bounce
            else:
                # Untargeted spray: one expected hit per volley (documented
                # assumption, exploding default_enemies_hit precedent).
                ok = ok and bounce == 0
                enemies_hit = 1.0
            if ok:
                p0, ps = calc.companion_dps_line(
                    float(damage), _rd_coefficient(ws.get("scaling_stats") or []),
                    ct, count, enemies_hit)
                proc0 += p0
                proc_slope += ps
            elif eff.get("key"):
                unmodeled.append(str(eff["key"]))
```

Also update `procs.py`'s module docstring "Model schema" section by appending one line:

```
    damage_source: "companion_ranged_stats" — spawn-projectiles-on-hit; the
        proc's own damage line lives on the effect's weapon_stats companion.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_build_weapons.py tests/test_calc.py -v`
Expected: PASS (all, including pre-existing burn/explode tests)

- [ ] **Step 5: Commit**

```bash
git add brotato_coach/builders/procs.py brotato_coach/builders/weapons.py tests/test_build_weapons.py
git commit -m "feat(procs): model companion-projectile procs (lightning + sprays)"
```

---

### Task 6: `classifications.py` + `classified_effects`

**Files:**
- Create: `brotato_coach/builders/classifications.py`
- Test: `tests/test_build_classifications.py` (new)
- Modify: `brotato_coach/builders/weapons.py` (proc loop tail + record dict)
- Test: `tests/test_build_weapons.py` (append integration tests)

**Interfaces:**
- Produces: `classifications.CATEGORIES: frozenset[str]` and `classifications.classify_effect(eff: dict) -> dict | None`. A non-None result always has `"key"` and `"category"` (category ∈ CATEGORIES) plus category-specific metadata. Weapon records gain `"classified_effects": list[dict]`.

- [ ] **Step 1: Write the failing unit tests**

Create `tests/test_build_classifications.py`:

```python
from brotato_coach.builders.classifications import CATEGORIES, classify_effect


def test_flat_sum_stat_key_is_stat_rider():
    entry = classify_effect({"key": "stat_armor", "value": 1, "script": "effect.gd"})
    assert entry == {"key": "stat_armor", "category": "stat_rider", "value": 1}


def test_key_value_storage_is_dynamic_not_rider():
    # jousting_lance's stand-still damage penalty: same key string as a flat
    # rider, but KEY_VALUE storage routes it through a conditional bucket.
    entry = classify_effect({"key": "stat_percent_damage", "value": -10,
                             "storage_method": 1,
                             "custom_key": "temp_stats_while_not_moving",
                             "script": "effect.gd"})
    assert entry == {"key": "stat_percent_damage", "category": "dynamic"}


def test_dynamic_scripts_classify_by_script():
    for script in ("gain_stat_for_every_stat_effect.gd",
                   "temp_stats_per_interval_effect.gd",
                   "gain_stat_every_killed_enemies_effect.gd",
                   "player_no_hit_effect.gd"):
        entry = classify_effect({"key": "stat_lifesteal", "value": 1, "script": script})
        assert entry["category"] == "dynamic", script


def test_cc_scripts():
    assert classify_effect({"key": "EFFECT_WEAPON_SLOW_ON_HIT", "value": 1,
                            "script": "weapon_slow_on_hit_effect.gd"})["category"] == "cc"
    assert classify_effect({"key": "effect_slow_in_zone", "value": 1,
                            "script": "slow_in_zone_effect.gd"})["category"] == "cc"


def test_crit_riders_and_economy():
    pierce = classify_effect({"key": "pierce_on_crit", "value": 4, "script": "null_effect.gd"})
    assert pierce == {"key": "pierce_on_crit", "category": "delivery_modifier",
                      "on_crit_extra_hits_max": 4}
    gold = classify_effect({"key": "gold_on_crit_kill", "value": 50, "script": "null_effect.gd"})
    assert gold == {"key": "gold_on_crit_kill", "category": "economy",
                    "gold_chance_on_crit_kill": 0.5}


def test_drawback():
    entry = classify_effect({"key": "lose_hp_per_second", "value": 3, "script": "effect.gd"})
    assert entry == {"key": "lose_hp_per_second", "category": "drawback",
                     "self_damage_per_second": 3}


def test_execute_names_blank_key_by_mechanic():
    entry = classify_effect({"key": "", "value": 2,
                             "script": "one_shot_on_hit_effect.gd"})
    assert entry == {"key": "one_shot_on_hit", "category": "execute",
                     "execute_chance_per_hit": 0.02}


def test_stack_metadata():
    entry = classify_effect({"key": "EFFECT_WEAPON_STACK", "value": 4,
                             "stat_name": "damage", "weapon_stacked_id": "weapon_stick",
                             "script": "weapon_stack_effect.gd"})
    assert entry == {"key": "EFFECT_WEAPON_STACK", "category": "stack",
                     "stat_name": "damage", "bonus_per_extra_copy": 4}


def test_structure_metadata_reads_stats_companion():
    entry = classify_effect({"key": "", "value": 1, "spawn_cooldown": 12,
                             "script": "structure_effect.gd",
                             "stats": {"damage": 10,
                                       "scaling_stats": [["stat_engineering", 1.0]]}})
    assert entry == {"key": "structure", "category": "structure",
                     "spawn_cooldown": 12, "structure_damage": 10,
                     "structure_scaling_stats": [["stat_engineering", 1.0]]}


def test_unknown_effect_is_not_classified():
    assert classify_effect({"key": "effect_burning", "script": "burning_effect.gd"}) is None
    assert classify_effect({"key": "", "script": "mystery_effect.gd"}) is None


def test_all_categories_in_vocabulary():
    samples = [
        {"key": "stat_armor", "value": 1, "script": "effect.gd"},
        {"key": "x", "storage_method": 1, "script": "effect.gd"},
        {"key": "gold_on_crit_kill", "value": 50, "script": "null_effect.gd"},
        {"key": "effect_slow_in_zone", "script": "slow_in_zone_effect.gd"},
        {"key": "pierce_on_crit", "value": 1, "script": "null_effect.gd"},
        {"key": "lose_hp_per_second", "value": 3, "script": "effect.gd"},
        {"key": "", "value": 1, "script": "one_shot_on_hit_effect.gd"},
        {"key": "EFFECT_WEAPON_STACK", "value": 4, "stat_name": "damage",
         "script": "weapon_stack_effect.gd"},
        {"key": "", "value": 1, "spawn_cooldown": 12, "script": "turret_effect.gd"},
    ]
    for s in samples:
        entry = classify_effect(s)
        assert entry is not None and entry["category"] in CATEGORIES, s
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_build_classifications.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'brotato_coach.builders.classifications'`

- [ ] **Step 3: Create `brotato_coach/builders/classifications.py`**

```python
"""Mechanism-based classification of non-DPS weapon effects.

An effect that has no PROC_MODELS damage model may still be a fully
understood mechanic — a passive stat grant, an economy perk, crowd control, a
crit-gated delivery modifier, or a special (execute / per-copy stack /
structure spawner). classify_effect() recognizes these by MECHANISM — the
attached script's basename, the Effect base class's storage_method, and
finally the key string — never by weapon name, because identical key strings
hide different mechanics (stat_percent_damage is a flat debuff nowhere and a
stand-still-gated one on Jousting Lance). Classified effects land in the
weapon record's `classified_effects` (with citation-ready metadata) instead
of `unmodeled_effects`, which then means strictly "uninvestigated."

Categories and the evidence behind each classification are documented in
docs/proc-mechanics.md ("Effect classification") and the research dossiers
under docs/superpowers/research/. Every script name below was verified to be
the engine's actual dispatch target (or a no-op NullEffect whose key string
is consumed elsewhere) — see the dossiers.
"""

from __future__ import annotations

CATEGORIES = frozenset({
    "stat_rider",        # flat player-stat grant while held (SUM storage)
    "dynamic",           # state/build/time-dependent — no honest static number
    "economy",           # gold/xp event effects
    "cc",                # slows/crowd control, zero damage
    "delivery_modifier", # crit-gated pierce/bounce on the weapon's own line
    "drawback",          # self-damage cost
    "execute",           # chance to force hit damage = target's current HP
    "stack",             # per-extra-copy flat weapon-stat bonus
    "structure",         # spawns a persistent structure (mines, garden)
})

# Scripts whose class IS the mechanic (engine dispatches on script class, or
# the .tres ships key="" so the script is the only identity).
_DYNAMIC_SCRIPTS = frozenset({
    "gain_stat_for_every_stat_effect.gd",        # missing-HP-scaled grant (Sharp Tooth)
    "temp_stats_per_interval_effect.gd",         # unbounded interval accumulator (Drill T4)
    "gain_stat_every_killed_enemies_effect.gd",  # per-weapon kill ratchet (Ghost weapons)
    "player_no_hit_effect.gd",                   # no-hit damage ramp (Rail Gun)
})
_CC_SCRIPTS = frozenset({
    "weapon_slow_on_hit_effect.gd",  # engineering-scaled percent slow (Particle Accelerator)
    "slow_in_zone_effect.gd",        # inert marker; slow is hardcoded in taser_projectile.gd
})

# Flat-SUM keys that are player-stat grants but don't start with "stat_".
_EXTRA_RIDER_KEYS = frozenset({"xp_gain", "knockback", "consumable_heal",
                               "burning_spread"})


def classify_effect(eff: dict) -> dict | None:
    """Classify a modeled-less effect record, or return None (→ unmodeled)."""
    key = str(eff.get("key", "") or "")
    script = str(eff.get("script", "") or "")

    if script == "one_shot_on_hit_effect.gd":
        return {"key": key or "one_shot_on_hit", "category": "execute",
                "execute_chance_per_hit": float(eff.get("value", 0)) / 100.0}
    if script == "weapon_stack_effect.gd":
        return {"key": key or "weapon_stack", "category": "stack",
                "stat_name": eff.get("stat_name"),
                "bonus_per_extra_copy": eff.get("value")}
    if script in ("structure_effect.gd", "turret_effect.gd"):
        stats = eff.get("stats") or {}
        return {"key": key or "structure", "category": "structure",
                # Raw engine value: seconds for StructureEffect, frames for
                # TurretEffect — units documented in docs/proc-mechanics.md.
                "spawn_cooldown": eff.get("spawn_cooldown"),
                "structure_damage": stats.get("damage"),
                "structure_scaling_stats": stats.get("scaling_stats")}
    if script in _DYNAMIC_SCRIPTS:
        return {"key": key, "category": "dynamic"}
    if script in _CC_SCRIPTS:
        return {"key": key, "category": "cc"}

    if key in ("pierce_on_crit", "bounce_on_crit"):
        return {"key": key, "category": "delivery_modifier",
                "on_crit_extra_hits_max": eff.get("value")}
    if key == "gold_on_crit_kill":
        return {"key": key, "category": "economy",
                "gold_chance_on_crit_kill": float(eff.get("value", 0)) / 100.0}
    if key == "lose_hp_per_second":
        return {"key": key, "category": "drawback",
                "self_damage_per_second": eff.get("value")}

    # KEY_VALUE storage (effect.gd:62-83) routes the value into a named
    # conditional bucket (temp_stats_while_not_moving / temp_stats_on_hit /
    # additional_weapon_effects) — state-dependent, no static number.
    if key and eff.get("storage_method", 0) == 1:
        return {"key": key, "category": "dynamic"}
    if key.startswith("stat_") or key in _EXTRA_RIDER_KEYS:
        return {"key": key, "category": "stat_rider", "value": eff.get("value")}
    return None
```

- [ ] **Step 4: Run unit tests to verify they pass**

Run: `uv run pytest tests/test_build_classifications.py -v`
Expected: PASS

- [ ] **Step 5: Write the failing integration tests**

Append to `tests/test_build_weapons.py`:

```python
def test_weapon_record_classifies_stat_rider_out_of_unmodeled():
    effect = ('[gd_resource type="Resource" format=2]\n'
              '[ext_resource path="res://items/global/effect.gd" type="Script" id=1]\n'
              '[resource]\nscript = ExtResource( 1 )\nkey = "stat_armor"\nvalue = 1\n')
    rec = build_weapon_record(STATS, DATA, [effect], weapon_id="w", name="W", tier=2)
    assert rec["unmodeled_effects"] == []
    assert rec["classified_effects"] == [
        {"key": "stat_armor", "category": "stat_rider", "value": 1}]


def test_weapon_record_blank_key_unknown_script_surfaces_in_unmodeled():
    effect = ('[gd_resource type="Resource" format=2]\n'
              '[ext_resource path="res://effects/weapons/mystery_effect.gd" type="Script" id=1]\n'
              '[resource]\nscript = ExtResource( 1 )\nkey = ""\nvalue = 1\n')
    rec = build_weapon_record(STATS, DATA, [effect], weapon_id="w", name="W", tier=1)
    assert rec["classified_effects"] == []
    assert rec["unmodeled_effects"] == ["mystery_effect.gd"]


def test_weapon_record_burn_gate_failure_stays_unmodeled_not_classified():
    rec = build_weapon_record(STATS, DATA, [BURNING_EFFECT],
                              [{"burning_data": _burning_data(chance=0.5)}],
                              weapon_id="w", name="W", tier=1)
    assert rec["unmodeled_effects"] == ["effect_burning"]
    assert rec["classified_effects"] == []
```

- [ ] **Step 6: Run to verify they fail**

Run: `uv run pytest tests/test_build_weapons.py -k "classif or mystery" -v`
Expected: FAIL with `KeyError: 'classified_effects'`

- [ ] **Step 7: Integrate into `build_weapon_record`**

In `brotato_coach/builders/weapons.py`:

Add the import below the existing `PROC_MODELS` import:

```python
from brotato_coach.builders.classifications import classify_effect
```

In the proc loop, initialize alongside `unmodeled`:

```python
    unmodeled: list[str] = []
    classified: list[dict] = []
```

Replace the loop's final fallback branch:

```python
        elif eff.get("key"):
            unmodeled.append(str(eff["key"]))
```

with:

```python
        else:
            entry = classify_effect(eff)
            if entry is not None:
                classified.append(entry)
            elif eff.get("key") or eff.get("script"):
                # Blank-key effects were previously dropped silently; naming
                # them by script keeps hidden mechanics visible.
                unmodeled.append(str(eff.get("key") or eff["script"]))
```

(The gate-failure `elif eff.get("key"): unmodeled.append(...)` branches inside the `burn_dot` and `companion_ranged_stats` sources stay exactly as they are — a failed damage-model gate is a modeling gap, not a classification.)

In the returned dict, after `"unmodeled_effects": unmodeled,` add:

```python
        "classified_effects": classified,
```

Also update the comment block above `"effects"` (lines 112-115) to:

```python
        # On-hit effects, resolved from the data .tres `effects`
        # ext_resources. Effects with a verified PROC_MODELS entry contribute
        # the proc_dps_* expected line; classified non-DPS mechanics land in
        # classified_effects; anything left is listed in unmodeled_effects.
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest -q`
Expected: PASS (full suite; shipped-dataset skipped unless built)

- [ ] **Step 9: Commit**

```bash
git add brotato_coach/builders/classifications.py tests/test_build_classifications.py brotato_coach/builders/weapons.py tests/test_build_weapons.py
git commit -m "feat(classify): categorize non-DPS effects into classified_effects"
```

---

### Task 7: Shipped-dataset assertions + local build verification

**Files:**
- Modify: `tests/test_shipped_dataset.py` (append after the burn-weapon assertion block from PR #8)

**Interfaces:** None new.

- [ ] **Step 1: Append assertions**

In `tests/test_shipped_dataset.py`, after the existing block ending

```python
    torch = query.get_weapon(ds, "Torch", tier=1)
    assert torch["proc_dps_at_zero_rd"] > 0
    assert torch["unmodeled_effects"] == []
```

append:

```python

    # companion-projectile procs carry expected lines
    shiv = query.get_weapon(ds, "Lightning Shiv", tier=1)
    assert shiv["proc_dps_at_zero_rd"] > 0
    cactus = query.get_weapon(ds, "Cactus Mace", tier=1)
    assert cactus["proc_dps_at_zero_rd"] > 0
    assert cactus["proc_dps_slope_per_rd"] > 0  # companion scales off RD

    # classified specials carry structured metadata
    stick = query.get_weapon(ds, "Stick", tier=1)
    assert any(c["category"] == "stack" and c["bonus_per_extra_copy"] == 4
               for c in stick["classified_effects"])
    vorpal = query.get_weapon(ds, "Vorpal Sword", tier=2)
    assert any(c["category"] == "execute" and c["execute_chance_per_hit"] == 0.01
               for c in vorpal["classified_effects"])
    screwdriver = query.get_weapon(ds, "Screwdriver", tier=1)
    assert any(c["category"] == "structure" and c["structure_damage"] == 10
               for c in screwdriver["classified_effects"])

    # the proc worklist is fully triaged: nothing shipped is unmodeled
    assert all(w["unmodeled_effects"] == [] for w in ds["weapons"])
```

- [ ] **Step 2: Rebuild the dataset and run the whole suite**

```bash
uv run python build_dataset.py
uv run pytest -v
```

Expected: PASS, including `tests/test_shipped_dataset.py` (not skipped). If the final `all(...)` assertion fails, print the offenders (`[(w["id"], w["tier"], w["unmodeled_effects"]) for w in ds["weapons"] if w["unmodeled_effects"]]`) — any hit is either a classification rule gap (extend `classifications.py` with evidence from the dossiers) or a genuinely uninvestigated key (report it; do NOT invent a classification). `data/brotato.json` stays uncommitted.

- [ ] **Step 3: Commit**

```bash
git add tests/test_shipped_dataset.py
git commit -m "test(dataset): assert companion procs, classified specials, empty worklist"
```

---

### Task 8: `docs/proc-mechanics.md` — companion procs + classification

**Files:**
- Modify: `docs/proc-mechanics.md`

**Interfaces:** None — documentation, mirroring the existing sections' evidence format.

- [ ] **Step 1: Add the "Companion-projectile procs" section**

Insert after the "Burning effect" section (before `## Unmodeled effect-key worklist`):

```markdown

## Companion-projectile procs (`ProjectilesOnHitEffect`, `recovered/effects/weapons/projectiles_on_hit_effect.gd`)

One script class serves four differently-keyed effects (dispatch is on script
class; casing is cosmetic): `effect_lightning_on_hit` (Lightning Shiv T1-4,
Dextroyer T4), `effect_projectiles_on_hit` (Cactus Mace T1-4),
`EFFECT_PROJECTILES_ON_HIT` (Sniper Gun T3-4), and
`EFFECT_SLOW_PROJECTILES_ON_HIT` (Thunder Sword T3-4). All share one
`PROC_MODELS` entry (`damage_source: "companion_ranged_stats"`). Full
evidence: `docs/superpowers/research/2026-07-05-family-lightning.md` and
`...-family-projectiles-on-hit.md`.

### Mechanics

- `recovered/weapons/weapon.gd:146-149` (`init_stats`): for a
  `ProjectilesOnHitEffect`, the hitbox carries `[effect.value, companion
  weapon_stats, effect.auto_target_enemy]`.
- `recovered/entities/units/unit/unit.gd:586-603`: on every landed hit,
  `value` projectiles spawn from the just-hit enemy's position —
  **unconditionally** (no chance roll; there is no `chance` field on this
  effect class, and `value` is a spawn count, not a probability).
- Damage is fully independent of the host weapon: the companion
  `RangedWeaponStats` (`weapon_stats = ExtResource(N)` on the effect .tres)
  carries its own `damage`, `scaling_stats`, crit fields. At the dataset's
  zero-stat baseline this reduces to the companion's raw `damage` field
  (`weapon_service.gd` `init_ranged_stats(…, is_special_spawn=true)`).
- Targeting (`weapon_service.gd:353-357`): with `auto_target_enemy=true`
  (lightning users) the projectile aims at a uniformly *random other* enemy
  (`entity_spawner.gd:485-495`, excludes the triggering enemy — worth 0
  against a lone target); with `false` (all other users) the direction stays
  `rand_range(-PI, PI)` — an unaimed spray.
- Bounce chaining (`player_projectile.gd:119-129`) re-rolls a random target
  per hop; lightning users ship `bounce` 0/1/2/3/4 with an explicit
  `bounce_dmg_reduction = 0.0` (engine default is 0.5,
  `ranged_weapon_stats.gd:9`); spray users ship `bounce = 0`.

### Model

`proc_dps0 = companion_damage × value × enemies_hit / host_cycle_time`, slope
via the companion's own `stat_ranged_damage` coefficient (nonzero only for
Cactus Mace, 0.6→1.0 by tier; lightning scales off elemental, Sniper Gun off
`stat_range`, Thunder Sword off elemental — slope 0 for those).

`enemies_hit` policy (the softest number, like exploding's
`default_enemies_hit`):

- targeted chain: `1 + bounce`, gated on lossless bounce (`bounce == 0` or
  `bounce_dmg_reduction == 0.0`) — assumes the nominal chain connects;
  optimistic in sparse fields, 0 against a lone enemy.
- untargeted spray: `1.0` per volley, gated on `bounce == 0` — a pure
  assumption constant; a random-direction volley has no evidence anchor for
  its hit rate. Callers evaluating single-target scenarios should override
  down, as with exploding.

Gate failures (missing companion/damage, `value <= 0`, lossy or unexpected
bounce) fall back to `unmodeled_effects` — no decaying-bounce or
hit-probability math is modeled, since no shipped weapon needs it.

Thunder Sword's spawned projectile is literally taser's bullet scene, whose
`SlowHitbox` applies a hardcoded `add_decaying_speed(-200)`
(`taser_projectile.gd:15-17`) — the slow is CC (see classification below);
this model scores only the companion's damage=1 sliver.

## Effect classification (`brotato_coach/builders/classifications.py`)

Effects with no damage model but a fully evidenced mechanic are classified
into `classified_effects` on the weapon record instead of polluting
`unmodeled_effects` (which now strictly means "uninvestigated" — blank-key
effects surface there by script basename instead of being dropped silently).
Classification is mechanism-based (script basename, then `storage_method`,
then key string) — never per-weapon lists. Categories, with evidence in the
2026-07-05 research dossiers:

| category | shipped examples | notes |
|---|---|---|
| `stat_rider` | Rock armor/HP, Hand harvesting, Fighting Stick xp_gain, Hammer knockback (player-wide, `weapon_service.gd:265-270`), Jousting Lance speed, Torch `burning_spread` (+1 one-hop burn spread, global stat, `weapon_service.gd:334`), Chopper `consumable_heal`, Scythe... | flat SUM grant while held (`run_data.gd:989/1081`) |
| `dynamic` | Jousting Lance stand-still −damage% (`player.gd:215-239`), Scythe T4 on-player-hit stack (`player.gd:493-495`), Excalibur −2 armor × weapons owned (`run_data.gd:1190-1203`), Sharp Tooth missing-HP lifesteal (`linked_stats.gd`), Drill T4 unbounded +AS/5s, Rail Gun no-hit ramp (`railgun.gd:82-99`), Ghost weapons kill ratchet (`weapon.gd:211-232`) | state/build/time-dependent; no honest static number — deliberately no metadata value |
| `economy` | Dagger/Drill `gold_on_crit_kill` (`unit.gd:376-379`, value%/100 for +1 gold on crit-kill) | |
| `cc` | Particle Accelerator slow (engineering-scaled, `weapon_service.gd:191` → `unit.gd:605-606`), Taser `effect_slow_in_zone` (inert marker — the −200 slow is hardcoded in the projectile scene, not in extracted data) | |
| `delivery_modifier` | Crossbow `pierce_on_crit`, Shuriken `bounce_on_crit` (`player_projectile.gd:132-154`: each crit converts one charge into +1 pierce/bounce, per-projectile budget, 0% damage falloff by explicit override) | no DPS number — the expected crit-chain needs a crowd-density assumption on top of `crit_chance`; deferred |
| `drawback` | Scythe T4 `lose_hp_per_second` (3 HP/s, undodgeable/unarmored, `player.gd:844-850`) | |
| `execute` | Vorpal Sword T2-4 blank-key `OneShotOnHitEffect` (`unit.gd:285-305`: value% chance to force damage = target's current HP) | chance surfaces as `execute_chance_per_hit`; damage is run-state-dependent, never folded into DPS |
| `stack` | Stick `EFFECT_WEAPON_STACK` (`weapon_service.gd:192-197`: +value flat damage per extra copy owned, additive before RD scaling → slope 0) | `bonus_per_extra_copy` metadata; per-copies DPS needs a loadout axis the schema doesn't have — computed at answer time if needed |
| `structure` | Screwdriver landmines (blank key, `StructureEffect`; mine damage flat 10 + `stat_engineering` scaling for all tiers, tier only buys spawn rate 12/9/6/3s; trigger is enemy enter-then-exit pathing — no evidence anchor for an "eventually triggers" steady state), Pruner garden (`TurretEffect`, `damage = 0` explicit — healing-fruit spawner; `spawn_cooldown` in frames, unlike StructureEffect's seconds) | `spawn_cooldown` is the raw engine value — units differ by script |
```

- [ ] **Step 2: Replace the worklist table**

Replace the `## Unmodeled effect-key worklist` section's intro paragraph and table with:

```markdown
Effect `key` values found across `extracted/weapons/*.tres`
(`grep -rh '^key = ' extracted/weapons/ | sort | uniq -c`). As of the
2026-07-05 triage (research dossiers under `docs/superpowers/research/`),
every shipped key is either modeled (contributes to `proc_dps_*`) or
classified (`classified_effects`); `unmodeled_effects` is empty across the
shipped dataset and now strictly means "uninvestigated." Blank-key effects
are named by script basename rather than silently dropped.

| count | key | disposition |
|---|---|---|
| 19 | `effect_burning` | modeled (burn_dot) |
| 12 | `effect_gain_stat_every_killed_enemies` | classified: dynamic |
| 10 | *(blank key)* | classified: execute (Vorpal Sword) / structure (Screwdriver, Pruner) |
| 9  | `effect_explode_melee` | modeled (weapon_damage) |
| 5  | `stat_percent_damage` | classified: dynamic (KEY_VALUE storage on all shipped users) |
| 5  | `gold_on_crit_kill` | classified: economy |
| 5  | `effect_lightning_on_hit` | modeled (companion_ranged_stats) |
| 5  | `effect_explode` | modeled (weapon_damage) |
| 4  | `xp_gain` | classified: stat_rider |
| 4  | `stat_speed` | classified: stat_rider |
| 4  | `stat_lifesteal` | classified: dynamic (missing-HP-scaled) |
| 4  | `stat_harvesting` | classified: stat_rider |
| 4  | `stat_armor` | classified: stat_rider (Rock) / dynamic (Excalibur, KEY_VALUE) |
| 4  | `pierce_on_crit` | classified: delivery_modifier |
| 4  | `effect_projectiles_on_hit` | modeled (companion_ranged_stats) |
| 4  | `effect_no_hit_boost` | classified: dynamic |
| 4  | `bounce_on_crit` | classified: delivery_modifier |
| 4  | `EFFECT_WEAPON_STACK` | classified: stack |
| 3  | `knockback` | classified: stat_rider |
| 3  | `effect_explode_custom` | modeled (weapon_damage) |
| 2  | `EFFECT_PROJECTILES_ON_HIT` | modeled (companion_ranged_stats) |
| 2  | `EFFECT_SLOW_PROJECTILES_ON_HIT` | modeled (damage sliver) + CC noted |
| 2  | `EFFECT_WEAPON_SLOW_ON_HIT` | classified: cc |
| 2  | `burning_spread` | classified: stat_rider (global) |
| 2  | `consumable_heal` | classified: stat_rider |
| 2  | `stat_max_hp` | classified: stat_rider |
| 1  | `effect_slow_in_zone` | classified: cc |
| 1  | `lose_hp_per_second` | classified: drawback |
| 1  | `stat_attack_speed` | classified: dynamic (interval accumulator) |
```

Adjust the final counts against a fresh `grep -rh '^key = ' extracted/weapons/ | sort | uniq -c` run at write time — the table above reflects the 2026-07-05 census; re-pin before committing.

- [ ] **Step 3: Commit**

```bash
git add docs/proc-mechanics.md
git commit -m "docs(proc-mechanics): document companion procs and effect classification"
```
