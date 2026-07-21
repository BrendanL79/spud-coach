# DLC Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the dataset pipeline now — before the Abyssal Terrors DLC exists — so DLC-day is a triage list, not an archaeology dig: provenance tagging, silent-drop-eliminating coverage reporting, a dataset diff harness, and an executable incorporation playbook.

**Architecture:** Additive, defaults-to-base changes. Every record gains a `source` field (stamped by a one-function detector that returns `"base"` until taught the real DLC signal). The build gains a coverage report (new content trees / weapon kinds / zones vs a calibrated 1.1.15.4 baseline) plus an aggregated unmodeled-effects report, gated by an opt-in `--strict`. A standalone `tools/diff_dataset.py` diffs two local dataset JSONs. A new playbook doc drives DLC-day execution.

**Tech Stack:** Python 3.11+, `uv`, pytest, ruff. Pure-logic modules with unit tests against hand-built fixtures (no DLC data required to build or test any of this).

## Global Constraints

- Python 3.11+; managed with **uv**. Test: `uv run pytest`. Lint (keep green): `uv run ruff check .`.
- **TDD is mandatory** — write the failing test first, watch it fail, then implement.
- **Never commit or redistribute** `data/brotato.json`, `extracted/`, `recovered/`, `game_files/` (all gitignored, copyright-derived). The diff harness operates on two *local* dataset files; it commits no baseline.
- The MCP server reads only `data/brotato.json`; only the build step reads `extracted/`. Preserve this one-way flow.
- Schema bump is a single **v6 → v7** covering the `source` field + root `content_sources`.
- Commit style: conventional commits (`feat:`, `test:`, `docs:`, `chore:`), matching repo history.
- Coverage baseline constants are a **snapshot of Brotato 1.1.15.4** (verified against the current `extracted/`, which Brendan has backed up). Comment them as such; extend when new content is triaged.

---

## File Structure

- **Create** `brotato_coach/builders/provenance.py` — `detect_source()`, the single provenance seam.
- **Modify** `brotato_coach/dataset.py` — `DATASET_VERSION=7`; `assemble_dataset` adds `content_sources`; `validate_dataset` requires per-record `source` + top-level `content_sources`; new pure `aggregate_unmodeled_effects()`.
- **Modify** `brotato_coach/builders/discover.py` — new `coverage_report()` + calibrated baseline constants.
- **Modify** `build_dataset.py` — stamp `source` on every record; print coverage/unmodeled report; `--strict` gate.
- **Create** `tools/diff_dataset.py` — dataset-vs-dataset diff harness (dev tool, no MCP surface).
- **Create** `docs/dlc-incorporation-playbook.md` — DLC-day execution playbook.
- **Tests:** `tests/test_build_provenance.py`, `tests/test_diff_dataset.py` (new); edits to `tests/test_dataset.py`, `tests/test_build_discover.py`, `tests/test_build_dataset_paths.py`.

Tasks are ordered so each builds only on earlier ones. Interfaces are pinned per task.

---

### Task 1: Provenance detector

**Files:**
- Create: `brotato_coach/builders/provenance.py`
- Test: `tests/test_build_provenance.py`

**Interfaces:**
- Produces: `detect_source(*, record: dict | None = None, entry: dict | None = None) -> str` — returns `"base"` today.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_build_provenance.py
from brotato_coach.builders.provenance import detect_source


def test_detect_source_defaults_to_base():
    assert detect_source(record={"id": "weapon_pistol"}) == "base"
    assert detect_source(entry={"weapon_id": "weapon_pistol"}) == "base"
    assert detect_source() == "base"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_build_provenance.py -v`
Expected: FAIL (`ModuleNotFoundError: brotato_coach.builders.provenance`).

- [ ] **Step 3: Write minimal implementation**

```python
# brotato_coach/builders/provenance.py
from __future__ import annotations


def detect_source(*, record: dict | None = None, entry: dict | None = None) -> str:
    """Return a record's content origin: "base" or a DLC id (e.g. "abyssal_terrors").

    Ships defaulting to "base" for everything. On DLC day, teach THIS ONE
    function the real signal, in priority order (see
    docs/dlc-incorporation-playbook.md):

      1. Extraction origin (most likely + cleanest): if the DLC ships as a
         separate .pck, unpack it into a marked tree and pass the origin in via
         `entry`; echo it here.
      2. In-.tres flag / unlock gate: a `dlc`/`unlock` field readable off
         `record`.
      3. Directory prefix: a DLC-specific path segment (e.g. "abyssal/") on the
         record's source paths.

    Until taught, every record is base-game content.
    """
    return "base"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_build_provenance.py -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check brotato_coach/builders/provenance.py tests/test_build_provenance.py
git add brotato_coach/builders/provenance.py tests/test_build_provenance.py
git commit -m "feat(build): add detect_source provenance seam (defaults to base)"
```

---

### Task 2: Schema v7 — `source` + `content_sources` + unmodeled aggregation

**Files:**
- Modify: `brotato_coach/dataset.py`
- Test: `tests/test_dataset.py`

**Interfaces:**
- Consumes: records already carrying `"source"` (stamped in Task 3; tests here supply it directly).
- Produces:
  - `DATASET_VERSION == 7`
  - `assemble_dataset(...)` output gains `"content_sources": list[str]` (sorted union of record sources, or `["base"]` if none).
  - `validate_dataset(ds)` flags any record missing `source` and a missing top-level `content_sources`.
  - `aggregate_unmodeled_effects(ds: dict) -> dict[str, list[str]]` — source → sorted unique unmodeled effect keys.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dataset.py`:

```python
def test_schema_version_is_7():
    assert _minimal()["schema_version"] == 7


def test_content_sources_defaults_to_base_when_empty():
    assert _minimal()["content_sources"] == ["base"]


def test_content_sources_reflects_record_sources():
    ds = _minimal(
        weapons=[{"id": "w", "name": "W", "tier": 1, "weapon_type": "ranged",
                  "base_damage": 5, "cooldown": 60, "source": "base"}],
        items=[{"id": "i", "name": "I", "effects": [], "source": "abyssal_terrors"}])
    assert ds["content_sources"] == ["abyssal_terrors", "base"]


def test_validate_flags_missing_source():
    ds = _minimal(enemies=[{"id": "baby_alien", "name": "Baby Alien"}])  # no source
    problems = dataset.validate_dataset(ds)
    assert any("source" in p for p in problems)


def test_aggregate_unmodeled_effects_buckets_by_source():
    ds = _minimal(
        weapons=[{"id": "w", "name": "W", "tier": 1, "weapon_type": "ranged",
                  "base_damage": 5, "cooldown": 60, "source": "abyssal_terrors",
                  "unmodeled_effects": ["mystery_curse", "mystery_curse", "abyssal_x"]}])
    agg = dataset.aggregate_unmodeled_effects(ds)
    assert agg == {"abyssal_terrors": ["abyssal_x", "mystery_curse"]}


def test_aggregate_unmodeled_effects_empty_when_all_modeled():
    assert dataset.aggregate_unmodeled_effects(_minimal()) == {}
```

Then update the three existing tests that assert a clean dataset, so their records carry `source` and the version assertion matches:

- In `test_assemble_and_validate_ok`: add `"source": "base"` to both the `weapon` and `item` dicts.
- In `test_enemies_and_waves_present_in_output`: change the enemy to `{"id": "baby_alien", "name": "Baby Alien", "source": "base"}` and the wave to `{"wave": 1, "groups": [{"enemy_id": "baby_alien"}], "source": "base"}`.
- Delete `test_schema_version_is_6` (replaced by `test_schema_version_is_7` above).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_dataset.py -v`
Expected: FAIL — `test_schema_version_is_7` (still 6), `content_sources` KeyError, `aggregate_unmodeled_effects` AttributeError, missing-source not flagged.

- [ ] **Step 3: Implement in `brotato_coach/dataset.py`**

Change the version constant:

```python
DATASET_VERSION = 7  # was 6 (per-record `source` + root `content_sources`)
```

Replace `assemble_dataset` with:

```python
def assemble_dataset(*, game_version: str, generated_at: str, weapons: list,
                     items: list, characters: list, sets: list,
                     enemies: list, zone_1_waves: list) -> dict:
    all_records = [*weapons, *items, *characters, *sets, *enemies, *zone_1_waves]
    content_sources = sorted({r["source"] for r in all_records if "source" in r}) or ["base"]
    return {
        "schema_version": DATASET_VERSION,
        "game_version": game_version,
        "generated_at": generated_at,
        "content_sources": content_sources,
        "stat_mechanics": STAT_MECHANICS,
        "weapons": weapons,
        "items": items,
        "characters": characters,
        "sets": sets,
        "enemies": enemies,
        "zone_1_waves": zone_1_waves,
    }
```

In `validate_dataset`, add `"content_sources"` to the top-level required-key tuple:

```python
    problems: list[str] = [
        f"missing top-level key: {key}"
        for key in ("schema_version", "game_version", "content_sources", "weapons",
                    "items", "characters", "sets", "enemies", "zone_1_waves")
        if key not in dataset
    ]
```

Then, just before `return problems`, add the per-record source check:

```python
    for coll_name in ("weapons", "items", "characters", "sets", "enemies", "zone_1_waves"):
        for rec in dataset.get(coll_name, []):
            if "source" not in rec:
                rid = rec.get("id") or rec.get("name") or rec.get("wave", "<unknown>")
                problems.append(f"{coll_name} record {rid} missing source")

    return problems
```

Add the new pure aggregator (module-level, e.g. after `validate_dataset`):

```python
def aggregate_unmodeled_effects(dataset: dict) -> dict[str, list[str]]:
    """Map content source -> sorted unique unmodeled effect keys across all
    records. Empty when every effect is modeled or classified (the base-game
    state today). A DLC introducing new effect scripts populates it as the
    modeling worklist, bucketed by origin."""
    by_source: dict[str, set[str]] = {}
    for coll in ("weapons", "items", "characters", "sets", "enemies"):
        for rec in dataset.get(coll, []):
            src = rec.get("source", "base")
            for key in rec.get("unmodeled_effects", []) or []:
                by_source.setdefault(src, set()).add(str(key))
    return {src: sorted(keys) for src, keys in sorted(by_source.items())}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_dataset.py -v`
Expected: PASS (all, including the edited existing tests).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check brotato_coach/dataset.py tests/test_dataset.py
git add brotato_coach/dataset.py tests/test_dataset.py
git commit -m "feat(schema): v7 adds per-record source + content_sources; aggregate_unmodeled_effects"
```

---

### Task 3: Stamp `source` on every record in the build

**Files:**
- Modify: `build_dataset.py`
- Test: `tests/test_build_dataset_paths.py`

**Interfaces:**
- Consumes: `detect_source` (Task 1).
- Produces: module-level `_stamp_sources(*record_lists: list) -> None` — mutates each record in place, setting `rec["source"] = detect_source(record=rec)`. Called in `main()` after all record lists are built and before `assemble_dataset`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_build_dataset_paths.py`:

```python
def test_stamp_sources_sets_base_on_every_record():
    import build_dataset
    weapons = [{"id": "w1"}, {"id": "w2"}]
    enemies = [{"id": "e1"}]
    build_dataset._stamp_sources(weapons, enemies, [])
    assert all(r["source"] == "base" for r in weapons)
    assert enemies[0]["source"] == "base"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_build_dataset_paths.py::test_stamp_sources_sets_base_on_every_record -v`
Expected: FAIL (`AttributeError: module 'build_dataset' has no attribute '_stamp_sources'`).

- [ ] **Step 3: Implement in `build_dataset.py`**

Add the import near the other builder imports:

```python
from brotato_coach.builders.provenance import detect_source
```

Add the helper at module level (e.g. after `resolve_recovered_paths`):

```python
def _stamp_sources(*record_lists) -> None:
    """Tag every built record with its content origin. Today detect_source
    returns "base" for all; on DLC day it learns the real signal (see
    provenance.py) and this stamps records without further plumbing changes."""
    for records in record_lists:
        for rec in records:
            rec["source"] = detect_source(record=rec)
```

In `main()`, immediately before the `ds = dataset.assemble_dataset(...)` call, insert:

```python
    _stamp_sources(weapons, items, characters, sets, enemies, zone_1_waves)

```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_build_dataset_paths.py -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check build_dataset.py tests/test_build_dataset_paths.py
git add build_dataset.py tests/test_build_dataset_paths.py
git commit -m "feat(build): stamp source on every record before assemble"
```

---

### Task 4: Coverage report in discovery

**Files:**
- Modify: `brotato_coach/builders/discover.py`
- Test: `tests/test_build_discover.py`

**Interfaces:**
- Produces: `coverage_report(extracted_root: str) -> dict[str, list[str]]` with keys `unclaimed_trees`, `unknown_weapon_kinds`, `unmodeled_zones` (each a sorted list; all empty on the 1.1.15.4 base extraction).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_build_discover.py`:

```python
def test_coverage_report_empty_on_baseline_dirs(tmp_path):
    from brotato_coach.builders.discover import coverage_report
    # Only accounted-for baseline dirs present.
    for name in ("weapons", "items", "entities", "zones", "challenges", "ui", "effects"):
        (tmp_path / name).mkdir()
    (tmp_path / "weapons" / "melee").mkdir()
    (tmp_path / "weapons" / "ranged").mkdir()
    (tmp_path / "weapons" / "weapon_stats").mkdir()
    (tmp_path / "zones" / "zone_1").mkdir()
    (tmp_path / "zones" / "zone_2").mkdir()
    (tmp_path / "zones" / "common").mkdir()
    report = coverage_report(str(tmp_path))
    assert report == {"unclaimed_trees": [], "unknown_weapon_kinds": [], "unmodeled_zones": []}


def test_coverage_report_flags_new_content(tmp_path):
    from brotato_coach.builders.discover import coverage_report
    (tmp_path / "abyssal").mkdir()                       # new top-level tree
    (tmp_path / "weapons").mkdir()
    (tmp_path / "weapons" / "thrown").mkdir()            # new weapon kind
    (tmp_path / "zones").mkdir()
    (tmp_path / "zones" / "zone_4").mkdir()              # new zone
    report = coverage_report(str(tmp_path))
    assert report["unclaimed_trees"] == ["abyssal"]
    assert report["unknown_weapon_kinds"] == ["thrown"]
    assert report["unmodeled_zones"] == ["zone_4"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_build_discover.py -k coverage_report -v`
Expected: FAIL (`ImportError: cannot import name 'coverage_report'`).

- [ ] **Step 3: Implement in `brotato_coach/builders/discover.py`**

Add near the top (after the existing imports / id-prefix constants):

```python
# Baseline snapshot of Brotato 1.1.15.4's extracted/ layout (verified against
# the current extraction). coverage_report() flags anything NOT in these sets —
# empty on the base game, non-empty when a game/DLC update adds a new content
# tree, weapon kind, or zone. Extend a set only when its new content has been
# triaged into the build.
_ACCOUNTED_TOP_LEVEL = frozenset({
    "addons", "challenges", "effect_behaviors", "effects", "entities", "global",
    "items", "overlap", "particles", "projectiles", "resources", "singletons",
    "tools", "ui", "visual_effects", "weapons", "zones",
})
_ACCOUNTED_WEAPON_SUBDIRS = frozenset({
    "melee", "ranged", "melee_sounds", "shooting_behaviors", "weapon_stats",
})
# zone_1 is modeled; zone_2/zone_3 are present-but-unmodeled (roadmap-tracked);
# backgrounds/common are non-wave assets. All accounted for, so the base build
# stays clean and only a genuinely new zone surfaces.
_ACCOUNTED_ZONE_SUBDIRS = frozenset({
    "zone_1", "zone_2", "zone_3", "backgrounds", "common",
})


def _immediate_subdirs(path: str) -> set[str]:
    if not os.path.isdir(path):
        return set()
    return {n for n in os.listdir(path) if os.path.isdir(os.path.join(path, n))}


def coverage_report(extracted_root: str) -> dict[str, list[str]]:
    """New content trees / weapon kinds / zones not in the 1.1.15.4 baseline.

    Empty on the base game. A DLC (or major patch) that introduces a new
    top-level content tree, a new weapon kind, or a new zone surfaces it here so
    the build can report — and, under --strict, refuse to ship — un-triaged
    content instead of silently dropping it.
    """
    return {
        "unclaimed_trees": sorted(
            _immediate_subdirs(extracted_root) - _ACCOUNTED_TOP_LEVEL),
        "unknown_weapon_kinds": sorted(
            _immediate_subdirs(os.path.join(extracted_root, "weapons"))
            - _ACCOUNTED_WEAPON_SUBDIRS),
        "unmodeled_zones": sorted(
            _immediate_subdirs(os.path.join(extracted_root, "zones"))
            - _ACCOUNTED_ZONE_SUBDIRS),
    }
```

(`os` is already imported at the top of `discover.py`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_build_discover.py -k coverage_report -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check brotato_coach/builders/discover.py tests/test_build_discover.py
git add brotato_coach/builders/discover.py tests/test_build_discover.py
git commit -m "feat(build): coverage_report flags new trees/weapon-kinds/zones vs 1.1.15.4 baseline"
```

---

### Task 5: Build-time coverage/unmodeled report + `--strict`

**Files:**
- Modify: `build_dataset.py`
- Test: `tests/test_build_dataset_paths.py`

**Interfaces:**
- Consumes: `discover.coverage_report` (Task 4), `dataset.aggregate_unmodeled_effects` (Task 2).
- Produces:
  - `_coverage_report_lines(coverage: dict, unmodeled_by_source: dict) -> list[str]` — human-readable report lines (empty when nothing to report).
  - `_has_blocking_issues(coverage: dict, unmodeled_by_source: dict) -> bool` — True if any coverage list is non-empty OR any source has unmodeled effects.
  - `main()` accepts `--strict`; on issues it prints the report and, under `--strict`, returns `1` without writing the dataset.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_build_dataset_paths.py`:

```python
def test_has_blocking_issues_true_on_new_tree():
    import build_dataset
    coverage = {"unclaimed_trees": ["abyssal"], "unknown_weapon_kinds": [], "unmodeled_zones": []}
    assert build_dataset._has_blocking_issues(coverage, {}) is True


def test_has_blocking_issues_true_on_unmodeled_effect():
    import build_dataset
    empty = {"unclaimed_trees": [], "unknown_weapon_kinds": [], "unmodeled_zones": []}
    assert build_dataset._has_blocking_issues(empty, {"abyssal_terrors": ["curse_x"]}) is True


def test_has_blocking_issues_false_when_clean():
    import build_dataset
    empty = {"unclaimed_trees": [], "unknown_weapon_kinds": [], "unmodeled_zones": []}
    assert build_dataset._has_blocking_issues(empty, {}) is False


def test_coverage_report_lines_summarizes():
    import build_dataset
    coverage = {"unclaimed_trees": ["abyssal"], "unknown_weapon_kinds": [], "unmodeled_zones": ["zone_4"]}
    lines = build_dataset._coverage_report_lines(coverage, {"abyssal_terrors": ["curse_x", "curse_y"]})
    text = "\n".join(lines)
    assert "abyssal" in text
    assert "zone_4" in text
    assert "abyssal_terrors" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_build_dataset_paths.py -k "blocking or report_lines" -v`
Expected: FAIL (attributes don't exist).

- [ ] **Step 3: Implement in `build_dataset.py`**

Ensure `discover` is imported (it already is: `from brotato_coach.builders import discover`). Add the two pure helpers at module level:

```python
def _coverage_report_lines(coverage: dict, unmodeled_by_source: dict) -> list[str]:
    lines: list[str] = []
    for label, key in (("new content trees", "unclaimed_trees"),
                       ("new weapon kinds", "unknown_weapon_kinds"),
                       ("new/unmodeled zones", "unmodeled_zones")):
        vals = coverage.get(key) or []
        if vals:
            lines.append(f"  {label}: {', '.join(vals)}")
    for src, keys in (unmodeled_by_source or {}).items():
        if keys:
            shown = ", ".join(keys[:8]) + ("…" if len(keys) > 8 else "")
            lines.append(f"  unmodeled effects [{src}]: {len(keys)} ({shown})")
    return lines


def _has_blocking_issues(coverage: dict, unmodeled_by_source: dict) -> bool:
    if any(coverage.get(k) for k in
           ("unclaimed_trees", "unknown_weapon_kinds", "unmodeled_zones")):
        return True
    return any(bool(v) for v in (unmodeled_by_source or {}).values())
```

Add the `--strict` argument alongside the other `parser.add_argument(...)` calls:

```python
    parser.add_argument(
        "--strict", action="store_true",
        help="fail the build (exit 1, no write) if coverage finds new content "
             "trees/weapon-kinds/zones or any unmodeled effect")
```

In `main()`, after the existing `problems = dataset.validate_dataset(ds)` block returns cleanly and **before** the file is written (i.e. before `out_dir = os.path.dirname(args.out)`), insert:

```python
    coverage = discover.coverage_report(args.extracted)
    unmodeled = dataset.aggregate_unmodeled_effects(ds)
    report_lines = _coverage_report_lines(coverage, unmodeled)
    if report_lines:
        print("Coverage / unmodeled-content report:", file=sys.stderr)
        for line in report_lines:
            print(line, file=sys.stderr)
        if args.strict and _has_blocking_issues(coverage, unmodeled):
            print("Build failed (--strict): un-triaged content above; "
                  "triage or extend the baseline before shipping.", file=sys.stderr)
            return 1

```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_build_dataset_paths.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite + lint + commit**

Run: `uv run pytest -q && uv run ruff check .`
Expected: all green.

```bash
git add build_dataset.py tests/test_build_dataset_paths.py
git commit -m "feat(build): coverage/unmodeled report with opt-in --strict gate"
```

---

### Task 6: Dataset diff harness

**Files:**
- Create: `tools/diff_dataset.py`
- Test: `tests/test_diff_dataset.py`

**Interfaces:**
- Produces:
  - `diff_datasets(old: dict, new: dict) -> dict` — per-collection `{added, removed, changed}` plus `new_sources`, `new_unmodeled_effects`, `game_version`, `schema_version`.
  - `format_report(diff: dict) -> str`.
  - `main(argv=None) -> int` — CLI: `old new [--json]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_diff_dataset.py
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import diff_dataset  # noqa: E402


def _ds(**over):
    base = {"schema_version": 7, "game_version": "1.1.15.4", "content_sources": ["base"],
            "weapons": [], "items": [], "characters": [], "sets": [], "enemies": []}
    base.update(over)
    return base


def test_diff_detects_added_removed_changed_weapons():
    old = _ds(weapons=[{"id": "w_keep", "base_damage": 10, "source": "base"},
                       {"id": "w_gone", "base_damage": 5, "source": "base"}])
    new = _ds(weapons=[{"id": "w_keep", "base_damage": 12, "source": "base"},
                       {"id": "w_new", "base_damage": 8, "source": "abyssal_terrors"}],
              content_sources=["abyssal_terrors", "base"])
    diff = diff_dataset.diff_datasets(old, new)
    assert diff["weapons"]["added"] == ["w_new"]
    assert diff["weapons"]["removed"] == ["w_gone"]
    assert diff["weapons"]["changed"] == {"w_keep": {"base_damage": [10, 12]}}
    assert diff["new_sources"] == ["abyssal_terrors"]


def test_diff_collects_new_unmodeled_effects():
    old = _ds()
    new = _ds(weapons=[{"id": "w", "source": "abyssal_terrors",
                        "unmodeled_effects": ["curse_bind"]}])
    diff = diff_dataset.diff_datasets(old, new)
    assert diff["new_unmodeled_effects"] == ["curse_bind"]


def test_format_report_is_readable():
    old = _ds()
    new = _ds(game_version="1.2.0.0", weapons=[{"id": "w_new", "source": "base"}])
    text = diff_dataset.format_report(diff_dataset.diff_datasets(old, new))
    assert "1.1.15.4 -> 1.2.0.0" in text
    assert "w_new" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_diff_dataset.py -v`
Expected: FAIL (`ModuleNotFoundError: diff_dataset`).

- [ ] **Step 3: Implement `tools/diff_dataset.py`**

```python
"""Diff two brotato.json datasets to triage a game/DLC update.

Usage:
    python tools/diff_dataset.py OLD.json NEW.json [--json]

Neither file is committed (both are gitignored, copyright-derived data). Keep a
base-only build as OLD (e.g. data/brotato.base.json, regenerable from the
backed-up base extraction) and diff the post-update build against it.
"""
from __future__ import annotations

import argparse
import json

_COLLECTIONS = ("weapons", "items", "characters", "sets", "enemies")
_SCALAR = (int, float, str, bool)


def _by_id(records: list) -> dict:
    return {r.get("id"): r for r in records if r.get("id") is not None}


def _scalar_field_changes(old: dict, new: dict) -> dict:
    changes: dict = {}
    for k in sorted(set(old) | set(new)):
        ov, nv = old.get(k), new.get(k)
        if ov == nv:
            continue
        if isinstance(ov, _SCALAR) and isinstance(nv, _SCALAR):
            changes[k] = [ov, nv]
        else:
            changes[k] = "<complex field changed>"
    return changes


def diff_collection(old: list, new: list) -> dict:
    o, n = _by_id(old), _by_id(new)
    changed = {}
    for cid in sorted(set(o) & set(n)):
        ch = _scalar_field_changes(o[cid], n[cid])
        if ch:
            changed[cid] = ch
    return {"added": sorted(set(n) - set(o)),
            "removed": sorted(set(o) - set(n)),
            "changed": changed}


def _all_unmodeled(ds: dict) -> set[str]:
    keys: set[str] = set()
    for coll in _COLLECTIONS:
        for r in ds.get(coll, []):
            keys.update(str(k) for k in r.get("unmodeled_effects", []) or [])
    return keys


def diff_datasets(old: dict, new: dict) -> dict:
    result: dict = {coll: diff_collection(old.get(coll, []), new.get(coll, []))
                    for coll in _COLLECTIONS}
    result["new_sources"] = sorted(set(new.get("content_sources", []))
                                   - set(old.get("content_sources", [])))
    result["new_unmodeled_effects"] = sorted(_all_unmodeled(new) - _all_unmodeled(old))
    result["game_version"] = [old.get("game_version"), new.get("game_version")]
    result["schema_version"] = [old.get("schema_version"), new.get("schema_version")]
    return result


def format_report(diff: dict) -> str:
    gv = diff.get("game_version", [None, None])
    sv = diff.get("schema_version", [None, None])
    lines = [f"game_version: {gv[0]} -> {gv[1]}",
             f"schema_version: {sv[0]} -> {sv[1]}"]
    if diff.get("new_sources"):
        lines.append(f"new content_sources: {', '.join(diff['new_sources'])}")
    for coll in _COLLECTIONS:
        d = diff[coll]
        lines.append(f"\n{coll}: +{len(d['added'])} / -{len(d['removed'])} / ~{len(d['changed'])}")
        if d["added"]:
            lines.append(f"  added: {', '.join(d['added'])}")
        if d["removed"]:
            lines.append(f"  removed: {', '.join(d['removed'])}")
        for cid, ch in d["changed"].items():
            lines.append(f"  changed {cid}: {ch}")
    nu = diff.get("new_unmodeled_effects") or []
    lines.append(f"\nnew unmodeled effects ({len(nu)}): {', '.join(nu) if nu else '(none)'}")
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Diff two brotato.json datasets.")
    p.add_argument("old")
    p.add_argument("new")
    p.add_argument("--json", action="store_true", help="emit the diff as JSON")
    args = p.parse_args(argv)
    with open(args.old, encoding="utf-8") as fh:
        old = json.load(fh)
    with open(args.new, encoding="utf-8") as fh:
        new = json.load(fh)
    diff = diff_datasets(old, new)
    print(json.dumps(diff, indent=2) if args.json else format_report(diff))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_diff_dataset.py -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check tools/diff_dataset.py tests/test_diff_dataset.py
git add tools/diff_dataset.py tests/test_diff_dataset.py
git commit -m "feat(tools): add diff_dataset harness for game/DLC update triage"
```

---

### Task 7: DLC-day incorporation playbook

**Files:**
- Create: `docs/dlc-incorporation-playbook.md`

No test cycle (documentation). This task authors the executable DLC-day runbook now, while calm.

- [ ] **Step 1: Write `docs/dlc-incorporation-playbook.md`**

```markdown
# DLC / major-update incorporation playbook

Execute this when a Brotato DLC (or content patch) lands. It ingests new data
cleanly, tags provenance, and produces a triage list. It does **not** model new
mechanics — those are separate spec→plan→implement cycles (curse is the expected
first one, kicked off right after ingestion).

Prereq: the base-game snapshot (`game_files/`, `extracted/`, `recovered/` as of
1.1.15.4) is backed up locally, so a base-only dataset is always reproducible.

1. **Preserve the baseline.** Keep a base-only dataset to diff against. Either
   copy the current `data/brotato.json` → `data/brotato.base.json`, or rebuild
   it from the backed-up base extraction. Both stay local (gitignored).
2. **Re-copy game files.** Copy the updated `Brotato.pck` (and any DLC pack)
   from the Steam install into `game_files/`. **Confirm how the DLC ships** — is
   there a second `.pck`? This resolves the provenance mechanism (see step 5).
3. **Re-extract.** Run `unpack_pck.py` per pack → `extracted/`; run gdre_tools
   → `recovered/`. If the DLC is a separate pack, unpack it into a marked tree
   so origin is known by construction.
4. **Rebuild + read the report.** `uv run python build_dataset.py`. Read the
   "Coverage / unmodeled-content report" (new trees / weapon kinds / zones,
   and unmodeled effects). If a new content tree/kind/zone appears, extend the
   `_ACCOUNTED_*` sets in `discover.py` (after confirming it's real content) or
   the relevant discoverer.
5. **Teach `detect_source`.** In `brotato_coach/builders/provenance.py`, fill in
   the confirmed signal from step 2 (extraction origin > in-`.tres` flag >
   directory prefix). Rebuild; confirm `content_sources` now lists the DLC id.
6. **Diff.** `uv run python tools/diff_dataset.py data/brotato.base.json data/brotato.json`
   → the triage list (added/removed/changed records, new sources, new unmodeled
   effects).
7. **Triage.** New *records* mostly ingest for free. The real work is each its
   own spec→plan→implement cycle:
   - unknown effect scripts → the existing proc-worklist process
     (`docs/proc-mechanics.md`, `builders/procs.py`/`classifications.py`);
   - new mechanics (curse/elements) → new `docs/` mechanics writeups;
   - new zones/bosses → bestiary follow-up.
8. **Re-pin all evidence** against the NEW decompiled source. Never carry
   base-game citations forward — misattributed functions have shipped that way
   before.
9. **`read_me` caveat.** If `content_sources` includes a DLC and unmodeled
   effects exist, add/refresh the primer caveat in `brotato_coach/orientation.py`
   so the coach never presents un-modeled DLC content as verified. Write the
   wording against the *actual* unmodeled list from step 6.
10. **Stamp.** Bump `DATASET_VERSION` if the delta added fields; run the build
    with `--strict` to confirm the dataset is fully triaged; stamp `server.json`
    at release time.
11. **Deploy.** Regenerate the schema-matching `brotato.json` for spudcoach-chat
    and redeploy: `fly deploy -a spudcoach-2c57` (the `fly.toml` app name is a
    placeholder, so `-a` is required). Confirm the app name is still current.
```

- [ ] **Step 2: Commit**

```bash
git add docs/dlc-incorporation-playbook.md
git commit -m "docs: add DLC/major-update incorporation playbook"
```

---

## Final verification

- [ ] Run the full suite and linter:

```bash
uv run pytest -q && uv run ruff check .
```
Expected: all tests pass, ruff clean.

- [ ] **Rebuild the local dataset** (not committed) to confirm the real build is green end-to-end and the base game reports clean coverage:

```bash
uv run python build_dataset.py --strict
```
Expected: writes `data/brotato.json`, schema_version 7, `content_sources: ["base"]`, no coverage/unmodeled report lines (base game is fully accounted), exit 0.

---

## Self-review notes (author)

- **Spec coverage:** Section 1 → Tasks 1–3; Section 2 → Task 4 (narrowed to the three bounded, zero-base-noise signals — within-dir convention-failure reporting intentionally dropped as low-value/high-noise per real-extraction calibration); Section 3 → Task 6; Section 4 → Task 5 (the `read_me` caveat moved to playbook step 9 so its wording is written against real unmodeled effects); Section 5 → Task 7.
- **Deferred (update the committed spec to match):** narrower Section 2 scope; `read_me` caveat is playbook-time, not build-now.
- **Type consistency:** `detect_source(record=...)` used identically in Tasks 1/3; `coverage_report` keys (`unclaimed_trees`/`unknown_weapon_kinds`/`unmodeled_zones`) identical in Tasks 4/5; `aggregate_unmodeled_effects` return shape (`dict[str, list[str]]`) identical in Tasks 2/5/6 consumers.
