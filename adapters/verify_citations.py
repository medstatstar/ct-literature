#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_citations.py — citation verification (anti-hallucination, ct-base §17.1).

Each merged work is checked against its public identifier(s):
  - doi        -> resolves via https://doi.org/<doi> (final HTTP 2xx: 200 OK or 206
                 Partial Content after redirects; big publishers answer a Range request
                 with 206, which still means the DOI is live)
  - pmid       -> resolves via Europe PMC EXT_ID lookup (JSON)
  - OpenAlex id -> resolves via api.openalex.org/works/<id> (JSON)

Each work gets additive fields:
  citation_verified       (bool)
  citation_verify_status   "verified" | "unresolved" | "no_identifier" | "suspicious"
                            | "bot_blocked" | "mismatch"
  citation_verify_note     (str, human readable)
  citation_consistency     (bool | None)  title/author cross-check result
  citation_title_ratio    (float | None)  normalized title similarity to the resolved paper

Title/author consistency (anti-hallucination depth): once an identifier resolves to a
LIVE resource, we fetch that resource's canonical metadata (title + first-author surname)
from the authoritative, bot-friendly API — Crossref for DOIs, Europe PMC for PMIDs,
OpenAlex for OpenAlex ids — and compare it to the work we hold. A resolved-but-mismatched
identifier (e.g. a real-but-wrong DOI, or a hallucinated DOI that happens to exist) is
flagged ``mismatch`` instead of ``verified``. Metadata-fetch failures degrade gracefully
to "verified, consistency unchecked" — they NEVER invent a mismatch.

Network runs ONLY when run=True (SAFE PREVIEW). A single verification failure marks
that work "unresolved" — it never aborts the whole pipeline. Pure stdlib + http_utils.
"""
import os
import re
import sys
import difflib
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adapters import http_utils  # shared GET + retry; UA; get_json

_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s]+")
_OA_ID_RE = re.compile(r"W\d+")


def _strip_doi_tail(s):
    """Drop a trailing terminal punctuation a source may have appended to a DOI
    (e.g. "10.1056/NEJMoa2403614."). Split into two rstrip calls so the bracket
    chars never sit adjacent to a string-quote (avoids an accidental tokenization)."""
    return s.rstrip(".,;:").rstrip(")]")


def _resolve_doi(doi, timeout=15):
    """Resolve a DOI, returning one of: ``"ok"`` | ``"bot_blocked"`` | ``"unresolved"``.

    - ``"ok"``: final HTTP 2xx (200 OK or 206 Partial Content after the
      doi.org 302 redirect). Major publishers answer a ``Range: bytes=0-0``
      probe with 206 — that is still a live, resolvable DOI.
    - ``"bot_blocked"``: doi.org redirected to a *real* publisher page, but that
      publisher returned **403** to a programmatic request. The DOI EXISTS
      (the redirect succeeded; the publisher simply will not serve content to
      bots). This is a FALSE NEGATIVE and must be reported distinctly from a
      genuinely missing identifier — NEJM / JCO / JAMA / JNCCN / Wiley / MDPI
      all do this, so the most authoritative, highest-cited papers get caught
      here, not because they are suspect but because they are bot-blocked.
    - ``"unresolved"``: the DOI did not resolve to a live resource (404 / 410 /
      5xx), or the string was not a recognizable DOI at all.

    Robust to mixed DOI formats: OpenAlex stores the full URL
    (https://doi.org/10.x/...), Europe PMC stores the bare DOI (10.x/...).
    We extract the canonical 10.x/... suffix via _DOI_RE and always build the
    resolution URL ourselves, so no double-prefix can occur.
    """
    raw = str(doi).strip()
    m = _DOI_RE.search(raw)
    if not m:
        # not a recognizable DOI — leave malformed/None handling to the caller
        return "unresolved"
    # strip a trailing terminal punctuation a source may have appended to the DOI
    # (e.g. "10.1056/NEJMoa2403614.") so the resolution URL is clean.
    url = "https://doi.org/" + _strip_doi_tail(m.group(0))
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
        # 2xx => resolved (200 OK or 206 Partial Content)
        if 200 <= code < 300:
            return "ok"
        # Defensive: urllib raises HTTPError for 4xx/5xx, so we normally won't
        # land here for those — but if a non-2xx response slips through:
        if code == 403:
            return "bot_blocked"
        return "unresolved"
    except urllib.error.HTTPError as e:
        # urllib raises HTTPError for any 4xx/5xx final status (post-redirect).
        # A 403 from the publisher is bot-blocking; 404/410 mean the DOI is gone.
        try:
            e.close()
        except Exception:
            pass
        if e.code == 403:
            return "bot_blocked"
        return "unresolved"
    except Exception:
        return "unresolved"


def _resolve_pmid(pmid, timeout=15):
    """Resolve a PMID via Europe PMC EXT_ID lookup.

    Returns ``(ok, meta)`` where ``meta`` is ``(title, [surnames], "Europe PMC")`` or
    None. Reusing the same response for the consistency check avoids a second call.
    """
    url = ("https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=%s"
           "&format=json&pageSize=1") % urllib.parse.quote("EXT_ID:%s" % pmid)
    try:
        j = http_utils.get_json(url, headers={"User-Agent": http_utils.UA},
                                timeout=timeout, max_retries=2)
        res = (j.get("resultList") or {}).get("result") or []
        if not res:
            return False, None
        r0 = res[0]
        title = r0.get("title", "")
        al = (r0.get("authorList") or {}).get("author") or []
        surnames = [a.get("lastName", "") for a in al if a.get("lastName")]
        meta = (title, surnames, "Europe PMC") if (title or surnames) else None
        return True, meta
    except Exception:
        return False, None


def _fetch_meta_doi(doi, timeout=15):
    """Fetch canonical title + author surnames for a DOI from Crossref (bot-friendly).

    Returns ``(title, [surnames], "Crossref")`` or None on any failure / missing fields.
    Crossref is used (not doi.org content negotiation) because it returns cleanly
    structured ``title[0]`` + ``author[].family`` even when the publisher bot-blocks
    doi.org with a 403 — so a ``bot_blocked`` DOI can STILL be consistency-checked.
    """
    m = _DOI_RE.search(str(doi))
    if not m:
        return None
    bare = _strip_doi_tail(m.group(0))
    url = "https://api.crossref.org/works/%s" % urllib.parse.quote(bare)
    try:
        j = http_utils.get_json(url, headers={"User-Agent": http_utils.UA},
                                timeout=timeout, max_retries=2)
        msg = (j.get("message") or {})
        title = (msg.get("title") or [""])[0] if msg.get("title") else ""
        surnames = [a.get("family", "") for a in (msg.get("author") or [])
                    if a.get("family")]
        if not title and not surnames:
            return None
        return (title, surnames, "Crossref")
    except Exception:
        return None


def _resolve_openalex(oid, timeout=15):
    """Resolve an OpenAlex id via api.openalex.org/works/<id>.

    Returns ``(ok, meta)`` where ``meta`` is ``(title, [surnames], "OpenAlex")`` or None.
    """
    m = _OA_ID_RE.search(str(oid))
    if not m:
        return False, None
    url = "https://api.openalex.org/works/%s" % m.group(0)
    try:
        j = http_utils.get_json(url, headers={"User-Agent": http_utils.UA},
                                timeout=timeout, max_retries=2)
        title = j.get("title", "")
        auths = j.get("authorships") or []
        surnames = []
        for a in auths:
            dn = (a.get("author") or {}).get("display_name") or ""
            if dn:
                toks = _norm_name(dn).split()
                if toks:
                    surnames.append(toks[-1])
        meta = (title, surnames, "OpenAlex") if (title or surnames) else None
        return True, meta
    except Exception:
        return False, None


# ---------------------------------------------------------------------------
# Title / author consistency check (anti-hallucination depth)
# ---------------------------------------------------------------------------
_TITLE_THRESHOLD = 0.80  # normalized title similarity needed to call it "the same paper"


def _norm_title(s):
    if not s:
        return ""
    s = str(s).lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _norm_name(s):
    if not s:
        return ""
    s = str(s).lower()
    s = re.sub(r"[^a-z\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _first_author_tokens(authors):
    """Return ``(tokens_set, longest_token)`` for the FIRST author of a messy field.

    Handles "Last, First", "First Last", "First Initial", and list-of-strings. Order
    independent so both "Ramalingam V" and "V Ramalingam" surface "ramalingam".
    """
    if not authors:
        return set(), ""
    if isinstance(authors, list):
        authors = authors[0] if authors else ""
    if not authors:
        return set(), ""
    first = str(authors).split(",")[0].split(";")[0].strip()
    toks = [t for t in _norm_name(first).split() if t]
    return set(toks), (max(toks, key=len) if toks else "")


def _first_surname(surnames):
    """From a metadata surname list, return the normalized FIRST surname (or '')."""
    if not surnames:
        return ""
    if isinstance(surnames, list):
        for s in surnames:
            n = _norm_name(s)
            if n:
                return n
    return _norm_name(surnames)


def _author_ok(work_authors, meta_surname):
    """Order-independent check: does the work's first author match the metadata surname?

    Returns True / False / None (None when the metadata surname is unknown, so the
    author signal is inconclusive and must not by itself flip a verdict).
    """
    ms = _norm_name(meta_surname)
    if not ms:
        return None
    toks, longest = _first_author_tokens(work_authors)
    if not toks:
        return None
    if ms in toks:
        return True
    # fallback: fuzzy match against the longest token (minor normalization drift)
    return difflib.SequenceMatcher(None, ms, longest).ratio() >= 0.85


def _consistency(work, meta):
    """Compare the work we hold against the resolved paper's canonical metadata.

    ``meta`` is ``(title, [surnames], source)``. Returns a dict with ``consistent``
    (bool | None — None when metadata is too incomplete to judge), ``title_ratio`` and
    ``author_ok``.
    """
    title, surnames, source = meta
    wt = _norm_title(work.get("title"))
    mt = _norm_title(title)
    if not wt or not mt:
        return {"consistent": None, "title_ratio": None, "author_ok": None, "source": source}
    ratio = difflib.SequenceMatcher(None, wt, mt).ratio()
    ms = _first_surname(surnames)
    author_ok = _author_ok(work.get("authors"), ms)
    # Title must match; author must NOT contradict (an unknown author signal is not fatal).
    consistent = (ratio >= _TITLE_THRESHOLD) and (author_ok is not False)
    return {"consistent": consistent, "title_ratio": round(ratio, 3),
            "author_ok": author_ok, "source": source}


def _emit(work, via, base_status, meta, check_consistency):
    """Build the citation_* result after a positive identifier resolution.

    - ``meta is None`` or ``check_consistency=False``  -> keep ``base_status`` (verified /
      bot_blocked), note "consistency unchecked".
    - metadata present + consistent -> status "verified" (a bot_blocked DOI is upgraded
      to fully verified once its title/author are confirmed).
    - metadata present + MISMATCH  -> status "mismatch", citation_verified=False.
    """
    via_note = {"doi": "doi resolved", "pmid": "pmid resolved",
                "openalex": "openalex-id resolved"}[via]
    out = {"citation_verified": True, "citation_verify_status": base_status,
           "citation_verify_note": via_note,
           "citation_consistency": None, "citation_title_ratio": None}
    if not check_consistency or meta is None:
        if check_consistency and meta is None:
            out["citation_verify_note"] = via_note + "; consistency unchecked (metadata unavailable)"
        return out
    cmp = _consistency(work, meta)
    out["citation_title_ratio"] = cmp["title_ratio"]
    if cmp["consistent"] is None:
        out["citation_consistency"] = None
        out["citation_verify_note"] = via_note + "; consistency unchecked (metadata incomplete)"
        return out
    if cmp["consistent"]:
        out["citation_verify_status"] = "verified"  # upgrade bot_blocked -> verified
        out["citation_consistency"] = True
        out["citation_verify_note"] = ("%s; title/author consistent (%s, ratio=%.2f)"
                                       % (via_note, cmp["source"], cmp["title_ratio"]))
    else:
        out["citation_verify_status"] = "mismatch"
        out["citation_verified"] = False
        out["citation_consistency"] = False
        out["citation_verify_note"] = (
            "%s but TITLE/AUTHOR MISMATCH (%s, ratio=%.2f) — identifier resolves to a "
            "different paper; possible hallucinated/incorrect id"
            % (via_note, cmp["source"], cmp["title_ratio"]))
    return out


def verify_one(work, timeout=15, skip_sources=None, check_consistency=True):
    """Return the citation_* fields for one work (dict).

    Verification order (first positive wins), with title/author consistency depth:
      DOI (via doi.org)  -> fetch Crossref metadata
        -> PMID (Europe PMC EXT_ID, bot-friendly) -> reuse its metadata
        -> OpenAlex id (api.openalex.org, bot-friendly) -> reuse its metadata

    skip_sources is retained for API compatibility but no longer suppresses the
    reliable same-source fallback. When the DOI fails — and the dominant failure
    on big publishers is exactly a 403 bot-block while the Europe PMC / OpenAlex
    APIs still resolve cleanly — the PMID / OpenAlex id are the dependable
    bot-friendly path and MUST be tried. Skipping them produced false negatives
    (e.g. a Europe PMC work whose real PMID was never checked because its DOI
    hit a 403). See ct-literature CHANGELOG v0.6.6.

    After a positive resolution, if ``check_consistency`` is True we fetch the
    resolved paper's canonical metadata and compare title + first-author surname
    (see ``_emit`` / ``_consistency``). A resolved-but-different paper becomes
    ``mismatch`` instead of ``verified`` — this is the catch for a real-but-wrong
    or hallucinated DOI that still resolves to a LIVE resource.

    citation_verify_status values:
      verified      — identifier resolved AND title/author consistent (bot_blocked
                      DOIs are upgraded to verified once Crossref confirms them)
      bot_blocked   — DOI redirected to a real publisher but that publisher
                      returned 403 to a programmatic request; the DOI is REAL
                      (false negative, not a suspect/missing identifier)
      mismatch      — identifier resolved to a LIVE resource but its title/author
                      do NOT match this work (possible hallucinated/incorrect id)
      unresolved    — no identifier resolved to a live resource
      no_identifier — the work carried no doi/pmid/openalex-id at all
      suspicious    — the DOI string was malformed (possible hallucinated id)
    """
    doi = work.get("doi")
    pmid = work.get("pmid")
    oid = work.get("id") or ""
    skip = set(skip_sources or [])

    # malformed DOI => suspicious (possible hallucinated identifier)
    if doi and not _DOI_RE.search(str(doi)):
        return {"citation_verified": False,
                "citation_verify_status": "suspicious",
                "citation_verify_note": "malformed DOI: %s" % doi,
                "citation_consistency": False, "citation_title_ratio": None}

    # DOI first (canonical cross-source id). ok / bot_blocked both mean the DOI is
    # REAL; either way we can still pull Crossref metadata for the consistency check
    # (Crossref is bot-friendly even when the publisher bot-blocks doi.org).
    if doi:
        st = _resolve_doi(doi, timeout)
        if st in ("ok", "bot_blocked"):
            meta = _fetch_meta_doi(doi, timeout)
            return _emit(work, "doi", "verified" if st == "ok" else "bot_blocked",
                         meta, check_consistency)

    # PMID + OpenAlex id: reliable, bot-friendly API lookups. Always attempt when
    # the DOI did NOT positively verify — the fallback that keeps real papers from
    # being mislabeled "unresolved". Their responses already carry the metadata we
    # need for the consistency check (no extra call).
    if pmid:
        ok, meta = _resolve_pmid(pmid, timeout)
        if ok:
            return _emit(work, "pmid", "verified", meta, check_consistency)
    if oid:
        ok, meta = _resolve_openalex(oid, timeout)
        if ok:
            return _emit(work, "openalex", "verified", meta, check_consistency)

    notes = []
    if doi:
        notes.append("doi-unresolved")
    if pmid:
        notes.append("pmid-unresolved")
    if oid:
        notes.append("openalex-unresolved")
    if not (doi or pmid or oid):
        return {"citation_verified": False, "citation_verify_status": "no_identifier",
                "citation_verify_note": "no doi/pmid/openalex-id",
                "citation_consistency": None, "citation_title_ratio": None}
    return {"citation_verified": False, "citation_verify_status": "unresolved",
            "citation_verify_note": "; ".join(notes) or "could not verify",
            "citation_consistency": None, "citation_title_ratio": None}


def work_key(work):
    """Stable key for a work, used to attach verification results across
    merge/dedupe (the same paper may arrive from two sources).

    Priority: doi -> pmid -> OpenAlex id -> normalized title -> object id.
    """
    doi = work.get("doi")
    if doi:
        # normalize mixed formats: OpenAlex stores "https://doi.org/10.x/..." while
        # Europe PMC stores bare "10.x/...". Extract the canonical suffix so both
        # forms of the same paper share one key. Strip a trailing terminal
        # punctuation a source may have appended (e.g. "10.1056/x.").
        m = _DOI_RE.search(str(doi))
        _bare = (_strip_doi_tail(m.group(0)) if m else str(doi))
        return "doi:" + _bare.lower().strip()
    pmid = work.get("pmid")
    if pmid:
        return "pmid:" + str(pmid)
    oid = work.get("id") or ""
    m = _OA_ID_RE.search(str(oid))
    if m:
        return "oa:" + m.group(0)
    title = work.get("title")
    if title:
        return "title:" + re.sub(r"\s+", " ", str(title)).strip().lower()
    return "idx:" + str(id(work))


def summarize_results(results_map):
    """Build the verification summary dict from a {key: verify_one_result} map."""
    s = {"total": 0, "verified": 0, "bot_blocked": 0, "unresolved": 0,
         "no_identifier": 0, "suspicious": 0, "mismatch": 0, "skipped_preview": False}
    for r in results_map.values():
        s["total"] += 1
        st = r.get("citation_verify_status", "unresolved")
        s[st] = s.get(st, 0) + 1
    return s


def attach_verifications(works, results_map):
    """In-place attach a verification result onto each merged work (matched by work_key).

    Thread-safe: results_map is populated by the consumer pool before this is called;
    verify_one never mutates the caller's work objects, so no shared state is touched here.
    """
    for w in works:
        res = results_map.get(work_key(w))
        if res:
            w.update(res)


def verify_works(works, run=True, timeout=15, skip_sources=None, check_consistency=True):
    """Annotate works (copy-safe) with citation_* fields. Returns (works, summary).

    summary keys: total, verified, bot_blocked, unresolved, no_identifier,
                  suspicious, mismatch, skipped_preview (bool).
    """
    summary = {"total": 0, "verified": 0, "bot_blocked": 0, "unresolved": 0,
               "no_identifier": 0, "suspicious": 0, "mismatch": 0,
               "skipped_preview": False}
    out = []
    for w in works:
        w = dict(w)
        if not run:
            summary["skipped_preview"] = True
            out.append(w)
            continue
        res = verify_one(w, timeout=timeout, skip_sources=skip_sources,
                         check_consistency=check_consistency)
        w.update(res)
        out.append(w)
        summary["total"] += 1
        summary[res["citation_verify_status"]] = \
            summary.get(res["citation_verify_status"], 0) + 1
    return out, summary


def main():
    ap = argparse.ArgumentParser(description="Verify citation identifiers (offline-safe preview).")
    ap.add_argument("--in", default=".merged.json", dest="inp", help=".merged.json path")
    ap.add_argument("--run", action="store_true", help="perform live verification")
    ap.add_argument("--no-consistency", action="store_true",
                   help="skip title/author consistency cross-check "
                        "(⚠️ weakens the anti-hallucination guarantee; debugging only)")
    ap.add_argument("--timeout", type=int, default=15)
    args = ap.parse_args()
    import json
    data = json.load(open(args.inp, encoding="utf-8"))
    works = data.get("works", [])
    out, summary = verify_works(works, run=args.run, timeout=args.timeout,
                                check_consistency=not args.no_consistency)
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
