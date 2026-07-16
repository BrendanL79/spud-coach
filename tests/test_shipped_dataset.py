import json
import os

import pytest

DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "brotato.json")


@pytest.mark.skipif(not os.path.exists(DATA), reason="dataset not built")
def test_shipped_dataset_is_complete():
    from brotato_coach import calc, query, evaluate

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

    # proc weapons carry a nonzero expected proc DPS at the stat-aware engine's
    # zero-stat baseline
    sh = query.get_weapon(ds, "Shredder", tier=1)
    assert calc.weapon_dps_profile(sh, {})["proc_dps"] > 0

    # burn weapons carry a nonzero expected DoT proc DPS
    torch = query.get_weapon(ds, "Torch", tier=1)
    assert calc.weapon_dps_profile(torch, {})["proc_dps"] > 0
    assert torch["unmodeled_effects"] == []

    # companion-projectile procs carry expected DPS and respond to their
    # scaling stat (Cactus Mace's companion scales ranged_damage)
    shiv = query.get_weapon(ds, "Lightning Shiv", tier=1)
    assert calc.weapon_dps_profile(shiv, {})["proc_dps"] > 0
    cactus = query.get_weapon(ds, "Cactus Mace", tier=1)
    cactus_lo = calc.weapon_dps_profile(cactus, {})["proc_dps"]
    cactus_hi = calc.weapon_dps_profile(cactus, {"ranged_damage": 30})["proc_dps"]
    assert cactus_lo > 0
    assert cactus_hi > cactus_lo

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
    # schema_version 6 = stat-aware DPS engine (weapon_type/recoil_duration/
    # max_range/scaling_stats replace the old RD-slope proc model)
    assert ds["schema_version"] == 6


@pytest.mark.skipif(not os.path.exists(DATA), reason="dataset not built")
def test_every_weapon_has_type_and_raw_timing():
    ds = json.load(open(DATA, encoding="utf-8"))
    for w in ds["weapons"]:
        assert w["weapon_type"] in ("melee", "ranged"), w["id"]
        assert "recoil_duration" in w, w["id"]
        assert "max_range" in w, w["id"]


@pytest.mark.skipif(not os.path.exists(DATA), reason="dataset not built")
def test_precise_weapons_respond_to_melee_damage():
    # THE headline fix: every Precise weapon's DPS moves with melee damage,
    # except the weapons whose scaling_stats genuinely omit melee_damage:
    #   - weapon_crossbow: scales stat_ranged_damage (0.5) + stat_range (0.1)
    #   - weapon_sniper_gun: scales stat_ranged_damage (1.0) + stat_range (0.2)
    #   - weapon_icicle: scales stat_elemental_damage (1.0) only
    from brotato_coach import calc

    ds = json.load(open(DATA, encoding="utf-8"))
    no_melee_term = {"weapon_crossbow", "weapon_sniper_gun", "weapon_icicle"}
    for w in ds["weapons"]:
        if "Precise" not in (w.get("sets") or []):
            continue
        lo = calc.weapon_dps_profile(w, {})["dps"]
        hi = calc.weapon_dps_profile(w, {"melee_damage": 50})["dps"]
        if w["id"] in no_melee_term:
            assert hi == lo, w["id"]
        else:
            assert hi > lo, w["id"]


@pytest.mark.skipif(not os.path.exists(DATA), reason="dataset not built")
def test_burn_weapons_respond_to_elemental():
    from brotato_coach import calc

    ds = json.load(open(DATA, encoding="utf-8"))
    burn = [w for w in ds["weapons"]
            if any(p["kind"] == "burn_dot" for p in w.get("proc_effects", []))]
    assert burn  # Torch/Fireball/etc. exist
    for w in burn:
        lo = calc.weapon_dps_profile(w, {})["dps"]
        hi = calc.weapon_dps_profile(w, {"elemental_damage": 20})["dps"]
        assert hi > lo, w["id"]


@pytest.mark.skipif(not os.path.exists(DATA), reason="dataset not built")
def test_read_me_provenance_complete_on_shipped_dataset():
    from brotato_coach import orientation

    ds = json.load(open(DATA, encoding="utf-8"))
    primer = orientation.read_me_payload(ds)["primer"]
    line = next(ln for ln in primer.splitlines()
                if ln.startswith("Dataset: Brotato v"))
    assert "unknown" not in line


@pytest.mark.skipif(not os.path.exists(DATA), reason="dataset not built")
def test_crazy_has_precise_range_class_bonus():
    ds = json.load(open(DATA, encoding="utf-8"))
    crazy = next(c for c in ds["characters"] if c["id"] == "character_crazy")
    assert {"set_id": "set_precise", "set_name": "Precise",
            "stat": "max_range", "stat_displayed": "stat_range",
            "value": 100} in crazy["class_bonuses"]
