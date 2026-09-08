# AGENTS.md · ct-literature

> A-tier public-intel skill of the `ct-` library (A 档 = non-confidential input). Systematic literature search (published-evidence base + CSM qualitative subset).
>
> **Tier (A/B two-tier):** this skill is **A 档 / A-tier** — its input is **non-confidential** (ordinary query terms only). Every data source is a public bibliographic API (OpenAlex / Europe PMC / preprint servers) and the skill processes **zero confidential input**. `network=public-retrieval` is an orthogonal sub-attribute of tier A (it answers "does the skill retrieve public sources?"), **not** a separate tier — ct- now classifies skills on the single axis of input sensitivity (A = non-confidential / B = confidential).

## Scope

- Retrieve published scholarly literature (OpenAlex primary; Europe PMC / Semantic Scholar optional) about a drug / disease / method.
- Normalize multi-source records into one de-duplicated evidence base; surface study-type distribution, yearly trend, and a safety/CSM subset.
- **Out of scope**: trial-registry metadata (→ `ct-registry`), FAERS disproportionality (→ `ct-safety`), full-text PDF download, paywalled content.

## Boundaries (do NOT blur)

- `ct-registry` answers *what trials exist*; `ct-literature` answers *what has been published*. Keep the object distinct — literature never fetches registry phase/status/enrollment; registry never fetches paper abstracts.
- `--safety` literature is qualitative; never feed it into FAERS PRR/ROR/IC. It only qualitatively corroborates `ct-safety`.

## Conventions

- Scripts: stdlib `urllib` for fetch (no hard `requests` dependency in fetch path); `normalize.py` / `report.py` are pure local.
- SAFE PREVIEW default: network runs only with `--run`.
- Zero confidential data or information input (A-tier).
- Common files (`scripts/i18n.py`, `references/language_policy.md`, `references/report_template.md`) are shared across the `ct-` library — do not fork them here; sync from the library instead. (`scripts/r_libs.py` was previously vendored but removed in v0.6.12 — this skill is pure Python and never calls R.)

## Self-improvement

- On repeated failure patterns, record to the workspace `.learnings/` per self-improving-agent rules.
- Source API changes (OpenAlex filter syntax, Europe PMC schema, S2 429 policy) → update `scripts/` + SKILL.md Data Sources, bump version in CHANGELOG.

## Version

Current: v1.0.0 (A-tier public-intel literature search skill; aligned with SKILL.md). See SKILL.md `version:` for the authoritative number.
