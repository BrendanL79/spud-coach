from brotato_coach import bestiary

_DS = {
    "enemies": [
        {"id": "baby_alien", "name": "Baby Alien", "display_name": "Baby Alien",
         "base": {"health": 3, "speed": 250, "speed_randomization": 50,
                  "damage": 1, "armor": 0, "attack_cd": 30.0,
                  "knockback_resistance": 0.0},
         "per_wave": {"health": 2.0, "damage": 0.6, "armor": 0.0},
         "attack": {"kind": "melee"}, "abilities": [], "appears_in": ["normal"]},
        {"id": "spitter", "name": "Spitter", "display_name": "Spitter",
         "base": {"health": 10, "speed": 200, "speed_randomization": 0,
                  "damage": 2, "armor": 0, "attack_cd": 60.0,
                  "knockback_resistance": 0.0},
         "per_wave": {"health": 4.0, "damage": 0.0, "armor": 0.0},
         "attack": {"kind": "ranged", "projectile_damage": 1,
                    "projectile_dmg_per_wave": 0.75, "number_projectiles": 1},
         "abilities": [], "appears_in": ["normal"]},
    ],
    "zone_1_waves": [],
}


def test_effective_stats_scale_with_wave():
    eff = bestiary.effective_stats(_DS["enemies"][0], wave=20)
    assert eff["health"] == 3 + 2.0 * 19   # 41
    assert eff["damage"] == 1 + 0.6 * 19   # 12.4
    assert eff["speed_range"] == [200, 300]  # 250 +/- 50


def test_get_enemy_without_wave_has_base_and_slopes():
    r = bestiary.get_enemy(_DS, "Baby Alien")
    assert r["base"]["health"] == 3
    assert r["per_wave"]["health"] == 2.0
    assert "effective" not in r


def test_get_enemy_with_wave_adds_effective():
    r = bestiary.get_enemy(_DS, "baby_alien", wave=20)
    assert r["effective"]["health"] == 41


def test_get_enemy_miss_suggests():
    r = bestiary.get_enemy(_DS, "baby alein")
    assert r["error"] == "not_found"
    assert "Baby Alien" in r["did_you_mean"]


def test_list_enemies_filters_by_attack_kind():
    out = bestiary.list_enemies(_DS, attack_kind="ranged")
    assert [e["id"] for e in out] == ["spitter"]


_DS_WAVES = {
    "enemies": _DS["enemies"],
    "zone_1_waves": [
        {"wave": 12, "wave_duration": 60, "max_enemies": 100, "groups": [
            {"enemy_id": "baby_alien", "base_count": [5, 5], "first_spawn_s": 1,
             "repeats": 5, "repeat_interval": 3, "spawn_chance": 1.0,
             "min_danger": 0, "max_danger": 9999, "is_horde": False,
             "is_boss": False, "is_loot": False},
            {"enemy_id": "spitter", "base_count": [1, 2], "first_spawn_s": 5,
             "repeats": 999, "repeat_interval": 15, "spawn_chance": 1.0,
             "min_danger": 6, "max_danger": 9999, "is_horde": False,
             "is_boss": False, "is_loot": False},
        ]},
    ],
}


def test_wave_composition_danger_gates_groups():
    at0 = bestiary.wave_composition(_DS_WAVES, 12, danger=0)
    ids0 = [g["enemy_id"] for g in at0["base_enemies"]]
    assert ids0 == ["baby_alien"]           # spitter group is d6-only

    at6 = bestiary.wave_composition(_DS_WAVES, 12, danger=6)
    ids6 = [g["enemy_id"] for g in at6["base_enemies"]]
    assert set(ids6) == {"baby_alien", "spitter"}


def test_wave_composition_labels_run_variance():
    comp = bestiary.wave_composition(_DS_WAVES, 12)
    assert "number_of_enemies" in " ".join(comp["scales_with"])
    assert "per-run" in comp["elite_horde"].lower()


def test_wave_context_has_effective_threat_at_wave():
    ctx = bestiary.wave_context(_DS_WAVES, 12, danger=0)
    assert ctx["death_wave"] == 12
    threat = {t["enemy_id"]: t for t in ctx["effective_threat"]}
    # baby_alien effective HP at wave 12 = 3 + 2*11 = 25
    assert threat["baby_alien"]["health"] == 25
