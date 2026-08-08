#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
normalize.py — multi-source literature normalization & merge.

Merges OpenAlex + Europe PMC + Semantic Scholar payloads into one unified, de-duplicated
work list. Dedupe key: DOI (preferred) else normalized title. Each merged record keeps a
`sources` list so the report can show provenance. Pure local computation, no network.
"""
import argparse
import json
import re

# Source priority (lower = higher priority). SemanticScholar is a low-priority
# supplementary source (its key requires a manual form review and is often absent),
# so pure-S2 works sink to the bottom; OpenAlex / EuropePMC and multi-source hits rank first.
_SOURCE_PRIORITY = {"OpenAlex": 0, "EuropePMC": 0, "SemanticScholar": 1}


def _norm_title(t):
    if not t:
        return ""
    t = t.lower()
    t = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", t)
    return " ".join(t.split())


def _norm_doi(d):
    if not d:
        return None
    d = d.strip().lower()
    m = re.search(r"10\.\d{4,9}/[^\s]+", d)
    return m.group(0) if m else d


def merge(payloads):
    """payloads: list of {source, query, works:[...]} dicts (or None)."""
    by_key = {}
    order = []

    for p in payloads:
        if not p:
            continue
        for w in p.get("works", []):
            doi = _norm_doi(w.get("doi"))
            title = _norm_title(w.get("title"))
            key = doi or ("t:" + title)
            if not key or key == "t:":
                continue
            if key in by_key:
                rec = by_key[key]
                if w["source"] not in rec["sources"]:
                    rec["sources"].append(w["source"])
                # prefer richer record (has abstract / mesh / authors / new fields)
                for fld in ("abstract_snippet", "mesh", "concepts", "keywords", "funders",
                            "publication", "year", "publication_date", "volume", "issue", "page",
                            "authors", "affiliations", "pmid", "pmcid",
                            "open_access_url", "journal_iso", "language"):
                    cur = rec.get(fld)
                    new = w.get(fld)
                    if (not cur) and new:
                        rec[fld] = new
                # Merge concepts and keywords lists (dedup)
                if w.get("concepts"):
                    rec_concepts = rec.get("concepts") or []
                    for c in w["concepts"]:
                        if c not in rec_concepts:
                            rec_concepts.append(c)
                    rec["concepts"] = rec_concepts
                if w.get("keywords"):
                    rec_kw = rec.get("keywords") or []
                    for k in w["keywords"]:
                        if k not in rec_kw:
                            rec_kw.append(k)
                    rec["keywords"] = rec_kw
                # Use max cited_by_count
                if (w.get("cited_by_count") or 0) > (rec.get("cited_by_count") or 0):
                    rec["cited_by_count"] = w["cited_by_count"]
                if w.get("is_safety") and not rec.get("is_safety"):
                    rec["is_safety"] = True
                if w.get("study_type") and rec.get("study_type") in (None, "article"):
                    rec["study_type"] = w["study_type"]
            else:
                w["sources"] = [w["source"]]
                by_key[key] = w
                order.append(key)

    works = [by_key[k] for k in order]
    # Source-priority demotion: pure SemanticScholar works sink to the bottom;
    # OpenAlex / EuropePMC and multi-source hits rank first.
    # Within the same priority, still sort by citation count descending.
    def _src_rank(w):
        srcs = w.get("sources") or [w.get("source")]
        return min(_SOURCE_PRIORITY.get(s, 1) for s in srcs)

    works.sort(key=lambda x: (_src_rank(x), -(x.get("cited_by_count") or 0)))
    return works


def main():
    ap = argparse.ArgumentParser(description="Merge + dedupe multi-source literature JSON.")
    ap.add_argument("--in", nargs="+", required=True, dest="inputs",
                    help="source payload JSON files (openalex / europepmc / s2)")
    ap.add_argument("--out", required=True, help="merged unified JSON")
    args = ap.parse_args()

    payloads = []
    for f in args.inputs:
        try:
            payloads.append(json.load(open(f, encoding="utf-8")))
        except Exception as e:
            print("[WARN] cannot read %s: %s" % (f, e))
    works = merge(payloads)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"count": len(works), "works": works}, f, ensure_ascii=False, indent=2)
    print("[OK] merged %d unique works -> %s" % (len(works), args.out))


if __name__ == "__main__":
    main()
