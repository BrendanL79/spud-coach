from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from brotato_coach import answers, dataset, evaluate, query


def _safe(fn):
    def wrapper(**kwargs):
        try:
            return fn(**kwargs)
        except Exception as exc:  # noqa: BLE001 - surface as structured error, never a traceback
            return {"error": "internal", "detail": str(exc)}
    return wrapper


def build_server(ds: dict) -> FastMCP:
    mcp = FastMCP("brotato-coach")

    @mcp.tool()
    def get_weapon(name: str, tier: int | None = None) -> dict[str, Any]:
        return _safe(query.get_weapon)(ds=ds, name=name, tier=tier)

    @mcp.tool()
    def get_item(name: str) -> dict[str, Any]:
        return _safe(query.get_item)(ds=ds, name=name)

    @mcp.tool()
    def get_character(name: str) -> dict[str, Any]:
        return _safe(query.get_character)(ds=ds, name=name)

    @mcp.tool()
    def get_set(class_name: str) -> dict[str, Any]:
        return _safe(query.get_set)(ds=ds, class_name=class_name)

    @mcp.tool()
    def list_weapons(scaling_stat: str | None = None, tier: int | None = None) -> dict[str, Any]:
        return _safe(lambda **kw: {"weapons": query.list_weapons(ds, **kw)})(
            scaling_stat=scaling_stat, tier=tier)

    @mcp.tool()
    def list_items(tag: str | None = None, scaling_stat: str | None = None,
                   archetype: str | None = None, tier: int | None = None) -> dict[str, Any]:
        return _safe(lambda **kw: {"items": query.list_items(ds, **kw)})(
            tag=tag, scaling_stat=scaling_stat, archetype=archetype, tier=tier)

    @mcp.tool()
    def weapon_dps(name: str, tier: int, stats: dict) -> dict[str, Any]:
        return _safe(answers.weapon_dps)(ds=ds, name=name, tier=tier, stats=stats)

    @mcp.tool()
    def compare_weapons(names_with_tiers: list, stats: dict) -> dict[str, Any]:
        return _safe(lambda **kw: answers.compare_weapons(
            ds, [tuple(x) for x in kw["names_with_tiers"]], kw["stats"]))(
            names_with_tiers=names_with_tiers, stats=stats)

    @mcp.tool()
    def compare_merge_paths(weapon_name: str, path_a: list, path_b: list) -> dict[str, Any]:
        return _safe(answers.compare_merge_paths)(
            ds=ds, weapon_name=weapon_name, path_a=path_a, path_b=path_b)

    @mcp.tool()
    def explain_stat(stat: str) -> dict[str, Any]:
        return _safe(answers.explain_stat)(ds=ds, stat=stat)

    @mcp.tool()
    def stat_display_value(character: str, stat: str, raw_value: float) -> dict[str, Any]:
        return _safe(answers.stat_display_value)(
            ds=ds, character=character, stat=stat, raw_value=raw_value)

    @mcp.tool()
    def evaluate_item_for_build(item_name: str, character_name: str,
                                current_stats: dict) -> dict[str, Any]:
        return _safe(evaluate.evaluate_item_for_build)(
            ds=ds, item_name=item_name, character_name=character_name,
            current_stats=current_stats)

    @mcp.tool()
    def check_dataset_version() -> dict[str, Any]:
        return _safe(lambda: {
            "game_version": ds.get("game_version"),
            "generated_at": ds.get("generated_at"),
            "schema_version": ds.get("schema_version"),
        })()

    return mcp


def main() -> None:
    ds = dataset.load_dataset("data/brotato.json")
    build_server(ds).run()


if __name__ == "__main__":
    main()
