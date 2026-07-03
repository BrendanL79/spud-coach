"""Verified stat mechanics, encoded from decompiled code (see docs/stat-mechanics.md).

Only stats whose behavior has been confirmed against the game code are listed.
This table is authoritative for what the coach claims about stat mechanics.
"""

from __future__ import annotations


def _m(cap=None, special=None, safe_below_zero=False, safe_at_zero=False,
       avoid_positive=False, never_dead_weight=False, summary=None) -> dict:
    return {
        "cap": cap, "special": special, "safe_below_zero": safe_below_zero,
        "safe_at_zero": safe_at_zero, "avoid_positive": avoid_positive,
        "never_dead_weight": never_dead_weight, "summary": summary,
    }


_WEAPON_SCALING = ("Weapon scaling stat: each weapon whose scaling_stats lists "
                   "it adds coefficient x stat to that weapon's damage per hit; "
                   "it does nothing for weapons without a matching entry — check "
                   "the weapon record's scaling_stats.")

STAT_MECHANICS: dict[str, dict] = {
    "stat_max_hp": _m(cap={"cap_key": "hp_cap"},
                      summary="Capped via hp_cap; cap-at-current-value items "
                              "(Handcuffs) can freeze it for the run."),
    "stat_speed": _m(cap={"cap_key": "speed_cap"},
                     summary="Capped via speed_cap; freezable by Shackles "
                             "(cap-at-current-value)."),
    "stat_dodge": _m(cap={"cap_key": "dodge_cap"},
                     summary="Capped via dodge_cap (utils.gd get_capped_stat)."),
    "stat_crit_chance": _m(cap={"cap_key": "crit_chance_cap"},
                           summary="Capped via crit_chance_cap (utils.gd "
                                   "get_capped_stat)."),
    "stat_curse": _m(cap={"cap_key": "curse_cap"}, special="curse_sqrt_penalty",
                     safe_below_zero=True, avoid_positive=True,
                     summary="Positive curse scales enemy damage/HP by a "
                             "sqrt(curse) factor (entity_service.gd) — avoid. "
                             "Negative curse is clamped to zero benefit: "
                             "harmless, but not a defensive gain."),
    "stat_hp_regeneration": _m(special="regen_zero_safe", safe_below_zero=True,
                               safe_at_zero=True,
                               summary="At or below 0 it is a harmless no-op — "
                                       "player.gd just stops the regen timer."),
    "stat_lifesteal": _m(special="lifesteal_negative_drains",
                         summary="Negative lifesteal actively drains HP on hit "
                                 "(unlike regen, which no-ops at or below 0)."),
    "stat_attack_speed": _m(special="attack_speed_universal", never_dead_weight=True,
                            summary="Universal cooldown-reducing multiplier, "
                                    "applied identically to ranged and melee "
                                    "weapons — never dead weight."),
    "knockback": _m(special="knockback_clamped_by_weapon_flag", safe_below_zero=True,
                    safe_at_zero=True,
                    summary="Clamped to non-negative per weapon unless the "
                            "weapon sets can_have_negative_knockback."),
    # Weapon scaling-damage stats — mechanism verified by this repo's own
    # hand-verified DPS model (docs/weapon-merge-dps-methodology.md).
    "stat_ranged_damage": _m(special="weapon_scaling_stat", summary=_WEAPON_SCALING),
    "stat_melee_damage": _m(special="weapon_scaling_stat", summary=_WEAPON_SCALING),
    "stat_elemental_damage": _m(special="weapon_scaling_stat", summary=_WEAPON_SCALING),
    "stat_engineering": _m(special="weapon_scaling_stat", summary=_WEAPON_SCALING),
}
