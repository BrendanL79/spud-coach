import re

import pytest

from brotato_coach import dataset
from brotato_coach.builders.mechanics import STAT_MECHANICS


def test_mechanics_known_facts():
    assert STAT_MECHANICS["stat_attack_speed"]["never_dead_weight"] is True
    assert STAT_MECHANICS["stat_hp_regeneration"]["safe_at_zero"] is True
    assert STAT_MECHANICS["stat_curse"]["avoid_positive"] is True
    assert STAT_MECHANICS["stat_max_hp"]["cap"] == {"cap_key": "hp_cap"}


def test_assemble_and_validate_ok():
    weapon = {
        "id": "w", "name": "W", "tier": 4, "base_damage": 25, "cooldown": 45,
        "accuracy": 1.0, "crit_chance": 0.03, "crit_damage": 2.0, "piercing": 3,
        "nb_projectiles": 1, "scaling_stats": [], "can_have_negative_knockback": False,
        "base_knockback": 0, "cycle_time": 1.05, "dps_at_zero_rd": 23.8,
        "dps_slope_per_rd": 0.48, "sets": [], "effects": [],
    }
    item = {"id": "i", "name": "I", "tier": 0, "value": 10, "tags": [], "effects": [],
            "archetype": [], "frozen_stat": None, "scaling_stats": [], "damage_tags": []}
    ds = dataset.assemble_dataset(game_version="1.1.0.0", generated_at="2026-07-01T00:00:00Z",
                                  weapons=[weapon], items=[item], characters=[], sets=[])
    assert ds["schema_version"] == dataset.DATASET_VERSION
    assert ds["game_version"] == "1.1.0.0"
    assert dataset.validate_dataset(ds) == []


def test_validate_flags_bad_tier():
    ds = dataset.assemble_dataset(game_version="x", generated_at="t",
                                  weapons=[{"id": "w", "tier": 9, "dps_slope_per_rd": 1.0}],
                                  items=[], characters=[], sets=[])
    problems = dataset.validate_dataset(ds)
    assert any("tier" in p for p in problems)


def test_load_missing_dataset_message(tmp_path):
    with pytest.raises(FileNotFoundError, match=re.escape("build_dataset.py")):
        dataset.load_dataset(str(tmp_path / "nope.json"))
