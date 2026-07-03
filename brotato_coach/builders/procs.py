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

PROC_MODELS: dict[str, dict] = {}
