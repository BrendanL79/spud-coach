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
