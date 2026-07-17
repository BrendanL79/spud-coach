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
        # dataset-convention vocabulary (stat-aware engine)
        "base_dps", "proc_dps", "assumptions", "engagement_distance",
        "stat_gradient", "cycle_time",
        "classified_effects", "unmodeled_effects", "enemies_hit",
        # exploding-proc rider stats: both named, with the manual formula
        # for explosion_damage so callers compute instead of giving up
        "explosion_size", "(1 + explosion_damage/100)",
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
    # per-wave scaling formula (named against the record's per_wave field) and
    # the speed-range convention
    assert "per_wave" in primer
    assert "wave - 1" in primer
    assert "speed_randomization" in primer
    # wave_composition honesty envelope: exact base groups, randomized elites/hordes
    assert "wave_composition" in primer
    assert "randomized" in primer


def test_read_me_weapon_dps_raw_vs_displayed_contract():
    primer = orientation.read_me_payload(FAKE_DS)["primer"]
    # weapon_dps/compare_weapons need DISPLAYED (post-gain-modifier) stats,
    # not the raw effects values a save file carries — must be explicit,
    # since a caller feeding raw values gets no error, just a wrong number.
    assert "weapon_dps" in primer
    assert "displayed" in primer.lower()
    assert "character" in primer


def test_primer_describes_verified_cadence_not_unmodeled_sync():
    primer = orientation.read_me_payload(FAKE_DS)["primer"]
    assert "attacks_per_second" in primer
    assert "randomizes each shot's cooldown" in primer
    # The old misleading blanket claim is gone.
    assert "Attack-timing synchronization is NOT modeled" not in primer


def test_primer_caveats_burn_uptime_gating():
    primer = orientation.read_me_payload(FAKE_DS)["primer"]
    # Burn steady-state eligibility is decided at BUILD time from zero-AS
    # cycle time; runtime attack speed never re-gates it, so callers must
    # know the two directions the static line can be wrong.
    assert "zero-attack-speed" in primer
    assert "overstates burn uptime" in primer
    assert "chance < 100%" in primer


def test_read_me_appears_in_nuance():
    primer = orientation.read_me_payload(FAKE_DS)["primer"]
    # empty appears_in means "not in numbered-wave base groups", not "never spawns"
    assert "appears_in" in primer
    assert "never spawns" in primer
