import copy

from brotato_coach import answers
from brotato_coach.runfile import godot_string_hash

# A synthetic dataset with just enough to exercise every composed analysis:
# two Gun-class weapons (for DPS ranking + set progress), one item with a
# ranged-damage effect (for the per-item verdict), and the Ranger.
#
# Raw stat-aware fields (schema v6): base_damage 1.0 + 1.0x ranged_damage per
# hit (int, no crit/percent-damage modifiers here) over cycle_time = 2 x
# recoil_duration + cooldown/60. SMG: ct = 0.2 + 18/60 = 0.5s -> dps = per_hit
# / 0.5. Pistol: ct = 0.2 + 48/60 = 1.0s -> dps = per_hit / 1.0. At RD 8:
# SMG per_hit 9 -> dps 18.0; Pistol per_hit 9 -> dps 9.0 (same golden values
# the old precomputed-line fixture produced, by construction).
DS = {
    "weapons": [
        {"id": "weapon_smg", "name": "SMG", "tier": 1, "sets": ["Gun"],
         "weapon_type": "ranged", "base_damage": 1.0, "cooldown": 18.0,
         "recoil_duration": 0.1, "accuracy": 1.0, "crit_chance": 0.0,
         "crit_damage": 0.0, "max_range": 300.0,
         "scaling_stats": [["stat_ranged_damage", 1.0]], "proc_effects": []},
        {"id": "weapon_pistol", "name": "Pistol", "tier": 1, "sets": ["Gun"],
         "weapon_type": "ranged", "base_damage": 1.0, "cooldown": 48.0,
         "recoil_duration": 0.1, "accuracy": 1.0, "crit_chance": 0.0,
         "crit_damage": 0.0, "max_range": 300.0,
         "scaling_stats": [["stat_ranged_damage", 1.0]], "proc_effects": []},
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


DS_RANGER_GAIN = {
    **DS,
    "characters": [
        {"id": "character_ranger", "name": "Ranger", "display_name": "Ranger",
         "wanted_tags": [], "banned_item_groups": [], "flat_bonuses": [],
         "gain_modifiers": [{"stat": "stat_ranged_damage", "pct": 50}],
         "special_effects": []},
    ],
}


def test_evaluate_run_realized_stats_reflect_gain_modifier():
    # raw RD 8 -> Ranger's +50% ranged-damage gain -> displayed RD 12
    r = answers.evaluate_run(DS_RANGER_GAIN, _run(stats={"ranged_damage": 8}))
    assert r["realized_stats"]["ranged_damage"] == 12


def test_evaluate_run_ranks_weapons_at_displayed_stats_not_raw():
    r = answers.evaluate_run(DS_RANGER_GAIN, _run(stats={"ranged_damage": 8}))
    # SMG at displayed RD 12: per_hit 1+12=13 / ct 0.5 = 26 (would be 18 at raw RD 8)
    assert r["weapon_dps_ranking"][0]["dps"] == 26.0


def test_evaluate_run_reports_character_and_context():
    r = answers.evaluate_run(DS, _run())
    assert r["run"]["character"] == "Ranger"
    assert r["run"]["character_id"] == "character_ranger"
    assert r["run"]["wave"] == 3
    assert r["run"]["danger"] == 4


def test_evaluate_run_passes_through_realized_stats():
    r = answers.evaluate_run(DS, _run(stats={"ranged_damage": 8, "range": 80}))
    assert r["realized_stats"] == {"ranged_damage": 8, "range": 80, "level": 3}


def test_evaluate_run_feeds_save_level_into_stat_levels_scaling():
    # SMG rescaled to stat_levels: per_hit = 1 + 1.0 x level. The save's
    # current_level 3 must reach the DPS math -> per_hit 4 / ct 0.5 = 8.0
    # (a dropped level would yield 2.0).
    ds = copy.deepcopy(DS)
    ds["weapons"][0]["scaling_stats"] = [["stat_levels", 1.0]]
    r = answers.evaluate_run(ds, _run(weapons=[{"weapon_id": "weapon_smg", "tier": "0"}],
                                      stats={}))
    assert r["weapon_dps_ranking"][0]["dps"] == 8.0


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


def test_evaluate_run_ranking_has_cadence_at_loadout_count():
    report = answers.evaluate_run(DS, _run())
    ranking = report["weapon_dps_ranking"]
    assert all("cadence" in row for row in ranking)
    # Two weapons in the loadout -> jitter computed at N=2, not N=1.
    smg = next(r for r in ranking if r["name"] == "SMG")
    # gap_range_s depends only on cycle_time/cooldown/weapon_count, not on
    # ranged_damage, so the stats here are immaterial — the difference below
    # isolates the N=2 (loadout) vs N=1 jitter, nothing else.
    n1 = answers.compare_weapons(
        DS, [("SMG", 1)], {"ranged_damage": 8}, weapon_count=1)["ranking"][0]
    assert smg["cadence"]["gap_range_s"] != n1["cadence"]["gap_range_s"]


DS_RANGER_CLASS_BONUS = copy.deepcopy(DS)
DS_RANGER_CLASS_BONUS["characters"][0]["class_bonuses"] = [
    {"set_id": "set_gun", "set_name": "Gun", "stat": "damage",
     "stat_displayed": "stat_damage", "value": 10}]


def test_evaluate_run_reports_class_synergy():
    r = answers.evaluate_run(DS_RANGER_CLASS_BONUS, _run())
    synergy = r["class_synergy"]
    assert synergy["character"] == "Ranger"
    assert synergy["bonuses"][0]["set_name"] == "Gun"
    # both equipped Gun weapons benefit
    assert sorted(synergy["bonuses"][0]["matched_weapons"]) == ["Pistol", "SMG"]


def test_evaluate_run_class_synergy_empty_without_bonus():
    r = answers.evaluate_run(DS, _run())
    assert r["class_synergy"]["bonuses"] == []


def test_evaluate_run_includes_top_stat_gradient():
    r = answers.evaluate_run(DS, _run(stats={"ranged_damage": 8}))
    gradient = r["top_stat_gradient"]
    assert len(gradient) > 0
    assert len(gradient) <= 5
    deltas = [row["dps_delta"] for row in gradient]
    assert deltas == sorted(deltas, reverse=True)


DS_MELEE = copy.deepcopy(DS)
DS_MELEE["weapons"] = [
    {"id": "weapon_knife", "name": "Knife", "tier": 1, "sets": ["Blade"],
     "weapon_type": "melee", "base_damage": 9.0, "cooldown": 25.0,
     "recoil_duration": 0.1, "accuracy": 1.0, "crit_chance": 0.0,
     "crit_damage": 0.0, "max_range": 150.0,
     "scaling_stats": [["stat_melee_damage", 0.8]], "proc_effects": []},
]


def test_evaluate_run_melee_weapon_ranking_responds_to_melee_damage():
    # Two saves differing only in melee_damage should produce different
    # DPS on the melee weapon's ranking row -- the stat-aware engine
    # scales melee weapons too, not just ranged_damage.
    weapons = [{"weapon_id": "weapon_knife", "tier": "0"}]
    r_low = answers.evaluate_run(
        DS_MELEE, _run(weapons=weapons, stats={"melee_damage": 0}))
    r_high = answers.evaluate_run(
        DS_MELEE, _run(weapons=weapons, stats={"melee_damage": 20}))
    assert r_low["weapon_dps_ranking"][0]["dps"] != r_high["weapon_dps_ranking"][0]["dps"]
