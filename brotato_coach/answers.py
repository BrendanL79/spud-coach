from __future__ import annotations

import difflib

from brotato_coach import bestiary, calc, evaluate, query, runfile


def _weapon_at(ds: dict, name: str, tier: int) -> dict | None:
    rec = query.get_weapon(ds, name, tier=tier)
    return rec if "id" in rec else None


def display_stats(ds: dict, character: str, raw_stats: dict) -> dict:
    """Convert raw stats (short names, e.g. ranged_damage) to the values the
    game DISPLAYS for `character`, applying that character's stat-gain
    modifiers. Unknown characters pass the stats through unchanged."""
    rec = query.get_character(ds, character)
    mods = {m["stat"]: m["pct"] for m in rec.get("gain_modifiers", [])} if "id" in rec else {}
    out = {}
    for short, value in raw_stats.items():
        pct = mods.get(f"stat_{short}", 0)
        displayed = value * (1 + pct / 100)
        out[short] = int(displayed) if float(displayed).is_integer() else displayed
    return out


def _merge_set_bonus_stats(stats: dict, active: list[dict]) -> dict:
    """Fold active set-bonus stat grants (full stat_* keys) into a short-name
    stat block. Only used when the caller opts in — screen/save stats already
    include these grants in-game."""
    out = dict(stats)
    for bonus in active:
        eff = bonus.get("effect") or {}
        key, value = eff.get("key"), eff.get("value")
        if not key or value is None:
            continue
        short = calc._SHORT_BY_STAT_NAME.get(key, str(key).removeprefix("stat_"))
        out[short] = float(out.get(short, 0)) + float(value)
    return out


def weapon_dps(ds: dict, name: str, tier: int, stats: dict,
               aoe_enemies_hit: float = 1.0, character: str | None = None,
               weapon_count: int = 1, engagement_distance: float | None = None,
               loadout: list[str] | None = None,
               apply_set_bonuses: bool = False) -> dict:
    rec = query.get_weapon(ds, name, tier=tier)
    if "id" not in rec:
        return rec
    if character is not None:
        stats = display_stats(ds, character, stats)

    active_bonuses: list[dict] = []
    if loadout:
        for cls in loadout_set_bonuses(ds, loadout)["classes"]:
            active_bonuses.extend(cls["active"])
        if apply_set_bonuses:
            stats = _merge_set_bonus_stats(stats, active_bonuses)

    profile = calc.weapon_dps_profile(
        rec, stats, level=float(stats.get("level", 0)),
        aoe_enemies_hit=aoe_enemies_hit,
        engagement_distance=engagement_distance)

    assumptions = {"aoe_enemies_hit": aoe_enemies_hit,
                   "set_bonuses_applied": bool(loadout and apply_set_bonuses)}
    if profile["engagement_distance_used"] is not None:
        assumptions["engagement_distance"] = profile["engagement_distance_used"]
    if loadout:
        assumptions["active_set_bonuses"] = active_bonuses

    result = {
        "name": rec["name"], "tier": tier,
        "dps": profile["dps"], "base_dps": profile["base_dps"],
        "proc_dps": profile["proc_dps"],
        "unmodeled_effects": rec.get("unmodeled_effects", []),
        "breakdown": {
            "per_hit_damage": profile["per_hit_damage"],
            "expected_hit_damage": profile["expected_hit_damage"],
            "cycle_time": profile["cycle_time"],
            "crit_chance_total": profile["crit_chance_total"],
            "scaling_stats": rec.get("scaling_stats", []),
        },
        "assumptions": assumptions,
    }
    if profile["cycle_time"] > 0:
        result["cadence"] = calc.cadence_profile(
            profile["cycle_time"], profile["dps"],
            float(profile["effective_cooldown_frames"]),
            weapon_count=weapon_count,
            burst_reload=bool(rec.get("burst_reload", False)))
    return result


def compare_weapons(ds: dict, names_with_tiers: list, stats: dict,
                    aoe_enemies_hit: float = 1.0, character: str | None = None,
                    weapon_count: int = 1, engagement_distance: float | None = None,
                    loadout: list[str] | None = None,
                    apply_set_bonuses: bool = False) -> dict:
    if character is not None:
        stats = display_stats(ds, character, stats)
    rows = []
    for name, tier in names_with_tiers:
        r = weapon_dps(ds, name, tier, stats, aoe_enemies_hit,
                       weapon_count=weapon_count,
                       engagement_distance=engagement_distance,
                       loadout=loadout, apply_set_bonuses=apply_set_bonuses)
        if "dps" in r:
            row = {"name": r["name"], "tier": tier, "dps": r["dps"],
                   "base_dps": r["base_dps"], "proc_dps": r["proc_dps"],
                   "unmodeled_effects": r["unmodeled_effects"],
                   "assumptions": r["assumptions"]}
            if "cadence" in r:
                row["cadence"] = r["cadence"]
            rows.append(row)
    rows.sort(key=lambda x: x["dps"], reverse=True)
    return {"ranking": rows}


def compare_merge_paths(ds: dict, weapon_name: str, path_a: list, path_b: list,
                        rd_range: tuple = (0, 100), stats: dict | None = None) -> dict:
    """Compare two tier-merge paths across the ranged-damage range at an
    otherwise-fixed stat block (default all-zero). Game-exact DPS is a step
    function of RD, so the crossover is the first integer RD in the range
    where the high-end winner weakly overtakes — not an algebraic intersection.
    """
    base_stats = dict(stats or {})

    def total(tiers: list, rd: int) -> float | None:
        s = dict(base_stats, ranged_damage=rd)
        acc = 0.0
        for t in tiers:
            rec = _weapon_at(ds, weapon_name, t)
            if rec is None:
                return None
            acc += calc.weapon_dps_profile(rec, s, level=float(s.get("level", 0)))["dps"]
        return acc

    lo, hi = int(rd_range[0]), int(rd_range[1])
    if total(path_a, lo) is None or total(path_b, lo) is None:
        return {"error": "not_found",
                "did_you_mean": query.suggest(ds["weapons"], weapon_name)}
    # Independently rounded tier curves can overtake mid-range and return, so
    # matching endpoint winners prove nothing — evaluate every integer RD.
    dps_a = [total(path_a, rd) for rd in range(lo, hi + 1)]
    dps_b = [total(path_b, rd) for rd in range(lo, hi + 1)]

    def _winner(a: float, b: float) -> str:
        if abs(a - b) < 1e-9:
            return "tie"
        return "a" if a > b else "b"

    result = {"weapon": weapon_name, "path_a": path_a, "path_b": path_b,
              "dps_a_at_range_ends": [dps_a[0], dps_a[-1]],
              "dps_b_at_range_ends": [dps_b[0], dps_b[-1]]}
    winners = [_winner(a, b) for a, b in zip(dps_a, dps_b, strict=True)]
    strict = [w for w in winners if w != "tie"]
    if not strict:
        return {**result, "winner": "tie", "rd_independent": True, "crossover_rd": None}
    w0 = strict[0]
    if all(w == w0 for w in strict):
        return {**result, "winner": w0, "rd_independent": True, "crossover_rd": None}
    # Crossover = first strict win by the other path, walked back over the
    # contiguous weak-overtake (tie) run leading into it.
    other = "b" if w0 == "a" else "a"
    idx = winners.index(other)
    weak = (lambda i: dps_b[i] >= dps_a[i]) if other == "b" else (lambda i: dps_a[i] >= dps_b[i])
    while idx > 0 and weak(idx - 1):
        idx -= 1
    return {**result, "winner": None, "rd_independent": False, "crossover_rd": lo + idx}


_UNIVERSAL_GRADIENT_STATS = ("damage", "attack_speed", "crit_chance")


def stat_gradient(ds: dict, weapons: list, stats: dict, step: float = 10.0,
                  character: str | None = None, aoe_enemies_hit: float = 1.0,
                  engagement_distance: float | None = None) -> dict:
    """Rank stats by how much +`step` of each would raise the loadout's total
    DPS. Candidates = the union of the loadout's scaling stats plus the
    universal multipliers (%damage, attack speed, crit chance). The default
    step of 10 is deliberate: the game's integer damage arithmetic makes a
    ±1 delta frequently zero and unrepresentative.
    """
    if step <= 0:
        return {"error": "invalid_step", "note": "step must be > 0"}
    if character is not None:
        stats = display_stats(ds, character, stats)
    recs = []
    for name, tier in weapons:
        rec = _weapon_at(ds, name, tier)
        if rec is None:
            return {"error": "not_found",
                    "did_you_mean": query.suggest(ds["weapons"], name)}
        recs.append(rec)
    if not recs:
        # No weapons ⇒ nothing scales; an empty gradient beats three all-zero
        # rows whose crit "saturated" flag would be vacuously True (all([])).
        return {"baseline_dps": 0.0, "step": step, "gradient": [],
                "note": "no weapons in loadout — nothing to rank"}

    def total(s: dict) -> float:
        return sum(calc.weapon_dps_profile(
            r, s, level=float(s.get("level", 0)),
            aoe_enemies_hit=aoe_enemies_hit,
            engagement_distance=engagement_distance)["dps"] for r in recs)

    candidates: list[str] = []
    for rec in recs:
        for entry in rec.get("scaling_stats") or []:
            name = entry[0]
            if name == "stat_levels":
                continue
            short = calc._SHORT_BY_STAT_NAME.get(name, name.removeprefix("stat_"))
            if short not in candidates:
                candidates.append(short)
    for short in _UNIVERSAL_GRADIENT_STATS:
        if short not in candidates:
            candidates.append(short)

    baseline = total(stats)
    rows = []
    for short in candidates:
        bumped = dict(stats)
        bumped[short] = float(bumped.get(short, 0)) + step
        after = total(bumped)
        row = {"stat": short, "dps_after": after,
               "dps_delta": after - baseline,
               "dps_delta_per_point": (after - baseline) / step}
        if short == "crit_chance":
            row["saturated"] = all(
                calc.weapon_dps_profile(r, stats)["crit_chance_total"] >= 1.0
                for r in recs)
        rows.append(row)
    rows.sort(key=lambda x: x["dps_delta"], reverse=True)
    return {"baseline_dps": baseline, "step": step, "gradient": rows,
            "note": f"delta per +{step} of each stat; integer game arithmetic makes "
                    "small steps non-representative"}


def explain_stat(ds: dict, stat: str) -> dict:
    mechanics = ds.get("stat_mechanics", {})
    if stat not in mechanics:
        return {"error": "unknown_stat",
                "did_you_mean": difflib.get_close_matches(stat, list(mechanics), n=3, cutoff=0.4)}
    return {"stat": stat, **mechanics[stat]}


def stat_display_value(ds: dict, character: str, stat: str, raw_value: float) -> dict:
    rec = query.get_character(ds, character)
    modifier_pct = 0
    if "id" in rec:
        for mod in rec.get("gain_modifiers", []):
            if mod["stat"] == stat:
                modifier_pct = mod["pct"]
                break
    displayed = raw_value * (1 + modifier_pct / 100)
    displayed = int(displayed) if float(displayed).is_integer() else displayed
    return {"stat": stat, "raw_value": raw_value, "displayed_value": displayed,
            "modifier_pct": modifier_pct}


def loadout_set_bonuses(ds: dict, weapon_names: list[str]) -> dict:
    counts: dict[str, int] = {}
    unknown: list[dict] = []
    for name in weapon_names:
        rec = query.get_weapon(ds, name)
        if "matches" in rec:
            rec = rec["matches"][0]  # class membership is tier-independent
        if "id" not in rec:
            unknown.append({"name": name,
                            "did_you_mean": rec.get("did_you_mean", [])})
            continue
        for cls in rec.get("sets", []):
            counts[cls] = counts.get(cls, 0) + 1  # duplicates count in-game

    classes = []
    for cls in sorted(counts):
        n = counts[cls]
        set_rec = query.get_set(ds, cls)
        bonuses = set_rec.get("bonuses", []) if "id" in set_rec else []
        active = [b for b in bonuses if b["count"] <= n]
        upcoming = [b for b in bonuses if b["count"] > n]
        nxt = None
        if upcoming:
            first = min(upcoming, key=lambda b: b["count"])
            nxt = {**first, "needs": first["count"] - n}
        classes.append({"class": cls, "count": n, "active": active, "next": nxt})
    return {"classes": classes, "unknown_weapons": unknown}


def character_class_synergy(ds: dict, character: str, weapon_names: list[str]) -> dict:
    """Which equipped weapons benefit from the character's class bonuses.

    A ClassBonusEffect grants `value` of a stat to weapons of a given set
    (e.g. Crazy: +100 range to Precise weapons). This joins the character's
    class_bonuses to `weapon_names` by set membership. Advisory only — it does
    NOT alter any DPS number (range/attack-speed/lifesteal are not in the
    RD-only DPS line; see the read_me primer)."""
    rec = query.get_character(ds, character)
    bonuses = rec.get("class_bonuses", []) if "id" in rec else []
    out = []
    for b in bonuses:
        matched = []
        for name in weapon_names:
            w = query.get_weapon(ds, name)
            if "matches" in w:
                w = w["matches"][0]  # set membership is tier-independent
            if "id" not in w:
                continue
            if b.get("set_name") in (w.get("sets") or []):
                matched.append(w["name"])
        out.append({**b, "matched_weapons": matched})
    return {"character": rec.get("name", character), "bonuses": out}


def evaluate_run(ds: dict, run: dict) -> dict:
    """One-call run post-mortem: parse a Brotato save and evaluate the whole
    build against the loaded dataset.

    Returns run context, realized stats, a weapon-DPS ranking at those stats,
    weapon-class set progress, and a per-item live/wasted/harmful verdict.
    `realized_stats` (and everything computed from it) is the save's raw
    effects converted through the character's stat-gain modifiers, matching
    what the game displays — not the raw accumulator value.
    Unknown weapon/item ids (e.g. content newer than the dataset) are collected
    in `notes` rather than dropped silently. A malformed save comes back as
    `{"error": "bad_run_format", "detail": ...}`.
    """
    try:
        build = runfile.parse_run(run)
    except runfile.RunFormatError as exc:
        return {"error": "bad_run_format", "detail": str(exc)}

    notes: list[str] = []

    char_rec = query.get_character(ds, build["character"])
    char_name = char_rec["name"] if "id" in char_rec else build["character"]
    if "id" not in char_rec:
        notes.append(f"unknown character '{build['character']}' — "
                     "not in the loaded dataset")

    # Convert once: raw effects values -> displayed (post-gain-modifier)
    # values, matching what the player actually sees and what weapon_dps'
    # stat-aware DPS engine expects.
    stats = display_stats(ds, build["character"], build["stats"])

    ranking = compare_weapons(
        ds, [(w["id"], w["tier"]) for w in build["weapons"]], stats,
        weapon_count=len(build["weapons"]))["ranking"]

    # stat_gradient (unlike compare_weapons) errors out on any unknown
    # weapon rather than skipping it -- filter to known weapons here so an
    # unrecognized id (already surfaced via notes below) doesn't blow up
    # the whole report.
    known_weapons = [(w["id"], w["tier"]) for w in build["weapons"]
                     if _weapon_at(ds, w["id"], w["tier"]) is not None]
    top_stat_gradient = stat_gradient(ds, known_weapons, stats)["gradient"][:5]

    weapon_ids = [w["id"] for w in build["weapons"]]
    set_bonuses = loadout_set_bonuses(ds, weapon_ids)
    notes.extend(
        f"unknown weapon '{u['name']}' — not in the loaded dataset"
        for u in set_bonuses.get("unknown_weapons", [])
    )

    class_synergy = character_class_synergy(ds, build["character"], weapon_ids)

    item_verdicts = []
    for item_id in build["items"]:
        verdict = evaluate.evaluate_item_for_build(ds, item_id, build["character"], stats)
        if "summary" in verdict:
            item_verdicts.append(verdict)
        else:
            notes.append(f"unknown item '{item_id}' — not in the loaded dataset")

    ctx = build["context"]
    if ctx.get("coop"):
        notes.append("co-op run — only player 1's build was analyzed")

    wave_no = ctx.get("wave")
    if isinstance(wave_no, int) and any(
            w.get("wave") == wave_no for w in ds.get("zone_1_waves", [])):
        wave_ctx = bestiary.wave_context(ds, wave_no, ctx.get("danger"))
    else:
        wave_ctx = {"death_wave": wave_no,
                    "note": "no base-game wave data for this wave "
                            "(endless, or wave outside 1-20)"}

    return {
        "run": {"character": char_name, "character_id": build["character"], **ctx},
        "realized_stats": stats,
        "weapons": build["weapons"],
        "weapon_dps_ranking": ranking,
        "top_stat_gradient": top_stat_gradient,
        "set_bonuses": set_bonuses,
        "class_synergy": class_synergy,
        "item_verdicts": item_verdicts,
        "wave_context": wave_ctx,
        "notes": notes,
    }
