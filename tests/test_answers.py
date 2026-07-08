import math

from brotato_coach import answers

DS = {
    "weapons": [
        {"id": "weapon_minigun", "name": "Minigun", "tier": 4,
         "dps_at_zero_rd": 55.5556, "dps_slope_per_rd": 8.3333, "scaling_stats": []},
        {"id": "weapon_revolver", "name": "Revolver", "tier": 4,
         "dps_at_zero_rd": 57.35, "dps_slope_per_rd": 2.8673, "scaling_stats": []},
        {"id": "weapon_laser", "name": "Laser", "tier": 2,
         "dps_at_zero_rd": 30.0, "dps_slope_per_rd": 1.8, "scaling_stats": []},
        {"id": "weapon_laser", "name": "Laser", "tier": 3,
         "dps_at_zero_rd": 45.0, "dps_slope_per_rd": 2.7, "scaling_stats": []},
        {"id": "weapon_laser", "name": "Laser", "tier": 1,
         "dps_at_zero_rd": 15.0, "dps_slope_per_rd": 0.9,
         "proc_dps_at_zero_rd": 3.0, "proc_dps_slope_per_rd": 0.1,
         "scaling_stats": []},
        {"id": "weapon_shredder", "name": "Shredder", "tier": 4,
         "dps_at_zero_rd": 23.8095, "dps_slope_per_rd": 0.47619,
         "proc_dps_at_zero_rd": 11.9048, "proc_dps_slope_per_rd": 0.238095,
         "unmodeled_effects": [], "scaling_stats": []},
    ],
    "characters": [
        {"id": "character_ranger", "name": "Ranger",
         "gain_modifiers": [{"stat": "stat_ranged_damage", "pct": 50},
                            {"stat": "stat_max_hp", "pct": -25}]},
    ],
    "stat_mechanics": {
        "stat_attack_speed": {"special": "attack_speed_universal", "never_dead_weight": True},
    },
}


def test_weapon_dps_at_rd():
    result = answers.weapon_dps(DS, "Minigun", 4, {"ranged_damage": 10})
    assert math.isclose(result["dps"], 55.5556 + 8.3333 * 10, rel_tol=1e-4)


def test_compare_weapons_minigun_beats_revolver_at_rd10():
    result = answers.compare_weapons(
        DS, [("Minigun", 4), ("Revolver", 4)], {"ranged_damage": 10})
    assert result["ranking"][0]["name"] == "Minigun"


def test_compare_weapons_rows_carry_dps_breakdown():
    result = answers.compare_weapons(
        DS, [("Shredder", 4), ("Minigun", 4)], {"ranged_damage": 10})
    rows = {r["name"]: r for r in result["ranking"]}
    # base 23.8095 + 0.47619*10 = 28.5714; proc 11.9048 + 0.238095*10 = 14.2857
    assert math.isclose(rows["Shredder"]["base_dps"], 28.5714, rel_tol=1e-4)
    assert math.isclose(rows["Shredder"]["proc_dps"], 14.2857, rel_tol=1e-4)
    assert rows["Shredder"]["unmodeled_effects"] == []
    assert rows["Minigun"]["proc_dps"] == 0.0


def test_compare_merge_paths_crossover_reported():
    # path_a = II+II (two tier-2), path_b = III+I (tier-3 + tier-1)
    result = answers.compare_merge_paths(DS, "Laser", [2, 2], [3, 1])
    # II+II line: (60.0, 3.6); III+I line: (60.0, 3.6) -> effectively tie
    assert "crossover_rd" in result


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
    result = answers.weapon_dps(DS, "Minigun", 4, {"ranged_damage": 6}, character="Ranger")
    assert math.isclose(result["dps"], 55.5556 + 8.3333 * 9, rel_tol=1e-4)


def test_weapon_dps_without_character_uses_raw_stats():
    result = answers.weapon_dps(DS, "Minigun", 4, {"ranged_damage": 6})
    assert math.isclose(result["dps"], 55.5556 + 8.3333 * 6, rel_tol=1e-4)


def test_compare_weapons_with_character_uses_displayed_stats():
    result = answers.compare_weapons(
        DS, [("Minigun", 4)], {"ranged_damage": 6}, character="Ranger")
    assert math.isclose(result["ranking"][0]["dps"], 55.5556 + 8.3333 * 9, rel_tol=1e-4)


def test_weapon_dps_adds_expected_proc_contribution():
    result = answers.weapon_dps(DS, "Shredder", 4, {"ranged_damage": 10})
    # base 23.8095 + 0.47619*10 = 28.5714; proc 11.9048 + 0.238095*10 = 14.2857
    assert math.isclose(result["base_dps"], 28.5714, rel_tol=1e-4)
    assert math.isclose(result["proc_dps"], 14.2857, rel_tol=1e-4)
    assert math.isclose(result["dps"], 42.8571, rel_tol=1e-4)


def test_weapon_dps_aoe_scales_proc_term_only():
    result = answers.weapon_dps(DS, "Shredder", 4, {"ranged_damage": 10},
                                aoe_enemies_hit=3.0)
    assert math.isclose(result["proc_dps"], 3 * 14.2857, rel_tol=1e-4)
    assert math.isclose(result["base_dps"], 28.5714, rel_tol=1e-4)


def test_weapon_dps_records_without_proc_fields_still_work():
    result = answers.weapon_dps(DS, "Minigun", 4, {"ranged_damage": 10})
    assert result["proc_dps"] == 0.0
    assert math.isclose(result["dps"], result["base_dps"])


def test_compare_merge_paths_includes_proc_lines():
    result = answers.compare_merge_paths(DS, "Laser", [2, 2], [3, 1])
    # path_b = T3 (45, 2.7) + T1 (15+3, 0.9+0.1) = (63.0, 3.7)
    assert math.isclose(result["line_b"][0], 63.0)
    assert math.isclose(result["line_b"][1], 3.7)


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
