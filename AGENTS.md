# AGENTS.md · ct-literature

> B-tier public-intel skill of the `ct-` library. Systematic literature search (published-evidence base + CSM qualitative subset).

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
- Zero confidential data or information input (B-tier).
- Common files (`scripts/i18n.py`, `scripts/r_libs.py`, `references/language_policy.md`, `references/report_template.md`) are copied from `ct-base` — do not fork them here; sync from ct-base instead.

## Self-improvement

- On repeated failure patterns, record to the workspace `.learnings/` per `ct-base`/self-improving-agent rules.
- Source API changes (OpenAlex filter syntax, Europe PMC schema, S2 429 policy) → update `scripts/` + SKILL.md Data Sources, bump version in CHANGELOG.

## Version

Current: v0.5.2 (B-tier public-intel literature search skill; aligned with SKILL.md).
