# PyPI Publish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `spudcoach` installable via `uvx spudcoach` by publishing it to PyPI through an automated, tokenless GitHub Actions release workflow.

**Architecture:** A single GitHub Actions workflow (`.github/workflows/publish.yml`) triggers when a GitHub Release is published. It runs the existing test suite, builds the sdist+wheel with `uv build`, and publishes via `pypa/gh-action-pypi-publish` using PyPI's OIDC trusted-publishing (no stored API token). The `pypi` GitHub environment and the PyPI-side trusted publisher registration are already configured (external, done by the repo owner on 2026-07-04).

**Tech Stack:** `uv` (build backend: hatchling, already configured), GitHub Actions, `pypa/gh-action-pypi-publish@release/v1`, `astral-sh/setup-uv@v5`.

## Global Constraints

- Python `>=3.11` (from `pyproject.toml`)
- Version for this release: `0.9.0` (not `1.0.0` — deliberately held back in case the release process needs another pass)
- Release trigger: GitHub Release publish (not raw tag push, not manual dispatch)
- Trusted publishing only — never add a PyPI API token/secret to the repo or workflow
- Workflow filename must be exactly `.github/workflows/publish.yml` and environment name exactly `pypi` — these exact strings are what PyPI's trusted publisher registration and the GitHub environment are keyed on; a mismatch breaks OIDC auth with no useful error

---

### Task 1: Bump project version to 0.9.0

**Files:**
- Modify: `pyproject.toml:3` (the `version = "0.2.0"` line)
- Modify: `uv.lock` (regenerated, not hand-edited — it pins the project's own version at the `name = "spudcoach"` package entry, currently `version = "0.2.0"` around line 690)

**Interfaces:**
- Produces: project version string `0.9.0`, consumed by Task 2's build step (`uv build` reads it from `pyproject.toml`) and by the eventual release tag `v0.9.0`.

- [ ] **Step 1: Edit the version field**

In `pyproject.toml`, change:

```toml
version = "0.2.0"
```

to:

```toml
version = "0.9.0"
```

- [ ] **Step 2: Regenerate the lockfile so it matches**

Run: `uv lock`

Expected: exits 0; `uv.lock`'s `spudcoach` package entry now reads `version = "0.9.0"`. Confirm with:

```bash
grep -A1 'name = "spudcoach"' uv.lock
```

Expected output includes `version = "0.9.0"`.

- [ ] **Step 3: Confirm the test suite still passes at the new version**

Run: `uv run pytest`

Expected: same pass/skip counts as before the bump (89 tests: 88 passed, 1 skipped without a built dataset) — a version bump must not change test behavior.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: bump version to 0.9.0 for first PyPI release"
```

---

### Task 2: Add the PyPI publish workflow

**Files:**
- Create: `.github/workflows/publish.yml`

**Interfaces:**
- Consumes: GitHub environment `pypi` (already created on the repo, verified via `gh api repos/BrendanL79/spud-coach/environments`), PyPI trusted publisher registration for project `spudcoach` bound to repo `BrendanL79/spud-coach`, workflow file `.github/workflows/publish.yml`, environment `pypi` (already registered on PyPI's side, external, done 2026-07-04).
- Produces: nothing consumed by later tasks in this plan — this is the terminal deliverable. The workflow itself produces the published `spudcoach` package on PyPI once a Release triggers it (verification happens outside this plan's automated steps — see Task 3).

- [ ] **Step 1: Write the workflow file**

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Install dependencies
        run: uv sync

      - name: Run tests
        run: uv run pytest

      - name: Build package
        run: uv build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
```

- [ ] **Step 2: Validate the YAML is well-formed**

Run:

```bash
python3 -c "import yaml, sys; yaml.safe_load(open('.github/workflows/publish.yml'))" && echo "valid YAML"
```

Expected: prints `valid YAML` with no exception. (If `python3`/`pyyaml` isn't available locally, `uv run python -c "..."` works too since `pyyaml` isn't a project dependency — fall back to visually re-reading the file for indentation errors if neither is available.)

- [ ] **Step 3: Dry-run the build and test steps locally**

Run the same commands the workflow will run, to catch failures before they show up in Actions:

```bash
uv sync
uv run pytest
uv build
```

Expected: all three exit 0; `uv build` creates `dist/spudcoach-0.9.0.tar.gz` and `dist/spudcoach-0.9.0-py3-none-any.whl` (confirm with `ls dist/`).

- [ ] **Step 4: Clean up local build artifacts**

The `dist/` directory from Step 3 is a local-only smoke test artifact, not something to ship in the commit.

```bash
rm -rf dist/
git status
```

Expected: `git status` shows no `dist/` entry (already gitignored, or untracked-and-removed either way — confirm it's gone).

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/publish.yml
git commit -m "ci: add PyPI trusted-publishing release workflow"
```

---

### Task 3: Cut the release (manual, not subagent-executed)

This task is **not** automated as part of plan execution — creating a GitHub Release is a real, public, hard-to-reverse action (it publishes a real package version to PyPI that can't be deleted, only yanked). Whoever executes this plan should stop after Task 2 and hand back to the user for this step, rather than triggering it automatically.

**Manual steps (for the user to run, or explicitly confirm before an agent runs them):**

1. Push the two commits from Tasks 1–2 to `main` (or merge via PR, per your normal workflow).
2. Create a GitHub Release:
   ```bash
   gh release create v0.9.0 --title "v0.9.0" --generate-notes
   ```
3. Watch the workflow run: `gh run watch` (or check the Actions tab).
4. Once green, confirm the package landed on PyPI: `https://pypi.org/project/spudcoach/`.
5. Confirm the end-to-end install works from a clean environment:
   ```bash
   uvx spudcoach --help
   ```

**Rollback note:** if the workflow fails partway (e.g. after tests but before publish), nothing has shipped — just fix and cut a new patch release. If it fails *after* a successful PyPI publish somehow produces a bad artifact, PyPI versions can be yanked (marked "don't install by default") but not deleted or overwritten — a fixed release must ship as a new version number (`0.9.1`).
