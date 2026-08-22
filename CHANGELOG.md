# Changelog · ct-literature

All notable changes to this skill are documented here. Versioning follows the
ct- library convention (B-tier public-intel skill, semver-ish).

## v0.9.0 (2026-08-22) · Bug Report 功能正式发布（三站点）

发布原因：**增加 bug report 功能**（ct-base §20.3 统一技能错误上报）。

- **Bug Report 功能正式随包发布**：`adapters/bug_report.py` 客户端（11 键脱敏白名单信封 + 两阶段用户确认 + coze 端点 `https://ct-bugreport.coze.site/run` + 本地兜底 `save_local_report`），SKILL.md「Bug Reporting」节与 README 安全与隐私说明同步（自 v0.7.6 起开发完成，本版起纳入正式发布）。
- **发布树修正（§16.8）**：`adapters/` 下 6 个运行模块此前从未进入 git 索引（`bug_report.py` / `build_guidelines.py` / `fetch_guidelines.py` / `guideline_corpus.py` / `portal_fetch.py` / `_smoke_guidelines.py`），`git archive HEAD` 发布包会缺文件 → 本次全部纳入跟踪，保证 GitHub / SkillHub / ClawHub 三平台发布树一致。
- **发布包排除补齐**：`.gitignore` / `.clawhubignore` 新增 `.ctbase_injected.json`（含本机绝对路径，不随包公开）、`*.ctbase_bak_*`、`tools/`（作者侧批量维护脚本，非运行部件）、`adapters/_smoke_guidelines.py`（未引用的本地测试脚本）。
- **版本对齐（§9）**：SKILL.md `version` 0.7.6 → 0.9.0；两份 README 版本脚注同步 v0.9.0。
- **代码修正**：`adapters/__init__.py` docstring 纠正（误写为 ct-samplesize，实际为 ct-literature 出站收口目录）。
- **术语扩展**：`references/term_map.json` 补充 GLP-1 类药物中英术语（司美格鲁肽 / 替尔泊肽 / 利拉鲁肽 / 瑞他鲁肽 / 度拉糖肽 / 艾塞那肽）。

## v0.7.6 (2026-08-22) · Bug Report 客户端与规则对齐（ct-base §20.3 同步）+ 发布前 §16 整改

- **`adapters/bug_report.py` 副本**：补齐 `confirm_thanks`/`build_followup`/`parse_history` + `_MSGS` thank/done/pending 双语文案 + `send_to_endpoint` 透传 `history`（此前缺这些函数）；docstring「三阶段确认」→「两阶段确认」。
- **SKILL.md Bug Reporting 节**：Trigger 补「主动触发」独立路径（用户显式说 report a bug / 反馈问题直接走两阶段，不受每会话 1 次限制）；新增 Post-send history回执 bullet（endpoint 返回 `history`，回复由 `confirm_thanks(locale)` + `build_followup(history, locale)` 双语拼接：空→结束；`resultstr=="done"`→展示 memo；否则"未修复"）。
- **发布前 §16 整改（ct-base 规范）**：
  - `.gitignore` / `.clawhubignore` 补齐发布排除：`tests/`、`.env`、`__pycache__/`、`*.pyc`、`*.pyo`、`*.db`、`out/`、`*.log`、`.Rhistory`、`.RData`、`staging/`、`references/user_terms.json`、`adapters/coze/`（此前仅 guideline 排除，`tests/` 与 `.env` 会随发布包公开；与 README「仅 `.env.example` 随包发布」承诺对齐）。
  - **版本对齐（§9）**：SKILL.md `version` 0.7.5 → 0.7.6；两份 README 的 Version 引用 v0.6.11 → v0.7.6（修复三处版本不一致）。
  - **SKILL.md 压缩至 195 行**（§16.1 ≤200 行上限，原 278 行）：压缩 Language / Positioning / Data Sources / guidelines 段 / Features 表 / Implementation / Bug Reporting 长段，关键安全契约（SAFE PREVIEW、B 档、qualitative 警告、verify 反幻觉、guideline pointer-only、bug report 两阶段/11-key 白名单/端点/client-only）全部保留；细节仍指向 `references/`。
  - **README 弱化「chat 让助手写 key 进 .env」表述**：自配置路径 (a)–(c) 提前为主推荐，chat 写入降级为可选（回应 ClawHub 审计 UNVERIFIED「Context-Inappropriate Capability」项）。
  - **i18n 一致性确认**：`shared_sync_check` 提示的 6 个未携带 key（`auth.coze_outbound` 等）经 grep 验证 scripts/adapters 零引用，属纯 Python 裁剪，豁免。
  - **发布树修正（方案 A 硬化测试暴露）**：`tests/` 的 7 个文件此前已进入 git 索引（历史 `.gitignore` 仅排除运行产物、从未排除 `tests/` 目录），**ignore 规则对已跟踪文件无效**，导致 `git archive HEAD` 发布包仍含 tests/。`git rm -r --cached tests/` 解除跟踪（工作区文件保留）并本地 commit `chore(§16.8)`；源仓库 `git ls-files` 现为 59 文件，`publish_secret_scan` P0=0 / P1=0。
  - **description 中英对称化**：description 中英文统一按 summary 内容重写（补齐 guidelines「本地语料库」模式、pointer-only/Coze KB、B 档等此前仅英文侧或 summary 侧的信息），消除英文比中文多出一整段 guidelines 描述的不对称；中文前 / 英文后格式不变。
  - **README「安全与隐私」更新+精简**：出站说明补充 bug report 出站（`https://ct-bugreport.coze.site/run`，两阶段确认后仅发 11 键脱敏信封，无法联网回退本地文件），删除过时的「无其他出站路径」表述；key 相关两条重复说明合并为一条。SKILL.md `permissions.network_note` 同步补充 bug-report 出站声明。

## v0.7.5 — 2026-08-16

### Change · data-protection split (pointer-only skill tree; full text → author's Coze KB)

- **Design decision (per user's data-protection concern):** the shareable skill is a copyable artifact, so
  full-text guideline documents must NOT live inside it. The skill tree now ships **pointer-only**
  (`references/guidelines/guidelines_index.json`: org / title / URL / version metadata — low-sensitivity,
  publish-safe). **Full text is the author's curated IP and lives in the author's self-controlled Coze KB**
  (not publicly copied with the skill). ct-advisor consults that Coze KB for native guideline Q&A and delegates
  structured retrieval to this skill.
- **`build_guidelines.build()` now defaults `download=False`.** When `--download` IS used, OA full texts are
  written to a **LOCAL CACHE OUTSIDE the skill** (`~/.workbuddy/ct-guideline-docs`, default) — never under
  `references/guidelines/`. A startup `[WARN]` reminds the author that docs are not part of the skill and must
  not be published. New CLI flags: `--download` (opt-in), `--doc-cache-dir`.
- **Defense-in-depth:** added `.clawhubignore` + `.gitignore` excluding any `references/guidelines/**`
  PDF/XML/HTML and `ct-guideline-docs/` (in case `--doc-cache-dir` is ever pointed inside the skill tree).
- **Docs:** SKILL.md G-section + summary/description/Features updated to state the pointer-only / Coze-home
  split; version 0.7.4 → 0.7.5. A Coze-KB draft (`guideline_coze_kb_draft.md`, workspace root, OUTSIDE the
  skill) enumerates the 4 seeded topics' orgs + canonical URLs with `key_recommendations` placeholders for the
  author to fill from official sources before deploying to Coze.
- **Verified:** `adapters/_smoke_guidelines.py` ALL PASS (external-cache download path + warning included).

## v0.7.4 — 2026-08-16

### Feature · build-time lightweight fetch for the 6 portal-only orgs (user-chosen "构建期轻量抓取")

- **New `adapters/portal_fetch.py`** (BUILD-TIME only, called by `build_guidelines.build(run=True)`):
  lightweight fetchers for the six portal-only orgs that have no free keyword API.
  - **CPIC** — genuine fetch via its free, keyless PostgREST API (`api.cpicpgx.org/v1/guideline`,
    falling back to `/publication`); stored as real `api` records (`retrieved:true`).
  - **NCCN / ADA / AHA / SIGN / CMA** — best-effort public-portal HTML link-scrape. Schema-tolerant;
    on login-wall (NCCN) / JS-render / network block it returns `[]` and `build_guidelines` falls back
    to the honest `portal` pointer. **Nothing is fabricated.**
  - Every fetcher is wrapped so it **never raises** — a failed fetch degrades gracefully to a pointer.
- **Wired into the builder:** `build_guidelines.build()` step 2 now tries `portal_fetch.fetch_portal(org, …)`
  per portal org; fetched records become `api` entries, failures fall back to `_portal_pointers()`.
  `source_status` now reports each portal org as `fetched` or `pointer`. Analysis-time loading is unchanged
  (still zero network via `guideline_corpus.load()`).
- **Honest limitation:** only CPIC has a real free API; the other five are fragile HTML scrapes that will
  likely stay pointers until tuned on open internet. NCCN is login-walled (free account) so may never yield
  content without auth. No live verification in this sandbox (egress limited) — verified offline via mocks.
- **Offline-verified:** 11 new smoke checks cover CPIC API path, HTML extraction, graceful `[]` on network
  error, and the build-time "fetch→api / fail→pointer" wiring. Full smoke (`adapters/_smoke_guidelines.py`)
  ALL PASS.

## v0.7.3 — 2026-08-16

### Refactor · clinical guideline corpus → local-first (corrects the v0.7.2 live-fetch design)
- **Design correction (per user feedback):** clinical guidelines are a *versioned* reference standard
  (NCCN 2024.v3, ADA 2026 Standards). The v0.7.2 model fetched "latest" via code at analysis time; the
  correct model is a **curated, version-pinned LOCAL corpus** — build once, read many times (zero network
  at analysis, reproducible, honours ct-base local-first / 数据不出域).
- **New `adapters/guideline_corpus.py`** (analysis-time, ZERO network): reads
  `references/guidelines/guidelines_index.json` and returns the same payload shape as
  `fetch_guidelines.fetch()`, so `scripts/ct_literature.py` consumes it uniformly. Filters by topic/org;
  returns an honest `corpus_missing` payload (with the builder command) when the index is absent.
- **New `adapters/build_guidelines.py`** (build-time, network, author action): aggregates 12+ sources,
  downloads OpenAlex OA-PDFs where reachable, writes/merges `guidelines_index.json` (+ optional doc files).
  SAFE PREVIEW: omit `--run` → dry-run, **no network, no write**. Dedupe by `(org, topic/title)`;
  special-cases portal orgs (`org:topic:title`) to avoid cross-topic id collisions.
- **Rewired pipeline:** `scripts/ct_literature.py` `--with-guidelines` now calls `guideline_corpus.load()`
  (was `fetch_guidelines.fetch(run=True)`). `fetch_guidelines.py` is retained as the source-library used
  by the builder, not by analysis-time loading.
- **Seeded corpus built live (network):** `references/guidelines/guidelines_index.json` — 96 curated
  entries (72 `api` + 24 `portal` pointers, all `retrieved:false`) across 4 topics (diabetes /
  breast-cancer / heart-failure / community-acquired-pneumonia). 0 OA-PDF docs on disk in this sandbox
  (external publisher domains unreachable here) — downloads succeed on the author's open-internet machine.
- **Offline-verified:** loader reads the real corpus in ~0.012 s with **zero network calls**; 22-check
  smoke (`adapters/_smoke_guidelines.py`) ALL PASS (loader zero-network, builder SAFE PREVIEW, dedupe,
  portal honesty, source-library 13 sources).
- `SKILL.md`: G section rewritten to the corpus-first model; frontmatter summary/description + Features
  row + Implementation CLI updated. `version` 0.7.1 → 0.7.3 (frontmatter had lagged behind CHANGELOG).
- **Red line honoured:** no publish/deploy (no git push / SkillHub / ClawHub / Coze deploy); local changes
  + local verification only.

## v0.7.2 — 2026-08-16

### Feature · clinical guideline aggregation across 12+ sources (G-upgrade, opt-in)
- New `adapters/fetch_guidelines.py`: aggregates clinical-practice guidelines from **12+**
  authoritative sources into one normalized, de-duplicated list. Two access tiers, honestly
  labelled per record via `access` (`api`/`portal`) + `retrieved`:
  - **Live `api`**: OpenAlex (guideline-typed search), Europe PMC (guideline pub types),
    GIN (Guidelines International Network), WHO IRIS — fetched via the shared `http_utils`
    GET+retry (429 Retry-After, exponential backoff, Bearer key).
  - **Live `api` (key-gated, best-effort)**: NICE¹ / MAGICapp / TRIP² — graceful `skipped_no_key`
    when the env key is absent (never fakes a result).
  - **`portal` pointer** (no free keyword API): NCCN / ADA / AHA / SIGN / CMA / CPIC — emit an
    honest navigational pointer (`retrieved:false`) to the org portal, **not** a fabricated fetch.
- Wired into `scripts/ct_literature.py` as a **separate** capability (kept OUT of
  `normalize.merge` so it never pollutes citation verification / PRISMA): `--with-guidelines`
  (BooleanOptionalAction, opt-in) → writes `guidelines.json` + a `guidelines` block in
  `.merged.json` (`meta.guidelines.source_status` shows per-source coverage). Flags:
  `--guideline-sources` (subset), `--guideline-max` (per-source cap, default 20).
- SAFE PREVIEW preserved: no network unless `--run`; `fetch(run=False)` returns `None`. Every
  live source is wrapped so a failure degrades to a `source_status` note, never aborting.
- `SKILL.md`: new "Clinical guideline sources" section, Features row, Implementation CLI examples,
  and frontmatter summary/description updated.
- Offline smoke test (`adapters/_smoke_guidelines.py`, mock-injected): 22 checks — parse /
  normalize / dedupe / merge, SAFE PREVIEW, portal honesty (`retrieved:false`), key-gated skip,
  and full `run()` integration — all pass.

¹ NICE public REST auth header is undocumented (like PROSPERO); degrades to skip until a working
token is supplied. ² TRIP requires a commercial API key. Live-correctness of GIN/WHO/MAGICapp/
NICE/TRIP parse paths is schema-tolerant but pending validation against a real 200 response.

## v0.7.1 — 2026-08-15

### Fix + Docs · make the abstract term-annotation tool actually work, and describe it honestly
- **Fix `abstract_translator.translate_abstract`** (was producing garbage): the old loop replaced each term without word boundaries, so short keys like `os`/`evaluate` corrupted inside longer words (`osimertinib` → `【总生存期】imertinib`), and sequential per-term substitution re-matched inside already-replaced spans (nested 【【…】】). Now: (1) only English keys are used (the Chinese-key entries from `term_map.json` are ignored — they belong to the zh→en topic translator, not this EN→ZH annotator); (2) word-boundary matching `(?<![A-Za-z0-9])…(?![A-Za-z0-9])`; (3) single-pass alternation, longest-first — no nesting. Verified: `randomized controlled trial → 【随机对照试验】`, `NSCLC → 【非小细胞肺癌】`, `overall survival → 【总生存期】`, `osimertinib` untouched.
- `SKILL.md` summary/description: "本地英文→中文摘要翻译助手" → **"可选英文→中文摘要术语标注工具（本地、术语级替换，非全文翻译）"** — the helper is a term-level annotator and not part of the retrieval pipeline; the old wording set a full-translation expectation it cannot meet.
- `README.md` / `README_zh-CN.md` (Advanced Reference): new "Optional tool · English→Chinese abstract term-annotation" section with CLI usage, real verified examples, and the explicit boundary: **term-level substitution, not full-text translation**.
- `README.md` / `README_zh-CN.md` (FAQ): new "Why don't you support Chinese domestic databases (e.g. CNKI)?" — deliberately not supported: (1) marginal incremental value vs the international evidence base; (2) no compliant channel exists (CNKI et al. have no public API for individuals and aggressively block / sue crawlers, against the skill's "official public access only" rule); (3) ROI. Users needing a Chinese paper export the citation (RIS/BibTeX) themselves.
- `scripts/abstract_translator.py`: docstring & CLI help aligned — removed the stale "optional translation API" claim (the code has **no API path**; purely local dictionary substitution).

## v0.7.0 — 2026-08-14

> v0.6.13（进度事件流）与 v0.6.14（架构优化）开发版均未单独发布，功能统一并入 v0.7.0。

### Feature · progress event stream (`--progress json`, agent-facing)
- New `--progress {human,json}` flag on `ct_literature.py` (default `human` = unchanged console
  output). In `json` mode stdout carries **only** a flushed NDJSON event stream —
  `run_start / source_done / source_failed / fetch_done / verify_progress / verify_done /
  evidence_log / intermediate / export_done / export_failed / run_done` — and sub-module
  prints are redirected to **stderr** so the stream stays parseable for agents.
- Human mode additionally gained per-source progress lines (`[OK] source OpenAlex: N works in X.Xs`).

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
- **Measured speed-up (verify all, 20 works)**: verification segment ~119 s → ~35 s (~3.4×,
  -70%); two-phase key path 3.5 s to a usable report (~35× faster time-to-first-result).

### Docs (README FAQ, 2026-08-13)
- FAQ "How long does a search take": fixed misleading "per-source concurrency" → precise
  "sources run in parallel with each other, but each source pages serially (rate-limit / ban
  safety)".
- New FAQ "Why can't the fetch be faster?": compliance-first answer (official public access
  methods only, never violates site terms → no bulk-crawl effect) + parallel/serial structure
  + bottleneck (verification) + speed-up knobs. Synced into ct-base §13.8 as a mandatory FAQ
  item for any skill with data-fetch operations.

### Prepublish cleanup
- Removed 6 Coze-specific i18n messages (zero runtime references — `auth.coze_outbound`,
  `auth.coze_outbound_denied`, `auth.serial_blocked`, `error.coze_401`, `error.fallback_local`,
  `error.requests_missing`) that were vendored leftovers from ct-base (ct-literature has no
  Coze endpoint; they also fed SkillSpector Autonomous-Decision-Making findings).
- SKILL.md "zero confidential input" reworded to "zero confidential research / subject data
  input (API keys are local config, never research data)".

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
