import json
import os

import pytest

DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "brotato.json")


@pytest.mark.skipif(not os.path.exists(DATA), reason="dataset not built")
def test_shipped_dataset_is_complete():
    from brotato_coach import query, evaluate

    ds = json.load(open(DATA, encoding="utf-8"))
    assert len(ds["weapons"]) > 0
    assert len(ds["items"]) > 0
    assert len(ds["characters"]) > 0
    assert len(ds["sets"]) > 0

    # a known item survives the pipeline with its archetype
    hc = query.get_item(ds, "Handcuffs")
    assert hc.get("frozen_stat") == "stat_max_hp"

    # a known character carries its gain modifiers
    rg = query.get_character(ds, "Ranger")
    assert any(m["stat"] == "stat_ranged_damage" for m in rg["gain_modifiers"])

    # the flagship evaluator now works end-to-end on the shipped data
    result = evaluate.evaluate_item_for_build(ds, "Handcuffs", "Ranger",
                                              {"ranged_damage": 7, "elemental_damage": -1})
    verdicts = {e["effect"]["key"]: e["verdict"] for e in result["effects"]}
    assert verdicts["stat_ranged_damage"] == "live"
    assert verdicts["hp_cap"] == "harmful"

    # proc weapons carry a nonzero expected proc line
    sh = query.get_weapon(ds, "Shredder", tier=1)
    assert sh["proc_dps_at_zero_rd"] > 0

    # burn weapons carry a nonzero expected DoT proc line
    torch = query.get_weapon(ds, "Torch", tier=1)
    assert torch["proc_dps_at_zero_rd"] > 0
    assert torch["unmodeled_effects"] == []

    # localization resolved real in-game text
    sh = query.get_weapon(ds, "Shredder", tier=1)
    assert sh["display_name"] == "Shredder"
    hc = query.get_item(ds, "Handcuffs")
    assert hc["display_name"] == "Handcuffs"
    assert any(e["text"] for e in hc["effects"])  # effect text_keys resolved
    rg = query.get_character(ds, "Ranger")
    assert rg["display_name"] == "Ranger"
    # schema_version 2 = proc-aware + localized dataset
    assert ds["schema_version"] == 2
