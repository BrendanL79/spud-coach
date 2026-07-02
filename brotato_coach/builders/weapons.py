from __future__ import annotations

from brotato_coach import calc
from brotato_coach.tres import parse_tres


def _rd_coefficient(scaling_stats: list) -> float:
    for entry in scaling_stats or []:
        if isinstance(entry, list) and len(entry) == 2 and entry[0] == "stat_ranged_damage":
            return float(entry[1])
    return 0.0


def _weapon_effect_record(text: str) -> dict:
    """A weapon's on-hit effect as plain scalar fields.

    Drops nested resource references (script, explosion_scene, …) and keeps the
    gameplay scalars — e.g. the Shredder's `key="effect_explode_custom"` with
    `chance=0.5`.
    """
    r = parse_tres(text).resource
    return {k: v for k, v in r.items()
            if not (isinstance(v, dict) and ("__ext__" in v or "__sub__" in v))}


def build_weapon_record(stats_text: str, data_text: str,
                        effect_texts: list[str] | None = None, *,
                        weapon_id: str, name: str, tier: int,
                        classes: list[str] | None = None) -> dict:
    s = parse_tres(stats_text).resource

    cooldown = float(s.get("cooldown", 0))
    recoil_duration = float(s.get("recoil_duration", 0.0))
    base_damage = float(s.get("damage", 0))
    accuracy = float(s.get("accuracy", 1.0))
    scaling_stats = s.get("scaling_stats", []) or []

    burst = None
    every = s.get("additional_cooldown_every_x_shots", -1)
    mult = s.get("additional_cooldown_multiplier", -1.0)
    if isinstance(every, int) and every > 0 and isinstance(mult, (int, float)) and mult > 0:
        burst = (every, float(mult))

    ct = calc.cycle_time(recoil_duration, cooldown, burst=burst)
    dps0, slope = calc.dps_line(base_damage, _rd_coefficient(scaling_stats), ct, accuracy)

    return {
        "id": weapon_id,
        "name": name,
        "tier": tier,
        "base_damage": base_damage,
        "cooldown": cooldown,
        "accuracy": accuracy,
        "crit_chance": float(s.get("crit_chance", 0.0)),
        "crit_damage": float(s.get("crit_damage", 0.0)),
        "piercing": s.get("piercing", 0),
        "nb_projectiles": s.get("nb_projectiles", 1),
        "scaling_stats": scaling_stats,
        "can_have_negative_knockback": bool(s.get("can_have_negative_knockback", False)),
        "base_knockback": s.get("knockback", 0),
        "cycle_time": ct,
        "dps_at_zero_rd": dps0,
        "dps_slope_per_rd": slope,
        # Weapon-class set membership (e.g. ["Gun", "Explosive"]); resolved from
        # the data .tres `sets` ext_resources by the discover step.
        "sets": list(classes or []),
        # On-hit effects (e.g. exploding projectile), resolved from the data
        # .tres `effects` ext_resources. NOTE: these are surfaced for reasoning;
        # the DPS math does not yet factor procs into dps_at_zero_rd/slope.
        "effects": [_weapon_effect_record(t) for t in (effect_texts or [])],
    }
