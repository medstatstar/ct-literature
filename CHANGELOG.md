# Changelog · ct-literature

All notable changes to this skill are documented here. Versioning follows the
ct- library convention (B-tier public-intel skill, semver-ish).

## v0.5.0 — 2026-08-08

### Initial public release (init version)
- First public release of ct-literature; consolidates the v0.3.x internal
  hardening aligned with ct-base v1.1.18 (i18n locale-aware strings, README
  rebuilt on the ct-advisor skeleton, `invocable: true` frontmatter, dual-author
  footer `medstatstar, phoe-zip`, packaging exclusions in `.clawhubignore`).
- The full compliance changelog carried into this release is recorded under
  v0.3.12 below.

## v0.3.12 — 2026-08-08

### Compliance & documentation (aligned with ct-base v1.1.18)
- **SKILL.md**: added `invocable: true` to frontmatter (task-entry skill, per BASE.md §16.5).
- **README (EN + ZH)**: added two dialogue-flow examples covering the two branches
  from `references/search_menu.md` — Complex (popup confirmation menu, §4.1–§4.3)
  and Vague (grill-me style clarifying questions, §6).
- Bumped version v0.3.11 → v0.3.12 across SKILL.md / AGENTS.md / both READMEs.

### Prior hardening (carried into this release)
- **i18n**: moved all hardcoded Chinese `print`/docstrings in `scripts/` to
  `i18n.py` en+zh key pairs (locale-aware) — clears BASE.md §16.3.
- **README (EN + ZH)**: restructured to the ct-advisor skeleton
  (switch line → logo → intro → Who This Is For → 1.How to Use → 2.Scenarios →
  3.FAQ → 4.Security & Privacy → 5.Advanced); removed the "Future Release Plans"
  section to stay consistent with BASE.md §13.6.
- **SKILL.md**: English-only body; frontmatter re-ordered to the ct-base §3 schema.
- **AGENTS.md**: version aligned.
- **references/**: sop.md / openalex_key.md / search_menu.md / multi-db-search.md
  fully English-only.
- **Authors**: README footer version line set to `medstatstar, phoe-zip`
  (synced to the ct-base template).

### Packaging
- `.clawhubignore`: now excludes `tests/results/`, `tests/scenario10_run/`,
  `tests/scenario10b_run/`, `tests/__pycache__/`, plus global `__pycache__/` / `*.pyc`.
- `.gitignore`: already excludes `__pycache__/` / `*.pyc` (no change needed).

## v0.3.11
- Baseline B-tier public-intel literature search skill: OpenAlex (primary) +
  Europe PMC (MEDLINE/MeSH) + Semantic Scholar (citation ranking, optional),
  normalized merge + dedupe, CSM qualitative safety subset, Markdown + Excel + HTML output.
