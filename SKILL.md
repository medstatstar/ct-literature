---
slug: ct-literature
name: ct-literature
displayName: Clinical Trial Literature Search / 临床试验文献检索专家
cn_name: 临床试验文献检索专家
version: 1.4.5
invocable: true
summary: 全数据源覆盖检索医学领域学术文献（OpenAlex + Europe PMC/MeSH + bioRxiv/medRxiv 预印本 + arXiv 方法学广度），归一化合并去重，可产出 CSM 安全性定性子集，协助提供OA文献PDF下载。集成 Docling PDF 结构化解析。无key亦可使用。
license: MIT
description: "Search medical-domain scholarly literature with full data-source coverage (OpenAlex + Europe PMC/MeSH + bioRxiv/medRxiv preprints + arXiv methodology breadth), normalize, merge, and de-duplicate the results, produce a qualitative CSM safety-literature subset, and assist in providing open-access (OA) full-text PDF downloads. Integrated Docling PDF structured parsing. Usable without a key. / 全数据源覆盖检索医学领域学术文献（OpenAlex + Europe PMC/MeSH + bioRxiv/medRxiv 预印本 + arXiv 方法学广度），归一化合并去重，可产出 CSM 安全性定性子集，协助提供OA文献PDF下载。集成 Docling PDF 结构化解析。无key亦可使用。"
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
  pdf_parsing: "Docling (primary) / PyMuPDF / PdfPlumber (fallback)"
permissions:
  scope: "user-space-only"
  network: "optional"
  network_note: "Reads only public bibliographic sources: OpenAlex (api.openalex.org, no key), Europe PMC (ebi.ac.uk, MEDLINE/MeSH, no key; also indexes bioRxiv/medRxiv preprints via SRC:PPR), Semantic Scholar (api.semanticscholar.org, no key; rate-limited HTTP 429 -> gracefully skipped), arXiv (export.arxiv.org/api/query, no key). Europe PMC is ON by default (--no-with-europepmc to disable); bioRxiv/medRxiv are ON by default (--no-with-biorxiv / --no-with-medrxiv to disable); arXiv is opt-in via --with-arxiv. No WAF, no confidential input; ordinary input + public retrieval (A-tier). Opt-in, user-confirmed bug reports additionally reach https://ct-bugreport.coze.site/run with an 11-key sanitized envelope only (never raw data)."
  filesystem: "read-only to its own files; writes report files only to the current working directory"
  data: "no confidential data input; no external transmission of user data"

---

## Published Application

The workbench is published as a Python HTTP service at `https://ct-literature.app.workbuddy.host/`
(appId `wbapp_WuOPnJ4caJ32GTquNlR7vc`; bundle `workbench/publish-dist/`, workspace-independent,
re-publish via `workbench/publish-kit/install_genie.py` — **overwrite, never `createNewApp`**;
mis-bound paths are permanently retired and the returned `shareLink` must always be asserted).
**Full registry table + re-publishing protocol → [references/published_app.md](references/published_app.md)** — load it before any deploy / re-publish operation.

## Language

- **English guide** → [README.md](https://github.com/medstatstar/ct-literature/blob/main/README.md) · **Chinese guide** → [README_zh-CN.md](https://github.com/medstatstar/ct-literature/blob/main/README_zh-CN.md)
- Bilingual auto-switch: the answer language follows the user's question language (English question → English answer, Chinese question → Chinese answer).

## Purpose

Retrieve **published scholarly literature** (peer-reviewed papers, systematic reviews, conference abstracts, preprints) about a drug / disease / method, normalize heterogeneous records from multiple public bibliographic sources into one de-duplicated evidence base, and surface the evidence landscape plus a **CSM (cumulative safety monitoring)** qualitative subset. Supports trial-planning background, protocol / CSR introductions, and published-safety literature checks.

## Positioning within the ct- library

Four complementary A-tier public-intel skills: `ct-registry` (registered trials) · **`ct-literature` (published evidence)** · `ct-safety` (FAERS signals) · `ct-pipeline` (aggregate intel brief).
**Boundaries:** `ct-literature --safety` is *qualitative* published-safety literature — never a substitute for `ct-safety`'s FAERS disproportionality. Unsure which skill? Route via `ct-advisor` (§15). Full four-skill matrix + boundary detail → [references/capabilities.md](references/capabilities.md).

## Data Sources

Default pipeline: **OpenAlex (primary) + Europe PMC (default ON) + bioRxiv/medRxiv (default ON)**.
Opt-in: arXiv (`--with-arxiv`), Cochrane CDSR via Europe PMC journal filter (`--cochrane`), Semantic Scholar (`--with-semantic-scholar`, key needed), PROSPERO (`--with-prospero` — **reserved source**, dormant no-op without token, never claimed functional). All public bibliographic APIs, no WAF; keyless OpenAlex is capped 100/day since 2026-02-13 — a free key lifts to 100k/day (`.env` auto-load, key never printed).
Per-source access/status/role table + PROSPERO caveat → [references/capabilities.md](references/capabilities.md).

## Clinical guideline sources (`--with-guidelines`, opt-in · LOCAL corpus)

Version-pinned, **pointer-only** corpus (`references/guidelines/guidelines_index.json`) — build once (network, `adapters/build_guidelines.py`), read many (zero network). Full-text documents are NEVER shipped in the skill (author Coze KB / opt-in external cache). Corpus is honest by construction: failed fetch degrades to a `retrieved:false` pointer, never a fabricated citation.
Tier matrix, data-protection split, audit notes → [references/capabilities.md](references/capabilities.md).

## Features

Core: topic/drug/disease search · review-type & year filters · safety/CSM tagging · multi-source merge+dedupe · citation ranking · MeSH/concepts/funders · structured output (JSON/MD/Excel) · retry+backoff · safe link rendering · citations BibTeX/RIS · PRISMA funnel · doc-type exclusion (`--original-only` / `--only-type`, bidirectional) · relevance scoring · Obsidian/Zotero.
- **Month-level date window (route B, 2026-10-12)**: `--date-from YYYY-MM-DD` / `--date-to YYYY-MM-DD` / `--recent-months N` push the publication-date lower bound **natively down** into the OpenAlex `from_publication_date`, Europe PMC and preprint `(FIRST_PDATE:[...])` query clauses (replacing the coarse year-level `Jan-1` granularity; 🔴 never use `filter=pdates:` — the API silently ignores it); after merging, `run()` applies an additional client-side clipping fallback (including a year fallback) to guarantee cross-source correctness. Use it for "recent N months only" queries.
- **online/Coze channel date window (v1.4.2 client + v1.4.3 cloud, 2026-10-12/13)**: `dispatch()` passes `lit_date_from/lit_date_to` through to the Coze payload and clips returned results with `clip_by_date_window`. The cloud side (`ct-registry/adapters/coze`, COZE_VERSION **0.3.94**) now declares `lit_date_from/lit_date_to` in all three schema models and filters natively in all five literature nodes (OpenAlex `from/to_publication_date`; Europe PMC + preprints `(FIRST_PDATE:[lo TO hi])`; arXiv `submittedDate`; S2 `publicationDateOrYear`), plus fixes the europepmc empty-`publication_date` root cause (`firstPublicationDate` top-level field, aligning with the local 2026-09-08 BUGFIX). **Native online filtering takes effect only after the cloud 0.3.94 bundle is deployed** (manual Coze-platform release); until then `--offline`/`--local` remains the hard recency guarantee, and the client-side clip keeps correctness against the un-upgraded cloud.

Anti-hallucination: **P0 citation verification** (`--verify`, §17.1) · **P1 DOI audit** (`--verify-dois`) · **P0 evidence provenance log**.
Full capability table (per-feature flags & semantics) → [references/capabilities.md](references/capabilities.md).

### Retrieval structure model (2026-09-30, adapted from the `tencent-lit-search` expert · P0/P1)

Ported the `tencent-lit-search` expert's auditable retrieval structure to ct-literature — all **additive, backward-compatible** (no new flag = identical old behavior):

- **Structured PICO concepts `--concept TYPE=VALUE`** (repeatable): `TYPE∈{condition,population,intervention,comparator,outcome,endpoint,study_design,biomarker,drug,indication}`. Concepts are AND-combined into the query, with intervention / comparator / outcome on separate axes (no longer all crammed into `--topic`); each concept is MeSH-normalized and its `mapping_status` recorded (`exact_label` / `synonym` / `unmapped_literal`; fuzzy matches are rejected and literal terms are never fabricated).
- **Retrieval depth budget `--depth quick|standard|deep`**: per-source cap + whether to trigger weak-result rescue (`quick` never rescues; `standard`/`deep` do). Not an evidence-quality rating.
- **Evidence-dimension lane**: each merged record gets `evidence_dimension` (= `safety` if `is_safety`, else `general`); `--safety` plans a dedicated safety lane so safety signals are not diluted by efficacy records. SAFE PREVIEW prints the **lane plan view** (purpose / source / evidence_dimension / notes) for pre-run review.
- **Four-state audit ledger + coverage verdict**: evidence-log adds `status∈{ok,empty,error,skipped}` and `coverage∈{healthy,partial,empty,critical_gap}`; explicitly-disabled sources are logged as `skipped` (not_run); gaps are surfaced honestly, never zeroed; OpenAlex failure → `critical_gap` with a warning against extrapolation.
- **Weak-result rescue (P1-6)**: when `standard`/`deup` and unique merged works < 5 and concepts had narrowed the query, automatically re-run with a broader query (topic only); single-shot, non-fatal; logs `skipped` if nothing new is added.

> What is NOT ported: the `tencent-lit-search` expert's 7-scenario exhaustive set / first-class trial·drug·target objects / target-gene-variation entities — these fall outside ct-literature's clinical-literature scope and would overlap with ct-registry / ct-safety, so they are deliberately excluded.

## Unified work schema

Normalizes all sources into one record shape (`source / id / title / authors / year / … / doi / mesh / concepts / is_safety / is_preprint / sources`). Field list → [references/capabilities.md](references/capabilities.md).

## Output

**Standard deliverables = HTML + Excel only** — present `lit_report.html`; `lit_report.xlsx` keeps the complete filterable result. On-demand add-ons: citations (`.bib`/`.ris`/styled md), OA-PDF download (`--download-pdf`, legal sources only; **never open/list individual PDFs after download — point users at `out_dir/pdfs/`**), Obsidian notes, Zotero exports. PDF pipeline runs local-resolve ‖ Coze-decode ‖ download in parallel (2026-09-19).
Full output catalogue, sheet layout, server-side supplement chain, concurrency notes → [references/capabilities.md](references/capabilities.md); command catalogue → [references/sop.md](references/sop.md).

## Requirements

- Python 3.10+ (Anaconda `C:\Tools\anaconda3\python.exe` recommended).
- `requests` optional (fetch scripts use stdlib `urllib`); `matplotlib` optional (future trend charts).
- Network: read-only public bibliographic APIs.

## ⚠️ Safety

- Default **SAFE PREVIEW**: scripts only generate / display; network requests run only with explicit `--run`.
- Reads **public publications ONLY**, zero confidential research / subject data input (A-tier — non-confidential input, per §11; API keys are local config, never research data).
- `--safety` literature is **qualitative** — never feed it into FAERS disproportionality; it only corroborates `ct-safety` qualitatively.
- Output is for reference / background only, not a regulatory submission.

## Implementation

Primary entry: `python scripts/ct_literature.py --topic "<query>" [--review-type …] [--year-from …] [--safety] [--cochrane] [--sources "OpenAlex,EuropePMC"] [--with-guidelines] --run --out-dir ./out` (omit `--run` = SAFE PREVIEW). Guidelines corpus build: `python adapters/build_guidelines.py --topic <topic> --run`.
**Date window (route B)**: add `--recent-months 1` (or `--date-from 2026-09-12 --date-to 2026-10-12`) to keep only papers published in the last month; date-level parameters take precedence over the year-level `--year-from`, are pushed natively down into every source API, and are clipped client-side after merging (reusing `clip_by_date_window`, including the year fallback). The online/Coze channel also passes `date` through and clips the response, but since the cloud does not filter natively, recent papers can still be truncated away by `max_results` (measured: openalex/biorxiv clipped to zero) — **use `--offline` for a hard recency guarantee**.
Invocation cookbook (worked examples, `--sources` semantics, OpenAlex key setup) → [references/capabilities.md](references/capabilities.md).

## Errors

See [references/errors.md](references/errors.md) for the full error catalogue (network / 429 / 401 / empty results / DOI dedupe).

## Evaluation Benchmarks (v1.4.0 blueprint)

Evidence-synthesis evaluation design (retrieval recall / dedup precision / summary faithfulness)
based on TrialMind / TrialReviewBench (npj Digit Med 2025, 100 reviews / 2,220 studies), MedReview
(2024, 8,161 Cochrane pairs) and TrialPanorama (2026, 8 tasks) →
[references/evidence_synthesis_benchmark.md](references/evidence_synthesis_benchmark.md).
Blueprint only — engine behavior unchanged in v1.4.0.

## Pipeline

- `ct-registry` → `ct-literature`: landscape hypothesis seeds the literature search topic.
- `ct-literature` → `ct-pipeline` (intel evidence dimension), → `ct-protocol` / `ct-csr` (background), `--safety` → `ct-safety` (qualitative corroboration).

## Cross-Database Search Mode

A cross-database planning layer (Embase / Cochrane / Web of Science + preprint Tier P, adapted from `multi-database-literature-collector`, AIPOCH MIT) builds search strategy; live fetch still runs the six sources. See [references/multi-db-search.md](references/multi-db-search.md). The **Cochrane** leg is now directly automatable via `--cochrane` (a verified Europe PMC journal filter — identical to meta-analysis's in-skill dedup probe), so CDSR needs no manual browser step.

## PDF Parsing Enhancement (Docling · v1.3.0)

> **Docling** (`github.com/docling-project/docling`): IBM's open-source document structure parser. Protocol, IB and CSR PDFs are dense with tables that ordinary parsers shred on conversion. Docling preserves table structure and section hierarchy — the single most important preprocessing step before feeding regulatory documents into RAG question answering.

- Install: `pip install docling`
- Call: `DocumentConverter().convert('paper.pdf')` emits Markdown/JSON with hierarchical structure
- Complements the existing PDF pipeline: Docling parses first (preserving table structure), falling back to PyMuPDF/PdfPlumber on failure
- Use cases: structured parsing of CT.gov protocol PDFs, EU-CTR document PDFs and OA full-text PDFs

## Natural-Language Dialogue — Triage-First (mandatory)

Every NL turn MUST start at Step 0 triage — never skipped, never jump straight to `--run`
(§6.2 + [references/search_menu.md](references/search_menu.md)). Four buckets: **Simple** (topic +
≥2 params → §4.2 preview) · **Complex** (menu §4.1 → §12 keyword gate → §4.2 → run) · **Vague**
(grill-me ≤2 rounds → re-triage) · **Middle** (answer directly).
**Red lines:** never skip triage; never decide for the user (Complex menu keeps the "explain the differences" entry ③); the §12 keyword-system confirmation gate is mandatory whenever search terms are parseable.
**Cross-turn continuity (high-risk, mode A):** query spec lives only in the thread — after every run append the `## 当前检索设定：topic=… | type=… | year=… | safety=… | sources=… | max=… | verify=…` echo block (never omit fields); follow-ups override only changed fields and run through `merge_spec.py` by default; remotes are stateless, so continuity is local-only.
Full triage tables, echo/merge_spec rules, execution flow → [references/dialogue.md](references/dialogue.md) — load it when executing an NL dialogue round.

## Bug Reporting (§20.3, adapter: `adapters/bug_report.py`)

Trigger = explicit user request (unlimited) or strong signal + one retry (≤1 proposal/session).
Hard two-stage confirmation: ① show full sanitized report → ② send only on explicit consent
(endpoint `https://ct-bugreport.coze.site/run`, public credential). 11-key whitelist envelope,
`description` is the only user-reviewed free text; never raw data. Client sends `report` only —
governance belongs to `ct-update`.
Full trigger/two-stage/sanitization detail → [references/dialogue.md](references/dialogue.md).
