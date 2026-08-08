#!/usr/bin/env python3
"""ct-literature → self-contained HTML report (no Excel needed to view).

Reads `merged.json` (OpenAlex + Europe PMC merged evidence base) and renders a
single standalone .html file (inline CSS, safety-row highlight, source/type
distributions as CSS bars) so content is fully readable in any browser / the
WorkBuddy artifact preview without the client's limited xlsx viewer.

Theme: literature academic green, reusing ct-base `excel_style` palette.

Usage:
    python export_html.py --in-json ../out_live/merged.json \
                          --out ../out_live/merged.html --lang zh
"""
import os, sys, json, html, argparse, datetime
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "ct-base", "scripts"))
import excel_style as X

PALETTE = X.PALETTES["literature"]

_LABELS = {
    "en": {
        "doc_title": "Literature Evidence Base",
        "generated": "Generated", "kpi.total": "Works", "kpi.safety": "Safety-related",
        "kpi.year": "Year Span", "kpi.topcited": "Top Cited",
        "works": "Works", "col.source": "Source", "col.id": "ID", "col.title": "Title",
        "col.authors": "Authors", "col.year": "Year", "col.pub": "Publication",
        "col.type": "Type", "col.study": "Study", "col.cited": "Cited", "col.link": "Link",
        "col.abstract": "Abstract", "overview": "Overview", "by_src": "By Source",
        "by_type": "By Type", "by_year": "By Year", "safety": "Safety / CSM Subset",
    },
    "zh": {
        "doc_title": "文献证据库",
        "generated": "生成时间", "kpi.total": "文献数", "kpi.safety": "安全性相关",
        "kpi.year": "年份跨度", "kpi.topcited": "最高被引",
        "works": "文献列表", "col.source": "来源", "col.id": "ID", "col.title": "标题",
        "col.authors": "作者", "col.year": "年份", "col.pub": "期刊",
        "col.type": "类型", "col.study": "研究类型", "col.cited": "被引", "col.link": "链接",
        "col.abstract": "摘要", "overview": "概览", "by_src": "按来源", "by_type": "按类型",
        "by_year": "按年份", "safety": "安全性 / CSM 子集",
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
        wrows += (f'<tr{tr_cls}><td>{esc(w.get("source"))}</td><td>{esc(w.get("id"))}</td>'
                  f'<td>{esc(w.get("title"))}</td><td>{esc(w.get("authors"))}</td>'
                  f'<td class="num">{esc(w.get("year"))}</td><td>{esc(w.get("publication"))}</td>'
                  f'<td>{esc(w.get("type"))}</td><td>{esc(w.get("study_type"))}</td>'
                  f'<td class="num">{esc(w.get("cited_by_count"))}</td><td>{link}</td></tr>')

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
<div class="meta">{esc(L['generated'])}: {now} ｜ {total} works</div></div>
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
  <th>{esc(L['col.type'])}</th><th>{esc(L['col.study'])}</th><th class="num">{esc(L['col.cited'])}</th><th>{esc(L['col.link'])}</th></tr></thead>
  <tbody>{wrows}</tbody></table>

  <h2>{esc(L['safety'])}</h2>
  <table><thead><tr><th>{esc(L['col.source'])}</th><th>{esc(L['col.title'])}</th><th class="num">{esc(L['col.year'])}</th>
  <th>{esc(L['col.pub'])}</th><th>{esc(L['col.abstract'])}</th><th>{esc(L['col.link'])}</th></tr></thead>
  <tbody>{srows}</tbody></table>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-json", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lang", default="zh", choices=["zh", "en"])
    args = ap.parse_args()
    data = json.load(open(args.in_json, encoding="utf-8"))
    html_out = render(data, args.lang)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"HTML written: {args.out} ({len(html_out)} bytes, lang={args.lang})")


if __name__ == "__main__":
    main()
