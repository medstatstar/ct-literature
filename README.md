# Clinical Trial Literature Search (ct-literature)

[🇨🇳 中文](./README_zh-CN.md) | [🇺🇸 English (Current)](#)

<div align="center">
<img src="assets/icon.svg" width="240" height="240" alt="ct-literature logo"/>
</div>

> **A `ct-` library skill (B-tier public-intel) that retrieves published scholarly literature about a drug / disease / method, normalizes multiple public bibliographic sources into one de-duplicated evidence base, and surfaces the evidence landscape plus a CSM (cumulative safety monitoring) qualitative subset.**

> 💡 **Keyless by default, but a free key lifts the cap a lot:** OpenAlex has required an API key since 2026-02-13; without one you are in the keyless pool (100 credits/day, flagged *not suitable for production*). A free key lifts this to 100k/day. Apply in ~30s — see §4 and the key-notice the skill prints automatically when no key is detected.

> No commands or manual needed. Just describe your literature question **in plain language inside a chat** — the skill fetches from OpenAlex (primary) plus optional Europe PMC / Semantic Scholar, then writes a Markdown + Excel report. B-tier: fully local computation, only public retrieval. **Note: your topic query is sent to the public bibliographic APIs below — see the outbound notice in §4.**

---

## Who This Is For

ct-literature is part of the `ct-` clinical-trial skill family, built for three groups:

- **Clinical-trial practitioners at pharmaceutical companies** — sponsors, CROs, and medical / statistical / regulatory roles;
- **Clinicians and nurses who take part in the hands-on conduct of trials**;
- **Medical students who want to learn clinical-trial methodology in a structured way**.

## Sources

| Source | Key | Role |
|---|---|---|
| OpenAlex | recommended (free key; keyless = 100/day since 2026-02-13) | **Primary** — broad, citation-rich |
| Europe PMC | no key | Optional `--with-europepmc` — MEDLINE/MeSH biomedical precision |
| Semantic Scholar | no key (429-prone) | Optional `--with-semantic-scholar` — citation ranking; **skipped automatically** when no key / on 429 |

## 1. How to Use It in a Chat (the Core)

ct-literature is a **conversational skill**: you simply tell the assistant what you want to look up — no commands, no parameter names to remember. Once installed as a WorkBuddy skill, you invoke it in a chat via the Skill tool; there is no extra setup, but it activates only when you call it.

Below are 7 real conversational examples ordered from simple to advanced. Each shows **"You say"** and a sketch of **"The assistant replies"**, plus how the report is produced.

### Example 1 · A simple literature search (direct)
**You say:**
Search published literature on osimertinib in NSCLC, 2018–2025.

**Assistant replies (sketch):**
Routing to OpenAlex (primary). Here is the normalized evidence base — N papers, top-cited works, yearly trend, plus a CSM subset. Report saved to `lit_report.md` / `lit_report.xlsx`.

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

### Example 4 · Configure the OpenAlex key (conversational)
**You say:**
How do I lift the 100/day limit for large searches?

**Assistant replies (sketch):**
Apply for a free key (~30s) at <https://openalex.org/settings/api>, then just paste the key to me — I'll write it into `ct-literature/.env` for you. No manual file editing. (Recommended over `--openalex-key` / env var because it survives reruns with zero extra flags.)

### Example 5 · Get the Excel deliverable
**You say:**
Can I get an Excel file instead of just Markdown?

**Assistant replies (sketch):**
Yes — `--run` auto-produces `lit_report.xlsx` (academic-green theme, 4 sheets: README → Overview → Works → Safety; safety-relevant rows highlighted). Use `--no-xlsx` to skip.

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

---

## 2. What Can It Do — Scenarios

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

### ③ Output formats
| Situation | Try saying in chat |
|:---|:---|
| Excel deliverable | "Export the literature as an Excel file" |
| Markdown report only | "Just give me the Markdown report, skip Excel" |

### ④ Key / setup
| Situation | Try saying in chat |
|:---|:---|
| Lift the OpenAlex rate limit | "How do I raise the rate limit?" |
| Check what's configured | "What keys does the skill currently see?" |

> The sibling skills are described in their own READMEs; ordinary users only need to say what they want in plain language — the skill routes the right sources and writes the report.

---

## 3. First-Time FAQ

**Q: Do I need a key to run?** A: No. OpenAlex keyless pool = 100 credits/day (enough for small searches); a free key lifts it to 100k/day. Europe PMC and Semantic Scholar need no key.

**Q: Where does my query go?** A: Your topic query and filters are sent to the public bibliographic APIs — OpenAlex, Europe PMC, and Semantic Scholar (when enabled). No confidential or sponsor data is ever sent.

**Q: What's the difference from `ct-safety`?** A: `ct-literature` = published *qualitative* evidence (papers / reviews / case reports); `ct-safety` = structured FAERS disproportionality (PRR / ROR / IC). They are explicitly distinct data types — literature complements but does not replace FAERS.

**Q: On a Chinese system, is the output in Chinese?** A: Yes. Output language follows your OS setting by default (Chinese on a Chinese-OS, English otherwise), and you can force-switch anytime with one sentence (e.g. "switch to English").

**Q: Semantic Scholar keeps failing / being skipped?** A: The S2 key requires a manual form review (not auto-issued, waits after applying), so it is usually absent short-term. When no key is configured the source is **skipped entirely** (no network request) rather than attempting-and-degrading. Configure it later if you need citation ranking.

---

## 4. Security & Privacy

### Safe Preview (local computation)
- **Runs locally:** The normalize / report / Excel rendering steps run entirely on your machine — no code is executed on any remote server beyond the bundled scripts.
- **Traceable, not fabricated:** Every factual claim in the report carries a source label (`sources` list per work) or an `⚠️ needs official verification` marker; it never fills evidence gaps with fluent prose.
- Outputs are for reference only; validate against official sources before regulatory submissions.

### Outbound & Privacy (public retrieval only)
- **The only outbound paths = the three public bibliographic APIs:** when you run a search, your topic query + filters are sent to **OpenAlex** (`api.openalex.org`), **Europe PMC** (`ebi.ac.uk/europepmc`), and **Semantic Scholar** (`api.semanticscholar.org`) — only the sources you enable. There is **no other outbound path** and **no confidential / sponsor data is ever sent**.
- **Keys stay on your machine:** If you configure an OpenAlex / S2 key, it is read from your local `ct-literature/.env` and **never ships with the package** — `.env` is excluded by `.gitignore` (GitHub) / `.clawhubignore` (ClawHub), and SkillHub's narrow allowlist also omits it; only `.env.example` ships. After a reinstall you re-enter the key yourself.
- **No auto-provisioning:** The skill does not auto-transfer or auto-provision keys; when no key is detected it prints the apply notice and runs keyless.

---

## 5. Advanced Reference (for developers)

CLI helpers, runtime requirements, the architecture tree, and the unified work-mode schema have moved here so everyday users don't need them. See [`SKILL.md`](SKILL.md) and [`CHANGELOG.md`](CHANGELOG.md) for the agent-facing spec and version history.

### Runtime & requirements
| Item | Requirement |
|---|---|
| Runtime | Python 3.11+ (CPython). The pipeline uses only the standard library + `requests` for HTTP. |
| Keys (optional) | OpenAlex free key (recommended for scale); Semantic Scholar key optional (lifts ~1 req/s limit). Both via `.env` / env var / `--openalex-key`. |
| Sibling skills | `ct-registry` (trial registries), `ct-safety` (FAERS), `ct-pipeline` (intel brief) — ct-literature seeds topics and is seeded by them; all install from GitHub. |

### Architecture
```
ct-literature/
├── SKILL.md              # agent-facing spec (English body)
├── scripts/
│   ├── ct_literature.py  # orchestration entry: fetch → normalize → report
│   ├── fetch_openalex.py # primary source
│   ├── fetch_europepmc.py# optional MEDLINE/MeSH
│   ├── fetch_semantic_scholar.py # optional citation rank (low-priority, skippable)
│   ├── normalize.py      # multi-source merge + dedupe
│   ├── report.py         # Markdown report
│   ├── export_xlsx.py    # Excel deliverable (ct-base excel_style)
│   ├── export_html.py    # optional HTML
│   ├── http_utils.py     # shared retry / headers / key load
│   └── i18n.py           # bilingual single source of truth
├── references/           # SOP, key setup, search menu, multi-db method
└── assets/icon.svg       # B-tier logo
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
  sources                                     # contributing source list
}
```

---

**Version**: v0.5.1 | **License**: MIT | **Authors**: medstatstar, phoe-zip

For feature requests, bug reports, or other feedback, feel free to contact the author directly at medstatstar@gmail.com (Wintone Zhang / 张文彤).

---

## Confidentiality Notice

> The CT series consists of 16+ skills, providing full coverage of the entire new-drug clinical trial (Clinical Trial) lifecycle. However, since many skills involve strictly confidential clinical-trial data and internal information from pharma sponsors, only the non-confidential Level A / B skills are published openly on GitHub; the confidential Level C / D skills (e.g., ct-analysis) are designated for internal enterprise use only.

> If you do have a genuine need for these confidential skills, please contact the author to request custom installation.

> 📧 Contact: medstatstar@gmail.com (Wintone Zhang / 张文彤)
