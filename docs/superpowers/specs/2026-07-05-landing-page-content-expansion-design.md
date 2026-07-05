# Landing page content expansion (Connect-to-Claude + tool list)

## Goal

The original landing page spec (`2026-07-05-landing-page-design.md`) deliberately scoped the
page down to a focused install page: hero, "What it is," "Install," links, footer disclaimer —
explicitly excluding "feature-highlight sections beyond 'What it is'." This doc reverses that
scope decision: bring over most of what's on the [PyPI project page](https://pypi.org/project/spudcoach/),
specifically the parts PyPI visitors would want that the current page doesn't have — how to wire
the server into Claude, and what it can actually do once connected.

Out of scope (deliberately not ported): dataset stats (202 weapons/197 items/50 characters/15
sets), the prose features list, and architecture internals (`tres.py`/`builders/`/`calc.py`
breakdown) — these read as marketing/dev-manual filler for a page whose job is "convince someone
to install, then get them connected."

## New sections

Two new `<section class="section">` blocks are added to `site/index.html`, inserted **after**
the existing "Install" section and **before** the footer. Both reuse existing CSS classes
(`.section`, `.install-code`, `.caveat`) — no new colors/fonts.

### Section 3: "Connect it to Claude"

Two sub-parts under one `<h2>`, each with its own `<h3>` (new element on this page — style per
CSS section below).

**Claude Code:**
```html
<h3>Claude Code</h3>
<pre class="install-code"><code>claude mcp add brotato-coach -- uv run --directory /path/to/spud-coach python -m brotato_coach.server</code></pre>
```
(Sourced verbatim from `README.md` line 84 — the direct-registration form, not the plugin
manifest, since this page has no plugin packaging context.)

**Claude Desktop:**
```html
<h3>Claude Desktop</h3>
<pre class="install-code"><code>{
  "mcpServers": {
    "spud-coach": {
      "command": "uvx",
      "args": ["spudcoach", "--data", "/path/to/brotato.json"]
    }
  }
}</code></pre>
<p class="caveat">Add this to <code>claude_desktop_config.json</code>, then fully restart Claude Desktop. Hitting a "Git executable not found" error on Windows? See the <a href="https://github.com/BrendanL79/spud-coach#windows-git-executable-not-found-or-uvx-not-found">README</a>.</p>
```
This is a simpler config than the README's `--from git+https://...` / local-checkout variants
(those exist for auto-update/offline tradeoffs the README covers in depth) — it matches the
page's own `uvx spudcoach` framing from the Install section above it. The README link is
scoped to the specific troubleshooting anchor, not the general README, since that's the one
piece of Desktop-specific friction worth flagging here.

### Section 4: "What you get"

One `<h2>What you get</h2>`, sub-headed by four `<h3>` category labels, each followed by a
`<ul>` of tool one-liners. Tool names in `<code>`. Content sourced from `brotato_coach/server.py`
docstrings (lines 40-268), not the PyPI page's partial 9-of-16 list.

```html
<h3>Data lookups</h3>
<ul>
  <li><code>get_weapon</code> / <code>get_item</code> / <code>get_character</code> — full records: stats, effects, kit</li>
  <li><code>get_weapon_class_set</code> — set bonuses for a weapon class</li>
  <li><code>list_weapons</code> / <code>list_items</code> — filtered summaries</li>
  <li><code>get_filter_options</code> — valid filter values (tags, archetypes, tiers, classes)</li>
</ul>

<h3>DPS &amp; comparison</h3>
<ul>
  <li><code>weapon_dps</code> — one weapon's realized DPS at your stats</li>
  <li><code>compare_weapons</code> — rank several weapons by DPS</li>
  <li><code>compare_merge_paths</code> — which tier-merge order wins, and where it flips</li>
</ul>

<h3>Build evaluation</h3>
<ul>
  <li><code>evaluate_item_for_build</code> — live / wasted / harmful verdict for an item</li>
  <li><code>loadout_set_bonuses</code> — set-bonus progress across a whole loadout</li>
  <li><code>explain_stat</code> — a stat's real mechanics (caps, dead-weight ranges)</li>
  <li><code>stat_display_value</code> — raw stat &rarr; what the game displays</li>
</ul>

<h3>Run analysis</h3>
<ul>
  <li><code>evaluate_run</code> — post-mortem a whole run.json in one call</li>
  <li><code>check_dataset_version</code> — which game version the facts are from</li>
</ul>
```

16 tools total, matching the 16 `@mcp.tool()` decorators in `server.py`.

## CSS additions

New rules in `site/style.css` (nothing existing changes):

```css
.section h3 {
  font-family: 'Inter', sans-serif;
  font-weight: 600;
  font-size: 1rem;
  color: var(--heading);
  margin: 20px 0 8px;
}

.section h3:first-of-type {
  margin-top: 0;
}

.section ul {
  margin: 0 0 0 18px;
  padding: 0;
  font-size: 0.95rem;
}

.section li {
  margin-bottom: 6px;
}

.section li code {
  background: var(--code-bg);
  padding: 1px 5px;
  border-radius: 3px;
  font-family: 'Space Mono', monospace;
  font-size: 0.85rem;
  color: var(--heading);
}
```

`h3` uses Inter (not Bitter) — it's a sub-label within a section, not a new heading tier that
should compete visually with the Bitter `h2`s.

## Final page structure

```
Hero (unchanged)
  h1 Spud Coach
  subhead
  install-cta
  links nav

main
  Section: What it is (unchanged)
  Section: Install (unchanged)
  Section: Connect it to Claude (NEW)
    h3 Claude Code + code block
    h3 Claude Desktop + code block + caveat
  Section: What you get (NEW)
    h3 Data lookups + ul
    h3 DPS & comparison + ul
    h3 Build evaluation + ul
    h3 Run analysis + ul

Footer disclaimer (unchanged)
```

## Testing

Same approach as the original landing page build — no application logic, so verification is
structural + visual:
- `grep -c` checks that each new tool name and the two code snippets appear in `index.html`
  exactly as specified (catches paraphrasing/drift, same pattern as the original plan's Step 4)
- Open `site/index.html` directly in a browser to visually confirm the new sections render
  correctly and don't break the existing layout/responsiveness (768px/480px breakpoints)

## Out of scope

- Dataset stats, prose features list, architecture internals (see Goal section)
- Anchor/jump navigation for the now-longer page — four sections is still short enough for a
  single scroll
- Any change to the existing Hero, "What it is," "Install," or footer content/copy
- Any change to `netlify.toml`, deployment, or DNS (unaffected by a content-only change)
