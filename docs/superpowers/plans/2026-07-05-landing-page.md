# Landing Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `spudcoach.fyi` install/getting-started page as static HTML/CSS in `site/`, wire it up for Netlify's connected-repo auto-deploy, and hand off the manual account-linking steps needed to actually put it live.

**Architecture:** A single static page (`site/index.html` + `site/style.css`, no build step, no JS) with a `netlify.toml` at the repo root telling Netlify's GitHub integration where to find it. No server-side logic, no templating — this is the smallest thing that can be "deployed" by just serving files as-is.

**Tech Stack:** Plain HTML5 + CSS3. Google Fonts (Bitter, Inter, Space Mono) loaded via `<link>` tags, no local font files. Netlify for hosting, connected directly to the GitHub repo (no GitHub Actions workflow needed for this one — Netlify's own integration handles the build/deploy).

## Global Constraints

- Brand name in the page is **"Spud Coach"** (not "Brotato Coach") — Brotato is named only in the sub-head text, never in the header/title itself
- Palette (exact hex values, from the spec): background `#e8e2d8`, divider `#d3c9b8`, heading text `#3d2f22`, body text `#4a3f34`, muted text `#6b5d4d`, muted-light text `#8a7c6a`, button background `#4a3527`, button text `#f4ede2`, code background `#dcd2c0`
- Fonts: **Bitter** (700/800 weight) for all headings, **Inter** for body/UI text, **Space Mono** for code/install snippets only
- Hero sub-head uses a line break (`<br>`), not an em dash
- The dataset caveat under Install says **"before use"**, not "first" (clarifies you run the install command, then build the dataset — not the other way around)
- The "What it is" copy is exact, already validated — do not paraphrase or regenerate it
- Footer disclaimer text is exact, already validated — do not paraphrase or regenerate it
- No logo/custom mark, no blog/docs/testimonials sections, no analytics/tracking script, no JavaScript at all
- Out of scope for this plan: the pyproject.toml `Homepage` field and `server.json`'s `websiteUrl` still point at the GitHub repo — updating those to `https://spudcoach.fyi` happens only after the domain is confirmed live (Task 3), not before

---

### Task 1: Build the page

**Files:**
- Create: `site/index.html`
- Create: `site/style.css`

**Interfaces:**
- Produces: a self-contained static page. `index.html` references `style.css` via a relative `<link>` (`href="style.css"`) — both files must live in the same `site/` directory for that reference to resolve.

- [ ] **Step 1: Write the HTML**

Create `site/index.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Spud Coach — a deterministic theorycrafter for Brotato</title>
  <meta name="description" content="Spud Coach is a deterministic theorycrafter for Brotato, delivered as an MCP server. Facts and math, not guesses or tier lists.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Bitter:wght@700;800&family=Inter:wght@400;500;600&family=Space+Mono&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header class="hero">
    <h1>Spud Coach</h1>
    <p class="subhead">
      A deterministic theorycrafter for Brotato.<br>
      Facts and math, not guesses or tier lists.
    </p>
    <div class="install-cta"><code>uvx spudcoach</code></div>
    <nav class="links">
      <a href="https://github.com/BrendanL79/spud-coach">GitHub</a>
      <span aria-hidden="true"> &middot; </span>
      <a href="https://pypi.org/project/spudcoach/">PyPI</a>
      <span aria-hidden="true"> &middot; </span>
      <a href="https://registry.modelcontextprotocol.io/v0/servers?search=spudcoach">MCP Registry</a>
    </nav>
  </header>

  <main>
    <section class="section">
      <h2>What it is</h2>
      <p>Is this weapon actually better at your stats? Is your build strong, or did you just get lucky? Spud Coach answers with real numbers pulled straight from the game's data — every weapon, item, and stat interaction computed exactly, not remembered off a tier list.</p>
    </section>

    <section class="section">
      <h2>Install</h2>
      <pre class="install-code"><code>uvx spudcoach</code></pre>
      <p class="caveat">You'll need to build your own dataset before use — the game files are copyrighted and never distributed. See the <a href="https://github.com/BrendanL79/spud-coach#building-the-dataset">README</a> for how.</p>
    </section>
  </main>

  <footer class="disclaimer">
    <p>Spud Coach is an unofficial fan project and is not affiliated with, endorsed by, or sponsored by Blobfish or any other developer or publisher of Brotato. Brotato is a trademark of its respective owner(s).</p>
  </footer>
</body>
</html>
```

Note on the MCP Registry link: there's no confirmed stable per-server browse page on `registry.modelcontextprotocol.io` (it's an API-first registry, still in preview) — the link goes to the actual API query that returns this server's real listing (`?search=spudcoach`), which is verifiably correct today, rather than a guessed pretty-UI URL that might not exist.

- [ ] **Step 2: Write the CSS**

Create `site/style.css`:

```css
:root {
  --bg: #e8e2d8;
  --divider: #d3c9b8;
  --heading: #3d2f22;
  --body-text: #4a3f34;
  --muted: #6b5d4d;
  --muted-light: #8a7c6a;
  --button-bg: #4a3527;
  --button-text: #f4ede2;
  --code-bg: #dcd2c0;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: var(--bg);
  color: var(--body-text);
  font-family: 'Inter', sans-serif;
  line-height: 1.6;
}

.hero {
  text-align: center;
  padding: 64px 24px 48px;
  border-bottom: 1px solid var(--divider);
}

.hero h1 {
  font-family: 'Bitter', serif;
  font-weight: 800;
  font-size: 3rem;
  color: var(--heading);
  margin: 0;
}

.subhead {
  color: var(--muted);
  font-size: 1.15rem;
  margin: 14px 0 28px;
}

.install-cta {
  display: inline-block;
  background: var(--button-bg);
  color: var(--button-text);
  font-family: 'Inter', sans-serif;
  font-weight: 600;
  font-size: 1.05rem;
  padding: 14px 28px;
  border-radius: 6px;
}

.install-cta code {
  font-family: 'Space Mono', monospace;
  background: none;
  color: inherit;
}

.links {
  margin-top: 14px;
  color: var(--muted-light);
  font-size: 0.85rem;
}

.links a {
  color: var(--muted-light);
  text-decoration: none;
}

.links a:hover {
  text-decoration: underline;
}

main {
  max-width: 640px;
  margin: 0 auto;
  padding: 40px 24px;
}

.section {
  margin-bottom: 32px;
}

.section h2 {
  font-family: 'Bitter', serif;
  font-weight: 700;
  font-size: 1.3rem;
  color: var(--heading);
  margin-bottom: 12px;
}

.install-code {
  background: var(--code-bg);
  border-radius: 6px;
  padding: 16px 20px;
  font-family: 'Space Mono', monospace;
  color: var(--heading);
  font-size: 0.95rem;
  overflow-x: auto;
  margin: 0;
}

.caveat {
  color: var(--muted);
  font-size: 0.9rem;
  margin-top: 10px;
}

.disclaimer {
  max-width: 640px;
  margin: 0 auto;
  padding: 24px 24px 48px;
  color: var(--muted-light);
  font-size: 0.8rem;
  text-align: center;
}

@media (max-width: 480px) {
  .hero h1 {
    font-size: 2.2rem;
  }
  .hero {
    padding: 48px 16px 32px;
  }
}
```

- [ ] **Step 3: Validate the HTML is well-formed**

Run:

```bash
uvx --with html5validator html5validator --root site --show-warnings 2>&1 || echo "html5validator unavailable, falling back to structural check"
```

If `html5validator` isn't available in your environment, fall back to a structural check instead:

```bash
grep -c "<h1>Spud Coach</h1>" site/index.html
grep -c "uvx spudcoach" site/index.html
grep -c 'href="style.css"' site/index.html
```

Expected: each `grep -c` prints a count ≥ 1 (the h1 count should be exactly 1; `uvx spudcoach` appears twice — once in the hero CTA, once in the Install code block).

- [ ] **Step 4: Confirm every required copy/constraint element is present**

Run:

```bash
grep -c "Blobfish" site/index.html
grep -c "before use" site/index.html
grep -c "did you just get lucky" site/index.html
grep -c "font-family: 'Bitter'" site/style.css
grep -c "#e8e2d8" site/style.css
```

Expected: each prints a count ≥ 1 — confirms the disclaimer, the "before use" caveat wording, the validated "What it is" copy, the Bitter heading font, and the taupe background color are all actually present (not paraphrased or dropped).

- [ ] **Step 5: Note the visual-verification gap**

There is no browser tool available to this task's implementer, so rendering can only be checked structurally (Steps 3-4), not visually. In your report, explicitly state that a human should open `site/index.html` directly in a browser to confirm the actual visual rendering before this ships — do not claim the page "looks correct" without having seen it rendered.

- [ ] **Step 6: Commit**

```bash
git add site/index.html site/style.css
git commit -m "feat: add spudcoach.fyi landing page"
```

---

### Task 2: Add the Netlify config

**Files:**
- Create: `netlify.toml` (repo root)

**Interfaces:**
- Consumes: the `site/` directory from Task 1 (must exist for `publish = "site"` to point somewhere real).

- [ ] **Step 1: Write the config**

Create `netlify.toml` at the repo root:

```toml
[build]
  publish = "site"
```

- [ ] **Step 2: Confirm the referenced directory actually exists**

Run:

```bash
ls site/index.html site/style.css
```

Expected: both file paths print with no "No such file or directory" error — confirms `netlify.toml`'s `publish = "site"` points at a directory that's actually populated.

- [ ] **Step 3: Validate the TOML is well-formed**

Run:

```bash
uvx --with tomli python -c "import tomli; print(tomli.load(open('netlify.toml', 'rb')))"
```

Expected: prints `{'build': {'publish': 'site'}}` with no exception.

- [ ] **Step 4: Commit**

```bash
git add netlify.toml
git commit -m "ci: add netlify.toml for connected-repo deploys"
```

---

### Task 3: Connect Netlify, point DNS, and update the URLs (manual, not subagent-executed)

This task is **not** automated as part of plan execution — it requires interactive access to the Netlify dashboard and the Porkbun DNS panel (external accounts), which no subagent has credentials for. Whoever executes this plan should stop after Task 2 and hand back to the user for this step.

**Manual steps (for the user to run):**

1. Push the commits from Tasks 1-2 to `main`.
2. In the Netlify dashboard: "Add new site" → "Import an existing project" → connect the `BrendanL79/spud-coach` GitHub repo. Netlify should auto-detect `netlify.toml`'s `publish = "site"` — no build command needed since there's no build step.
3. Once the site deploys, Netlify assigns a `*.netlify.app` URL. Open it and confirm the page renders as expected (this is the first real visual check — recommend doing this before touching DNS).
4. In the Netlify site's "Domain settings," add `spudcoach.fyi` as a custom domain. Netlify's UI will show either nameservers to delegate to, or specific A/ALIAS + CNAME record values to add.
5. In Porkbun's DNS panel for `spudcoach.fyi`, enter whichever option Netlify's UI showed in Step 4.
6. DNS propagation can take anywhere from minutes to ~24 hours. Once `https://spudcoach.fyi` serves the page (not Porkbun's parking page), the domain is live.

**Once the domain is confirmed live**, a follow-up commit (small, can be done by an agent at that point — it's a one-file text edit, not an account/DNS action) updates the one reference still pointing at the GitHub repo instead of the new domain:
- `server.json`: change `"websiteUrl": "https://github.com/BrendanL79/spud-coach"` to `"websiteUrl": "https://spudcoach.fyi"`. This change will only reach the official registry the next time a release is cut (per the phase-2 workflow), so it doesn't need an immediate release just for this, but don't forget it's pending next time a release happens for any other reason.
- `pyproject.toml`'s `Homepage` field already reads `https://spudcoach.fyi` (set before phase 1 started) — nothing to change there.

**Rollback note:** none of this is destructive — worst case, Netlify's custom-domain setup can be removed and DNS reverted in Porkbun without affecting the GitHub repo, PyPI package, or MCP registry listing, which are all independent of this phase.
