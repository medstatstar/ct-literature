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
import fetch_openalex
import fetch_europepmc
import fetch_semantic_scholar
import normalize
import report as report_mod
import export_xlsx
import export_html
import http_utils  # shared GET+retry; load_openalex_key() auto-loads key from env/.env


def run(topic, review_type="all", year_from=None, year_to=None, safety=False,
        max_results=30, with_europepmc=False, with_semantic_scholar=False,
        out_dir="./out", make_xlsx=True, make_html=True, openalex_key=None):
    os.makedirs(out_dir, exist_ok=True)
    http_utils.notify_openalex_key_if_missing(openalex_key)
    oa_json = os.path.join(out_dir, "openalex.json")
    epmc_json = os.path.join(out_dir, "europepmc.json")
    s2_json = os.path.join(out_dir, "semantic_scholar.json")
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

    works = normalize.merge(payloads)
    with open(merged_json, "w", encoding="utf-8") as f:
        json.dump({"count": len(works), "works": works}, f, ensure_ascii=False, indent=2)
    print("[OK] merged %d unique works -> %s" % (len(works), merged_json))

    meta = {"topic": topic, "review_type": review_type,
            "year_from": year_from, "year_to": year_to, "safety": safety}
    md = report_mod.render(works, meta)
    with open(md_out, "w", encoding="utf-8") as f:
        f.write(md)
    print("[OK] report ->", md_out)

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
            html_text = export_html.render({"count": len(works), "works": works}, "auto")
            with open(html_out, "w", encoding="utf-8") as f:
                f.write(html_text)
            print("[OK] html  ->", html_out)
        except Exception as _he:
            print("[WARN] html export failed: %s" % _he)
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
    ap.add_argument("--with-europepmc", action="store_true",
                    help="also search Europe PMC (MEDLINE/MeSH, biomedical precision)")
    ap.add_argument("--with-semantic-scholar", action="store_true",
                    help="(low-priority supplementary source) search via Semantic Scholar "
                         "(citation-ranked); its API key requires a manual form review and is "
                         "not auto-issued, so it auto-skips when absent and never affects the "
                         "OpenAlex / Europe PMC primary output")
    ap.add_argument("--run", action="store_true", help="execute network requests")
    ap.add_argument("--no-xlsx", action="store_true",
                    help="skip Excel (.xlsx) export (default: auto-generate)")
    ap.add_argument("--no-html", action="store_true",
                    help="skip standalone HTML report (default: auto-generate)")
    ap.add_argument("--out-dir", default="./out")
    ap.add_argument("--openalex-key", default=http_utils.load_openalex_key(),
                    help="OpenAlex API key (Bearer). Auto-loaded from env OPENALEX_API_KEY "
                         "or skill .env. Free key lifts rate limit 100 -> 100k credits/day.")
    args = ap.parse_args()

    if not args.run:
        extra = []
        if args.with_europepmc:
            extra.append("EuropePMC")
        if args.with_semantic_scholar:
            extra.append("SemanticScholar")
        srcs = "OpenAlex" + (" + " + ", ".join(extra) if extra else "")
        print("[PREVIEW] would run literature pipeline: topic=%r review_type=%r safety=%s "
              "sources=[%s] (use --run)" % (args.topic, args.review_type, args.safety, srcs))
        return
    run(args.topic, args.review_type, args.year_from, args.year_to, args.safety,
        args.max, args.with_europepmc, args.with_semantic_scholar, args.out_dir,
        make_xlsx=not args.no_xlsx, make_html=not args.no_html,
        openalex_key=args.openalex_key)


if __name__ == "__main__":
    main()
