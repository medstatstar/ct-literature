# Cross-Database Literature Search: Selection, Strategy, Syntax Adaptation and Labeling

> English summary: methodology for cross-database literature search — choose databases by question type (not by habit), build layered search strategies, adapt syntax per database, normalize to a minimum field set, dedupe and prepare for screening, and label preprints / evidence status (Tier 1/2/3/P). This fills the manual-database layer (Embase / Cochrane / WoS / registries / preprints) that sits beyond ct-literature's existing automated OpenAlex + Europe PMC + Semantic Scholar sources.
>
> **Adapted from**: `multi-database-literature-collector` — AIPOCH, MIT License
> **Source**: https://github.com/aipoch/medical-research-skills
> **Migrated**: 2026-08-04 (into ct-literature)

---

## 1. Relation to ct-literature's automated sources

`ct-literature` already retrieves and merges three **API-accessible, keyless** sources automatically:

| Automated (already implemented) | Role |
|---|---|
| OpenAlex | Primary, citation-rich, broad coverage |
| Europe PMC | MEDLINE / MeSH biomedical precision |
| Semantic Scholar | Citation ranking (optional, rate-limited) |

This file governs the **manual / subscription / non-API layer** that a systematic review still needs, and the general methodology (strategy construction, syntax adaptation, tiering) that applies to *all* sources including the automated ones.

| Manual layer | When it must be added |
|---|---|
| **Embase** | Drug, pharmacology, European journals; mandatory for a Cochrane-grade drug SR |
| **Cochrane Library (CENTRAL)** | Controlled-trial and review-oriented clinical evidence |
| **Web of Science** | Citation-indexed retrieval, cross-disciplinary coverage |
| **ClinicalTrials.gov / registries** | Ongoing and unpublished trials (→ delegate to `ct-registry`) |
| **bioRxiv / medRxiv / arXiv** | Preprints and methods not yet indexed |
| **Google Scholar** | Broad recall, citation chaining, grey literature |

---

## 2. Database selection rules

Select by **question type, not by habit**.

1. Use at least 2–3 databases for any cross-database collection task.
2. Justify each choice with a concrete purpose — never add a database to lengthen the list.
3. For every selected database, state:
   - why it is included,
   - what it is expected to contribute,
   - what it is likely to miss.

Worked mapping:

| Question type | Minimum set |
|---|---|
| Drug efficacy SR / meta-analysis | OpenAlex + Europe PMC + Embase + CENTRAL |
| Safety / pharmacovigilance evidence base | OpenAlex + Europe PMC + Embase (+ `ct-safety` for FAERS) |
| Methodological / statistical question | OpenAlex + WoS + arXiv |
| Landscape / competitive intelligence | OpenAlex + registries (`ct-registry`) + preprints |
| Rapid background for a protocol introduction | OpenAlex + Europe PMC only (declare the limitation) |

---

## 3. Search strategy construction

Optimize recall first; narrow later.

**Elements to build (as relevant)**

- disease / condition terms
- intervention / exposure / biomarker / mechanism terms
- outcome or evidence-type terms
- modality / method terms
- synonyms, abbreviations, spelling variants (US/UK)

**Layered strategy**

```
Layer 1  broad core concept search              (recall anchor)
Layer 2  concept × evidence-type refinement     (RCT / SR / meta-analysis filters)
Layer 3  optional recent-update layer           (date-restricted, for surveillance runs)
```

**Principles**

- Start broad enough to avoid premature exclusion.
- Add narrowing only when the topic is too diffuse.
- Apply date filters only when the user asks or the task is update-oriented.
- Apply study-type filters only when necessary — they silently drop conference abstracts and preprints.

**Required transparency** — always report: key terms used, synonym logic, filters applied, and restrictions deliberately *not* applied.

---

## 4. Database syntax adaptation

Never copy one query string across databases unchanged.

| Database | Query style | Field focus | Known compromise |
|---|---|---|---|
| **PubMed / Europe PMC** | Controlled vocabulary + free text | MeSH where appropriate, plus `[tiab]` | MeSH indexing lags ~6–12 months; MeSH-only queries miss recent papers |
| **Embase** | Emtree + free text | `/exp` explosion, `:ti,ab` | Subscription required; Emtree ≠ MeSH, must re-map drug terms |
| **Cochrane CENTRAL** | Simplified MeSH + free text | Trial-oriented | Poor for observational designs |
| **Web of Science** | Topic search `TS=`, phrase logic | Citation-linked retrieval | No controlled vocabulary; phrase precision matters |
| **Google Scholar** | Short, concise queries; phrase search | Full text | Noisy, unstable metadata, no reproducible export — use for recall and citation discovery, not as a primary record source |
| **Preprint servers** | Focused, narrow queries | Title/abstract | Must be explicitly labeled as preprints |

For each database used, document: query style, field focus, date filters, and the database-specific compromise accepted.

---

## 5. Result normalization

A cross-database collection is only usable if records are normalized to one schema.

**Minimum record fields**

`title` · `authors` · `year` · `journal/venue` · `source_database` · `abstract_or_snippet` · `study_type` · `direct_link` · `doi` · `pmid` · `evidence_status` · `preliminary_tier`

**DOI rule** — include the DOI when available and verified. If absent or unverifiable, write `DOI not available` or `DOI not verified`. **Never insert placeholder DOI strings.**

**Link rule** — every formal record needs a real, verifiable direct link: DOI landing page, PubMed, PMC, journal page, or preprint server page.

**Source preservation rule** — never strip source metadata; keep the originating database on every record even after merging. (`ct-literature`'s merge step already carries a `source` field — keep it populated for manually added records too.)

---

## 6. Deduplication and screening readiness

Fields that must survive merging for deduplication to work: `title`, `authors`, `year`, `doi`, `pmid`, `journal`, `source_database`.

Output must support: title/abstract review · study-type filtering · source-specific backtracking · preprint separation · later full-text retrieval.

Always state the next step explicitly: deduplicate → title/abstract screen → separate preprints → prioritize Tier 1 reading.

---

## 7. Preliminary priority layering

First-pass organization, **not** final inclusion.

| Tier | Definition |
|---|---|
| **Tier 1** | Highly likely core papers, directly relevant to the question |
| **Tier 2** | Possibly relevant / borderline, needs screening |
| **Tier 3** | Background, context, indirect support |
| **Tier P** | Preprints — separated regardless of likely relevance |

Tiering signals: directness to the question · study-type relevance · recency (when appropriate) · population/intervention/condition/mechanism match · original evidence vs background context.

**Restriction** — tiering must never be presented as a final inclusion/exclusion decision. That belongs to a screened PRISMA flow.

---

## 8. Evidence-status labeling

Do not mix evidence-status categories into one unlabeled list. Required labels:

- Peer-reviewed original study
- Review
- Guideline / consensus
- Trial registration
- **Preprint**
- Background / context paper

**Preprint rule** — preprints must be clearly labeled and, where possible, separated (Tier P). Never describe a preprint as peer-reviewed unless verified. If evidence status cannot be confirmed from source metadata, say so explicitly rather than guessing.

---

## 9. Cross-database mode in ct-literature

Trigger phrases: "cross-database", "multi-database", "Embase", "Cochrane", "Web of Science", "systematic review search strategy", "PRISMA search", "跨库检索", "多数据库检索", "系统综述检索策略".

Behaviour in this mode:

1. Run the automated three sources as usual.
2. Emit a **manual-search worklist**: for each additional database, the adapted query string, the expected contribution, and the expected gap.
3. Provide an import slot so manually exported records can be normalized into the same schema and merged/de-duplicated with the automated set.
4. Label every record with evidence status and preliminary tier.
5. Report the full strategy (terms, synonyms, filters, per-database adaptation) so the search is reproducible in a PRISMA appendix.
