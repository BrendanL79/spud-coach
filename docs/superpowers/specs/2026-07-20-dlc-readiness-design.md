# DLC readiness — design

**Date:** 2026-07-20
**Status:** approved (brainstorming) — pending implementation plan
**Context:** Brendan will purchase the Abyssal Terrors DLC in the near future and
wants to capture and incorporate its data (new characters, weapons, weapon
classes, items, enemies, new zones, and at least one new mechanic layer —
curse/elements). This spec covers what we build **now**, before the DLC data
exists, to make DLC-day tractable.

## Guiding constraint

We have no DLC source to verify against yet. The project's ethos is "verify
against decompiled source; re-pin every citation at write time." Therefore we do
**not** speculatively model DLC shapes. Everything here is either (a) honest
plumbing that defaults to the base game and is fully testable today, or (b) a
tool/playbook that turns DLC-day from an archaeology dig into a triage list.

## Decisions locked (from brainstorming)

- **Deliverable:** proactive pipeline hardening **now** + a written DLC-day
  playbook. (Not "just a checklist" and not "speculative full build.")
- **Provenance:** *tag now, gate later* — every record carries a `source`
  field; no ownership-filtering UX is built yet.
- **Approach:** A (fail-loud honesty) + two targeted borrows from B
  (a provenance detector, and a light discovery-registry that eliminates
  silent-drop risk). Approach C (pre-modeling Abyssal specifics) rejected —
  unverifiable against absent source.
- **Modeling is out of scope** for the incorporation work. New mechanics
  (curse, elements), new-zone bestiary, and unknown effect scripts are each
  their own downstream spec→plan→implement cycle. Curse is the expected
  **first** follow-up cycle, kicked off right after ingestion — but still a
  separate cycle, not part of incorporation.

## Non-goals

- No gating UX (no MCP `owns_dlc` flag, no locked-content filtering). Deferred
  to `docs/roadmap.md` until real usage justifies it.
- No modeling of curse/elements/new zones in this work.
- No generic "auto-handle unknown entity type" machinery — discovery *reports*
  unknown content, it does not model it.
- No committed baseline or manifest derived from copyrighted data (see the diff
  harness — it compares two local, gitignored dataset files).

---

## Section 1 — Provenance (`source` field), schema v7

**Schema (single bump v6 → v7):**
- Every record (weapons, items, characters, sets, enemies, waves) gains
  `"source"` — `"base"` today, a DLC id (e.g. `"abyssal_terrors"`) once the
  detector is taught.
- Dataset root gains `"content_sources"`: a summary list, e.g. `["base"]` today,
  `["base", "abyssal_terrors"]` post-DLC — so `read_me` can state provenance
  honestly.
- `validate_dataset` asserts every record carries a `source`.

**Detector — `brotato_coach/builders/provenance.py`:** one function,
`detect_source(...) -> str`, shipping **defaulted to `"base"`**, with a docstring
enumerating candidate DLC-marking signals to confirm on DLC day, in priority
order:
1. **Extraction origin** (most likely + cleanest): if Abyssal Terrors ships as a
   separate `.pck`, provenance is simply which pack a file came from — captured
   at unpack time and passed into the build; the detector echoes it.
2. **In-`.tres` flag / unlock gate:** if content is patched into the main PCK,
   look for a `dlc`/`unlock`-style field or challenge-gated unlock.
3. **Directory prefix:** a DLC-specific subtree (e.g. an `abyssal/` segment).

Today: the field, the plumbing through every builder, the schema bump, and the
tests all land. DLC day: teach one function the real signal.

## Section 2 — Discovery hardening (silent-drop elimination)

`discover.py` today drops anything outside its hardcoded globs silently. Fixes:

| Leak | Today | Fix |
|------|-------|-----|
| New weapon *kind* | only `{ranged, melee}` iterated | iterate whatever kinds exist under `weapons/`; warn on unrecognized |
| New zones | `find_zone_waves` hardcodes `zone_1` | discover all `zones/zone_*`; still model only what's verified, but report the rest exist |
| Whole new content tree (`abyssal/`, curse pickups…) | nothing globs it → invisible | top-level **coverage pass**: diff `extracted/` subdirs against what discoverers claim; report **unclaimed trees** |
| Dirs failing filename conventions | silent `continue` | collect skipped dirs and report them |

**Light registry (the B borrow):** each discoverer declares the subtree(s) it
claims; a coverage check reports unclaimed trees and per-discoverer skips. This
is a *reporting* structure, not a generic entity-handler — the build handles
what it knows and loudly enumerates what it doesn't.

## Section 3 — Diff harness (`tools/diff_dataset.py`) — centerpiece

Operates on **two local dataset JSONs** (never a committed baseline — both files
are gitignored data the user already holds):

```
uv run python tools/diff_dataset.py data/brotato.base.json data/brotato.json
```

Reports, per collection (weapons / items / characters / sets / enemies / waves):
- **Added / removed / changed** records, with a top-line summary
  ("12 new weapons, 40 new items, 6 new characters, 2 new zones, 18 unknown
  effect scripts").
- For **changed** records: which fields moved (e.g. `base_damage 12 → 15`) —
  catches DLC *rebalances* to existing content, not only additions.
- **Unknown effect scripts**: effects referenced by new/changed records that no
  proc-model or classification recognizes → the modeling worklist,
  auto-generated.
- **New `source` values** — confirms provenance detection fired.
- Passes through discovery's coverage report (unclaimed trees / skipped dirs).

`--json` for machine triage. Dev tool in `tools/`; no MCP surface, no schema
impact.

## Section 4 — Build-time coverage/unmodeled report

`build_dataset.py` gains, after its existing summary line:
- A **coverage report**: unclaimed trees, skipped dirs (Section 2), and
  referenced-but-unrecognized effect scripts.
- A `--strict` flag turning unclaimed content into a build *failure* — so a
  deploy can't silently ship half-ingested DLC. Default is non-strict: the build
  still writes the json and prints the report as a warning.
- New unknown effects flow through the **existing** `unmodeled_effects` /
  `classified_effects` machinery (no new mechanism). When `content_sources`
  includes a DLC with unmodeled effects, `read_me`'s primer caveats it — keeping
  the "never present unverified as verified" contract intact.

## Section 5 — DLC-day playbook (`docs/dlc-incorporation-playbook.md`)

A new ordered, executable doc — **authored now** as part of this work (calm
day), even though its steps execute on DLC day:

1. **Preserve baseline** — copy `data/brotato.json` → `data/brotato.base.json`.
2. **Re-copy game files** — fresh `Brotato.pck` (+ any DLC pack) from the
   updated Steam install; **confirm how the DLC ships** (second `.pck`?) — this
   resolves the provenance mechanism.
3. **Re-extract** — `unpack_pck.py` per pack → `extracted/`; gdre_tools →
   `recovered/` (DLC pack into a marked tree if separate).
4. **Rebuild** — `build_dataset.py`; read the coverage/unmodeled report.
5. **Teach `detect_source`** — fill in the confirmed signal from step 2;
   rebuild; confirm `content_sources` lists the DLC.
6. **Diff** — `diff_dataset.py base vs new` → triage list.
7. **Triage** — new *records* mostly ingest for free; the real work is unknown
   effects (existing proc-worklist process), new mechanics (curse/elements →
   `docs/` writeups), new zones (bestiary follow-up). **Each is its own
   spec→plan→implement cycle**, not done in the incorporation session. Curse is
   the expected first such cycle.
8. **Re-pin all evidence** against the *new* decompiled source — never carry
   base-game citations forward (the project's known failure mode).
9. **Stamp** — bump `DATASET_VERSION` if fields were added; stamp `server.json`.
10. **Deploy** — regenerate the schema-matching json for spudcoach-chat and
    redeploy (`fly deploy -a spudcoach-2c57`; `fly.toml` app name is a
    placeholder, so `-a` is required).

The playbook's stance: the incorporation session **ingests cleanly, tags
provenance, and produces the triage list** — it does *not* model curse/elements
on the spot.

---

## Testing strategy

All of Sections 1–4 are testable **now**, with no DLC data, via TDD (write the
failing test first, per project norm):

- **Provenance:** builder tests assert every record carries `source == "base"`
  and the root carries `content_sources == ["base"]`; `validate_dataset` test
  asserts a record missing `source` fails the build. A `detect_source` unit test
  pins the default and (once stubs for signals 1–3 exist) each branch.
- **Discovery hardening:** inject a synthetic unrecognized top-level dir and a
  synthetic new `weapons/<kind>/` and assert both are *reported* (not silently
  dropped); inject a convention-violating entity dir and assert it appears in
  the skip report.
- **Diff harness:** feed two hand-built minimal dataset dicts (added / removed /
  changed / new-source / unknown-effect cases) and assert the report content;
  test `--json` shape.
- **Build report:** assert the coverage report lists injected unclaimed trees;
  assert `--strict` exits non-zero when unclaimed content is present.

`uv run ruff check .` stays green throughout.

## Schema/version impact

- `DATASET_VERSION`: 6 → **7** (adds `source` per record + root
  `content_sources`).
- spudcoach-chat consumes `brotato.json`; the v7 bump means its bundled dataset
  must be regenerated on the next deploy (already a playbook step).
- `server.json` stamp happens at release time per existing process, not in this
  work.
