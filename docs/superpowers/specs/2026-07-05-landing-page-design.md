# Landing page (phase 3 of 3: ship it)

Part of a three-phase publish push: PyPI publish (done) → MCP registry
listings (done) → **landing page** (this doc).

## Goal

A focused install/getting-started page at `spudcoach.fyi`, matching the
roadmap's own framing ("the spudcoach.fyi install page") rather than a full
marketing site. Hosted on Netlify, connected to the existing GitHub repo for
auto-deploy on push.

## Scope

One page. No logo/custom mark — typographic only. Sections: hero, "What it
is," "Install," links (GitHub / PyPI / MCP Registry), footer disclaimer. No
blog, no docs section, no testimonials.

## Visual direction (validated via the visual brainstorming companion)

- **Header font:** Bitter (bold/800 weight) — a rustic slab serif with a
  crate-stamp / potato-sack-label feel, chosen over a playful rounded
  option (Fredoka) and a technical monospace option (Space Mono) for the
  headline itself.
- **Body font:** Inter — clean and readable, doesn't compete with Bitter.
- **Code font:** Space Mono, for the `uvx spudcoach` install snippet only.
- **Palette:** Light Taupe/Stone + Deep Umber (chosen over a dark
  warm-potato-brown option and a dark charcoal+rust option — this one reads
  more "docs site," less "game site," which fits the "deterministic, no
  guessing" positioning better than a darker/moodier palette would).
  - Page background: `#e8e2d8`
  - Section divider: `#d3c9b8`
  - Headline / primary text: `#3d2f22`
  - Body / secondary text: `#4a3f34`
  - Muted text (subhead, links row): `#6b5d4d` / `#8a7c6a`
  - Button background: `#4a3527`, button text: `#f4ede2`
  - Code block background: `#dcd2c0`, code text: `#3d2f22`

## Copy (validated, final)

- **Brand name:** "Spud Coach" (not "Brotato Coach") — Brotato is named only
  in the sub-head, not the header itself.
- **Hero headline:** `Spud Coach`
- **Hero sub-head** (line break, not em dash):
  ```
  A deterministic theorycrafter for Brotato.
  Facts and math, not guesses or tier lists.
  ```
- **Install button:** `uvx spudcoach`
- **Links row:** GitHub · PyPI · MCP Registry
- **"What it is" body copy** (rewritten from an earlier AI-slurry draft that
  explained LLM mechanics — this version leads with the concrete user
  benefit instead):
  ```
  Is this weapon actually better at your stats? Is your build strong, or
  did you just get lucky? Spud Coach answers with real numbers pulled
  straight from the game's data — every weapon, item, and stat interaction
  computed exactly, not remembered off a tier list.
  ```
- **"Install" section:**
  - Code block: `uvx spudcoach`
  - Caveat line (says "before use," not "first," to make the sequence
    clear — you run the install command, then build the dataset before the
    tool is actually usable, not build-then-install):
    ```
    You'll need to build your own dataset before use — the game files are
    copyrighted and never distributed. See the README for how.
    ```

## Footer disclaimer

A fan-project disclaimer at the bottom of the page, small/muted text,
distinct from the main content:

```
Spud Coach is an unofficial fan project and is not affiliated with,
endorsed by, or sponsored by Blobfish or any other developer or publisher
of Brotato. Brotato is a trademark of its respective owner(s).
```

Kept deliberately generic rather than naming every studio involved in
Brotato's development (Blobfish, Erabit Studios for mobile ports, Evil
Empire for ongoing development as of late 2025) — that list could change
again, and "Blobfish or any other developer or publisher" covers it without
needing an update if it does.

## File structure

- `site/index.html` — the page (single file, no templating)
- `site/style.css` — all styling (colors/fonts above, plus responsive
  layout — single column, readable on mobile, `max-width` on body text
  matching the mockup's ~640px reading column)
- `netlify.toml` (repo root) — declares `publish = "site"` so Netlify's
  connected-repo build knows where the site lives without manual dashboard
  configuration

## Deployment

Two one-time manual steps (external accounts, not automatable):
1. Link the GitHub repo in the Netlify dashboard (Brendan already has a
   Netlify account) — auto-deploys on every push to `main` once connected,
   matching the "push and it ships" pattern from phases 1-2.
2. In Porkbun's DNS panel, point `spudcoach.fyi` at Netlify — domain is
   already registered and parked there (confirmed live via HTTP fetch on
   2026-07-04, Porkbun's default parking page), no domain purchase needed.
   Either delegate to Netlify's nameservers or add the A/ALIAS + CNAME
   records Netlify's domain-setup screen provides — exact values come from
   Netlify's UI once the site exists, so this happens after the site is
   built and connected, not before.

Once Homepage-in-`pyproject.toml` and `server.json`'s `websiteUrl` both
still point at the GitHub repo as of phase 2 — update both to
`https://spudcoach.fyi` once the domain is live (this was explicitly
deferred to this phase in the phase-2 spec).

## Testing

No application logic — verification is: open `site/index.html` directly in
a browser to confirm it renders correctly (no build step needed for a local
check), then after Netlify is connected, confirm the Netlify-provided
`*.netlify.app` URL serves the page correctly, and finally confirm the
custom domain does too once DNS propagates.

## Out of scope

- Blog/docs section, testimonials, feature-highlight sections beyond "What
  it is" — deliberately a focused install page, not a marketing site.
- Custom logo/mark — typographic only for v1.
- Analytics/tracking on the page itself (interest tracking already covered
  by PyPI/GitHub/registry dashboards, not this page).
