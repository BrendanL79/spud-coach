# Weapon cadence reporting — design

**Date:** 2026-07-09
**Status:** Design (awaiting review)
**Scope chosen:** Approach A — per-weapon cadence foundation + verified consistency. No
cross-weapon synchronization model.

## Motivation

`weapon_dps` / `compare_weapons` / `evaluate_run` collapse weapon efficacy into a single
`dps` scalar (plus an RD-line breakdown). DPS is a **time-average**: it says nothing about
how the damage is distributed within a cycle. A slow 100-damage weapon and a fast
10-damage weapon can report identical DPS while playing completely differently — the slow
one fires a burst, then goes silent for a long dead window during which a horde can close
in and kill you ("stuck in the cooldown").

The player-reported framing was cross-weapon: several similar weapons "volley in unison"
into a shared dead window. Source investigation (below) **refutes** the unison mechanism
but **confirms** the underlying survival concern, relocating it from a loadout property to
a per-weapon one.

## Source findings (verified against `recovered/`)

Citations are pinned here for the design's reasoning. Per project rule they MUST be
re-pinned against the decompiled source at doc-write time and verified by review — not
carried forward from this spec.

- **The cycle.** On fire, projectiles spawn, then `set_shooting(true)`; the sprite recoils
  out and back over two tweens of `recoil_duration` each, then `set_shooting(false)`
  (`ranged_weapon_shooting_behavior.gd:14–48`). Cooldown ticks down **only while not
  shooting** (`weapon.gd:192–193`). So `cycle_time = 2·recoil_duration + cooldown/60`
  seconds — the coach's existing formula is correct.
- **Cooldown is randomized every shot.** On fire, `_current_cooldown = get_next_cooldown()`
  (`weapon.gd:323`), which returns `rand_range(max(1, basis − Δ), basis + Δ)`
  (`weapon.gd:337–349`). The draw is symmetric around basis, so `E[cooldown] = basis` and
  **expected DPS is unchanged — no DPS regression — EXCEPT when the low bound floors at 1**
  (`basis − Δ < 1`: fast weapons at high weapon counts, e.g. 6× Minigun basis 3 → draw
  `[1, 6.6]`, mean 3.8). There the mean skews above basis and nominal DPS modestly
  overstates those builds. The coach's `cycle_time` uses raw basis and does not model this
  floor-skew; it is logged in `docs/roadmap.md` as a small, situational unmodeled effect.
- **Jitter scales with weapon count (anti-synchronization).**
  `Δ = min(N·basis/5, N·5)` frames, `N = min(nb_weapons, 6)` (`weapon.gd:352–354`). The
  game de-synchronizes volleys *more* as you add weapons.
- **Wave-start cap.** The first cooldown of a wave uses a basis capped at 180 frames if
  `basis ≥ 180` (`weapon.gd:344–345`), also randomized (`weapon.gd:162–164`).

**Consequence.** A cycle_time-spread "synchronization risk" heuristic (the 2026-07-08
roadmap hypothesis) would advise *backwards*: the engine actively prevents unison, harder
with more weapons. The real signal is the **bounded jitter ratio**. For a slow weapon Δ is
capped at `N·5` frames (≤0.5s), so a 5s-cooldown weapon jitters only ~±10% — its long dead
window stays long, every cycle. Streakiness is therefore a **per-weapon** property, worst
for slow weapons, and fully source-derived.

## Non-goals

- No change to any `dps`, `dps_at_zero_rd`, `dps_slope_per_rd`, or proc-line value.
- No change to ranking sort order (still DPS-descending).
- No schema-version bump. The core cadence metrics need **no rebuild** — every input
  (`cycle_time`, `cooldown`, `nb_projectiles`, dps line) already exists in
  `data/brotato.json`. The only additive change is one backward-compatible boolean field,
  `burst_reload`, on the weapon record (for the bimodal caveat marker); it defaults to
  `False` when absent, so old datasets keep working and only a local rebuild is needed to
  populate it on Revolver/Chain Gun.
- No cross-weapon synchronization / loadout-superposition metric (deferred; see roadmap
  amendment).
- Crit remains unmodeled (unchanged, out of scope).

## Metrics

All derived from fields already on each weapon record: `cycle_time`, `cooldown` (pre-jitter
basis, in frames), `base_damage`, `nb_projectiles`, and the RD-scaled dps line.

| Metric | Definition | Notes |
|---|---|---|
| `attacks_per_second` | `1 / cycle_time` | The "rate of fire" headline. |
| `seconds_between_attacks` | `cycle_time` | Mean gap; legible for slow weapons. |
| `damage_per_attack` | `total_dps × cycle_time` | Burst size per volley. Defined off total DPS (incl. proc) so `damage_per_attack × attacks_per_second == dps` exactly. |
| `cadence` | label ∈ {`sustained`, `moderate`, `bursty`} | Thresholded on `attacks_per_second`; thresholds documented and hand-tuned. Lets the coach *say* "slow, bursty weapon: long dead windows." |
| `gap_range_s` | `[min_s, max_s]` from `cooldown_jitter(basis, N)` | Verified streakiness. `Δ = min(N·basis/5, N·5)` frames. Since `cycle_time = 2·recoil + basis/60`, only the cooldown term varies: `min_s = cycle_time − (basis − max(1, basis−Δ))/60`, `max_s = cycle_time + Δ/60`. N-dependent; needs no separate recoil value. |

Proposed `cadence` thresholds (documented in `docs/cadence-mechanics.md`, tunable):
`sustained ≥ 3` atk/s, `1 ≤ moderate < 3`, `bursty < 1`.

## New pure primitives (`calc.py`)

No I/O; unit-tested against hand-verified values.

- `cooldown_jitter(cooldown_basis_frames: float, weapon_count: int) -> tuple[float, float]`
  → `(min_frames, max_frames)` for the per-shot cooldown, applying
  `Δ = min(N·basis/5, N·5)`, `N = min(weapon_count, 6)`, and the `max(1, …)` floor.
- `cadence_profile(cycle_time: float, total_dps: float, cooldown_basis_frames: float,
  weapon_count: int = 1) -> dict` → assembles `attacks_per_second`,
  `seconds_between_attacks`, `damage_per_attack`, `cadence`, `gap_range_s`. Derives the
  gap range from `cycle_time` and the cooldown basis (the recoil term is common to both
  bounds and cancels), so no separate recoil value and no schema field are required.

## Report surface changes

Each response gains a `cadence` sub-object; existing DPS fields are untouched.

- **`answers.weapon_dps`** and **`answers.compare_weapons`**: add `cadence` via
  `cadence_profile`. Both accept an optional `weapon_count` (default `1`) feeding the jitter
  range; documented that `gap_range_s` widens with loadout size.
- **`answers.evaluate_run`** (in `answers.py`, not `evaluate.py`): its ranking is produced
  by *calling* `compare_weapons` (`answers.py:173`), so threading a `weapon_count` through
  `compare_weapons` automatically feeds the run's ranking. `evaluate_run` passes
  `weapon_count = len(build["weapons"])`, so `gap_range_s` is real. Sort stays
  DPS-descending; cadence is descriptive only.
- **`server.py`**: the tools are thin wrappers whose outputs are documented by docstring
  (there is no formal output schema; `schemas.py` holds only the input `Stats` model). Add
  an optional `weapon_count: int = 1` param to the `weapon_dps` and `compare_weapons` tools
  and describe the new `cadence` object in their docstrings.

**Graceful degradation.** `cadence` is attached only when the record has `cycle_time > 0`
(always true for real weapon records; keeps minimal test fixtures and any non-weapon record
from breaking). When absent, output is exactly as today.

## Known caveat (surfaced, not hidden)

Burst-reload weapons (`additional_cooldown_every_x_shots ≠ -1`) have a **bimodal** cadence
(fast-fast-fast-LONG reload) that the averaged `cycle_time` smooths over.
`attacks_per_second` reports the average, not the felt rhythm. This property is
**tier-gated**, and only two weapons have it in the base game: **Revolver** (every 6 shots,
tiers 2–4 — tier 1 is a normal weapon) and **Chain Gun** (every 100 shots, tier 4 only).
Flagged explicitly in the `cadence` output (e.g. a `burst_reload: true` marker) and in
`docs/cadence-mechanics.md` so it does not read as fully modeled. The two hand-verified test
weapons (fast vs slow) should be *non*-burst weapons to keep the invariant clean; add a
separate Revolver-tier-3 case to pin the bimodal caveat.

## Documentation changes

- **New `docs/cadence-mechanics.md`.** The verified attack-timing model: the cycle,
  the randomization, the weapon-count-scaled Δ, the wave-start cap, and the per-weapon
  streakiness consequence. Citations re-pinned against `recovered/` at write time.
- **Update the `read_me` primer** (`orientation.py:92–100`). Replace the
  "Attack-timing synchronization is NOT modeled" block: per-weapon cadence **is** now
  surfaced; cross-weapon synchronization is **intentionally not scored** because the engine
  randomizes cooldowns to prevent unison (verified) — a sync-risk metric would mislead. Add
  the burst-reload bimodal caveat.
- **Amend `docs/roadmap.md`** (2026-07-08 "Loadout timing/consistency" entry). Mark the
  unison hypothesis and the cycle_time-spread heuristic **refuted by source** (cite it);
  note per-weapon cadence shipped; re-scope any future loadout metric around the verified
  de-sync mechanic rather than the naive spread idea.

## Testing (TDD — failing test first)

- Unit tests in `tests/` for `cooldown_jitter` and `cadence_profile` against hand-verified
  values for one fast weapon and one slow weapon (concrete picks from the dataset, e.g. a
  Pistol-class vs a Sniper/Rocket-class), at `N = 1` and `N = 6`.
- Consistency invariant: `damage_per_attack × attacks_per_second == dps` (within float
  tolerance).
- No-regression: existing DPS / ranking outputs unchanged for current test cases.
- `uv run ruff check .` stays green.

## Files touched

- `brotato_coach/calc.py` — new primitives.
- `brotato_coach/answers.py` — `weapon_dps`, `compare_weapons`, and `evaluate_run` (threads
  `weapon_count`).
- `brotato_coach/orientation.py` — primer caveat rewrite.
- `brotato_coach/server.py` — `weapon_count` param + docstring updates on the `weapon_dps`
  and `compare_weapons` tools.
- `docs/cadence-mechanics.md` — new.
- `docs/roadmap.md` — amend the loadout-timing entry.
- `tests/test_calc.py`, `tests/test_answers.py`, `tests/test_orientation.py` — new cadence
  tests.
