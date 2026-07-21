# DLC / major-update incorporation playbook

Execute this when a Brotato DLC (or content patch) lands. It ingests new data
cleanly, tags provenance, and produces a triage list. It does **not** model new
mechanics — those are separate spec→plan→implement cycles (curse is the expected
first one, kicked off right after ingestion).

Prereq: the base-game snapshot (`game_files/`, `extracted/`, `recovered/` as of
1.1.15.4) is backed up locally, so a base-only dataset is always reproducible.

1. **Preserve the baseline.** Keep a base-only dataset to diff against. Either
   copy the current `data/brotato.json` → `data/brotato.base.json`, or rebuild
   it from the backed-up base extraction. Both stay local (gitignored).
2. **Re-copy game files.** Copy the updated `Brotato.pck` (and any DLC pack)
   from the Steam install into `game_files/`. **Confirm how the DLC ships** — is
   there a second `.pck`? This resolves the provenance mechanism (see step 5).
3. **Re-extract.** Run `unpack_pck.py` per pack → `extracted/`; run gdre_tools
   → `recovered/`. If the DLC is a separate pack, unpack it into a marked tree
   so origin is known by construction.
4. **Rebuild + read the report.** `uv run python build_dataset.py`. Read the
   "Coverage / unmodeled-content report" (new trees / weapon kinds / zones,
   and unmodeled effects). If a new content tree/kind/zone appears, extend the
   `_ACCOUNTED_*` sets in `discover.py` (after confirming it's real content) or
   the relevant discoverer.
5. **Teach `detect_source`.** In `brotato_coach/builders/provenance.py`, fill in
   the confirmed signal from step 2 (extraction origin > in-`.tres` flag >
   directory prefix). Rebuild; confirm `content_sources` now lists the DLC id.
6. **Diff.** `uv run python tools/diff_dataset.py data/brotato.base.json data/brotato.json`
   → the triage list (added/removed/changed records, new sources, new unmodeled
   effects).
7. **Triage.** New *records* mostly ingest for free. The real work is each its
   own spec→plan→implement cycle:
   - unknown effect scripts → the existing proc-worklist process
     (`docs/proc-mechanics.md`, `builders/procs.py`/`classifications.py`);
   - new mechanics (curse/elements) → new `docs/` mechanics writeups;
   - new zones/bosses → bestiary follow-up.
8. **Re-pin all evidence** against the NEW decompiled source. Never carry
   base-game citations forward — misattributed functions have shipped that way
   before.
9. **`read_me` caveat.** If `content_sources` includes a DLC and unmodeled
   effects exist, add/refresh the primer caveat in `brotato_coach/orientation.py`
   so the coach never presents un-modeled DLC content as verified. Write the
   wording against the *actual* unmodeled list from step 6.
10. **Stamp.** Bump `DATASET_VERSION` if the delta added fields; run the build
    with `--strict` to confirm the dataset is fully triaged; stamp `server.json`
    at release time.
11. **Deploy.** Regenerate the schema-matching `brotato.json` for spudcoach-chat
    and redeploy: `fly deploy -a spudcoach-2c57` (the `fly.toml` app name is a
    placeholder, so `-a` is required). Confirm the app name is still current.
