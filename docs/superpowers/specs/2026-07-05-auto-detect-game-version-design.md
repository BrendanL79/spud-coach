# Auto-detect game version from the decompiled singleton

## Goal

`build_dataset.py --game-version` is currently `required=True`, and the README tells users to
"check the Steam client" for the value because "it is not recorded inside the .pck." That's
misleading: `recovered/singletons/progress_data.gd` (decompiled GDScript, part of the existing
`recovered/` extraction) declares `const VERSION = "1.1.15.4"` — the game's own source of truth
for its version string. Read it from there by default instead of asking the user to supply it
by hand.

## Design

### New module: `brotato_coach/builders/version.py`

One pure function, parallel to `builders/localization.py`'s `parse_translations_csv` (parses
text, does no file I/O):

```python
import re

_VERSION_RE = re.compile(r'const VERSION\s*=\s*"([^"]+)"')

def parse_game_version(text: str) -> str | None:
    """Extract the VERSION constant from progress_data.gd source text.

    Returns None if the constant isn't present (e.g. the singleton's format changed).
    """
    m = _VERSION_RE.search(text)
    return m.group(1) if m else None
```

### `build_dataset.py` changes

- `--game-version` changes from `required=True` to `default=None` — an explicit override, not
  a mandatory input.
- New `--version-file` arg, `default="recovered/singletons/progress_data.gd"` — same pattern as
  the existing `--translations` default (a hardcoded path under `recovered/`, overridable, and
  tolerant of the file being absent).
- Resolution order in `main()`, replacing the direct `args.game_version` usage:

```python
game_version = args.game_version
if game_version is None:
    if os.path.isfile(args.version_file):
        game_version = parse_game_version(_read(args.version_file))
    if game_version is None:
        parser.error(
            f"could not detect game version from {args.version_file}; "
            "pass --game-version explicitly")
```

Precedence: an explicitly-passed `--game-version` always wins, even if the version file is
present and parses fine — this preserves the ability to build against a declared version other
than what's in a given `recovered/` checkout (e.g. testing). If neither source yields a version,
the build fails the same way it does today (a required value with no default), just pointed at
`--version-file` instead of `--game-version` in the error message.

### Docs updates

- `README.md`'s "Building the dataset" section: both the Bash and PowerShell example commands
  drop the `--game-version` line entirely (it's now optional/auto-detected). Add a sentence
  noting auto-detection from `recovered/singletons/progress_data.gd`, with `--game-version` kept
  documented as an explicit-override flag for the rare case the file's missing or wrong.
- Project `CLAUDE.md`'s build snippet (`uv run python build_dataset.py --game-version <ver>
  --generated-at <iso8601>`) updates to drop `--game-version`, keeping the "generated_at is
  never read from a clock" reproducibility note (unaffected — this change is only about
  `game_version`, which was never clock-derived to begin with).
- Downstream effect (not part of this task, tracked separately): the not-yet-implemented landing
  page "Build your dataset" section (`2026-07-05-landing-page-content-expansion-design.md`)
  currently shows `--game-version <your-installed-version>` in its PowerShell command — that
  spec needs a follow-up edit to drop the flag once this change lands, since the whole point of
  that placeholder was working around the exact manual-entry problem this task removes.

## Testing (TDD)

New `tests/test_build_version.py`, following the existing `test_build_<module>.py` convention:

- `parse_game_version` finds `"1.1.15.4"` in a real-shaped fixture string (`const VERSION =
  "1.1.15.4"` plus surrounding lines copied from the actual file's structure, e.g. the
  `VERSION_SWITCH` constant beneath it, to guard against a regex that's accidentally too greedy).
- `parse_game_version` returns `None` for text with no `VERSION` constant at all.
- `parse_game_version` returns `None` for a near-miss (e.g. `const VERSION_SWITCH = "..."` alone,
  no bare `VERSION`) — guards against the regex matching the wrong constant.

No test needs a real `recovered/` checkout — this worktree doesn't have one (it's gitignored),
and the function under test takes text, not a path. The `build_dataset.py` CLI wiring
(file-exists check, `parser.error` fallback) is thin enough to be covered by inspection rather
than a dedicated subprocess test, consistent with `build_dataset.py` having no existing test
file of its own today.

## Out of scope

- Changing `brotato_coach/dataset.py`'s `assemble_dataset(game_version=...)` signature — it
  already just takes a string; where that string comes from is entirely `build_dataset.py`'s
  concern.
- Validating the detected version against any known-good list, or warning on version mismatches
  between `--extracted` and the detected value — out of scope for this fix.
- Implementing the landing-page spec's follow-up edit — noted above, but that's a change to an
  already-approved separate spec, not part of this task.
