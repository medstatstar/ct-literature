# Clinical Trial Literature Search (ct-literature)

[🇨🇳 中文](./README_zh-CN.md) | [🇺🇸 English (Current)](#)

<div align="center">
<img src="assets/icon.svg" width="240" height="240" alt="ct-literature logo"/>
</div>

> **A `ct-` library skill (A-tier public-intel — non-confidential input) that retrieves published scholarly literature about a drug / disease / method, normalizes multiple public bibliographic sources into one de-duplicated evidence base, and surfaces the evidence landscape plus a CSM (cumulative safety monitoring) qualitative subset.**

> No commands or manual needed. Just describe your literature question **in plain language inside a chat** — the skill fetches from **OpenAlex (primary) + Europe PMC (on by default) + bioRxiv/medRxiv (on by default)**, then writes a self-contained **HTML + Excel** report. (Semantic Scholar and arXiv are opt-in via flags, not part of the default pipeline.) A-tier (non-confidential input): fully local computation, only public retrieval. **Note: your topic query is sent to the public bibliographic APIs below — see the [outbound notice](#outbound--privacy).** The skill activates **only when you explicitly ask for a literature search**; it never retrieves on its own during unrelated conversations.

> 💡 **Keyless by default, but a free key lifts the cap a lot:** OpenAlex has required an API key since 2026-02-13; without one you are in the keyless pool (100 credits/day, flagged *not suitable for production*). A free key lifts this to 100k/day. Apply in ~30s — see the [First-Time FAQ](#first-time-faq) and the key-notice the skill prints automatically when no key is detected.

## Table of Contents

- [Who This Is For](#who-this-is-for)
- [How to Use It in a Chat](#how-to-use-it-in-a-chat)
- [Data Sources](#data-sources)
- [Why You Can Trust the Output — Anti-Hallucination](#why-you-can-trust-the-output--anti-hallucination)
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

## How to Use It in a Chat

ct-literature is a **conversational skill**: you simply tell the assistant what you want to look up — no commands, no parameter names to remember. Once installed as a WorkBuddy skill, you invoke it in a chat via the Skill tool; there is no extra setup, but it activates only when you call it.

Below are 7 real conversational examples ordered from simple to advanced. Each shows **"You say"** and **"The assistant replies"**, plus how the report is produced. Replies are **key excerpts** of the real interaction (progress lines and details compressed); whenever your decision is needed, the skill lists the options **on screen for click-to-confirm**, or asks you to say "default / go ahead". The primary deliverables are a self-contained **`lit_report.html`** (offline, printable) and **`lit_report.xlsx`**. By default the workbook has **3 data sheets: Overview → Literature master → Evidence Log** (plus a README cover). The **Safety-related** sheet is opt-in — it appears only when you add `--safety` (the CSM qualitative subset), since the safety/CSM literature subset is a safety-oriented concern, not a default deliverable of every literature search.

### Example 1 · A simple literature search (with preview confirmation)
**You say:**
> Search published literature on osimertinib in NSCLC, 2018–2025, focused on adverse events / post-marketing safety.

**Assistant replies (excerpt):**
> Recognized as a **simple request** (topic + year + safety angle all clear) → straight to a preview for your confirmation:

| Setting | Value |
|---|---|
| Topic | osimertinib + NSCLC (synonym family AZD9291 / Tagrisso / 奥希替尼 merged automatically) |
| Years | 2018–2025 · safety focus ✅ |
| Sources | OpenAlex + Europe PMC + preprints (default three) · 50 works per source |
| Verification | all (anti-hallucination, default ON) |

Confirmed → keyword list reviewed → search runs (~30–60 s):
> Done: **103** de-duplicated unique works (3 sources); **81 safety-related**. Citation verification 100/103 passed. Report written to `lit_report.html` and `lit_report.xlsx` (Literature master + Safety-related sheets).

**📌 No key needed** — OpenAlex keyless pool covers a small search; the skill fetches and writes the report directly.

### Example 2 · Evidence-synthesis layer only (systematic reviews / meta-analyses)
**You say:**
> Same topic, but keep only systematic reviews and meta-analyses — I want the synthesis, not single trials.

**Assistant replies (excerpt):**
> Restricting `--review-type systematic-review/meta-analysis` and re-searching. **3 systematic reviews hit** (after cross-source de-dup) — listed separately with full abstracts and citation verification. If a type has zero hits, the skill says "no works of this type" rather than padding with near-matches.

**📌 Safety subset vs FAERS is a key distinction:** `--safety` (CSM qualitative subset = published case reports / PV articles) and `ct-safety` (structured FAERS signal detection, PRR / ROR / IC) are **clearly different data types** — literature complements but does not replace FAERS.

### Example 3 · Broader coverage (Europe PMC + Semantic Scholar)
**You say:**
> Also pull MEDLINE via Europe PMC and citation-rank via Semantic Scholar.

**Assistant replies (excerpt):**
> Adding `--with-europepmc` (MeSH precision) and `--with-semantic-scholar` (citation ranking). S2 is skipped automatically if no key or on 429 — OpenAlex + Europe PMC still produce results.

### Example 4 · Configure the OpenAlex key (self-config)
**You say:**
> How do I lift the 100/day limit for large searches?

**Assistant replies (excerpt):**
> Apply for a free key (~30s) at <https://openalex.org/settings/api>. Configure it yourself via (a) adding `OPENALEX_API_KEY=<key>` to `ct-literature/.env`, (b) exporting an `OPENALEX_API_KEY` environment variable, or (c) passing `--openalex-key <key>` on the command line. **Note:** chat messages may be logged or retained by the platform — for maximum secrecy use the self-config routes (a)–(c). If you prefer, you can also ask the assistant to write the key into `ct-literature/.env` for you — it stores the key locally, never echoes it back, never logs it, and sends it only over HTTPS to the official OpenAlex API.

**With a key, retrieval is faster AND your key never leaves your machine:** the key enters OpenAlex's keyed pool (~100k credits/day, rarely 429'd), and the OpenAlex / Semantic Scholar sources switch to **local direct-connect retrieval, bypassing the cloud** — your key is used in local memory only to call the official APIs and is never sent to any third-party service. Only keyless users go through the cloud channel (OpenAlex anonymous pool; Semantic Scholar auto-skipped).

### Example 5 · Complex request → parameter confirmation (menu / card style)
**You say:**
> I want to look into diabetes treatment literature.

**Assistant replies (excerpt):**
> Triage → **Complex** (topic = diabetes is clear, but key parameters — **literature type / year / sources** — are still open). The skill does not decide for you; it lists what it detected and asks you to confirm two things on screen:

> Detected: topic `diabetes treatment` ｜ To confirm: ① **Literature type** (all types [recommended] / systematic reviews + meta-analyses only / SR + RCT + case reports…) ② **Run now?** (✅ run / ✏️ adjust parameters / ❌ cancel)
> Not sure about the differences? Say "explain the differences between these choices in detail" — it explains the clinical / statistical meaning first, then you decide.

After parameters are confirmed there are **two more gates** before any network call: ① **keyword confirmation** — the expanded keyword list (e.g. `diabetes mellitus`, Chinese/English synonym families) is shown for your review; ② **preview confirmation** — the same settings table as Example 1; the search only runs after you approve.

**📌 Note:** Simple requests (topic + ≥2 parameters clear) skip the confirmation menu and go straight to preview (Example 1); Vague requests use grill-me clarification (Example 6).

### Example 6 · Vague request → bounded clarifying questions (grill-me style)
**You say:**
> Find me something about that new cancer drug.

**Assistant replies (excerpt):**
> Triage → **Vague** ("that new drug" cannot be pinned down) → asks back with **bounded grill-me (max 2 rounds)**, each round with a recommended default; if it is still unclear it falls back to defaults + a preview reminder:

> **Round 1:** "Can't recall the name — that's fine. Which **class** is it? A 3rd-gen EGFR-TKI (e.g. osimertinib), an immune-checkpoint inhibitor (e.g. pembrolizumab), or a target (PD-1 / EGFR)? Or paste the brand name / indication and I'll reverse-look it up."
> You: osimertinib, the lung-cancer one.
> **Round 2 (narrowing scope):** "Locked to osimertinib. Should the cancer type be limited to **NSCLC**? (default: yes). Any year range or safety angle? (none → last 5 years, all types)"

After the two rounds the skill gives a **need profile + recommended settings** for confirmation: "topic osimertinib + NSCLC ｜ last 5 years ｜ all types ｜ default three sources" — approve to move to preview; if still unclear it runs with defaults and flags that in the preview.

### Example 7 · On-demand batch download of legal open-access PDFs
**You say:**
> Download the PDFs of the 40 most recently published works in the report, and log how long it takes.

**Assistant replies (excerpt):**
> Takes the newest 40 works from the 103-work merged set (sorted by publication date, newest first) and starts the batch download — **before starting it tells you the expected pace**:

> Starting batch download of 40 PDFs: **roughly 10–20 s per paper** (network / rate limits vary) — please be patient, no action needed.

Downloading routes automatically: **OA / preprint direct links download locally first** (Frontiers, MDPI, PMC author manuscripts, …); only items that cannot be fetched locally but carry an OA/preprint signal go through the cloud decode chain; paywalled works with no legal copy are not forced. On completion it reports honestly:

> Done: **36/40** succeeded, took **853 s (14.2 min)**. PDFs saved to `pdfs_latest40/`; **the Excel report now has the「PDF 本地路径」column updated** (36 absolute paths + 3 "failed" markers).
> ⚠️ The 4 missing are all paywalled (NEJM / JCO / BMJ) — get them via your library or the authors; the skill never bypasses a paywall.

**⏱ Pace:** roughly 10–20 s per paper (incl. rate-limit backoff + cloud decode); a 40-work batch runs ~10–15 min — that is normal wait, not a hang; single direct-connect papers (Frontiers-class) usually finish in 3–5 s.

---

## Data Sources

| Source | Key | Role |
|---|---|---|
| OpenAlex | recommended (free key; keyless = 100/day since 2026-02-13) | **Primary** — broad, citation-rich |
| Europe PMC | no key | **On by default** (`--no-with-europepmc` to disable) — MEDLINE/MeSH biomedical precision |
| Semantic Scholar | key recommended (manual form review) | **Opt-in only** `--with-semantic-scholar` — citation ranking; **not part of default sources**, skipped unless explicitly enabled with a key |
| bioRxiv | no key (via Europe PMC PPR) | **On by default** (`--no-with-biorxiv` to disable) — biomedical preprints |
| medRxiv | no key (via Europe PMC PPR) | **On by default** (`--no-with-medrxiv` to disable) — medical/clinical preprints |
| arXiv | no key | Optional `--with-arxiv` — physics/CS/ML methodology breadth |
| PROSPERO | token required (undocumented auth header) | Optional `--with-prospero` — systematic-review registry / protocol discovery; **reserved source**, degrades to a no-op skip until a working token + header is supplied |

### How the sources fit together

The default trio — **OpenAlex (primary) + Europe PMC (on by default) + bioRxiv/medRxiv (on by default)** — already reaches almost the entire published landscape: through these three endpoints you get PubMed / PMC, the bioRxiv / medRxiv / arXiv preprints, and the Crossref, Semantic Scholar, CORE, and Unpaywall records (Semantic Scholar records are surfaced via OpenAlex's linkage even without querying S2 directly). The extra sources are opt-in, not because the trio is incomplete, but for two practical reasons:

- **Preprint freshness** — **bioRxiv / medRxiv are now on by default**, pulling preprints straight from the source instead of waiting for them to propagate through Europe PMC's PPR feed.
- **Resilience against rate limits** — if Europe PMC is throttled (HTTP 429), the standalone preprint endpoints let you keep widening coverage without depending on a single bottleneck. (Semantic Scholar is a separate opt-in source requiring `--with-semantic-scholar` + a key, and is not part of the default pipeline.)

## Why You Can Trust the Output — Anti-Hallucination

LLM-powered literature tools are notorious for **inventing papers that don't exist** — fabricated DOIs, wrong PMIDs, plausible-but-fake citations. ct-literature is built to make that impossible *by construction*, through four independent guardrails plus two operational safeguards:

1. **Every citation is resolved against its live source (P0, default ON).** Before a work reaches your report, its identifier is checked against the real bibliographic API: DOI → `doi.org` (HTTP 2xx), PMID → Europe PMC `EXT_ID`, OpenAlex id → `api.openalex.org/works/<id>`. Each work is tagged `citation_verified` plus a status of `verified` / `bot_blocked` / `unresolved` / `no_identifier` / `suspicious`. A **malformed DOI is flagged `suspicious`** — a likely hallucinated identifier is caught *before* it can appear in the report. Scope it with `--verify {all|top|background}`; the default `all` verifies every work.
   - **`bot_blocked`**: some publishers (NEJM, JAMA, Wiley, MDPI…) return **403** to programmatic access even though the DOI is real. The skill reports this distinctly — it is *not* a broken link, and the work stays `verified=True`.
2. **Title / author consistency depth (v0.6.11).** Once an identifier resolves to a live resource, the skill fetches that resource's canonical metadata (title + first-author surname) from the authoritative, bot-friendly API — **Crossref** for DOIs (bot-friendly even when the publisher blocks `doi.org`), **Europe PMC** for PMIDs, **OpenAlex** for OpenAlex ids — and compares it to the work you hold. A resolved-but-**different** paper is flagged **`mismatch`** (not `verified`); a `bot_blocked` DOI whose Crossref metadata matches is **upgraded to `verified`**. A hallucinated-but-real DOI is thus caught *even when it resolves*. Metadata-fetch failure degrades gracefully to "verified, consistency unchecked" — it never invents a mismatch. Opt out with `--no-consistency`.
3. **Full provenance is recorded, not summarized away.** Every merged work keeps its `sources` list (which API produced it), and `evidence_log.json` stores an immutable-style audit trail: query → source → hit count → retrieved_at → verification rate. You can always trace a claim back to the exact API call that produced it.
4. **The report never pads gaps with fluent prose.** Every factual line in the report carries a source label or an explicit `⚠️ needs official verification` marker. The skill does **not** generate plausible-looking evidence to fill holes — if a source failed or a work is unverified, that is shown, not hidden.

Operational safeguards reinforce this: **Safe Preview** keeps normalization / reporting on your machine (no remote code execution), and **source-aware skip** avoids redundant re-checks while still trusting each identifier *by provenance* (a paper OpenAlex returned already carries a real OpenAlex id, so it isn't re-queried there). All of this follows the anti-hallucination spec (§17.1).

**Net:** the references this skill gives you are real, resolvable, and traceable — safe to put in a slide, a protocol, or a CSR appendix, provided you validate against the official source before any regulatory submission (see the [First-Time FAQ](#first-time-faq)).

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
| **Batch-download OA PDFs** (v1.0.0) | "Download the newest 40 PDFs and log the time" — files land in a local `pdfs*/` folder (DOI-named), the Excel report gets a 「PDF 本地路径」column, failures are marked honestly |

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

**Q: On a Chinese system, is the output in Chinese?** A: Yes. **Conversation answers and the reports** (HTML / Excel) follow your OS setting by default (Chinese on a Chinese-OS, English otherwise), and you can force-switch anytime with one sentence (e.g. "switch to English"). **Console progress lines** (fetch / download process hints) are Chinese auxiliary output — runtime noise, they do not affect the language of the answers or deliverables.

**Q: Semantic Scholar keeps failing / being skipped?** A: The S2 key requires a manual form review (not auto-issued, waits after applying), so it is usually absent short-term. When no key is configured the source is **skipped entirely** (no network request) rather than attempting-and-degrading. Configure it later if you need citation ranking.

**Q: How long does a search take? What are the rate limits?** A:
- **Typical latency:** Enabled sources run **in parallel with each other** (one worker per source), but **each source pages serially** — requests inside a source are chained one after another, because parallel paging would raise rate-limit / ban risk (e.g. on the OpenAlex keyless pool). Europe PMC ~1s/page, OpenAlex ~2s/page, so the wall-clock is the *slowest* source, not the sum. A 3-source search pulling ~50 works typically finishes in **10–30 seconds** (plus ~1–4 min more when full citation verification is on — see the pre-run time estimate). Adding preprints (bioRXiv/medRXiv/arXiv) adds a few seconds more.
- **Result cap:** Default `max_results` is **50 works per source**; there is no hard ceiling (raising it is allowed), but time and API usage scale linearly. **Measured 2026-08-14** (two sources, `osimertinib ILD`): `--max 100` → fetch+merge **~20 s**, full verification **~78 s** (≈0.64 s/work after cross-source dedup, which keeps **~62%** of fetched works with two sources). **Suggested ceiling for a ~5-minute run: 300 works per source with two sources, ~250 with three sources** (either way ≈370–380 unique merged works; dedup is automatic, so 3×250 does not mean 750 in the report). Beyond that total time grows ~linearly — for very large harvests, configure an OpenAlex key and use `--verify top 15` instead of pushing `max_results`.
- **Rate limits:**
  - **OpenAlex (keyless):** 100 credits/day (since 2026-02-13). A single multi-page search can use 5–20 credits. A free key lifts this to **100k/day**.
  - **Europe PMC:** No hard key limit, but please keep request frequency reasonable (no tight loops).
  - **Semantic Scholar (no key):** Prone to HTTP 429; the skill skips it entirely when no key is configured.
- **Tip:** Start with the default sources (OpenAlex + Europe PMC) and a modest `max_results`; only enable extra sources if you need broader coverage.

**Q: Why can't the fetch be faster?** A: Because the skill only uses the **official public access methods each site provides** (their public APIs / endpoints) and **never violates any site's terms or policies** — it fetches politely, source by source, page by page, so it cannot deliver the "crawl a huge dataset in minutes" effect of an aggressive scraper. Concretely: (1) **Different sources already run in parallel** (one worker per source) — adding more cross-source parallelism won't help. (2) **Each source must page serially** — the public bibliographic APIs (OpenAlex keyless pool, Europe PMC polite pool) throttle or ban clients that fire many parallel requests; serial paging is what keeps you under the ban radar. (3) If a run feels slow, the usual bottleneck is **full citation verification** (default ON; one or more HTTP lookups per work) — switch to `--verify top` (default top-15) to cut ~1–4 minutes. (4) Keep `max_results` moderate — time and API usage scale linearly with it. Bulk PDF fetching is the other multi-second-per-work operation (each request follows a redirect chain).

**Q: Can I search in Chinese?** A: Partially — the skill auto-translates Chinese topics to English through **bundled offline dictionaries** (~900 entries: medical terms + drug INN names + brand names like 泰瑞沙→Tagrisso/osimertinib + MeSH synonyms; no network call) before querying the APIs, and the report banner shows the original and the translation as `中文 → English`. Equivalent names are combined with boolean OR to widen recall (e.g. `osimertinib OR Tagrisso`, `lung cancer OR pulmonary neoplasm`). Terms the dictionaries do not cover pass through as-is (recall may suffer) and a notice lists the unmapped ones — you can extend the dictionaries yourself by adding entries to `references/user_terms.json` (same `{中文: "English"}` format, values may be a list of synonyms; the file is git-ignored so your additions are never published). For best recall, use English terms — especially for rare conditions or novel compounds.

**Q: Why don't you support Chinese domestic databases (e.g. CNKI / 知网)?** A: Deliberately not supported, for three reasons. (1) **Marginal value** — this skill targets the publicly retrievable international evidence base (OpenAlex / Europe PMC / ...); the incremental coverage of Chinese-only databases is small, and much of their content overlaps or is already indexed internationally. (2) **No compliant channel exists** — CNKI and similar Chinese databases **do not offer public APIs to individuals** (only to contracted, paying institutions), and they aggressively block — and have sued — web crawlers; automated retrieval would have neither a legal interface nor a defensible risk posture, violating this skill's rule of "official public access only, never breach a site's terms". (3) **ROI** — paying that compliance/legal risk for marginal coverage is not worth it. If you need a specific Chinese paper, search CNKI yourself and export the citation (RIS / BibTeX) for your records.

**Q: Can the skill download full-text PDFs?** A: Yes — but **for open-access (OA) works only**, in two ways. (1) The Excel and HTML reports always include an **"Open Access"** column with a direct link to a free OA copy when one exists (typically 60–80% of recent works); **non-OA, paywalled papers show "—" and are not supported**. (2) Since v1.0.0 the skill can also **download the OA PDFs to disk for you**. The compliance boundary first:
- **OA-only assistance; non-OA is not supported:** the skill pulls only from legitimate OA channels (publisher OA links, Europe PMC, PMC author manuscripts, open preprints) — **it performs no illegal operation of any kind**: no cracking, no bypassing, nothing touches a paywall. Paywalled works (NEJM / JCO / BMJ …) are honestly marked **"failed"** — get them via your institution's subscription, interlibrary loan, or the corresponding author.
- **For personal use only; no commercial use:** this feature exists to make it convenient for an individual to get OA copies. Do not use the downloaded content for commercial purposes.
- **OA direct-fetch fails → it looks for a preprint substitute:** when the canonical OA link cannot be pulled, it searches for an earlier preprint or author manuscript (bioRxiv / medRxiv / PMC) as a substitute; only when no usable copy exists is the work marked failed.
- **Use the free resources wisely and pace your requests (avoid an IP block):** OA providers commonly block programmatic high-frequency downloads — to stay clear of legal trouble, the skill **strictly enforces a ≥5 s gap between consecutive download requests** and never pushes against a server's load threshold; please also control your own batch frequency and **do not over-use the free resources**. The skill has built-in cross-domain concurrency limits and per-domain throttling, and **a single batch above 50 works is refused outright** — split it (top-N / single source).

Experience details: before a batch starts it states the pace (roughly **10–20 s per paper**; a 40-work batch runs ~10–15 min); afterwards PDFs land in a `pdfs*/` folder (DOI-named), it reports elapsed time ("N/M succeeded, took X s"), and **the Excel report gets a 「PDF 本地路径」column** (absolute path on success, "failed" otherwise). Keyless auto channels give a real-world success rate of roughly **70–90%** (OA coverage and publisher blocking vary). How to ask: say "download ALL OA PDFs", "download the newest 40 PDFs and log the time", or give a DOI/PMID list.

**Q: What if I found an error in the result — how do I report it?**
A: This skill follows the bug-report workflow. If you suspect the result is wrong (or the engine errored), just say **"report a bug" / "上报问题" / "提交错误报告"**. The skill also **proactively asks** whether to report when it detects a likely defect (e.g. the engine errors or retries still fail) — at most **once per session**, and you can always decline. Either way, the assistant will:
1. **Propose a sanitized report** (11-field whitelist: skill / skill_version / test / error_type / error_code / engine_status / description / locale / query_origin / session_hash / attempts — **no raw input values or personal data**, except the `description` field where you decide what to disclose, e.g. the algorithm/function used and the error message);
2. **Show the full report text for your review** — you can add a problem description or correct anything before confirming;
3. **Send after your explicit confirmation** — to the unified endpoint `https://ct-bugreport.coze.site/run` (if this session called coze) or saved locally + emailed to the author (if purely local, data never leaves your machine);
4. **Receive an acknowledgment** — including whether a previously submitted report from your source has already been fixed (with the fix note) or is still pending.

You stay in full control: the report is shown to you **before** anything is sent, and nothing is transmitted without your explicit "send" confirmation.

---

## Security & Privacy

### Safe Preview (local computation)
- **Runs locally:** The normalize / report / Excel rendering steps run entirely on your machine — no code is executed on any remote server beyond the bundled scripts.
- **Traceable, not fabricated:** Every factual claim in the report carries a source label (`sources` list per work) or an `⚠️ needs official verification` marker; it never fills evidence gaps with fluent prose.
- Outputs are for reference only; validate against official sources before regulatory submissions.

### Outbound & Privacy
- **Bibliographic search (public APIs only):** your topic + filters go to **OpenAlex** / **Europe PMC** / **Semantic Scholar** (only the sources you enable), plus **doi.org** and **Crossref** during citation verification. No confidential / sponsor data is ever sent.
- **Metadata sent with every outbound request:** each request carries ① your business parameters (topic / filters) plus ② `query_origin` (a SHA-256 hash of your machine hostname — used for rate-limit attribution and billing; **this is a one-way hash, NOT your plaintext hostname**) and `locale` (your OS language, used to localize UI prompts). These fields are computed locally on your machine and sent as opaque identifiers — no PII, no hostname, no IP leaves your device.
- **Bug reports (opt-in, user-confirmed):** `adapters/bug_report.py` sends an **11-key sanitized envelope** (skill / version / error_type / description / … — never raw data or subject records) to `https://ct-bugreport.coze.site/run` **only after you explicitly confirm** a two-stage prompt; without cloud access it falls back to a local file.
- **Keys stay on your machine:** keys are read from your local `ct-literature/.env` and never ship with the package (only `.env.example` ships). Apply for your own OpenAlex key at <https://openalex.org/settings/api> and configure it yourself via the [First-Time FAQ](#first-time-faq) (`.env` / env var / `--openalex-key`); never commit `.env` to a repo. (Optional, not recommended: you may paste a key and ask the assistant to write it locally — stored only on your machine, never echoed or logged. Self-configuring is preferred.)

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
│   ├── export_xlsx.py       # Excel deliverable (excel_style)
│   ├── export_html.py       # self-contained HTML report
│   ├── format_citations.py  # APA/Nature/Vancouver/IEEE/GB7714 + BibTeX/RIS
│   ├── evidence_log.py      # provenance audit trail (evidence_log.json/.md)
│   ├── obsidian_exporter.py # Obsidian notes + MOC
│   ├── zotero_exporter.py   # Zotero RIS/CSV
│   ├── i18n.py              # bilingual single source of truth
│   └── excel_style.py, …             # shared style
├── references/              # SOP, key setup, search menu, multi-db method
└── assets/icon.svg          # A-tier logo
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

# P0 · citation verification (default ON, mode=background) + evidence log are automatic under --run.
# Scope it with --verify {all|top|background}; source-aware skip avoids redundant same-source
# re-resolution (a paper from OpenAlex/Europe PMC is trusted by provenance).
# Verification is an anti-hallucination gate (§17.1 P0): it cannot be fully disabled —
# "none" is not a valid mode (v0.9.6 removed the CLI bypass).
python scripts/ct_literature.py --topic "osimertinib" --run --out-dir ./out
# Best speed/coverage balance for large result sets: verify only the top-ranked works (default top 15; --verify-top-n adjusts N — verification is never disabled)
python scripts/ct_literature.py --topic "osimertinib" --run --verify top --out-dir ./out
# Non-blocking default: background verification streams in without delaying the report
python scripts/ct_literature.py --topic "osimertinib" --run --verify background --out-dir ./out
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

**Version**: v1.0.1 | **License**: MIT | **Authors**: medstatstar, phoe-zip

For feature requests, bug reports, or other feedback, feel free to contact the author directly at medstatstar@gmail.com (Wintone Zhang / 张文彤).

---

## Confidentiality Notice

> The CT series consists of 20+ specialized domain skills, organized into **two tiers — A, B** — by "whether the input contains confidential information" (network / egress / publish are independent orthogonal attributes), providing full coverage of the entire new-drug clinical trial (Clinical Trial) lifecycle.
>
> - **Tier A (non-confidential input)**: run fully locally using only ordinary data; Tier A may need external public retrieval but involves no confidential information. These skills are published openly on GitHub.
> - **Tier B (confidential input)**: accept strictly confidential clinical-trial data / protocols / CRFs from pharma sponsors (e.g., ct-analysis, ct-sdtm, ct-protocol, ct-eligibility); Tier B is processed locally and never leaves the boundary (egress=none), or additionally requires policy approval (egress=approval-req, e.g. ct-eligibility). Tier B packages contain zero confidential data but are NOT publicly published (stays fully local) — confidential input never ships with the package or leaves the machine. For custom / on-prem deployment, contact the author.
>
> 📧 Contact: medstatstar@gmail.com (Wintone Zhang / 张文彤)

> 🌐 Other languages: [中文 README](README_zh-CN.md)
