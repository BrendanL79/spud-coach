from brotato_coach import answers
from brotato_coach.runfile import godot_string_hash

# A synthetic dataset with just enough to exercise every composed analysis:
# two Gun-class weapons (for DPS ranking + set progress), one item with a
# ranged-damage effect (for the per-item verdict), and the Ranger.
DS = {
    "weapons": [
        {"id": "weapon_smg", "name": "SMG", "tier": 1, "sets": ["Gun"],
         "dps_at_zero_rd": 10.0, "dps_slope_per_rd": 1.0, "scaling_stats": []},
        {"id": "weapon_pistol", "name": "Pistol", "tier": 1, "sets": ["Gun"],
         "dps_at_zero_rd": 5.0, "dps_slope_per_rd": 0.5, "scaling_stats": []},
    ],
    "items": [
        {"id": "item_dynamite", "name": "Dynamite", "tags": ["explosive"],
         "archetype": [],
         "effects": [{"key": "stat_ranged_damage", "value": 5,
                      "text_key": "", "text": ""}]},
    ],
    "characters": [
        {"id": "character_ranger", "name": "Ranger", "display_name": "Ranger",
         "wanted_tags": [], "banned_item_groups": [], "flat_bonuses": [],
         "gain_modifiers": [], "special_effects": []},
    ],
    "sets": [
        {"id": "set_gun", "name": "Gun", "bonuses": [
            {"count": 2, "effect": {"key": "stat_range", "value": 10}},
            {"count": 4, "effect": {"key": "stat_range", "value": 20}}]},
    ],
    "stat_mechanics": {},
    "enemies": [
        {"id": "baby_alien", "name": "Baby Alien", "display_name": "Baby Alien",
         "base": {"health": 3, "speed": 250, "speed_randomization": 50,
                  "damage": 1, "armor": 0, "attack_cd": 30.0,
                  "knockback_resistance": 0.0},
         "per_wave": {"health": 2.0, "damage": 0.6, "armor": 0.0},
         "attack": {"kind": "melee"}, "abilities": [], "appears_in": ["normal"]},
    ],
    "zone_1_waves": [
        {"wave": 12, "wave_duration": 60, "max_enemies": 100, "groups": [
            {"enemy_id": "baby_alien", "base_count": [5, 5], "first_spawn_s": 1,
             "repeats": 5, "repeat_interval": 3, "spawn_chance": 1.0,
             "min_danger": 0, "max_danger": 9999, "is_horde": False,
             "is_boss": False, "is_loot": False},
        ]},
    ],
}


def _run(*, character="character_ranger", weapons=None, items=None,
         stats=None, wave=3, danger=4, coop=False) -> dict:
    weapons = weapons if weapons is not None else [
        {"weapon_id": "weapon_smg", "tier": "0"},
        {"weapon_id": "weapon_pistol", "tier": "0"},
    ]
    item_ids = items if items is not None else ["item_dynamite"]
    stats = stats if stats is not None else {"ranged_damage": 8}
    effects = {str(godot_string_hash(f"stat_{k}")): v for k, v in stats.items()}
    return {
        "current_run_state": {
            "current_wave": wave, "current_difficulty": danger,
            "nb_of_waves": 20, "is_endless_run": False, "is_coop_run": coop,
            "players_data": [{
                "current_character": character,
                "current_health": 6, "gold": 66, "current_level": 3,
                "weapons": weapons,
                "items": [{"my_id": character}] + [{"my_id": i} for i in item_ids],
                "effects": effects,
            }],
        }
    }


def test_evaluate_run_reports_character_and_context():
    r = answers.evaluate_run(DS, _run())
    assert r["run"]["character"] == "Ranger"
    assert r["run"]["character_id"] == "character_ranger"
    assert r["run"]["wave"] == 3
    assert r["run"]["danger"] == 4


def test_evaluate_run_passes_through_realized_stats():
    r = answers.evaluate_run(DS, _run(stats={"ranged_damage": 8, "range": 80}))
    assert r["realized_stats"] == {"ranged_damage": 8, "range": 80}


def test_evaluate_run_ranks_weapon_dps_at_realized_stats():
    r = answers.evaluate_run(DS, _run(stats={"ranged_damage": 8}))
    ranking = r["weapon_dps_ranking"]
    # SMG: 10 + 1.0*8 = 18 ; Pistol: 5 + 0.5*8 = 9 -> SMG ranks first
    assert [row["name"] for row in ranking] == ["SMG", "Pistol"]
    assert ranking[0]["dps"] == 18.0


def test_evaluate_run_reports_set_progress():
    r = answers.evaluate_run(DS, _run())
    gun = {c["class"]: c for c in r["set_bonuses"]["classes"]}["Gun"]
    assert gun["count"] == 2  # SMG + Pistol
    assert gun["active"] == [{"count": 2, "effect": {"key": "stat_range", "value": 10}}]
    assert gun["next"]["count"] == 4
    assert gun["next"]["needs"] == 2


def test_evaluate_run_gives_per_item_verdict():
    r = answers.evaluate_run(DS, _run(stats={"ranged_damage": 8}))
    verdicts = r["item_verdicts"]
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v["item"] == "Dynamite"
    # ranged_damage effect is live because the build has ranged investment
    assert v["effects"][0]["verdict"] == "live"


def test_evaluate_run_flags_wasted_item_effect_for_off_build():
    # No ranged investment -> the ranged-damage effect is wasted.
    r = answers.evaluate_run(DS, _run(stats={"melee_damage": 5}))
    v = r["item_verdicts"][0]
    assert v["effects"][0]["verdict"] == "wasted"


def test_evaluate_run_notes_unknown_ids():
    run = _run(weapons=[{"weapon_id": "weapon_zzz", "tier": "0"}],
               items=["item_zzz"])
    r = answers.evaluate_run(DS, run)
    joined = " ".join(r["notes"])
    assert "weapon_zzz" in joined
    assert "item_zzz" in joined


def test_evaluate_run_notes_coop_run():
    r = answers.evaluate_run(DS, _run(coop=True))
    assert any("co-op" in n.lower() or "coop" in n.lower() for n in r["notes"])


def test_evaluate_run_bad_format_returns_structured_error():
    r = answers.evaluate_run(DS, {"nonsense": True})
    assert r["error"] == "bad_run_format"
    assert "detail" in r


def test_evaluate_run_includes_wave_context():
    # wave 12 is a base-game (zone_1) wave present in DS -> full wave_context
    r = answers.evaluate_run(DS, _run(wave=12, danger=0))
    wc = r["wave_context"]
    assert wc["death_wave"] == 12
    assert "per-run" in wc["elite_horde_note"].lower()
    assert isinstance(wc["effective_threat"], list)


def test_evaluate_run_wave_context_skip_note_outside_base_game_range():
    # wave 25 has no zone_1_waves record (endless / outside 1-20) -> skip note
    r = answers.evaluate_run(DS, _run(wave=25, danger=0))
    wc = r["wave_context"]
    assert wc["death_wave"] == 25
    assert "note" in wc
    assert "composition" not in wc
