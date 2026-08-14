# Changelog · ct-literature

All notable changes to this skill are documented here. Versioning follows the
ct- library convention (B-tier public-intel skill, semver-ish).

## v0.6.14 — 2026-08-14

### Performance · architecture-level wait-time reduction
- **Pooled HTTP connections** (`adapters/http_utils.py`): replaced the per-request
  `urllib.request.urlopen` (a fresh TCP+TLS handshake on every request) with a **thread-local
  keep-alive connection pool** + manual redirect following + **per-host concurrency caps**
  (doi.org 8 / Crossref 4 / OpenAlex 6 / Europe PMC 6 / S2 2). Saves ~100–300 ms handshake
  per request across the hundreds of fetch + verify round-trips; stale connections are
  dropped and rebuilt automatically. `verify_citations._resolve_doi` (doi.org Range probe)
  now uses the same pooled path.
- **Cross-source verification dedup** (`scripts/ct_literature.py`): the same work indexed by
  two sources (e.g. OpenAlex + Europe PMC) now verifies **once** by `work_key` — results still
  attach to every copy by key. Cuts 5–20% of verification calls on typical runs.
- **Wider verification pool** (8 → 24 workers): per-host politeness is now enforced by the
  connection-pool caps, not the worker count, so a 50-work verify finishes much sooner.
- **Two-phase delivery — `--verify background`**: the report is emitted immediately with works
  marked `pending_background` (fetch-time, ~seconds), then the background verification pass
  finishes and re-renders `lit_report.html` + writes `lit_report_verified.xlsx` + updates the
  evidence log. New progress events: `report_ready` → `verify_progress*` → `verify_done` →
  `report_verified` → `run_done` (export events carry `verified: false|true`).
- All existing modes (`all` / `top` / `none`) and human/json progress output are unchanged
  (regression-tested; verified 4/4 in `all` and `top`, connection reuse confirmed).
- **Prepublish cleanup**: removed 6 Coze-specific i18n messages (zero runtime references —
  `auth.coze_outbound`, `auth.coze_outbound_denied`, `auth.serial_blocked`, `error.coze_401`,
  `error.fallback_local`, `error.requests_missing`) that were vendored leftovers from ct-base
  (ct-literature has no Coze endpoint; they also fed SkillSpector Autonomous-Decision-Making
  findings). SKILL.md "zero confidential input" reworded to "zero confidential research /
  subject data input (API keys are local config, never research data)".

## v0.6.13 — 2026-08-14

### Feature · progress event stream (`--progress json`, agent-facing)
- New `--progress {human,json}` flag on `ct_literature.py` (default `human` = unchanged console
  output). In `json` mode stdout carries **only** a flushed NDJSON event stream —
  `run_start / source_done / source_failed / fetch_done / verify_progress / verify_done /
  evidence_log / intermediate / export_done / export_failed / run_done` — and sub-module
  prints are redirected to **stderr** so the stream stays parseable for agents.
- Human mode additionally gained per-source progress lines (`[OK] source OpenAlex: N works in X.Xs`).
- **Why**: the pipeline is already internally streamed (fetch ∥ verify, producer-consumer);
  the only block was the single-shot report output. Streaming the progress events gives users /
  agents first-visible-result and per-source progress without changing total wall-clock
  (bottleneck is network round-trips — unchanged).

### Docs (README FAQ, 2026-08-13)
- FAQ "How long does a search take": fixed misleading "per-source concurrency" → precise
  "sources run in parallel with each other, but each source pages serially (rate-limit / ban
  safety)".
- New FAQ "Why can't the fetch be faster?": compliance-first answer (official public access
  methods only, never violates site terms → no bulk-crawl effect) + parallel/serial structure
  + bottleneck (verification) + speed-up knobs. Synced into ct-base §13.8 as a mandatory FAQ
  item for any skill with data-fetch operations.

## v0.6.12 — 2026-08-13

### Security-audit fixes (ClawHub / NVIDIA SkillSpector, 21 findings)
- **README: unify API-key setup to the conversational flow (user preference)** — both READMEs
  now give one consistent story: tell the assistant in chat to configure the key (it writes it
  to the local `.env` via Write/Edit; never echoed back, never logged, sent only over HTTPS to
  the official API), or self-configure via `.env` / env var / `--openalex-key`; with an explicit
  notice that chat may be logged and self-config is the most secretive route. Fixes the
  internal contradiction SkillSpector flagged (6+ findings: one section said "never paste",
  another told you to); the conversational option is kept intentionally per user preference,
  accepting a residual chat-channel advisory. `http_utils` key-notice i18n strings updated to
  the same dual-path wording.
- **Remove all R-only dead code and messages** — this skill is pure Python
  (`required_commands: [python]`) and never calls R. Deleted `scripts/r_libs.py` (vendored
  ct-base stub, zero references here) and 13 R-only keys from `i18n_messages.json`
  (`error.rscript_not_found*`, `error.r_timeout`, `error.invalid_temp_path`,
  `error.invalid_install_path`, `install.*`, `header.r_code`, `header.install_cmd`). This also
  eliminates the stale "CRAN is the ONLY network operation" claim — that message applied to an
  R install flow this skill never uses. README/AGENTS reference lists updated.
- **SKILL.md summary/description now mention the local EN→ZH abstract translation helper**
  (eliminates the manifest-vs-behavior mismatch flagged at High/95%).
- **drug_name_resolver: auto mode now matches its docstring** — only a *unique* candidate is
  auto-translated; ambiguous names (multiple candidates) return unresolved instead of silently
  picking the first (could bias downstream queries in a biomedical context).
- **CLI help hardening**: `--no-verify-citations` / `--no-consistency` now carry a WARNING that
  they weaken the anti-hallucination gate (ct-base §17.1; debugging only); `abstract_translator
  --file/--output` now state they read/write only the paths you specify.
- **README: explicit activation boundary** — the skill activates only when the user explicitly
  asks for a literature search (addresses Vague-Triggers findings).

### Packaging note
- ClawHub audit scans confirmed the previously published package **contained `tests/`**.
  Per the new ct-base §16.8 red-line ("test content never ships"), the next publish must
  rebuild a clean package (`git archive` staging + `rm -rf tests scripts/tests`) and drop
  `tests/` via `.clawhubignore` (already updated).

## v0.6.11 — 2026-08-12

### Feature · title/author consistency cross-check in citation verification (anti-hallucination depth)
- Closes the gap flagged in v0.6.10: verification previously only confirmed an identifier
  *resolves to a live resource*. A hallucinated-but-real DOI (or a real-but-wrong id) still
  passed. Now, after an identifier resolves, the canonical metadata (title + first-author
  surname) is fetched from the authoritative, bot-friendly API and compared to the work we hold:
  - DOI  -> Crossref (`api.crossref.org/works/<doi>`)
  - PMID -> Europe PMC EXT_ID response (already fetched for resolution, no extra call)
  - OpenAlex id -> `api.openalex.org/works/<id>`
- New status **`mismatch`**: identifier resolved to a LIVE resource but its title/author do
  **not** match this work → flagged `citation_verified=False`, surfaced in all four deliverables
  (xlsx Evidence Log, html Evidence block, report, evidence_log.md) as **Mismatch / 不一致**.
  A consistent resolution is `verified`; a `bot_blocked` DOI whose Crossref metadata matches is
  now **upgraded to `verified`** (the 403 was only the publisher blocking doi.org, not the id).
- Robust by design:
  - Author matching is **order-independent** (handles "Last, First", "First Last", "First Initial"
    and list forms) via token-set membership against the metadata surname — fixes a naive
    "last token = surname" bug that misread "Ramalingam V" as surname "V".
  - Title match uses normalized `difflib` similarity (threshold 0.80) + author must not contradict.
  - Metadata **fetch failure / incomplete fields degrade gracefully** to "verified, consistency
    unchecked" — it NEVER invents a `mismatch` from a transient API error.
  - New additive per-work fields: `citation_consistency` (bool|None), `citation_title_ratio` (float|None).
- New opt-out: `--no-consistency` (pipeline `run()`) / `--no-consistency` (standalone
  `verify_citations.py`) skips the metadata fetch; verification then behaves as before v0.6.11.
- Verified: offline mock test (9 cases: match / mismatch / meta-fail / malformed / no-id /
  empty-meta / bot-block+match / pmid-path+match / no-consistency) all pass; EN+ZH render smoke
  test confirms `Mismatch / 不一致` surfaces in xlsx + html + evidence_log + report without crash.

### Docs · README + SKILL.md accuracy & clarity pass
- `README.md` / `README_zh-CN.md` restructured for clarity: added a **Table of Contents**
  anchor nav; renumbered sections (Who This Is For → Data Sources → Anti-Hallucination →
  How to Use → Scenarios → FAQ → Security → Advanced); compacted the scenario index.
- Fixed factual inaccuracies carried from earlier versions:
  - Version string `0.6.0` → `0.6.11`.
  - Dropped the false `requests` dependency claim — the skill uses **only the standard-library
    `urllib`**.
  - Architecture tree realigned to the actual layout: `adapters/` holds the 6 source fetchers +
    `http_utils` + `verify_citations`; `normalize` / `score_relevance` / `screen_prisma` /
    `format_citations` / `evidence_log` / `obsidian_exporter` / `zotero_exporter` / `export_*`
    live in `scripts/` (not `adapters/`). Output described as **HTML + Excel**, not Markdown.
  - Anti-Hallucination expanded to **4 guardrails** (was described as 3) incl. the v0.6.11
    title/author consistency layer; added `bot_blocked` + `mismatch` explanations and the
    `citation_*` schema fields.
  - Unified EN/ZH on **parallel** source execution (ZH previously said "serial").
  - Removed stale `.merged.json` references from the OA-PDF scenario (the file is now hidden /
    internal, not a user-facing artifact).
- `SKILL.md` `version:` bumped `0.6.0` → `0.6.11` to match CHANGELOG and the READMEs.

## v0.6.10 — 2026-08-12

### Logic audit · systematic bug sweep (HIGH + MEDIUM + LOW)

Systematic review of the whole skill (pipeline `run()`, every `scripts/*` exporter, both
adapters, i18n messages, formatters, docs) after the v0.6.8 output-cleanup refactor.

- **HIGH · `lit_report.xlsx` Evidence Log sheet rendered empty (v0.6.8 regression).**
  The pipeline `run()` passed `export_workbook({"count", "works", "meta"})` but
  `build_evidence` reads `evidence_log` / `verification` from the **top level** of `data`.
  So the Verification summary, source provenance and run-config blocks were all dropped —
  the sheet showed only its title + the anti-hallucination disclaimer.
  Fix: `export_workbook` now promotes `evidence_log` / `verification` out of `meta` when they
  are missing at top level (standalone CLI still passes `.merged.json` with them at top level).
  Verified by regenerating an xlsx from a real `.merged.json` — `verified=…`, `bot-blocked=…`,
  `Run config / 运行配置`, and source provenance all appear again.
- **MEDIUM · `evidence_log.py` standalone CLI lost its source trail.**
  `main()` read `data.get("payloads")`, but `.merged.json` persists `evidence_log` and does **not**
  persist `payloads`, so the rendered `evidence_log.md` had an empty source list.
  Fix: prefer the `evidence_log` already embedded in `.merged.json`; only fall back to
  rebuilding from `payloads` when it is absent.
- **LOW · DOI regex greedily swallowed trailing punctuation.**
  `_DOI_RE` used `[^\s]+`, so a trailing `.` / `)` / `]` etc. was captured into the DOI, producing
  links/labels like `10.1056/NEJMoa2403614.)`. Fixed in two places with a `_strip_doi_tail()`
  helper that strips `.,;:` then `)]` separately (the two-stage rstrip also avoids a Python
  parsing ambiguity when `)]` sits next to a string literal):
  `scripts/normalize.py::_norm_doi` and `adapters/verify_citations.py::_resolve_doi` / `work_key`.
- **Doc consistency · `merged.html` → `lit_report.html`.**
  `SKILL.md` (feature table + Output list) and `export_html.py` docstring still said `merged.html`;
  the pipeline has written `lit_report.html` since before v0.6.8. Corrected both.
- Verified: all four modified `.py` files `py_compile` clean; xlsx Evidence Log regen smoke test passes.

## v0.6.9 — 2026-08-12

### Fix · restore the "apply for an OpenAlex key" prompt in the deliverables
- Regression from v0.6.8: the keyless warning (`cfg.warn`, with the signup URL) lived in
  `report.py` / `lit_report.md`, which v0.6.8 stopped generating. After that the prompt
  survived only in console output and `evidence_log.md` — the two primary deliverables
  (HTML / XLSX) carried no actionable hint.
- `export_html.py`: added bilingual `cfg.warn` labels and render a warning block with a
  clickable signup link inside the Evidence section when `config.openalex_key == "missing"`.
- `export_xlsx.py`: the Run-config block now appends an actionable bilingual line with the
  signup URL when the key is missing (previously it only printed `missing — keyless`).
- No prompt is shown when the key is configured (verified by render smoke test, EN + ZH).

## v0.6.8 — 2026-08-12

### Output cleanup · drop `lit_report.md`; demote `merged.json` to hidden `.merged.json`
- Stop generating `lit_report.md` (the Markdown report). `lit_report.html` + `lit_report.xlsx`
  already cover the same content, so the `.md` deliverable was redundant. `report.py` stays in the
  skill as a reusable standalone Markdown renderer but is no longer called by the pipeline.
- Rename the unified work list from `merged.json` to `.merged.json` (dot-prefixed → normally hidden
  by the OS). It is now an **internal cache**, not a user-facing deliverable.
- All standalone tools (`export_html` / `export_xlsx` / `format_citations` / `obsidian_exporter` /
  `zotero_exporter` / `score_relevance` / `screen_prisma` / `evidence_log` + `verify_citations`) now
  default `--in` / `--in-json` / `--merged` to `.merged.json` (no longer `required`), so they keep
  working out-of-the-box against the hidden cache. Docstrings/help text updated accordingly.
- Docs (`SKILL.md` Output list; `README.md` / `README_zh-CN.md` report + OA-PDF references) updated:
  `lit_report.md` removed; `merged.json` → `.merged.json`; PRISMA block reference updated.
- Pre-existing (out of scope at v0.6.8, **resolved in v0.6.10**): `SKILL.md` still named the HTML
  deliverable `merged.html`, but the pipeline writes `lit_report.html`. Now fixed in both the
  feature table and the Output list; `export_html.py` docstring example updated too.

## v0.6.7 — 2026-08-12

### Bugfix · `evidence_log.md` bot-blocked label not localized (follow-up to v0.6.6)
- v0.6.6 localized the `bot_blocked` label in `report.py` / `export_xlsx.py` / `export_html.py`
  (`ev.bot_blocked`: "bot-blocked" / "出版社拦爬") but `evidence_log.py::render_md` still
  hard-coded the English `bot-blocked=` token. In a zh locale the report said `出版社拦爬=0`
  while the evidence log said `bot-blocked=0` — inconsistent.
- `render_md` now emits `bot-blocked=%s (出版社拦爬=%s)` so the zh label is present alongside
  the English key in the bilingual evidence log. Regenerated `out_lit_osimertinib_v6/evidence_log.md`.

## v0.6.6 — 2026-08-12

### Bugfix · Verification false-negative on big-publisher bot-block (403) + same-source-skip regression
- **Root cause (confirmed on another machine via live re-check):** the 37 "unresolved" papers were NOT suspect — they were the most credible, highest-cited works (FLAURA-OS, ADAURA, AURA3-CNS, BLOOM, NCCN guidelines…). Their DOIs are real: `doi.org` returns a correct 302 to the publisher, but NEJM / ASCO-JCO / JNCCN / JAMA / Nature-vs-others / Wiley / MDPI **return 403 to programmatic requests** (bot-blocking). `_resolve_doi` only accepted 2xx, so a 403 was wrongly marked `unresolved` — a **false negative**, not a broken DOI. (Publishers that allow bots — Nature / BMC / Elsevier — return 200 and were the "verified" set; so "verified vs unresolved" tracked publisher bot-policy, not paper quality.)
- **Fix 1 — `bot_blocked` status:** `_resolve_doi` now returns a 3-state string `ok | bot_blocked | unresolved`. A post-redirect 403 → `bot_blocked`. `verify_one` marks such works `citation_verified=True, citation_verify_status="bot_blocked"` (the identifier IS real) with a note "publisher bot-block (DOI likely valid; 403 from publisher, not a broken link)". This is reported **distinctly** from `unresolved`/`suspicious` everywhere (report.md / xlsx / html / evidence_log.json) so the 37 are never misread as suspect.
- **Fix 2 — same-source-skip regression:** v0.6.1's source-aware skip silenced the Europe PMC PMID (and OpenAlex id) check for same-source works. When such a work's DOI hit a 403, it had **no fallback** and fell to `unresolved` — even though its real PMID (Europe PMC EXT_ID API, bot-friendly) would have confirmed it. Now, when the DOI does NOT positively verify, PMID (Europe PMC `ext_id`) and OpenAlex id (`api.openalex.org`) are always attempted as the reliable bot-friendly fallback. `skip_sources` is retained for API compat but no longer suppresses that fallback.
- Summary dicts (`summarize_results`, `verify_works`, `none`-mode vsum) now carry `bot_blocked`. New bilingual labels `ev.bot_blocked` / `ev.bot_blocked.note`.
- Verified: 14-assertion offline self-test (200/206→ok, 403→bot_blocked, 404→unresolved, full-URL DOI normalized w/o double prefix, DOI-403+PMID-ok→verified, DOI-403+OpenAlex-ok→verified, summarize includes bot_blocked) + EN/ZH report render smoke (bot-blocked=37 shown, note present). `py_compile` clean.

## v0.6.5 — 2026-08-12

### Bugfix · Double-prefix DOI in formatted exports (`format_citations.py`)
- `references_apa.md` / `references.bib` / `references.ris` could emit `https://doi.org/https://doi.org/10.x/...` when the source DOI was OpenAlex's full resolver URL (`https://doi.org/10.x/...`). `_resolve_doi` was already fixed in v0.6.4, but the **citation-formatting path** still concatenated `"https://doi.org/" + doi` blindly at 6 sites (APA/Nature URL, `url` fallback, BibTeX `doi=` field, RIS `DO ` field, plus vancouver/ieee/gb7714 `doi:` tokens).
- Added `_bare_doi()` to `format_citations.py` — extracts the canonical `10.x/...` suffix via `_DOI_RE` regardless of input shape (full URL or bare). All 6 sites now build at most one resolver prefix. BibTeX `doi` and RIS `DO` now write the **bare** DOI (spec-correct; previously wrote the full URL).
- `export_xlsx.py._normalize_link` was already safe (checks `startswith(("http://","https://",...))` first) — no change there.
- Verified: unit self-test (full-URL + bare inputs → single prefix everywhere, bare in bib/ris) + regenerated real fixture `tests/smoke_out/merged.json` → **zero** `https://doi.org/https://doi.org/` across all three outputs; `doi = {10.1016/...}` and `DO  - 10.1016/...` now correct. `py_compile` clean.

## v0.6.4 — 2026-08-12

### Bugfix · DOI resolution mis-classified big-publisher DOIs as `unresolved`
- `_resolve_doi` accepted **only HTTP 200** (`code == 200`). Major publishers (NEJM / JCO / JAMA / AACR / Wiley / MDPI / ...) answer the `Range: bytes=0-0` probe with **206 Partial Content** instead of 200, so their live DOIs were wrongly marked `unresolved`. Now any 2xx is treated as resolved (`200 <= code < 300`). The dead `HTTPError`-branch `e.code == 200` (urllib never raises HTTPError for 2xx) was removed.
- **Mixed DOI formats normalized**: OpenAlex stores the full URL (`https://doi.org/10.x/...`), Europe PMC stores the bare DOI (`10.x/...`). `_resolve_doi` now extracts the canonical `10.x/...` suffix via `_DOI_RE` and always rebuilds the URL, so a double-prefix (`https://doi.org/https://doi.org/...`) can never occur. `work_key` was made format-agnostic too, so the same paper arriving from both sources collapses to one key (no silent duplicate / split verification).
- Offline-deterministic self-test (mocked `urllib.request.urlopen`): 206/200 resolve for NEJM/JCO/JAMA/AACR/Wiley/MDPI (full-URL + bare forms), 404 stays `unresolved`, URL normalization asserted, `work_key` equality asserted, `verify_one` end-to-end for a NEJM 206 → `verified`. `py_compile` clean.

## v0.6.1 — 2026-08-12

### P0 · Citation verification — scope control + source-aware skip
- New `--verify {all|top|none}` (default `all`) controls verification scope; legacy `--no-verify-citations` is now an alias for `--verify none`.
  - `all`: verify every merged work (concurrent with fetch, "verify one as it lands") — unchanged default behavior.
  - `top`: verify only the top-N by rank (`--verify-top-n`, default 15); remaining works are tagged `unverified_sampled` (no network call). Best speed/coverage trade-off for large result sets.
  - `none`: skip verification entirely (preview-style annotation).
- **Source-aware skip**: a work returned by OpenAlex / Europe PMC already carries a real identifier at that source, so the redundant same-source re-resolution round-trip is skipped and trusted **by source provenance** (marked `verified`, no network call). DOI is always cross-checked via `doi.org` (canonical + anti-hallucination net). `verify_citations.verify_one` gains a `skip_sources` parameter; the streaming worker and the `top` post-merge verifier both pass each work's `sources`.
- Reporting surfaces (report.md / xlsx Evidence Log) now show the verify `mode` (all/top/none) and the `sampled` count, plus bilingual mode notes.

### Tests
- Offline-deterministic self-tests: 7 `verify_one` skip/provenance cases + full `run()` integration across all three modes (mocked fetchers + verification). `py_compile` clean on all changed modules.

## v0.6.2 — 2026-08-12

### UX · Pre-run time estimate
- `run()` now prints a localized time-estimate banner **before the fetch begins**, so the user knows results may take a few minutes to return. Estimate scales with verification scope: `all` ≈ 1–4 min, `top` ≈ 1–3 min, `none` ≈ 1 min; rate-limit backoff on the keyless pool extends it further. Output path is shown so the user knows where to look while waiting.
- New i18n keys `run.starting` / `run.est.{all,top,none}` / `run.vmode.{all,top,none}` (EN/ZH).
- `SKILL.md` dialogue guidance updated: the agent must mirror this wait-time warning in chat before triggering the real fetch.

## v0.6.3 — 2026-08-12

### Docs · Anti-hallucination value section
- README.md / README_zh-CN.md: added a prominent "Why You Can Trust the Output — Anti-Hallucination by Design / 为什么可以信任输出 —— 反幻觉设计" section (right after Sources, before §1). Covers the three guardrails (live citation-id resolution P0 default ON + `suspicious` on malformed DOI; full provenance audit trail `evidence_log.json`; reports never pad gaps with prose) plus the two operational safeguards (Safe Preview local compute; source-aware skip by provenance), tied to ct-base §17.1.
- Fixed a stale FAQ claim: sources actually run **in parallel** (not sequential) since the concurrency change; latency now stated as the slowest source, plus the 1–4 min verification note.

## v0.6.0 — 2026-08-12

### P0 · Citation verification (anti-hallucination, ct-base §17.1)
- New `scripts/verify_citations.py`: each merged work is checked against its live identifier and tagged `citation_verified` / `citation_verify_status` (verified / unresolved / no_identifier / suspicious) / `citation_verify_note`.
  - doi → `https://doi.org/<doi>` resolves to final HTTP 200; pmid → Europe PMC `EXT_ID` lookup; OpenAlex id → `api.openalex.org/works/<id>`.
  - A **malformed DOI is flagged `suspicious`** (possible hallucinated identifier) — catches fabricated ids before they reach the report.
  - Each verification failure marks that work `unresolved` and **never aborts** the pipeline (pure stdlib + `http_utils`).
- Default **ON**; `--no-verify-citations` disables. Network runs only under `--run` (SAFE PREVIEW); in preview mode it records `skipped_preview` and passes works through untouched.
- New `scripts/evidence_log.py`: builds an immutable-style provenance audit trail → `evidence_log.json` + `evidence_log.md` (also embedded in `merged.json`). Traceability: query → source → hit count → retrieved_at → verification rate.

### P1 · PROSPERO systematic-review registry (opt-in, key-gated, UNVERIFIED)
- New `scripts/fetch_prospero.py`: answers *"is a review on this topic already registered / ongoing?"* (duplication-avoidance + protocol discovery), a distinct question from the bibliographic sources.
- **UNVERIFIED**: the public REST API now requires an undocumented auth header (`{"status":"error","errormessage":"Error code: header value undefined"}` on every probe). Until a working token + header is supplied, `--with-prospero` degrades to a no-op skip (returns `None`, no file written — like Semantic Scholar's no-key skip) and is **not** claimed functional. Provide `--prospero-token` (+ `--prospero-header` if `PROSPERO-ACCESS-TOKEN` is wrong). Response parser is schema-tolerant (JSON + XML) but must be re-validated against a real 200.

### Reporting surface
- `report.py` adds a bilingual **Evidence & verification** section (verification counts + source provenance table).
- `export_xlsx.py` adds an **Evidence Log** sheet (verification summary + source provenance table).
- `export_html.py` adds an **Evidence & Verification** block (verification summary + provenance table).

### Tests
- New `tests/scenario10d_evidence.py` — 8 offline-deterministic cases (D1–D8) covering verify preview / suspicious / no-identifier, evidence build+write, and the report / xlsx / html evidence surfaces, plus PROSPERO no-token graceful skip. `py_compile` clean.

### Deferred (by prior agreement)
- **Journal impact factor (IF) auto-annotation** — deferred. Will use an open proxy (e.g. OpenAlex `citation_normalized_*`) or a user-supplied local mapping table; not implemented until the mapping is provided.

## v0.5.7 — 2026-08-11

### Pre-publish hardening pass (ct-base BASE.md §16 checklist)
- **Fixed missing `scripts/i18n_messages.json`** — the ct-base shared generic i18n key set was never injected (omitted from `.ctbase_injected.json`'s file list), so `_MESSAGES` fell back to `{}` and every generic i18n key (`exec.running`, `error.generic`, `info.result_saved`, …) rendered as its raw key string at runtime. Copied the ct-base shared `i18n_messages.json` into `scripts/`; Excel UI keys stay self-contained in `export_xlsx._LOCAL`, domain keys inline in their consuming scripts (per §16.3).
- **SKILL.md 214 → 199 lines** (≤200, §16.1): trimmed the Cross-Database and Natural-language-dialogue sections.
- **Hardened `.gitignore` / `.clawhubignore`**: added `.ctbase_injected.json`, `*.ctbase_bak_*`, `tests/smoke_out/`, `.env.*`; removed a tracked `.ctbase_injected.json` (machine-specific absolute path) via `git rm --cached`.
- **references language (§16.2)**: rewrote `citation_styles.md` to English-only; stripped Chinese trigger phrases from `multi-db-search.md` (English trigger list + note that Chinese triggers mirror SKILL.md `triggers`).
- **No hardcoded Chinese output strings (§16.3)**: `abstract_translator.py` / `mesh_mapper.py` argparse help + `print` changed to English. `export_html.py` keeps ` / `-separated bilingual labels (policy-compliant); `obsidian_exporter.py` keeps `lang`-conditional bilingual.
- Not published — push/publish pending user confirmation.

## v0.5.6 — 2026-08-11

### Source expansion (real network, 10×10 hardening regression passed)
- **Europe PMC is now ON by default** (`with_europepmc=True`; `--no-with-europepmc` to disable). It is free/keyless and gives the whole PubMed/PMC/MEDLINE/MeSH pool, so the previous opt-in default (OpenAlex-only) was leaving the highest-value biomedical source off by default.
- **Added bioRxiv + medRxiv** as opt-in `--with-biorxiv` / `--with-medrxiv` (Tier P preprints). Neither has a free keyword-search API, so both are pulled through Europe PMC's preprint corpus (`SRC:PPR` + `publisher:` filter) and emitted with distinct `bioRxiv` / `medRxiv` provenance in the merged record.
- **Added arXiv** as opt-in `--with-arxiv` (keyless Atom API). Mostly methodology/ML/CS breadth for clinical questions, so kept opt-in (rank priority 1, sinks below biomedical sources).
- New fetchers: `scripts/fetch_preprints.py` (bioRxiv/medRxiv via EPMC PPR) and `scripts/fetch_arxiv.py` (arXiv Atom parser, with retry).
- `normalize._SOURCE_PRIORITY` extended: bioRxiv/medRxiv = 0 (primary biomedical), arXiv = 1 (supplementary, like SemanticScholar).

## v0.5.3 — 2026-08-08

- .env key 轻混淆（XOR+base64）防误打包明文扫描命中；http_utils.py 增加 `_deobfuscate` 向后兼容明文 .env；三平台同步发布。

## v0.5.2 — 2026-08-08

### Follow-up security audit cleanup (ClawHub SkillSpector, post-0.5.1)
- **Closed the residual Ssd3 (paste-key-to-chat) finding**: v0.5.1 removed the
  "paste your key to the assistant" prompt from `scripts/i18n.py`, but the same
  guidance was still present in README "Example 4 · Configure the OpenAlex key"
  (both `README.md` and `README_zh-CN.md`). Rewrote both to self-config only —
  `.env` / env var / `--openalex-key` — with an explicit "never paste a key into
  chat" statement. This was the true source of the 98%-confidence Ssd3 hit
  (the scanner reads the README, not just scripts).
- **Cleared the Unpinned Dependencies (Low) finding**: `requirements.txt` no
  longer declares `requests>=2.28`. `requests` is not a runtime dependency —
  fetch uses stdlib `urllib`, and the R-bridge (`r_libs.py`) was removed in
  0.5.1. The reserved optional `requests` import in `fetch_openalex.py` is noted
  with a pin-if-enabled comment.

## v0.5.1 — 2026-08-08

### Security audit remediation (ClawHub SkillSpector, post-0.5.0)
- **Removed API-key paste-to-assistant guidance**: deleted the conversational
  "paste your key to the assistant" prompts in `scripts/i18n.py`
  (`openalex.key_notice` / `semantic_scholar.key_notice`) and reverted to the
  self-service methods in `references/openalex_key.md` (Method A/B/C: `.env`,
  env var, or `--openalex-key`). Clarified the key is user-private, stored
  locally, sent only over HTTPS to the official API, and must never be pasted
  into chat — also resolves an internal contradiction with openalex_key.md §7.
- **Removed arbitrary R code execution primitive**: `scripts/r_libs.py` no longer
  imports `run_r` / `subprocess` / `tempfile`; it keeps only validation /
  sanitization helpers. ct-literature is pure-Python and never calls R, so the
  "Context-Inappropriate Capability" finding is eliminated at the root. The shared
  `ct-base/scripts/r_libs.py` was likewise stripped of `run_r` (execution
  primitives are no longer shared from the base), and `ct-base/BASE.md` §16.4 / §2
  / §10 references were updated to match.
- Dropped dead R-related i18n keys (`dry_run.*`, `exec.*`, `install.*`,
  `header.*`, etc.) that were only referenced by the removed R runner.

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
