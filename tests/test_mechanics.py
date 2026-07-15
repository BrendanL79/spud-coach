from brotato_coach.builders.mechanics import STAT_MECHANICS


def test_weapon_scaling_damage_stats_encoded():
    for stat in ("stat_ranged_damage", "stat_melee_damage",
                 "stat_elemental_damage", "stat_engineering"):
        assert STAT_MECHANICS[stat]["special"] == "weapon_scaling_stat", stat


def test_every_entry_has_a_summary():
    missing = [s for s, m in STAT_MECHANICS.items() if not m.get("summary")]
    assert missing == []


DISPLAYED_STATS = (
    "stat_armor", "stat_attack_speed", "stat_crit_chance", "stat_dodge",
    "stat_elemental_damage", "stat_engineering", "stat_harvesting",
    "stat_hp_regeneration", "stat_lifesteal", "stat_luck", "stat_max_hp",
    "stat_melee_damage", "stat_percent_damage", "stat_range",
    "stat_ranged_damage", "stat_speed",
)


def test_all_displayed_stats_have_mechanics():
    missing = [s for s in DISPLAYED_STATS if s not in STAT_MECHANICS]
    assert missing == []


def test_stat_range_projectile_speed_nuance_documented():
    assert "increase_projectile_speed_with_range" in STAT_MECHANICS["stat_range"]["summary"]


def test_stat_crit_chance_cap_semantics_documented():
    summary = STAT_MECHANICS["stat_crit_chance"]["summary"]
    assert "LARGE_NUMBER" in summary
    assert "[0, 1]" in summary


def test_stat_crit_chance_expectation_documented():
    summary = STAT_MECHANICS["stat_crit_chance"]["summary"]
    assert "expectation" in summary or "expected value" in summary


def test_stat_attack_speed_melee_extras_documented():
    summary = STAT_MECHANICS["stat_attack_speed"]["summary"]
    assert "melee_shooting_data.gd" in summary
    assert "back-swing" in summary
    assert "wind-up" in summary
