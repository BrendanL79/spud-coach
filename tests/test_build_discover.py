from brotato_coach.builders.discover import find_weapon_dirs


def test_find_weapon_dirs(tmp_path):
    d = tmp_path / "weapons" / "ranged" / "shredder" / "4"
    d.mkdir(parents=True)
    (d / "shredder_4_stats.tres").write_text("stats")
    (d / "shredder_4_data.tres").write_text("data")

    found = find_weapon_dirs(str(tmp_path))
    assert len(found) == 1
    entry = found[0]
    assert entry["weapon_id"] == "weapon_shredder"
    assert entry["tier"] == 4
    assert entry["stats_path"].endswith("shredder_4_stats.tres")
    assert entry["data_path"].endswith("shredder_4_data.tres")
