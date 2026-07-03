from brotato_coach.builders.mechanics import STAT_MECHANICS


def test_weapon_scaling_damage_stats_encoded():
    for stat in ("stat_ranged_damage", "stat_melee_damage",
                 "stat_elemental_damage", "stat_engineering"):
        assert STAT_MECHANICS[stat]["special"] == "weapon_scaling_stat", stat


def test_every_entry_has_a_summary():
    missing = [s for s, m in STAT_MECHANICS.items() if not m.get("summary")]
    assert missing == []
