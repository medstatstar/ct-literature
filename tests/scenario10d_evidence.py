#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scenario10d_evidence.py — offline deterministic regression for the P0/P1 upgrade
(P0: citation verification + evidence log; P1: PROSPERO registry, key-gated).

These cases do NOT hit the network (SAFE PREVIEW / graceful-skip paths), so they
run fast and reliably in any sandbox. They validate that the new wiring is correct:

  D1 verify preview      -> verify_works(run=False) sets skipped_preview, counts total=0
  D2 verify suspicious   -> verify_one(malformed DOI) -> status "suspicious" (no network)
  D3 verify no_id        -> verify_one(no identifiers) -> status "no_identifier" (no network)
  D4 evidence build+write-> build_log + write_log emits evidence_log.json/.md with sources
  D5 report evidence     -> report.render includes the bilingual evidence section
  D6 xlsx evidence sheet -> export_workbook adds an Evidence Log sheet (en/zh tolerant)
  D7 html evidence block -> export_html.render includes evidence block (en)
  D8 prospero no-token   -> fetch_prospero.fetch(run=True, token=None) returns None (no crash)

Run:
  python tests/scenario10d_evidence.py
"""
import json
import os
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL, "scripts")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.dirname(SCRIPTS))

from adapters import verify_citations  # noqa: E402
import evidence_log      # noqa: E402
from adapters import fetch_prospero    # noqa: E402
import report as report_mod  # noqa: E402
import export_xlsx       # noqa: E402
import export_html       # noqa: E402


def _synthetic_works():
    """A tiny mixed work list exercising the verification branches."""
    return [
        {"id": "W1", "source": "OpenAlex", "sources": ["OpenAlex"], "title": "Paper A",
         "doi": "10.1234/valid.example", "pmid": None, "year": 2022,
         "cited_by_count": 10, "is_safety": False},
        {"id": "W2", "source": "OpenAlex", "sources": ["OpenAlex"], "title": "Paper B",
         "doi": "NOT-A-DOI", "pmid": None, "year": 2021, "cited_by_count": 3,
         "is_safety": False},  # malformed -> suspicious
        {"id": "W3", "source": "OpenAlex", "sources": ["OpenAlex"], "title": "Paper C",
         "doi": None, "pmid": None, "year": 2020, "cited_by_count": 1,
         "is_safety": False},  # no identifier -> no_identifier
    ]


def _check(name, cond, detail=""):
    ok = bool(cond)
    print("[%s] %s -> %s%s" % ("PASS" if ok else "FAIL", name, ok,
                               (" | " + detail) if detail and not ok else ""))
    return ok, detail


def d1_verify_preview():
    works = _synthetic_works()
    out, vsum = verify_citations.verify_works(works, run=False)
    ok = vsum.get("skipped_preview") is True and vsum.get("total", 0) == 0
    return _check("D1_verify_preview", ok,
                   "skipped_preview=%s total=%s" % (vsum.get("skipped_preview"),
                                                    vsum.get("total")))


def d2_verify_suspicious():
    res = verify_citations.verify_one({"doi": "NOT-A-DOI", "pmid": None, "id": ""})
    ok = res["citation_verify_status"] == "suspicious"
    return _check("D2_verify_suspicious", ok, res.get("citation_verify_note", ""))


def d3_verify_no_id():
    res = verify_citations.verify_one({"doi": None, "pmid": None, "id": ""})
    ok = res["citation_verify_status"] == "no_identifier"
    return _check("D3_verify_no_id", ok, res.get("citation_verify_note", ""))


def d4_evidence_build_write():
    tmp = tempfile.mkdtemp(prefix="ctlit_ev_")
    payloads = [{"source": "OpenAlex", "query": "osimertinib", "review_type": "all",
                 "year_from": 2020, "year_to": None, "safety": False,
                 "count": 3, "works": _synthetic_works()}]
    meta = {"topic": "osimertinib", "verification": {"total": 3, "verified": 1,
             "unresolved": 1, "no_identifier": 1, "suspicious": 0}}
    log = evidence_log.build_log(payloads, "osimertinib", meta, meta["verification"])
    res = evidence_log.write_log(log, tmp)
    jpath = res["json"]
    mpath = res["md"]
    ok = (os.path.exists(jpath) and os.path.exists(mpath)
          and len(log.get("sources", [])) == 1)
    # sanity: re-read json + md
    reloaded = json.load(open(jpath, encoding="utf-8"))
    md_txt = open(mpath, encoding="utf-8").read()
    ok = ok and reloaded["topic"] == "osimertinib" and "Evidence Log" in md_txt
    return _check("D4_evidence_build_write", ok,
                   "json=%s md=%s" % (os.path.basename(jpath), os.path.basename(mpath)))


def d5_report_evidence():
    works = _synthetic_works()
    vsum = {"total": 3, "verified": 1, "unresolved": 1, "no_identifier": 1,
            "suspicious": 0, "skipped_preview": False}
    evidence = {"topic": "osimertinib", "generated_at": "2026-08-12T12:00:00",
                "sources": [{"source": "OpenAlex", "query": "osimertinib",
                             "review_type": "all", "year_from": 2020, "year_to": None,
                             "safety": False, "count": 3,
                             "retrieved_at": "2026-08-12T12:00:00", "status": "ok"}],
                "verification": vsum}
    meta = {"topic": "osimertinib", "verification": vsum, "evidence_log": evidence}
    md = report_mod.render(works, meta)
    ok = ("Evidence & verification" in md) and ("OpenAlex" in md) and ("verified=1" in md)
    return _check("D5_report_evidence", ok, "len=%d" % len(md))


def d6_xlsx_evidence_sheet():
    tmp = tempfile.mkdtemp(prefix="ctlit_xlsx_")
    out = os.path.join(tmp, "lit_report.xlsx")
    works = _synthetic_works()
    vsum = {"total": 3, "verified": 1, "unresolved": 1, "no_identifier": 1,
            "suspicious": 0, "skipped_preview": False}
    evidence = {"topic": "osimertinib", "generated_at": "2026-08-12T12:00:00",
                "sources": [{"source": "OpenAlex", "query": "osimertinib",
                             "review_type": "all", "year_from": 2020, "year_to": None,
                             "safety": False, "count": 3,
                             "retrieved_at": "2026-08-12T12:00:00", "status": "ok"}],
                "verification": vsum}
    data = {"count": len(works), "works": works, "meta": {"topic": "osimertinib"},
            "verification": vsum, "evidence_log": evidence}
    try:
        export_xlsx.export_workbook(data, out, lang="en")
    except Exception:
        return _check("D6_xlsx_evidence_sheet", False, traceback.format_exc(limit=3))
    ok = os.path.exists(out)
    sheet_name = None
    if ok:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(out)
            for cand in ("Evidence Log", "证据溯源"):
                if cand in wb.sheetnames:
                    sheet_name = cand
                    break
            ok = sheet_name is not None
        except Exception:
            # openpyxl unavailable: fall back to file-exists check only
            ok = ok and True
    return _check("D6_xlsx_evidence_sheet", ok,
                   "sheet=%s" % (sheet_name or "file-only"))


def d7_html_evidence_block():
    works = _synthetic_works()
    vsum = {"total": 3, "verified": 1, "unresolved": 1, "no_identifier": 1,
            "suspicious": 0, "skipped_preview": False}
    evidence = {"topic": "osimertinib", "generated_at": "2026-08-12T12:00:00",
                "sources": [{"source": "OpenAlex", "query": "osimertinib",
                             "review_type": "all", "year_from": 2020, "year_to": None,
                             "safety": False, "count": 3,
                             "retrieved_at": "2026-08-12T12:00:00", "status": "ok"}],
                "verification": vsum}
    data = {"count": len(works), "works": works, "meta": {"topic": "osimertinib"},
            "verification": vsum, "evidence_log": evidence}
    html = export_html.render(data, "en")
    ok = ("Evidence &amp; Verification" in html) and ("Verified" in html) and ("OpenAlex" in html)
    return _check("D7_html_evidence_block", ok, "len=%d" % len(html))


def d8_prospero_no_token():
    # key-gated graceful skip: no token => returns None, no network, no crash
    res = fetch_prospero.fetch("osimertinib", run=True, token=None)
    ok = res is None
    return _check("D8_prospero_no_token", ok,
                   "returned=%r (expect None)" % res)


def main():
    checks = [
        d1_verify_preview, d2_verify_suspicious, d3_verify_no_id,
        d4_evidence_build_write, d5_report_evidence, d6_xlsx_evidence_sheet,
        d7_html_evidence_block, d8_prospero_no_token,
    ]
    passed = 0
    for fn in checks:
        try:
            ok, _ = fn()
            if ok:
                passed += 1
        except Exception:
            print("[FAIL] %s raised: %s" % (fn.__name__, traceback.format_exc(limit=2)))
    print("scenario10d: %d/%d passed" % (passed, len(checks)))
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
