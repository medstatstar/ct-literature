#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_citations.py — citation verification (anti-hallucination, ct-base §17.1).

Each merged work is checked against its public identifier(s):
  - doi        -> resolves via https://doi.org/<doi> (final HTTP 200 after redirects)
  - pmid       -> resolves via Europe PMC EXT_ID lookup (JSON)
  - OpenAlex id -> resolves via api.openalex.org/works/<id> (JSON)

Each work gets three additive fields:
  citation_verified       (bool)
  citation_verify_status   "verified" | "unresolved" | "no_identifier" | "suspicious"
  citation_verify_note     (str, human readable)

Network runs ONLY when run=True (SAFE PREVIEW). A single verification failure marks
that work "unresolved" — it never aborts the whole pipeline. Pure stdlib + http_utils.
"""
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adapters import http_utils  # shared GET + retry; UA; get_json

_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s]+")
_OA_ID_RE = re.compile(r"W\d+")


def _resolve_doi(doi, timeout=15):
    """Return True if the DOI resolves (final HTTP 200 after redirects)."""
    url = doi if str(doi).startswith("http") else "https://doi.org/" + str(doi)
    req = urllib.request.Request(
        url, method="GET",
        headers={"User-Agent": http_utils.UA, "Range": "bytes=0-0"})
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        code = r.status
        try:
            r.close()
        except Exception:
            pass
        return code == 200
    except urllib.error.HTTPError as e:
        try:
            e.close()
        except Exception:
            pass
        return e.code == 200
    except Exception:
        return False


def _resolve_pmid(pmid, timeout=15):
    url = ("https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=%s"
           "&format=json&pageSize=1") % urllib.parse.quote("EXT_ID:%s" % pmid)
    try:
        j = http_utils.get_json(url, headers={"User-Agent": http_utils.UA},
                                timeout=timeout, max_retries=2)
        res = (j.get("resultList") or {}).get("result") or []
        return len(res) > 0
    except Exception:
        return False


def _resolve_openalex(oid, timeout=15):
    m = _OA_ID_RE.search(str(oid))
    if not m:
        return False
    url = "https://api.openalex.org/works/%s" % m.group(0)
    try:
        http_utils.get_json(url, headers={"User-Agent": http_utils.UA},
                            timeout=timeout, max_retries=2)
        return True
    except Exception:
        return False


def verify_one(work, timeout=15):
    """Return the three citation_* fields for one work (dict)."""
    doi = work.get("doi")
    pmid = work.get("pmid")
    oid = work.get("id") or ""

    # malformed DOI => suspicious (possible hallucinated identifier)
    if doi:
        if not _DOI_RE.search(str(doi)):
            return {"citation_verified": False,
                    "citation_verify_status": "suspicious",
                    "citation_verify_note": "malformed DOI: %s" % doi}

    notes = []
    if doi:
        if _resolve_doi(doi, timeout):
            return {"citation_verified": True, "citation_verify_status": "verified",
                    "citation_verify_note": "doi resolved"}
        notes.append("doi-unresolved")
    if pmid:
        if _resolve_pmid(pmid, timeout):
            return {"citation_verified": True, "citation_verify_status": "verified",
                    "citation_verify_note": "pmid resolved"}
        notes.append("pmid-unresolved")
    if oid:
        if _resolve_openalex(oid, timeout):
            return {"citation_verified": True, "citation_verify_status": "verified",
                    "citation_verify_note": "openalex-id resolved"}
        notes.append("openalex-unresolved")

    if not (doi or pmid or oid):
        return {"citation_verified": False, "citation_verify_status": "no_identifier",
                "citation_verify_note": "no doi/pmid/openalex-id"}
    return {"citation_verified": False, "citation_verify_status": "unresolved",
            "citation_verify_note": "; ".join(notes) or "could not verify"}


def verify_works(works, run=True, timeout=15):
    """Annotate works (copy-safe) with citation_* fields. Returns (works, summary).

    summary keys: total, verified, unresolved, no_identifier, suspicious,
                  skipped_preview (bool).
    """
    summary = {"total": 0, "verified": 0, "unresolved": 0,
               "no_identifier": 0, "suspicious": 0, "skipped_preview": False}
    out = []
    for w in works:
        w = dict(w)
        if not run:
            summary["skipped_preview"] = True
            out.append(w)
            continue
        res = verify_one(w, timeout=timeout)
        w.update(res)
        out.append(w)
        summary["total"] += 1
        summary[res["citation_verify_status"]] = \
            summary.get(res["citation_verify_status"], 0) + 1
    return out, summary


def main():
    ap = argparse.ArgumentParser(description="Verify citation identifiers (offline-safe preview).")
    ap.add_argument("--in", required=True, dest="inp", help="merged.json path")
    ap.add_argument("--run", action="store_true", help="perform live verification")
    ap.add_argument("--timeout", type=int, default=15)
    args = ap.parse_args()
    import json
    data = json.load(open(args.inp, encoding="utf-8"))
    works = data.get("works", [])
    out, summary = verify_works(works, run=args.run, timeout=args.timeout)
    print("[verify] %s" % json.dumps(summary, ensure_ascii=False))
    if args.run:
        # write back annotated works
        data["works"] = out
        json.dump(data, open(args.inp, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print("[OK] annotated %d works -> %s" % (len(out), args.inp))


if __name__ == "__main__":
    import argparse  # late import so module import (pipeline) stays cheap
    main()
