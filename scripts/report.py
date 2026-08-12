#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
report.py — literature search report renderer.

Renders the merged, de-duplicated work list into a Markdown report: summary,
top-works table, study-type distribution, yearly trend, and a safety/CSM subset.
Pure local rendering, no network.

Bilingual (EN/ZH): follows the same auto-switch policy as export_xlsx /
export_html — `render(..., lang="auto")` picks zh in a Chinese locale, otherwise
en. Pass lang="zh"/"en" to force.
"""
import argparse
import json
import locale


# ═══════════════════════════════════════════════════════════════════════════
# Bilingual labels (EN / ZH) — mirrors export_xlsx._LOCAL / export_html._LABELS
# policy: single-language per locale, auto-switched. No mixed "A / B" strings.
# ═══════════════════════════════════════════════════════════════════════════
_LABELS = {
    "en": {
        "title": "📚 Literature Search Report",
        "m.topic": "Topic", "m.review_type": "Review type",
        "m.year_range": "Year range", "m.works": "Works retrieved",
        "m.sources": "Sources", "m.mode": "Mode",
        "m.citation_style": "Citation style", "m.rank": "Rank",
        "m.deduplicated": " (unique, de-duplicated)",
        "m.retrieved": " (retrieved: %s)",
        "m.safety_mode": "safety / CSM (safety-biased)",
        "m.citation_style_note": " (references.bib / .ris exported)",
        "m.rank_val": "by relevance_score (desc)",
        "cfg.openalex": "OpenAlex key", "cfg.s2": "Semantic Scholar key",
        "cfg.prospero": "PROSPERO token",
        "cfg.configured": "configured ✓",
        "cfg.missing_keyless": "**missing — keyless mode (rate-limited)**",
        "cfg.missing": "missing",
        "cfg.not_used": "not used",
        "cfg.warn": "⚠️ OpenAlex key not configured: the search runs in keyless mode "
                    "(capped at 100 requests/day, prone to HTTP 429). Apply for a free "
                    "key and write it to the skill `.env` (`OPENALEX_API_KEY=<key>`): %s",
        "cfg.degraded": "Degraded sources",
        "cfg.degraded.note": "The following source(s) failed (rate-limited / error); "
                             "results come only from the other available sources.",
        "no_works": "_No works retrieved. Try a broader topic or widen the year range._",
        "top_works": "Top works by citations",
        "tbl.hdr": "| # | Year | Type | Title | Authors | Cited | Rel | Source | OA |",
        "tbl.sep": "|---|---|---|---|---|---|---|---|---|",
        "oa_available": "📥 = open-access full text available (%d of %d, %.0f%%)",
        "key_details": "Key details",
        "lbl.authors": "Authors", "lbl.journal": "Journal", "lbl.date": "Date",
        "lbl.volume": "Volume", "lbl.issue": "Issue", "lbl.page": "Page",
        "lbl.cited": "Cited",
        "id.doi": "DOI", "id.pubmed": "PubMed", "id.pmc": "PMC",
        "id.fulltext": "Full Text",
        "lbl.concepts": "Concepts", "lbl.keywords": "Keywords",
        "lbl.funders": "Funders", "lbl.mesh": "MeSH",
        "retracted": "⚠️ RETRACTED",
        "lbl.abstract": "Abstract",
        "prisma.title": "PRISMA screening funnel",
        "prisma.stage": "Stage", "prisma.count": "Count",
        "prisma.excl": "Exclusion reasons",
        "prisma.note": "Machine screen — not a substitute for human final review.",
        "study_dist": "Study-type distribution",
        "yearly": "Yearly trend",
        "safety.title": "Safety / CSM subset",
        "safety.intro": "%d works flagged as safety-related (AE / toxicity / case report / PV):",
        "safety.note": "CSM note: published safety literature (case reports / PV articles) is "
                       "**qualitative evidence** — it complements, but must NOT replace, "
                       "structured FAERS disproportionality (ct-safety).",
        "evidence.title": "Evidence & verification",
        "ev.verify": "Citation verification",
        "ev.src_prov": "Source provenance",
        "ev.generated": "Generated",
        "ev.note": "Provenance audit trail (ct-base §17.1): every evidence item is traceable "
                   "to its source query and retrieval time. Verification status is **advisory**, "
                   "not a substitute for human review.",
        "ev.preview": " (preview — verification skipped, run `--run` to verify live)",
        "ev.verify.top": " (top-%s verified; remaining works not checked — use `--verify all` for full coverage)",
        "ev.verify.none": " (verification disabled via `--verify none`)",
        "ev.sampled": "sampled",
        "ev.bot_blocked": "bot-blocked",
        "ev.bot_blocked.note": " (publisher returned 403 to automated access — DOI is real, "
                               "not a broken link; verify manually if needed)",
        "ev.src": "Source", "ev.query": "Query", "ev.type": "Type", "ev.year": "Year",
        "ev.safety": "Safety", "ev.count": "Count", "ev.retrieved": "Retrieved",
        "ev.status": "Status",
        "ev.mismatch": "mismatch",
        "ev.mismatch.note": " (identifier resolved to a LIVE resource but title/author do NOT match — possible hallucinated/incorrect id)",
    },
    "zh": {
        "title": "📚 文献检索报告",
        "m.topic": "主题", "m.review_type": "类型",
        "m.year_range": "年份", "m.works": "检索到",
        "m.sources": "来源", "m.mode": "模式",
        "m.citation_style": "引文样式", "m.rank": "排序",
        "m.deduplicated": "（已去重唯一结果）",
        "m.retrieved": "（实际检索年份范围：%s）",
        "m.safety_mode": "safety / CSM（安全性偏倚）",
        "m.citation_style_note": "（已导出 references.bib / .ris）",
        "m.rank_val": "按相关性得分降序",
        "cfg.openalex": "OpenAlex 密钥", "cfg.s2": "Semantic Scholar 密钥",
        "cfg.prospero": "PROSPERO 令牌",
        "cfg.configured": "已配置 ✓",
        "cfg.missing_keyless": "**缺失 — keyless 模式（受限流）**",
        "cfg.missing": "缺失",
        "cfg.not_used": "未使用",
        "cfg.warn": "⚠️ 未配置 OpenAlex key：检索以 keyless 模式运行（限 100 次/天，易 429）。"
                    "免费申请后写入技能 `.env`（`OPENALEX_API_KEY=<key>`）：%s",
        "cfg.degraded": "降级数据源",
        "cfg.degraded.note": "以下数据源未能正常返回（限流 / 报错），结果仅来自其余可用数据源。",
        "no_works": "_未检索到文献。请尝试更宽泛的主题或放宽年份范围。_",
        "top_works": "按被引排序的 Top 文献",
        "tbl.hdr": "| # | 年份 | 类型 | 标题 | 作者 | 被引 | 相关度 | 来源 | 开放获取 |",
        "tbl.sep": "|---|---|---|---|---|---|---|---|---|",
        "oa_available": "📥 = 可获取开放获取全文（%d / %d，%.0f%%）",
        "key_details": "关键文献详情",
        "lbl.authors": "作者", "lbl.journal": "期刊", "lbl.date": "日期",
        "lbl.volume": "卷", "lbl.issue": "期", "lbl.page": "页码",
        "lbl.cited": "被引",
        "id.doi": "DOI", "id.pubmed": "PubMed", "id.pmc": "PMC",
        "id.fulltext": "全文",
        "lbl.concepts": "概念", "lbl.keywords": "关键词",
        "lbl.funders": "资助方", "lbl.mesh": "MeSH",
        "retracted": "⚠️ 已撤稿",
        "lbl.abstract": "摘要",
        "prisma.title": "PRISMA 筛选漏斗",
        "prisma.stage": "阶段", "prisma.count": "数量",
        "prisma.excl": "排除原因",
        "prisma.note": "机器初筛，非人工终审。",
        "study_dist": "研究类型分布",
        "yearly": "年度趋势",
        "safety.title": "安全性 / CSM 子集（累积安全性监测）",
        "safety.intro": "共 %d 篇标记为安全性相关（不良事件 / 毒性 / 病例报告 / 药物警戒）：",
        "safety.note": "CSM 说明：已发表安全性文献（病例报告 / 药物警戒文章）为**定性证据**——"
                       "补充而非替代 FAERS 结构化信号检测（ct-safety）。",
        "evidence.title": "证据溯源与引文验证",
        "ev.verify": "引文验证",
        "ev.src_prov": "来源溯源",
        "ev.generated": "生成时间",
        "ev.note": "证据溯源审计（ct-base §17.1）：每条证据可回溯至来源检索式与检索时间；"
                   "验证状态仅供参考，不替代人工核查。",
        "ev.preview": "（预览 — 已跳过验证，运行 `--run` 以实时验证）",
        "ev.verify.top": "（仅验证 top-%s；其余未核验 — 用 `--verify all` 全量核验）",
        "ev.verify.none": "（已通过 `--verify none` 关闭核验）",
        "ev.sampled": "抽样跳过",
        "ev.bot_blocked": "出版社拦爬",
        "ev.bot_blocked.note": "（出版社对自动化访问回 403 —— DOI 真实有效、非断链；如需可人工复核）",
        "ev.src": "来源", "ev.query": "检索式", "ev.type": "类型", "ev.year": "年份",
        "ev.safety": "安全性", "ev.count": "数量", "ev.retrieved": "检索时间",

        "ev.status": "状态",
        "ev.mismatch": "不一致",
        "ev.mismatch.note": "（标识符解析到存活资源，但标题/作者不一致 —— 可能为幻觉或错误 id）",
    },
}


def _resolve_lang(lang):
    """'auto' -> detect zh from locale; otherwise normalise zh / en."""
    if lang == "auto":
        try:
            _l = (locale.getdefaultlocale()[0] or "zh").lower()
        except Exception:
            _l = "zh"
        return "zh" if _l.startswith("zh") else "en"
    return "zh" if lang in ("zh", "zh-CN", "zh-cn") else "en"


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


def render(works, meta=None, lang="auto"):
    meta = meta or {}
    L = _LABELS[_resolve_lang(lang)]
    _lang = _resolve_lang(lang)
    works = [w for w in (works or []) if isinstance(w, dict)]
    n = len(works)
    src_set = sorted({s for w in works for s in _src_list(w)})
    years = [y for y in (_int_or_none(w.get("year")) for w in works) if y is not None]
    yr_range = "%d–%d" % (min(years), max(years)) if years else "n/a"

    lines = []
    lines.append("## %s\n" % L["title"])
    lines.append("- **%s**: %s" % (L["m.topic"], meta.get("topic", "—")))
    lines.append("- **%s**: %s" % (L["m.review_type"], meta.get("review_type", "all")))
    yr_filter = "all"
    if meta.get("year_from") and meta.get("year_to"):
        yr_filter = "%d–%d" % (meta["year_from"], meta["year_to"])
    elif meta.get("year_from"):
        yr_filter = "≥ %d" % meta["year_from"]
    elif meta.get("year_to"):
        yr_filter = "≤ %d" % meta["year_to"]
    lines.append("- **%s**: %s%s"
                 % (L["m.year_range"], yr_filter,
                    (L["m.retrieved"] % yr_range) if years else ""))
    lines.append("- **%s**: %d%s" % (L["m.works"], n, L["m.deduplicated"]))
    lines.append("- **%s**: %s" % (L["m.sources"],
                                   ", ".join(src_set) if src_set else "—"))
    if meta.get("safety"):
        lines.append("- **%s**: %s" % (L["m.mode"], L["m.safety_mode"]))
    if meta.get("citation_style"):
        lines.append("- **%s**: %s%s"
                     % (L["m.citation_style"], meta["citation_style"],
                        L["m.citation_style_note"]))
    if meta.get("rank") == "relevance":
        lines.append("- **%s**: %s" % (L["m.rank"], L["m.rank_val"]))
    # ---- run-time config audit (key status; avoids silently taking the wrong path) ----
    cfg = meta.get("config") or (meta.get("evidence_log") or {}).get("config") or {}
    if cfg:
        oa = cfg.get("openalex_key")
        s2 = cfg.get("semantic_scholar_key")
        pro = cfg.get("prospero_token")
        oa_s = L["cfg.configured"] if oa == "configured" else L["cfg.missing_keyless"]
        s2_s = L["cfg.configured"] if s2 == "configured" else L["cfg.missing"]
        pro_s = {"configured": L["cfg.configured"], "missing": L["cfg.missing"],
                 "not_used": L["cfg.not_used"]}.get(pro, str(pro))
        lines.append("- **%s**: %s" % (L["cfg.openalex"], oa_s))
        lines.append("- **%s**: %s" % (L["cfg.s2"], s2_s))
        lines.append("- **%s**: %s" % (L["cfg.prospero"], pro_s))
        if oa == "missing" and cfg.get("openalex_key_url"):
            lines.append("  > " + L["cfg.warn"] % cfg["openalex_key_url"])

    # degraded sources (rate-limit / fetch failure) — friendly, actionable, locale-aware
    notes = meta.get("source_notes") or []
    if notes:
        lines.append("- **%s**:" % L["cfg.degraded"])
        lines.append("  > %s" % L["cfg.degraded.note"])
        for _n in notes:
            _msg = _n.get("message_zh") if _lang == "zh" else _n.get("message_en")
            lines.append("  - ⚠️ **%s** (%s): %s" % (_n.get("source"), _n.get("status"), _msg))
    lines.append("")

    if not works:
        lines.append(L["no_works"])
        return "\n".join(lines)

    # Top works table
    lines.append("### %s\n" % L["top_works"])
    lines.append(L["tbl.hdr"])
    lines.append(L["tbl.sep"])
    for i, w in enumerate(works[:25], 1):
        title = (w.get("title") or "").replace("|", "/")
        if len(title) > 90:
            title = title[:87] + "…"
        oa_url = w.get("open_access_url")
        oa_cell = "[📥](%s)" % oa_url if oa_url else ""
        rel = w.get("relevance_score")
        rel_cell = "%.0f%%" % (float(rel) * 100) if isinstance(rel, (int, float)) else "—"
        lines.append("| %d | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            i,
            w.get("year") or "—",
            w.get("study_type") or w.get("type") or "—",
            title,
            _authors_str(w.get("authors")),
            _int_or_none(w.get("cited_by_count")) or 0,
            rel_cell,
            "/".join(_src_list(w)) or "—",
            oa_cell,
        ))
    lines.append("")
    # OA summary line
    oa_count = sum(1 for w in works if w.get("open_access_url"))
    if oa_count > 0:
        lines.append(L["oa_available"] % (oa_count, n, 100.0 * oa_count / n) + "\n")

    # Detailed record cards
    lines.append("### %s\n" % L["key_details"])
    for i, w in enumerate(works[:15], 1):
        title = (w.get("title") or "—")
        lines.append("#### %d. %s" % (i, title))
        lines.append("- **%s**: %s" % (L["lbl.authors"], _authors_str(w.get("authors"))))
        meta_parts = []
        if w.get("publication"):
            meta_parts.append("**%s**: %s" % (L["lbl.journal"], w["publication"]))
        if w.get("publication_date"):
            meta_parts.append("**%s**: %s" % (L["lbl.date"], w["publication_date"]))
        if w.get("volume"):
            meta_parts.append("**%s**: %s" % (L["lbl.volume"], w["volume"]))
        if w.get("issue"):
            meta_parts.append("**%s**: %s" % (L["lbl.issue"], w["issue"]))
        if w.get("page"):
            meta_parts.append("**%s**: %s" % (L["lbl.page"], w["page"]))
        _cited = _int_or_none(w.get("cited_by_count"))
        if _cited:
            meta_parts.append("**%s**: %d" % (L["lbl.cited"], _cited))
        if meta_parts:
            lines.append("- %s" % " | ".join(meta_parts))
        id_parts = []
        if w.get("doi"):
            _doi = str(w["doi"])
            id_parts.append("[%s](%s)" % (L["id.doi"],
                           (_doi if _doi.startswith("http") else "https://doi.org/" + _doi)))
        if w.get("pmid"):
            id_parts.append("[%s %s](https://pubmed.ncbi.nlm.nih.gov/%s)"
                            % (L["id.pubmed"], w["pmid"], w["pmid"]))
        if w.get("pmcid"):
            id_parts.append("[%s %s](https://www.ncbi.nlm.nih.gov/pmc/articles/%s)"
                            % (L["id.pmc"], w["pmcid"], w["pmcid"]))
        if w.get("open_access_url"):
            id_parts.append("[%s](%s)" % (L["id.fulltext"], w["open_access_url"]))
        if id_parts:
            lines.append("- %s" % " · ".join(id_parts))
        for _label, _key, _lim in ((L["lbl.concepts"], "concepts", None),
                                   (L["lbl.keywords"], "keywords", 6),
                                   (L["lbl.funders"], "funders", None),
                                   (L["lbl.mesh"], "mesh", 6)):
            _txt = _join(w.get(_key), _lim)
            if _txt:
                lines.append("- **%s**: %s" % (_label, _txt))
        if w.get("is_retracted"):
            lines.append("- ⚠️ **%s**" % L["retracted"])
        # Full abstract
        abstract = w.get("abstract_snippet")
        if abstract:
            lines.append("")
            lines.append("> **%s**: %s" % (L["lbl.abstract"], abstract))
        lines.append("")

    # PRISMA screening funnel (machine rule-based screen, P0-B)
    prisma = meta.get("prisma") if isinstance(meta, dict) else None
    if prisma and prisma.get("stages"):
        lines.append("### %s\n" % L["prisma.title"])
        lines.append("| %s | %s |" % (L["prisma.stage"], L["prisma.count"]))
        lines.append("|---|---|")
        for s in prisma["stages"]:
            lines.append("| %s | %s |" % (s.get("label", s.get("stage")), s.get("count")))
        lines.append("")
        if prisma.get("stages")[2].get("reasons"):
            reasons = prisma["stages"][2]["reasons"]
            lines.append("%s: %s"
                         % (L["prisma.excl"],
                            ", ".join("%s=%d" % (k, v) for k, v in reasons.items())))
            lines.append("")
        lines.append("> ⚠️ %s" % prisma.get("note", L["prisma.note"]))
        lines.append("")

    # Study-type distribution
    dist = {}
    for w in works:
        st = w.get("study_type") or w.get("type") or "other"
        dist[st] = dist.get(st, 0) + 1
    lines.append("### %s\n" % L["study_dist"])
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
        lines.append("### %s\n" % L["yearly"])
        for y in sorted(yt):
            bar = "#" * max(1, round(yt[y] / max(yt.values()) * 20))
            lines.append("- %d: %d %s" % (y, yt[y], bar))
        lines.append("")

    # Safety / CSM subset
    safety = [w for w in works if w.get("is_safety")]
    if safety:
        lines.append("### %s\n" % L["safety.title"])
        lines.append(L["safety.intro"] % len(safety))
        lines.append("")
        for w in safety[:12]:
            title = (w.get("title") or "").replace("|", "/")
            lines.append("- [%s] %s — %s %s" % (
                _int_or_none(w.get("year")) or "—", title,
                "/".join(_src_list(w)) or "—",
                (" · " + str(w.get("url"))) if w.get("url") else ""))
        lines.append("")
        lines.append("> %s" % L["safety.note"])
        lines.append("")

    # ---- P0: evidence provenance + citation verification (ct-base §17.1) ----
    evidence = meta.get("evidence_log") if isinstance(meta, dict) else None
    verification = meta.get("verification") if isinstance(meta, dict) else None
    if evidence or verification:
        lines.append("### %s\n" % L["evidence.title"])
        if verification:
            if verification.get("skipped_preview"):
                skip = L["ev.preview"]
            elif verification.get("mode") == "top":
                skip = L["ev.verify.top"] % verification.get("top_n", 15)
            elif verification.get("mode") == "none":
                skip = L["ev.verify.none"]
            else:
                skip = ""
            lines.append("- **%s**: total=%s · verified=%s · %s=%s · %s=%s · unresolved=%s · "
                         "no_identifier=%s · suspicious=%s · %s=%s%s"
                         % (L["ev.verify"],
                            verification.get("total", 0), verification.get("verified", 0),
                            L["ev.bot_blocked"], verification.get("bot_blocked", 0),
                            L["ev.mismatch"], verification.get("mismatch", 0),
                            verification.get("unresolved", 0), verification.get("no_identifier", 0),
                            verification.get("suspicious", 0), L["ev.sampled"],
                            verification.get("unverified_sampled", 0), skip))
            if verification.get("bot_blocked"):
                lines.append("  - %s: %s%s" % (L["ev.bot_blocked"],
                                               verification.get("bot_blocked", 0),
                                               L["ev.bot_blocked.note"]))
            if verification.get("mismatch"):
                lines.append("  - %s: %s%s" % (L["ev.mismatch"],
                                               verification.get("mismatch", 0),
                                               L["ev.mismatch.note"]))
            lines.append("")
        if evidence:
            srcs = evidence.get("sources") or []
            if srcs:
                lines.append("**%s**:\n" % L["ev.src_prov"])
                lines.append("| %s | %s | %s | %s | %s | %s | %s | %s |"
                             % (L["ev.src"], L["ev.query"], L["ev.type"], L["ev.year"],
                                L["ev.safety"], L["ev.count"], L["ev.retrieved"], L["ev.status"]))
                lines.append("|---|---|---|---|---|---|---|---|")
                for s in srcs:
                    yf = s.get("year_from") or ""
                    yt_ = s.get("year_to") or ""
                    yr = ("%s–%s" % (yf, yt_)) if (yf or yt_) else "—"
                    lines.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
                        s.get("source"), (s.get("query") or "")[:80],
                        s.get("review_type") or "all", yr,
                        "Y" if s.get("safety") else "—", s.get("count", 0),
                        (s.get("retrieved_at") or "")[:19], s.get("status", "")))
                lines.append("")
            if evidence.get("generated_at"):
                lines.append("- **%s**: %s" % (L["ev.generated"], evidence["generated_at"]))
                lines.append("")
        lines.append("> %s" % L["ev.note"])
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
    ap.add_argument("--lang", default="auto", choices=["auto", "zh", "en"])
    args = ap.parse_args()

    data = json.load(open(args.inp, encoding="utf-8"))
    works = data.get("works", [])
    meta = {
        "topic": args.topic, "review_type": args.review_type,
        "year_from": args.year_from, "year_to": args.year_to, "safety": args.safety,
    }
    md = render(works, meta, lang=args.lang)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md)
        print("[OK] report ->", args.out)
    else:
        print(md)


if __name__ == "__main__":
    main()
