#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fetch_preprints.py — bioRxiv / medRxiv fetcher (clinical & biomedical preprints).

bioRxiv and medRxiv (both run by CSHL) expose NO free keyword-search API — their
official endpoints only resolve DOIs / date ranges. However, both servers ARE
indexed by Europe PMC's preprint corpus (SRC:PPR), keyed by
`bookOrReportDetails.publisher` ("bioRxiv" / "medRxiv"). So this fetcher queries
Europe PMC with `SRC:PPR AND publisher:<server>`, then emits works labelled with
the specific source ("bioRxiv" / "medRxiv") so they appear as distinct provenance
in the merged report.

No key required. Reuses http_utils.get_json (exponential backoff, Retry-After).
Zero confidential data or information input; reads only public literature.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import http_utils  # shared GET+retry (exponential backoff, 429 Retry-After)

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

SERVER_MAP = {
    "biorxiv": "bioRxiv",
    "medrxiv": "medRxiv",
}

SAFETY_LEXICON = [
    "adverse event", "adverse reaction", "side effect", "safety", "toxicity",
    "toxic", "case report", "pharmacovigilance", "drug-induced", "drug reaction",
]


def _strip_html(s):
    if not s:
        return s
    return re.sub(r"<[^>]+>", "", s)


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
    return "preprint"


def _flag_safety(title, abstract):
    blob = ((title or "") + " " + (abstract or "")).lower()
    return any(k in blob for k in SAFETY_LEXICON)


def _extract(rec, source_label):
    ji = rec.get("journalInfo") or {}
    authors = []
    affiliations = []
    al = rec.get("authorList") or {}
    for a in (al.get("author") or [])[:6]:
        nm = a.get("fullName")
        if nm:
            authors.append(nm)
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
    cited = rec.get("citedByCount")
    ftl = rec.get("fullTextUrlList") or {}
    ft_urls = ftl.get("fullTextUrl", [])
    fulltext_url = ft_urls[0].get("url") if ft_urls else None
    return {
        "source": source_label,
        "id": rec.get("id") or rec.get("doi"),
        "pmid": rec.get("pmid"),
        "pmcid": rec.get("pmcid"),
        "doi": rec.get("doi"),
        "title": title,
        "authors": authors or None,
        "affiliations": affiliations[:5] or None,
        "year": int(rec["pubYear"]) if rec.get("pubYear") and str(rec.get("pubYear")).isdigit() else None,
        "publication_date": rec.get("printPublicationDate") or rec.get("dateOfPublication"),
        "publication": source_label,
        "journal_iso": source_label,
        "type": "preprint",
        "study_type": _study_type_from(rec.get("pubTypeList", {}).get("pubType", []) or [], title, abstract),
        "cited_by_count": int(cited) if isinstance(cited, int) else 0,
        "url": fulltext_url or rec.get("doi") or None,
        "open_access_url": fulltext_url,
        "abstract_snippet": abstract or "",
        "mesh": mesh or None,
        "is_safety": _flag_safety(title, abstract),
        "is_preprint": True,
        "volume": None,
        "issue": None,
        "page": rec.get("pageInfo"),
    }


def fetch(topic, review_type="all", year_from=None, year_to=None,
          safety=False, max_results=30, run=False, out=None, server="biorxiv"):
    """Fetch preprints from one server (bioRxiv / medRxiv) via Europe PMC PPR.

    `server` is the key in SERVER_MAP; the emitted `source` label is the mapped
    display name ("bioRxiv" / "medRxiv").
    """
    source_label = SERVER_MAP.get(server, server)
    if not run:
        print("[PREVIEW] would query Europe PMC PPR for %s (topic=%r)"
              % (source_label, topic))
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
    # Restrict to the preprint corpus AND the specific server.
    q += " AND SRC:PPR AND publisher:%s" % source_label

    if year_from or year_to:
        lo = str(year_from) if year_from else "1900"
        hi = str(year_to) if year_to else "3000"
        q += " AND (PUB_YEAR:[%s TO %s])" % (lo, hi)

    collected = []
    page = 1
    per = 25
    while len(collected) < max_results:
        params = {
            "query": q,
            "format": "json",
            "resultType": "core",
            "pageSize": min(per, max_results - len(collected)),
            "page": page,
        }
        url = BASE + "?" + urllib.parse.urlencode(params)
        try:
            j = http_utils.get_json(url, headers={"User-Agent": http_utils.UA},
                                    timeout=45, max_retries=4)
        except http_utils.HttpError as e:
            print("[WARN] %s (Europe PMC PPR) request failed: %s"
                  % (source_label, e))
            break
        results = (j.get("resultList") or {}).get("result", [])
        if not results:
            break
        for rec in results:
            pub = (rec.get("bookOrReportDetails") or {}).get("publisher")
            if pub and pub.lower() == source_label.lower():
                collected.append(_extract(rec, source_label))
        if len(results) < per:
            break
        page += 1
        time.sleep(0.3)

    payload = {
        "source": source_label,
        "query": q,
        "review_type": review_type,
        "year_from": year_from,
        "year_to": year_to,
        "safety": safety,
        "count": len(collected),
        "works": collected,
    }
    if out:
        _write(out, payload)
    return payload


def _write(out, payload):
    try:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print("[OK] %s wrote %d works -> %s" % (payload["source"], payload["count"], out))
    except OSError as werr:
        print("[WARN] could not write %s payload: %s" % (payload["source"], werr))


def _empty(topic, source_label):
    return {"source": source_label, "query": topic, "count": 0, "works": []}


def main():
    ap = argparse.ArgumentParser(description="Fetch bioRxiv / medRxiv via Europe PMC PPR.")
    ap.add_argument("--topic", required=True)
    ap.add_argument("--server", default="biorxiv", choices=["biorxiv", "medrxiv"])
    ap.add_argument("--review-type", default="all",
                    choices=["all", "systematic-review", "scoping-review",
                             "meta-analysis", "rct", "case-report"])
    ap.add_argument("--year-from", type=int)
    ap.add_argument("--year-to", type=int)
    ap.add_argument("--safety", action="store_true")
    ap.add_argument("--max", type=int, default=30)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()
    res = fetch(args.topic, args.review_type, args.year_from, args.year_to,
                args.safety, args.max, args.run, args.out, server=args.server)
    if res and not args.out:
        print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
