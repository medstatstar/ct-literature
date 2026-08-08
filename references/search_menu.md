# Search Confirmation Menu

> This file defines the interaction flow the AI agent uses, in natural-language mode, to confirm retrieval parameters with the user before executing. It covers every confirmation node from "user request" to "execute search".

---

## 1. Dialogue State Machine

```
user request → [recognize intent] → collect params → [preview confirm] → execute → show results
                ↑________↓              ↑________↓
          (ask when missing)      (user may edit and re-run)
```

## 2. Parameter Checklist

| Parameter | Required | Default | Ask-when-missing prompt |
|---|:---:|---|---|
| `--topic` | ✅ | — | "What is the search topic (drug / disease / method)?" |
| `--review-type` | ❌ | `all` | "Limit the literature type?" |
| `--year-from` | ❌ | — | "Set a starting year?" |
| `--year-to` | ❌ | — | "Set an ending year?" |
| `--safety` | ❌ | off | "Bias toward safety / adverse-event literature?" |
| `--max` | ❌ | 30 | "Max works per source? (default 30)" |
| `--with-europepmc` | ❌ | off | "Enable Europe PMC (MeSH precision)?" |
| `--with-semantic-scholar` | ❌ | off | "Enable Semantic Scholar (citation ranking)?" |

## 3. Quick Mode

When the user request already contains ≥2 explicit parameters, **skip step-by-step prompts** and go straight to the preview confirmation.

**Trigger examples:**
- "Search semaglutide systematic reviews from 2020 to now" → straight to preview
- "Check osimertinib safety literature" → straight to preview

## 4. Menu Templates

### 4.1 Initial confirmation menu (when params are insufficient)

```
📚 Literature search — ready

Detected so far:
- Topic: {topic}
- Type: {review_type}
- Year: {year_range}

Still to confirm:
1. Literature type — all / systematic-review / meta-analysis / RCT / case-report
2. Year range — all / custom
3. Safety bias — yes / no
4. Data sources — primary only / + Europe PMC / + Semantic Scholar / all

Reply with a number to choose, or say "default" to use the recommended config.
```

### 4.2 Preview confirmation menu (after params are complete)

```
📚 Search preview

| Parameter | Value |
|---|---|
| Topic | {topic} |
| Type | {review_type} |
| Year | {year_range} |
| Safety | {safety} |
| Sources | {sources} |
| Max / source | {max} |

Confirm execution?
1. ✅ Run now
2. ✏️ Edit a parameter (reply with the number)
3. ❌ Cancel
```

### 4.3 Edit sub-menu (when the user chooses to edit)

```
Which to edit?
1. Topic (current: {topic})
2. Type (current: {review_type})
3. Year (current: {year_range})
4. Safety (current: {safety})
5. Sources (current: {sources})
6. Max / source (current: {max})
0. Back

Reply with number + new value, e.g. "2 meta-analysis".
```

## 5. Recommended Presets

| Scenario | Recommended config |
|---|---|
| Quick evidence landscape of a drug | `all` + last 5 years + all sources |
| Systematic review / meta-analysis | `systematic-review` + `meta-analysis` + last 10 years |
| Safety assessment | `--safety` + `case-report` + all years |
| Competitor research | `all` + last 3 years + citation-rank priority |
| Clinical protocol background | `rct` + `systematic-review` + last 5 years |

## 6. Follow-up Strategy

### 6.1 Priority

1. **topic missing** → must ask, cannot proceed
2. **year missing** → recommend "last 5 years", wait for confirmation
3. **review_type missing** → default `all`, remind at preview
4. **sources missing** → default "all enabled", remind at preview

### 6.2 Ask ceiling

- At most **2 rounds** of follow-up questions
- Still missing after round 2 → use defaults + preview reminder

### 6.3 Example prompts

```
# topic missing
"Please tell me the search topic (drug / disease / method), e.g. semaglutide, osimertinib, PD-1 inhibitor"

# year missing
"Limit by year? e.g. '2020 to now', 'last 5 years', or all years?"

# review_type confirmation
"Currently searching all literature types. Limit it? Options: systematic-review / meta-analysis / RCT / case-report"

# sources confirmation
"Currently all sources enabled (OpenAlex + Europe PMC + Semantic Scholar). Adjust?"
```

## 7. Output Confirmation

After the search, show a result summary + follow-up options:

```
📚 Search complete!

- Topic: {topic}
- Found: {count} unique works ({source_count} sources)
- Open access: {oa_count} ({oa_pct}%)
- Top 3 cited:
  1. {title_1} ({cited_1})
  2. {title_2} ({cited_2})
  3. {title_3} ({cited_3})

Next steps:
1. 📄 View full report
2. 📥 Download merged.json
3. 🔄 Adjust params and re-search
4. 🔗 Chain ct-pipeline for an intel brief
```

## 8. Error Handling

| Case | Handling |
|---|---|
| No results | "No literature found. Suggestion: broaden the topic / relax year / switch review-type" |
| Europe PMC returns 0 | Silently skip, no user prompt (fixed to PUB_YEAR) |
| Semantic Scholar 429 | Silently skip; note "S2 not included" in the result |
| Network timeout | "Network timed out. Check connection and retry, or use OpenAlex primary only" |
| Topic spelling anomaly | "No results. Did you mean: {suggestion}?" |

## 9. i18n

All user-facing strings in this flow must be served via `scripts/i18n.py` (en + zh pairs) and switch by locale — **do not hardcode bare strings in the skill**. Chinese environment → Chinese menu + Chinese report; English environment → English. The templates above are the structural reference; localize the actual wording through i18n.

## 10. Dialogue Example

```
User: help me search semaglutide literature

Agent:
📚 Literature search — ready

Detected so far:
- Topic: semaglutide
- Type: all
- Year: unspecified

Recommended: last 5 years (2020→now) + all sources

Confirm?
1. ✅ Run now (recommended)
2. ✏️ Edit params
3. Other config...

User: 1

Agent: [executes search]

📚 Search complete!
- Topic: semaglutide
- Found: 55 unique works (2 sources)
- Open access: 43 (78%)
...
```
