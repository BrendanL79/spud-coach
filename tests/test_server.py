import asyncio

from brotato_coach.server import build_server

# Raw stat-aware fields (schema v6): base_damage 10.0 + 1.0x ranged_damage per
# hit (int, no crit/percent-damage modifiers) over cycle_time = 2 x
# recoil_duration + cooldown/60 = 0.1s + 0.1s = 0.2s exactly (cooldown 6.0 is
# above the game's 2-frame minimum, so it isn't clamped), so
# dps == per_hit_damage / 0.2 == per_hit_damage * 5 (clean numbers for
# hand-verified goldens below).
DS = {
    "schema_version": 1, "game_version": "dev", "generated_at": "t",
    "weapons": [{"id": "weapon_minigun", "name": "Minigun", "tier": 4,
                 "weapon_type": "ranged", "base_damage": 10.0, "cooldown": 6.0,
                 "recoil_duration": 0.05, "accuracy": 1.0, "crit_chance": 0.0,
                 "crit_damage": 0.0, "max_range": 400.0,
                 "scaling_stats": [["stat_ranged_damage", 1.0]],
                 "proc_effects": []}],
    "items": [], "characters": [], "sets": [], "stat_mechanics": {},
}


async def _call(server, tool_name, **kwargs):
    # FastMCP's call_tool returns a (content, structured) tuple when the tool's
    # return-type annotation carries an output schema (e.g. dict[str, Any]);
    # otherwise it returns just the unstructured content list.
    result = await server.call_tool(tool_name, kwargs)
    return result[1] if isinstance(result, tuple) else result


def test_server_registers_tools():
    server = build_server(DS)

    async def _list_names():
        tools = await server.list_tools()
        return {t.name for t in tools}

    tool_names = asyncio.run(_list_names())
    assert {"read_me", "get_weapon", "weapon_dps", "evaluate_item_for_build",
            "check_dataset_version"} <= tool_names


def test_check_dataset_version_tool():
    server = build_server(DS)
    result = asyncio.run(_call(server, "check_dataset_version"))
    assert result["game_version"] == "dev"


def test_weapon_dps_tool():
    server = build_server(DS)
    result = asyncio.run(_call(server, "weapon_dps", name="Minigun", tier=4,
                               stats={"ranged_damage": 10}))
    # per_hit 10+10=20 / ct 0.2 = 100.0
    assert round(result["dps"]) == 100


def _tool_list(server):
    async def _tools():
        return await server.list_tools()
    return asyncio.run(_tools())


def test_all_tools_have_descriptions():
    # A blank description is the main reason a model picks the wrong tool.
    missing = [t.name for t in _tool_list(build_server(DS)) if not (t.description or "").strip()]
    assert missing == []


def test_get_set_renamed_to_weapon_class_set():
    names = {t.name for t in _tool_list(build_server(DS))}
    assert "get_weapon_class_set" in names
    assert "get_set" not in names


def test_get_filter_options_tool():
    ds = {**DS,
          "weapons": [{"id": "w", "name": "W", "tier": 4,
                       "scaling_stats": [["ranged_damage", 1.0]]}],
          "items": [{"id": "i", "name": "I", "tier": 2, "tags": ["ranged"],
                     "archetype": ["dmg"], "scaling_stats": ["luck"]}],
          "sets": [{"id": "set_blade", "name": "Blade"}]}
    result = asyncio.run(_call(build_server(ds), "get_filter_options"))
    assert result["item_tags"] == ["ranged"]
    assert result["weapon_classes"] == ["Blade"]
    assert result["weapon_scaling_stats"] == ["ranged_damage"]


def test_typed_stats_param_accepts_plain_dict():
    # `stats` is a typed model now; a plain dict from the client must still coerce.
    result = asyncio.run(_call(build_server(DS), "compare_weapons",
                               names_with_tiers=[["Minigun", 4]], stats={"ranged_damage": 10}))
    assert result["ranking"][0]["name"] == "Minigun"


def test_weapon_dps_tool_reports_proc_fields():
    ds = {**DS, "weapons": [{**DS["weapons"][0],
          "proc_effects": [{"kind": "weapon_damage", "chance": 0.5,
                            "enemies_hit": 1.0, "multiplier": 1.0}],
          "unmodeled_effects": ["effect_burning"]}]}
    result = asyncio.run(_call(build_server(ds), "weapon_dps", name="Minigun",
                               tier=4, stats={"ranged_damage": 10}))
    # base_dps 100.0 (see DS docstring); 50% weapon-damage proc -> 50.0
    assert round(result["proc_dps"], 4) == 50.0
    assert result["unmodeled_effects"] == ["effect_burning"]


def test_weapon_dps_tool_character_param_applies_gain_modifier():
    ds = {**DS, "characters": [
        {"id": "character_ranger", "name": "Ranger", "gain_modifiers": [
            {"stat": "stat_ranged_damage", "pct": 50}]}]}
    server = build_server(ds)
    result = asyncio.run(_call(server, "weapon_dps", name="Minigun", tier=4,
                               stats={"ranged_damage": 6}, character="Ranger"))
    # raw RD 6 -> displayed RD 9 via Ranger's +50% gain modifier;
    # per_hit 10+9=19 / ct 0.2 = 95.0
    assert round(result["dps"], 2) == 95.0


def test_compare_weapons_tool_character_param_applies_gain_modifier():
    ds = {**DS, "characters": [
        {"id": "character_ranger", "name": "Ranger", "gain_modifiers": [
            {"stat": "stat_ranged_damage", "pct": 50}]}]}
    server = build_server(ds)
    result = asyncio.run(_call(server, "compare_weapons",
                               names_with_tiers=[["Minigun", 4]],
                               stats={"ranged_damage": 6}, character="Ranger"))
    assert round(result["ranking"][0]["dps"], 2) == 95.0


def test_loadout_set_bonuses_tool():
    ds = {**DS,
          "weapons": [{"id": "weapon_smg", "name": "SMG", "tier": 1,
                       "sets": ["Gun"], "dps_at_zero_rd": 0.0,
                       "dps_slope_per_rd": 0.0, "scaling_stats": []}],
          "sets": [{"id": "set_gun", "name": "Gun", "bonuses": [
              {"count": 2, "effect": {"key": "stat_range", "value": 10}}]}]}
    result = asyncio.run(_call(build_server(ds), "loadout_set_bonuses",
                               weapon_names=["SMG", "SMG"]))
    assert result["classes"][0]["class"] == "Gun"
    assert result["classes"][0]["count"] == 2
    assert result["classes"][0]["active"][0]["effect"]["value"] == 10


_RUN_DS = {
    **DS,
    "weapons": [{"id": "weapon_smg", "name": "SMG", "tier": 1, "sets": ["Gun"],
                 "weapon_type": "ranged", "base_damage": 5.0, "cooldown": 0.0,
                 "recoil_duration": 0.05, "accuracy": 1.0, "crit_chance": 0.0,
                 "crit_damage": 0.0, "max_range": 300.0,
                 "scaling_stats": [["stat_ranged_damage", 1.0]],
                 "proc_effects": []}],
    "characters": [{"id": "character_ranger", "name": "Ranger",
                    "gain_modifiers": [], "wanted_tags": [],
                    "banned_item_groups": [], "flat_bonuses": [],
                    "special_effects": []}],
    "sets": [{"id": "set_gun", "name": "Gun",
              "bonuses": [{"count": 2, "effect": {"key": "stat_range", "value": 10}}]}],
}


def _minimal_run() -> str:
    import json

    from brotato_coach.runfile import godot_string_hash
    return json.dumps({
        "current_run_state": {
            "current_wave": 5, "current_difficulty": 3, "nb_of_waves": 20,
            "is_endless_run": False, "is_coop_run": False,
            "players_data": [{
                "current_character": "character_ranger", "current_health": 10,
                "gold": 40, "current_level": 4,
                "weapons": [{"weapon_id": "weapon_smg", "tier": "0"}],
                "items": [{"my_id": "character_ranger"}],
                "effects": {str(godot_string_hash("stat_ranged_damage")): 12},
            }],
        }
    })


def test_evaluate_run_tool_from_inline_json():
    result = asyncio.run(_call(build_server(_RUN_DS), "evaluate_run",
                               run_json=_minimal_run()))
    assert result["run"]["character"] == "Ranger"
    assert result["run"]["wave"] == 5
    assert result["realized_stats"] == {"ranged_damage": 12, "level": 4}
    assert result["weapon_dps_ranking"][0]["name"] == "SMG"


def test_evaluate_run_tool_from_path(tmp_path):
    f = tmp_path / "run.json"
    f.write_text(_minimal_run())
    result = asyncio.run(_call(build_server(_RUN_DS), "evaluate_run",
                               path=str(f)))
    assert result["run"]["character"] == "Ranger"


def test_evaluate_run_tool_bad_file_is_structured_error():
    result = asyncio.run(_call(build_server(_RUN_DS), "evaluate_run",
                               run_json="{not json"))
    assert result["error"] == "bad_run_file"
    assert "detail" in result


def test_evaluate_run_tool_rejects_both_path_and_dict():
    # The dict run_json branch must still enforce "exactly one of path/run_json".
    result = asyncio.run(_call(build_server(_RUN_DS), "evaluate_run",
                               path="x", run_json={"current_run_state": {}}))
    assert result["error"] == "bad_run_file"
    assert "exactly one" in result["detail"]


def test_data_path_default():
    from brotato_coach import server
    assert server._data_path([]) == "data/brotato.json"


def test_data_path_flag_overrides():
    from brotato_coach import server
    assert server._data_path(["--data", "/x/y.json"]) == "/x/y.json"


def test_data_path_env_fallback(monkeypatch):
    from brotato_coach import server
    monkeypatch.setenv("SPUDCOACH_DATA", "/env/brotato.json")
    assert server._data_path([]) == "/env/brotato.json"
    assert server._data_path(["--data", "/flag.json"]) == "/flag.json"


def test_read_me_tool_returns_rendered_primer():
    result = asyncio.run(_call(build_server(DS), "read_me"))
    # DS fixture: game_version "dev", schema_version 1, generated_at "t"
    assert "Dataset: Brotato vdev — schema v1, generated t." in result["primer"]


def test_instructions_point_to_read_me():
    assert "read_me" in build_server(DS).instructions


def test_get_enemy_tool_returns_record():
    ds = {**DS, "enemies": [{"id": "baby_alien", "name": "Baby Alien",
                             "display_name": "Baby Alien",
                             "base": {"health": 3, "speed": 250, "speed_randomization": 50,
                                      "damage": 1, "armor": 0, "attack_cd": 30.0,
                                      "knockback_resistance": 0.0},
                             "per_wave": {"health": 2.0, "damage": 0.6, "armor": 0.0},
                             "attack": {"kind": "melee"}, "abilities": [],
                             "appears_in": ["normal"]}]}
    result = asyncio.run(_call(build_server(ds), "get_enemy", name="Baby Alien", wave=20))
    assert result["effective"]["health"] == 41


def test_list_enemies_tool():
    ds = {**DS, "enemies": [{"id": "baby_alien", "name": "Baby Alien",
                             "attack": {"kind": "melee"}, "abilities": [],
                             "appears_in": ["normal"]}]}
    result = asyncio.run(_call(build_server(ds), "list_enemies", appears_in="normal"))
    assert result["enemies"][0]["id"] == "baby_alien"


def test_wave_composition_tool():
    ds = {**DS, "zone_1_waves": [{"wave": 1, "wave_duration": 60, "max_enemies": 10,
                                  "groups": [{"enemy_id": "baby_alien",
                                             "min_danger": 0, "max_danger": 5}]}]}
    result = asyncio.run(_call(build_server(ds), "wave_composition", wave=1))
    assert result["wave"] == 1
    assert result["base_enemies"][0]["enemy_id"] == "baby_alien"


def test_weapon_dps_tool_returns_cadence_and_honors_weapon_count():
    server = build_server(DS)
    r1 = asyncio.run(_call(server, "weapon_dps", name="Minigun", tier=4,
                           stats={"ranged_damage": 10}, weapon_count=1))
    r6 = asyncio.run(_call(server, "weapon_dps", name="Minigun", tier=4,
                           stats={"ranged_damage": 10}, weapon_count=6))
    assert r1["cadence"]["cadence"] == "sustained"
    # gap range widens with weapon count
    assert r6["cadence"]["gap_range_s"][1] > r1["cadence"]["gap_range_s"][1]


def test_get_filter_options_tool_bestiary_fields():
    ds = {**DS, "enemies": [{"id": "e", "name": "E", "abilities": ["charger"],
                             "attack": {"kind": "melee"}, "appears_in": ["normal"]}]}
    result = asyncio.run(_call(build_server(ds), "get_filter_options"))
    assert result["enemy_abilities"] == ["charger"]
    assert result["attack_kinds"] == ["melee"]
    assert result["enemy_appears_in"] == ["normal"]


def test_stat_gradient_tool_registered_and_listed():
    names = {t.name for t in _tool_list(build_server(DS))}
    assert "stat_gradient" in names


def test_stat_gradient_tool_ranks_stats():
    result = asyncio.run(_call(build_server(DS), "stat_gradient",
                               weapons=[["Minigun", 4]],
                               stats={"ranged_damage": 10}))
    assert "gradient" in result
    assert result["gradient"][0]["stat"] == "ranged_damage"


def test_weapon_dps_tool_result_carries_assumptions():
    result = asyncio.run(_call(build_server(DS), "weapon_dps", name="Minigun",
                               tier=4, stats={"ranged_damage": 10}))
    assert result["assumptions"]["aoe_enemies_hit"] == 1.0
    assert result["assumptions"]["set_bonuses_applied"] is False


def test_weapon_dps_tool_accepts_loadout_and_apply_set_bonuses():
    ds = {**DS,
          "weapons": [{**DS["weapons"][0], "sets": ["Gun"]}],
          "sets": [{"id": "set_gun", "name": "Gun", "bonuses": [
              {"count": 1, "effect": {"key": "stat_ranged_damage", "value": 5}}]}]}
    with_bonus = asyncio.run(_call(build_server(ds), "weapon_dps", name="Minigun",
                                   tier=4, stats={"ranged_damage": 10},
                                   loadout=["Minigun"], apply_set_bonuses=True))
    without_bonus = asyncio.run(_call(build_server(ds), "weapon_dps", name="Minigun",
                                      tier=4, stats={"ranged_damage": 10}))
    assert with_bonus["dps"] > without_bonus["dps"]
    assert with_bonus["assumptions"]["set_bonuses_applied"] is True
    assert with_bonus["assumptions"]["active_set_bonuses"][0]["effect"]["value"] == 5


def test_weapon_dps_tool_accepts_engagement_distance():
    melee_ds = {**DS, "weapons": [{**DS["weapons"][0], "weapon_type": "melee",
                                   "max_range": 200.0}]}
    result = asyncio.run(_call(build_server(melee_ds), "weapon_dps", name="Minigun",
                               tier=4, stats={"ranged_damage": 10},
                               engagement_distance=50.0))
    assert result["assumptions"]["engagement_distance"] == 50.0


def test_compare_weapons_tool_accepts_loadout_and_apply_set_bonuses():
    ds = {**DS,
          "weapons": [{**DS["weapons"][0], "sets": ["Gun"]}],
          "sets": [{"id": "set_gun", "name": "Gun", "bonuses": [
              {"count": 1, "effect": {"key": "stat_ranged_damage", "value": 5}}]}]}
    result = asyncio.run(_call(build_server(ds), "compare_weapons",
                               names_with_tiers=[["Minigun", 4]],
                               stats={"ranged_damage": 10},
                               loadout=["Minigun"], apply_set_bonuses=True))
    assert result["ranking"][0]["dps"] > 100.0


def test_compare_merge_paths_tool_accepts_stats():
    server = build_server(DS)
    baseline = asyncio.run(_call(server, "compare_merge_paths",
                                 weapon_name="Minigun", path_a=[4], path_b=[4]))
    with_stats = asyncio.run(_call(server, "compare_merge_paths",
                                   weapon_name="Minigun", path_a=[4], path_b=[4],
                                   stats={"damage": 100}))
    # +100 %damage doubles the guaranteed line at every RD in range, so the
    # stats param must be threaded through to move the reported DPS.
    assert with_stats["dps_a_at_range_ends"][0] > baseline["dps_a_at_range_ends"][0]
