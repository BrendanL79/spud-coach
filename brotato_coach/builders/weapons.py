from __future__ import annotations

from brotato_coach import calc
from brotato_coach.builders.localization import resolve_text
from brotato_coach.builders.procs import PROC_MODELS
from brotato_coach.tres import parse_tres


def _rd_coefficient(scaling_stats: list) -> float:
    for entry in scaling_stats or []:
        if isinstance(entry, list) and len(entry) == 2 and entry[0] == "stat_ranged_damage":
            return float(entry[1])
    return 0.0


def _weapon_effect_record(text: str, companion_texts: dict[str, str] | None = None) -> dict:
    """A weapon's on-hit effect as plain scalar fields.

    Drops nested resource references (script, explosion_scene, …) and keeps the
    gameplay scalars — e.g. the Shredder's `key="effect_explode_custom"` with
    `chance=0.5`. The script ext_resource's basename is kept as `script`, since
    the engine dispatches many effects on script class (and blank-key effects
    have nothing else identifying them). Some effects keep their real numbers
    on companion resources instead of inline (burning_data / weapon_stats /
    stats); each given companion's scalar fields nest under its own field name
    rather than flattening, since the files carry unrelated same-named
    boilerplate (e.g. `value`).
    """
    doc = parse_tres(text)
    r = doc.resource
    record = {k: v for k, v in r.items()
              if not (isinstance(v, dict) and ("__ext__" in v or "__sub__" in v))}
    script_ref = r.get("script")
    if isinstance(script_ref, dict) and "__ext__" in script_ref:
        ext = doc.ext_resources.get(script_ref["__ext__"]) or {}
        script_path = str(ext.get("path", ""))
        if script_path:
            record["script"] = script_path.rsplit("/", 1)[-1]
    for field, extra_text in (companion_texts or {}).items():
        extra = parse_tres(extra_text).resource
        record[field] = {k: v for k, v in extra.items()
                        if not (isinstance(v, dict) and ("__ext__" in v or "__sub__" in v))}
    return record


def build_weapon_record(stats_text: str, data_text: str,
                        effect_texts: list[str] | None = None,
                        effect_companion_texts: list[dict[str, str] | None] | None = None, *,
                        weapon_id: str, name: str, tier: int,
                        classes: list[str] | None = None,
                        proc_models: dict | None = None,
                        tr: dict[str, str] | None = None) -> dict:
    s = parse_tres(stats_text).resource
    d = parse_tres(data_text).resource

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

    companions = effect_companion_texts or [None] * len(effect_texts or [])
    effects = [_weapon_effect_record(t, c)
               for t, c in zip(effect_texts or [], companions, strict=True)]
    models = PROC_MODELS if proc_models is None else proc_models
    proc0 = proc_slope = 0.0
    unmodeled: list[str] = []
    for eff in effects:
        model = models.get(str(eff.get("key", "")))
        source = model["damage_source"] if model is not None else None
        if source == "weapon_damage":
            p0, ps = calc.proc_line(dps0, slope, float(eff.get("chance", 1.0)),
                                    model["default_enemies_hit"],
                                    model["damage_multiplier"])
            proc0 += p0
            proc_slope += ps
        elif source == "burn_dot":
            bd = eff.get("burning_data") or {}
            chance = float(bd.get("chance", 0.0))
            damage = bd.get("damage")
            duration = float(bd.get("duration", 0))
            window = duration * model["tick_interval"]
            if chance == 1.0 and damage is not None and window > 0 and ct <= window:
                p0, ps = calc.burn_dps_line(float(damage), model["tick_interval"])
                proc0 += p0
                proc_slope += ps
            elif eff.get("key"):
                unmodeled.append(str(eff["key"]))
        elif source == "companion_ranged_stats":
            ws = eff.get("weapon_stats") or {}
            damage = ws.get("damage")
            count = float(eff.get("value", 0))
            bounce = int(ws.get("bounce", 0)) if bool(ws.get("can_bounce", True)) else 0
            ok = damage is not None and count > 0
            if bool(eff.get("auto_target_enemy", False)):
                # Targeted chain: assume the nominal chain fully connects.
                # No decaying-bounce math exists — lossy bounces fall back.
                ok = ok and (bounce == 0 or float(ws.get("bounce_dmg_reduction", 0.5)) == 0.0)
                enemies_hit = 1.0 + bounce
            else:
                # Untargeted spray: one expected hit per volley (documented
                # assumption, exploding default_enemies_hit precedent).
                ok = ok and bounce == 0
                enemies_hit = 1.0
            if ok:
                p0, ps = calc.companion_dps_line(
                    float(damage), _rd_coefficient(ws.get("scaling_stats") or []),
                    ct, count, enemies_hit)
                proc0 += p0
                proc_slope += ps
            elif eff.get("key"):
                unmodeled.append(str(eff["key"]))
        elif eff.get("key"):
            unmodeled.append(str(eff["key"]))

    return {
        "id": weapon_id,
        "name": name,
        "display_name": resolve_text(tr, d.get("name"), name),
        "description": resolve_text(tr, d.get("description")),
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
        "sets": list(classes or []),
        # On-hit effects (e.g. exploding projectile), resolved from the data
        # .tres `effects` ext_resources. Effects with a verified PROC_MODELS
        # entry contribute the proc_dps_* expected line; the rest are listed
        # in unmodeled_effects.
        "effects": effects,
        "proc_dps_at_zero_rd": proc0,
        "proc_dps_slope_per_rd": proc_slope,
        "unmodeled_effects": unmodeled,
    }
