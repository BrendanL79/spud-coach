# Class-Bonus Modeling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture the six `ClassBonusEffect` character kits the build step currently drops (e.g. Crazy's "+100 Range with Precise weapons"), surface them via `get_character`/`evaluate_run`, and reason about them advisorily — with no change to any computed DPS number.

**Architecture:** The build step gains a structured `class_bonuses` field on each character record (parsed from the `ClassBonusEffect` `.tres` payload the catch-all currently discards). A pure `answers.character_class_synergy` helper joins a character's class bonuses to an equipped loadout, and `evaluate_run` surfaces the result. The RD-only DPS engine is untouched; the primer gains a caveat and the roadmap gains a seed for the deferred engine work.

**Tech Stack:** Python 3.11+, uv, pytest, ruff. Pure-logic modules with no I/O (`answers.py`, `builders/characters.py`), unit-tested against hand-verified values.

## Global Constraints

- Python 3.11+, managed with uv. Test with `uv run pytest`; lint with `uv run ruff check .` (keep green).
- TDD: write the failing test first, watch it fail, then implement.
- The MCP server reads only `data/brotato.json` — never `.tres`. Build-step code (`build_dataset.py`, `builders/`) is the only code that reads `extracted/`.
- Never commit `data/brotato.json`, `extracted/`, `recovered/`, `game_files/` (all gitignored). Regenerate the dataset locally.
- Merge convention: this is a large multi-commit feature → merge commit at the end (not squash). Work stays on branch `feature/class-bonus-modeling`.
- No change to any computed DPS number. Range/attack-speed/lifesteal bonuses are build context, not DPS deltas.

---

### Task 1: Builder captures `class_bonuses`

**Files:**
- Modify: `brotato_coach/builders/characters.py`
- Modify: `build_dataset.py:122-138` (reorder sets before characters; thread `set_names`)
- Test: `tests/test_build_characters.py`

**Interfaces:**
- Produces: `build_character_record(..., set_names: dict[str, str] | None = None) -> dict` where the returned dict gains `"class_bonuses": list[dict]`, each entry `{"set_id": str, "set_name": str, "stat": str, "stat_displayed": str, "value": int|float}`. Empty list for characters without a `ClassBonusEffect`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_build_characters.py`:

```python
EFF_CLASS_BONUS_PRECISE = (
    '[resource]\nkey = "effect_weapon_class_bonus"\nvalue = 100\n'
    'set_id = "set_precise"\nstat_displayed_name = "stat_range"\n'
    'stat_name = "max_range"\n'
)
EFF_CLASS_BONUS_UPPER = (
    '[resource]\nkey = "EFFECT_WEAPON_CLASS_BONUS"\nvalue = 50\n'
    'set_id = "set_unarmed"\nstat_displayed_name = "stat_attack_speed"\n'
    'stat_name = "attack_speed_mod"\n'
)


def test_class_bonus_captured_structurally():
    rec = build_character_record(
        RANGER_DATA, [EFF_CLASS_BONUS_PRECISE],
        char_id="character_crazy", name="Crazy",
        wanted_tags=[], banned_item_groups=[],
        set_names={"set_precise": "Precise"})
    assert rec["class_bonuses"] == [{
        "set_id": "set_precise", "set_name": "Precise",
        "stat": "max_range", "stat_displayed": "stat_range", "value": 100}]


def test_class_bonus_token_absent_from_special_effects_uppercase_key():
    rec = build_character_record(
        RANGER_DATA, [EFF_CLASS_BONUS_UPPER],
        char_id="character_brawler", name="Brawler",
        wanted_tags=[], banned_item_groups=[])
    assert rec["special_effects"] == []
    assert rec["class_bonuses"][0]["set_id"] == "set_unarmed"
    assert rec["class_bonuses"][0]["value"] == 50


def test_class_bonus_set_name_falls_back_to_titlecased_id():
    rec = build_character_record(
        RANGER_DATA, [EFF_CLASS_BONUS_PRECISE],
        char_id="c", name="C", wanted_tags=[], banned_item_groups=[])
    assert rec["class_bonuses"][0]["set_name"] == "Precise"


def test_non_class_character_has_empty_class_bonuses():
    rec = build_character_record(
        RANGER_DATA, [EFF_FLAT_RANGE], char_id="c", name="C",
        wanted_tags=[], banned_item_groups=[])
    assert rec["class_bonuses"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_build_characters.py -k class_bonus -v`
Expected: FAIL — `KeyError: 'class_bonuses'` (field not yet produced).

- [ ] **Step 3: Implement the builder change**

Replace the full contents of `brotato_coach/builders/characters.py` with:

```python
from __future__ import annotations

from brotato_coach.builders.localization import resolve_text
from brotato_coach.tres import parse_tres

_GAIN_KEYS = {"effect_increase_stat_gains", "effect_reduce_stat_gains"}


def _set_name(set_id: str, set_names: dict[str, str]) -> str:
    name = set_names.get(set_id)
    if name:
        return name
    slug = set_id[len("set_"):] if set_id.startswith("set_") else set_id
    return slug.replace("_", " ").title()


def build_character_record(data_text: str, effect_texts: list[str], *, char_id: str,
                          name: str, wanted_tags: list[str],
                          banned_item_groups: list[str],
                          tr: dict[str, str] | None = None,
                          set_names: dict[str, str] | None = None) -> dict:
    d = parse_tres(data_text).resource
    flat_bonuses: list[dict] = []
    gain_modifiers: list[dict] = []
    special_effects: list[str] = []
    class_bonuses: list[dict] = []
    set_names = set_names or {}

    for text in effect_texts:
        r = parse_tres(text).resource
        key = str(r.get("key", ""))
        set_id = r.get("set_id")
        if key in _GAIN_KEYS:
            mods = r.get("stats_modified", []) or []
            stat = mods[0] if mods else None
            if stat is not None:
                gain_modifiers.append({"stat": stat, "pct": r.get("value", 0)})
        elif set_id:
            class_bonuses.append({
                "set_id": str(set_id),
                "set_name": _set_name(str(set_id), set_names),
                "stat": str(r.get("stat_name", "")),
                "stat_displayed": str(r.get("stat_displayed_name", "")),
                "value": r.get("value", 0),
            })
        elif key.startswith("stat_"):
            flat_bonuses.append({"stat": key, "value": r.get("value", 0)})
        else:
            if not key.startswith("weapon_"):
                special_effects.append(key)

    return {
        "id": char_id,
        "name": name,
        "display_name": resolve_text(tr, d.get("name"), name),
        "description": resolve_text(tr, d.get("description")),
        "wanted_tags": wanted_tags,
        "banned_item_groups": banned_item_groups,
        "flat_bonuses": flat_bonuses,
        "gain_modifiers": gain_modifiers,
        "special_effects": special_effects,
        "class_bonuses": class_bonuses,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_build_characters.py -v`
Expected: PASS (all, including the four new tests and the pre-existing ones).

- [ ] **Step 5: Thread `set_names` in the build orchestrator**

In `build_dataset.py`, move the `sets = [...]` block (currently at lines 132-138) to **above** the `characters = []` loop, then build a name map and pass it in. The two blocks become, in this order:

```python
    sets = [
        build_set_record(
            _read(e["set_data_path"]),
            {c: _read(p) for c, p in e["count_effect_paths"].items()},
            set_id=e["set_id"], name=e["name"], tr=tr)
        for e in discover.find_set_dirs(args.extracted)
    ]
    set_names = {s["id"]: s["display_name"] for s in sets}

    characters = []
    for e in discover.find_character_dirs(args.extracted):
        data_text = _read(e["data_path"])
        res = parse_tres(data_text).resource
        characters.append(build_character_record(
            data_text, [_read(p) for p in e["effect_paths"]],
            char_id=e["char_id"], name=e["name"],
            wanted_tags=res.get("wanted_tags", []) or [],
            banned_item_groups=res.get("banned_item_groups", []) or [],
            tr=tr, set_names=set_names))
```

- [ ] **Step 6: Lint and commit**

Run: `uv run ruff check brotato_coach/builders/characters.py build_dataset.py tests/test_build_characters.py`
Expected: no errors.

```bash
git add brotato_coach/builders/characters.py build_dataset.py tests/test_build_characters.py
git commit -m "feat(build): capture ClassBonusEffect kits as structured class_bonuses

The character builder's catch-all dropped ClassBonusEffect payloads,
keeping only the opaque key. Emit a structured class_bonuses entry
(set_id, set_name, stat, stat_displayed, value) instead, resolving the
set display name from a set_names map (title-cased fallback). Removes the
effect_weapon_class_bonus token from special_effects for all 6 affected
characters.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Advisory synergy helper + `evaluate_run` section

**Files:**
- Modify: `brotato_coach/answers.py` (add `character_class_synergy`; call it in `evaluate_run`)
- Test: `tests/test_answers.py`, `tests/test_run_report.py`

**Interfaces:**
- Consumes: character records with `class_bonuses` (Task 1); `query.get_character`, `query.get_weapon`.
- Produces: `character_class_synergy(ds: dict, character: str, weapon_names: list[str]) -> dict` returning `{"character": str, "bonuses": [ {set_id, set_name, stat, stat_displayed, value, "matched_weapons": [str]} ]}`. `evaluate_run` result gains a `"class_synergy"` key holding that dict.

- [ ] **Step 1: Write the failing helper test**

Append to `tests/test_answers.py`:

```python
def test_character_class_synergy_matches_weapons_in_bonus_set():
    ds = {
        "characters": [
            {"id": "character_crazy", "name": "Crazy", "class_bonuses": [
                {"set_id": "set_precise", "set_name": "Precise",
                 "stat": "max_range", "stat_displayed": "stat_range",
                 "value": 100}]},
            {"id": "character_plain", "name": "Plain", "class_bonuses": []},
        ],
        "weapons": [
            {"id": "weapon_knife", "name": "Knife", "tier": 1, "sets": ["Precise"]},
            {"id": "weapon_pistol", "name": "Pistol", "tier": 1, "sets": ["Gun"]},
        ],
    }
    out = answers.character_class_synergy(ds, "Crazy", ["Knife", "Pistol"])
    assert out["character"] == "Crazy"
    assert len(out["bonuses"]) == 1
    b = out["bonuses"][0]
    assert b["value"] == 100 and b["stat_displayed"] == "stat_range"
    assert b["matched_weapons"] == ["Knife"]


def test_character_class_synergy_empty_for_character_without_bonus():
    ds = {
        "characters": [{"id": "character_plain", "name": "Plain",
                        "class_bonuses": []}],
        "weapons": [{"id": "weapon_knife", "name": "Knife", "tier": 1,
                     "sets": ["Precise"]}],
    }
    out = answers.character_class_synergy(ds, "Plain", ["Knife"])
    assert out["bonuses"] == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_answers.py -k class_synergy -v`
Expected: FAIL — `AttributeError: module 'brotato_coach.answers' has no attribute 'character_class_synergy'`.

- [ ] **Step 3: Implement the helper**

Add to `brotato_coach/answers.py` (place it just above `def evaluate_run`):

```python
def character_class_synergy(ds: dict, character: str, weapon_names: list[str]) -> dict:
    """Which equipped weapons benefit from the character's class bonuses.

    A ClassBonusEffect grants `value` of a stat to weapons of a given set
    (e.g. Crazy: +100 range to Precise weapons). This joins the character's
    class_bonuses to `weapon_names` by set membership. Advisory only — it does
    NOT alter any DPS number (range/attack-speed/lifesteal are not in the
    RD-only DPS line; see the read_me primer)."""
    rec = query.get_character(ds, character)
    bonuses = rec.get("class_bonuses", []) if "id" in rec else []
    out = []
    for b in bonuses:
        matched = []
        for name in weapon_names:
            w = query.get_weapon(ds, name)
            if "matches" in w:
                w = w["matches"][0]  # set membership is tier-independent
            if "id" not in w:
                continue
            if b.get("set_name") in (w.get("sets") or []):
                matched.append(w["name"])
        out.append({**b, "matched_weapons": matched})
    return {"character": rec.get("name", character), "bonuses": out}
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_answers.py -k class_synergy -v`
Expected: PASS.

- [ ] **Step 5: Write the failing `evaluate_run` test**

Append to `tests/test_run_report.py`:

```python
import copy

DS_RANGER_CLASS_BONUS = copy.deepcopy(DS)
DS_RANGER_CLASS_BONUS["characters"][0]["class_bonuses"] = [
    {"set_id": "set_gun", "set_name": "Gun", "stat": "damage",
     "stat_displayed": "stat_damage", "value": 10}]


def test_evaluate_run_reports_class_synergy():
    r = answers.evaluate_run(DS_RANGER_CLASS_BONUS, _run())
    synergy = r["class_synergy"]
    assert synergy["character"] == "Ranger"
    assert synergy["bonuses"][0]["set_name"] == "Gun"
    # both equipped Gun weapons benefit
    assert sorted(synergy["bonuses"][0]["matched_weapons"]) == ["Pistol", "SMG"]


def test_evaluate_run_class_synergy_empty_without_bonus():
    r = answers.evaluate_run(DS, _run())
    assert r["class_synergy"]["bonuses"] == []
```

- [ ] **Step 6: Run to verify it fails**

Run: `uv run pytest tests/test_run_report.py -k class_synergy -v`
Expected: FAIL — `KeyError: 'class_synergy'`.

- [ ] **Step 7: Wire the section into `evaluate_run`**

In `brotato_coach/answers.py`, inside `evaluate_run`, after the `set_bonuses = loadout_set_bonuses(ds, weapon_ids)` block (around line 192), add:

```python
    class_synergy = character_class_synergy(ds, build["character"], weapon_ids)
```

Then add to the returned dict (after the `"set_bonuses": set_bonuses,` line):

```python
        "class_synergy": class_synergy,
```

- [ ] **Step 8: Run to verify it passes**

Run: `uv run pytest tests/test_run_report.py tests/test_answers.py -v`
Expected: PASS (all).

- [ ] **Step 9: Lint and commit**

Run: `uv run ruff check brotato_coach/answers.py tests/test_answers.py tests/test_run_report.py`
Expected: no errors.

```bash
git add brotato_coach/answers.py tests/test_answers.py tests/test_run_report.py
git commit -m "feat(answers): advisory class-bonus synergy in evaluate_run

character_class_synergy joins a character's class_bonuses to an equipped
loadout by set membership; evaluate_run surfaces it as a class_synergy
section. Advisory only — no DPS number changes.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Schema bump, surfacing docstring, primer caveat, roadmap seed

**Files:**
- Modify: `brotato_coach/dataset.py:7` (`DATASET_VERSION`)
- Modify: `tests/test_dataset.py:55-56` (version assertion)
- Modify: `brotato_coach/server.py` (`get_character` docstring)
- Modify: `brotato_coach/orientation.py` (primer caveat)
- Modify: `docs/roadmap.md` (B seed)
- Test: `tests/test_dataset.py`

**Interfaces:**
- Consumes: nothing new. Produces: `DATASET_VERSION == 5`.

Note: `tests/test_shipped_dataset.py` asserts the version against the on-disk `data/brotato.json` and is updated in Task 4 (after the rebuild), so it stays green here.

- [ ] **Step 1: Update the schema-version test (failing)**

In `tests/test_dataset.py`, change the test at lines 55-56 to:

```python
def test_schema_version_is_5():
    assert _minimal()["schema_version"] == 5
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_dataset.py -k schema_version -v`
Expected: FAIL — asserts 5 but constant is still 4.

- [ ] **Step 3: Bump the constant**

In `brotato_coach/dataset.py:7`, change:

```python
DATASET_VERSION = 5  # was 4 (added character class_bonuses)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_dataset.py -v`
Expected: PASS.

- [ ] **Step 5: Update `get_character` docstring**

In `brotato_coach/server.py`, replace the `get_character` docstring (lines 76-78) with:

```python
        """Look up one character's kit: wanted_tags, banned_item_groups,
        flat_bonuses, gain_modifiers (stat-gain multipliers), special_effects,
        and class_bonuses (conditional per-weapon-set stat bonuses, e.g. Crazy's
        +100 range to Precise weapons). Use this to know what a character wants
        and can't use before evaluating a build."""
```

- [ ] **Step 6: Add the primer caveat**

In `brotato_coach/orientation.py`, in the `PRIMER` string's "Using the tools" section, immediately after the bullet ending `run.json to evaluate_run.` (the `weapon_dps / compare_weapons` bullet, ~line 174), add a new bullet:

```
- **Class bonuses are build context, not DPS deltas.** A character's
  class_bonuses (e.g. Crazy's +100 range to Precise weapons) grant a stat to
  weapons of one set. The RD-only DPS line does NOT consume range,
  attack-speed, or lifesteal, so these do not move weapon_dps numbers — read
  them from get_character or evaluate_run's class_synergy section as synergy
  guidance (favor the boosted set), not as a DPS change.
```

- [ ] **Step 7: Add the roadmap seed**

In `docs/roadmap.md`, under `## Bigger build`, add a new bullet:

```
- **DPS engine beyond ranged damage** — the DPS model is RD-only
  (`calc.dps_line` + `builders/weapons.py:_rd_coefficient`): it consumes only
  ranged_damage, ignoring melee / percent / elemental damage scaling. Origin:
  it was built while grinding Ranger. Consequence: 35 of 36 Precise weapons
  have a zero RD slope (melee-scaling), so for melee/crit characters like Crazy
  the `dps(rd)` lines are near-flat constants and class-bonus stats (range,
  attack-speed, lifesteal) cannot enter the line at all. A stat-aware DPS model
  would parameterize by the weapon's real scaling stat and fold in flat/percent
  damage — a larger change that touches every weapon number; its own spec.
```

- [ ] **Step 8: Lint and commit**

Run: `uv run ruff check brotato_coach/dataset.py brotato_coach/server.py brotato_coach/orientation.py tests/test_dataset.py`
Expected: no errors.

```bash
git add brotato_coach/dataset.py brotato_coach/server.py brotato_coach/orientation.py docs/roadmap.md tests/test_dataset.py
git commit -m "feat: schema v5 for class_bonuses; surfacing + primer caveat + roadmap

Bump DATASET_VERSION to 5 (character class_bonuses field). Document the
field on get_character, add a read_me primer caveat that class bonuses are
build context (range/AS/lifesteal not in the RD-only DPS line), and seed
the roadmap with the deferred stat-aware-DPS engine work.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Rebuild dataset + full verification

**Files:**
- Regenerate (not committed): `data/brotato.json`
- Modify: `tests/test_shipped_dataset.py` (version assertion + a Crazy class-bonus assertion)

**Interfaces:**
- Consumes: everything above. Produces: a rebuilt `data/brotato.json` at schema 5 with populated `class_bonuses`.

- [ ] **Step 1: Rebuild the dataset**

Run: `uv run python build_dataset.py`
Expected: completes; prints the character/set/record counts line.

- [ ] **Step 2: Spot-check the rebuilt data**

Run:
```bash
uv run python -c "import json; d=json.load(open('data/brotato.json')); c=[x for x in d['characters'] if x['id']=='character_crazy'][0]; print(d['schema_version']); print(c['class_bonuses']); print('token gone:', 'effect_weapon_class_bonus' not in c['special_effects'])"
```
Expected: `5`; a single class-bonus entry with `set_name` "Precise", `stat` "max_range", `value` 100; `token gone: True`.

- [ ] **Step 3: Update the shipped-dataset test (failing before rebuild-aware assertions)**

In `tests/test_shipped_dataset.py`, update the version assertion (lines 72-73) and add a class-bonus assertion:

```python
    # schema_version 5 = character class_bonuses (4 was enemies + zone_1_waves)
    assert ds["schema_version"] == 5
```

Add a new test in the same file:

```python
def test_crazy_has_precise_range_class_bonus(shipped_ds):
    crazy = next(c for c in shipped_ds["characters"]
                 if c["id"] == "character_crazy")
    assert {"set_id": "set_precise", "set_name": "Precise",
            "stat": "max_range", "stat_displayed": "stat_range",
            "value": 100} in crazy["class_bonuses"]
```

Note: use the same dataset fixture the other tests in this file use (inspect the file header — if they read `data/brotato.json` via a `shipped_ds` fixture, reuse it; if they load inline, match that pattern).

- [ ] **Step 4: Run the full suite + lint**

Run: `uv run pytest`
Expected: PASS (entire suite).

Run: `uv run ruff check .`
Expected: no errors.

- [ ] **Step 5: Commit the test update**

```bash
git add tests/test_shipped_dataset.py
git commit -m "test: assert schema v5 and Crazy's precise-range class bonus in shipped data

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 6: End-to-end verification via the running server path**

Confirm the gap is actually closed the way a session sees it:

```bash
uv run python -c "
import json
from brotato_coach import answers
ds = json.load(open('data/brotato.json'))
print(answers.character_class_synergy(ds, 'Crazy', ['Knife','Dagger','Shuriken','Icicle']))
"
```
Expected: bonuses list with the +100 range Precise entry and `matched_weapons` containing the Precise weapons among those passed (Knife, Dagger, Shuriken).

---

## Self-Review

**Spec coverage:**
- Schema `class_bonuses` field + v4→v5 bump → Task 1 (field), Task 3 (bump). ✓
- Builder detection/discriminator + set_name resolution + token removal → Task 1. ✓
- Advisory `character_class_synergy` + `evaluate_run` section → Task 2. ✓
- Surfacing (`get_character` docstring, primer caveat) → Task 3. ✓
- Roadmap seed → Task 3. ✓
- Tests at builder/answers/schema/shipped layers → Tasks 1-4. ✓
- Dataset rebuild → Task 4. ✓
- Out-of-scope (no DPS change) honored: no task touches `calc.py`/`weapons.py` DPS math. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. The one soft instruction (Task 4 Step 3 "match the fixture pattern") is guarded with an explicit inspect-and-reuse directive because the fixture style must be read at execution time.

**Type consistency:** `class_bonuses` entry shape `{set_id, set_name, stat, stat_displayed, value}` is identical in Task 1 (builder), Task 2 (tests + helper spread `{**b, ...}`), and Task 4 (shipped assertion). `character_class_synergy` signature and return match between Task 2 definition and its `evaluate_run` call. `set_names` param name matches between `characters.py` and `build_dataset.py`.
