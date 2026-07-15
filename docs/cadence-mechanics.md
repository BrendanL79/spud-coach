# Attack cadence mechanics

How the coach models a weapon's *timing*, verified against the decompiled
source. Companion to `docs/stat-mechanics.md`, `docs/proc-mechanics.md`, and
`docs/dps-engine.md` (the full stat-aware formula chain this timing feeds
into).

## The attack cycle is stat-aware, and melee differs from ranged

Cooldown counts down **only while not shooting** (`weapon.gd:192-193`), so in
general `cycle_time = shooting_total_duration + effective_cooldown / 60`
(seconds; cooldown in frames @60fps), computed by
`calc.stat_aware_cycle_time` (superseding the old `calc.cycle_time`).
`effective_cooldown` already folds in attack speed (floors at 2 frames,
divides by `1+AS` for positive AS, multiplies by `1+|AS|` for negative AS —
`weapon_service.gd:227-229,570-573`). `shooting_total_duration` is where
ranged and melee weapons diverge:

- **Ranged** (`ranged_shooting_data.gd:10-15`): fires immediately, then two
  symmetric recoil tweens (`set_shooting(true)`, two tweens of
  `recoil_duration` each, then `set_shooting(false)` —
  `ranged_weapon_shooting_behavior.gd:14-48`):

      shooting = 2 * recoil_duration'   (recoil_duration shrunk by attack speed for AS > 0)

- **Melee** (`melee_shooting_data.gd:17-28`): a wind-up/back-swing pair, both
  with their own (different) attack-speed sensitivity, plus a term that grows
  with how far away the target is (`range_factor`):

      shooting = atk_duration/2 + back_duration + recoil_duration'

  Full formulas, the melee-specific attack-speed asymmetry, and the
  engagement-distance assumption constant are in `docs/dps-engine.md` (step
  E). This is the mismodeling the old RD-only engine had — it applied the
  ranged formula to melee swings.

Burst-reload weapons (Revolver, Chain Gun) do not add an extra term on top —
the game *replaces* one ordinary cooldown draw with `cooldown * multiplier`
every `every_x_shots`-th shot (`weapon.gd:337-339,357-358`), and the coach
amortizes that replacement across the cycle count. See "Known limitation:
burst-reload weapons" below and `docs/dps-engine.md`'s "Burst reload:
replaces, not adds" for the exact amortization formula.

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
- `cadence` label: sustained (>= 3/s), moderate (1 to <3/s), bursty (< 1/s).
- `gap_range_s` — the verified min/max seconds between volleys at a given
  weapon count. Streakiness is a PER-WEAPON property: slow weapons have Δ
  capped at N*5 frames (<= 0.5s), so their long dead window barely jitters,
  while fast weapons get jitter exceeding their whole cooldown (fully
  smoothed). No cross-weapon "synchronization risk" score is offered — the
  randomization above shows unison is actively prevented, so such a score
  would mislead.
- **Floor-skew caveat.** When `basis - Δ < 1` the cooldown draw floors at 1,
  lifting the mean above basis (fast weapons at high weapon counts). Those
  weapons fire slightly slower than basis implies; `cycle_time`/DPS use raw
  basis and do not model this — nominal DPS modestly overstates such builds.
  See the roadmap.

## Known limitation: burst-reload weapons

Revolver (every 6 shots, all tiers) and Chain Gun (every 100, tier 4) — the
only base-game weapons with `additional_cooldown_every_x_shots` set — have a
bimodal cadence (fast, then a long reload). `cycle_time` amortizes the reload,
so `attacks_per_second` is an average, not the felt rhythm; `burst_reload:
true` marks them.
