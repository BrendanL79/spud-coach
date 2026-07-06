from datetime import datetime, UTC

from brotato_coach.builders.timestamps import format_generated_at


def test_format_generated_at_matches_iso8601_with_z_suffix():
    dt = datetime(2026, 7, 5, 12, 34, 56, tzinfo=UTC)
    assert format_generated_at(dt) == "2026-07-05T12:34:56Z"
