import os

from build_dataset import resolve_recovered_paths


def test_paths_derive_from_recovered_root():
    version_file, translations = resolve_recovered_paths("/data/rec", None, None)
    assert version_file == os.path.join("/data/rec", "singletons", "progress_data.gd")
    assert translations == os.path.join(
        "/data/rec", ".assets", "resources", "translations", "translations.csv")


def test_explicit_overrides_win_over_recovered_root():
    version_file, translations = resolve_recovered_paths(
        "/data/rec", "custom/version.gd", "custom/tr.csv")
    assert version_file == "custom/version.gd"
    assert translations == "custom/tr.csv"


def test_default_recovered_root_matches_old_defaults():
    # Backward compat: with the default root and no overrides, the derived
    # paths equal the old hardcoded argparse defaults.
    version_file, translations = resolve_recovered_paths("recovered", None, None)
    assert version_file == os.path.join("recovered", "singletons", "progress_data.gd")
    assert translations == os.path.join(
        "recovered", ".assets", "resources", "translations", "translations.csv")


def test_stamp_sources_sets_base_on_every_record():
    import build_dataset
    weapons = [{"id": "w1"}, {"id": "w2"}]
    enemies = [{"id": "e1"}]
    build_dataset._stamp_sources(weapons, enemies, [])
    assert all(r["source"] == "base" for r in weapons)
    assert enemies[0]["source"] == "base"


def test_has_blocking_issues_true_on_new_tree():
    import build_dataset
    coverage = {"unclaimed_trees": ["abyssal"], "unknown_weapon_kinds": [], "unmodeled_zones": []}
    assert build_dataset._has_blocking_issues(coverage, {}) is True


def test_has_blocking_issues_true_on_unmodeled_effect():
    import build_dataset
    empty = {"unclaimed_trees": [], "unknown_weapon_kinds": [], "unmodeled_zones": []}
    assert build_dataset._has_blocking_issues(empty, {"abyssal_terrors": ["curse_x"]}) is True


def test_has_blocking_issues_false_when_clean():
    import build_dataset
    empty = {"unclaimed_trees": [], "unknown_weapon_kinds": [], "unmodeled_zones": []}
    assert build_dataset._has_blocking_issues(empty, {}) is False


def test_coverage_report_lines_summarizes():
    import build_dataset
    coverage = {"unclaimed_trees": ["abyssal"], "unknown_weapon_kinds": [], "unmodeled_zones": ["zone_4"]}
    lines = build_dataset._coverage_report_lines(coverage, {"abyssal_terrors": ["curse_x", "curse_y"]})
    text = "\n".join(lines)
    assert "abyssal" in text
    assert "zone_4" in text
    assert "abyssal_terrors" in text
