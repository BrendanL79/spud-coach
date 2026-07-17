import json

import pytest

from brotato_coach.runfile import (
    RunFormatError, _STAT_KEY_BY_SHORT, godot_string_hash, load_run, parse_run)


# Hash constants below are hand-verified against a real Brotato save's
# `effects` dict, whose keys are Godot djb2 hashes of the stat names.
_H = {
    "stat_ranged_damage": 156323247,
    "stat_range": 453346765,
    "stat_max_hp": 1880215261,
    "stat_armor": 433796225,
}


def test_godot_string_hash_matches_known_stat_hashes():
    assert godot_string_hash("stat_ranged_damage") == _H["stat_ranged_damage"]
    assert godot_string_hash("stat_range") == _H["stat_range"]
    assert godot_string_hash("stat_max_hp") == _H["stat_max_hp"]
    assert godot_string_hash("stat_armor") == _H["stat_armor"]


def test_percent_damage_uses_real_stat_key():
    assert _STAT_KEY_BY_SHORT["damage"] == str(godot_string_hash("stat_percent_damage"))


def test_level_is_not_an_effects_stat():
    assert "level" not in _STAT_KEY_BY_SHORT


def _sample_run() -> dict:
    """A minimal run save mirroring the real v3 structure."""
    return {
        "current_run_state": {
            "current_wave": 3,
            "current_difficulty": 4,
            "nb_of_waves": 20,
            "is_endless_run": False,
            "is_coop_run": False,
            "players_data": [
                {
                    "current_character": "character_ranger",
                    "current_health": 6,
                    "gold": 66,
                    "current_level": 3,
                    "weapons": [
                        {"weapon_id": "weapon_laser_gun", "tier": "0"},
                        {"weapon_id": "weapon_shredder", "tier": "2"},
                    ],
                    "items": [
                        {"my_id": "character_ranger"},  # character listed as pseudo-item
                        {"my_id": "item_dynamite"},
                    ],
                    "effects": {
                        str(_H["stat_ranged_damage"]): 1,
                        str(_H["stat_range"]): 80,
                        str(_H["stat_max_hp"]): 13,
                        str(_H["stat_armor"]): 2,
                        "99999999": 0,  # unrelated non-stat effect, ignored
                    },
                }
            ],
        }
    }


def test_parse_run_extracts_character_and_context():
    build = parse_run(_sample_run())
    assert build["character"] == "character_ranger"
    ctx = build["context"]
    assert ctx["wave"] == 3
    assert ctx["danger"] == 4
    assert ctx["nb_of_waves"] == 20
    assert ctx["endless"] is False
    assert ctx["coop"] is False
    assert ctx["health"] == 6
    assert ctx["gold"] == 66
    assert ctx["level"] == 3


def test_parse_run_normalizes_weapon_tiers_to_one_indexed():
    build = parse_run(_sample_run())
    assert build["weapons"] == [
        {"id": "weapon_laser_gun", "tier": 1},
        {"id": "weapon_shredder", "tier": 3},
    ]


def test_parse_run_drops_character_pseudo_item():
    build = parse_run(_sample_run())
    assert build["items"] == ["item_dynamite"]


def test_parse_run_recovers_realized_stats_by_hash():
    build = parse_run(_sample_run())
    assert build["stats"] == {
        "ranged_damage": 1,
        "range": 80,
        "max_hp": 13,
        "armor": 2,
        "level": 3,
    }


def test_parse_run_includes_player_level_in_stats():
    # current_level lives on the player dict, not in effects; stat_levels
    # scaling weapons need it in the stats block
    assert parse_run(_sample_run())["stats"]["level"] == 3


def test_parse_run_omits_level_when_save_lacks_it():
    run = _sample_run()
    del run["current_run_state"]["players_data"][0]["current_level"]
    assert "level" not in parse_run(run)["stats"]


def test_parse_run_rejects_unrecognized_structure():
    with pytest.raises(RunFormatError):
        parse_run({"not_a_run": True})
    with pytest.raises(RunFormatError):
        parse_run({"current_run_state": {"players_data": []}})


def test_load_run_from_inline_json():
    assert load_run(run_json='{"current_run_state": {"a": 1}}') == {
        "current_run_state": {"a": 1}}


def test_load_run_from_path(tmp_path):
    f = tmp_path / "run.json"
    f.write_text(json.dumps({"current_run_state": {"a": 2}}))
    assert load_run(path=str(f)) == {"current_run_state": {"a": 2}}


def test_load_run_requires_exactly_one_source():
    with pytest.raises(RunFormatError):
        load_run()
    with pytest.raises(RunFormatError):
        load_run(path="x", run_json="{}")


def test_load_run_rejects_invalid_json():
    with pytest.raises(RunFormatError):
        load_run(run_json="{not json")


def test_load_run_missing_file_raises(tmp_path):
    with pytest.raises(RunFormatError):
        load_run(path=str(tmp_path / "nope.json"))


def test_load_run_non_utf8_file_raises_run_format_error(tmp_path):
    # A non-UTF-8 file raises UnicodeDecodeError (a ValueError, not OSError);
    # it must still surface as the structured RunFormatError, not escape.
    f = tmp_path / "run.json"
    f.write_bytes(b"\xff\xfe\x00 not valid utf-8")
    with pytest.raises(RunFormatError):
        load_run(path=str(f))
