#!/usr/bin/env python3
"""ct-literature → self-contained HTML report (no Excel needed to view).

Reads `.merged.json` (OpenAlex + Europe PMC merged evidence base) and renders a
single standalone .html file (inline CSS, safety-row highlight, source/type
distributions as CSS bars) so content is fully readable in any browser / the
WorkBuddy artifact preview without the client's limited xlsx viewer.

Theme: literature academic green, reusing vendored excel_style palette.

Usage:
    python export_html.py --in-json ../out_live/.merged.json \
                          --out ../out_live/lit_report.html --lang zh
"""
import os, sys, json, html, argparse, datetime
from collections import Counter

# IMPORTANT (2026-08-11): ct-base is NEVER published. Every ct- skill must carry
# its own complete copy. We ONLY import from this skill's own `scripts/` dir.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import excel_style as X

PALETTE = X.PALETTES["literature"]

_LABELS = {
    "en": {
        "doc_title": "Literature Evidence Base",
        "generated": "Generated", "kpi.total": "Works", "kpi.safety": "Safety-related",
        "search.topic": "Search Topic", "search.keywords": "Generated Keywords",
        "search.filter": "Filter", "search.none": "—",
        "kpi.year": "Year Span", "kpi.topcited": "Top Cited",
        "works": "Works", "col.source": "Source", "col.id": "ID", "col.title": "Title",
        "col.authors": "Authors", "col.year": "Year", "col.pub": "Publication",
        "col.type": "Type", "col.study": "Study", "col.cited": "Cited", "col.link": "Link",
        "col.oa": "Open Access",
        "col.abstract": "Abstract", "overview": "Overview", "by_src": "By Source",
        "by_type": "By Type", "by_year": "By Year", "safety": "Safety / CSM Subset",
        "evidence": "Evidence & Verification", "ev.verify": "Citation verification",
        "ev.verified": "Verified", "ev.bot_blocked": "Bot-blocked",
        "ev.bot_blocked.note": "publisher returned 403 to automated access — DOI is real, not a broken link",
        "ev.unresolved": "Unresolved",
        "ev.no_id": "No identifier", "ev.suspicious": "Suspicious",
        "ev.mismatch": "Mismatch",
        "ev.mismatch.note": "identifier resolved to a LIVE resource but title/author do NOT match — possible hallucinated/incorrect id",
        "cfg.warn": ("OpenAlex API key not configured — this run used the keyless pool "
                     "(100 credits/day, easily rate-limited). Apply for a FREE key and write it "
                     "to the skill `.env` as `OPENALEX_API_KEY=<key>`, then re-run for full coverage:"),
        "ev.preview": "preview — skipped", "ev.src": "Source", "ev.query": "Query",
        "ev.type": "Type", "ev.year": "Year", "ev.safety": "Safety",
        "ev.count": "Count", "ev.retrieved": "Retrieved", "ev.status": "Status",
    },
    "zh": {
        "doc_title": "文献证据库",
        "generated": "生成时间", "kpi.total": "文献数", "kpi.safety": "安全性相关",
        "search.topic": "检索主题", "search.keywords": "生成关键字",
        "search.filter": "筛选条件", "search.none": "—",
        "kpi.year": "年份跨度", "kpi.topcited": "最高被引",
        "works": "文献列表", "col.source": "来源", "col.id": "ID", "col.title": "标题",
        "col.authors": "作者", "col.year": "年份", "col.pub": "期刊",
        "col.type": "类型", "col.study": "研究类型", "col.cited": "被引", "col.link": "链接",
        "col.oa": "开放获取链接",
        "col.abstract": "摘要", "overview": "概览", "by_src": "按来源", "by_type": "按类型",
        "by_year": "按年份", "safety": "安全性 / CSM 子集",
        "evidence": "证据溯源与引文验证", "ev.verify": "引文验证",
        "ev.verified": "已验证", "ev.bot_blocked": "出版社拦爬",
        "ev.bot_blocked.note": "出版社对自动化访问回 403 —— DOI 真实有效、非断链",
        "ev.unresolved": "未解析",
        "ev.no_id": "无标识", "ev.suspicious": "可疑",
        "ev.mismatch": "不一致",
        "ev.mismatch.note": "标识符解析到存活资源，但标题/作者不一致 —— 可能为幻觉或错误 id",
        "cfg.warn": ("未配置 OpenAlex API key —— 本次以 keyless 模式运行（限 100 次/天，易触发 429 限流）。"
                     "建议免费申请 key 并写入技能目录 `.env`（`OPENALEX_API_KEY=<key>`）后重跑以获得完整覆盖："),
        "ev.preview": "预览，已跳过", "ev.src": "来源", "ev.query": "检索式",
        "ev.type": "类型", "ev.year": "年份", "ev.safety": "安全性",
        "ev.count": "数量", "ev.retrieved": "检索时间", "ev.status": "状态",
    },
}


def esc(v):
    return html.escape("" if v is None else str(v))


def _html_link(u):
    """Normalise a link target: keep http(s)/ftp/mailto, prefix bare DOIs with
    https://doi.org/, and return '' for anything non-linkable (so we render '—'
    instead of a broken href)."""
    if not u:
        return ""
    u = str(u).strip()
    if u.startswith(("http://", "https://", "ftp://", "mailto:")):
        return u
    if u.startswith("10."):
        return "https://doi.org/" + u
    return ""


def bar(value, maxv, color):
    v = float(value or 0)
    pct = max(0, min(100, v / maxv * 100)) if maxv else 0
    return (f'<div class="barwrap"><div class="bar" style="width:{pct:.1f}%;'
            f'background:{color};"></div><span class="barval">{v:.0f}</span></div>')


def _sanitize(data):
    """Reuse the xlsx exporter's type-normalisation so both stay in sync."""
    try:
        import export_xlsx
        return export_xlsx.sanitize(data)
    except Exception:
        # Minimal inline fallback if the xlsx exporter is unavailable.
        works = [w for w in (data.get("works") or []) if isinstance(w, dict)]
        out = []
        for w in works:
            w = dict(w)
            y = w.get("year")
            w["year"] = y if isinstance(y, int) and not isinstance(y, bool) else (
                int(y) if isinstance(y, str) and y.strip().isdigit() else None)
            c = w.get("cited_by_count")
            w["cited_by_count"] = c if isinstance(c, int) else 0
            out.append(w)
        data = dict(data)
        data["works"] = out
        return data


def prisma_funnel_svg(prisma, P):
    """Inline SVG PRISMA-2020 funnel (no third-party deps). Returns '' if empty."""
    stages = (prisma or {}).get("stages") or []
    if not stages:
        return ""
    maxc = max((s.get("count") or 0) for s in stages) or 1
    W, H, pad, top = 620, 340, 24, 18
    n = len(stages)
    band_h = (H - top - 24) / n
    colors = [P["navy"], P["blue"], P["banner"], P["warn_bd"]]
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
           f'width="100%" role="img" aria-label="PRISMA funnel">']
    for i, s in enumerate(stages):
        c = s.get("count") or 0
        w = max(50, c / maxc * (W - 2 * pad))
        x = (W - w) / 2.0
        y = top + i * band_h
        col = colors[i % len(colors)]
        svg.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{band_h - 6:.1f}" '
                   f'rx="6" fill="{col}" opacity="0.88"/>')
        cx = W / 2.0
        cy = y + (band_h - 6) / 2.0
        label = (s.get("label") or s.get("stage") or "")
        if len(label) > 42:
            label = label[:40] + "…"
        svg.append(f'<text x="{cx:.1f}" y="{cy - 2:.1f}" fill="#fff" font-size="13" '
                   f'text-anchor="middle" font-family="sans-serif">{esc(label)}</text>')
        svg.append(f'<text x="{cx:.1f}" y="{cy + 15:.1f}" fill="#fff" font-size="15" '
                   f'font-weight="700" text-anchor="middle" font-family="sans-serif">n = {c}</text>')
    svg.append('</svg>')
    return "".join(svg)


def render(data, lang):
    # resolve "auto" to a concrete language (mirrors ct-pipeline fix) — never
    # index _LABELS with the literal "auto" (KeyError).
    if lang == "auto":
        import locale as _loc
        try:
            _l = (_loc.getdefaultlocale()[0] or "zh").lower()
        except Exception:
            _l = "zh"
        lang = "zh" if _l.startswith("zh") else "en"
    L = _LABELS[lang]
    P = PALETTE
    # Coerce mixed / missing field types once (year as str, sources None, ...)
    # so sorting and joining below cannot abort the whole export.
    data = _sanitize(data)
    works = data.get("works") or []
    total = data.get("count") or len(works)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # search provenance (topic / generated keywords / filter) surfaced in the banner —
    # the user's original query and the skill's derived keywords must be reproducible
    # from the report itself, not just the evidence log.
    meta = data.get("meta") or {}
    _topic = meta.get("topic") or ""
    _kw = meta.get("keywords")
    if isinstance(_kw, str):
        _kw_str = _kw  # 兼容字符串直传（standalone 调用方）
    elif _kw:
        _kw_str = ", ".join(str(x) for x in _kw)
    else:
        _kw_str = ""
    _filters = []
    if meta.get("review_type") and meta.get("review_type") != "all":
        _filters.append("type=" + str(meta["review_type"]))
    if meta.get("year_from") or meta.get("year_to"):
        _filters.append("%s–%s" % (meta.get("year_from") or "?", meta.get("year_to") or "?"))
    _filter_str = " · ".join(_filters) if _filters else ""
    search_chips = []
    if _topic:
        search_chips.append(f'<span class="chip">{esc(L["search.topic"])}: <b>{esc(_topic)}</b></span>')
    if _kw_str:
        search_chips.append(f'<span class="chip">{esc(L["search.keywords"])}: <b>{esc(_kw_str)}</b></span>')
    if _filter_str:
        search_chips.append(f'<span class="chip">{esc(L["search.filter"])}: <b>{esc(_filter_str)}</b></span>')
    searchinfo = ('<div class="searchinfo">' + "".join(search_chips) + "</div>") if search_chips else ""

    years = sorted({w.get("year") for w in works if w.get("year")})
    year_span = f"{years[0]}–{years[-1]}" if years else "—"
    top_cited = max((w.get("cited_by_count") or 0) for w in works) if works else 0
    n_safety = sum(1 for w in works if w.get("is_safety"))

    # KPI
    kpis = [
        (L["kpi.total"], str(total), ""),
        (L["kpi.safety"], str(n_safety), esc(P["warn_bd"]) and ""),
        (L["kpi.year"], esc(year_span), ""),
        (L["kpi.topcited"], str(top_cited), ""),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="kpi-label">{esc(lbl)}</div>'
        f'<div class="kpi-val">{esc(val)}</div><div class="kpi-sub">{esc(sub)}</div></div>'
        for lbl, val, sub in kpis
    )

    # distributions
    src_c = Counter(w.get("source") for w in works)
    type_c = Counter(w.get("type") for w in works)
    year_c = Counter(w.get("year") for w in works)
    max_src = max(src_c.values()) if src_c else 1
    max_type = max(type_c.values()) if type_c else 1
    max_year = max(year_c.values()) if year_c else 1

    def dist_rows(counter, maxv):
        return "".join(
            f'<tr><td>{esc(k)}</td><td>{bar(v, maxv, P["blue"])}</td>'
            f'<td class="num">{v}</td></tr>'
            for k, v in counter.most_common()
        )
    src_rows = dist_rows(src_c, max_src)
    type_rows = dist_rows(type_c, max_type)
    year_rows = dist_rows(year_c, max_year)

    # works table
    wrows = ""
    for w in works:
        safe = w.get("is_safety")
        tr_cls = ' class="safety"' if safe else ""
        url = _html_link(w.get("url"))
        link = f'<a href="{esc(url)}" target="_blank" rel="noopener">↗</a>' if url else "—"
        oa_url = _html_link(w.get("open_access_url"))
        oa_link = f'<a href="{esc(oa_url)}" target="_blank" rel="noopener">OA</a>' if oa_url else "—"
        wrows += (f'<tr{tr_cls}><td>{esc(w.get("source"))}</td><td>{esc(w.get("id"))}</td>'
                  f'<td>{esc(w.get("title"))}</td><td>{esc(w.get("authors"))}</td>'
                  f'<td class="num">{esc(w.get("year"))}</td><td>{esc(w.get("publication"))}</td>'
                  f'<td>{esc(w.get("type"))}</td><td>{esc(w.get("study_type"))}</td>'
                  f'<td class="num">{esc(w.get("cited_by_count"))}</td><td>{link}</td>'
                  f'<td>{oa_link}</td></tr>')

    # safety subset
    srows = ""
    for w in works:
        if not w.get("is_safety"):
            continue
        url = _html_link(w.get("url"))
        link = f'<a href="{esc(url)}" target="_blank" rel="noopener">↗</a>' if url else "—"
        abs_snip = (w.get("abstract_snippet") or "")[:220]
        srows += (f'<tr><td>{esc(w.get("source"))}</td><td>{esc(w.get("title"))}</td>'
                  f'<td class="num">{esc(w.get("year"))}</td><td>{esc(w.get("publication"))}</td>'
                  f'<td>{esc(abs_snip)}{"…" if len(w.get("abstract_snippet") or "") > 220 else ""}</td>'
                  f'<td>{link}</td></tr>')
    if not srows:
        srows = f'<tr><td colspan="6" class="empty">—</td></tr>'

    # PRISMA funnel (P0-B) — machine rule-based screen summary
    prisma = data.get("prisma")
    prisma_html = ""
    if prisma and prisma.get("stages"):
        svg = prisma_funnel_svg(prisma, P)
        rows = "".join(
            f'<tr><td>{esc(s.get("label", s.get("stage")))}</td>'
            f'<td class="num">{s.get("count")}</td></tr>'
            for s in prisma["stages"])
        reasons = prisma["stages"][2].get("reasons") if len(prisma["stages"]) > 2 else {}
        reason_txt = (" · ".join("%s=%d" % (k, v) for k, v in reasons.items())) if reasons else ""
        prisma_html = (
            f'<h2>PRISMA 筛选漏斗 / Screening funnel</h2>'
            f'<div class="prisma">{svg}'
            f'<table><thead><tr><th>Stage / 阶段</th><th class="num">n</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>'
            + (f'<div class="prisma-note">排除原因 / Excluded: {esc(reason_txt)}</div>' if reason_txt else "")
            + f'<div class="prisma-note">⚠️ {esc(prisma.get("note", ""))}</div>'
            f'</div>')

    # Evidence & verification (P0: provenance + citation verification, ct-base §17.1)
    evidence = data.get("evidence_log") or {}
    verification = data.get("verification") or {}
    evidence_html = ""
    if evidence or verification:
        blocks = []
        if verification:
            skip = (" · " + esc(L["ev.preview"])) if verification.get("skipped_preview") else ""
            vsum = (f'<div class="ev-verify"><b>{esc(L["ev.verify"])}:</b> '
                    f'{esc(L["ev.verified"])}={verification.get("verified", 0)} · '
                    f'{esc(L["ev.bot_blocked"])}={verification.get("bot_blocked", 0)} · '
                    f'{esc(L["ev.mismatch"])}={verification.get("mismatch", 0)} · '
                    f'{esc(L["ev.unresolved"])}={verification.get("unresolved", 0)} · '
                    f'{esc(L["ev.no_id"])}={verification.get("no_identifier", 0)} · '
                    f'{esc(L["ev.suspicious"])}={verification.get("suspicious", 0)}'
                    f'{esc(skip)}</div>')
            if verification.get("bot_blocked"):
                vsum += (f'<div class="ev-verify-note">{esc(L["ev.bot_blocked"])}'
                         f'={verification.get("bot_blocked", 0)}: '
                         f'{esc(L["ev.bot_blocked.note"])}</div>')
            if verification.get("mismatch"):
                vsum += (f'<div class="ev-verify-note">{esc(L["ev.mismatch"])}'
                         f'={verification.get("mismatch", 0)}: '
                         f'{esc(L["ev.mismatch.note"])}</div>')
            blocks.append(vsum)
        # run-time config audit: warn (with signup link) when the OpenAlex key is absent.
        # The HTML report is the primary deliverable since v0.6.8 (lit_report.md dropped),
        # so the key notice must live here too — otherwise it only exists in console output.
        _cfg = (evidence.get("config") or {}) if isinstance(evidence, dict) else {}
        if _cfg.get("openalex_key") == "missing":
            _u = esc(_cfg.get("openalex_key_url") or
                     "https://docs.openalex.org/about-openalex/api-key")
            blocks.append(
                f'<div class="ev-verify-note">⚠️ {esc(L["cfg.warn"])} '
                f'<a href="{_u}" target="_blank" rel="noopener">{_u}</a></div>')
        srcs = (evidence.get("sources") or []) if isinstance(evidence, dict) else []
        if srcs:
            rows = "".join(
                f'<tr><td>{esc(s.get("source"))}</td><td>{esc((s.get("query") or "")[:120])}</td>'
                f'<td>{esc(s.get("review_type") or "all")}</td>'
                f'<td>{esc(("%s–%s" % (s.get("year_from") or "", s.get("year_to") or "")) if (s.get("year_from") or s.get("year_to")) else "—")}</td>'
                f'<td>{esc("Y" if s.get("safety") else "—")}</td>'
                f'<td class="num">{esc(s.get("count", 0))}</td>'
                f'<td>{esc((s.get("retrieved_at") or "")[:19])}</td>'
                f'<td>{esc(s.get("status", ""))}</td></tr>'
                for s in srcs)
            blocks.append(
                f'<table><thead><tr><th>{esc(L["ev.src"])}</th><th>{esc(L["ev.query"])}</th>'
                f'<th>{esc(L["ev.type"])}</th><th>{esc(L["ev.year"])}</th>'
                f'<th>{esc(L["ev.safety"])}</th><th class="num">{esc(L["ev.count"])}</th>'
                f'<th>{esc(L["ev.retrieved"])}</th><th>{esc(L["ev.status"])}</th></tr></thead>'
                f'<tbody>{rows}</tbody></table>')
        if not blocks:
            blocks.append('<div class="ev-verify">—</div>')
        ev_note = ('<div class="prisma-note">Provenance audit trail (ct-base §17.1): '
                   'every evidence item is traceable to its source query and retrieval time. '
                   'Verification status is advisory, not a substitute for human review. / '
                   '证据溯源审计（ct-base §17.1）：每条证据可回溯至来源检索式与检索时间；'
                   '验证状态仅供参考，不替代人工核查。</div>')
        evidence_html = (
            f'<h2>{esc(L["evidence"])}</h2>'
            f'<div class="prisma">{"".join(blocks)}{ev_note}</div>')

    css = f"""
    :root {{ --navy:{P['navy']}; --blue:{P['blue']}; --light:{P['light']};
            --banner:{P['banner']}; --grid:{P['grid']}; --greytx:{P['greytx']};
            --warn:{P['warn_bg']}; --warnbd:{P['warn_bd']}; }}
    * {{ box-sizing:border-box; }}
    body {{ font-family:'Microsoft YaHei','PingFang SC',sans-serif; margin:0;
            color:#1a1a1a; background:#f5f7f8; }}
    .banner {{ background:linear-gradient(135deg,var(--navy),var(--banner)); color:#fff;
               padding:22px 28px; }}
    .banner h1 {{ margin:0; font-size:22px; }}
    .banner .meta {{ margin-top:6px; font-size:12px; opacity:.85; }}
    .banner .searchinfo {{ margin-top:8px; font-size:12px; display:flex; flex-wrap:wrap; gap:6px; }}
    .banner .searchinfo .chip {{ background:rgba(255,255,255,.15); border-radius:10px;
      padding:2px 10px; opacity:.95; }}
    .banner .searchinfo .chip b {{ font-weight:600; }}
    .wrap {{ max-width:1180px; margin:0 auto; padding:20px 24px 60px; }}
    h2 {{ color:var(--navy); border-left:5px solid var(--blue); padding-left:10px;
          margin-top:30px; font-size:17px; }}
    .kpis {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-top:18px; }}
    .kpi {{ background:#fff; border:1px solid var(--grid); border-radius:10px; padding:16px;
            box-shadow:0 1px 3px rgba(0,0,0,.06); }}
    .kpi-label {{ font-size:12px; color:var(--greytx); }}
    .kpi-val {{ font-size:24px; font-weight:700; color:var(--navy); margin-top:4px; }}
    table {{ width:100%; border-collapse:collapse; background:#fff; margin-top:12px;
             border:1px solid var(--grid); border-radius:8px; overflow:hidden; }}
    th,td {{ padding:9px 11px; text-align:left; border-bottom:1px solid var(--grid);
             font-size:13px; vertical-align:top; }}
    th {{ background:var(--light); color:var(--navy); font-weight:600; position:sticky; top:0; }}
    tr:nth-child(even) td {{ background:#fafcfb; }}
    tr.safety td {{ background:var(--warn); }}
    tr.safety td:first-child {{ border-left:4px solid var(--warnbd); }}
    .num {{ text-align:right; font-variant-numeric:tabular-nums; }}
    .empty {{ color:var(--greytx); text-align:center; }}
    .barwrap {{ position:relative; min-width:150px; }}
    .bar {{ height:14px; border-radius:4px; display:inline-block; vertical-align:middle; }}
    .barval {{ margin-left:8px; font-size:12px; color:var(--greytx); }}
    .dist {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:18px; }}
    .prisma {{ background:#fff; border:1px solid var(--grid); border-radius:10px;
               padding:16px; margin-top:14px; }}
    .prisma svg {{ display:block; max-width:620px; margin:0 auto 10px; }}
    .prisma table {{ max-width:420px; margin:0 auto; }}
    .prisma-note {{ font-size:12px; color:var(--greytx); margin-top:8px; text-align:center; }}
    @media (max-width:880px) {{ .dist {{ grid-template-columns:1fr; }} .kpis {{ grid-template-columns:repeat(2,1fr); }} }}
    @media print {{
      @page {{ margin:12mm; }}
      * {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
      body {{ background:#fff; color:#000; }}
      .banner {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; color:#fff; }}
      .wrap {{ max-width:none; padding:0; }}
      .kpi, table, ul, h2, .dist {{ break-inside:avoid; }}
      a {{ color:#000; text-decoration:none; }}
      .bar {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
      tr.safety td {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
    }}
    """

    return f"""<!DOCTYPE html>
<html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(L['doc_title'])}</title>
<style>{css}</style></head>
<body>
<div class="banner"><h1>{esc(L['doc_title'])}</h1>
<div class="meta">{esc(L['generated'])}: {now} ｜ {total} works</div>{searchinfo}</div>
<div class="wrap">
  <div class="kpis">{kpi_html}</div>

  <h2>{esc(L['overview'])}</h2>
  <div class="dist">
    <div><table><thead><tr><th>{esc(L['by_src'])}</th><th></th><th class="num">n</th></tr></thead><tbody>{src_rows}</tbody></table></div>
    <div><table><thead><tr><th>{esc(L['by_type'])}</th><th></th><th class="num">n</th></tr></thead><tbody>{type_rows}</tbody></table></div>
    <div><table><thead><tr><th>{esc(L['by_year'])}</th><th></th><th class="num">n</th></tr></thead><tbody>{year_rows}</tbody></table></div>
  </div>

  <h2>{esc(L['works'])}</h2>
  <table><thead><tr><th>{esc(L['col.source'])}</th><th>{esc(L['col.id'])}</th><th>{esc(L['col.title'])}</th>
  <th>{esc(L['col.authors'])}</th><th class="num">{esc(L['col.year'])}</th><th>{esc(L['col.pub'])}</th>
  <th>{esc(L['col.type'])}</th><th>{esc(L['col.study'])}</th><th class="num">{esc(L['col.cited'])}</th><th>{esc(L['col.link'])}</th><th>{esc(L['col.oa'])}</th></tr></thead>
  <tbody>{wrows}</tbody></table>

  <h2>{esc(L['safety'])}</h2>
  <table><thead><tr><th>{esc(L['col.source'])}</th><th>{esc(L['col.title'])}</th><th class="num">{esc(L['col.year'])}</th>
  <th>{esc(L['col.pub'])}</th><th>{esc(L['col.abstract'])}</th><th>{esc(L['col.link'])}</th></tr></thead>
  <tbody>{srows}</tbody></table>

  {prisma_html}
  {evidence_html}
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-json", default=".merged.json",
                    help=".merged.json (hidden intermediate from ct_literature)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--lang", default="auto", choices=["auto", "zh", "en"])
    args = ap.parse_args()
    data = json.load(open(args.in_json, encoding="utf-8"))
    html_out = render(data, args.lang)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"HTML written: {args.out} ({len(html_out)} bytes, lang={args.lang})")


if __name__ == "__main__":
    main()
