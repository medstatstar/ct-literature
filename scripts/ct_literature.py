#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ct_literature.py — orchestration entry point.

One-shot pipeline: fetch OpenAlex (required) + optional Europe PMC / Semantic Scholar
-> normalize (merge + dedupe) -> Markdown report. Reads only public literature;
zero confidential data or information input.

Usage:
  python scripts/ct_literature.py --topic "osimertinib" --review-type systematic-review \
      --year-from 2018 --safety --run --out-dir ./out
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adapters import fetch_openalex
from adapters import fetch_europepmc
from adapters import fetch_semantic_scholar
from adapters import fetch_preprints
from adapters import fetch_arxiv
import normalize
import report as report_mod
import export_xlsx
import export_html
import score_relevance
import screen_prisma
import format_citations
import obsidian_exporter
import zotero_exporter
from adapters import verify_citations  # P0: citation identifier verification (anti-hallucination)
import evidence_log      # P0: provenance audit trail (ct-base §17.1)
from adapters import fetch_prospero    # P1: PROSPERO systematic-review registry (key-gated, opt-in)
from adapters import http_utils  # shared GET+retry; load_openalex_key() auto-loads key from env/.env

# P0 new capabilities default flags
DEFAULT_CITATION_STYLE = "apa"
DEFAULT_EXPORT_BIB = True
DEFAULT_PRISMA = True
DEFAULT_RANK = "cited"  # keep legacy cited-by ordering unless --rank relevance


def run(topic, review_type="all", year_from=None, year_to=None, safety=False,
        max_results=30, with_europepmc=True, with_semantic_scholar=False,
        with_biorxiv=False, with_medrxiv=False, with_arxiv=False,
        with_prospero=False, prospero_token=None, prospero_header="PROSPERO-ACCESS-TOKEN",
        verify_citations_flag=True,
        out_dir="./out", make_xlsx=True, make_html=True, openalex_key=None,
        citation_style=DEFAULT_CITATION_STYLE, export_bib=DEFAULT_EXPORT_BIB,
        prisma=DEFAULT_PRISMA, rank=DEFAULT_RANK, keywords=None,
        obsidian=False, zotero=False):
    os.makedirs(out_dir, exist_ok=True)
    http_utils.notify_openalex_key_if_missing(openalex_key)
    oa_json = os.path.join(out_dir, "openalex.json")
    epmc_json = os.path.join(out_dir, "europepmc.json")
    s2_json = os.path.join(out_dir, "semantic_scholar.json")
    biorxiv_json = os.path.join(out_dir, "biorxiv.json")
    medrxiv_json = os.path.join(out_dir, "medrxiv.json")
    arxiv_json = os.path.join(out_dir, "arxiv.json")
    prospero_json = os.path.join(out_dir, "prospero.json")
    merged_json = os.path.join(out_dir, "merged.json")
    md_out = os.path.join(out_dir, "lit_report.md")

    payloads = []
    oa = fetch_openalex.fetch(topic, review_type, year_from, year_to, safety,
                              max_results, run=True, out=oa_json, api_key=openalex_key)
    payloads.append(oa)
    if with_europepmc:
        ep = fetch_europepmc.fetch(topic, review_type, year_from, year_to, safety,
                                   max_results, run=True, out=epmc_json)
        payloads.append(ep)
    if with_semantic_scholar:
        s2 = fetch_semantic_scholar.fetch(topic, review_type, year_from, year_to, safety,
                                          max_results, run=True, out=s2_json)
        payloads.append(s2)
    if with_biorxiv:
        br = fetch_preprints.fetch(topic, review_type, year_from, year_to, safety,
                                   max_results, run=True, out=biorxiv_json, server="biorxiv")
        payloads.append(br)
    if with_medrxiv:
        mr = fetch_preprints.fetch(topic, review_type, year_from, year_to, safety,
                                   max_results, run=True, out=medrxiv_json, server="medrxiv")
        payloads.append(mr)
    if with_arxiv:
        ax = fetch_arxiv.fetch(topic, review_type, year_from, year_to, safety,
                               max_results, run=True, out=arxiv_json)
        payloads.append(ax)
    if with_prospero:
        pr = fetch_prospero.fetch(topic, review_type, year_from, year_to, safety,
                                  max_results, run=True, out=prospero_json,
                                  token=prospero_token, header_name=prospero_header)
        payloads.append(pr)

    works = normalize.merge(payloads)

    # ---- P0-C: relevance scoring (annotates merged works, incremental) ----
    works = score_relevance.score_works(works, topic=topic, keywords=keywords)

    # ---- P0-B: deterministic PRISMA title/abstract screen (no LLM) ----
    prisma_block = None
    if prisma:
        sp = screen_prisma.screen(works, topic=topic, review_type=review_type,
                                  safety=safety)
        works = sp["works"]
        prisma_block = sp["prisma"]

    # ---- ranking ----
    if rank == "relevance":
        try:
            works = sorted(works, key=lambda w: -(float(w.get("relevance_score") or 0)))
        except Exception:
            pass

    # ---- P0: citation verification (anti-hallucination, ct-base §17.1) ----
    vsum = None
    if verify_citations_flag:
        works, vsum = verify_citations.verify_works(works, run=True)
        print("[OK] citation verification: %s" % json.dumps(vsum, ensure_ascii=False))

    # ---- build meta (shared by report / xlsx / html / evidence log) ----
    meta = {"topic": topic, "review_type": review_type,
            "year_from": year_from, "year_to": year_to, "safety": safety,
            "citation_style": citation_style if export_bib else None,
            "rank": rank, "keywords": keywords,
            "prisma": prisma_block,
            "verification": vsum,
            "with_prospero": with_prospero}

    # ---- P0: provenance audit trail (evidence log) ----
    evidence = evidence_log.build_log(payloads, topic, meta, vsum)
    ev_res = evidence_log.write_log(evidence, out_dir)
    meta["evidence_log"] = evidence
    print("[OK] evidence_log -> %s / %s" % (ev_res["json"], ev_res["md"]))

    out_data = {"count": len(works), "works": works}
    if prisma_block:
        out_data["prisma"] = prisma_block
    out_data["evidence_log"] = evidence
    out_data["verification"] = vsum
    with open(merged_json, "w", encoding="utf-8") as f:
        json.dump(out_data, f, ensure_ascii=False, indent=2)
    print("[OK] merged %d unique works -> %s" % (len(works), merged_json))

    md = report_mod.render(works, meta)
    with open(md_out, "w", encoding="utf-8") as f:
        f.write(md)
    print("[OK] report ->", md_out)

    # ---- P0-A: citation formatting + BibTeX/RIS export ----
    if export_bib:
        try:
            fc = format_citations.export_citations(
                {"count": len(works), "works": works}, style=citation_style,
                out_dir=out_dir, lang="auto")
            print("[OK] citations(%s) -> %s / %s" % (
                citation_style, fc["bib_path"], fc["ris_path"]))
        except Exception as _ce:
            print("[WARN] citation export failed: %s" % _ce)

    if make_xlsx:
        xlsx_out = os.path.join(out_dir, "lit_report.xlsx")
        try:
            export_xlsx.export_workbook(
                {"count": len(works), "works": works, "meta": meta},
                xlsx_out, lang="auto")
            print("[OK] xlsx  ->", xlsx_out)
        except Exception as _xe:
            print("[WARN] xlsx export failed: %s" % _xe)
    if make_html:
        html_out = os.path.join(out_dir, "lit_report.html")
        try:
            html_text = export_html.render(out_data, "auto")
            with open(html_out, "w", encoding="utf-8") as f:
                f.write(html_text)
            print("[OK] html  ->", html_out)
        except Exception as _he:
            print("[WARN] html export failed: %s" % _he)

    # ---- F: Obsidian / Zotero 文献管理软件集成 ----
    if obsidian:
        try:
            ob = obsidian_exporter.export_obsidian(
                {"count": len(works), "works": works}, out_dir=out_dir, lang="zh")
            print("[OK] obsidian notes=%d -> %s" % (ob["count"], ob["folder"]))
            print("     moc -> %s" % ob["moc"])
        except Exception as _oe:
            print("[WARN] obsidian export failed: %s" % _oe)
    if zotero:
        try:
            zo = zotero_exporter.export_zotero(
                {"count": len(works), "works": works}, out_dir=out_dir)
            print("[OK] zotero csv/ris -> %s / %s" % (zo["csv"], zo["ris"]))
        except Exception as _ze:
            print("[WARN] zotero export failed: %s" % _ze)
    return md_out


def main():
    ap = argparse.ArgumentParser(description="ct-literature pipeline (public literature search).")
    ap.add_argument("--topic", required=True, help="free-text topic / drug / disease")
    ap.add_argument("--review-type", default="all",
                    choices=["all", "systematic-review", "scoping-review",
                             "meta-analysis", "rct", "case-report"])
    ap.add_argument("--year-from", type=int, help="lower bound publication year")
    ap.add_argument("--year-to", type=int, help="upper bound publication year")
    ap.add_argument("--safety", action="store_true",
                    help="safety / CSM bias (AE, toxicity, case report, PV)")
    ap.add_argument("--max", type=int, default=30, help="max works per source")
    ap.add_argument("--with-europepmc", action=argparse.BooleanOptionalAction, default=True,
                    help="search Europe PMC (MEDLINE/MeSH, biomedical precision); default ON; "
                         "use --no-with-europepmc to disable")
    ap.add_argument("--with-semantic-scholar", action="store_true",
                    help="(low-priority supplementary source) search via Semantic Scholar "
                         "(citation-ranked); its API key requires a manual form review and is "
                         "not auto-issued, so it auto-skips when absent and never affects the "
                         "OpenAlex / Europe PMC primary output")
    ap.add_argument("--with-biorxiv", action="store_true",
                    help="include bioRxiv preprints (biomedical preprints, via Europe PMC PPR index)")
    ap.add_argument("--with-medrxiv", action="store_true",
                    help="include medRxiv preprints (medical/clinical preprints, via Europe PMC PPR index)")
    ap.add_argument("--with-arxiv", action="store_true",
                    help="include arXiv (physics/CS/ML methodology breadth; opt-in supplementary)")
    # ---- P1: PROSPERO systematic-review registry (opt-in, key-gated, UNVERIFIED) ----
    ap.add_argument("--with-prospero", action="store_true",
                    help="(P1, supplementary) include PROSPERO systematic-review registry "
                         "hits (duplication-avoidance / protocol discovery). Requires an API "
                         "token; currently key-gated + UNVERIFIED (the public REST API auth "
                         "header is undocumented) — degrades to a no-op skip when no token.")
    ap.add_argument("--prospero-token", default=os.environ.get("PROSPERO_API_TOKEN"),
                    help="PROSPERO API token (env PROSPERO_API_TOKEN). Required for --with-prospero.")
    ap.add_argument("--prospero-header", default="PROSPERO-ACCESS-TOKEN",
                    help="header name carrying the PROSPERO token (default: "
                         "PROSPERO-ACCESS-TOKEN; override if the real header differs)")
    ap.add_argument("--run", action="store_true", help="execute network requests")
    ap.add_argument("--no-xlsx", action="store_true",
                    help="skip Excel (.xlsx) export (default: auto-generate)")
    ap.add_argument("--no-html", action="store_true",
                    help="skip standalone HTML report (default: auto-generate)")
    ap.add_argument("--out-dir", default="./out")
    ap.add_argument("--openalex-key", default=http_utils.load_openalex_key(),
                    help="OpenAlex API key (Bearer). Auto-loaded from env OPENALEX_API_KEY "
                         "or skill .env. Free key lifts rate limit 100 -> 100k credits/day.")
    # ---- P0 new flags ----
    ap.add_argument("--citation-style", default=DEFAULT_CITATION_STYLE,
                    choices=format_citations.STYLES,
                    help="citation style for references export (default: apa)")
    ap.add_argument("--export-bib", action=argparse.BooleanOptionalAction,
                    default=DEFAULT_EXPORT_BIB,
                    help="export references.bib / references.ris (default: on; "
                         "use --no-export-bib to disable)")
    ap.add_argument("--prisma", action=argparse.BooleanOptionalAction,
                    default=DEFAULT_PRISMA,
                    help="run deterministic PRISMA title/abstract screen + funnel "
                         "(default: on; use --no-prisma to disable)")
    ap.add_argument("--rank", default=DEFAULT_RANK, choices=["cited", "relevance"],
                    help="order works by cited_by_count (default) or relevance_score")
    ap.add_argument("--keywords", default=None,
                    help="comma-separated extra keywords for relevance scoring")
    # ---- P0: citation verification toggle ----
    ap.add_argument("--no-verify-citations", action="store_true",
                    help="disable P0 citation-identifier verification (anti-hallucination); "
                         "default ON (verifies doi/pmid/OpenAlex id against the live source)")
    # ---- F: literature-manager integration ----
    ap.add_argument("--obsidian", action="store_true",
                    help="export Obsidian notes (per-paper .md + MOC index, "
                         "internal [[links]]); writes <out-dir>/obsidian/")
    ap.add_argument("--zotero", action="store_true",
                    help="export Zotero-importable zotero.csv + zotero.ris into <out-dir>/")
    args = ap.parse_args()

    if not args.run:
        extra = []
        if args.with_europepmc:
            extra.append("EuropePMC")
        if args.with_semantic_scholar:
            extra.append("SemanticScholar")
        if args.with_biorxiv:
            extra.append("bioRxiv")
        if args.with_medrxiv:
            extra.append("medRxiv")
        if args.with_arxiv:
            extra.append("arXiv")
        if args.with_prospero:
            extra.append("PROSPERO(token-gated)")
        srcs = "OpenAlex" + (" + " + ", ".join(extra) if extra else "")
        print("[PREVIEW] would run literature pipeline: topic=%r review_type=%r safety=%s "
              "sources=[%s] (use --run)" % (args.topic, args.review_type, args.safety, srcs))
        return
    run(args.topic, args.review_type, args.year_from, args.year_to, args.safety,
        args.max, args.with_europepmc, args.with_semantic_scholar,
        args.with_biorxiv, args.with_medrxiv, args.with_arxiv,
        with_prospero=args.with_prospero, prospero_token=args.prospero_token,
        prospero_header=args.prospero_header,
        verify_citations_flag=not args.no_verify_citations,
        out_dir=args.out_dir,
        make_xlsx=not args.no_xlsx, make_html=not args.no_html,
        openalex_key=args.openalex_key, citation_style=args.citation_style,
        export_bib=args.export_bib, prisma=args.prisma, rank=args.rank,
        keywords=args.keywords, obsidian=args.obsidian, zotero=args.zotero)


if __name__ == "__main__":
    main()
