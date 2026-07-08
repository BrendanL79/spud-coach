"""Session-start orientation primer served by the read_me tool.

The primer is our own MIT-licensed prose about mechanics facts and this
project's modeling conventions — it contains no game data. Claims in the
"verified" sections must stay in sync with docs/stat-mechanics.md and
docs/proc-mechanics.md (the evidence record); update both together.
Rendering uses str.replace, not str.format, so the markdown may safely
contain braces anywhere except the one {provenance} placeholder.
"""
from __future__ import annotations

PRIMER = """\
# Spud Coach — read me first

This server is the authoritative source for Brotato facts: it is built from
a versioned, fan-extracted copy of the game's own data files, not from
training data. Training-data knowledge of Brotato is frequently stale or
wrong for the loaded game version — prefer these tools over memory for any
weapon/item/character/mechanics claim.

{provenance}

## Game basics

Orientation only — general game knowledge, not source-verified.

- A run is a series of waves (20 in a standard run, then optional endless)
  at a difficulty chosen up front (Danger 0-5; higher = harder, better loot).
- Enemies drop materials, which are simultaneously money and XP: every
  material picked up counts toward both the shop budget and level-ups
  (a level-up offers a choice of stat upgrades).
- Between waves you visit the shop: buy weapons and items, reroll offers,
  or lock an offer for later.
- A character holds up to 6 weapons (character-dependent). Buying a copy of
  a weapon you already own at the same tier merges the two into one weapon
  of the next tier, in place — merging never costs an extra slot.
- Tiers everywhere in this dataset and API are 1-indexed (1-4), matching
  the in-game display (I-IV).

## Verified stat mechanics

Source-verified against the game's decompiled code (details per stat via
the explain_stat tool).

- **Caps.** Exactly 5 stats have caps: max_hp, speed, dodge, curse, and
  crit_chance. Only two bind from wave 1: dodge (60) and curse (0). The
  HP/speed/crit caps default to effectively infinite until an item sets a
  real one (e.g. Handcuffs freezes Max HP, Shackles freezes Speed at their
  current values).
- **Curse.** Positive curse scales enemy damage and HP (a sqrt factor) —
  a drawback stat. Negative curse is clamped: harmless, but no benefit.
- **Armor.** Diminishing returns: percent damage taken is 10/(10+armor/1.5),
  and damage taken never drops below 1. NEGATIVE armor is asymmetric — it
  amplifies damage taken above 100%, worse than the mirror image of the
  positive curve.
- **Luck.** A drop-chance multiplier. NEGATIVE luck divides drop chances
  rather than subtracting — a diminishing-returns penalty, not symmetric.
- **Harvesting.** Pays at end of each wave: one point of harvesting grants
  one material AND one XP. While positive it grows ~5% per wave; in endless
  it decays 20% per wave; NEGATIVE harvesting actively drains gold each
  wave (not a no-op).
- **Attack speed.** A universal cooldown multiplier applied identically to
  melee and ranged weapons — never dead weight.
- **HP regeneration.** At or below 0 it is a harmless no-op. (Unlike
  negative lifesteal, which actively drains HP on hit.)
- **% Damage.** A multiplicative global weapon-damage bonus (1 + stat/100),
  uncapped; final damage is floored at 1.
- **Range.** Adds flat range; melee weapons receive only HALF the stat.
  Uncapped.
- **Gain modifiers.** Character stat-gain modifiers (e.g. Ranger's +50%
  ranged-damage gains) multiply the raw sum of collected bonuses at display
  time: raw +6 ranged damage shows as +9. Use stat_display_value to convert.

## What the precomputed numbers mean

The DPS model is deliberately narrow and honest about it:

- **DPS is a line in ranged damage (RD).** Each weapon record carries
  dps_at_zero_rd and dps_slope_per_rd; realized base DPS at a build is
  dps_at_zero_rd + dps_slope_per_rd x RD. The slope is specifically the
  weapon's stat_ranged_damage scaling coefficient — weapons that scale
  with OTHER stats (melee damage, elemental, engineering, ...) have slope
  0 and their scaling lives only in scaling_stats; the served DPS number
  does NOT grow with those stats. Check scaling_stats before comparing
  across scaling types.
- **Baseline.** dps_at_zero_rd is computed at a zero-stat baseline — ALL
  player stats at zero; the weapon's own accuracy is already folded in.
- **cycle_time** is seconds per attack cycle: recoil_duration x 2 +
  cooldown/60, plus any burst-reload amortization.
- **Crit is NOT modeled.** crit_chance and crit_damage appear on the record
  but are not folded into any DPS line.
- **Proc lines.** proc_dps_at_zero_rd / proc_dps_slope_per_rd add expected
  on-hit proc damage from three verified damage sources:
  - weapon_damage (exploding): the explosion re-deals the weapon's own
    damage line. The engine EXCLUDES the directly-hit enemy from the blast,
    so the model's enemies_hit default of 1.0 means "one OTHER enemy is
    caught" — the proc is worth ZERO against a lone target (bosses!);
    override enemies_hit down for single-target reasoning, up for crowds.
  - burn_dot: burns tick every 0.5s for the burn's flat damage; re-ignition
    refreshes (max-based), never stacks. The line assumes steady-state
    (continuous attacking keeps the burn up).
  - companion_ranged_stats (lightning/spawned projectiles): spawned
    projectiles carry their OWN damage and scaling, independent of the host
    weapon. Targeted chains assume the nominal chain fully connects
    (enemies_hit = 1 + bounce; also zero against a lone target); untargeted
    sprays assume 1.0 expected hit per volley — an assumption constant, not
    a measurement.
  - Two player-level stats lift exploding weapons ABOVE these lines and are
    NOT modeled here, so builds stacking them out-damage the static numbers.
    explosion_damage is a % damage bonus that stacks additively with % Damage:
    at the zero-stat baseline multiply the exploding weapon's line by
    (1 + explosion_damage/100) — a +15 item -> x1.15 — and note it lifts the
    DIRECT line too, not just the proc. On a build already at +P% damage it
    adds into that bucket (-> 1 + (P+explosion_damage)/100), not another
    multiply. explosion_size widens the blast radius (x(1 + explosion_size/100))
    so more enemies are caught; density-dependent with no closed form, so
    raise the enemies_hit you assume for such builds.
- **classified_effects.** Non-DPS effects are classified, with metadata,
  into 9 categories: stat_rider (flat stat granted while held), dynamic
  (state/time-dependent, no honest static number), economy (gold
  generation), cc (slows/crowd control), delivery_modifier (pierce/bounce
  on crit), drawback (self-damage etc.), execute (chance to deal
  current-HP damage), stack (bonus per extra copy owned), structure
  (spawns mines/turrets).
- **unmodeled_effects** is empty across the shipped dataset; if you ever
  see an entry, it strictly means "uninvestigated" — mention it when the
  number matters.

## Bestiary and enemy scaling

Orientation only — see get_enemy, list_enemies, and wave_composition for
the data itself.

- Enemy HP, damage, and armor scale per wave: a record's effective stat is
  base.<stat> + per_wave.<stat> x (wave - 1) (get_enemy returns this as
  effective when you pass a wave); movement speed is a range,
  speed +/- speed_randomization, not a single value.
- wave_composition reports the EXACT base-game (Crash Zone) enemy groups
  for waves 1-20. Realized enemy counts scale with run modifiers (the
  number_of_enemies % setting, co-op player count), and elite/horde waves
  are scheduled per-run — randomized, never guaranteed at a specific wave.
- An enemy's appears_in holds provenance LABELS (currently just "normal"),
  NOT wave numbers. "normal" means the enemy shows up in a base group of the
  numbered waves (1-20). appears_in is EMPTY for bosses and for
  horde/elite/endless-only enemies: empty means "not in the numbered-wave
  base groups," NOT "never spawns" — check danger/wave-type context before
  telling a user an enemy can't show up.

## Using the tools

- Call get_filter_options BEFORE passing filter values to list_weapons /
  list_items / get_weapon_class_set — filters are case-sensitive exact
  matches.
- `stats` parameters take short names (e.g. ranged_damage); explain_stat
  and stat_display_value take the stat_-prefixed form (stat_ranged_damage).
- weapon_dps / compare_weapons rank by the RD line above — for merge-order
  questions use compare_merge_paths; for whole-run post-mortems pass the
  run.json to evaluate_run.
- **weapon_dps / compare_weapons need DISPLAYED stats, not raw ones.** A
  run.json's `effects` block stores the RAW pre-gain-modifier accumulator
  (see "Gain modifiers" above) — feeding that straight in silently
  understates (or overstates) DPS for any character with a gain modifier on
  the scaling stat, with no error to catch it. Pass `character` and hand in
  raw stats; the tool converts them for you. evaluate_run already does this
  internally, so its weapon_dps_ranking and realized_stats are safe to use
  as-is.
"""


def read_me_payload(ds: dict) -> dict:
    """Render the primer with the loaded dataset's provenance interpolated."""
    def _field(key: str) -> str:
        val = ds.get(key)
        return "unknown" if val is None else str(val)

    provenance = (f"Dataset: Brotato v{_field('game_version')} — "
                  f"schema v{_field('schema_version')}, "
                  f"generated {_field('generated_at')}.")
    return {"primer": PRIMER.replace("{provenance}", provenance)}
