---
slug: ct-literature
name: ct-literature
displayName: 临床试验文献检索专家 / Clinical Trial Literature Search
cn_name: 临床试验文献检索专家
version: 0.6.11
invocable: true
summary: 检索公开学术文献（OpenAlex 主源 + Europe PMC/MeSH 生物医学精准[默认开启] + Semantic Scholar 引用增强 + bioRxiv/medRxiv 预印本 + arXiv 方法学广度），归一化合并去重，产出证据基础与 CSM 定性安全性文献集；B 档公开检索，零保密输入。
license: MIT
description: "检索公开学术文献并归一化合并为统一去重证据库：OpenAlex（主源，免费、含引用数）+ Europe PMC（MEDLINE/MeSH，生物医学精准）+ Semantic Scholar（引用排序，可选）。按综述类型、年份区间筛选，并提供安全性/CSM 偏置模式以提取已发表不良事件/药物警戒文献。产出 JSON + Markdown。仅读公开文献，零保密数据输入，B 档（普通输入 + 对外检索）。含引文标识实时验证与证据溯源日志（反幻觉，ct-base §17.1）。 / Search public scholarly literature and normalize it into one de-duplicated evidence base: OpenAlex (primary, free, citation-rich) + Europe PMC (MEDLINE/MeSH, biomedical precision) + Semantic Scholar (citation ranking, optional). Filter by review type, year range, and a safety/CSM bias mode that surfaces published adverse-event / pharmacovigilance literature. Produces JSON + Markdown. Reads only public publications; zero confidential input, B-tier (ordinary input + public retrieval). Includes citation-identifier verification and a provenance evidence log (anti-hallucination, ct-base §17.1)."
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
  network_note: "Reads only public bibliographic sources: OpenAlex (api.openalex.org, no key), Europe PMC (ebi.ac.uk, MEDLINE/MeSH, no key; also indexes bioRxiv/medRxiv preprints via SRC:PPR), Semantic Scholar (api.semanticscholar.org, no key; rate-limited HTTP 429 -> gracefully skipped), arXiv (export.arxiv.org/api/query, no key). Europe PMC is ON by default (--no-with-europepmc to disable); bioRxiv/medRxiv/arXiv are opt-in via --with-biorxiv / --with-medrxiv / --with-arxiv. No WAF, no confidential input; ordinary input + public retrieval (B-tier)."
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
| Europe PMC | Public REST (MEDLINE / PubMed Central), no key, MeSH-indexed | **Default ON** (`--no-with-europepmc` to disable) | Biomedical precision + MeSH terms |
| Semantic Scholar | Public Graph API, no key, rate-limited (HTTP 429) | Optional `--with-semantic-scholar` | Citation-aware ranking; degrades gracefully to empty on 429 |
| bioRxiv | Via Europe PMC `SRC:PPR` + `publisher:bioRxiv` (no standalone keyword API) | Optional `--with-biorxiv` | Biomedical preprints (Tier P) |
| medRxiv | Via Europe PMC `SRC:PPR` + `publisher:medRxiv` | Optional `--with-medrxiv` | Medical/clinical preprints (Tier P) |
| arXiv | Public Atom API (`export.arxiv.org/api/query`), no key | Optional `--with-arxiv` | Physics/CS/ML methodology breadth (opt-in supplementary) |
| PROSPERO | Public REST (CRD York, systematic-review register), **auth header undocumented** | Optional `--with-prospero` (key-gated, **reserved source**) | Duplication-avoidance / protocol discovery — *is a review on this topic already registered?* (review/protocol granularity) |

> All are public bibliographic APIs — no WAF. OpenAlex requires an API key since 2026-02-13: keyless traffic is throttled to 100 credits/day; a free key lifts this to 100k/day. Provide via `--openalex-key` or env `OPENALEX_API_KEY`; ct-literature also keeps the polite-pool `mailto`. Europe PMC is **on by default** (zero key, high value) — disable with `--no-with-europepmc`. bioRxiv / medRxiv have no free keyword-search API of their own; both are indexed by Europe PMC's preprint corpus, so ct-literature pulls them through `SRC:PPR` filtered by publisher and labels them as distinct `bioRxiv` / `medRxiv` provenance. Semantic Scholar may return HTTP 429 without a key — ct-literature treats it as optional enrichment and skips it after retries; its key requires a manual application-form review (not auto-issued), so when no key is configured this source is skipped outright. arXiv is keyless but mostly methodology breadth for clinical questions — kept opt-in.

> **PROSPERO is a reserved source (2026-08-12).** Its public REST API now requires an auth header that is not documented anywhere; every unauthenticated probe returns `{"status":"error","errormessage":"Error code: header value undefined"}`. `--with-prospero` is kept as a dormant interface: without a token it degrades to a graceful no-op skip (returns `None`, no file written — exactly like Semantic Scholar's no-key behaviour) and is **not** claimed functional. Supply `--prospero-token` (+ `--prospero-header` if the default `PROSPERO-ACCESS-TOKEN` is wrong) to exercise it; the response parser is schema-tolerant (JSON + XML) but must be re-validated against a real 200 before the feature is declared done. No application for an API token is planned — the interface is retained for future enabling.

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
| Formatted citations + BibTeX/RIS | All | `--citation-style` (apa/nature/vancouver/ieee/gb7714, default apa) + `--export-bib` (default on) → `references.bib` / `references.ris` / `references_<style>.md` |
| PRISMA screening funnel | All | `--prisma` (default on) deterministic title/abstract rule screen (reuses `SAFETY_LEXICON` / `review_type`, no LLM) → `.merged.json` `prisma` block + inline SVG funnel in `lit_report.html` |
| Relevance scoring | All | `--rank relevance` + optional `--keywords` → each work gets `relevance_score` (0–1, title 0.6 + abstract 0.4); report adds a Relevance column |
| Obsidian / 文献管理集成 | All | `--obsidian` → 每篇文献一篇 Obsidian 兼容 Markdown 笔记（含 `[[笔记名\|作者 年份]]` 内部链接 + 基于共享概念的「相关文献」交叉链接）+ `Literature MOC.md` 索引；`--zotero` → 导出 `zotero.csv` / `zotero.ris`（Zotero 可导入） |
| **P0 · Citation verification** | All | Identifier reality check (anti-hallucination, ct-base §17.1). Scope via `--verify {all\|top\|none}` (default `all`): `all` verifies every merged work (concurrent with fetch, "verify one as it lands"); `top` verifies only the top-N by rank (`--verify-top-n`, default 15) and marks the rest `unverified_sampled`; `none` skips verification. **Source-aware skip**: a work returned by OpenAlex / Europe PMC already carries a real id at that source, so the redundant same-source re-resolution is skipped and trusted by provenance (no network call) — DOI is always cross-checked via `doi.org`. **Title/author consistency depth (v0.6.11)**: once an identifier resolves to a live resource, its canonical metadata is fetched (Crossref for DOI — bot-friendly even when the publisher bot-blocks `doi.org`; Europe PMC for PMID; OpenAlex for OpenAlex id) and compared to the work's title + first-author surname. A resolved-but-different paper is flagged `mismatch` (not `verified`); a `bot_blocked` DOI whose Crossref metadata matches is upgraded to `verified`. Metadata-fetch failure degrades to "verified, consistency unchecked" (never invents a mismatch). `--no-consistency` skips this layer. Each work is tagged `citation_verified` / `citation_verify_status` (verified / bot_blocked / mismatch / unresolved / no_identifier / suspicious / unverified_sampled) / `citation_verify_note` / `citation_consistency` / `citation_title_ratio`; a malformed DOI is flagged `suspicious`. Legacy alias `--no-verify-citations` = `--verify none`. |
| **P0 · Evidence provenance log** | All | Every run emits `evidence_log.json` + `evidence_log.md` (and an Evidence Log sheet in the workbook + an Evidence & Verification block in the HTML): query → source → hit count → retrieved_at → verification rate, fully traceable. |
| **P1 · PROSPERO registry** | Review register | `--with-prospero` (opt-in, key-gated, **reserved source**) → systematic-review registration / protocol discovery. Requires an API token (`--prospero-token` / env `PROSPERO_API_TOKEN`); the public REST auth header is undocumented so it degrades to a no-op skip until a working token + header is supplied. Never claimed functional. Retained as a dormant interface — no token application planned. |

## Unified work schema

```
{ source, id, title, authors, year, publication_date, publication, journal_iso,
  type, study_type, cited_by_count, url, open_access_url,
  pmid, pmcid, doi,
  abstract_snippet,            # full text, not truncated
  mesh, concepts, keywords, funders,
  language, is_retracted, is_safety, is_preprint,
  volume, issue, page,
  affiliations,                # Europe PMC only
  sources }                    # list of contributing sources
```

## Output

- `openalex.json` / `europepmc.json` / `semantic_scholar.json` / `biorxiv.json` / `medrxiv.json` / `arxiv.json` — per-source payloads (only those enabled)
- `lit_report.xlsx` — Excel delivery (reuses ct-base `excel_style`); auto-generated on `--run` (`--no-xlsx` to skip). Green theme, 4 sheets: Overview → Literature master → Safety-related, with KPI cards, yearly/source/type charts, `is_safety` amber highlighting, and a field dictionary.
- `lit_report.html` — self-contained HTML report (inline CSS, offline, print/PDF styles); auto-generated on `--run` (`--no-html` to skip). Same palette as the xlsx. Includes an inline-SVG **PRISMA funnel** when `--prisma` is on.
- `references.bib` / `references.ris` / `references_<style>.md` — formatted citations (style from `--citation-style`) + BibTeX/RIS exports; auto-generated on `--run` unless `--no-export-bib`. See `references/citation_styles.md`.
- `obsidian/` (with `--obsidian`) — `<论文标题>.md` 每篇文献一篇（YAML frontmatter + 摘要 + 来源链接 + `[[Literature MOC]]` 回链 + 相关文献 `[[...]]` 交叉链接）+ `Literature MOC.md` 索引笔记。将整个 `obsidian/` 文件夹作为 Obsidian vault 打开即可图谱化浏览文献网络。
- `zotero.csv` / `zotero.ris` (with `--zotero`) — Zotero 可导入格式：CSV 列名对齐 Zotero 导入约定（多作者 / 多标签用 `||` 分隔），RIS 为跨平台书目交换权威格式（建议优先用 RIS 导入）。
- `.merged.json` gains two additive blocks: `prisma` (screening funnel counts) and per-work `relevance_score` / `prisma_included` — both incremental-compatible with existing consumers.

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

# Add biomedical/medical preprints (bioRxiv + medRxiv) and arXiv methodology breadth
# (Europe PMC is already ON by default; disable with --no-with-europepmc)
python scripts/ct_literature.py --topic "osimertinib" --with-biorxiv --with-medrxiv --with-arxiv --run --out-dir ./out
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

See `references/errors.md` for the full error catalogue (network / 429 / 401 / empty results / DOI dedupe).

## Pipeline

- `ct-registry` → `ct-literature`: landscape hypothesis seeds the literature search topic.
- `ct-literature` → `ct-pipeline`: literature works feed the `intel` preset's evidence dimension.
- `ct-literature` → `ct-protocol` / `ct-csr`: published evidence backs the introduction / background.
- `ct-literature --safety` → `ct-safety`: published safety literature qualitatively corroborates FAERS signals.

## Cross-Database Search Mode

A cross-database planning layer (Embase / Cochrane / Web of Science + preprint Tier P, adapted from `multi-database-literature-collector`, AIPOCH MIT) builds search strategy and labels preprints **Tier P**; live fetch still runs OpenAlex / Europe PMC / Semantic Scholar / bioRxiv / medRxiv / arXiv. See `references/multi-db-search.md`.

## Natural language dialogue

Follow `references/search_menu.md`: parse topic / review_type / year / safety; ≥2 params → preview; otherwise ≤2 rounds then default; preview → confirm → `--run` → present summary. Atomic-task units: `references/units.md`.

**Before the actual fetch begins, warn the user it may take several minutes** (the pipeline prints a localized time estimate at run start; mirror it in chat). `--verify all` (default) overlaps fetch with per-paper identifier verification and can run 1–4 min on large result sets; `--verify top` ~1–3 min; `--verify none` ~1 min. Rate-limit backoff on the keyless pool extends this further.
