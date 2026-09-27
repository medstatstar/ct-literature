---
slug: ct-literature
name: ct-literature
displayName: Clinical Trial Literature Search / 临床试验文献检索专家
cn_name: 临床试验文献检索专家
version: 1.1.3
invocable: true
summary: 全数据源覆盖检索医学领域学术文献（OpenAlex + Europe PMC/MeSH + bioRxiv/medRxiv 预印本 + arXiv 方法学广度），归一化合并去重，可产出 CSM 安全性定性子集，协助提供OA文献PDF下载。无key亦可使用。
license: MIT
description: "Search medical-domain scholarly literature with full data-source coverage (OpenAlex + Europe PMC/MeSH + bioRxiv/medRxiv preprints + arXiv methodology breadth), normalize, merge, and de-duplicate the results, produce a qualitative CSM safety-literature subset, and assist in providing open-access (OA) full-text PDF downloads. Usable without a key. / 全数据源覆盖检索医学领域学术文献（OpenAlex + Europe PMC/MeSH + bioRxiv/medRxiv 预印本 + arXiv 方法学广度），归一化合并去重，可产出 CSM 安全性定性子集，协助提供OA文献PDF下载。无key亦可使用。"
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

- **English guide** → [README.md](https://github.com/medstatstar/ct-literature/blob/main/README.md) · **中文指南** → [README_zh-CN.md](https://github.com/medstatstar/ct-literature/blob/main/README_zh-CN.md)
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
Anti-hallucination: **P0 citation verification** (`--verify`, §17.1) · **P1 DOI audit** (`--verify-dois`) · **P0 evidence provenance log**.
Full capability table (per-feature flags & semantics) → [references/capabilities.md](references/capabilities.md).

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
Invocation cookbook (worked examples, `--sources` semantics, OpenAlex key setup) → [references/capabilities.md](references/capabilities.md).

## Errors

See [references/errors.md](references/errors.md) for the full error catalogue (network / 429 / 401 / empty results / DOI dedupe).

## Pipeline

- `ct-registry` → `ct-literature`: landscape hypothesis seeds the literature search topic.
- `ct-literature` → `ct-pipeline` (intel evidence dimension), → `ct-protocol` / `ct-csr` (background), `--safety` → `ct-safety` (qualitative corroboration).

## Cross-Database Search Mode

A cross-database planning layer (Embase / Cochrane / Web of Science + preprint Tier P, adapted from `multi-database-literature-collector`, AIPOCH MIT) builds search strategy; live fetch still runs the six sources. See [references/multi-db-search.md](references/multi-db-search.md). The **Cochrane** leg is now directly automatable via `--cochrane` (a verified Europe PMC journal filter — identical to meta-analysis's in-skill dedup probe), so CDSR needs no manual browser step.

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
