import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import diff_dataset


def _ds(**over):
    base = {"schema_version": 7, "game_version": "1.1.15.4", "content_sources": ["base"],
            "weapons": [], "items": [], "characters": [], "sets": [], "enemies": []}
    base.update(over)
    return base


def test_diff_detects_added_removed_changed_weapons():
    old = _ds(weapons=[{"id": "w_keep", "base_damage": 10, "source": "base"},
                       {"id": "w_gone", "base_damage": 5, "source": "base"}])
    new = _ds(weapons=[{"id": "w_keep", "base_damage": 12, "source": "base"},
                       {"id": "w_new", "base_damage": 8, "source": "abyssal_terrors"}],
              content_sources=["abyssal_terrors", "base"])
    diff = diff_dataset.diff_datasets(old, new)
    assert diff["weapons"]["added"] == ["w_new"]
    assert diff["weapons"]["removed"] == ["w_gone"]
    assert diff["weapons"]["changed"] == {"w_keep": {"base_damage": [10, 12]}}
    assert diff["new_sources"] == ["abyssal_terrors"]


def test_diff_collects_new_unmodeled_effects():
    old = _ds()
    new = _ds(weapons=[{"id": "w", "source": "abyssal_terrors",
                        "unmodeled_effects": ["curse_bind"]}])
    diff = diff_dataset.diff_datasets(old, new)
    assert diff["new_unmodeled_effects"] == ["curse_bind"]


def test_format_report_is_readable():
    old = _ds()
    new = _ds(game_version="1.2.0.0", weapons=[{"id": "w_new", "source": "base"}])
    text = diff_dataset.format_report(diff_dataset.diff_datasets(old, new))
    assert "1.1.15.4 -> 1.2.0.0" in text
    assert "w_new" in text
