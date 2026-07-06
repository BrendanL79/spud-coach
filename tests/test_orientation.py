from brotato_coach import orientation

FAKE_DS = {"game_version": "9.9.9", "schema_version": 3,
           "generated_at": "2026-07-06T00:00:00Z"}


def test_payload_renders_provenance():
    primer = orientation.read_me_payload(FAKE_DS)["primer"]
    assert ("Dataset: Brotato v9.9.9 — schema v3, "
            "generated 2026-07-06T00:00:00Z.") in primer
    assert "{provenance}" not in primer


def test_payload_missing_provenance_renders_unknown():
    primer = orientation.read_me_payload({})["primer"]
    assert ("Dataset: Brotato vunknown — schema vunknown, "
            "generated unknown.") in primer


def test_primer_contains_required_sentinels():
    primer = orientation.read_me_payload(FAKE_DS)["primer"]
    for sentinel in [
        # every classification category, by exact name
        "stat_rider", "dynamic", "economy", "cc", "delivery_modifier",
        "drawback", "execute", "stack", "structure",
        # dataset-convention vocabulary
        "dps_at_zero_rd", "dps_slope_per_rd", "zero-stat", "cycle_time",
        "classified_effects", "unmodeled_effects", "enemies_hit",
        # the game-basics disclaimer, verbatim per spec
        "Orientation only — general game knowledge, not source-verified.",
        # tool pointers
        "get_filter_options",
    ]:
        assert sentinel in primer, f"primer missing sentinel: {sentinel}"


def test_payload_shape():
    payload = orientation.read_me_payload(FAKE_DS)
    assert set(payload) == {"primer"}
    assert isinstance(payload["primer"], str)
    assert len(payload["primer"]) > 2000


def test_read_me_mentions_bestiary_scaling():
    primer = orientation.read_me_payload(FAKE_DS)["primer"]
    # per-wave scaling formula and the speed-range convention
    assert "increase_each_wave" in primer
    assert "wave - 1" in primer
    assert "speed_randomization" in primer
    # wave_composition honesty envelope: exact base groups, randomized elites/hordes
    assert "wave_composition" in primer
    assert "randomized" in primer


def test_read_me_appears_in_nuance():
    primer = orientation.read_me_payload(FAKE_DS)["primer"]
    # empty appears_in means "not in numbered-wave base groups", not "never spawns"
    assert "appears_in" in primer
    assert "never spawns" in primer
