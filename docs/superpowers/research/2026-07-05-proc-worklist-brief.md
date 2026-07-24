# Proc-worklist investigation brief (shared instructions for all family agents)

Read this whole file before doing anything else.

## Mission

You are one of several parallel investigators triaging Brotato weapon-effect keys
that the `spud-coach` dataset currently cannot model (they show up in weapon
records' `unmodeled_effects`, contributing zero DPS). Your job is **evidence
gathering and a verdict proposal** — you write ONE dossier file and change
NOTHING else. A later, serial phase turns dossiers into specs and code.

## MANDATORY first step: checkout verification

A previous session had subagents edit the wrong checkout. Before writing anything:

1. Run `git rev-parse --show-toplevel` from your working directory.
2. It MUST be `C:/Users/brend/src/spud-coach/.claude/worktrees/remaining-weapon-procs`
   (any slash style). If it is anything else, STOP immediately and return only
   the text `NEEDS_CONTEXT: wrong checkout <what you saw>`.

## Where things live

- **This worktree** (the ONLY place you may write, and only your one dossier file):
  `C:\Users\brend\src\spud-coach\.claude\worktrees\remaining-weapon-procs\`
- **Game data (read-only, in the MAIN checkout — never write/edit/commit there):**
  - Decompiled code: `C:\Users\brend\src\spud-coach\recovered\` — key files:
    `weapons/weapon.gd`, `singletons/weapon_service.gd`, `singletons/run_data.gd`,
    `entities/units/unit/unit.gd`, `entities/units/player/player.gd`,
    `effects/` and `effects/weapons/` (effect scripts), `projectiles/`.
  - Extracted data: `C:\Users\brend\src\spud-coach\extracted\weapons\{melee,ranged}\<weapon>\<tier>\`
    (`*_stats.tres`, `*_data.tres` with its `effects` array, `*_effect*.tres`).
    Some tier-1/untiered files sit at the weapon root instead of a tier dir.
- **Template for evidence quality** (read it — your dossier mirrors its Evidence section):
  `docs/superpowers/specs/2026-07-05-burn-proc-and-stat-range-design.md` (in this worktree)
- **Existing mechanics docs** (format reference + already-established facts):
  `docs/proc-mechanics.md` and `docs/stat-mechanics.md` in this worktree.
- **Builder context**: `brotato_coach/builders/procs.py` (PROC_MODELS),
  `brotato_coach/builders/weapons.py` (effect records + proc aggregation),
  `brotato_coach/calc.py` (pure DPS lines). Dataset weapons carry
  `dps_at_zero_rd`, `dps_slope_per_rd`, `proc_dps_at_zero_rd`,
  `proc_dps_slope_per_rd`, `unmodeled_effects`.

## Investigation checklist (per effect key in your family)

Your job is **evidence transcription, not design**. Follow the recipe; where a
step requires a judgment call the recipe doesn't cover, record the evidence,
mark the item `TENTATIVE`, and move on — the synthesis phase decides.

1. **Find the runtime mechanic.** Mechanical recipe:
   a. Open one shipped `.tres` for your key; note its `[ext_resource]` script
      path (e.g. `res://effects/weapons/...gd`) — that file in `recovered/` is
      the effect class. If there is no script, the key is likely consumed as a
      plain string.
   b. Grep `recovered/` for the effect's **class_name** (from the script file)
      AND for the **key string** (try both casings). Consumption points are
      usually in: `weapons/weapon.gd` (hit handlers), `singletons/
      weapon_service.gd`, `singletons/run_data.gd` / `singletons/
      effect_manager*.gd` (player-effect application), `entities/units/unit/
      unit.gd`, `projectiles/`.
   c. Read each consumption site and transcribe what it does. NOTE: the game may
      dispatch on **script class, not the key string** (true for exploding
      effects), and differently-cased keys may share one script — check the
      script attached to each .tres before assuming.
2. **Pin citations.** Every claim gets `path:line` (and function name) against the
   files as they exist right now. Quote the decisive line(s) briefly. Do not
   carry citations from docs/notes without re-checking them.
3. **Survey every shipped user.** For each weapon+tier carrying the key: list the
   effect's parameter values (chance, value, damage, counts, etc.) from its
   `.tres`, plus the weapon's relevant stats (cooldown, damage, crit, etc.) where
   they matter to the mechanic. Cover ALL tiers, including root-dir untiered files.
   **Companion resources**: if the effect `.tres` references another `.tres` for
   its numbers (as burning does via `burning_data = ExtResource( N )`), resolve
   and survey that file too, and say so explicitly in the dossier — the builder
   needs extra plumbing for these. Also list any OTHER auxiliary `.tres` files in
   the weapon dirs beyond `*_stats.tres`/`*_data.tres`/effect files: companion
   files have already broken a builder glob once (`*_burning_data.tres` matched
   the `*_data.tres` glob and corrupted 16 weapon records — fixed in commit
   25f8ca2), so naming patterns matter.
4. **Classify and propose a verdict** — exactly one of the four below. If the
   evidence does not cleanly pick one, write `Verdict: TENTATIVE` with the two
   candidate categories and the evidence for each — do NOT force a choice or
   invent math to break the tie. A TENTATIVE verdict with clean citations is a
   fully successful dossier; a confident wrong verdict is a failed one.
   - **DPS-modelable**: propose a `damage_source` name, the dps0/slope formula in
     terms the builder already has (weapon dps line, RD, effect params), and the
     preconditions under which the formula is valid — verified true for every
     shipped user (list the check per weapon/tier, like the burn spec's
     cycle_time-vs-window table). If a precondition fails for some weapon, say
     which and what the fallback is. **Enumerate EVERY field the formula
     consumes**, each with its engine default from the `.gd` `export` declaration
     — the gate must cover all of them, not just the obvious ones (burn's PR
     review caught an ungated `damage` field silently modeling 0 DPS instead of
     falling back to unmodeled_effects; commit 25f8ca2).
   - **Delivery modifier**: it changes the weapon's own hit delivery (pierce,
     bounce, extra projectiles...). Explain exactly how the engine applies it and
     what dataset representation would be honest (e.g. multiplies enemies-hit,
     conditional on crit chance).
   - **Non-DPS rider**: passive stat grant / economy / CC / utility. State what
     it grants, when (held? equipped? on-hit?), and how the engine folds it in;
     propose how the dataset should classify it so it stops polluting
     `unmodeled_effects` (classification only — schema design is Phase 2's call).
   - **Unmodelable-static**: state-dependent in a way a static dataset honestly
     cannot capture (e.g. scales with kills this wave). Document the mechanic
     anyway and argue why no number is better than a wrong number.
5. **Flag everything uncertain.** Anything you could not fully verify gets a
   literal `UNVERIFIED:` prefix. Never present inference as fact. If decompiled
   code is ambiguous, show the snippet and say so.

## Hard constraints

- Write exactly ONE file: your assigned dossier path under
  `docs/superpowers/research/` in this worktree. No edits to any other file, no
  commits, no `git` state changes anywhere, nothing written in the main checkout.
- Evidence-only culture: this project has been burned by carried-forward
  citations. Every `path:line` you write must be one you personally opened.
- Speculative math is worse than no math. Follow the burn spec's example:
  model only what preconditions make safe, fall back otherwise.

## Dossier format

```markdown
# <family name> — proc-worklist investigation dossier
Date: 2026-07-05. Game version: 1.1.15.4 (extracted/). Investigator: subagent.

## Keys covered
<key → weapon/tier census table with parameter values>

## Mechanic (evidence)
<per key or shared: how it actually works, every claim cited path:line>

## Verdict
<one of the four classifications (or TENTATIVE with candidates), with proposed
model/preconditions or rationale>

## Precondition verification table (if DPS-modelable)
<weapon/tier → check → pass/fail>

## Open questions / UNVERIFIED items
```

## Return value (your final message)

A summary of at most ~20 lines: keys covered, verdict per key, the proposed
model or classification in one sentence each, and any UNVERIFIED flags. Do NOT
paste the whole dossier back.
