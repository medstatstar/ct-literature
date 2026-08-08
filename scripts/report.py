#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
report.py — literature search report renderer.

Renders the merged, de-duplicated work list into a Markdown report: summary,
top-works table, study-type distribution, yearly trend, and a safety/CSM subset.
Pure local rendering, no network.
"""
import argparse
import json


def _authors_str(authors):
    """Tolerate None / non-list / None-elements in the authors field."""
    if not authors or not isinstance(authors, (list, tuple)):
        return "—"
    names = [str(a) for a in authors if a]
    if not names:
        return "—"
    return ", ".join(names[:3]) + (" et al." if len(names) > 3 else "")


def _src_list(w):
    """Provenance list of a work, tolerant to missing / None `sources`."""
    srcs = w.get("sources")
    if not isinstance(srcs, (list, tuple)) or not srcs:
        srcs = [w.get("source")]
    return [str(s) for s in srcs if s]


def _join(values, limit=None):
    """Join a possibly-None / mixed-type iterable into a comma string."""
    if not isinstance(values, (list, tuple)):
        return ""
    items = [str(v) for v in values if v]
    if limit:
        items = items[:limit]
    return ", ".join(items)


def _int_or_none(v):
    """Coerce year / citation-like values that may arrive as strings."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.strip().lstrip("-").isdigit():
        return int(v.strip())
    return None


def render(works, meta=None):
    meta = meta or {}
    works = [w for w in (works or []) if isinstance(w, dict)]
    n = len(works)
    src_set = sorted({s for w in works for s in _src_list(w)})
    years = [y for y in (_int_or_none(w.get("year")) for w in works) if y is not None]
    yr_range = "%d–%d" % (min(years), max(years)) if years else "n/a"

    lines = []
    lines.append("## 📚 Literature Search Report / 文献检索报告\n")
    lines.append("- **Topic / 主题**: %s" % meta.get("topic", "—"))
    lines.append("- **Review type / 类型**: %s" % meta.get("review_type", "all"))
    yr_filter = "all"
    if meta.get("year_from") and meta.get("year_to"):
        yr_filter = "%d–%d" % (meta["year_from"], meta["year_to"])
    elif meta.get("year_from"):
        yr_filter = "≥ %d" % meta["year_from"]
    elif meta.get("year_to"):
        yr_filter = "≤ %d" % meta["year_to"]
    lines.append("- **Year range / 年份**: %s%s"
                 % (yr_filter, "  (retrieved: %s)" % yr_range if years else ""))
    lines.append("- **Works retrieved / 检索到**: %d (unique, de-duplicated)" % n)
    lines.append("- **Sources / 来源**: %s" % (", ".join(src_set) if src_set else "—"))
    if meta.get("safety"):
        lines.append("- **Mode / 模式**: safety / CSM (safety-biased)")
    lines.append("")

    if not works:
        lines.append("_No works retrieved. Try a broader topic or widen the year range._")
        return "\n".join(lines)

    # Top works table
    lines.append("### Top works by citations / 按被引排序的 Top 文献\n")
    lines.append("| # | Year | Type | Title | Authors | Cited | Source | OA |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for i, w in enumerate(works[:25], 1):
        title = (w.get("title") or "").replace("|", "/")
        if len(title) > 90:
            title = title[:87] + "…"
        oa_url = w.get("open_access_url")
        oa_cell = "[📥](%s)" % oa_url if oa_url else ""
        lines.append("| %d | %s | %s | %s | %s | %s | %s | %s |" % (
            i,
            w.get("year") or "—",
            w.get("study_type") or w.get("type") or "—",
            title,
            _authors_str(w.get("authors")),
            _int_or_none(w.get("cited_by_count")) or 0,
            "/".join(_src_list(w)) or "—",
            oa_cell,
        ))
    lines.append("")
    # OA summary line
    oa_count = sum(1 for w in works if w.get("open_access_url"))
    if oa_count > 0:
        lines.append("📥 = open-access full text available (%d of %d, %.0f%%)\n" % (oa_count, n, 100.0*oa_count/n))

    # Detailed record cards
    lines.append("### Key details / 关键文献详情\n")
    for i, w in enumerate(works[:15], 1):
        title = (w.get("title") or "—")
        lines.append("#### %d. %s" % (i, title))
        lines.append("- **Authors**: %s" % _authors_str(w.get("authors")))
        meta_parts = []
        if w.get("publication"):
            meta_parts.append("**Journal**: %s" % w["publication"])
        if w.get("publication_date"):
            meta_parts.append("**Date**: %s" % w["publication_date"])
        if w.get("volume"):
            meta_parts.append("**Volume**: %s" % w["volume"])
        if w.get("issue"):
            meta_parts.append("**Issue**: %s" % w["issue"])
        if w.get("page"):
            meta_parts.append("**Page**: %s" % w["page"])
        _cited = _int_or_none(w.get("cited_by_count"))
        if _cited:
            meta_parts.append("**Cited**: %d" % _cited)
        if meta_parts:
            lines.append("- %s" % " | ".join(meta_parts))
        id_parts = []
        if w.get("doi"):
            _doi = str(w["doi"])
            id_parts.append("[DOI](%s)" % (_doi if _doi.startswith("http") else "https://doi.org/" + _doi))
        if w.get("pmid"):
            id_parts.append("[PubMed %s](https://pubmed.ncbi.nlm.nih.gov/%s)" % (w["pmid"], w["pmid"]))
        if w.get("pmcid"):
            id_parts.append("[PMC %s](https://www.ncbi.nlm.nih.gov/pmc/articles/%s)" % (w["pmcid"], w["pmcid"]))
        if w.get("open_access_url"):
            id_parts.append("[Full Text](%s)" % w["open_access_url"])
        if id_parts:
            lines.append("- %s" % " · ".join(id_parts))
        for _label, _key, _lim in (("Concepts", "concepts", None),
                                   ("Keywords", "keywords", 6),
                                   ("Funders", "funders", None),
                                   ("MeSH", "mesh", 6)):
            _txt = _join(w.get(_key), _lim)
            if _txt:
                lines.append("- **%s**: %s" % (_label, _txt))
        if w.get("is_retracted"):
            lines.append("- ⚠️ **RETRACTED**")
        # Full abstract
        abstract = w.get("abstract_snippet")
        if abstract:
            lines.append("")
            lines.append("> **Abstract**: %s" % abstract)
        lines.append("")

    # Study-type distribution
    dist = {}
    for w in works:
        st = w.get("study_type") or w.get("type") or "other"
        dist[st] = dist.get(st, 0) + 1
    lines.append("### Study-type distribution / 研究类型分布\n")
    for st, c in sorted(dist.items(), key=lambda x: -x[1]):
        lines.append("- %s: %d" % (st, c))
    lines.append("")

    # Yearly trend
    yt = {}
    for w in works:
        y = _int_or_none(w.get("year"))
        if y is not None:
            yt[y] = yt.get(y, 0) + 1
    if yt:
        lines.append("### Yearly trend / 年度趋势\n")
        for y in sorted(yt):
            bar = "#" * max(1, round(yt[y] / max(yt.values()) * 20))
            lines.append("- %d: %d %s" % (y, yt[y], bar))
        lines.append("")

    # Safety / CSM subset
    safety = [w for w in works if w.get("is_safety")]
    if safety:
        lines.append("### Safety / CSM subset / 安全性（累积安全性监测）子集\n")
        lines.append("%d works flagged as safety-related (AE / toxicity / case report / PV):\n"
                     % len(safety))
        for w in safety[:12]:
            title = (w.get("title") or "").replace("|", "/")
            lines.append("- [%s] %s — %s %s" % (
                _int_or_none(w.get("year")) or "—", title,
                "/".join(_src_list(w)) or "—",
                (" · " + str(w.get("url"))) if w.get("url") else ""))
        lines.append("")
        lines.append("> CSM note: published safety literature (case reports / PV articles) is "
                     "**qualitative evidence** — it complements, but must NOT replace, "
                     "structured FAERS disproportionality (ct-safety). / 已发表安全性文献为定性证据，"
                     "补充而非替代 FAERS 结构化信号检测。")
        lines.append("")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Render Markdown literature report.")
    ap.add_argument("--in", required=True, dest="inp", help="merged works JSON")
    ap.add_argument("--out", help="output Markdown path")
    ap.add_argument("--topic", default="—")
    ap.add_argument("--review-type", default="all")
    ap.add_argument("--year-from", type=int)
    ap.add_argument("--year-to", type=int)
    ap.add_argument("--safety", action="store_true")
    args = ap.parse_args()

    data = json.load(open(args.inp, encoding="utf-8"))
    works = data.get("works", [])
    meta = {
        "topic": args.topic, "review_type": args.review_type,
        "year_from": args.year_from, "year_to": args.year_to, "safety": args.safety,
    }
    md = render(works, meta)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md)
        print("[OK] report ->", args.out)
    else:
        print(md)


if __name__ == "__main__":
    main()
