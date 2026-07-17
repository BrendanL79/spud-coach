import math

import pytest

from brotato_coach import answers

KNIFE_T1 = {
    "id": "weapon_knife", "name": "Knife", "tier": 1,
    "sets": ["Blade"], "effects": [], "unmodeled_effects": [],
    "classified_effects": [], "burst_reload": False, "nb_projectiles": 1,
    "weapon_type": "melee", "base_damage": 9.0, "cooldown": 25.0,
    "recoil_duration": 0.1, "attack_speed_mod": 0.0, "accuracy": 1.0,
    "crit_chance": 0.2, "crit_damage": 2.5, "max_range": 150.0,
    "scaling_stats": [["stat_melee_damage", 0.8]],
    "additional_cooldown_every_x_shots": -1, "additional_cooldown_multiplier": -1.0,
    "proc_effects": [],
}

PISTOL_T1 = {
    "id": "weapon_pistol", "name": "Pistol", "tier": 1,
    "sets": [], "effects": [], "unmodeled_effects": [],
    "classified_effects": [], "burst_reload": False, "nb_projectiles": 1,
    "weapon_type": "ranged", "base_damage": 12.0, "cooldown": 60.0,
    "recoil_duration": 0.1, "attack_speed_mod": 0.0, "accuracy": 0.9,
    "crit_chance": 0.1, "crit_damage": 2.0, "max_range": 400.0,
    "scaling_stats": [["stat_ranged_damage", 1.0]],
    "additional_cooldown_every_x_shots": -1, "additional_cooldown_multiplier": -1.0,
    "proc_effects": [],
}

# ct = 2*0.05 + 0/60 = 0.1s; base 8.0 + rd*1.0 per hit; 50% weapon-damage
# proc re-deals the base line — a synthetic fixture for exercising
# proc_dps/aoe_enemies_hit, not tied to any real weapon's numbers.
SHREDDER_T4 = {
    "id": "weapon_shredder", "name": "Shredder", "tier": 4,
    "sets": [], "effects": [], "unmodeled_effects": [],
    "classified_effects": [], "burst_reload": False, "nb_projectiles": 1,
    "weapon_type": "ranged", "base_damage": 8.0, "cooldown": 0.0,
    "recoil_duration": 0.05, "attack_speed_mod": 0.0, "accuracy": 1.0,
    "crit_chance": 0.0, "crit_damage": 0.0, "max_range": 400.0,
    "scaling_stats": [["stat_ranged_damage", 1.0]],
    "additional_cooldown_every_x_shots": -1, "additional_cooldown_multiplier": -1.0,
    "proc_effects": [{"kind": "weapon_damage", "chance": 0.5,
                      "enemies_hit": 1.0, "multiplier": 1.0}],
}

LASER_T1 = {
    "id": "weapon_laser", "name": "Laser", "tier": 1,
    "sets": [], "effects": [], "unmodeled_effects": [],
    "classified_effects": [], "burst_reload": False, "nb_projectiles": 1,
    "weapon_type": "ranged", "base_damage": 12.0, "cooldown": 60.0,
    "recoil_duration": 0.1, "attack_speed_mod": 0.0, "accuracy": 1.0,
    "crit_chance": 0.0, "crit_damage": 0.0, "max_range": 400.0,
    "scaling_stats": [["stat_ranged_damage", 1.0]],
    "additional_cooldown_every_x_shots": -1, "additional_cooldown_multiplier": -1.0,
    "proc_effects": [],
}

LASER_T2 = {
    **LASER_T1, "tier": 2, "base_damage": 30.0,
}

DS = {
    "weapons": [
        KNIFE_T1, PISTOL_T1, SHREDDER_T4, LASER_T1, LASER_T2,
    ],
    "characters": [
        {"id": "character_ranger", "name": "Ranger",
         "gain_modifiers": [{"stat": "stat_ranged_damage", "pct": 50},
                            {"stat": "stat_max_hp", "pct": -25}]},
    ],
    "sets": [
        {"id": "set_blade", "name": "Blade", "display_name": "Blade", "bonuses": [
            {"count": 2, "effect": {"key": "stat_melee_damage", "value": 1}}]},
    ],
    "stat_mechanics": {
        "stat_attack_speed": {"special": "attack_speed_universal", "never_dead_weight": True},
    },
}


def test_weapon_dps_stat_aware_melee():
    r = answers.weapon_dps(DS, "Knife", 1, {"melee_damage": 20})
    assert r["dps"] == pytest.approx(36.5607476636)
    assert r["breakdown"]["per_hit_damage"] == 25
    assert r["assumptions"]["engagement_distance"] == 70.0


def test_weapon_dps_engagement_override():
    close = answers.weapon_dps(DS, "Knife", 1, {}, engagement_distance=0.0)
    far = answers.weapon_dps(DS, "Knife", 1, {})
    assert close["dps"] > far["dps"]


def test_weapon_dps_loadout_reports_but_does_not_merge():
    r = answers.weapon_dps(DS, "Knife", 1, {}, loadout=["Knife", "Knife"])
    assert r["assumptions"]["set_bonuses_applied"] is False
    assert r["assumptions"]["active_set_bonuses"]  # Blade 2: +1 melee_damage
    base = answers.weapon_dps(DS, "Knife", 1, {})
    assert r["dps"] == base["dps"]


def test_weapon_dps_apply_set_bonuses_merges_stats():
    r = answers.weapon_dps(DS, "Knife", 1, {"melee_damage": 19},
                           loadout=["Knife", "Knife"], apply_set_bonuses=True)
    base = answers.weapon_dps(DS, "Knife", 1, {"melee_damage": 20})
    assert r["dps"] == pytest.approx(base["dps"])


def test_weapon_dps_at_rd():
    result = answers.weapon_dps(DS, "Pistol", 1, {"ranged_damage": 10})
    assert result["dps"] == pytest.approx(18.15)


def test_compare_weapons_shredder_beats_pistol_at_rd10():
    result = answers.compare_weapons(
        DS, [("Pistol", 1), ("Shredder", 4)], {"ranged_damage": 10})
    assert result["ranking"][0]["name"] == "Shredder"


def test_compare_weapons_rows_carry_dps_breakdown():
    result = answers.compare_weapons(
        DS, [("Shredder", 4), ("Pistol", 1)], {"ranged_damage": 10})
    rows = {r["name"]: r for r in result["ranking"]}
    # base 8+10=18 per hit / ct (0.1s shooting + 2-frame-floor cooldown/60)
    # = 18/0.133333 = 135.0; proc 135.0*0.5 = 67.5
    assert math.isclose(rows["Shredder"]["base_dps"], 135.0, rel_tol=1e-4)
    assert math.isclose(rows["Shredder"]["proc_dps"], 67.5, rel_tol=1e-4)
    assert rows["Shredder"]["unmodeled_effects"] == []
    assert rows["Pistol"]["proc_dps"] == 0.0


def test_merge_paths_crossover_at_rd6():
    # one T2 (base 30) vs two T1 (base 12), ct 1.2 both:
    # rd0: 25.0 vs 20.0 (A); rd6: 30.0 vs 30.0 (first B>=A); rd100: B wins
    r = answers.compare_merge_paths(DS, "Laser", [2], [1, 1])
    assert r["crossover_rd"] == 6
    assert r["rd_independent"] is False


def test_merge_paths_dominant_path():
    r = answers.compare_merge_paths(DS, "Laser", [1], [1, 1])
    assert r["winner"] == "b"
    assert r["rd_independent"] is True


def test_merge_paths_interior_flipflop_is_not_rd_independent():
    # A (base 5, x0.4) vs two B (base 2, x0.25), same ct: integer rounding
    # makes the winner sequence a..a with B strictly ahead only at rd 12 —
    # matching endpoint winners must not short-circuit the interior scan.
    ds = {**DS, "weapons": [
        {**LASER_T1, "base_damage": 5.0,
         "scaling_stats": [["stat_ranged_damage", 0.4]]},
        {**LASER_T2, "base_damage": 2.0,
         "scaling_stats": [["stat_ranged_damage", 0.25]]},
    ]}
    r = answers.compare_merge_paths(ds, "Laser", [1], [2, 2], rd_range=(0, 15))
    assert r["rd_independent"] is False
    assert r["winner"] is None
    assert r["crossover_rd"] == 12


def test_merge_paths_forward_fixed_level_stat():
    # Laser rescaled to stat_levels: per_hit = 12 + 1.0 x level, ct 1.2.
    # A fixed stats block with level 5 must reach the profile ->
    # 17/1.2, not 12/1.2.
    ds = {**DS, "weapons": [
        {**LASER_T1, "scaling_stats": [["stat_levels", 1.0]]},
        {**LASER_T2, "scaling_stats": [["stat_levels", 1.0]]},
    ]}
    r = answers.compare_merge_paths(ds, "Laser", [1], [2], rd_range=(0, 10),
                                    stats={"level": 5})
    assert r["dps_a_at_range_ends"][0] == pytest.approx(17 / 1.2)


def test_stat_gradient_ranks_scaling_stat_first():
    r = answers.stat_gradient(DS, [("Knife", 1)], {"melee_damage": 20})
    assert r["baseline_dps"] == pytest.approx(36.5607476636)
    top = r["gradient"][0]
    assert top["stat"] == "melee_damage"
    # md30: d2=33, exp=43.0, dps=48.2242990654
    assert top["dps_delta"] == pytest.approx(48.2242990654 - 36.5607476636)
    by_stat = {g["stat"]: g for g in r["gradient"]}
    assert by_stat["attack_speed"]["dps_after"] == pytest.approx(41.8483864071)
    assert by_stat["crit_chance"]["dps_after"] == pytest.approx(40.8224299065)
    assert by_stat["damage"]["dps_after"] == pytest.approx(40.8224299065)


def test_stat_gradient_flags_saturated_crit():
    r = answers.stat_gradient(DS, [("Knife", 1)], {"crit_chance": 80})
    by_stat = {g["stat"]: g for g in r["gradient"]}
    assert by_stat["crit_chance"]["saturated"] is True


def test_stat_gradient_rejects_nonpositive_step():
    for step in (0, -10):
        r = answers.stat_gradient(DS, [("Knife", 1)], {}, step=step)
        assert r["error"] == "invalid_step"


def test_stat_gradient_empty_loadout_yields_empty_gradient():
    r = answers.stat_gradient(DS, [], {"melee_damage": 20})
    assert r["baseline_dps"] == 0.0
    assert r["gradient"] == []


def test_explain_stat_known():
    result = answers.explain_stat(DS, "stat_attack_speed")
    assert result["never_dead_weight"] is True


def test_stat_display_value_ranger_rd():
    result = answers.stat_display_value(DS, "Ranger", "stat_ranged_damage", 6)
    assert result["displayed_value"] == 9
    assert result["modifier_pct"] == 50


def test_stat_display_value_no_modifier():
    result = answers.stat_display_value(DS, "Ranger", "stat_speed", 10)
    assert result["displayed_value"] == 10
    assert result["modifier_pct"] == 0


def test_display_stats_applies_gain_modifiers_by_short_name():
    result = answers.display_stats(DS, "Ranger", {"ranged_damage": 6, "speed": 10})
    assert result == {"ranged_damage": 9, "speed": 10}


def test_display_stats_unknown_character_returns_raw():
    result = answers.display_stats(DS, "Nonexistent", {"ranged_damage": 6})
    assert result == {"ranged_damage": 6}


def test_weapon_dps_with_character_uses_displayed_stats():
    # raw RD 6 -> Ranger's +50% gain modifier -> displayed RD 9
    result = answers.weapon_dps(DS, "Pistol", 1, {"ranged_damage": 6}, character="Ranger")
    assert result["dps"] == pytest.approx(17.325)


def test_weapon_dps_without_character_uses_raw_stats():
    result = answers.weapon_dps(DS, "Pistol", 1, {"ranged_damage": 6})
    assert result["dps"] == pytest.approx(14.85)


def test_compare_weapons_rows_carry_assumptions():
    # the server docstring promises per-row active set-bonus reporting;
    # each ranking row must keep weapon_dps' assumptions block
    r = answers.compare_weapons(DS, [("Knife", 1), ("Pistol", 1)], {},
                                loadout=["Knife", "Knife"])
    for row in r["ranking"]:
        a = row["assumptions"]
        assert a["set_bonuses_applied"] is False
        assert a["active_set_bonuses"]  # the 2-Blade bonus is active


def test_compare_weapons_with_character_uses_displayed_stats():
    result = answers.compare_weapons(
        DS, [("Pistol", 1)], {"ranged_damage": 6}, character="Ranger")
    assert result["ranking"][0]["dps"] == pytest.approx(17.325)


def test_weapon_dps_adds_expected_proc_contribution():
    result = answers.weapon_dps(DS, "Shredder", 4, {"ranged_damage": 10})
    assert math.isclose(result["base_dps"], 135.0, rel_tol=1e-4)
    assert math.isclose(result["proc_dps"], 67.5, rel_tol=1e-4)
    assert math.isclose(result["dps"], 202.5, rel_tol=1e-4)


def test_weapon_dps_aoe_scales_proc_term_only():
    result = answers.weapon_dps(DS, "Shredder", 4, {"ranged_damage": 10},
                                aoe_enemies_hit=3.0)
    assert math.isclose(result["proc_dps"], 202.5, rel_tol=1e-4)
    assert math.isclose(result["base_dps"], 135.0, rel_tol=1e-4)


def test_weapon_dps_records_without_proc_fields_still_work():
    result = answers.weapon_dps(DS, "Pistol", 1, {"ranged_damage": 10})
    assert result["proc_dps"] == 0.0
    assert math.isclose(result["dps"], result["base_dps"])


def test_compare_merge_paths_not_found_suggests_display_name():
    ds = {"weapons": [{"id": "weapon_laser", "name": "Laser",
                       "display_name": "Laser Blaster", "tier": 1,
                       "dps_at_zero_rd": 15.0, "dps_slope_per_rd": 0.9}]}
    result = answers.compare_merge_paths(ds, "laser blaster X", [1], [1])
    assert result["error"] == "not_found"
    assert "Laser Blaster" in result["did_you_mean"]


SETS_DS = {
    "weapons": [
        {"id": "weapon_smg", "name": "SMG", "tier": 1, "sets": ["Gun"]},
        {"id": "weapon_pistol", "name": "Pistol", "tier": 2, "sets": ["Gun", "Precise"]},
        {"id": "weapon_knife", "name": "Knife", "tier": 1, "sets": ["Blade", "Precise"]},
    ],
    "sets": [
        {"id": "set_gun", "name": "Gun", "bonuses": [
            {"count": 2, "effect": {"key": "stat_range", "value": 10}},
            {"count": 4, "effect": {"key": "stat_range", "value": 20}}]},
        {"id": "set_precise", "name": "Precise", "bonuses": [
            {"count": 2, "effect": {"key": "stat_crit_chance", "value": 5}}]},
        {"id": "set_blade", "name": "Blade", "bonuses": [
            {"count": 2, "effect": {"key": "stat_lifesteal", "value": 2}}]},
    ],
}


def test_loadout_set_bonuses_counts_duplicates_and_reports_next():
    result = answers.loadout_set_bonuses(SETS_DS, ["SMG", "SMG", "Pistol", "Knife"])
    by_class = {c["class"]: c for c in result["classes"]}
    gun = by_class["Gun"]  # SMG x2 + Pistol = 3
    assert gun["count"] == 3
    assert gun["active"] == [{"count": 2, "effect": {"key": "stat_range", "value": 10}}]
    assert gun["next"]["count"] == 4
    assert gun["next"]["needs"] == 1


def test_loadout_set_bonuses_maxed_class_has_no_next():
    result = answers.loadout_set_bonuses(SETS_DS, ["Pistol", "Knife"])
    by_class = {c["class"]: c for c in result["classes"]}
    assert by_class["Precise"]["count"] == 2
    assert by_class["Precise"]["next"] is None
    assert len(by_class["Precise"]["active"]) == 1


def test_loadout_set_bonuses_below_first_threshold():
    result = answers.loadout_set_bonuses(SETS_DS, ["Knife"])
    by_class = {c["class"]: c for c in result["classes"]}
    assert by_class["Blade"]["active"] == []
    assert by_class["Blade"]["next"]["needs"] == 1


def test_loadout_set_bonuses_unknown_weapon_suggested():
    result = answers.loadout_set_bonuses(SETS_DS, ["Knifee"])
    assert result["classes"] == []
    assert result["unknown_weapons"][0]["name"] == "Knifee"
    assert "Knife" in result["unknown_weapons"][0]["did_you_mean"]


def test_weapon_dps_includes_cadence_when_cycle_time_present():
    result = answers.weapon_dps(DS, "Pistol", 1, {"ranged_damage": 10})
    cad = result["cadence"]
    assert cad["cadence"] == "bursty"
    assert math.isclose(cad["attacks_per_second"], 1 / 1.2, rel_tol=1e-9)
    # Invariant holds against the report's own dps
    assert math.isclose(
        cad["damage_per_attack"] * cad["attacks_per_second"], result["dps"], rel_tol=1e-9)


# Note: the game's 2-frame minimum cooldown (GD_MIN_COOLDOWN, applied inside
# calc.stat_aware_cycle_time via calc.effective_cooldown) means cycle_time is
# always > 0 for any real weapon record, so weapon_dps's "no cadence" branch
# (calc.py's `if profile["cycle_time"] > 0`) is a defensive guard rather than
# a reachable case worth a dedicated fixture — unlike the old precomputed-line
# schema, where an absent `cycle_time` field was a normal, common shape.


def test_compare_weapons_rows_carry_cadence():
    result = answers.compare_weapons(
        DS, [("Pistol", 1), ("Shredder", 4)], {"ranged_damage": 10}, weapon_count=2)
    rows = {r["name"]: r for r in result["ranking"]}
    assert rows["Pistol"]["cadence"]["cadence"] == "bursty"
    assert rows["Shredder"]["cadence"]["cadence"] == "sustained"
    # Sort order still DPS-descending, unchanged
    assert result["ranking"][0]["name"] == "Shredder"


def test_character_class_synergy_matches_weapons_in_bonus_set():
    ds = {
        "characters": [
            {"id": "character_crazy", "name": "Crazy", "class_bonuses": [
                {"set_id": "set_precise", "set_name": "Precise",
                 "stat": "max_range", "stat_displayed": "stat_range",
                 "value": 100}]},
            {"id": "character_plain", "name": "Plain", "class_bonuses": []},
        ],
        "weapons": [
            {"id": "weapon_knife", "name": "Knife", "tier": 1, "sets": ["Precise"]},
            {"id": "weapon_pistol", "name": "Pistol", "tier": 1, "sets": ["Gun"]},
        ],
    }
    out = answers.character_class_synergy(ds, "Crazy", ["Knife", "Pistol"])
    assert out["character"] == "Crazy"
    assert len(out["bonuses"]) == 1
    b = out["bonuses"][0]
    assert b["value"] == 100
    assert b["stat_displayed"] == "stat_range"
    assert b["matched_weapons"] == ["Knife"]


def test_character_class_synergy_empty_for_character_without_bonus():
    ds = {
        "characters": [{"id": "character_plain", "name": "Plain",
                        "class_bonuses": []}],
        "weapons": [{"id": "weapon_knife", "name": "Knife", "tier": 1,
                     "sets": ["Precise"]}],
    }
    out = answers.character_class_synergy(ds, "Plain", ["Knife"])
    assert out["bonuses"] == []


def test_character_class_synergy_handles_multi_tier_weapon_matches():
    # A weapon id present at multiple tiers makes query.get_weapon return
    # {"matches": [...]} rather than a single record. character_class_synergy
    # takes matches[0] (set membership is tier-independent) — this exercises
    # that branch, which every real weapon lookup hits in production.
    ds = {
        "characters": [
            {"id": "character_crazy", "name": "Crazy", "class_bonuses": [
                {"set_id": "set_precise", "set_name": "Precise",
                 "stat": "max_range", "stat_displayed": "stat_range",
                 "value": 100}]},
        ],
        "weapons": [
            {"id": "weapon_knife", "name": "Knife", "tier": 1, "sets": ["Precise"]},
            {"id": "weapon_knife", "name": "Knife", "tier": 2, "sets": ["Precise"]},
        ],
    }
    out = answers.character_class_synergy(ds, "Crazy", ["Knife"])
    assert out["bonuses"][0]["matched_weapons"] == ["Knife"]
