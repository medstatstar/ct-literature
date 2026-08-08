---
slug: ct-literature
name: ct-literature
displayName: 临床试验文献检索专家 / Clinical Trial Literature Search
cn_name: 临床试验文献检索专家
version: 0.5.0
invocable: true
summary: 检索公开学术文献（OpenAlex 主源 + Europe PMC/MeSH 生物医学精准 + Semantic Scholar 引用增强），归一化合并去重，产出证据基础与 CSM 定性安全性文献集；B 档公开检索，零保密输入。
license: MIT
description: "Search public scholarly literature and normalize it into one de-duplicated evidence base: OpenAlex (primary, free, citation-rich) + Europe PMC (MEDLINE/MeSH, biomedical precision) + Semantic Scholar (citation ranking, optional). Filter by review type, year range, and a safety/CSM bias mode that surfaces published adverse-event / pharmacovigilance literature. Produces JSON + Markdown. Reads only public publications; zero confidential input, B-tier (ordinary input + public retrieval). / 检索公开学术文献并归一化合并为统一去重证据库：OpenAlex（主源，免费、含引用数）+ Europe PMC（MEDLINE/MeSH，生物医学精准）+ Semantic Scholar（引用排序，可选）。按综述类型、年份区间筛选，并提供安全性/CSM 偏置模式以提取已发表不良事件/药物警戒文献。产出 JSON + Markdown。仅读公开文献，零保密数据输入，B 档（普通输入 + 对外检索）。"
triggers:
  - "systematic literature search"
  - "系统文献检索"
  - "文献证据基础"
  - "已发表安全性文献 / CSM"
  - "cross-database literature search"
  - "跨数据库 文献检索"
  - "Embase Cochrane Web of Science"
  - "多数据库 系统综述"
  - "ct-literature"
required_commands: [python]
metadata:
  openclaw: { emoji: "📚" }
  authors: ["medstatstar", "phoe-zip"]
  tags: [clinical-trial, literature, evidence, systematic-review, csm, openalex, pubmed, public-data]
  homepage: "https://github.com/medstatstar/ct-literature"
permissions:
  scope: "user-space-only"
  network: "optional"
  network_note: "Reads only public bibliographic sources: OpenAlex (api.openalex.org, no key), Europe PMC (ebi.ac.uk, MEDLINE/MeSH, no key), Semantic Scholar (api.semanticscholar.org, no key; rate-limited HTTP 429 -> gracefully skipped). No WAF, no confidential input; ordinary input + public retrieval (B-tier)."
  filesystem: "read-only to its own files; writes report files only to the current working directory"
  data: "no confidential data input; no external transmission of user data"

---

## Language

Pick the README that matches your language:

- **English guide** → [README.md](./README.md)
- **中文指南** → [README_zh-CN.md](./README_zh-CN.md)

This skill responds in the user's input language and auto-switches (runtime scripts embed a locale check; all user-facing prompts switch to Chinese on a `zh-*` locale, English otherwise). The SKILL.md body, `references/*.md`, and `AGENTS.md` are English-only (agent-facing). For walkthroughs and troubleshooting, open the README above.

## Purpose

Retrieve **published scholarly literature** (peer-reviewed papers, systematic reviews, conference abstracts, preprints) about a drug / disease / method, normalize heterogeneous records from multiple public bibliographic sources into one de-duplicated evidence base, and surface the evidence landscape plus a **CSM (cumulative safety monitoring)** qualitative subset. Supports trial-planning background, protocol / CSR introductions, and published-safety literature checks.

## Positioning within the ct- library

The four B-tier public-intel skills are complementary, each answering a different question about the same drug / indication:

| Skill | Answers | Object retrieved | Source family |
|---|---|---|---|
| `ct-registry` | What trials are registered / ongoing / completed? | Trial-registry metadata (phase/status/sponsor/enrollment) | Registry libraries (CT.gov / CDE / ChiCTR / EU CTIS / ISRCTN) |
| `ct-literature` | What evidence has been *published*? | Publications (papers / reviews / abstracts / citations) | Literature libraries (OpenAlex / Europe PMC / Semantic Scholar) |
| `ct-safety` | Is a drug–event over-reported (signal)? | Structured spontaneous reports (FAERS cases) | Adverse-event databases (FAERS / openFDA) |
| `ct-pipeline` | Aggregate the above into a strategic intel brief | Consumes the three JSONs (intel layer) | Public-intel / competitor-monitoring layer |

**ct-registry ↔ ct-literature boundary:** `ct-registry` never fetches paper full-text / abstracts (answers *what trials exist*); `ct-literature` never fetches registry structured metadata (answers *what has been reported in the literature*). They populate different facets of the intel brief: registry → competitive **landscape**; literature → **evidence base**. The `intel` preset chains `registry → safety → literature → intel layer`, each adding a distinct dimension.

**CSM note:** `ct-literature --safety` surfaces *published* safety literature (case reports / PV articles) — **qualitative** evidence that complements but must NOT replace `ct-safety`'s structured FAERS disproportionality (PRR / ROR / IC).

**Not sure which skill?** Use `ct-advisor` (the unified entry point of the ct- public-intel library) to route by intent; for a full competitive-intel picture, `ct-advisor` stitches the three sources locally, or call `ct-pipeline` directly (its `intel` / `surveillance` presets). `ct-pipeline` is no longer the default router (see ct-base/BASE.md §15).

## Data Sources

| Source | Access | Status | Role |
|---|---|---|---|
| OpenAlex | Public REST; free key recommended (100k/day via `.env` auto-load) — keyless capped at 100/day since 2026-02-13 | Required (primary) | Broad coverage + citation counts |
| Europe PMC | Public REST (MEDLINE / PubMed Central), no key, MeSH-indexed | Optional `--with-europepmc` | Biomedical precision + MeSH terms |
| Semantic Scholar | Public Graph API, no key, rate-limited (HTTP 429) | Optional `--with-semantic-scholar` | Citation-aware ranking; degrades gracefully to empty on 429 |

> All three are public bibliographic APIs — no WAF. OpenAlex requires an API key since 2026-02-13: keyless traffic is throttled to 100 credits/day; a free key lifts this to 100k/day. Provide via `--openalex-key` or env `OPENALEX_API_KEY`; ct-literature also keeps the polite-pool `mailto`. Semantic Scholar may return HTTP 429 without a key — ct-literature treats it as optional enrichment and skips it after retries. Semantic Scholar's key requires a manual application-form review (not auto-issued); when no key is configured, this source is skipped outright (no doomed 429 request is sent).

## Features

| Capability | Source | Typical scenario |
|---|---|---|
| Topic / drug / disease search | All | Build the published-evidence base for a compound or indication |
| Review-type filter | All | `systematic-review` / `meta-analysis` / `rct` / `case-report` precision |
| Year-range filter | All | Focus on recent evidence |
| Safety / CSM bias | All | Surface published AE / toxicity / case-report / PV literature |
| Multi-source merge + dedupe | normalize | One unified list, DOI/title de-duplicated, provenance kept |
| Citation ranking | OpenAlex / S2 | Find the most influential works |
| MeSH terms | Europe PMC | Biomedical concept indexing |
| Concepts / Keywords / Funders | OpenAlex | Multi-level topic classification + conflict-of-interest signals |
| PubMed ID + PMC ID | All | Direct links to PubMed / PMC full text |
| Open-access full-text URL | All | Direct PDF download links |
| Complete abstract (not truncated) | All | Full evidence preservation |
| Structured output | — | JSON (merged) + Markdown report + Excel workbook (ct-base `excel_style`) |
| Chained invocation | — | → `ct-pipeline`, → `ct-protocol` / `ct-csr` |
| Resilient fetch (retry + backoff) | All | Exponential backoff on 429/5xx/timeout; honors `Retry-After`; OpenAlex Bearer key via `--openalex-key` / `OPENALEX_API_KEY` / skill `.env` auto-load |
| Safe link rendering | All | `_normalize_link()` sanitises every hyperlink before export |

## Unified work schema

```
{ source, id, title, authors, year, publication_date, publication, journal_iso,
  type, study_type, cited_by_count, url, open_access_url,
  pmid, pmcid, doi,
  abstract_snippet,            # full text, not truncated
  mesh, concepts, keywords, funders,
  language, is_retracted, is_safety,
  volume, issue, page,
  affiliations,                # Europe PMC only
  sources }                    # list of contributing sources
```

## Output

- `openalex.json` / `europepmc.json` / `semantic_scholar.json` — per-source payloads
- `merged.json` — unified, de-duplicated work list (DOI/title dedupe, `sources` provenance)
- `lit_report.md` — summary header + top-works table (with OA download links) + key-detail cards + study-type distribution + yearly trend + safety/CSM subset
- `lit_report.xlsx` — Excel delivery (reuses ct-base `excel_style`); auto-generated on `--run` (`--no-xlsx` to skip). Green theme, 4 sheets: Overview → Literature master → Safety-related, with KPI cards, yearly/source/type charts, `is_safety` amber highlighting, and a field dictionary.
- `merged.html` — self-contained HTML report (inline CSS, offline, print/PDF styles); auto-generated on `--run` (`--no-html` to skip). Same palette as the xlsx.

See `references/sop.md` for the full command catalogue.

## Requirements

- Python 3.10+ (Anaconda `C:\Tools\anaconda3\python.exe` recommended).
- `requests` optional (fetch scripts use stdlib `urllib`); `matplotlib` optional (future trend charts).
- Network: read-only public bibliographic APIs.

## ⚠️ Safety

- Default **SAFE PREVIEW**: scripts only generate / display; network requests run only with explicit `--run`.
- Reads **public publications ONLY**, zero confidential input (B-tier).
- `--safety` literature is **qualitative** — never feed it into FAERS disproportionality; it only corroborates `ct-safety` qualitatively.
- Output is for reference / background only, not a regulatory submission.

## Implementation

```bash
# Primary: OpenAlex only (no key)
python scripts/ct_literature.py --topic "osimertinib" --review-type systematic-review --year-from 2018 --safety --run --out-dir ./out

# Add Europe PMC (MEDLINE/MeSH) + Semantic Scholar (citation ranking; may 429 -> skipped)
python scripts/ct_literature.py --topic "osimertinib" --with-europepmc --with-semantic-scholar --run --out-dir ./out
```

One-shot orchestration (OpenAlex + optional sources → merge → report):

```bash
python scripts/ct_literature.py --topic "osimertinib" --review-type systematic-review \
    --year-from 2018 --safety --with-europepmc --run --out-dir ./out
```

### OpenAlex API key (recommended since 2026-02-13)

OpenAlex requires an API key for production-scale use; keyless traffic is capped at 100 credits/day. A free key lifts this to 100k/day. **Recommended (zero-friction):** drop the key into the skill's `.env` (copy from `.env.example`) — no extra flag needed:

```bash
cp .env.example .env        # edit .env -> OPENALEX_API_KEY=your_key
python scripts/ct_literature.py --topic "osimertinib" --safety --run --out-dir ./out
```

`http_utils.load_openalex_key()` auto-resolves the key at startup: **env `OPENALEX_API_KEY` → skill-root `.env` → `scripts/.env`** (key value is never printed). Explicit provision also works (`--openalex-key` / `export`). Application steps, quota, troubleshooting → `references/openalex_key.md`.

## Errors

| Error | Cause | Fix |
|---|---|---|
| `urllib.error.URLError` / timeout (after retries) | No network / proxy / outage | Auto-retried with exponential backoff (4 attempts, honors `Retry-After`); if still failing, confirm api.openalex.org reachable; configure proxy |
| Semantic Scholar HTTP 429 | No-key rate limit | Expected — source is skipped; rely on OpenAlex + Europe PMC |
| OpenAlex HTTP 401 / persistent 429 | Invalid key / daily quota exhausted | Re-copy key from settings/api; confirm `.env` loaded (see references/openalex_key.md) |
| Empty results | Topic too narrow / wrong spelling | Broaden topic; drop `--review-type` / year filter |
| DOI dedupe merged too aggressively | Two papers share a DOI typo | Rare; inspect `merged.json` and re-run a single source if needed |

## Pipeline

- `ct-registry` → `ct-literature`: landscape hypothesis (from registry) seeds the literature search topic.
- `ct-literature` → `ct-pipeline`: literature works feed the `intel` preset's evidence dimension.
- `ct-literature` → `ct-protocol` / `ct-csr`: published evidence backs the introduction / background.
- `ct-literature --safety` → `ct-safety`: published safety literature qualitatively corroborates FAERS signals (distinct data type).

## Cross-Database Search Mode (Embase / Cochrane / Web of Science + preprint Tier P)

`ct-literature` is OpenAlex-primary by design, but for formal systematic reviews you can invoke a **cross-database** layer adapted from `multi-database-literature-collector` (AIPOCH, MIT — migrated 2026-08-04):

- **Database selection rules** — pick Embase (broad biomedical), Cochrane (RCT/intervention), Web of Science (citation), preprints (Tier P) per question type. See `references/multi-db-search.md`.
- **Search-strategy construction** — controlled vocabulary (MeSH/Emtree) + free text + Boolean; per-database syntax adaptation.
- **Preprint labelling** — tag preprint works as **Tier P** so the evidence base separates peer-reviewed from not-yet-peer-reviewed.
- **Normalization** — still collapses to the unified schema and de-dupes across all sources.

> This mode is a *planning + normalization* extension; the live fetch currently runs OpenAlex / Europe PMC / Semantic Scholar. Cross-database source lists inform the search strategy and screening-ready export, not a separate live crawler.

## Natural language dialogue

When the user triggers ct-literature via natural language (not CLI), follow the dialogue flow defined in `references/search_menu.md`:

1. Parse topic / review_type / year / safety from user utterance
2. If ≥2 params recognized → skip to preview
3. If params missing → ask max 2 rounds, then use defaults
4. Show preview table → wait for confirmation
5. Execute `--run` → present result summary with follow-up options

See `references/search_menu.md` for the full menu templates, follow-up strategy, preset recommendations, and dialogue examples. See `references/units.md` for the atomic-task unit index.
