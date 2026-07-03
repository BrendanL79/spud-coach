from __future__ import annotations

from brotato_coach.builders.localization import resolve_text
from brotato_coach.tres import parse_tres


def build_set_record(set_data_text: str, count_effect_texts: dict[int, str], *,
                     set_id: str, name: str, tr: dict[str, str] | None = None) -> dict:
    d = parse_tres(set_data_text).resource
    bonuses = []
    for count in sorted(count_effect_texts):
        r = parse_tres(count_effect_texts[count]).resource
        bonuses.append({
            "count": count,
            "effect": {"key": r.get("key", ""), "value": r.get("value", 0)},
        })
    return {"id": set_id, "name": name,
            "display_name": resolve_text(tr, d.get("name"), name),
            "description": resolve_text(tr, d.get("description")),
            "bonuses": bonuses}
