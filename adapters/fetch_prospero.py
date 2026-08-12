#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fetch_prospero.py — PROSPERO fetcher (systematic-review registry, P1).

PROSPERO (Centre for Reviews and Dissemination, Univ. of York) is the international
prospective register of systematic reviews. For ct-literature it answers a distinct
question from the bibliographic sources: *"is a review on this topic already
registered / ongoing?"* — i.e. duplication-avoidance + protocol discovery. It is a
review/protocol registry (not primary studies), so it is opt-in (default OFF) and
treated as a supplementary source (normalize._SOURCE_PRIORITY["PROSPERO"] = 1).

⚠️ UNVERIFIED SOURCE (2026-08-12): the PROSPERO REST API now requires an auth header
that is NOT documented publicly; every unauthenticated probe returns
`{"status":"error","errormessage":"Error code: header value undefined"}`. Until a valid
token + header name is supplied, this fetcher degrades gracefully (returns None, like
Semantic Scholar's no-key skip) and is NOT claimed functional. The caller must provide
`PROSPERO_API_TOKEN` (env) / `--prospero-token` and, if the default header name is
wrong, override it via `--prospero-header`. The success-response parser below is a
best-effort, schema-tolerant stub (handles both JSON and XML shapes) that must be
re-validated against a real 200 response before the feature is declared done.

Zero confidential data or information input; reads only public registry records.
"""
import argparse
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adapters import http_utils  # shared GET + retry

BASE = "https://www.crd.york.ac.uk/prospero/api/search/"

DEFAULT_HEADER = "PROSPERO-ACCESS-TOKEN"


def _build_query(topic, review_type="all", year_from=None, year_to=None, safety=False):
    q = topic
    if review_type in ("systematic-review", "meta-analysis"):
        q += " AND (systematic review OR meta-analysis)"
    elif review_type == "scoping-review":
        q += " AND scoping review"
    if safety:
        q += " AND (adverse event OR safety OR toxicity)"
    if year_from or year_to:
        lo = str(year_from) if year_from else ""
        hi = str(year_to) if year_to else ""
        if lo and hi:
            q += " AND (%s:%s)" % (lo, hi)
    return q


def _parse_response(text):
    """Best-effort parse of a PROSPERO search response into unified works.

    Tolerant of both JSON and XML shapes; returns [] on parse failure (never raises).
    Fields mapped defensively; unknown keys are ignored.
    """
    text = (text or "").strip()
    if not text:
        return []
    works = []
    # ---- try JSON first ----
    try:
        j = json.loads(text)
        if isinstance(j, dict) and j.get("status") == "error":
            return []  # API error payload (e.g. missing token) -> degrade
        reviews = (j.get("reviewlist") or j.get("resultList") or j.get("reviews")
                   or (j.get("return") or {}).get("reviewlist") or [])
        for rv in (reviews if isinstance(reviews, list) else []):
            w = _map_review(rv)
            if w:
                works.append(w)
        if works:
            return works
    except Exception:
        pass
    # ---- fall back to XML (legacy PROSPERO schema) ----
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(text)
        for rv in root.iter("review"):
            w = _map_review_xml(rv)
            if w:
                works.append(w)
    except Exception:
        pass
    return works


def _map_review(rv):
    if not isinstance(rv, dict):
        return None
    rid = rv.get("id") or rv.get("recordid") or rv.get("PROSPERO_ID")
    title = rv.get("displayName") or rv.get("title") or rv.get("reviewTitle")
    if not rid and not title:
        return None
    status = rv.get("status") or rv.get("reviewStatus") or ""
    reg = rv.get("registrationDate") or rv.get("dateRegistered") or ""
    url = ("https://www.crd.york.ac.uk/prospero/display_record.php?RecordID=%s"
           % rid) if rid else None
    return {
        "source": "PROSPERO",
        "id": rid,
        "doi": None, "pmid": None, "pmcid": None,
        "title": title,
        "authors": [],
        "year": int(reg[:4]) if (reg and reg[:4].isdigit()) else None,
        "publication_date": reg or None,
        "publication": "PROSPERO",
        "journal_iso": "PROSPERO",
        "type": "systematic-review-protocol",
        "study_type": "systematic-review",
        "cited_by_count": 0,
        "url": url,
        "open_access_url": None,
        "abstract_snippet": rv.get("description") or rv.get("objective") or "",
        "mesh": None,
        "concepts": None, "keywords": None, "funders": None,
        "language": None, "is_retracted": False, "is_safety": False,
        "is_preprint": False,
        "volume": None, "issue": None, "page": None,
        "affiliations": None,
        "sources": ["PROSPERO"],
        "prospero_status": status,
    }


def _map_review_xml(rv):
    def gt(tag):
        el = rv.find(tag)
        return el.text.strip() if el is not None and el.text else None
    rid = gt("id") or gt("recordid") or gt("PROSPERO_ID")
    title = gt("displayName") or gt("title") or gt("reviewTitle")
    if not (rid or title):
        return None
    status = gt("status") or gt("reviewStatus") or ""
    reg = gt("registrationDate") or gt("dateRegistered") or ""
    url = ("https://www.crd.york.ac.uk/prospero/display_record.php?RecordID=%s"
           % rid) if rid else None
    return {
        "source": "PROSPERO",
        "id": rid,
        "doi": None, "pmid": None, "pmcid": None,
        "title": title,
        "authors": [],
        "year": int(reg[:4]) if (reg and reg[:4].isdigit()) else None,
        "publication_date": reg or None,
        "publication": "PROSPERO",
        "journal_iso": "PROSPERO",
        "type": "systematic-review-protocol",
        "study_type": "systematic-review",
        "cited_by_count": 0,
        "url": url,
        "open_access_url": None,
        "abstract_snippet": gt("description") or gt("objective") or "",
        "mesh": None, "concepts": None, "keywords": None, "funders": None,
        "language": None, "is_retracted": False, "is_safety": False,
        "is_preprint": False,
        "volume": None, "issue": None, "page": None, "affiliations": None,
        "sources": ["PROSPERO"],
        "prospero_status": status,
    }


def fetch(topic, review_type="all", year_from=None, year_to=None, safety=False,
          max_results=30, run=False, out=None, token=None,
          header_name=DEFAULT_HEADER):
    if not run:
        print("[PREVIEW] would query PROSPERO for topic=%r review_type=%r "
              "(use --run to execute)" % (topic, review_type))
        return None

    if not token:
        print("[WARN] PROSPERO requires an API token (env PROSPERO_API_TOKEN / "
              "--prospero-token); skipping (key-gated, like Semantic Scholar). "
              "Feature UNVERIFIED until a working token + header is supplied.")
        return None

    q = _build_query(topic, review_type, year_from, year_to, safety)
    params = {"search": q, "limit": max_results, "offset": 0}
    url = BASE + "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": http_utils.UA, header_name: token}
    try:
        text = http_utils.get_text(url, headers=headers, timeout=45, max_retries=3)
    except http_utils.HttpError as e:
        print("[WARN] PROSPERO request failed: %s" % e)
        return None
    except Exception as e:  # noqa: BLE001
        print("[WARN] PROSPERO request error: %s" % e)
        return None

    works = _parse_response(text)
    payload = {
        "source": "PROSPERO",
        "query": q,
        "review_type": review_type,
        "year_from": year_from,
        "year_to": year_to,
        "safety": safety,
        "count": len(works),
        "works": works,
    }
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print("[OK] PROSPERO wrote %d works -> %s" % (len(works), out))
    return payload


def main():
    ap = argparse.ArgumentParser(description="Fetch systematic-review registrations via PROSPERO.")
    ap.add_argument("--topic", required=True)
    ap.add_argument("--review-type", default="all",
                    choices=["all", "systematic-review", "scoping-review",
                             "meta-analysis", "rct", "case-report"])
    ap.add_argument("--year-from", type=int)
    ap.add_argument("--year-to", type=int)
    ap.add_argument("--safety", action="store_true")
    ap.add_argument("--max", type=int, default=30)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--prospero-token", default=os.environ.get("PROSPERO_API_TOKEN"))
    ap.add_argument("--prospero-header", default=DEFAULT_HEADER)
    args = ap.parse_args()
    res = fetch(args.topic, args.review_type, args.year_from, args.year_to,
                args.safety, args.max, args.run, args.out,
                token=args.prospero_token, header_name=args.prospero_header)
    if res and not args.out:
        print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
