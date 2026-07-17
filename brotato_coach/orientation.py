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

## How the DPS engine works

The DPS model computes realized, stat-aware DPS at YOUR stat block — it is
not a baseline figure you have to hand-scale yourself:

- **DPS is realized expected DPS at your full stat block.** weapon_dps /
  compare_weapons / evaluate_run resolve every scaling stat the weapon
  actually has (ranged damage, melee damage, elemental damage,
  engineering, ...), %damage, attack speed, and expected crit (crit
  chance x crit damage) — game-exactly, including the game's own integer
  truncation/rounding at each arithmetic step. attack speed also drives
  cycle_time (see cadence below), with a melee-specific extra: the
  back-swing portion of a melee cycle shrinks by (1 + 3 x attack_speed),
  three times as sensitive to attack speed as the rest of the cycle.
  Because the arithmetic is integer, a small stat bump can land on a
  zero-delta step rather than a smooth increase — stat_gradient defaults
  to a step of +10 for this reason; don't read meaning into a raw +1 test.
- **Assumptions are surfaced per call, explicitly.** Every weapon_dps /
  compare_weapons result carries an `assumptions` object: `aoe_enemies_hit`
  (how many enemies an AoE proc is assumed to catch), `engagement_distance`
  for melee weapons (defaults to `min(max_range, 70)` — melee cycle time
  depends on distance-to-target; override it if your playstyle engages
  closer or farther), and `set_bonuses_applied`. Weapon-CLASS set bonuses
  (Blade/Gun/Elemental/... thresholds, see get_weapon_class_set) are
  opt-in: pass `loadout` to report which are active, and
  `apply_set_bonuses=True` to fold them into the stats you handed in —
  only do this for a manually-typed stat block. Screen/save-derived stats
  (what evaluate_run reads from a run.json) already include any active set
  bonuses, so applying them again would double-count.
- **cycle_time** is seconds per attack cycle, now stat-aware: ranged is
  2 x recoil_duration' (recoil_duration shrunk by attack speed); melee is
  atk_duration/2 + back_duration + recoil_duration', where atk_duration
  grows with the assumed engagement distance and back_duration carries the
  triple-attack-speed sensitivity above; either includes burst-reload
  amortization where it applies.
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
- **Proc lines.** `proc_dps` (part of every weapon_dps/compare_weapons
  result, alongside `base_dps`) adds expected on-hit proc damage from three
  verified damage sources, re-run through the SAME stat-aware pipeline as
  the direct hit — proc modeling is unchanged in spirit, but no longer
  frozen at a baseline:
  - weapon_damage (exploding): the explosion re-deals the weapon's own
    (stat-aware) damage line. The engine EXCLUDES the directly-hit enemy
    from the blast, so the model's enemies_hit default of 1.0 means "one
    OTHER enemy is caught" — the proc is worth ZERO against a lone target
    (bosses!); override enemies_hit down for single-target reasoning, up
    for crowds.
  - burn_dot: burns tick every 0.5s for the burn's flat damage, now
    resolved through the burn's own scaling_stats — a burn that scales
    with elemental damage genuinely grows with elemental damage instead of
    reporting a flat baseline number. Re-ignition refreshes (max-based),
    never stacks; the line assumes steady-state (continuous attacking
    keeps the burn up). CAVEAT: that steady-state eligibility is decided
    at dataset-build time from the weapon's zero-attack-speed cycle time,
    so it can be wrong in both directions at runtime — heavily NEGATIVE
    attack speed slows the cycle past the burn window and the static line
    then overstates burn uptime, while burns with chance < 100% are
    excluded entirely even though a fast weapon proccing at, say, 50%
    sustains real burn DPS the model reports as zero.
  - companion_ranged_stats (lightning/spawned projectiles): spawned
    projectiles carry their OWN damage and scaling, independent of the host
    weapon. Targeted chains assume the nominal chain fully connects
    (enemies_hit = 1 + bounce; also zero against a lone target); untargeted
    sprays assume 1.0 expected hit per volley — an assumption constant, not
    a measurement.
  - Two player-level stats lift exploding weapons ABOVE these lines and are
    NOT modeled here, so builds stacking them out-damage the static numbers.
    explosion_damage is a % damage bonus that stacks additively with % Damage:
    at zero other %damage, multiply the exploding weapon's reported DPS by
    (1 + explosion_damage/100) — a +15 item -> x1.15 — and note it lifts the
    DIRECT line too, not just the proc. On a build already at +P% damage it
    adds into that bucket (-> 1 + (P+explosion_damage)/100), not another
    multiply. explosion_size widens the blast radius (x(1 + explosion_size/100))
    so more enemies are caught; density-dependent with no closed form, so
    raise the enemies_hit you assume for such builds.
- **Still NOT modeled.** nb_projectiles is NOT multiplied into DPS (spread
  and pierce hit-rates depend on enemy density/positioning with no closed
  form); character class bonuses (e.g. Crazy's +100 range to Precise
  weapons) are surfaced advisorily via evaluate_run's class_synergy /
  get_character, not consumed by weapon_dps; the cooldown-jitter model
  covers the verified dead-window RANGE but not a floor-skew bias in how
  often a cooldown lands near its low end; and survivability (armor,
  dodge, HP, regen, lifesteal) is entirely out of scope — this is a DPS
  engine only, see stat_gradient's own "DPS gradient only" caveat.
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
- weapon_dps / compare_weapons rank by the realized DPS above — for
  merge-order questions use compare_merge_paths; for 'which stat should I
  buy next' use stat_gradient; for whole-run post-mortems pass the run.json
  to evaluate_run.
- **Class bonuses are build context, not DPS deltas.** A character's
  class_bonuses (e.g. Crazy's +100 range to Precise weapons) grant a stat to
  weapons of one set. The stat-aware DPS engine does NOT go looking for these
  grants and apply them on your behalf — it only consumes what's IN the
  `stats` you pass it (raw range, for instance, doesn't move DPS anyway
  since it's a cadence/positioning stat, not a damage scalar) — so read
  class_bonuses from get_character or evaluate_run's class_synergy section
  as synergy guidance (favor the boosted set), not as an automatic DPS
  change.
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
