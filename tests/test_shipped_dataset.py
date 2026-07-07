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

    # companion-projectile procs carry expected lines
    shiv = query.get_weapon(ds, "Lightning Shiv", tier=1)
    assert shiv["proc_dps_at_zero_rd"] > 0
    cactus = query.get_weapon(ds, "Cactus Mace", tier=1)
    assert cactus["proc_dps_at_zero_rd"] > 0
    assert cactus["proc_dps_slope_per_rd"] > 0  # companion scales off RD

    # classified specials carry structured metadata
    stick = query.get_weapon(ds, "Stick", tier=1)
    assert any(c["category"] == "stack" and c["bonus_per_extra_copy"] == 4
               for c in stick["classified_effects"])
    vorpal = query.get_weapon(ds, "Vorpal Sword", tier=2)
    assert any(c["category"] == "execute" and c["execute_chance_per_hit"] == 0.01
               for c in vorpal["classified_effects"])
    screwdriver = query.get_weapon(ds, "Screwdriver", tier=1)
    assert any(c["category"] == "structure" and c["structure_damage"] == 10
               for c in screwdriver["classified_effects"])

    # the proc worklist is fully triaged: nothing shipped is unmodeled
    assert all(w["unmodeled_effects"] == [] for w in ds["weapons"])

    # localization resolved real in-game text
    sh = query.get_weapon(ds, "Shredder", tier=1)
    assert sh["display_name"] == "Shredder"
    hc = query.get_item(ds, "Handcuffs")
    assert hc["display_name"] == "Handcuffs"
    assert any(e["text"] for e in hc["effects"])  # effect text_keys resolved
    rg = query.get_character(ds, "Ranger")
    assert rg["display_name"] == "Ranger"
    # schema_version 4 = enemies + zone_1_waves (3 was 1-indexed item tiers)
    assert ds["schema_version"] == 4


@pytest.mark.skipif(not os.path.exists(DATA), reason="dataset not built")
def test_read_me_provenance_complete_on_shipped_dataset():
    from brotato_coach import orientation

    ds = json.load(open(DATA, encoding="utf-8"))
    primer = orientation.read_me_payload(ds)["primer"]
    line = next(ln for ln in primer.splitlines()
                if ln.startswith("Dataset: Brotato v"))
    assert "unknown" not in line
