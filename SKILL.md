---
slug: ct-literature
name: ct-literature
displayName: 临床试验文献检索专家 / Clinical Trial Literature Search
cn_name: 临床试验文献检索专家
version: 0.7.6
invocable: true
summary: 检索公开学术文献（OpenAlex 主源 + Europe PMC/MeSH 生物医学精准[默认开启] + Semantic Scholar 引用增强 + bioRxiv/medRxiv 预印本 + arXiv 方法学广度），归一化合并去重，产出证据基础与 CSM 定性安全性文献集，附带可选英文→中文摘要术语标注工具（本地、术语级替换，非全文翻译）；临床指南 12+ 源「本地语料库」模式（--with-guidelines 读取预先构建、版本锁定的本地指南指针语料库，分析时零联网；语料库由作者用 python adapters/build_guidelines.py --topic <主题> --run 构建/刷新；构建期对 NCCN/ADA/AHA/SIGN/CMA/CPIC 门户源做轻量抓取——CPIC 走真 API，其余尽力网页抓取、失败则回退诚实指针）；⚠️ 技能树仅含指针（可安全发布），全文存于作者自控 Coze KB，绝不随技能被复制；B 档公开检索，零保密输入。
license: MIT
description: "检索公开学术文献并归一化合并为统一去重证据库：OpenAlex（主源，免费、含引用数）+ Europe PMC（MEDLINE/MeSH，生物医学精准）+ Semantic Scholar（引用排序，可选）。按综述类型、年份区间筛选，并提供安全性/CSM 偏置模式以提取已发表不良事件/药物警戒文献。产出 JSON + Markdown。仅读公开文献，零保密研究/受试者数据输入，B 档（普通输入 + 对外检索；API key 仅本地配置、非研究数据）。含引文标识实时验证与证据溯源日志（反幻觉，ct-base §17.1），并附带可选的英文→中文摘要术语标注工具（本地、术语级替换，非全文翻译）。 / Search public scholarly literature and normalize it into one de-duplicated evidence base: OpenAlex (primary, free, citation-rich) + Europe PMC (MEDLINE/MeSH, biomedical precision) + Semantic Scholar (citation ranking, optional). Filter by review type, year range, and a safety/CSM bias mode that surfaces published adverse-event / pharmacovigilance literature. Produces JSON + Markdown. Reads only public publications; zero confidential research / subject data input, B-tier (ordinary input + public retrieval; API keys are local config, never research data). Includes citation-identifier verification, a provenance evidence log (anti-hallucination, ct-base §17.1), and an optional local English→Chinese abstract term-annotation tool (term-level substitution, not full-text translation). Clinical guidelines are available via --with-guidelines as a LOCAL, version-pinned corpus: at analysis time it reads references/guidelines/guidelines_index.json (zero network), built/refreshed by the author via python adapters/build_guidelines.py --topic <topic> --run (OpenAlex/EuropePMC/GIN/WHO fetched; NICE/MAGICapp/TRIP key-gated; CPIC fetched via its free API; NCCN/ADA/AHA/SIGN/CMA best-effort build-time scrape that gracefully falls back to honest portal pointers when blocked). The skill tree holds only the pointer index (publish-safe); full-text documents live in the author's self-controlled Coze KB, never bundled with the shareable skill."
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

- **English guide** → [README.md](./README.md) · **中文指南** → [README_zh-CN.md](./README_zh-CN.md)
- Responds in the user's input language (auto locale detect). SKILL.md body / `references/*.md` / `AGENTS.md` are English-only (agent-facing). Walkthroughs & troubleshooting → README.

## Purpose

Retrieve **published scholarly literature** (peer-reviewed papers, systematic reviews, conference abstracts, preprints) about a drug / disease / method, normalize heterogeneous records from multiple public bibliographic sources into one de-duplicated evidence base, and surface the evidence landscape plus a **CSM (cumulative safety monitoring)** qualitative subset. Supports trial-planning background, protocol / CSR introductions, and published-safety literature checks.

## Positioning within the ct- library

The four B-tier public-intel skills are complementary:

| Skill | Answers | Object retrieved | Source family |
|---|---|---|---|
| `ct-registry` | What trials are registered / ongoing / completed? | Trial-registry metadata | Registry libraries |
| `ct-literature` | What evidence has been *published*? | Publications | Literature libraries |
| `ct-safety` | Is a drug–event over-reported (signal)? | FAERS cases | Adverse-event databases |
| `ct-pipeline` | Aggregate the above into a strategic intel brief | Consumes the three JSONs | Public-intel layer |

**Boundaries:** `ct-registry` never fetches paper full-text/abstracts; `ct-literature` never fetches registry structured metadata. `ct-literature --safety` surfaces *published* safety literature — **qualitative**, must NOT replace `ct-safety`'s FAERS disproportionality. Not sure which skill? Route via `ct-advisor`; full competitive-intel picture → `ct-pipeline` directly (ct-base/BASE.md §15).

## Data Sources

| Source | Access | Status | Role |
|---|---|---|---|
| OpenAlex | Public REST; free key recommended (100k/day via `.env` auto-load) — keyless capped 100/day since 2026-02-13 | Required (primary) | Broad coverage + citation counts |
| Europe PMC | Public REST (MEDLINE / PubMed Central), no key, MeSH-indexed | **Default ON** (`--no-with-europepmc`) | Biomedical precision + MeSH |
| Semantic Scholar | Public Graph API, no key, rate-limited (429) | Optional `--with-semantic-scholar` | Citation-aware ranking; degrades gracefully on 429 |
| bioRxiv / medRxiv | Via Europe PMC `SRC:PPR` + publisher filter | Optional `--with-biorxiv` / `--with-medrxiv` | Preprints (Tier P) |
| arXiv | Public Atom API, no key | Optional `--with-arxiv` | Methodology breadth |
| PROSPERO | Public REST (CRD York); **auth header undocumented** | Optional `--with-prospero` (key-gated, **reserved source**) | Duplication-avoidance / protocol discovery |

> All are public bibliographic APIs — no WAF. OpenAlex keyless = 100 credits/day since 2026-02-13; a free key lifts to 100k/day (`--openalex-key` / env `OPENALEX_API_KEY` / skill `.env` auto-load; key never printed). Semantic Scholar skips outright when no key is configured (manual application review).
>
> **PROSPERO is a reserved source (2026-08-12):** its public REST auth header is undocumented; unauthenticated probes return `{"status":"error",...}`. `--with-prospero` is a dormant interface: without a token it degrades to a graceful no-op skip (returns `None`, no file written) and is **not** claimed functional. Supply `--prospero-token` (+ `--prospero-header`) to exercise it; parser is schema-tolerant (JSON + XML) but must be re-validated against a real 200 before declared done. No token application planned.

## Clinical guideline sources (`--with-guidelines`, opt-in · LOCAL corpus)

Guidelines are **version-pinned** reference standards — at analysis time we read a **pre-built LOCAL corpus**, never "fetch latest" per run.

> **🔒 Data-protection split.** The skill tree ships **pointer-only** (`references/guidelines/guidelines_index.json`: org/title/URL/version — publish-safe). **Full-text documents are NEVER written into the skill** — they live in the author's self-controlled Coze KB (or an EXTERNAL local cache `~/.workbuddy/ct-guideline-docs`, opt-in via `--download`, off by default); ct-advisor consults that KB for native guideline Q&A.

- **Author / build-time** (network): `python adapters/build_guidelines.py --topic <topic> --run` aggregates 12+ sources → `guidelines_index.json` (96 curated entries, schema v1). SAFE PREVIEW: omit `--run` (dry-run, no network/write).
- **Analysis-time** (zero network): `--with-guidelines` on the main pipeline → `adapters/guideline_corpus.load()` reads the local index → `guidelines.json` + `guidelines` block in `.merged.json`.

| Tier | Sources | How it got into the corpus |
|---|---|---|
| `api` | OpenAlex, Europe PMC, GIN, WHO IRIS | fetched by the builder (OA-PDF download attempted) |
| `api` (key-gated) | NICE¹, MAGICapp, TRIP² | fetched if a key configured; else skipped |
| `portal`→`api` | CPIC | genuine fetch via free keyless PostgREST API (`api.cpicpgx.org/v1`) |
| `portal` pointer | NCCN, ADA, AHA, SIGN, CMA | best-effort public-portal scrape → graceful fallback to honest pointer (`retrieved:false`), never fabricated |

**Build-time portal fetch (`adapters/portal_fetch.py`):** every fetcher is wrapped so it never raises — failed fetch degrades to the honest pointer, so the corpus is always honest (build once, read many). Each record carries `access` (`api`/`portal`) + `retrieved`; `guideline_corpus.load()` filters by topic/org and returns `corpus_missing` (with the builder command) if the index is absent. ¹ NICE REST auth undocumented (like PROSPERO) — skip until a token works. ² TRIP requires a commercial key.

## Features

| Capability | Source | Typical scenario |
|---|---|---|
| Topic / drug / disease search | All | Build the published-evidence base |
| Review-type filter | All | `systematic-review` / `meta-analysis` / `rct` / `case-report` |
| Year-range filter | All | Focus on recent evidence |
| Safety / CSM bias | All | Surface published AE / PV literature |
| Multi-source merge + dedupe | normalize | One unified list, DOI/title de-duped, provenance kept |
| Citation ranking | OpenAlex / S2 | Most influential works |
| MeSH terms | Europe PMC | Biomedical concept indexing |
| Concepts / Keywords / Funders | OpenAlex | Topic classification + COI signals |
| PubMed/PMC ID, OA full-text URL, complete abstract | All | Direct links + full evidence preservation |
| Structured output | — | JSON + Markdown + Excel workbook (ct-base `excel_style`) |
| Chained invocation | — | → `ct-pipeline` / `ct-protocol` / `ct-csr` |
| Resilient fetch (retry + backoff) | All | Honors `Retry-After`; OpenAlex Bearer via key |
| Safe link rendering | All | `_normalize_link()` sanitises every hyperlink |
| Citations + BibTeX/RIS | All | `--citation-style` (apa/nature/vancouver/ieee/gb7714) + `--export-bib` |
| PRISMA screening funnel | All | `--prisma` deterministic rule screen → SVG funnel in HTML |
| Relevance scoring | All | `--rank relevance` → `relevance_score` (title .6 + abstract .4) |
| Obsidian / Zotero integration | All | `--obsidian` notes + MOC; `--zotero` CSV/RIS |
| **P0 · Citation verification** | All | Anti-hallucination (ct-base §17.1). `--verify {all\|top\|none}`; source-aware skip; DOI cross-checked via doi.org; title/author consistency vs Crossref/Europe PMC/OpenAlex; flags `verified/bot_blocked/mismatch/unresolved/...` |
| **P0 · Evidence provenance log** | All | `evidence_log.json/.md` + workbook sheet + HTML block: query→source→hits→retrieved_at→verification rate |
| **P1 · PROSPERO registry** | Review register | `--with-prospero` (opt-in, key-gated, **reserved**) — dormant no-op skip without token; never claimed functional |
| **G · Guideline corpus** | Guideline orgs | `--with-guidelines` → local pointer corpus (see above) |

## Unified work schema

```
{ source, id, title, authors, year, publication_date, publication, journal_iso,
  type, study_type, cited_by_count, url, open_access_url,
  pmid, pmcid, doi, abstract_snippet, mesh, concepts, keywords, funders,
  language, is_retracted, is_safety, is_preprint, volume, issue, page,
  affiliations, sources }
```

## Output

- Per-source payloads: `openalex.json` / `europepmc.json` / `semantic_scholar.json` / `biorxiv.json` / `medrxiv.json` / `arxiv.json` (enabled only)
- `lit_report.xlsx` — Excel delivery (ct-base `excel_style`; `--no-xlsx` to skip): Overview → Literature master → Safety-related, KPI cards, charts, `is_safety` amber highlighting
- `lit_report.html` — self-contained HTML report (inline CSS, offline; `--no-html` to skip); inline-SVG PRISMA funnel when `--prisma`
- `references.bib` / `references.ris` / `references_<style>.md` — formatted citations; `--no-export-bib` to skip
- `obsidian/` (`--obsidian`) — per-paper notes + `Literature MOC.md`; `zotero.csv` / `zotero.ris` (`--zotero`)
- `.merged.json` gains additive `prisma` + per-work `relevance_score` / `prisma_included` blocks

See `references/sop.md` for the full command catalogue.

## Requirements

- Python 3.10+ (Anaconda `C:\Tools\anaconda3\python.exe` recommended).
- `requests` optional (fetch scripts use stdlib `urllib`); `matplotlib` optional (future trend charts).
- Network: read-only public bibliographic APIs.

## ⚠️ Safety

- Default **SAFE PREVIEW**: scripts only generate / display; network requests run only with explicit `--run`.
- Reads **public publications ONLY**, zero confidential research / subject data input (B-tier; API keys are local config, never research data).
- `--safety` literature is **qualitative** — never feed it into FAERS disproportionality; it only corroborates `ct-safety` qualitatively.
- Output is for reference / background only, not a regulatory submission.

## Implementation

```bash
# Primary: OpenAlex only (no key)
python scripts/ct_literature.py --topic "osimertinib" --review-type systematic-review --year-from 2018 --safety --run --out-dir ./out

# Add Europe PMC (default ON) + Semantic Scholar (may 429 -> skipped)
python scripts/ct_literature.py --topic "osimertinib" --with-europepmc --with-semantic-scholar --run --out-dir ./out

# Clinical guidelines: build once (network), read many (zero network)
python adapters/build_guidelines.py --topic "diabetes" --run          # author/build-time; omit --run = SAFE PREVIEW
python scripts/ct_literature.py --topic "2型糖尿病" --with-guidelines --run --out-dir ./out
```

### OpenAlex API key (recommended since 2026-02-13)

Keyless is capped at 100 credits/day; a free key lifts to 100k/day. **Zero-friction:** drop the key into the skill's `.env` (copy from `.env.example`) — no extra flag needed. `http_utils.load_openalex_key()` auto-resolves: env `OPENALEX_API_KEY` → skill-root `.env` → `scripts/.env` (key value never printed). Explicit provision also works (`--openalex-key`). Application steps, quota, troubleshooting → `references/openalex_key.md`.

## Errors

See `references/errors.md` for the full error catalogue (network / 429 / 401 / empty results / DOI dedupe).

## Pipeline

- `ct-registry` → `ct-literature`: landscape hypothesis seeds the literature search topic.
- `ct-literature` → `ct-pipeline` (intel evidence dimension), → `ct-protocol` / `ct-csr` (background), `--safety` → `ct-safety` (qualitative corroboration).

## Cross-Database Search Mode

A cross-database planning layer (Embase / Cochrane / Web of Science + preprint Tier P, adapted from `multi-database-literature-collector`, AIPOCH MIT) builds search strategy; live fetch still runs the six sources. See `references/multi-db-search.md`.

## Natural language dialogue

Follow `references/search_menu.md`: parse topic / review_type / year / safety; ≥2 params → preview; otherwise ≤2 rounds then default; preview → confirm → `--run` → present summary. Atomic-task units: `references/units.md`.

**Before the fetch begins, warn the user it may take several minutes** (the pipeline prints a localized time estimate at run start; mirror it in chat). `--verify all` 1–4 min on large result sets; `--verify top` ~1–3 min; `--verify none` ~1 min.

## Bug Reporting (ct-base §20.3, adapter: `adapters/bug_report.py`)

- **Trigger:** (A) explicit user request ("report a bug" / "反馈问题" / "提交错误报告") → straight to two-stage confirmation, unlimited per session; (B) strong signal (unexpected non-zero exit / engine or compute error / user explicitly questions the result) **and** the same operation was retried ≥1 → at most 1 unsolicited proposal/session.
- **Two-stage confirmation (2026-08-21):** ① propose-with-preview — bilingual `confirm_prompt` together with the full sanitized report (invite a problem description; re-render before consent) → ② on explicit consent, `send_to_endpoint` (auto action=report, endpoint `https://ct-bugreport.coze.site/run`, token = §5 public credential). Decline → never re-propose this session.
- **Sanitization is hard:** 11-key whitelist only (skill / version / error_type / error_code / engine_status / description / locale / query_origin / session_hash / attempts / test) — never raw data or subject records; `description` is the single user-reviewed free-text field. No cloud call → `save_local_report()` (local md + author email).
- **Client-only:** sends `report` only; governance actions belong to `ct-update` (author side). Post-send (2026-08-22): endpoint returns `history` → reply via `confirm_thanks` + `build_followup` (bilingual, locale-switched).

Invoke: `python adapters/bug_report.py --error-type <t> --description "<free text>" [--send]` (add `--send` only after the user confirms).
