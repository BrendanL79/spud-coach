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
