# Clinical Trial Literature Search (ct-literature)

[🇨🇳 中文](./README_zh-CN.md) | [🇺🇸 English (Current)](#)

<div align="center">
<img src="assets/icon.svg" width="240" height="240" alt="ct-literature logo"/>
</div>

> **A `ct-` library skill (B-tier public-intel) that retrieves published scholarly literature about a drug / disease / method, normalizes multiple public bibliographic sources into one de-duplicated evidence base, and surfaces the evidence landscape plus a CSM (cumulative safety monitoring) qualitative subset.**

> 💡 **Keyless by default, but a free key lifts the cap a lot:** OpenAlex has required an API key since 2026-02-13; without one you are in the keyless pool (100 credits/day, flagged *not suitable for production*). A free key lifts this to 100k/day. Apply in ~30s — see §7 and the key-notice the skill prints automatically when no key is detected.

> No commands or manual needed. Just describe your literature question **in plain language inside a chat** — the skill fetches from OpenAlex (primary) plus optional Europe PMC / Semantic Scholar, then writes a self-contained **HTML + Excel** report. B-tier: fully local computation, only public retrieval. **Note: your topic query is sent to the public bibliographic APIs below — see the outbound notice in §7.** The skill activates **only when you explicitly ask for a literature search**; it never retrieves on its own during unrelated conversations.

## Table of Contents
- [Who This Is For](#who-this-is-for)
- [Data Sources](#data-sources)
- [Why You Can Trust the Output — Anti-Hallucination](#why-you-can-trust-the-output--anti-hallucination)
- [How to Use It in a Chat](#how-to-use-it-in-a-chat)
- [What Can It Do — Scenarios](#what-can-it-do--scenarios)
- [First-Time FAQ](#first-time-faq)
- [Security & Privacy](#security--privacy)
- [Advanced Reference (Developers)](#advanced-reference-developers)

---

## Who This Is For

ct-literature is part of the `ct-` clinical-trial skill family, built for three groups:

- **Clinical-trial practitioners at pharmaceutical companies** — sponsors, CROs, and medical / statistical / regulatory roles;
- **Clinicians and nurses who take part in the hands-on conduct of trials**;
- **Medical students who want to learn clinical-trial methodology in a structured way**.

## Data Sources

| Source | Key | Role |
|---|---|---|
| OpenAlex | recommended (free key; keyless = 100/day since 2026-02-13) | **Primary** — broad, citation-rich |
| Europe PMC | no key | **On by default** (`--no-with-europepmc` to disable) — MEDLINE/MeSH biomedical precision |
| Semantic Scholar | no key (429-prone) | Optional `--with-semantic-scholar` — citation ranking; **skipped automatically** when no key / on 429 |
| bioRxiv | no key (via Europe PMC PPR) | Optional `--with-biorxiv` — biomedical preprints |
| medRxiv | no key (via Europe PMC PPR) | Optional `--with-medrxiv` — medical/clinical preprints |
| arXiv | no key | Optional `--with-arxiv` — physics/CS/ML methodology breadth |
| PROSPERO | token required (undocumented auth header) | Optional `--with-prospero` — systematic-review registry / protocol discovery; **reserved source**, degrades to a no-op skip until a working token + header is supplied |

### How the sources fit together

The default pair — **OpenAlex (primary) + Europe PMC (on by default)** — already reaches almost the entire published landscape: through these two endpoints you get PubMed / PMC, the bioRxiv / medRxiv / arXiv preprints, and the Crossref, Semantic Scholar, CORE, and Unpaywall records. The extra sources are opt-in, not because the pair is incomplete, but for two practical reasons:

- **Resilience against rate limits** — Europe PMC is occasionally throttled (HTTP 429). When that happens, the standalone endpoints (Semantic Scholar, the preprint servers) let you keep widening coverage without depending on a single bottleneck.
- **Preprint freshness** — enabling direct **bioRxiv / medRxiv** retrieval is the choice you make when timeliness matters: you pull preprints straight from the source instead of waiting for them to propagate through Europe PMC's PPR feed.

## Why You Can Trust the Output — Anti-Hallucination

LLM-powered literature tools are notorious for **inventing papers that don't exist** — fabricated DOIs, wrong PMIDs, plausible-but-fake citations. ct-literature is built to make that impossible *by construction*, through four independent guardrails plus two operational safeguards:

1. **Every citation is resolved against its live source (P0, default ON).** Before a work reaches your report, its identifier is checked against the real bibliographic API: DOI → `doi.org` (HTTP 2xx), PMID → Europe PMC `EXT_ID`, OpenAlex id → `api.openalex.org/works/<id>`. Each work is tagged `citation_verified` plus a status of `verified` / `bot_blocked` / `unresolved` / `no_identifier` / `suspicious`. A **malformed DOI is flagged `suspicious`** — a likely hallucinated identifier is caught *before* it can appear in the report. Scope it with `--verify {all|top|none}`; the default `all` verifies every work.
   - **`bot_blocked`**: some publishers (NEJM, JAMA, Wiley, MDPI…) return **403** to programmatic access even though the DOI is real. The skill reports this distinctly — it is *not* a broken link, and the work stays `verified=True`.
2. **Title / author consistency depth (v0.6.11).** Once an identifier resolves to a live resource, the skill fetches that resource's canonical metadata (title + first-author surname) from the authoritative, bot-friendly API — **Crossref** for DOIs (bot-friendly even when the publisher blocks `doi.org`), **Europe PMC** for PMIDs, **OpenAlex** for OpenAlex ids — and compares it to the work you hold. A resolved-but-**different** paper is flagged **`mismatch`** (not `verified`); a `bot_blocked` DOI whose Crossref metadata matches is **upgraded to `verified`**. A hallucinated-but-real DOI is thus caught *even when it resolves*. Metadata-fetch failure degrades gracefully to "verified, consistency unchecked" — it never invents a mismatch. Opt out with `--no-consistency`.
3. **Full provenance is recorded, not summarized away.** Every merged work keeps its `sources` list (which API produced it), and `evidence_log.json` stores an immutable-style audit trail: query → source → hit count → retrieved_at → verification rate. You can always trace a claim back to the exact API call that produced it.
4. **The report never pads gaps with fluent prose.** Every factual line in the report carries a source label or an explicit `⚠️ needs official verification` marker. The skill does **not** generate plausible-looking evidence to fill holes — if a source failed or a work is unverified, that is shown, not hidden.

Operational safeguards reinforce this: **Safe Preview** keeps normalization / reporting on your machine (no remote code execution), and **source-aware skip** avoids redundant re-checks while still trusting each identifier *by provenance* (a paper OpenAlex returned already carries a real OpenAlex id, so it isn't re-queried there). All of this follows the ct-base anti-hallucination spec (§17.1).

**Net:** the references this skill gives you are real, resolvable, and traceable — safe to put in a slide, a protocol, or a CSR appendix, provided you validate against the official source before any regulatory submission (see §7).

## How to Use It in a Chat

ct-literature is a **conversational skill**: you simply tell the assistant what you want to look up — no commands, no parameter names to remember. Once installed as a WorkBuddy skill, you invoke it in a chat via the Skill tool; there is no extra setup, but it activates only when you call it.

Below are 8 real conversational examples ordered from simple to advanced. Each shows **"You say"** and a sketch of **"The assistant replies"**, plus how the report is produced. The primary deliverables are a self-contained **`lit_report.html`** (offline, printable) and **`lit_report.xlsx`** (4 sheets: Overview → Literature master → Safety-related → Evidence Log).

### Example 1 · A simple literature search (direct)
**You say:**
Search published literature on osimertinib in NSCLC, 2018–2025.

**Assistant replies (sketch):**
Routing to OpenAlex (primary). Here is the normalized evidence base — N papers, top-cited works, yearly trend, plus a CSM subset. Report saved to `lit_report.xlsx` (and `lit_report.html`).

**📌 No key needed** — OpenAlex keyless pool covers a small search; the skill fetches and writes the report directly.

### Example 2 · Add a safety / CSM subset
**You say:**
Same topic, but focus on adverse events / post-marketing safety.

**Assistant replies (sketch):**
Adding `--safety` — the report now includes a qualitative CSM subset (published case reports / PV articles), flagged separately from `ct-safety`'s structured FAERS signal analysis. The two are distinct data types; literature complements but does not replace FAERS.

### Example 3 · Broader coverage (Europe PMC + Semantic Scholar)
**You say:**
Also pull MEDLINE via Europe PMC and citation-rank via Semantic Scholar.

**Assistant replies (sketch):**
Adding `--with-europepmc` (MeSH precision) and `--with-semantic-scholar` (citation ranking). S2 is skipped automatically if no key or on 429 — OpenAlex + Europe PMC still produce results.

### Example 4 · Configure the OpenAlex key (self-config)
**You say:**
How do I lift the 100/day limit for large searches?

**Assistant replies (sketch):**
Apply for a free key (~30s) at <https://openalex.org/settings/api>. Configure it yourself via (a) adding `OPENALEX_API_KEY=<key>` to `ct-literature/.env`, (b) exporting an `OPENALEX_API_KEY` environment variable, or (c) passing `--openalex-key <key>` on the command line. **Note:** chat messages may be logged or retained by the platform — for maximum secrecy use the self-config routes (a)–(c). If you prefer, you can also ask the assistant to write the key into `ct-literature/.env` for you — it stores the key locally, never echoes it back, never logs it, and sends it only over HTTPS to the official OpenAlex API.

### Example 5 · Get the Excel deliverable
**You say:**
Can I get an Excel file as well?

**Assistant replies (sketch):**
Yes — `--run` always produces `lit_report.xlsx` (academic-green theme, 4 sheets: Overview → Literature master → Safety-related with KPI cards and charts; safety-relevant rows highlighted) alongside `lit_report.html`. Use `--no-xlsx` to skip the spreadsheet, or `--no-html` to skip the page.

### Example 6 · Complex request → confirmation menu (popup)
**You say:**
I want to look into diabetes treatment literature.

**Assistant replies (sketch):**
Detects topic = diabetes but type / year / sources still open, so it shows a numbered confirmation menu (see `references/search_menu.md` §4.1–§4.3):
📚 Literature search — ready
Detected so far: Topic: diabetes · Type: all · Year: unspecified
Still to confirm: 1) literature type 2) year range 3) safety bias 4) data sources
Reply with a number to choose, or say "default" to use the recommended config.

### Example 7 · Vague request → clarifying questions (grill-me style)
**You say:**
Find me something about that new cancer drug.

**Assistant replies (sketch):**
Topic is ambiguous, so it asks back (max 2 rounds, then falls back to defaults + a preview reminder — search_menu.md §6):
"Which drug exactly? e.g. osimertinib, pembrolizumab, or a target like PD-1?"
Once you name it, it pins the topic and proceeds to the preview confirmation.

### Example 8 · Fetch legal open-access PDFs on request
**You say:**
From the report you just made, try to fetch legal open-access PDFs for the top 10 cited works.

**Assistant replies (sketch):**
Pulling DOIs/PMIDs for those 10 from the works in your report, then resolving each against legitimate OA sources (Unpaywall, Europe PMC, PubMed Central). It reports back which resolved and which did not — e.g. "7/10 resolved; 3 have no legal OA copy (paywalled — use your library / interlibrary loan / corresponding author)". Resolved links are written to `lit_report_oa_pdfs.md` (or appended to the report). This is opt-in and does **not** bypass any paywall.

**⏱ Cost note** — a 10-work batch adds ~20–40s and a little extra API usage; a 50-work batch adds 1–3 min.

---

## What Can It Do — Scenarios

The skill covers published-evidence retrieval across the clinical-trial lifecycle. Each row gives the typical **situation** and a line you can **copy verbatim** under "Try saying".

### ① Published-evidence search (OpenAlex, primary)
| Situation | Try saying in chat |
|:---|:---|
| Evidence on a drug / disease / method | "Find systematic reviews on osimertinib in NSCLC" |
| Recent literature with a year filter | "Papers on CAR-T in lymphoma since 2020" |
| A topic with a safety angle | "Post-marketing safety literature for drug X" |

### ② Broader / deeper coverage (optional sources)
| Situation | Try saying in chat |
|:---|:---|
| MEDLINE / MeSH biomedical precision | "Also search Europe PMC for this topic" |
| Citation-ranked relevance | "Rank these by citation count via Semantic Scholar" |

### ③ Output formats & exports
| Situation | Try saying in chat |
|:---|:---|
| Excel deliverable | "Export the literature as an Excel file" |
| Self-contained HTML report only | "Just the HTML report, skip Excel" |
| Import into **Zotero** (reference manager) | "Export as Zotero RIS / CSV" — get `zotero.ris` / `zotero.csv`, import into the Zotero desktop app or browser connector |
| Browse as an **Obsidian** knowledge graph | "Export to Obsidian" — get one Markdown note per paper + a `Literature MOC.md` index; open the folder as a vault to see the paper network |

### ④ Evidence verification & provenance (P0, default ON)
| Situation | Try saying in chat |
|:---|:---|
| Verify every DOI/PMID is real (anti-hallucination) | "Verify the citations are real before you report" |
| Also confirm title/author match the paper (v0.6.11) | "Make sure the DOI actually points to this paper" |
| Trace where each hit came from | "Show me the evidence provenance / source log" |
| Verify only the top-N works (fast large searches) | "Just verify the top 15 citations" |
| Skip verification (faster, preview-only) | "Don't verify citations this time" |

### ⑤ Key / setup
| Situation | Try saying in chat |
|:---|:---|
| Lift the OpenAlex rate limit | "How do I raise the rate limit?" |
| Check what's configured | "What keys does the skill currently see?" |

> The sibling skills are described in their own READMEs; ordinary users only need to say what they want in plain language — the skill routes the right sources and writes the report.

---

## First-Time FAQ

**Q: Do I need a key to run?** A: No. OpenAlex keyless pool = 100 credits/day (enough for small searches); a free key lifts it to 100k/day. Europe PMC and Semantic Scholar need no key.

**Q: Where does my query go?** A: Your topic query and filters are sent to the public bibliographic APIs — OpenAlex, Europe PMC, and Semantic Scholar (when enabled). No confidential or sponsor data is ever sent.

**Q: What's the difference from `ct-safety`?** A: `ct-literature` = published *qualitative* evidence (papers / reviews / case reports); `ct-safety` = structured FAERS disproportionality (PRR / ROR / IC). They are explicitly distinct data types — literature complements but does not replace FAERS.

**Q: On a Chinese system, is the output in Chinese?** A: Yes. Output language follows your OS setting by default (Chinese on a Chinese-OS, English otherwise), and you can force-switch anytime with one sentence (e.g. "switch to English").

**Q: Semantic Scholar keeps failing / being skipped?** A: The S2 key requires a manual form review (not auto-issued, waits after applying), so it is usually absent short-term. When no key is configured the source is **skipped entirely** (no network request) rather than attempting-and-degrading. Configure it later if you need citation ranking.

**Q: How long does a search take? What are the rate limits?** A:
- **Typical latency:** Enabled sources run **in parallel with each other** (one worker per source), but **each source pages serially** — requests inside a source are chained one after another, because parallel paging would raise rate-limit / ban risk (e.g. on the OpenAlex keyless pool). Europe PMC ~1s/page, OpenAlex ~2s/page, so the wall-clock is the *slowest* source, not the sum. A 3-source search pulling ~50 works typically finishes in **10–30 seconds** (plus ~1–4 min more when full citation verification is on — see the pre-run time estimate). Adding preprints (bioRXiv/medRXiv/arXiv) adds a few seconds more.
- **Result cap:** Default `max_results` is **30 works per source**; there is no hard ceiling (raising it is allowed), but time and API usage scale linearly. **Measured 2026-08-14** (two sources, `osimertinib ILD`): `--max 100` → fetch+merge **~20 s**, full verification **~78 s** (≈0.64 s/work after cross-source dedup, which keeps **~62%** of fetched works with two sources). **Suggested ceiling for a ~5-minute run: 300 works per source with two sources, ~250 with three sources** (either way ≈370–380 unique merged works; dedup is automatic, so 3×250 does not mean 750 in the report). Beyond that total time grows ~linearly — for very large harvests, configure an OpenAlex key and use `--verify top 15` instead of pushing `max_results`.
- **Rate limits:**
  - **OpenAlex (keyless):** 100 credits/day (since 2026-02-13). A single multi-page search can use 5–20 credits. A free key lifts this to **100k/day**.
  - **Europe PMC:** No hard key limit, but please keep request frequency reasonable (no tight loops).
  - **Semantic Scholar (no key):** Prone to HTTP 429; the skill skips it entirely when no key is configured.
- **Tip:** Start with the default sources (OpenAlex + Europe PMC) and a modest `max_results`; only enable extra sources if you need broader coverage.

**Q: Why can't the fetch be faster?** A: Because the skill only uses the **official public access methods each site provides** (their public APIs / endpoints) and **never violates any site's terms or policies** — it fetches politely, source by source, page by page, so it cannot deliver the "crawl a huge dataset in minutes" effect of an aggressive scraper. Concretely: (1) **Different sources already run in parallel** (one worker per source) — adding more cross-source parallelism won't help. (2) **Each source must page serially** — the public bibliographic APIs (OpenAlex keyless pool, Europe PMC polite pool) throttle or ban clients that fire many parallel requests; serial paging is what keeps you under the ban radar. (3) If a run feels slow, the usual bottleneck is **full citation verification** (default ON; one or more HTTP lookups per work) — switch to `--verify top 15` or `--verify none` to cut ~1–4 minutes. (4) Keep `max_results` moderate — time and API usage scale linearly with it. Bulk PDF fetching is the other multi-second-per-work operation (each request follows a redirect chain).

**Q: Can I search in Chinese?** A: Partially — the skill auto-translates Chinese topics to English through **bundled offline dictionaries** (~900 entries: medical terms + drug INN names + brand names like 泰瑞沙→Tagrisso/osimertinib + MeSH synonyms; no network call) before querying the APIs, and the report banner shows the original and the translation as `中文 → English`. Equivalent names are combined with boolean OR to widen recall (e.g. `osimertinib OR Tagrisso`, `lung cancer OR pulmonary neoplasm`). Terms the dictionaries do not cover pass through as-is (recall may suffer) and a notice lists the unmapped ones — you can extend the dictionaries yourself by adding entries to `references/user_terms.json` (same `{中文: "English"}` format, values may be a list of synonyms; the file is git-ignored so your additions are never published). For best recall, use English terms — especially for rare conditions or novel compounds.

**Q: Why don't you support Chinese domestic databases (e.g. CNKI / 知网)?** A: Deliberately not supported, for three reasons. (1) **Marginal value** — this skill targets the publicly retrievable international evidence base (OpenAlex / Europe PMC / ...); the incremental coverage of Chinese-only databases is small, and much of their content overlaps or is already indexed internationally. (2) **No compliant channel exists** — CNKI and similar Chinese databases **do not offer public APIs to individuals** (only to contracted, paying institutions), and they aggressively block — and have sued — web crawlers; automated retrieval would have neither a legal interface nor a defensible risk posture, violating this skill's rule of "official public access only, never breach a site's terms". (3) **ROI** — paying that compliance/legal risk for marginal coverage is not worth it. If you need a specific Chinese paper, search CNKI yourself and export the citation (RIS / BibTeX) for your records.

**Q: Can the skill download full-text PDFs?** A: Yes — in two ways. (1) The Excel and HTML reports always include an **"Open Access"** column with a direct link to a free PDF when one is available from the publisher or repository (typically 60–80% of recent works); paywalled papers show "—". The skill does **not** bypass paywalls or download copyrighted content — for a paywalled paper, use your institution's library, interlibrary loan, or contact the corresponding author. (2) On request, the skill can also actively fetch the legal open-access PDFs for a given set of works:
- **What it does:** Given a DOI or PMID, it resolves an OA PDF URL from legitimate sources (Unpaywall, Europe PMC, PubMed Central).
- **Cost warning:** Each request is at least one HTTP lookup plus a redirect chain to the PDF; a 50-work batch adds **1–3 minutes** and consumes extra API credits (OpenAlex/Europe PMC).
- **No guarantee:** Many papers have no legal OA copy — the skill reports which ones resolved and which did not.
- **How to ask:** Provide a specific DOI/PMID list (e.g., from your report) and say "try to fetch legal OA PDFs for these".

---

## Security & Privacy

### Safe Preview (local computation)
- **Runs locally:** The normalize / report / Excel rendering steps run entirely on your machine — no code is executed on any remote server beyond the bundled scripts.
- **Traceable, not fabricated:** Every factual claim in the report carries a source label (`sources` list per work) or an `⚠️ needs official verification` marker; it never fills evidence gaps with fluent prose.
- Outputs are for reference only; validate against official sources before regulatory submissions.

### Outbound & Privacy
- **Bibliographic search (public APIs only):** your topic + filters go to **OpenAlex** / **Europe PMC** / **Semantic Scholar** (only the sources you enable), plus **doi.org** and **Crossref** during citation verification. No confidential / sponsor data is ever sent.
- **Bug reports (opt-in, user-confirmed):** `adapters/bug_report.py` sends an **11-key sanitized envelope** (skill / version / error_type / description / … — never raw data or subject records) to `https://ct-bugreport.coze.site/run` **only after you explicitly confirm** a two-stage prompt; without cloud access it falls back to a local file.
- **Keys stay on your machine:** keys are read from your local `ct-literature/.env` and never ship with the package (only `.env.example` ships). Apply for your own OpenAlex key at <https://openalex.org/settings/api> and configure it yourself via §7 (`.env` / env var / `--openalex-key`); never commit `.env` to a repo. (The assistant can write the key into `.env` for you on request — stored locally, never echoed or logged.)

---

## Advanced Reference (Developers)

CLI helpers, runtime requirements, the architecture tree, and the unified work-mode schema have moved here so everyday users don't need them. See [`SKILL.md`](SKILL.md) and [`CHANGELOG.md`](CHANGELOG.md) for the agent-facing spec and version history.

### Runtime & requirements
| Item | Requirement |
|---|---|
| Runtime | Python 3.11+ (CPython). The pipeline uses **only the Python standard library** (`urllib`) for HTTP — **no third-party dependency is required**. |
| Keys (optional) | OpenAlex free key (recommended for scale); Semantic Scholar key optional (lifts ~1 req/s limit). Both via `.env` / env var / `--openalex-key`. |
| Sibling skills | `ct-registry` (trial registries), `ct-safety` (FAERS), `ct-pipeline` (intel brief) — ct-literature seeds topics and is seeded by them; all install from GitHub. |

### Optional tool · English→Chinese abstract term-annotation (`abstract_translator.py`)
A small standalone CLI that annotates English text with Chinese glosses for matched medical terms — **term-level substitution, not full-text translation** (unmatched words stay in English). It is **not** part of the retrieval pipeline; run it on demand on a text or file:

```bash
# annotate a text snippet
python scripts/abstract_translator.py --text "Osimertinib is a third-generation EGFR-TKI used in NSCLC."
# annotate a file (e.g. an abstract), output ASCII or JSON
python scripts/abstract_translator.py --file abstract.txt --format ascii
python scripts/abstract_translator.py --file abstract.txt --format json --output out.json
```

Output shows the original and the annotated version (e.g. `randomized controlled trial` → 【随机对照试验】, `NSCLC` → 【非小细胞肺癌】, `overall survival` → 【总生存期】). The dictionary is a bundled offline EN→ZH medical-terms list (~130 entries, study types / trial-design / statistics) plus English entries from the shared `term_map.json`; no network call. For fluent full-sentence translation, use a general translation service instead.

### Architecture
```
ct-literature/
├── SKILL.md                 # agent-facing spec (English body)
├── CHANGELOG.md             # version history
├── adapters/                # one fetcher + verifier per public API
│   ├── fetch_openalex.py    # primary source
│   ├── fetch_europepmc.py   # MEDLINE/MeSH (on by default)
│   ├── fetch_semantic_scholar.py  # optional citation rank (skippable)
│   ├── fetch_preprints.py   # bioRxiv / medRxiv
│   ├── fetch_arxiv.py       # arXiv
│   ├── fetch_prospero.py    # PROSPERO (reserved, dormant until token set)
│   ├── http_utils.py        # shared retry / headers / key load
│   └── verify_citations.py  # P0 citation verification + title/author consistency
├── scripts/
│   ├── ct_literature.py     # orchestration: fetch → normalize → verify → report/export
│   ├── normalize.py         # multi-source merge + dedupe
│   ├── score_relevance.py   # relevance scoring
│   ├── screen_prisma.py     # deterministic PRISMA title/abstract screen
│   ├── export_xlsx.py       # Excel deliverable (ct-base excel_style)
│   ├── export_html.py       # self-contained HTML report
│   ├── format_citations.py  # APA/Nature/Vancouver/IEEE/GB7714 + BibTeX/RIS
│   ├── evidence_log.py      # provenance audit trail (evidence_log.json/.md)
│   ├── obsidian_exporter.py # Obsidian notes + MOC
│   ├── zotero_exporter.py   # Zotero RIS/CSV
│   ├── i18n.py              # bilingual single source of truth
│   └── excel_style.py, …             # shared style (ct-base vendor)
├── references/              # SOP, key setup, search menu, multi-db method
└── assets/icon.svg          # B-tier logo
```

### CLI examples (developers)
```bash
# Primary (OpenAlex, no key)
python scripts/ct_literature.py --topic "osimertinib" \
    --review-type systematic-review --year-from 2018 --safety --run --out-dir ./out

# Add Europe PMC (MeSH) + Semantic Scholar (citation rank)
python scripts/ct_literature.py --topic "osimertinib" \
    --with-europepmc --with-semantic-scholar --run --out-dir ./out

# Recommended (zero extra flags): put the key in the skill .env, then just run
cp .env.example .env          # edit .env -> OPENALEX_API_KEY=your_key
python scripts/ct_literature.py --topic "osimertinib" --safety --run --out-dir ./out

# P0 · citation verification (default ON) + evidence log are automatic under --run.
# Scope it with --verify {all|top|none}; source-aware skip avoids redundant same-source
# re-resolution (a paper from OpenAlex/Europe PMC is trusted by provenance).
python scripts/ct_literature.py --topic "osimertinib" --run --out-dir ./out
# Best speed/coverage balance for large result sets: verify only the top-20 by rank
python scripts/ct_literature.py --topic "osimertinib" --run --verify top --verify-top-n 20 --out-dir ./out
# Disable verification explicitly with --no-verify-citations (== --verify none).
python scripts/ct_literature.py --topic "osimertinib" --run --verify none --out-dir ./out
# v0.6.11 · skip the title/author consistency layer (verification still resolves identifiers)
python scripts/ct_literature.py --topic "osimertinib" --run --no-consistency --out-dir ./out
# v0.7.0 · stream progress as NDJSON events on stdout (agent-facing: --progress json
# redirects sub-module prints to stderr, so stdout stays parseable; events:
# run_start / source_done / source_failed / fetch_done / verify_progress / verify_done /
# evidence_log / export_done / export_failed / run_done, one JSON object per line, flushed)
python scripts/ct_literature.py --topic "osimertinib" --run --progress json --out-dir ./out
# v0.7.0 · two-phase delivery: unverified report in seconds, verification backfills later
python scripts/ct_literature.py --topic "osimertinib" --run --verify background --out-dir ./out

# P1 · PROSPERO systematic-review registry (opt-in, reserved source — dormant until a token is set)
python scripts/ct_literature.py --topic "osimertinib" \
    --with-prospero --prospero-token "$PROSPERO_API_TOKEN" --run --out-dir ./out
```

### Unified work mode (output schema)
```
{
  source, id, title, authors, year, publication_date, publication, journal_iso,
  type, study_type, cited_by_count, url, open_access_url,
  pmid, pmcid, doi,
  abstract_snippet,                           # full text, not truncated
  mesh, concepts, keywords, funders,
  language, is_retracted, is_safety,
  volume, issue, page,
  affiliations,                               # Europe PMC only
  sources,                                    # contributing source list
  # --- attached by P0 verification (verify_citations.py) ---
  citation_verified,                          # bool
  citation_verify_status,                     # verified | bot_blocked | mismatch |
                                              #   unresolved | no_identifier | suspicious | unverified_sampled
  citation_verify_note,                       # human-readable detail
  citation_consistency,                       # bool | None  (v0.6.11)
  citation_title_ratio                       # float | None  (normalized title similarity)
}
```

---

**Version**: v0.9.0 | **License**: MIT | **Authors**: medstatstar, phoe-zip

For feature requests, bug reports, or other feedback, feel free to contact the author directly at medstatstar@gmail.com (Wintone Zhang / 张文彤).

---

## Confidentiality Notice

> The CT series consists of 20+ specialized domain skills, organized into two tiers — A, B — by "confidential-data-exfiltration risk + whether external retrieval is needed", providing full coverage of the entire new-drug clinical trial (Clinical Trial) lifecycle.
>
> - **Tier A (non-confidential · public)**: takes only ordinary (non-confidential) input; runs fully locally (`network=off`) or performs public retrieval (`network=public-retrieval`, e.g. ct-registry / ct-advisor) — never involves confidential information. Tier A skills are published openly on GitHub.
> - **Tier B (confidential · internal)**: involve strictly confidential clinical-trial data and internal information from pharma sponsors (e.g., ct-analysis, ct-sdtm, ct-eligibility); Tier B is processed locally (`egress=none`, data never leaves the machine) or requires approved egress (`egress=approval-req`, e.g. ct-eligibility). These skills are designated for internal enterprise use only and are not publicly released at present.
>
> If you do have a genuine need for these confidential skills, please contact the author to request custom installation.
>
> 📧 Contact: medstatstar@gmail.com (Wintone Zhang / 张文彤)
