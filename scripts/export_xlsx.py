#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""export_xlsx.py - Export a ct-literature ``merged.json`` to a multi-sheet Excel
workbook (green theme, ct-base ``excel_style`` shared standard).

Sheets (names localized):
  1. README             - cover banner + KPI cards (count / safety / top-cited / span)
                          + search scope + field dictionary + data caveats
  2. Overview           - distribution blocks (year col chart; source/type/study_type
                          pies) + top-cited list; charts floated right (col E), no overlap
  3. Works              - unified literature table; title + url hyperlinked;
                           safety-relevant rows (is_safety) highlighted amber
  4. Safety-Related     - filtered subset where is_safety is true

Rendering standard: scripts/excel_style.py (vendored from ct-base/scripts/excel_style.py)
  - header row height 24px (HEADER_H)
  - per-cell zebra striping (light green + grey grid border)
  - safety-relevant rows highlighted with warn_bg
  - cover logo pinned top-right (icon_4x.png, scale 0.16)
  - native .xlsx charts (no web page)
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime

import xlsxwriter

# ═══════════════════════════════════════════════════════════════════════════
# import the shared excel rendering standard (vendored from ct-base)
# IMPORTANT (2026-08-11): ct-base is NEVER published. Every ct- skill must carry
# its own complete copy. We ONLY import from this skill's own `scripts/` dir.
# ═══════════════════════════════════════════════════════════════════════════
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
try:
    from excel_style import (
        make_formats, banner as _banner, page_decor as _page_decor,
        kpi_card as _kpi_card, cover_logo, PALETTES, FONT, HEADER_H,
        add_chart as _add_chart, chart_h as _chart_h, chart_w as _chart_w,
        dist_pie_points as _dist_pie_points, ROW_PX, BAND_GAP,
    )
except Exception as _e:  # pragma: no cover — vendored copy must be present
    raise RuntimeError("ct-literature export_xlsx: cannot import vendored "
                       "excel_style: " + str(_e))

P = PALETTES["literature"]
NAVY, BLUE, LIGHT = P["navy"], P["blue"], P["light"]
GRID, GREYTX = P["grid"], P["greytx"]
BANNER = P["banner"]

# distinct but on-brand fills for the source pie (so slices read clearly)
_SOURCE_COLOR = {
    "OpenAlex": "#2E7D4F",        # literature navy-green
    "EuropePMC": "#2E75B6",       # registry blue (clearly distinct)
    "SemanticScholar": "#BF9000", # amber (clearly distinct)
}
CHART_COL = "E"  # right-side anchor column for all overview charts (no overlap)


# ═══════════════════════════════════════════════════════════════════════════
# i18n — reuse vendored i18n; skill-specific labels live in _LOCAL.
# ═══════════════════════════════════════════════════════════════════════════
try:
    from i18n import (t as _base_t, set_lang as _base_set_lang,
                     is_chinese_os as _base_is_chinese_os)
except Exception:  # pragma: no cover
    _base_t = lambda k, **kw: k
    def _base_set_lang(c):
        pass
    def _base_is_chinese_os():
        return False

_LANG = "en"
_LOCAL = {
    "sheet.readme":    {"en": "README", "zh": "说明"},
    "sheet.works":     {"en": "Works", "zh": "文献总表"},
    "sheet.overview":  {"en": "Overview", "zh": "概览"},
    "sheet.safety":    {"en": "Safety-Related", "zh": "安全性相关"},
    "doc.title":       {"en": "Literature Evidence Base", "zh": "文献证据库"},
    "banner.title":    {"en": "Systematic Literature Review", "zh": "系统文献综述"},
    "kpi.count":       {"en": "Publications", "zh": "文献总数"},
    "kpi.count_sub":   {"en": "deduplicated", "zh": "已去重"},
    "kpi.safety":      {"en": "Safety-related", "zh": "安全性相关"},
    "kpi.safety_sub":  {"en": "is_safety flag", "zh": "安全性标记"},
    "kpi.cited":       {"en": "Top cited", "zh": "最高被引"},
    "kpi.cited_sub":   {"en": "citations", "zh": "次引用"},
    "kpi.span":        {"en": "Year span", "zh": "年份跨度"},
    "kpi.span_sub":    {"en": "publication years", "zh": "发表年份范围"},
    "prov.generated":  {"en": "Generated", "zh": "生成时间"},
    "prov.source":     {"en": "Sources", "zh": "数据来源"},
    "col.source":      {"en": "Source", "zh": "来源"},
    "col.year":        {"en": "Year", "zh": "年份"},
    "col.title":       {"en": "Title", "zh": "标题"},
    "col.authors":     {"en": "Authors", "zh": "作者"},
    "col.publication": {"en": "Journal", "zh": "期刊"},
    "col.type":        {"en": "Type", "zh": "类型"},
    "col.study_type":  {"en": "Study type", "zh": "研究类型"},
    "col.cited":       {"en": "Cited by", "zh": "被引"},
    "col.is_safety":   {"en": "Safety", "zh": "安全性"},
    "col.url":         {"en": "Link", "zh": "链接"},
    "col.oa":          {"en": "Open Access", "zh": "开放获取链接"},
    "col.mesh":        {"en": "MeSH", "zh": "MeSH"},
    "col.funders":     {"en": "Funders", "zh": "资助方"},
    "col.count":       {"en": "Count", "zh": "数量"},
    "col.share":       {"en": "Share", "zh": "占比"},
    "col.unknown":     {"en": "(unknown)", "zh": "(未知)"},
    "col.topic":       {"en": "Topic", "zh": "主题"},
    "ov.year":         {"en": "Publications by year", "zh": "逐年文献分布"},
    "ov.source":       {"en": "By source", "zh": "按来源分布"},
    "ov.type":         {"en": "By type", "zh": "按类型分布"},
    "ov.stype":        {"en": "By study type", "zh": "按研究类型分布"},
    "ov.top":          {"en": "Most cited", "zh": "高被引文献"},
    "ov.total":        {"en": "Total", "zh": "合计"},
    "ov.banner":       {"en": "Literature Search Summary", "zh": "文献检索结果概要"},
    "ov.intro":        {"en": "Distribution tables and charts below are auto-summarised from the search results: each block shows the data table on the left and the corresponding chart on the right.",
                       "zh": "下列数据表与图表由检索结果自动汇总生成：每个区块左侧为分布数据表、右侧为对应统计图。"},
    # ---- README scope (search overview) ----
    "scope.title":     {"en": "Search scope", "zh": "检索概览"},
    "scope.topic":     {"en": "Topic", "zh": "检索主题"},
    "scope.filter":    {"en": "Filter", "zh": "检索范围"},
    "scope.source":    {"en": "Sources", "zh": "数据来源"},
    "scope.year":      {"en": "Year range", "zh": "时间范围"},
    # ---- field dictionary (field meanings) ----
    "field.title":     {"en": "Field dictionary", "zh": "字段说明"},
    "field.col":       {"en": "Field", "zh": "字段"},
    "field.mean":      {"en": "Meaning", "zh": "含义"},
    "f.source":        {"en": "Source repository (OpenAlex / Europe PMC / Semantic Scholar)",
                       "zh": "文献来源库（OpenAlex / Europe PMC / Semantic Scholar）"},
    "f.title":         {"en": "Work title (click the link to open)", "zh": "文献标题（点击链接可访问）"},
    "f.authors":       {"en": "Author list (first 6)", "zh": "作者列表（前 6 位）"},
    "f.year":          {"en": "Publication year", "zh": "发表年份"},
    "f.publication":   {"en": "Journal / venue", "zh": "发表期刊 / 会议"},
    "f.type":          {"en": "Work type (article, etc.)", "zh": "文献类型（article 等）"},
    "f.study_type":    {"en": "Study type (RCT / review / case-report …)", "zh": "研究类型（RCT / 综述 / 病例报告 等）"},
    "f.cited":         {"en": "Citation count", "zh": "被引次数"},
    "f.is_safety":     {"en": "Safety-related flag (Y / —, amber-highlighted in the table)",
                       "zh": "是否安全性相关（Y / —，表中琥珀色高亮）"},
    "f.url":           {"en": "Link to the original / DOI", "zh": "原文 / DOI 链接"},
    "f.mesh":          {"en": "MeSH terms (Europe PMC)", "zh": "医学主题词（Europe PMC）"},
    "f.funders":       {"en": "Funding organisations (OpenAlex)", "zh": "资助机构（OpenAlex）"},
    # ---- caveat callout (data caveats) ----
    "caveat.title":    {"en": "Data caveats", "zh": "数据局限"},
    "caveat.text":     {"en": "① OpenAlex is the primary source; Europe PMC / Semantic Scholar are optional enrichments. ② Abstract availability depends on the source (Europe PMC ≈100%, OpenAlex partial). ③ Deduplicated by DOI / title; multi-source works keep provenance. ④ This is published-literature evidence, NOT trial-registry metadata (see ct-registry); the safety subset is qualitative, not FAERS quantitative signal.",
                       "zh": "① OpenAlex 为主源，Europe PMC / Semantic Scholar 为可选增强；② 摘要可用性取决于来源（Europe PMC ≈100%，OpenAlex 部分缺失）；③ 按 DOI / 标题去重，多源文献保留来源溯源；④ 本表为已发表文献证据，非试验注册信息（见 ct-registry）；安全性子集为定性证据，非 FAERS 定量信号。"},
    # ---- evidence log (P0: provenance + citation verification, ct-base §17.1) ----
    "sheet.evidence":   {"en": "Evidence Log", "zh": "证据溯源"},
    "ev.title":        {"en": "Evidence Provenance & Citation Verification", "zh": "证据溯源与引文验证"},
    "ev.generated":    {"en": "Generated", "zh": "生成时间"},
    "ev.verify":       {"en": "Citation verification", "zh": "引文验证"},
    "ev.verified":     {"en": "Verified", "zh": "已验证"},
    "ev.unresolved":   {"en": "Unresolved", "zh": "未解析"},
    "ev.no_id":        {"en": "No identifier", "zh": "无标识"},
    "ev.suspicious":   {"en": "Suspicious", "zh": "可疑"},
    "ev.preview":      {"en": "preview — verification skipped", "zh": "预览，已跳过验证"},
    "ev.src":          {"en": "Source", "zh": "来源"},
    "ev.query":        {"en": "Query", "zh": "检索式"},
    "ev.type":         {"en": "Type", "zh": "类型"},
    "ev.year":         {"en": "Year", "zh": "年份"},
    "ev.safety":       {"en": "Safety", "zh": "安全性"},
    "ev.count":        {"en": "Count", "zh": "数量"},
    "ev.retrieved":    {"en": "Retrieved", "zh": "检索时间"},
    "ev.status":       {"en": "Status", "zh": "状态"},
    "ev.note":         {"en": "Provenance audit trail (ct-base §17.1): every evidence item is traceable to its source query and retrieval time. Verification status is advisory, not a substitute for human review.",
                       "zh": "证据溯源审计（ct-base §17.1）：每条证据可回溯至来源检索式与检索时间；验证状态仅供参考，不替代人工核查。"},
}


def set_lang(code):
    global _LANG
    _LANG = "zh" if code in ("zh", "zh-CN", "zh-cn") else "en"
    _base_set_lang(code)


def t(key, **kw):
    if key in _LOCAL:
        return _LOCAL[key][_LANG].format(**kw)
    return _base_t(key, **kw)


def _style_series(chart_type, labels=None):
    lbl_font = {"size": 9, "font_name": FONT, "color": NAVY, "bold": False}
    opts = {"data_labels": {"value": True, "font": lbl_font}}
    if chart_type == "pie":
        opts = {"data_labels": {"percentage": True, "category": True,
                                "num_format": "0.0%", "font": lbl_font}, "gap": 55}
    if chart_type in ("col", "barh"):
        opts["gap"] = 55
        opts["fill"] = {"color": BLUE}
    if chart_type == "line":
        opts["line"] = {"color": NAVY, "width": 2.25}
        opts["marker"] = {"type": "circle", "size": 6,
                           "fill": {"color": BLUE}, "border": {"color": NAVY}}
    return opts


def _qref(name, cell):
    return "'%s'!%s" % (name, cell)


def _normalize_link(u):
    """Return a hyperlink-safe URL, or '' if `u` is not linkable.

    xlsxwriter.write_url raises 'Unknown URL type' for anything without a known
    scheme (http/https/ftp/mailto…). Real sources sometimes yield a bare DOI —
    e.g. Semantic Scholar ``externalIds.DOI`` or Europe PMC ``doi`` when no
    fullTextUrl is present — so normalise those to ``https://doi.org/<doi>`` and
    drop the rest (write as plain text instead of crashing the whole workbook).
    """
    if not u:
        return ""
    u = str(u).strip()
    if u.startswith(("http://", "https://", "ftp://", "ftps://", "mailto:")):
        return u
    if u.startswith("10."):
        return "https://doi.org/" + u
    return ""


# ═══════════════════════════════════════════════════════════════════════════
# sheet builders
# ═══════════════════════════════════════════════════════════════════════════
def build_readme(wb, data, fmts):
    ws = wb.add_worksheet(t("sheet.readme"))
    _page_decor(ws, t("doc.title"), fmts)
    ws.set_tab_color(NAVY)
    _banner(ws, 0, 0, 14, t("banner.title"), fmts)
    ws.set_row(0, 30)

    works = data.get("works") or []
    n = data.get("count") or len(works)
    n_safety = sum(1 for w in works if w.get("is_safety"))
    top = max((w.get("cited_by_count") or 0) for w in works) if works else 0
    yrs = sorted(y for y in (w.get("year") for w in works) if y)
    span = "%d–%d" % (yrs[0], yrs[-1]) if yrs else "—"
    meta = data.get("meta") or {}

    _logo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                         "assets", "icon_4x.png")
    cover_logo(ws, _logo, col=14, scale=0.16, x_offset=20, y_offset=2)

    # rich-text subtitle (row 1): topic + generated time
    topic = meta.get("topic") or t("doc.title")
    ws.write_rich_string(1, 0,
                         fmts["sub"], t("scope.topic") + "：",
                         fmts["body"], (topic or t("col.unknown"))[:60],
                         fmts["note"], "   " + datetime.now().strftime("%Y-%m-%d %H:%M"))
    ws.set_row(1, 20)

    # ---- KPI cards (row 3): 4 cards ----
    _kpi_card(ws, 3, 0, t("kpi.count"), n, t("kpi.count_sub"), fmts)
    _kpi_card(ws, 3, 4, t("kpi.safety"), n_safety, t("kpi.safety_sub"), fmts)
    _kpi_card(ws, 3, 8, t("kpi.cited"), top, t("kpi.cited_sub"), fmts)
    _kpi_card(ws, 3, 12, t("kpi.span"), span, t("kpi.span_sub"), fmts)
    ws.set_row(3, 18)   # label
    ws.set_row(4, 32)   # value (22pt)
    ws.set_row(5, 14)   # sub

    # ---- scope (search overview) ----
    r = 8
    ws.set_row(7, 6)
    ws.merge_range(7, 0, 7, 14, "", fmts["divider"])
    ws.write(r, 0, t("scope.title"), fmts["sub"])
    r += 1
    src = ", ".join(sorted(set(w.get("source", "") for w in works))) or "—"
    yf = meta.get("year_from")
    yt = meta.get("year_to")
    yr_range = ("%s–%s" % (yf, yt)) if (yf or yt) else "—"
    rt = meta.get("review_type") or "all"
    scope = [
        (t("scope.topic"), topic or t("col.unknown")),
        (t("scope.filter"), rt),
        (t("scope.source"), src),
        (t("scope.year"), yr_range),
    ]
    for k, v in scope:
        ws.write(r, 0, k, fmts["kpi_label"])
        ws.merge_range(r, 1, r, 14, v, fmts["body"])
        r += 1

    # ---- field dictionary (field meanings) ----
    r += 1
    ws.write(r, 0, t("field.title"), fmts["sub"])
    r += 1
    ws.write(r, 0, t("field.col"), fmts["header"])
    ws.merge_range(r, 1, r, 14, t("field.mean"), fmts["header"])
    r += 1
    fields = [
        ("col.source", "f.source"), ("col.title", "f.title"),
        ("col.authors", "f.authors"), ("col.year", "f.year"),
        ("col.publication", "f.publication"), ("col.type", "f.type"),
        ("col.study_type", "f.study_type"), ("col.cited", "f.cited"),
        ("col.is_safety", "f.is_safety"), ("col.url", "f.url"),
        ("col.mesh", "f.mesh"), ("col.funders", "f.funders"),
    ]
    for i, (ck, mk) in enumerate(fields):
        zebra = (i % 2 == 1)
        key_fmt = fmts["fkey_z"] if zebra else fmts["fkey"]
        val_fmt = fmts["zebra"] if zebra else fmts["plain"]
        ws.write(r, 0, t(ck), key_fmt)
        ws.merge_range(r, 1, r, 14, t(mk), val_fmt)
        r += 1

    # ---- caveat callout (data caveats) ----
    r += 1
    ws.write(r, 0, t("caveat.title"), fmts["sub"])
    r += 1
    ws.merge_range(r, 0, r + 2, 14, t("caveat.text"), fmts["warn"])
    ws.set_row(r, 18)
    ws.set_row(r + 1, 18)
    ws.set_row(r + 2, 18)

    ws.set_column(0, 0, 16)
    ws.set_column(1, 14, 13)
    return ws


def _write_works_table(ws, works, fmts, safety_hl, start_row=0):
    cols = [("source", t("col.source"), 14),
            ("year", t("col.year"), 8),
            ("title", t("col.title"), 52),
            ("authors", t("col.authors"), 34),
            ("publication", t("col.publication"), 26),
            ("type", t("col.type"), 14),
            ("study_type", t("col.study_type"), 20),
            ("cited_by_count", t("col.cited"), 10),
            ("is_safety", t("col.is_safety"), 10),
            ("url", t("col.url"), 22),
            ("open_access_url", t("col.oa"), 28)]
    ws.set_row(start_row, HEADER_H)
    for ci, (_, h, _) in enumerate(cols):
        ws.write(start_row, ci, h, fmts["header"])
    for ri, w in enumerate(works, start=start_row + 1):
        zebra = ((ri - start_row - 1) % 2 == 1)
        base = fmts["zebra"] if zebra else fmts["plain"]
        # safety-relevant rows get an amber highlight (wins over zebra)
        row_fmt = safety_hl if w.get("is_safety") else base
        for ci, (key, _, _) in enumerate(cols):
            v = w.get(key)
            if key == "authors":
                av = v if isinstance(v, list) else [str(v)]
                ws.write(ri, ci, ", ".join(av)[:120], row_fmt)
            elif key == "title":
                ws.write(ri, ci, (v or "")[:240], row_fmt)
            elif key == "is_safety":
                ws.write(ri, ci, "Y" if v else "—",
                         fmts["center"] if not w.get("is_safety") else safety_hl)
            elif key == "url":
                link = _normalize_link(v)
                if link:
                    ws.write_url(ri, ci, link, fmts["link"], string=str(v)[:42])
                else:
                    ws.write(ri, ci, str(v)[:42] if v else "", row_fmt)
            elif key == "open_access_url":
                oa = _normalize_link(v)
                if oa:
                    ws.write_url(ri, ci, oa, fmts["link"], string="OA PDF")
                else:
                    ws.write(ri, ci, "—", row_fmt)
            elif key == "cited_by_count":
                ws.write(ri, ci, v if v is not None else 0, fmts["right"])
            else:
                ws.write(ri, ci, v, row_fmt)
    return len(works)


def build_works(wb, data, fmts, safety_hl):
    ws = wb.add_worksheet(t("sheet.works"))
    _page_decor(ws, t("sheet.works"), fmts)
    ws.set_tab_color(BLUE)
    works = data.get("works") or []
    n = _write_works_table(ws, works, fmts, safety_hl)
    ws.freeze_panes(1, 0)
    if works:
        ws.autofilter(0, 0, n, 11)
    for ci, (_, _, w) in enumerate([("source", "", 14), ("year", "", 8),
                                    ("title", "", 52), ("authors", "", 34),
                                    ("publication", "", 26), ("type", "", 14),
                                    ("study_type", "", 20), ("cited", "", 10),
                                    ("safety", "", 10), ("url", "", 22),
                                    ("open_access_url", "", 28)]):
        ws.set_column(ci, ci, w)
    return ws


def _render_dist_block(ws, row0, title, label_header, chart_type, items, fmts, wb, sheet_name, color_map=None):
    """A distribution block: block title + (label/count/share) table + total row +
    data bar + right-side chart. Returns the 0-based bottom row so the caller can
    step to the next band without over-reserving blank rows (prevents overlap)."""
    total = sum(c for _, c in items) or 1
    ws.merge_range(row0, 0, row0, 2, title, fmts["block_title"])
    hdr = row0 + 1
    ws.write(hdr, 0, label_header, fmts["header"])
    ws.write(hdr, 1, t("col.count"), fmts["header"])
    ws.write(hdr, 2, t("col.share"), fmts["header"])
    r = hdr + 1
    for label, cnt in items:
        zebra = ((r - hdr) % 2 == 1)
        ws.write(r, 0, label if label else t("col.unknown"),
                 fmts["zebra"] if zebra else fmts["plain"])
        ws.write(r, 1, cnt, fmts["right"])
        ws.write(r, 2, cnt / total, fmts["pct"])
        r += 1
    last = r - 1
    # total row
    ws.write(last + 1, 0, t("ov.total"), fmts["sumrow"])
    ws.write(last + 1, 1, total, fmts["sumrow"])
    ws.write(last + 1, 2, 1.0, fmts["pct"])
    sum_row = last + 1
    r = sum_row + 1
    # data bar on the share column only
    if last >= hdr + 1:
        ws.conditional_format(hdr + 1, 2, last, 2,
                              {"type": "data_bar", "bar_color": BLUE})
    # native chart on the RIGHT (column E), top-aligned with the data header row.
    if items:
        last_ch = last
        n_rows = last - hdr
        h = _chart_h(n_rows)
        w = h if chart_type == "pie" else _chart_w(h)
        ch = _add_chart(wb, chart_type, title, w, h)
        cats = [sheet_name, hdr + 1, 0, last_ch, 0]
        vals = [sheet_name, hdr, 1, last_ch, 1]
        pts = None
        if chart_type == "pie":
            pts = _dist_pie_points("source", items, color_map) if color_map \
                  else _dist_pie_points("type", items)
        ch.add_series({
            "categories": cats,
            "values": vals,
            "points": pts or [],
            **_style_series(chart_type),
        })
        ws.insert_chart("%s%d" % (CHART_COL, hdr), ch)
    # block extent = max(table bottom, chart bottom) so the next band never overlaps
    table_bottom = last
    chart_bottom = row0 + (h // ROW_PX) if items else 0
    return max(table_bottom, chart_bottom)


def _render_top_block(ws, row0, fmts, works):
    """Top-cited list block (no chart)."""
    ws.merge_range(row0, 0, row0, 2, t("ov.top"), fmts["block_title"])
    hdr = row0 + 1
    ws.write(hdr, 0, t("col.title"), fmts["header"])
    ws.write(hdr, 1, t("col.cited"), fmts["header"])
    r = hdr + 1
    for i, w in enumerate(sorted(works, key=lambda x: -(x.get("cited_by_count") or 0))[:10]):
        zebra = ((r - hdr) % 2 == 1)
        ws.write(r, 0, (w.get("title") or "")[:90],
                 fmts["zebra"] if zebra else fmts["plain"])
        ws.write(r, 1, w.get("cited_by_count") or 0, fmts["right"])
        r += 1
    return r - 1


def build_overview(wb, data, fmts):
    ws = wb.add_worksheet(t("sheet.overview"))
    _page_decor(ws, t("sheet.overview"), fmts)
    ws.set_tab_color(BLUE)
    works = data.get("works") or []
    name = t("sheet.overview")

    _banner(ws, 0, 0, 12, t("ov.banner"), fmts)
    ws.merge_range(1, 0, 1, 12, t("ov.intro"), fmts["note"])

    row0 = 3
    # 1) year distribution (column chart)
    yr = Counter(w.get("year") for w in works if w.get("year"))
    yitems = sorted(yr.items())
    if yitems:
        row0 = _render_dist_block(ws, row0, t("ov.year"), t("col.year"),
                                  "col", yitems, fmts, wb, name) + 1 + BAND_GAP
    # 2) source distribution (pie, branded colours)
    src = Counter(w.get("source", "—") for w in works)
    sitems = sorted(src.items(), key=lambda x: -x[1])
    if sitems:
        row0 = _render_dist_block(ws, row0, t("ov.source"), t("col.source"),
                                  "pie", sitems, fmts, wb, name, _SOURCE_COLOR) + 1 + BAND_GAP
    # 3) type distribution (pie)
    typ = Counter(w.get("type", "—") for w in works)
    titems = sorted(typ.items(), key=lambda x: -x[1])
    if titems:
        row0 = _render_dist_block(ws, row0, t("ov.type"), t("col.type"),
                                  "pie", titems, fmts, wb, name) + 1 + BAND_GAP
    # 4) study_type distribution (pie)
    st = Counter((w.get("study_type") or "—") for w in works)
    stitems = sorted(st.items(), key=lambda x: -x[1])
    if stitems:
        row0 = _render_dist_block(ws, row0, t("ov.stype"), t("col.study_type"),
                                  "pie", stitems, fmts, wb, name) + 1 + BAND_GAP
    # 5) top-cited list
    row0 = _render_top_block(ws, row0, fmts, works) + 1 + BAND_GAP

    ws.set_column(0, 0, 40)
    for col in range(1, 3):
        ws.set_column(col, col, 12)
    for col in range(3, 12):   # narrow gutter so right-side charts never crowd tables
        ws.set_column(col, col, 3)
    return ws


def build_safety(wb, data, fmts, safety_hl):
    ws = wb.add_worksheet(t("sheet.safety"))
    _page_decor(ws, t("sheet.safety"), fmts)
    ws.set_tab_color(BLUE)
    works = [w for w in (data.get("works") or []) if w.get("is_safety")]
    n = _write_works_table(ws, works, fmts, safety_hl)
    ws.freeze_panes(1, 0)
    for ci, w in enumerate([14, 8, 52, 34, 26, 14, 20, 10, 10, 22]):
        ws.set_column(ci, ci, w)
    return ws


# ═══════════════════════════════════════════════════════════════════════════
# entry point
# ═══════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════
# evidence log (P0: provenance + citation verification, ct-base §17.1)
# ═══════════════════════════════════════════════════════════════
def build_evidence(wb, data, fmts):
    ws = wb.add_worksheet(t("sheet.evidence"))
    _page_decor(ws, t("sheet.evidence"), fmts)
    ws.set_tab_color(NAVY)
    _banner(ws, 0, 0, 12, t("ev.title"), fmts)
    ws.set_row(0, 30)
    evidence = data.get("evidence_log") or {}
    verification = data.get("verification") or {}
    r = 2

    # generated time
    if evidence.get("generated_at"):
        ws.write(r, 0, t("ev.generated"), fmts["kpi_label"])
        ws.merge_range(r, 1, r, 12, evidence["generated_at"], fmts["body"])
        r += 1

    # citation verification summary block
    if verification:
        ws.write(r, 0, t("ev.verify"), fmts["sub"])
        r += 1
        skip = (" " + t("ev.preview")) if verification.get("skipped_preview") else ""
        vrows = [
            (t("ev.verified"), verification.get("verified", 0)),
            (t("ev.unresolved"), verification.get("unresolved", 0)),
            (t("ev.no_id"), verification.get("no_identifier", 0)),
            (t("ev.suspicious"), verification.get("suspicious", 0)),
        ]
        ws.write(r, 0, "total", fmts["fkey"])
        ws.merge_range(r, 1, r, 2, verification.get("total", 0), fmts["right"])
        r += 1
        for label, cnt in vrows:
            ws.write(r, 0, label, fmts["fkey"])
            ws.merge_range(r, 1, r, 2, cnt, fmts["right"])
            r += 1
        ws.merge_range(r, 0, r, 12, ("verified=%s · unresolved=%s · no_identifier=%s · "
                                     "suspicious=%s%s" % (
                                         verification.get("verified", 0),
                                         verification.get("unresolved", 0),
                                         verification.get("no_identifier", 0),
                                         verification.get("suspicious", 0), skip)), fmts["note"])
        r += 2

    # source provenance table
    srcs = evidence.get("sources") or []
    if srcs:
        ws.write(r, 0, t("ev.src") + " provenance / 来源溯源", fmts["sub"])
        r += 1
        headers = [t("ev.src"), t("ev.query"), t("ev.type"), t("ev.year"),
                   t("ev.safety"), t("ev.count"), t("ev.retrieved"), t("ev.status")]
        for ci, h in enumerate(headers):
            ws.write(r, ci, h, fmts["header"])
        r += 1
        for s in srcs:
            yf = s.get("year_from") or ""
            yt_ = s.get("year_to") or ""
            yr = ("%s–%s" % (yf, yt_)) if (yf or yt_) else "—"
            row = [s.get("source"), (s.get("query") or "")[:120],
                   s.get("review_type") or "all", yr,
                   "Y" if s.get("safety") else "—", s.get("count", 0),
                   (s.get("retrieved_at") or "")[:19], s.get("status", "")]
            for ci, v in enumerate(row):
                ws.write(r, ci, v, fmts["plain"])
            r += 1
        r += 1

    # caveat callout
    ws.merge_range(r, 0, r + 2, 12, t("ev.note"), fmts["warn"])
    ws.set_row(r, 18)
    ws.set_row(r + 1, 18)
    ws.set_row(r + 2, 18)

    ws.set_column(0, 0, 16)
    ws.set_column(1, 1, 50)
    for col in range(2, 8):
        ws.set_column(col, col, 14)
    return ws


def _coerce_int(v):
    """Coerce a possibly string/None numeric field to int, else None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str) and v.strip().lstrip("-").isdigit():
        return int(v.strip())
    return None


def sanitize(data):
    """Normalise a merged payload so mixed / missing types cannot crash sheets.

    Real-world merged.json may carry year as str, cited_by_count as None,
    sources as None, or list fields holding None elements. Sorting or joining
    those raises TypeError deep inside a sheet builder and aborts the whole
    workbook, so we coerce once at the entry point.
    """
    if not isinstance(data, dict):
        data = {"works": data if isinstance(data, list) else []}
    works = [w for w in (data.get("works") or []) if isinstance(w, dict)]
    clean = []
    for w in works:
        w = dict(w)
        w["year"] = _coerce_int(w.get("year"))
        w["cited_by_count"] = _coerce_int(w.get("cited_by_count")) or 0
        srcs = w.get("sources")
        if not isinstance(srcs, (list, tuple)) or not srcs:
            srcs = [w.get("source")]
        w["sources"] = [str(s) for s in srcs if s]
        w["source"] = str(w.get("source") or (w["sources"][0] if w["sources"] else "—"))
        for k in ("authors", "mesh", "concepts", "keywords", "funders"):
            v = w.get(k)
            w[k] = [str(x) for x in v if x] if isinstance(v, (list, tuple)) else []
        for k in ("title", "abstract_snippet"):
            if w.get(k) is not None and not isinstance(w[k], str):
                w[k] = str(w[k])
        clean.append(w)
    data = dict(data)
    data["works"] = clean
    data["count"] = data.get("count") if isinstance(data.get("count"), int) else len(clean)
    return data


def export_workbook(data, out_path, lang="auto"):
    data = sanitize(data)
    if lang == "auto":
        set_lang("zh" if _base_is_chinese_os() else "en")
    elif lang == "zh":
        set_lang("zh")
    else:
        set_lang("en")
    wb = xlsxwriter.Workbook(out_path)
    fmts = make_formats(wb, PALETTES["literature"])
    # safety-row highlight (amber) — local extension of the shared format set
    fmts["safety_hl"] = wb.add_format({"bg_color": P["warn_bg"], "border": 1,
                                       "border_color": GRID, "font_name": FONT,
                                       "font_size": 10, "valign": "top",
                                       "text_wrap": True})
    build_readme(wb, data, fmts)
    build_overview(wb, data, fmts)
    build_works(wb, data, fmts, fmts["safety_hl"])
    build_safety(wb, data, fmts, fmts["safety_hl"])
    build_evidence(wb, data, fmts)
    wb.close()


def main():
    ap = argparse.ArgumentParser(description="Export ct-literature merged.json to .xlsx")
    ap.add_argument("--in-json", required=True, help="merged.json")
    ap.add_argument("--out", required=True, help="output .xlsx path")
    ap.add_argument("--lang", default="auto", choices=["auto", "zh", "en"])
    ap.add_argument("--topic", default=None, help="search topic (for README scope)")
    ap.add_argument("--review-type", default=None, help="review type filter")
    ap.add_argument("--year-from", default=None, help="year from")
    ap.add_argument("--year-to", default=None, help="year to")
    args = ap.parse_args()
    with open(args.in_json, encoding="utf-8") as f:
        data = json.load(f)
    if "meta" not in data:
        data["meta"] = {
            "topic": args.topic,
            "review_type": args.review_type,
            "year_from": args.year_from,
            "year_to": args.year_to,
        }
    export_workbook(data, args.out, lang=args.lang)
    print("[OK] wrote", args.out)


if __name__ == "__main__":
    main()
