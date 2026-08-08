#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fetch_openalex.py — OpenAlex fetcher (primary source).

Reads the OpenAlex open scholarly graph (https://api.openalex.org/works) — a free,
citation-rich bibliographic API covering PubMed + preprint servers + many
journal full texts. OpenAlex has required an API key since 2026-02-13 (a free key
lifts the cap from 100 to 100k credits/day); provide it via --openalex-key /
OPENALEX_API_KEY / skill .env. Returns normalized work records. Zero confidential
data or information input; reads only public literature.

Unified work schema (also produced by fetch_europepmc / fetch_semantic_scholar):
  { source, id, title, authors, year, publication, type, cited_by_count,
    url, doi, abstract_snippet, mesh, is_safety }
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import http_utils  # shared GET+retry (exponential backoff, 429 Retry-After, Bearer key)

try:
    import requests  # optional; reserved for future requests-path use
except ImportError:
    requests = None

BASE = "https://api.openalex.org/works"

# OpenAlex type -> our coarse study_type
TYPE_MAP = {
    "article": "article",
    "review": "review",
    "book-chapter": "book-chapter",
    "proceedings": "proceedings",
    "preprint": "preprint",
    "posted-content": "preprint",
    "editorial": "editorial",
    "letter": "letter",
    "comment": "comment",
    "news": "news",
    "correction": "correction",
    "erratum": "correction",
    "dataset": "dataset",
    "report": "report",
    "reference-entry": "reference-entry",
    "peer-review": "peer-review",
}

SAFETY_LEXICON = [
    "adverse event", "adverse reaction", "side effect", "safety", "toxicity",
    "toxic", "case report", "pharmacovigilance", "drug-induced", "drug reaction",
]


def _strip_html(s):
    if not s:
        return s
    import re as _re
    return _re.sub(r"<[^>]+>", "", s)


def _openalex_type_for(review_type):
    """Map our --review-type to an OpenAlex `type:` filter (or None)."""
    if review_type in ("systematic-review", "scoping-review", "meta-analysis"):
        return "review"
    if review_type == "rct":
        return "article"
    if review_type == "case-report":
        return "article"
    return None  # all


def _study_type_from(record, review_type):
    t = record.get("type", "") or ""
    title = (record.get("title") or "").lower()
    abstract = (record.get("abstract_snippet") or "").lower()
    blob = title + " " + abstract
    if review_type in ("systematic-review", "meta-analysis", "scoping-review"):
        if "systematic review" in blob or "meta-analysis" in blob or "meta analysis" in blob:
            return {"systematic-review": "systematic-review",
                    "meta-analysis": "meta-analysis",
                    "scoping-review": "scoping-review"}[review_type]
        return "review"
    if review_type == "rct":
        if "randomized" in blob or "rct" in blob:
            return "rct"
        return "article"
    if review_type == "case-report":
        if "case report" in blob or "case series" in blob:
            return "case-report"
        return "article"
    if "systematic review" in blob or "meta-analysis" in blob:
        return "systematic-review"
    if "case report" in blob or "case series" in blob:
        return "case-report"
    if "randomized controlled trial" in blob or ("randomized" in blob and "trial" in blob):
        return "rct"
    return TYPE_MAP.get(t, t or "article")


def _flag_safety(record):
    blob = " ".join([
        record.get("title") or "",
        record.get("abstract_snippet") or "",
    ]).lower()
    return any(k in blob for k in SAFETY_LEXICON)


def _extract(record):
    loc = record.get("primary_location") or {}
    src = loc.get("source") or {} if loc else {}
    authorships = record.get("authorships") or []
    authors = []
    for a in authorships[:6]:
        nm = (a.get("author") or {}).get("display_name")
        if nm:
            authors.append(nm)
    if len(authorships) > 6:
        authors.append("et al.")
    abstract = record.get("abstract_inverted_index")
    snippet = None
    if abstract:
        snippet = _invindex_to_text(abstract)
    title = _strip_html(record.get("title") or record.get("display_name") or "")
    # External IDs (pmid, pmcid, etc.)
    ids = record.get("ids") or {}
    # Concepts (top 5 by score)
    concepts = []
    for c in sorted(record.get("concepts") or [], key=lambda x: -(x.get("score") or 0))[:5]:
        dn = c.get("display_name")
        if dn:
            concepts.append(dn)
    # Keywords
    keywords = [k.get("display_name") for k in (record.get("keywords") or [])[:8] if k.get("display_name")]
    # Open access URL
    oa = record.get("best_oa_location") or {}
    oa_url = oa.get("pdf_url") or oa.get("landing_page_url")
    if not oa_url:
        oa_url = loc.get("landing_page_url") or record.get("doi") or record.get("id")
    # Funders (top 3)
    funders = []
    for f in (record.get("funders") or [])[:3]:
        dn = f.get("display_name")
        if dn:
            funders.append(dn)
    # Biblio (volume/issue/page)
    biblio = record.get("biblio") or {}
    return {
        "source": "OpenAlex",
        "id": record.get("id"),
        "doi": record.get("doi"),
        "pmid": ids.get("pubmed"),
        "pmcid": ids.get("pmcid"),
        "title": title,
        "authors": authors,
        "year": record.get("publication_year"),
        "publication_date": record.get("publication_date"),
        "publication": src.get("display_name"),
        "type": record.get("type"),
        "study_type": None,  # filled by caller via _study_type_from
        "cited_by_count": record.get("cited_by_count") or 0,
        "url": oa_url,
        "open_access_url": oa_url if (record.get("best_oa_location") or {}).get("pdf_url") else None,
        "abstract_snippet": snippet,
        "mesh": None,
        "concepts": concepts or None,
        "keywords": keywords or None,
        "funders": funders or None,
        "language": record.get("language"),
        "is_retracted": record.get("is_retracted") or False,
        "volume": biblio.get("volume"),
        "issue": biblio.get("issue"),
        "page": biblio.get("first_page"),
        "is_safety": False,  # filled by caller
    }


def _invindex_to_text(inv):
    """OpenAlex stores abstract as an inverted index; reconstruct plaintext."""
    try:
        # inv: {word: [pos1, pos2, ...]}
        # Find max position
        max_pos = max(max(positions) for positions in inv.values() if positions)
        slots = [None] * (max_pos + 1)
        for word, idxs in inv.items():
            for i in idxs:
                if i <= max_pos:
                    slots[i] = word
        return " ".join(w for w in slots if w)
    except Exception:
        return ""


def fetch(topic, review_type="all", year_from=None, year_to=None,
          safety=False, max_results=30, run=False, out=None, mailto="dev@example.com",
          api_key=None):
    if not run:
        print("[PREVIEW] would query OpenAlex for topic=%r review_type=%r (use --run to execute)"
              % (topic, review_type))
        return None

    http_utils.notify_openalex_key_if_missing(api_key)
    filt = ["has_doi:true"]
    oa_type = _openalex_type_for(review_type)
    if oa_type:
        filt.append("type:%s" % oa_type)
    if year_from:
        filt.append("from_publication_date:%d-01-01" % year_from)
    if year_to:
        filt.append("to_publication_date:%d-12-31" % year_to)

    query = topic
    if review_type == "systematic-review":
        query += " systematic review"
    elif review_type == "meta-analysis":
        query += " meta-analysis"
    elif review_type == "scoping-review":
        query += " scoping review"
    elif review_type == "rct":
        query += " randomized controlled trial"
    elif review_type == "case-report":
        query += " case report"
    if safety:
        query += " (" + " OR ".join(SAFETY_LEXICON[:6]) + ")"

    collected = []
    page = 1
    per = 100
    # Overall fetch budget: each single request already has 45s x 4 retries of
    # protection, but a recomposed query + slow network can push multi-page
    # accumulation past the outer timeout. Add a global budget; stop paging on expiry.
    fetch_deadline = time.time() + 240
    while len(collected) < max_results:
        if time.time() > fetch_deadline:
            print("[WARN] OpenAlex fetch exceeded 240s budget; stopping pagination early")
            break
        params = {
            "search": query,
            "filter": ",".join(filt),
            "per-page": min(per, max_results - len(collected)),
            "page": page,
            "mailto": mailto,
            "select": "id,doi,title,display_name,publication_year,publication_date,type,cited_by_count,primary_location,authorships,abstract_inverted_index,ids,concepts,keywords,funders,best_oa_location,biblio,language,is_retracted",
        }
        url = BASE + "?" + urllib.parse.urlencode(params)
        headers = http_utils.build_openalex_headers(api_key=api_key, mailto=mailto)
        try:
            j = http_utils.get_json(url, headers=headers, timeout=45, max_retries=4)
        except http_utils.HttpError as e:
            print("[WARN] OpenAlex request failed: %s" % e)
            break
        results = j.get("results", [])
        if not results:
            break
        for rec in results:
            w = _extract(rec)
            w["study_type"] = _study_type_from(rec, review_type)
            w["is_safety"] = _flag_safety(w)
            collected.append(w)
        if len(results) < per:
            break
        page += 1
        time.sleep(0.3)  # be polite to the public API

    payload = {
        "source": "OpenAlex",
        "query": query,
        "review_type": review_type,
        "year_from": year_from,
        "year_to": year_to,
        "safety": safety,
        "count": len(collected),
        "works": collected,
    }
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print("[OK] OpenAlex wrote %d works -> %s" % (len(collected), out))
    return payload


def main():
    ap = argparse.ArgumentParser(description="Fetch literature via OpenAlex (public, no key).")
    ap.add_argument("--topic", required=True, help="free-text topic / drug / disease")
    ap.add_argument("--review-type", default="all",
                    choices=["all", "systematic-review", "scoping-review",
                             "meta-analysis", "rct", "case-report"])
    ap.add_argument("--year-from", type=int, help="lower bound publication year")
    ap.add_argument("--year-to", type=int, help="upper bound publication year")
    ap.add_argument("--safety", action="store_true", help="bias toward safety / AE literature")
    ap.add_argument("--max", type=int, default=30, help="max works to retrieve")
    ap.add_argument("--mailto", default="dev@example.com", help="OpenAlex polite-pool email")
    ap.add_argument("--openalex-key", default=http_utils.load_openalex_key(),
                    help="OpenAlex API key (Bearer). Auto-loaded from env OPENALEX_API_KEY "
                         "or skill .env. Free key lifts rate limit 100 -> 100k credits/day.")
    ap.add_argument("--run", action="store_true", help="execute network request")
    ap.add_argument("--out", help="output JSON path")
    args = ap.parse_args()
    res = fetch(args.topic, args.review_type, args.year_from, args.year_to,
                args.safety, args.max, args.run, args.out, args.mailto, args.openalex_key)
    if res and not args.out:
        print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
