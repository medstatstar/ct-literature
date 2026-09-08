#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fetch_europepmc.py — Europe PMC fetcher (biomedical-precision enhancement source).

Reads Europe PMC (https://www.ebi.ac.uk/europepmc/webservices/rest/search) — the
REST front-end to MEDLINE + PubMed Central + Agricola + preprint servers, with
MeSH indexing for biomedical precision. No key required for low-volume use.
Zero confidential data or information input; reads only public literature.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adapters import http_utils  # shared GET+retry (exponential backoff, 429 Retry-After)

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

# Cochrane Database of Systematic Reviews — restrict to the journal itself.
# Verified 2026-08-26: `JOURNAL:"The Cochrane database of systematic reviews"`
# returns accurate counts; the looser bare-phrase match overcounts (it also
# catches papers that merely *cite* Cochrane), and `PUBLICATION_TYPE:"Cochrane
# Reviews"` returns 0 (the pubType value is "Systematic Review", not "Cochrane
# Reviews"). This is the SAME filter string meta-analysis.literature_probe uses,
# so cross-skill hit counts stay consistent.
COCHRANE_JOURNAL_FILTER = '(JOURNAL:"The Cochrane database of systematic reviews")'
COCHRANE_JOURNAL_MARK = "cochrane database of systematic reviews"

SAFETY_LEXICON = [
    "adverse event", "adverse reaction", "side effect", "safety", "toxicity",
    "toxic", "case report", "pharmacovigilance", "drug-induced", "drug reaction",
]


def _strip_html(s):
    if not s:
        return s
    import re as _re
    return _re.sub(r"<[^>]+>", "", s)


def _study_type_from(pub_types, title, abstract):
    blob = ((title or "") + " " + (abstract or "")).lower()
    pts = " ".join(pub_types).lower()
    if "systematic review" in blob or "meta-analysis" in blob:
        return "systematic-review"
    if "case report" in blob or "case series" in blob:
        return "case-report"
    if "randomized controlled trial" in blob or ("randomized" in blob and "trial" in blob):
        return "rct"
    if "review" in pts:
        return "review"
    return "article"


def _flag_safety(title, abstract):
    blob = ((title or "") + " " + (abstract or "")).lower()
    return any(k in blob for k in SAFETY_LEXICON)


def _extract(rec):
    ji = rec.get("journalInfo") or {}
    journal = (ji.get("journal") or {}).get("title")
    journal_iso = (ji.get("journal") or {}).get("isoabbreviation")
    authors = []
    affiliations = []
    al = rec.get("authorList") or {}
    for a in (al.get("author") or [])[:6]:
        nm = a.get("fullName")
        if nm:
            authors.append(nm)
        # Collect affiliations
        aff_list = (a.get("authorAffiliationDetailsList") or {}).get("authorAffiliation") or []
        for aff in aff_list:
            if aff.get("affiliation") and aff["affiliation"] not in affiliations:
                affiliations.append(aff["affiliation"])
    n_auth = len(al.get("author") or [])
    if n_auth > 6:
        authors.append("et al.")
    mesh = []
    mh = rec.get("meshHeadingList") or {}
    for h in (mh.get("meshHeading") or [])[:8]:
        d = h.get("descriptorName")
        if d:
            mesh.append(d)
    title = _strip_html(rec.get("title") or "")
    abstract = _strip_html(rec.get("abstractText") or "")
    # Raw publisher-type tags (e.g. ["Review"], ["Systematic Review"], ["Meta-Analysis"],
    # ["Journal Article"]). Saved verbatim under `pub_types` so downstream review-guard
    # (meta-analysis B1 hard signal) can trust the API self-label instead of guessing
    # from title/abstract. This is the cross-skill passthrough fix (ct-literature
    # normalize.merge was previously dropping it).
    pub_types = (rec.get("pubTypeList") or {}).get("pubType", []) or []
    cited = rec.get("citedByCount")
    # Full text URLs
    ftl = rec.get("fullTextUrlList") or {}
    ft_urls = ftl.get("fullTextUrl", [])
    fulltext_url = ft_urls[0].get("url") if ft_urls else None
    return {
        "source": "EuropePMC",
        "id": rec.get("id") or rec.get("pmid"),
        "pmid": rec.get("pmid"),
        "pmcid": rec.get("pmcid"),
        "doi": rec.get("doi"),
        "title": title,
        "authors": authors,
        "affiliations": affiliations[:5] or None,
        "year": int(rec["pubYear"]) if rec.get("pubYear") and str(rec.get("pubYear")).isdigit() else None,
        # BUGFIX 2026-09-08: `printPublicationDate` / `dateOfPublication` live under the
        # nested `journalInfo` object, NOT at the top level of a result record — so both
        # `rec.get(...)` lookups always returned None and every Europe PMC record shipped
        # with an empty publication_date. `firstPublicationDate` is the real top-level
        # field (verified live: doi 10.1016/j.cellsig.2026.112850 -> "2026-08-26"); the
        # journalInfo values are kept as fallbacks for records without it.
        "publication_date": (rec.get("firstPublicationDate")
                             or (rec.get("journalInfo") or {}).get("printPublicationDate")
                             or (rec.get("journalInfo") or {}).get("dateOfPublication")),
        "publication": journal,
        "journal_iso": journal_iso,
        "type": "article",
        "study_type": _study_type_from(rec.get("pubTypeList", {}).get("pubType", []) or [], title, abstract),
        "cited_by_count": int(cited) if isinstance(cited, int) else 0,
        "url": fulltext_url or rec.get("doi") or None,
        "open_access_url": fulltext_url,
        "abstract_snippet": abstract or "",
        "mesh": mesh or None,
        "is_safety": _flag_safety(title, abstract),
        "is_cochrane": bool(journal and COCHRANE_JOURNAL_MARK in journal.lower()),
        "pub_types": pub_types,
        "volume": ji.get("volume"),
        "issue": ji.get("issue"),
        "page": rec.get("pageInfo"),
    }


def fetch(topic, review_type="all", year_from=None, year_to=None,
          safety=False, max_results=30, run=False, out=None, cochrane=False,
          include_reviews=True):
    """Fetch from Europe PMC. When include_reviews=False, append a
    NOT (PUBLICATION_TYPE:"Review" OR "Systematic Review" OR "Meta-Analysis")
    clause to keep review-type publications out of the result set at the
    source — saves retrieval quota and spares the user a post-hoc cull."""
    if not run:
        print("[PREVIEW] would query Europe PMC for topic=%r review_type=%r include_reviews=%r "
              "(use --run to execute)" % (topic, review_type, include_reviews))
        return None

    q = topic
    if review_type == "systematic-review":
        q += " AND (systematic review OR meta-analysis)"
    elif review_type == "meta-analysis":
        q += " AND meta-analysis"
    elif review_type == "scoping-review":
        q += " AND scoping review"
    elif review_type == "rct":
        q += " AND randomized controlled trial"
    elif review_type == "case-report":
        q += " AND case report"
    if safety:
        q += " AND (adverse event OR safety OR toxicity OR case report)"

    if year_from or year_to:
        lo = str(year_from) if year_from else "1900"
        hi = str(year_to) if year_to else "3000"
        q += " AND (PUB_YEAR:[%s TO %s])" % (lo, hi)

    if cochrane:
        q += " AND " + COCHRANE_JOURNAL_FILTER

    # Source-level exclusion of review-type publications. Field verified against
    # Europe PMC's search grammar (PUBLICATION_TYPE is an indexed field; values
    # include "Review", "Systematic Review", "Meta-Analysis", "Journal Article").
    if not include_reviews:
        q += (' AND NOT (PUBLICATION_TYPE:"Review" OR PUBLICATION_TYPE:"Systematic Review" '
              'OR PUBLICATION_TYPE:"Meta-Analysis")')

    collected = []
    seen_dois = set()  # 防欧洲 PMC 翻页返回同一记录
    total_hits = None  # Europe PMC's full matching count (independent of max_results)
    cursor = "*"  # 第一次用 *，后续用 nextCursorMark
    per = min(100, max_results)  # Europe PMC 支持最大 1000，但 100 平衡速度与稳定性
    while len(collected) < max_results:
        params = {
            "query": q,
            "format": "json",
            "resultType": "core",
            "pageSize": min(per, max_results - len(collected)),
        }
        # cursorMark 深度分页（比 page 参数更可靠，不会返回重复记录）
        if cursor and cursor != "*":
            params["cursorMark"] = cursor
        url = BASE + "?" + urllib.parse.urlencode(params)
        try:
            j = http_utils.get_json(url, headers={"User-Agent": http_utils.UA},
                                    timeout=45, max_retries=4)
        except http_utils.HttpError as e:
            print("[WARN] Europe PMC request failed: %s" % e)
            break
        if total_hits is None:
            total_hits = j.get("hitCount")
        results = (j.get("resultList") or {}).get("result", [])
        if not results:
            break
        for rec in results:
            ext = _extract(rec)
            doi = ext.get("doi", "")
            if doi and doi in seen_dois:
                continue
            if doi:
                seen_dois.add(doi)
            collected.append(ext)
        # 获取下一页的 cursorMark
        cursor = j.get("nextCursorMark")
        if not cursor:
            break  # 没有更多结果
        # 如果返回结果少于 per，说明已经是最后一页
        if len(results) < per:
            break
        time.sleep(0.3)

    payload = {
        "source": "EuropePMC",
        "query": q,
        "review_type": review_type,
        "year_from": year_from,
        "year_to": year_to,
        "safety": safety,
        "cochrane": cochrane,
        "hit_count": total_hits,
        "count": len(collected),
        "works": collected,
    }
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print("[OK] Europe PMC wrote %d works -> %s" % (len(collected), out))
    return payload


def main():
    ap = argparse.ArgumentParser(description="Fetch literature via Europe PMC (MEDLINE/MeSH, public).")
    ap.add_argument("--topic", required=True)
    ap.add_argument("--review-type", default="all",
                    choices=["all", "systematic-review", "scoping-review",
                             "meta-analysis", "rct", "case-report"])
    ap.add_argument("--year-from", type=int)
    ap.add_argument("--year-to", type=int)
    ap.add_argument("--safety", action="store_true")
    ap.add_argument("--cochrane", action="store_true",
                    help="restrict to the Cochrane Database of Systematic Reviews "
                         "(journal filter via Europe PMC)")
    ap.add_argument("--include-reviews", action=argparse.BooleanOptionalAction,
                    default=True,
                    help="include review-type publications in results (default: on; "
                         "use --no-include-reviews to exclude at the source and save quota)")
    ap.add_argument("--max", type=int, default=50)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()
    res = fetch(args.topic, args.review_type, args.year_from, args.year_to,
                args.safety, args.max, args.run, args.out, cochrane=args.cochrane,
                include_reviews=args.include_reviews)
    if res and not args.out:
        print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
