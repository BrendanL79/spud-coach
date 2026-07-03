"""Expected-damage models for weapon on-hit proc effects.

A model may only be added here with decompiled-code evidence from recovered/
(the builders/mechanics.py standard) — record the evidence in
docs/proc-mechanics.md. Effects without a model contribute zero DPS and are
listed in the weapon record's `unmodeled_effects`, so rankings stay honest
about what they ignore.

Model schema, keyed by effect `key`:
    damage_source: "weapon_damage" — the proc re-deals the weapon's own damage
        line (base + scaling), scaled by damage_multiplier.
    damage_multiplier: fraction of the weapon's damage line the proc deals.
    default_enemies_hit: assumed average enemies caught per proc (AoE). The
        softest number in the model; answers surface it as an assumption and
        let callers override it.
"""

from __future__ import annotations

# Exploding effect: a chance-per-hit to spawn an explosion that re-deals the
# weapon's own current damage line (base + scaling stats), unmodified.
# Evidence: docs/proc-mechanics.md (recovered/weapons/weapon.gd:419-436,
# _on_Hitbox_hit_something — `_explosion_args.damage = _hitbox.damage`).
# All three keys attach the same recovered/effects/weapons/exploding_effect.gd
# script and are dispatched on script class at runtime, so they share one
# model: Shredder T1-3 (effect_explode_custom), Fireball/Nuclear
# Launcher T3-4/Rocket Launcher/Shredder T4 (effect_explode), and
# Plank/Power Fist/Plasma Sledgehammer/Dextroyer (effect_explode_melee).
_EXPLODE_MODEL = {
    "damage_source": "weapon_damage",
    "damage_multiplier": 1.0,
    # The explosion's ignored_objects excludes the enemy that was just hit
    # (weapon.gd:435), so it can only damage OTHER enemies in the blast.
    # 1.0 assumes one other enemy is caught — conservative for crowds,
    # optimistic against a lone target (true value there is 0).
    "default_enemies_hit": 1.0,
}

PROC_MODELS: dict[str, dict] = {
    "effect_explode_custom": _EXPLODE_MODEL,
    "effect_explode": _EXPLODE_MODEL,
    "effect_explode_melee": _EXPLODE_MODEL,
}
