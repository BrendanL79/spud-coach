# Brotato Coach

A deterministic theorycrafter for [Brotato](https://store.steampowered.com/app/1942280/Brotato/),
delivered as an MCP server you can chat with from Claude Code (and other MCP clients).

The design principle: **a deterministic core holds the ground truth** — weapon/item/character
data, DPS formulas, stat mechanics — so the language model *looks facts up and computes* instead
of recalling (and misremembering) them. Every tool returns a finished, verifiable answer or a
structured error; there are no baked-in tier lists or opinions, only facts and math.

The dataset (`data/brotato.json`) is **not committed** — it is derived from copyrighted game
files, so you build it yourself from a local Brotato install (see [Building the dataset](#building-the-dataset)).
A full build from **Brotato 1.1.15.4** contains **202 weapons, 197 items, 50 characters, and 15
weapon-class sets**.

## Requirements

- Python **3.11+**
- [`uv`](https://docs.astral.sh/uv/) for environment/dependency management

Install dependencies:

```bash
uv sync
```

## Quick start

Build the dataset (needs a local extraction — see [Building the dataset](#building-the-dataset)),
then start the server:

```bash
uv run python build_dataset.py --game-version 1.1.15.4 \
    --generated-at $(date -u +%Y-%m-%dT%H:%M:%SZ)     # writes data/brotato.json
uv run python -m brotato_coach.server                 # starts the MCP server over stdio
```

The server refuses to start without `data/brotato.json` and tells you to build it first.

Run the tests (the dataset-dependent integration test is skipped when no dataset is built):

```bash
uv run pytest        # 89 tests (88 passed + 1 skipped without a built dataset)
```

## Run

```bash
uvx spudcoach --data /path/to/brotato.json
```

The dataset is never distributed — build your own from your Brotato install:
`uv run python build_dataset.py --game-version <ver> --generated-at <iso8601>`
(see [docs/extraction-setup.md](docs/extraction-setup.md)). `SPUDCOACH_DATA` works as an env-var alternative
to `--data`.

## Use as a Claude Code plugin

The MCP server is described by [`plugin/.mcp.json`](plugin/.mcp.json):

```json
{
  "mcpServers": {
    "brotato-coach": {
      "command": "uv",
      "args": ["run", "python", "-m", "brotato_coach.server"],
      "cwd": "${CLAUDE_PLUGIN_ROOT}"
    }
  }
}
```

The server reads the (locally built) `data/brotato.json` relative to its working directory, so
**it must run with the repository root as its `cwd`** (the manifest handles this via
`${CLAUDE_PLUGIN_ROOT}` when bundled as a plugin), and you must
[build the dataset](#building-the-dataset) first.

To register it directly in Claude Code without packaging, add the server pointed at your checkout,
e.g.:

```bash
claude mcp add brotato-coach -- uv run --directory /path/to/brotato-exam python -m brotato_coach.server
```

Once connected, just ask in natural language — the model routes your question to the tools below:

- *"Does Handcuffs fit my Ranger run? I'm at 7 ranged damage, 65 HP."*
- *"Minigun T4 vs Revolver T4 at 20 ranged damage — which hits harder?"*
- *"Is attack speed ever dead weight? Can I let knockback go negative on a gun build?"*
- *"What does the Ranger's ranged-damage bonus do to a raw stat of 6?"*

## Use with Claude Desktop

Claude Desktop can launch the server with [`uvx`](https://docs.astral.sh/uv/) in two forms: fetch
straight from this repo (auto-updates on restart, but needs `git` reachable — see the Windows note
below), or point at a **local checkout** (nothing fetched at runtime; the most reliable form on
Windows). Either way you supply your own locally built `brotato.json` — the dataset is never
distributed.

1. Install `uv` on the machine running Claude Desktop (`winget install astral-sh.uv` on Windows,
   or the [standalone installer](https://docs.astral.sh/uv/getting-started/installation/)).
2. Open the config file and add the `spud-coach` server:
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

   Fetch-from-repo form:

   ```json
   {
     "mcpServers": {
       "spud-coach": {
         "command": "uvx",
         "args": [
           "--from", "git+https://github.com/BrendanL79/spud-coach",
           "spudcoach",
           "--data", "C:\\Users\\<you>\\path\\to\\brotato.json"
         ]
       }
     }
   }
   ```

   Point `--data` at your built dataset (`SPUDCOACH_DATA` works as an env-var alternative). On macOS
   use a POSIX path like `/Users/<you>/brotato.json`.
3. Fully restart Claude Desktop (quit from the tray, not just close the window).

### Windows: "Git executable not found" (or `uvx` not found)

The `git+https://…` form makes uv shell out to a `git` executable. **Claude Desktop does not pass
your shell — or even your System `PATH` — to the MCP subprocess;** it spawns servers with its own
trimmed environment. (The `PATH` it prints in the logs is its command-resolution list, *not* what
the child process receives.) So a `git` that runs fine in PowerShell, installed in a System-`PATH`
directory, can still come back "not found" here — and a bare `"command": "uvx"` can fail to resolve
for the same reason. Two fixes:

- **Point at a local checkout — no runtime git (recommended).** Clone once in a terminal where git
  works, then use `--from <folder>` instead of `--from git+…`:

  ```powershell
  git clone https://github.com/BrendanL79/spud-coach C:\Users\<you>\src\spud-coach
  ```
  ```json
  {
    "mcpServers": {
      "spud-coach": {
        "command": "uvx",
        "args": ["--from", "C:\\Users\\<you>\\src\\spud-coach", "spudcoach",
                 "--data", "C:\\Users\\<you>\\path\\to\\brotato.json"]
      }
    }
  }
  ```

  Update later with `git pull` in that folder, then restart Desktop.

- **Or force the tools onto the server's `PATH`.** Keep the `git+https` form and add an `env` block
  that hands the child an explicit `PATH` — git, plus uv's bin and the winget-links dir:

  ```json
  "env": {
    "PATH": "C:\\Program Files\\Git\\cmd;C:\\Users\\<you>\\.local\\bin;C:\\Users\\<you>\\AppData\\Local\\Microsoft\\WinGet\\Links;C:\\Windows\\System32"
  }
  ```

  If `uvx` itself still isn't found, also set `"command"` to its absolute path (`Get-Command uvx` to
  locate it, e.g. `C:\Users\<you>\AppData\Local\Microsoft\WinGet\Links\uvx.exe`).

## Available tools

All tools return a JSON object. Lookups that miss return `{"error": "not_found", "did_you_mean": [...]}`.

| Tool | Arguments | Returns |
|------|-----------|---------|
| `get_weapon` | `name`, `tier?` | Weapon record incl. precomputed DPS line, on-hit `effects`, and weapon-class `sets`; `{matches:[...]}` if `tier` omitted and several tiers match |
| `get_item` | `name` | Item record: effects, tags, `archetype`, `frozen_stat` |
| `get_character` | `name` | Character kit: `wanted_tags`, `banned_item_groups`, `flat_bonuses`, `gain_modifiers`, `special_effects` |
| `get_weapon_class_set` | `class_name` | Weapon-**class** set bonuses (Blade, Gun, Elemental, …), by equipped count |
| `loadout_set_bonuses` | `weapon_names` | Per-class set progress across a whole loadout: equipped count, active bonuses, and next threshold |
| `list_weapons` | `scaling_stat?`, `tier?` | `{weapons:[...]}` filtered summaries |
| `list_items` | `tag?`, `scaling_stat?`, `archetype?`, `tier?` | `{items:[...]}` filtered summaries |
| `get_filter_options` | — | Valid filter values in the dataset: item tags, archetypes, scaling stats, tiers, and weapon-class names |
| `weapon_dps` | `name`, `tier`, `stats` | Realized DPS at the given stats, with breakdown |
| `compare_weapons` | `names_with_tiers`, `stats` | `{ranking:[...]}` sorted by DPS descending |
| `compare_merge_paths` | `weapon_name`, `path_a`, `path_b` | Winner or crossover RD for two merge paths (lists of tiers) |
| `explain_stat` | `stat` | Verified stat mechanics: caps, special behavior, neglectable / never-negative flags |
| `stat_display_value` | `character`, `stat`, `raw_value` | Displayed value after the character's gain modifiers (e.g. Ranger RD 6 → 9) |
| `evaluate_item_for_build` | `item_name`, `character_name`, `current_stats` | Per-effect verdict — **live / wasted / harmful** — with reasons, plus a summary |
| `check_dataset_version` | — | `game_version`, `generated_at`, `schema_version` |

`stats` / `current_stats` are objects keyed by short stat name (e.g. `{"ranged_damage": 7, "max_hp": 65}`).
`names_with_tiers` is a list of `[name, tier]` pairs. `path_a` / `path_b` are lists of tier numbers.
Note the two stat-name forms: `stats` / `current_stats` use the **short** name (`ranged_damage`), while the `stat` argument of `explain_stat` and `stat_display_value` uses the **`stat_`-prefixed** form (`stat_ranged_damage`). `get_filter_options` returns the valid filter values so you don't have to guess (all filters are case-sensitive exact matches).

## Building the dataset

The dataset is **not committed** — it is built from an extraction of a real game install. The raw
`extracted/`, the decompiled `recovered/`, the copyrighted `game_files/`, and the derived
`data/brotato.json` are all gitignored (see [`docs/extraction-setup.md`](docs/extraction-setup.md)
for how the extraction is produced). Once `extracted/` is present at the repo root:

```bash
uv run python build_dataset.py \
    --game-version 1.1.15.4 \
    --generated-at $(date -u +%Y-%m-%dT%H:%M:%SZ)
```

This writes `data/brotato.json`. Supply the actual installed Brotato version to `--game-version`
(it is not recorded inside the `.pck`; check the Steam client). Re-run after each patch to refresh
your local copy — it stays gitignored, so don't commit it.

## How it works

```
extracted/  (gitignored, regenerable)          raw .tres game data
     │
     ▼   build_dataset.py   (offline, per patch)
data/brotato.json  (gitignored, built locally)  the deterministic core artifact
     │
     ▼   loaded at startup
brotato_coach.server (FastMCP)                  15 tools over the pure functions
     │
     ▼   connected as a plugin
Claude Code / Desktop / Web                     chat frontend
```

- `brotato_coach/tres.py` — a minimal Godot `.tres` parser.
- `brotato_coach/builders/` — turn parsed `.tres` into enriched records (weapons with precomputed DPS
  lines, items with archetype flags, characters with gain modifiers, sets, and the verified
  `stat_mechanics` table).
- `brotato_coach/calc.py` — pure DPS / merge math (no I/O), unit-tested against hand-verified values.
- `brotato_coach/{query,answers,evaluate}.py` — pure functions that produce finished answers.
- `brotato_coach/server.py` — thin FastMCP wrappers over those functions.

Reference material on the game mechanics the coach encodes lives in [`docs/`](docs/)
(extraction setup, weapon-merge DPS methodology, run post-mortem methodology, stat mechanics).

## Disclaimer

This is an unofficial, fan-made tool. It is **not affiliated with, endorsed by, or sponsored by
Blobfish**, the developer of Brotato, or any of its partners. *Brotato* and all related names,
marks, and assets are the property of their respective owners.

This project ships **no game assets and no game data**. The stat dataset it operates on is
generated locally, by you, from a copy of the game you already own (`build_dataset.py` reads an
extraction of your own install). Nothing derived from the game's copyrighted files is distributed
in this repository.

The software is provided "as is", without warranty of any kind (see [LICENSE](LICENSE)). Its
recommendations are computed from datamined values and may be incomplete or wrong; use your own
judgment.

## License

[MIT](LICENSE) © 2026 Brendan LeFebvre. This license covers the code and documentation in this
repository only — it does not grant any rights to Brotato or its assets.
