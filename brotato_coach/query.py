from __future__ import annotations

import difflib


def _names(records: list[dict]) -> list[str]:
    out = []
    for r in records:
        out.extend([r.get("name", ""), r.get("id", "")])
    return [n for n in out if n]


def _suggest(records: list[dict], name: str) -> list[str]:
    return difflib.get_close_matches(name, _names(records), n=3, cutoff=0.5)


def _match(records: list[dict], name: str) -> list[dict]:
    low = name.lower()
    return [r for r in records if r.get("name", "").lower() == low or r.get("id", "").lower() == low]


def get_weapon(ds: dict, name: str, tier: int | None = None) -> dict:
    matches = _match(ds["weapons"], name)
    if tier is not None:
        matches = [m for m in matches if m.get("tier") == tier]
    if not matches:
        return {"error": "not_found", "did_you_mean": _suggest(ds["weapons"], name)}
    if len(matches) == 1:
        return matches[0]
    return {"matches": matches}


def _get_one(records: list[dict], name: str) -> dict:
    matches = _match(records, name)
    if not matches:
        return {"error": "not_found", "did_you_mean": _suggest(records, name)}
    return matches[0]


def get_item(ds: dict, name: str) -> dict:
    return _get_one(ds["items"], name)


def get_character(ds: dict, name: str) -> dict:
    return _get_one(ds["characters"], name)


def get_set(ds: dict, class_name: str) -> dict:
    return _get_one(ds["sets"], class_name)


def _summary(r: dict) -> dict:
    return {"id": r.get("id"), "name": r.get("name"), "tier": r.get("tier")}


def list_weapons(ds: dict, *, scaling_stat=None, tier=None) -> list[dict]:
    out = []
    for w in ds["weapons"]:
        if tier is not None and w.get("tier") != tier:
            continue
        if scaling_stat is not None:
            stats = [s[0] for s in w.get("scaling_stats", []) if isinstance(s, list) and s]
            if scaling_stat not in stats:
                continue
        out.append(_summary(w))
    return out


def list_items(ds: dict, *, tag=None, scaling_stat=None, archetype=None, tier=None) -> list[dict]:
    out = []
    for it in ds["items"]:
        if tier is not None and it.get("tier") != tier:
            continue
        if tag is not None and tag not in it.get("tags", []):
            continue
        if scaling_stat is not None and scaling_stat not in it.get("scaling_stats", []):
            continue
        if archetype is not None and archetype not in it.get("archetype", []):
            continue
        out.append(_summary(it))
    return out
