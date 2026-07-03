from __future__ import annotations

import argparse
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from brotato_coach import answers, dataset, evaluate, query
from brotato_coach.schemas import Stats


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
        """Look up one weapon's full record: base stats, scaling stats, and the
        precomputed DPS line (dps_at_zero_rd, dps_slope_per_rd).

        Weapons exist at multiple tiers (1-6). Omit `tier` to get every tier that
        matches (returned as `{"matches": [...]}`); pass `tier` to pin one. On a
        miss, returns `{"error": "not_found", "did_you_mean": [...]}`.
        """
        return _safe(query.get_weapon)(ds=ds, name=name, tier=tier)

    @mcp.tool()
    def get_item(name: str) -> dict[str, Any]:
        """Look up one item's full record: effects, tags, archetype, and
        frozen_stat. Use for 'what does this item do'. Returns a not_found error
        with `did_you_mean` suggestions if the name doesn't match."""
        return _safe(query.get_item)(ds=ds, name=name)

    @mcp.tool()
    def get_character(name: str) -> dict[str, Any]:
        """Look up one character's kit: wanted_tags, banned_item_groups,
        flat_bonuses, gain_modifiers (stat-gain multipliers), and special_effects.
        Use this to know what a character wants and can't use before evaluating a build."""
        return _safe(query.get_character)(ds=ds, name=name)

    @mcp.tool()
    def get_weapon_class_set(class_name: str) -> dict[str, Any]:
        """Look up the set bonuses for a weapon CLASS (e.g. 'Blade', 'Gun',
        'Elemental'), keyed by how many weapons of that class are equipped.

        `class_name` is a weapon-*class* name, NOT an individual weapon name.
        Call get_filter_options to see the available class names.
        """
        return _safe(query.get_set)(ds=ds, class_name=class_name)

    @mcp.tool()
    def loadout_set_bonuses(weapon_names: list[str]) -> dict[str, Any]:
        """Report weapon-class set progress for a whole loadout: per class, how
        many equipped weapons count toward it, which set bonuses are ACTIVE
        now, and the NEXT threshold with how many more weapons it needs.

        `weapon_names` is the loadout as weapon names; tiers don't matter for
        class membership and duplicates count (six SMGs = six Gun weapons).
        Use when the player asks 'what set bonuses do I have / what should I
        add to hit the next bonus'. Unknown names come back under
        `unknown_weapons` with did_you_mean suggestions. For one class's full
        bonus table, use get_weapon_class_set instead.
        """
        return _safe(answers.loadout_set_bonuses)(ds=ds, weapon_names=weapon_names)

    @mcp.tool()
    def list_weapons(scaling_stat: str | None = None, tier: int | None = None) -> dict[str, Any]:
        """List weapon summaries (id, name, tier), optionally filtered by
        `scaling_stat` (a stat the weapon scales with) and/or `tier` (1-6).
        Filter values are case-sensitive; call get_filter_options first for the
        exact valid values."""
        return _safe(lambda **kw: {"weapons": query.list_weapons(ds, **kw)})(
            scaling_stat=scaling_stat, tier=tier)

    @mcp.tool()
    def list_items(tag: str | None = None, scaling_stat: str | None = None,
                   archetype: str | None = None, tier: int | None = None) -> dict[str, Any]:
        """List item summaries (id, name, tier), optionally filtered by `tag`,
        `scaling_stat`, `archetype`, and/or `tier` (1-4). All filters are
        case-sensitive exact matches — call get_filter_options first to see the
        valid tags, archetypes, and scaling stats."""
        return _safe(lambda **kw: {"items": query.list_items(ds, **kw)})(
            tag=tag, scaling_stat=scaling_stat, archetype=archetype, tier=tier)

    @mcp.tool()
    def weapon_dps(name: str, tier: int, stats: Stats,
                   aoe_enemies_hit: float = 1.0) -> dict[str, Any]:
        """Compute one weapon's realized DPS for a given build, with a breakdown.

        `dps` = guaranteed line (`base_dps`) + expected on-hit proc damage
        (`proc_dps`, e.g. exploding projectiles — chance x the weapon's own
        damage line).
        `aoe_enemies_hit` scales the proc term for AoE procs (default 1 enemy,
        conservative). Effect keys the model can't yet value are listed in
        `unmodeled_effects` — mention them when the number matters. `stats` is
        the player's current run stats (short names, e.g. ranged_damage); DPS
        scales linearly with ranged_damage. For ranking several weapons, use
        compare_weapons; for merge-order questions, use compare_merge_paths.
        """
        return _safe(answers.weapon_dps)(ds=ds, name=name, tier=tier,
                                         stats=stats.as_dict(),
                                         aoe_enemies_hit=aoe_enemies_hit)

    @mcp.tool()
    def compare_weapons(names_with_tiers: list[tuple[str, int]], stats: Stats,
                        aoe_enemies_hit: float = 1.0) -> dict[str, Any]:
        """Rank several weapons by realized DPS (guaranteed + expected proc
        damage) at the SAME build stats.

        `names_with_tiers` is a list of [name, tier] pairs, e.g.
        [["Minigun", 4], ["SMG", 6]]. `aoe_enemies_hit` scales proc terms for
        AoE procs (default 1). Returns `{"ranking": [...]}` sorted by total DPS
        descending. Use when the player asks 'which of these hits hardest'.
        """
        return _safe(lambda **kw: answers.compare_weapons(
            ds, [tuple(x) for x in kw["names_with_tiers"]], kw["stats"],
            kw["aoe_enemies_hit"]))(
            names_with_tiers=names_with_tiers, stats=stats.as_dict(),
            aoe_enemies_hit=aoe_enemies_hit)

    @mcp.tool()
    def compare_merge_paths(weapon_name: str, path_a: list[int],
                            path_b: list[int]) -> dict[str, Any]:
        """Compare two tier-merge paths for the SAME weapon across the
        ranged-damage range.

        Answers the Brotato 'which merge order is better' question. `path_a` and
        `path_b` are lists of tiers (ints), e.g. [1, 1, 2] vs [1, 2, 2]. Returns
        the winner if one path dominates at all RD, or the crossover ranged-damage
        value where the better path flips. Path lines include expected proc DPS
        (at the default single-enemy AoE assumption; aoe_enemies_hit is not
        tunable here).
        """
        return _safe(answers.compare_merge_paths)(
            ds=ds, weapon_name=weapon_name, path_a=path_a, path_b=path_b)

    @mcp.tool()
    def explain_stat(stat: str) -> dict[str, Any]:
        """Return verified mechanics for a stat: caps, special behaviors, and
        whether it's ever dead weight / safe below zero.

        `stat` uses the `stat_`-prefixed form, e.g. 'stat_crit_chance'. This is
        about how a stat WORKS — for converting a raw value to what the game shows
        a given character, use stat_display_value instead.
        """
        return _safe(answers.explain_stat)(ds=ds, stat=stat)

    @mcp.tool()
    def stat_display_value(character: str, stat: str, raw_value: float) -> dict[str, Any]:
        """Convert a raw stat value into the value the game DISPLAYS for a given
        character, after that character's stat-gain modifiers.

        E.g. a character with +50% ranged-damage gains shows raw 6 as 9. `stat`
        uses the `stat_`-prefixed form, e.g. 'stat_ranged_damage'. This is about a
        character's displayed number — for a stat's mechanics, use explain_stat.
        """
        return _safe(answers.stat_display_value)(
            ds=ds, character=character, stat=stat, raw_value=raw_value)

    @mcp.tool()
    def evaluate_item_for_build(item_name: str, character_name: str,
                                current_stats: Stats) -> dict[str, Any]:
        """Decide whether an item is worth taking for a specific character/build.

        The flagship 'should I pick this up' tool. Returns a per-effect verdict —
        **live** (applies/wanted), **wasted** (no effect for this build, e.g.
        melee damage on a no-melee character), or **harmful** — each with a reason,
        plus a summary line. `current_stats` is the player's current run stats
        (short stat names, e.g. ranged_damage), used to judge whether an effect
        lands.
        """
        return _safe(evaluate.evaluate_item_for_build)(
            ds=ds, item_name=item_name, character_name=character_name,
            current_stats=current_stats.as_dict())

    @mcp.tool()
    def get_filter_options() -> dict[str, Any]:
        """List the valid filter values in the loaded dataset so you filter with
        exact, case-sensitive values.

        Returns the item tags, item archetypes, scaling stats (item and weapon),
        available tiers, and the weapon-class names for get_weapon_class_set. Call
        this before list_items / list_weapons / get_weapon_class_set rather than
        guessing values.
        """
        def _uniq(vals) -> list:
            return sorted({v for v in vals if v})

        def _compute() -> dict[str, Any]:
            items = ds.get("items", [])
            weapons = ds.get("weapons", [])
            return {
                "item_tags": _uniq(t for it in items for t in it.get("tags", [])),
                "item_archetypes": _uniq(a for it in items for a in it.get("archetype", [])),
                "item_scaling_stats": _uniq(s for it in items for s in it.get("scaling_stats", [])),
                "weapon_scaling_stats": _uniq(
                    s[0] for w in weapons for s in w.get("scaling_stats", [])
                    if isinstance(s, list) and s),
                "tiers": sorted({x.get("tier") for x in [*weapons, *items]
                                 if x.get("tier") is not None}),
                "weapon_classes": _uniq(s.get("name") or s.get("id") for s in ds.get("sets", [])),
            }
        return _safe(_compute)()

    @mcp.tool()
    def check_dataset_version() -> dict[str, Any]:
        """Report the loaded dataset's provenance: game_version, generated_at, and
        schema_version. Use to confirm which Brotato version the facts are from."""
        return _safe(lambda: {
            "game_version": ds.get("game_version"),
            "generated_at": ds.get("generated_at"),
            "schema_version": ds.get("schema_version"),
        })()

    return mcp


def _data_path(argv: list[str] | None = None) -> str:
    parser = argparse.ArgumentParser(prog="spudcoach")
    parser.add_argument(
        "--data", default=os.environ.get("SPUDCOACH_DATA", "data/brotato.json"),
        help="path to brotato.json built by build_dataset.py "
             "(also settable via SPUDCOACH_DATA)")
    return parser.parse_args(argv).data


def main() -> None:
    ds = dataset.load_dataset(_data_path())
    build_server(ds).run()


if __name__ == "__main__":
    main()
