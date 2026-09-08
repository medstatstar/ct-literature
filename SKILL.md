---
slug: ct-literature
name: ct-literature
displayName: Clinical Trial Literature Search / 临床试验文献检索专家
cn_name: 临床试验文献检索专家
version: 1.0.2
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

## Language

- **English guide** → [README.md](https://github.com/medstatstar/ct-literature/blob/main/README.md) · **中文指南** → [README_zh-CN.md](https://github.com/medstatstar/ct-literature/blob/main/README_zh-CN.md)
- Bilingual auto-switch: the answer language follows the user's question language (English question → English answer, Chinese question → Chinese answer).

## Purpose

Retrieve **published scholarly literature** (peer-reviewed papers, systematic reviews, conference abstracts, preprints) about a drug / disease / method, normalize heterogeneous records from multiple public bibliographic sources into one de-duplicated evidence base, and surface the evidence landscape plus a **CSM (cumulative safety monitoring)** qualitative subset. Supports trial-planning background, protocol / CSR introductions, and published-safety literature checks.

## Positioning within the ct- library

The four A-tier public-intel skills (non-confidential input, `network=public-retrieval`) are complementary:

| Skill | Answers | Object retrieved | Source family |
|---|---|---|---|
| `ct-registry` | What trials are registered / ongoing / completed? | Trial-registry metadata | Registry libraries |
| `ct-literature` | What evidence has been *published*? | Publications | Literature libraries |
| `ct-safety` | Is a drug–event over-reported (signal)? | FAERS cases | Adverse-event databases |
| `ct-pipeline` | Aggregate the above into a strategic intel brief | Consumes the three JSONs | Public-intel layer |

**Boundaries:** `ct-registry` never fetches paper full-text/abstracts; `ct-literature` never fetches registry structured metadata. `ct-literature --safety` surfaces *published* safety literature — **qualitative**, must NOT replace `ct-safety`'s FAERS disproportionality. Not sure which skill? Route via `ct-advisor`; full competitive-intel picture → `ct-pipeline` directly (§15).

## Data Sources

| Source | Access | Status | Role |
|---|---|---|---|
| OpenAlex | Public REST; free key recommended (100k/day via `.env` auto-load) — keyless capped 100/day since 2026-02-13 | Required (primary) | Broad coverage + citation counts |
| Europe PMC | Public REST (MEDLINE / PubMed Central), no key, MeSH-indexed | **Default ON** (`--no-with-europepmc`) | Biomedical precision + MeSH |
| Cochrane (CDSR) | Via Europe PMC journal filter | Opt-in `--cochrane` | Cochrane Database of Systematic Reviews only |
| Semantic Scholar | Public Graph API, no key, rate-limited (429) | **Opt-in only** `--with-semantic-scholar` (not part of default sources; requires key to be useful) | Citation-aware ranking; skipped when no key |
| bioRxiv / medRxiv | Via Europe PMC `SRC:PPR` + publisher filter | **Default ON** (`--no-with-biorxiv` / `--no-with-medrxiv`) | Preprints (Tier P) |
| arXiv | Public Atom API, no key | Optional `--with-arxiv` | Methodology breadth |
| PROSPERO | Public REST (CRD York); **auth header undocumented** | Optional `--with-prospero` (key-gated, **reserved source**) | Duplication-avoidance / protocol discovery |

> All are public bibliographic APIs — no WAF. The **default data sources are OpenAlex (primary) + Europe PMC (on by default) + bioRxiv/medRxiv (on by default)**; everything else (arXiv, Cochrane, PROSPERO, Semantic Scholar) is opt-in. OpenAlex keyless = 100 credits/day since 2026-02-13; a free key lifts to 100k/day (`--openalex-key` / env `OPENALEX_API_KEY` / skill `.env` auto-load; key never printed). Semantic Scholar is an explicit opt-in source (`--with-semantic-scholar` + key) and is **not considered in the default pipeline**.
>
> **PROSPERO is a reserved source (2026-08-12):** its public REST auth header is undocumented; unauthenticated probes return `{"status":"error",...}`. `--with-prospero` is a dormant interface: without a token it degrades to a graceful no-op skip (returns `None`, no file written) and is **not** claimed functional. Supply `--prospero-token` (+ `--prospero-header`) to exercise it; parser is schema-tolerant (JSON + XML) but must be re-validated against a real 200 before declared done. No token application planned.

## Clinical guideline sources (`--with-guidelines`, opt-in · LOCAL corpus)

Guidelines are **version-pinned** reference standards — at analysis time we read a **pre-built LOCAL corpus**, never "fetch latest" per run.

> **Corpus boundary (audit note 2026-09-07):** every entry is a manually curated, version-pinned pointer to an organisation-issued document, but the builder's 12+ sources also surface reviews / consensus / adherence analyses and AI-in-medicine commentary. Such items are kept as background pointers only and are **not** authoritative clinical guidance — always resolve the linked source before relying on it; a `retrieved:false` pointer is an honest placeholder, never a fabricated citation.

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
| **Cochrane retrieval (focus)** | Europe PMC | `--cochrane` → restrict to the Cochrane Database of Systematic Reviews (verified journal filter, shared with meta-analysis) |
| Year-range filter | All | Focus on recent evidence |
| Safety / CSM tagging | All | Every work is flagged `is_safety` (amber-highlighted in the Works sheet) when its title/abstract mentions AE / PV / toxicity — useful for quick scanning. **The standalone Safety-Related sheet is opt-in** (`--safety`); a plain search does NOT emit it by default. |
| Multi-source merge + dedupe | normalize | One unified list, DOI/title de-duped, provenance kept |
| Citation ranking | OpenAlex / S2 | Most influential works |
| MeSH terms | Europe PMC | Biomedical concept indexing |
| Concepts / Keywords / Funders | OpenAlex | Topic classification + COI signals |
| PubMed/PMC ID, OA full-text URL, complete abstract | All | Direct links + full evidence preservation |
| Structured output | — | JSON + Markdown + Excel workbook (`excel_style`). Default sheets: README → Overview → Works → Evidence Log. `Safety-Related` sheet appears **only with `--safety`**. |
| Chained invocation | — | → `ct-pipeline` / `ct-protocol` / `ct-csr` |
| Resilient fetch (retry + backoff) | All | Honors `Retry-After`; OpenAlex Bearer via key |
| Safe link rendering | All | `_normalize_link()` sanitises every hyperlink |
| Citations + BibTeX/RIS | All | `--citation-style` (apa/nature/vancouver/ieee/gb7714) + `--export-bib` |
| PRISMA screening funnel | All | `--prisma` deterministic rule screen → SVG funnel in HTML |
| Relevance scoring | All | `--rank relevance` → `relevance_score` (title .6 + abstract .4) |
| Obsidian / Zotero integration | All | `--obsidian` notes + MOC; `--zotero` CSV/RIS |
| **P0 · Citation verification** | All | Anti-hallucination (§17.1). `--verify {all\|top\|none}`; source-aware skip; DOI cross-checked via doi.org; title/author consistency vs Crossref/Europe PMC/OpenAlex; flags `verified/bot_blocked/mismatch/unresolved/...` |
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

**Standard deliverables = HTML + Excel only.** Present `lit_report.html` to the user as the result, and remind them of the optional add-ons below (the report itself shows a "还能做什么 / Options" strip with these hints).

- Per-source payloads: `openalex.json` / `europepmc.json` / `semantic_scholar.json` / `biorxiv.json` / `medrxiv.json` / `arxiv.json` (enabled only)
- `lit_report.xlsx` — Excel delivery (`excel_style`; `--no-xlsx` to skip): Overview → Literature master → Safety-related, KPI cards, charts, `is_safety` amber highlighting. **The complete result — user can keep filtering / pivoting on top of it.**
- `lit_report.html` — self-contained HTML report (inline CSS, offline; `--no-html` to skip); inline-SVG PRISMA funnel when `--prisma`. **Default deliverable to open.**
- **On-demand citation formats** (default OFF — ask the user or use `--export-bib`): `references.bib` / `references.ris` / `references_<style>.md` (Zotero RIS / BibTeX / APA etc.). OA-PDF downloads are likewise on request: `--download-pdf` attempts **ALL** records that carry an OA URL or DOI (batched, legal OA sources only); users may instead ask for specific DOI / PMID(s) or the top-N works. The PDF local-path column in `lit_report.xlsx` is written back automatically by `PdfDownloader` when constructed with `xlsx_out` (the main `--download-pdf` flow and any standalone driver that passes `xlsx_out` both benefit); you no longer need to call `update_xlsx_pdf_paths.py` separately. **Server-side supplement chain**: when the A-path direct links all fail, the coze endpoint runs a supplement chain — Unpaywall best-OA → Europe PMC PMC-OA → PPR preprints (bioRxiv/medRxiv, author-verified) — before the (off) browser fallback; the local skill only calls, it no longer implements multi-channel download algorithms.
- **⚠️ PDF 下载后结果面板规则**：`--download-pdf` 及任何直驱 `PdfDownloader` 的脚本，下载完成后结果面板**只呈现标准产物 `lit_report.html` / `lit_report.xlsx`**，绝不逐个打开 / 列出 PDF 文件（数十个 PDF 同时打开会卡死 UI）。下载反馈仅用纯文本告知用户共同保存目录 `out_dir/pdfs/`，由用户自行打开所需 PDF。
- `obsidian/` (`--obsidian`) — per-paper notes + `Literature MOC.md`; `zotero.csv` / `zotero.ris` (`--zotero`)
- `.merged.json` gains additive `prisma` + per-work `relevance_score` / `prisma_included` blocks

See `references/sop.md` for the full command catalogue.

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

```bash
# Primary: OpenAlex only (no key)
python scripts/ct_literature.py --topic "osimertinib" --review-type systematic-review --year-from 2018 --safety --run --out-dir ./out

# Add Europe PMC (default ON) + Semantic Scholar (may 429 -> skipped)
python scripts/ct_literature.py --topic "osimertinib" --with-europepmc --with-semantic-scholar --run --out-dir ./out

# Cochrane-only retrieval (focus on the Cochrane Database of Systematic Reviews)
python scripts/ct_literature.py --topic "NSCLC" --cochrane --with-europepmc --run --out-dir ./out

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

A cross-database planning layer (Embase / Cochrane / Web of Science + preprint Tier P, adapted from `multi-database-literature-collector`, AIPOCH MIT) builds search strategy; live fetch still runs the six sources. See `references/multi-db-search.md`. The **Cochrane** leg is now directly automatable via `--cochrane` (a verified Europe PMC journal filter — identical to meta-analysis's in-skill dedup probe), so CDSR needs no manual browser step.

## Natural-Language Dialogue — Triage-First (mandatory)

NL dialogue MUST triage before choosing the interaction shape. Mandatory per
§6.2 + `references/search_menu.md` — this step is never skipped.

### Step 0 Triage (four buckets, run on the user's first message)

| Bucket | Condition | Behavior |
|---|---|---|
| **Simple** | topic + ≥2 parameters clear (e.g. "osimertinib systematic reviews since 2020") | straight to §4.2 preview confirmation; no §4.1 menu |
| **Complex** | topic given but parameters missing / multiple intents (e.g. "diabetes treatment literature") | §4.1 initial confirmation menu → once parameters are complete, forced through the §12 keyword gate → §4.2 preview confirmation → run |
| **Vague** | what the user wants is unclear (e.g. "find me that new drug") | grill-me branch questions (≤2 rounds), then re-triage |
| **Middle** | single deep point (e.g. "how to compute sample size") | answer directly; no menu |

### Red lines

- **Never skip triage and run `--run` directly.** Even with a clear topic, missing key parameters (review_type / year / sources / …) makes the Complex menu flow mandatory.
- **Never decide for the user.** The Complex menu must carry a "still unsure → explain the differences" entry (option ③ in the CN UI: 说「详细解释这些选择之间的差异」，我先讲清临床与统计含义再让你决定).
- **The §12 keyword-system confirmation gate is mandatory:** whenever the user provides parseable search terms, build the Manifest and let the user review the expanded keywords before running.

### Cross-turn continuity (continuity.md mode A, high risk)

ct-literature's query spec lives ONLY in the conversation thread (OpenAlex /
Europe PMC etc. are stateless remotes); a dropped field silently searches the
wrong scope.

#### Echo block (append after every run)

```
## 当前检索设定：topic=… | type=… | year=… | safety=… | sources=… | max=… | verify=…
```

- Fixed prefix `## 当前检索设定：` (inherited by search_menu.md §13)
- Fields are `key=value`, pipe-separated; missing defaults use `—`; **never omit fields**
- Full field list: `topic / type / year / safety / sources / max / verify`

#### Follow-ups change only the changed fields

The LLM must read the MOST RECENT settings block in the conversation, override
only the fields the user changed this turn, keep the rest as-is, then proceed
to the §12 gate or run.

#### merge_spec fallback (default path)

ct-literature is a high-risk skill (continuity.md §5.1); `merge_spec.py` is the
DEFAULT path on follow-ups:

```bash
echo '{"prev":{previous full spec},"cur":{this-turn partial}}' \
  | python scripts/merge_spec.py
```

Feed the `merged` output into the §12 keyword gate. `prev` comes from the
thread's latest settings block — never persisted, never cached across turns.

#### Local-only continuity

OpenAlex / Europe PMC / bioRxiv / medRxiv are all **stateless remotes** — they
do not remember your previous search parameters. Continuity (parameter
inheritance) MUST be solved locally (thread-resident + echo block +
merge_spec); there is no "the remote will remember" fallback.

### Execution flow

```
user request → Step 0 Triage
  ├─ Simple → §4.2 preview confirm → §12 keyword gate → run → §13 echo
  ├─ Complex → §4.1 initial menu → parameters complete → §12 keyword gate → §4.2 preview confirm → run → §13 echo
  ├─ Vague → grill-me (≤2 rounds) → re-triage
  └─ Middle → answer directly (no menu)
```

## Bug Reporting (§20.3, adapter: `adapters/bug_report.py`)

- **Trigger:** (A) explicit user request ("report a bug" / "反馈问题" / "提交错误报告") → straight to two-stage confirmation, unlimited per session; (B) strong signal (unexpected non-zero exit / engine or compute error / user explicitly questions the result) **and** the same operation was retried ≥1 → at most 1 unsolicited proposal/session.
- **Two-stage confirmation (2026-08-21):** ① propose-with-preview — bilingual `confirm_prompt` together with the full sanitized report (invite a problem description; re-render before consent) → ② on explicit consent, `send_to_endpoint` (auto action=report, endpoint `https://ct-bugreport.coze.site/run`, token = §5 public credential). Decline → never re-propose this session.
- **Sanitization is hard:** 11-key whitelist only (skill / version / error_type / error_code / engine_status / description / locale / query_origin / session_hash / attempts / test) — never raw data or subject records; `description` is the single user-reviewed free-text field. No cloud call → `save_local_report()` (local md + author email).
- **Client-only:** sends `report` only; governance actions belong to `ct-update` (author side). Post-send (2026-08-22): endpoint returns `history` → reply via `confirm_thanks` + `build_followup` (bilingual, locale-switched).

Invoke: `python adapters/bug_report.py --error-type <t> --description "<free text>" [--send]` (add `--send` only after the user confirms).
