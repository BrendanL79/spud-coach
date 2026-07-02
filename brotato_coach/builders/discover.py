from __future__ import annotations

import glob
import os


def find_weapon_dirs(extracted_root: str) -> list[dict]:
    results = []
    for kind in ("ranged", "melee"):
        pattern = os.path.join(extracted_root, "weapons", kind, "*", "*")
        for tier_dir in sorted(glob.glob(pattern)):
            if not os.path.isdir(tier_dir):
                continue
            tier_name = os.path.basename(tier_dir)
            if not tier_name.isdigit():
                continue
            weapon_folder = os.path.basename(os.path.dirname(tier_dir))
            stats = glob.glob(os.path.join(tier_dir, "*_stats.tres"))
            data = glob.glob(os.path.join(tier_dir, "*_data.tres"))
            if not stats or not data:
                continue
            results.append({
                "weapon_id": f"weapon_{weapon_folder}",
                "name": weapon_folder.replace("_", " ").title(),
                "tier": int(tier_name),
                "stats_path": stats[0],
                "data_path": data[0],
            })
    return results
