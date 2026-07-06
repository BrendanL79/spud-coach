import asyncio

from brotato_coach.server import build_server

DS = {
    "schema_version": 1, "game_version": "dev", "generated_at": "t",
    "weapons": [{"id": "weapon_minigun", "name": "Minigun", "tier": 4,
                 "dps_at_zero_rd": 55.5556, "dps_slope_per_rd": 8.3333, "scaling_stats": []}],
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
    assert round(result["dps"]) == round(55.5556 + 8.3333 * 10)


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
          "proc_dps_at_zero_rd": 5.0, "proc_dps_slope_per_rd": 0.5,
          "unmodeled_effects": ["effect_burning"]}]}
    result = asyncio.run(_call(build_server(ds), "weapon_dps", name="Minigun",
                               tier=4, stats={"ranged_damage": 10}))
    assert round(result["proc_dps"], 4) == 10.0
    assert result["unmodeled_effects"] == ["effect_burning"]


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
                 "dps_at_zero_rd": 10.0, "dps_slope_per_rd": 1.0, "scaling_stats": []}],
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
    assert result["realized_stats"] == {"ranged_damage": 12}
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
