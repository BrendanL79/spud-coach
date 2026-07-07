"""Pure logic over the bestiary dataset arrays. No I/O.

Effective per-wave stats use base + increase_each_wave * (wave - 1), matching
the game's (current_wave - 1) scaling. Movement speed is a range because the
game rolls speed +/- speed_randomization per spawn.
"""

from __future__ import annotations

from brotato_coach import query


def effective_stats(enemy: dict, wave: int) -> dict:
    base, slope = enemy["base"], enemy["per_wave"]
    n = wave - 1
    spd, rnd = base.get("speed", 0), base.get("speed_randomization", 0)
    return {
        "health": base.get("health", 0) + slope.get("health", 0) * n,
        "damage": base.get("damage", 0) + slope.get("damage", 0) * n,
        "armor": base.get("armor", 0) + slope.get("armor", 0) * n,
        "speed_range": [spd - rnd, spd + rnd],
    }


def _match(enemies: list[dict], name: str) -> dict | None:
    low = name.lower()
    for e in enemies:
        if low in (e.get("id", "").lower(), e.get("name", "").lower(),
                   e.get("display_name", "").lower()):
            return e
    return None


def get_enemy(ds: dict, name: str, wave: int | None = None) -> dict:
    enemies = ds.get("enemies", [])
    enemy = _match(enemies, name)
    if enemy is None:
        return {"error": "not_found", "did_you_mean": query.suggest(enemies, name)}
    if wave is None:
        return enemy
    return {**enemy, "effective": effective_stats(enemy, wave)}


def list_enemies(ds: dict, *, appears_in=None, ability=None, attack_kind=None) -> list[dict]:
    out = []
    for e in ds.get("enemies", []):
        if appears_in is not None and appears_in not in e.get("appears_in", []):
            continue
        if ability is not None and ability not in e.get("abilities", []):
            continue
        if attack_kind is not None and e.get("attack", {}).get("kind") != attack_kind:
            continue
        out.append({"id": e["id"], "name": e["name"],
                    "attack_kind": e.get("attack", {}).get("kind"),
                    "appears_in": e.get("appears_in", [])})
    return out


_SCALES_WITH = ["number_of_enemies % (item/character modifier)",
                "co-op player count"]
_ELITE_HORDE_LABEL = ("elite/horde waves are scheduled per-run (randomized at "
                      "run start) — treat as possible on this wave, not guaranteed")


def _wave_record(ds: dict, wave: int) -> dict | None:
    for w in ds.get("zone_1_waves", []):
        if w.get("wave") == wave:
            return w
    return None


def wave_composition(ds: dict, wave: int, danger: int | None = None) -> dict:
    w = _wave_record(ds, wave)
    if w is None:
        return {"error": "not_found", "detail": f"no base-game wave {wave} (valid 1-20)"}
    groups = []
    for g in w.get("groups", []):
        if danger is not None and not (g["min_danger"] <= danger <= g["max_danger"]):
            continue
        groups.append(g)
    return {
        "wave": wave,
        "wave_duration": w.get("wave_duration"),
        "max_enemies": w.get("max_enemies"),
        "base_enemies": groups,
        "scales_with": _SCALES_WITH,
        "elite_horde": _ELITE_HORDE_LABEL,
        "notes": ["base_count and repeats are pre-modifier base values"],
    }


def wave_context(ds: dict, wave: int, danger: int | None = None) -> dict:
    comp = wave_composition(ds, wave, danger)
    if comp.get("error"):
        return comp
    by_id = {e["id"]: e for e in ds.get("enemies", [])}
    present_ids = [g["enemy_id"] for g in comp["base_enemies"]]

    # enemies first seen in the ~3 waves ending at `wave`
    recent = set()
    earlier = set()
    for w in ds.get("zone_1_waves", []):
        wv = w.get("wave")
        if wv is None:
            continue
        ids = {g["enemy_id"] for g in w.get("groups", [])}
        if wv < wave - 2:
            earlier |= ids
        elif wv <= wave:
            recent |= ids
    newly_introduced = sorted(recent - earlier)

    effective_threat = []
    for eid in dict.fromkeys(present_ids):  # de-dup, preserve order
        e = by_id.get(eid)
        if e is None:
            continue
        eff = effective_stats(e, wave)
        effective_threat.append({
            "enemy_id": eid,
            "attack_kind": e.get("attack", {}).get("kind"),
            "health": eff["health"],
            "damage": eff["damage"],
        })
    return {
        "death_wave": wave,
        "composition": comp,
        "newly_introduced": newly_introduced,
        "effective_threat": effective_threat,
        "elite_horde_note": (
            f"wave {wave} can roll an elite/horde (per-run, randomized); "
            "if you hit a wall here, that may be why"),
    }
