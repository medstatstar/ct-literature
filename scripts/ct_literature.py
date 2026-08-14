#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ct_literature.py — orchestration entry point.

One-shot pipeline: fetch OpenAlex (required) + optional Europe PMC / Semantic Scholar
-> normalize (merge + dedupe) -> HTML / XLSX report. Reads only public literature;
zero confidential data or information input.

Usage:
  python scripts/ct_literature.py --topic "osimertinib" --review-type systematic-review \
      --year-from 2018 --safety --run --out-dir ./out
"""
import argparse
import json
import os
import queue
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)
# adapters/ 位于技能根目录（scripts/ 的上一级）——保证 CLI 直接运行时能找到
sys.path.insert(0, os.path.dirname(_SCRIPTS_DIR))
from adapters import fetch_openalex
from adapters import fetch_europepmc
from adapters import fetch_semantic_scholar
from adapters import fetch_preprints
from adapters import fetch_arxiv
import normalize
import export_xlsx
import export_html
import score_relevance
import screen_prisma
import format_citations
import obsidian_exporter
import zotero_exporter
import topic_translator  # 检索词 中文→英文 离线词典翻译
from adapters import verify_citations  # P0: citation identifier verification (anti-hallucination)
import evidence_log      # P0: provenance audit trail (ct-base §17.1)
from adapters import fetch_prospero    # P1: PROSPERO systematic-review registry (key-gated, opt-in)
from adapters import http_utils  # shared GET+retry; load_openalex_key() auto-loads key from env/.env
import i18n  # bilingual (EN/ZH) localization


# ── friendly degradation notice (rate-limit / fetch failure) ─────────────────────
def _friendly_source_note(source, exc):
    """Build a bilingual, actionable degradation note when a source fails to fetch.

    Returns {"source", "status", "message_zh", "message_en", "banner"} so renderers can
    show the user's-locale string while the evidence log keeps BOTH languages. The console
    `banner` uses the current OS locale. Never aborts the pipeline — a failed source just
    degrades coverage, and the user is told exactly what happened and what to do.
    """
    rl = isinstance(exc, http_utils.RateLimitError)
    if rl and source == "OpenAlex" and exc.keyless:
        key, kw = "openalex.rate_limited", {"url": http_utils.OPENALEX_SIGNUP_URL}
    elif rl:
        key, kw = "source.rate_limited", {"source": source}
    else:
        key, kw = "source.error", {"source": source, "err": str(exc)}
    cur = i18n.t(key, **kw)                       # current OS locale
    i18n.set_lang("zh"); msg_zh = i18n.t(key, **kw)
    i18n.set_lang("en"); msg_en = i18n.t(key, **kw)
    i18n.set_lang(None)                          # reset to auto-detect
    return {"source": source, "status": "rate_limited" if rl else "error",
            "message_zh": msg_zh, "message_en": msg_en, "banner": cur}


# ── progress event stream (--progress json) ───────────────────────────────────
# human（默认）：保持可读控制台进度；json：stdout 只输出 NDJSON 事件流（供 agent 流式消费）。
_PROGRESS = "human"
_ORIG_STDOUT = None  # json 模式下保留真 stdout；子模块进度 print 转 stderr 保持 NDJSON 纯净


def _out(human_msg=None, event=None, **fields):
    """Emit one progress line.

    - human mode (default): print `human_msg` (None = silent, for json-only events).
    - json mode: print a single-line JSON object {"event": <event>, **fields} on the
      real stdout (always flushed so an agent can stream it); the human message is
      suppressed and stdout stays pure NDJSON (sub-module prints are redirected to
      stderr by main()).
    """
    if _PROGRESS == "json":
        rec = {"event": event} if event else {}
        rec.update(fields)
        print(json.dumps(rec, ensure_ascii=False),
              file=_ORIG_STDOUT if _ORIG_STDOUT is not None else sys.stdout,
              flush=True)
    elif human_msg:
        print(human_msg, flush=True)


def _verify_top_n(works, n, timeout=15, check_consistency=True):
    """Verify only the top-N (already ranked) works concurrently.

    Used by `--verify top`: the most relevant / most-cited surviving works get full
    identifier verification; the rest are marked `unverified_sampled` (no network call).
    Each work's own `sources` list drives source-aware skip (a paper already returned by
    OpenAlex / Europe PMC skips the redundant same-source re-resolution).

    Returns (results_map, skipped_count).
    """
    target = works[:n]
    results = {}
    if not target:
        return results, len(works)
    _nw = min(8, len(target))
    with ThreadPoolExecutor(max_workers=_nw) as _ex:
        _futs = {}
        for _w in target:
            _ss = _w.get("sources") or ([_w.get("source")] if _w.get("source") else None)
            _futs[_ex.submit(verify_citations.verify_one, _w, timeout, _ss,
                              check_consistency)] = \
                verify_citations.work_key(_w)
        for _f in as_completed(_futs):
            results[_futs[_f]] = _f.result()
    return results, len(works) - len(target)


# P0 new capabilities default flags
DEFAULT_CITATION_STYLE = "apa"
DEFAULT_EXPORT_BIB = True
DEFAULT_PRISMA = True
DEFAULT_RANK = "cited"  # keep legacy cited-by ordering unless --rank relevance


def run(topic, review_type="all", year_from=None, year_to=None, safety=False,
        max_results=30, with_europepmc=True, with_semantic_scholar=False,
        with_biorxiv=False, with_medrxiv=False, with_arxiv=False,
        with_prospero=False, prospero_token=None, prospero_header="PROSPERO-ACCESS-TOKEN",
        verify_mode="all", verify_top_n=15, verify_consistency=True,
        out_dir="./out", make_xlsx=True, make_html=True, openalex_key=None,
        citation_style=DEFAULT_CITATION_STYLE, export_bib=DEFAULT_EXPORT_BIB,
        prisma=DEFAULT_PRISMA, rank=DEFAULT_RANK, keywords=None,
        obsidian=False, zotero=False, lang="auto"):
    os.makedirs(out_dir, exist_ok=True)
    # normalize --keywords (comma-separated string) → list once, so scoring AND all
    # exporters (HTML banner / XLSX scope / meta JSON) see the same shape
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    # Chinese topic → English via bundled offline dictionary (term_map + drug_name_map).
    # The translated query goes to the APIs; the ORIGINAL topic is preserved for meta /
    # reports / evidence log so the user's wording stays reproducible.
    _topic_zh = topic
    _tp = topic_translator.translate_topic(topic)
    if _tp["translated"]:
        topic = _tp["topic_en"]
        if _tp["untranslated"]:
            _out("[i18n] " + i18n.t("topic.partial", rest="、".join(_tp["untranslated"])),
                 "topic_translated", zh=_topic_zh, en=topic, partial=True)
        else:
            _out("[i18n] " + i18n.t("topic.translated", en=topic),
                 "topic_translated", zh=_topic_zh, en=topic, partial=False)
    http_utils.notify_openalex_key_if_missing(openalex_key)
    oa_json = os.path.join(out_dir, "openalex.json")
    epmc_json = os.path.join(out_dir, "europepmc.json")
    s2_json = os.path.join(out_dir, "semantic_scholar.json")
    biorxiv_json = os.path.join(out_dir, "biorxiv.json")
    medrxiv_json = os.path.join(out_dir, "medrxiv.json")
    arxiv_json = os.path.join(out_dir, "arxiv.json")
    prospero_json = os.path.join(out_dir, "prospero.json")
    merged_json = os.path.join(out_dir, ".merged.json")

    # ---- fetch all enabled sources in PARALLEL (per-source concurrency) ----
    # Each source is an independent network call that writes its own JSON file; running
    # them concurrently turns the summed per-source latency into the latency of the
    # SLOWEST source. (Intra-source multi-page pagination stays serial inside each
    # fetcher — default max_results=30 fits one page, and parallel paging would raise
    # rate-limit risk on the keyless pool.)
    jobs = []
    jobs.append(("OpenAlex", lambda: fetch_openalex.fetch(
        topic, review_type, year_from, year_to, safety, max_results,
        run=True, out=oa_json, api_key=openalex_key)))
    if with_europepmc:
        jobs.append(("EuropePMC", lambda: fetch_europepmc.fetch(
            topic, review_type, year_from, year_to, safety, max_results,
            run=True, out=epmc_json)))
    if with_semantic_scholar:
        jobs.append(("SemanticScholar", lambda: fetch_semantic_scholar.fetch(
            topic, review_type, year_from, year_to, safety, max_results,
            run=True, out=s2_json)))
    if with_biorxiv:
        jobs.append(("bioRxiv", lambda: fetch_preprints.fetch(
            topic, review_type, year_from, year_to, safety, max_results,
            run=True, out=biorxiv_json, server="biorxiv")))
    if with_medrxiv:
        jobs.append(("medRxiv", lambda: fetch_preprints.fetch(
            topic, review_type, year_from, year_to, safety, max_results,
            run=True, out=medrxiv_json, server="medrxiv")))
    if with_arxiv:
        jobs.append(("arXiv", lambda: fetch_arxiv.fetch(
            topic, review_type, year_from, year_to, safety, max_results,
            run=True, out=arxiv_json)))
    if with_prospero:
        jobs.append(("PROSPERO", lambda: fetch_prospero.fetch(
            topic, review_type, year_from, year_to, safety, max_results,
            run=True, out=prospero_json, token=prospero_token, header_name=prospero_header)))

    payloads = []
    source_notes = []  # degradation notices for sources that failed to fetch (rate-limit / error)
    # ---- P0: citation verification pipeline (producer = fetch, consumer = worker pool).
    # Runs CONCURRENTLY with the fetch phase: as soon as a source yields its works they are
    # queued for verification — no need to wait for all downloads to finish. Each work is
    # verified the moment it arrives ("verify one as it lands"). ----
    _verify_q = queue.Queue()
    _verify_results = {}
    _verify_workers = []
    # Cross-source duplicates (the same work indexed by OpenAlex AND Europe PMC) share a
    # work_key — verify once, attach to every copy by key (see attach_verifications).
    _seen_keys = set()
    # Source-aware streaming verification runs in `all` and `background` modes.
    # In `top` mode we verify after ranking (only the top-N); in `none` we skip entirely.
    _should_stream = (verify_mode in ("all", "background") and jobs)
    if _should_stream:
        _out("[verify] mode=%s (streaming; source-aware skip on same-source re-resolution)"
             % verify_mode,
             "verify_mode", mode=verify_mode)
        _verify_done = 0
        _verify_lock = threading.Lock()

        def _verify_worker():
            nonlocal _verify_done
            while True:
                _item = _verify_q.get()
                if _item is None:
                    _verify_q.task_done()
                    break
                _w, _k, _src = _item
                try:
                    # verify_one always tries DOI -> PMID -> OpenAlex id. When the DOI
                    # is bot-blocked (big-publisher 403) it falls back to the bot-friendly
                    # PMID / OpenAlex APIs instead of being mislabeled "unresolved".
                    # (skip_sources is accepted for API compat but no longer suppresses
                    # that reliable fallback — see verify_citations CHANGELOG v0.6.6.)
                    _verify_results[_k] = verify_citations.verify_one(
                        _w, timeout=15, skip_sources=[_src] if _src else None,
                        check_consistency=verify_consistency)
                except Exception as _ve:  # one failure must not abort the pool
                    _verify_results[_k] = {"citation_verified": False,
                                          "citation_verify_status": "unresolved",
                                          "citation_verify_note": "verify-error: %s" % _ve}
                with _verify_lock:
                    _verify_done += 1
                    _done = _verify_done
                _out(None, "verify_progress", done=_done)
                _verify_q.task_done()

        _vw = min(24, max(1, len(jobs) * 4))  # widened pool; per-host politeness enforced
        # by the connection-pool caps in http_utils (doi.org 8 / Crossref 4 / OpenAlex 6 /
        # EPMC 6), not by the worker count — so a 50-work verify finishes much sooner.
        for _ in range(_vw):
            _t = threading.Thread(target=_verify_worker, daemon=True)
            _t.start()
            _verify_workers.append(_t)

    # ---- time notice: a real run can take several minutes; tell the user up front ----
    # Honest estimate by verification scope; verification (`all`) overlaps with the fetch
    # phase but on large result sets still dominates the wall-clock time. Output path is
    # shown so the user knows where to look while waiting. Locale follows the OS.
    _est = i18n.t("run.est.%s" % verify_mode)
    if verify_mode == "top":
        _vmode = i18n.t("run.vmode.top", n=verify_top_n)
    else:
        _vmode = i18n.t("run.vmode.%s" % verify_mode)
    _out(i18n.t("run.starting", est=_est, vmode=_vmode, out=out_dir),
         "run_start", est=_est, vmode=_vmode, out=out_dir)

    if jobs:
        _t0 = time.time()
        _t_start = {n: time.time() for n, _ in jobs}
        with ThreadPoolExecutor(max_workers=len(jobs)) as _ex:
            _futs = {_ex.submit(fn): name for name, fn in jobs}
            _res = {}
            for _fut in as_completed(_futs):
                _name = _futs[_fut]
                try:
                    _p = _fut.result()
                    _res[_name] = _p
                    _n = len((_p or {}).get("works") or [])
                    _out("[OK] source %s: %d works in %.1fs"
                         % (_name, _n, time.time() - _t_start[_name]),
                         "source_done", source=_name, n=_n,
                         secs=round(time.time() - _t_start[_name], 1))
                    # stream this source's works into the verification queue immediately
                    if _should_stream and _p is not None:
                        for _w in (_p.get("works") or []):
                            _wk = verify_citations.work_key(_w)
                            if _wk not in _seen_keys:  # cross-source duplicates: verify once
                                _seen_keys.add(_wk)
                                _verify_q.put((_w, _wk, _w.get("source")))
                except Exception as _e:  # one source failing must not kill the pipeline
                    _note = _friendly_source_note(_name, _e)
                    _out(_note["banner"], "source_failed", source=_name,
                         status=_note.get("status"), message_en=_note.get("message_en"))
                    source_notes.append(_note)
                    _res[_name] = None
        # re-assemble in the original (stable) source order
        for _name, _ in jobs:
            _p = _res.get(_name)
            if _p is not None:
                payloads.append(_p)
        _out("[OK] parallel fetch: %d source(s) in %.1fs"
             % (len(jobs), time.time() - _t0),
             "fetch_done", sources=len(jobs), secs=round(time.time() - _t0, 1))
    else:
        _out("[WARN] no sources enabled", "no_sources")

    # Drain the verification workers (they finish as the queue empties).
    # Normal modes drain here; `background` mode defers the drain until AFTER the
    # unverified fast preview is rendered (two-phase delivery).
    def _drain_verifiers():
        for _ in _verify_workers:
            _verify_q.put(None)
        for _t in _verify_workers:
            _t.join()

    if verify_mode != "background":
        _drain_verifiers()

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
    # `all`: verification already ran concurrently with fetch above; attach + summarize.
    # `top`: verify only the top-N (ranked) works concurrently, leave the rest unverified.
    # `none`: skip verification entirely (preview-style annotation, no network).
    vsum = None
    if verify_mode == "all":
        verify_citations.attach_verifications(works, _verify_results)
        vsum = verify_citations.summarize_results(_verify_results)
        vsum["mode"] = "all"
        vsum["skipped_preview"] = False
        _out("[OK] citation verification (concurrent, all): %s"
             % json.dumps(vsum, ensure_ascii=False),
             "verify_done", mode="all", summary=vsum)
    elif verify_mode == "top":
        _tv, _skipped = _verify_top_n(works, verify_top_n,
                                      check_consistency=verify_consistency)
        verify_citations.attach_verifications(works, _tv)
        # mark works beyond the top-N as sampled-out (no network call)
        for _w in works[verify_top_n:]:
            _w.setdefault("citation_verified", False)
            _w.setdefault("citation_verify_status", "unverified_sampled")
            _w.setdefault("citation_verify_note",
                          "not verified (sampled out; --verify top N=%d)" % verify_top_n)
        vsum = verify_citations.summarize_results(_tv)
        vsum["unverified_sampled"] = _skipped
        vsum["total"] = len(works)
        vsum["mode"] = "top"
        vsum["top_n"] = verify_top_n
        vsum["skipped_preview"] = False
        _out("[OK] citation verification (top-%d, sampled %d): %s"
             % (verify_top_n, _skipped, json.dumps(vsum, ensure_ascii=False)),
             "verify_done", mode="top", top_n=verify_top_n,
             sampled=_skipped, summary=vsum)
    elif verify_mode == "none":
        for _w in works:
            _w.setdefault("citation_verified", False)
            _w.setdefault("citation_verify_status", "no_identifier")
            _w.setdefault("citation_verify_note", "verify disabled (--verify none)")
        vsum = {"total": len(works), "verified": 0, "bot_blocked": 0, "unresolved": 0,
                "no_identifier": len(works), "suspicious": 0, "mismatch": 0,
                "unverified_sampled": 0, "skipped_preview": True,
                "mode": "none"}
        _out("[OK] citation verification skipped (mode=none)", "verify_done", mode="none")
    else:  # verify_mode == "background" — handled by the two-phase block below
        pass

    # ---- build meta / evidence / exports (shared by all verify modes) ----
    def _finalize(works, vsum, suffix=""):
        """Render intermediate state + all exports for a given (works, vsum) pair.

        suffix=""            -> normal deliverables (lit_report.xlsx / lit_report.html)
        suffix="_verified"   -> verified refresh: lit_report_verified.xlsx + re-render
                                lit_report.html (overwrites the preview with the
                                verified version).
        Returns the primary deliverable path.
        """
        meta = {"topic": _topic_zh, "review_type": review_type,
                "year_from": year_from, "year_to": year_to, "safety": safety,
                "citation_style": citation_style if export_bib else None,
                "rank": rank, "keywords": keywords,
                "prisma": prisma_block,
                "verification": vsum,
                "with_prospero": with_prospero,
                "source_notes": source_notes}
        if _tp["translated"]:  # 中文→英文翻译信息（供报告展示与溯源）
            meta["topic_en"] = _tp["topic_en"]
            meta["topic_translated"] = True
            meta["topic_hits"] = _tp["hits"]
            meta["topic_untranslated"] = _tp["untranslated"]
        oa_status = http_utils.get_openalex_key_status()
        config = {
            "openalex_key": oa_status,
            "openalex_key_url": http_utils.OPENALEX_SIGNUP_URL,
            "semantic_scholar_key": "configured" if http_utils.load_s2_key() else "missing",
            "prospero_token": "configured" if (with_prospero and prospero_token) else (
                "missing" if with_prospero else "not_used"),
        }
        meta["config"] = config
        evidence = evidence_log.build_log(payloads, topic, meta, vsum, config=config,
                                          degraded=source_notes)
        ev_res = evidence_log.write_log(evidence, out_dir)
        meta["evidence_log"] = evidence
        _out("[OK] evidence_log -> %s / %s" % (ev_res["json"], ev_res["md"]),
             "evidence_log", json_path=ev_res["json"], md_path=ev_res["md"])
        if oa_status == "missing":
            _out("[WARN] OpenAlex ran in keyless mode — re-run with a configured key for full coverage.",
                 "warn", kind="keyless")
        out_data = {"count": len(works), "works": works}
        if prisma_block:
            out_data["prisma"] = prisma_block
        out_data["evidence_log"] = evidence
        out_data["verification"] = vsum
        out_data["meta"] = meta  # topic / keywords / review_type / year span → HTML & XLSX headers
        with open(merged_json, "w", encoding="utf-8") as f:
            json.dump(out_data, f, ensure_ascii=False, indent=2)
        _out("[OK] intermediate state -> %s (hidden; reused by standalone tools)" % merged_json,
             "intermediate", path=merged_json)
        primary = None
        _ver = {"verified": bool(suffix)}
        if export_bib:
            try:
                fc = format_citations.export_citations(
                    {"count": len(works), "works": works}, style=citation_style,
                    out_dir=out_dir, lang="auto")
                _out("[OK] citations(%s) -> %s / %s" % (
                    citation_style, fc["bib_path"], fc["ris_path"]),
                    "export_done", kind="citations",
                    bib=fc["bib_path"], ris=fc["ris_path"], **_ver)
            except Exception as _ce:
                _out("[WARN] citation export failed: %s" % _ce,
                     "export_failed", kind="citations", error=str(_ce), **_ver)
        if make_xlsx:
            xlsx_out = os.path.join(out_dir, "lit_report%s.xlsx" % suffix)
            try:
                export_xlsx.export_workbook(
                    {"count": len(works), "works": works, "meta": meta},
                    xlsx_out, lang=lang)
                _out("[OK] xlsx  -> %s" % xlsx_out, "export_done", kind="xlsx",
                     path=xlsx_out, **_ver)
                primary = primary or xlsx_out
            except Exception as _xe:
                _out("[WARN] xlsx export failed: %s" % _xe,
                     "export_failed", kind="xlsx", error=str(_xe), **_ver)
        if make_html:
            html_out = os.path.join(out_dir, "lit_report.html")
            try:
                html_text = export_html.render(out_data, lang)
                with open(html_out, "w", encoding="utf-8") as f:
                    f.write(html_text)
                _out("[OK] html  -> %s" % html_out, "export_done", kind="html",
                     path=html_out, **_ver)
                primary = html_out
            except Exception as _he:
                _out("[WARN] html export failed: %s" % _he,
                     "export_failed", kind="html", error=str(_he), **_ver)
        if obsidian:
            try:
                ob = obsidian_exporter.export_obsidian(
                    {"count": len(works), "works": works}, out_dir=out_dir, lang=lang)
                _out("[OK] obsidian notes=%d -> %s" % (ob["count"], ob["folder"]),
                     "export_done", kind="obsidian", count=ob["count"],
                     folder=ob["folder"], **_ver)
                _out("     moc -> %s" % ob["moc"], "export_done",
                     kind="obsidian_moc", path=ob["moc"], **_ver)
            except Exception as _oe:
                _out("[WARN] obsidian export failed: %s" % _oe,
                     "export_failed", kind="obsidian", error=str(_oe), **_ver)
        if zotero:
            try:
                zo = zotero_exporter.export_zotero(
                    {"count": len(works), "works": works}, out_dir=out_dir)
                _out("[OK] zotero csv/ris -> %s / %s" % (zo["csv"], zo["ris"]),
                     "export_done", kind="zotero", csv=zo["csv"], ris=zo["ris"], **_ver)
            except Exception as _ze:
                _out("[WARN] zotero export failed: %s" % _ze,
                     "export_failed", kind="zotero", error=str(_ze), **_ver)
        return primary

    # Two-phase (background) verification: fast unverified preview first, then a
    # verified refresh once the background verification workers finish. The user /
    # agent gets a usable report at fetch-time (~seconds) instead of waiting for the
    # full verification pass; verify_progress events keep streaming meanwhile.
    if verify_mode == "background":
        for _w in works:
            _w.setdefault("citation_verified", False)
            _w.setdefault("citation_verify_status", "pending_background")
            _w.setdefault("citation_verify_note",
                          "verification running in background (--verify background)")
        vsum_bg = {"total": len(works), "pending": len(works),
                   "skipped_preview": True, "mode": "background"}
        _out("[OK] background verification: fast unverified preview (results attach later)",
             "verify_mode", mode="background")
        primary = _finalize(works, vsum_bg, suffix="")
        _out("[OK] report ready (unverified preview): %s" % primary,
             "report_ready", primary=primary or "")
        _drain_verifiers()
        verify_citations.attach_verifications(works, _verify_results)
        vsum = verify_citations.summarize_results(_verify_results)
        vsum["total"] = len(works)
        vsum["mode"] = "background"
        vsum["skipped_preview"] = False
        _out("[OK] citation verification (background): %s"
             % json.dumps(vsum, ensure_ascii=False),
             "verify_done", mode="background", summary=vsum)
        primary_v = _finalize(works, vsum, suffix="_verified")
        _out("[OK] report verified -> %s" % primary_v,
             "report_verified", primary=primary_v or "")
        primary = primary_v or primary
    else:
        primary = _finalize(works, vsum, suffix="")

    _out("[OK] run finished: %s" % primary, "run_done", primary=primary or "")
    return primary


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
    # ---- P0: citation verification scope ----
    ap.add_argument("--verify", default="all", choices=["all", "top", "none", "background"],
                    help="citation verification scope (anti-hallucination, ct-base §17.1): "
                         "all = verify every work (default); top = verify only the top-N by "
                         "rank (fastest, good for large result sets); none = skip verification; "
                         "background = two-phase: emit an unverified report immediately, then "
                         "re-render with verification results when the background pass finishes. "
                         "All modes skip re-resolution of identifiers already trusted by provenance.")
    ap.add_argument("--verify-top-n", type=int, default=15,
                    help="N for --verify top (default 15): number of top-ranked works to verify")
    ap.add_argument("--no-verify-citations", action="store_true",
                    help="legacy alias for `--verify none` (disable citation verification). "
                         "⚠️ WARNING: disables the anti-hallucination gate (ct-base §17.1); use only for debugging or non-critical scoping.")
    ap.add_argument("--no-consistency", action="store_true",
                    help="skip the title/author consistency cross-check (identifier still "
                         "resolved, but not compared against the resolved paper's metadata). "
                         "⚠️ WARNING: weakens the anti-hallucination guarantee; debugging only.")
    # ---- F: literature-manager integration ----
    ap.add_argument("--obsidian", action="store_true",
                    help="export Obsidian notes (per-paper .md + MOC index, "
                         "internal [[links]]); writes <out-dir>/obsidian/")
    ap.add_argument("--zotero", action="store_true",
                    help="export Zotero-importable zotero.csv + zotero.ris into <out-dir>/")
    ap.add_argument("--lang", default="auto", choices=["auto", "zh", "en"],
                    help="UI language for xlsx / html / markdown / obsidian outputs. "
                         "auto = follow OS locale (zh in a Chinese locale, else en); "
                         "force zh or en to override.")
    ap.add_argument("--progress", default="human", choices=["human", "json"],
                    help="progress output mode: human (readable console, default) or "
                         "json (NDJSON event stream on stdout — run_start / source_done / "
                         "source_failed / fetch_done / verify_done / export_done; for agent use)")
    args = ap.parse_args()
    global _PROGRESS, _ORIG_STDOUT
    _PROGRESS = args.progress
    if args.progress == "json":
        # 子模块（fetch/report 等）的进度 print 全部转 stderr，stdout 只留 NDJSON 事件流
        _ORIG_STDOUT = sys.stdout
        sys.stdout = sys.stderr

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
        _out("[PREVIEW] would run literature pipeline: topic=%r review_type=%r safety=%s "
             "sources=[%s] (use --run)" % (args.topic, args.review_type, args.safety, srcs),
             "preview", topic=args.topic, review_type=args.review_type,
             safety=args.safety, sources=srcs)
        return
    run(args.topic, args.review_type, args.year_from, args.year_to, args.safety,
        args.max, args.with_europepmc, args.with_semantic_scholar,
        args.with_biorxiv, args.with_medrxiv, args.with_arxiv,
        with_prospero=args.with_prospero, prospero_token=args.prospero_token,
        prospero_header=args.prospero_header,
        verify_mode=("none" if args.no_verify_citations else args.verify),
        verify_top_n=args.verify_top_n,
        verify_consistency=not args.no_consistency,
        out_dir=args.out_dir,
        make_xlsx=not args.no_xlsx, make_html=not args.no_html,
        openalex_key=args.openalex_key, citation_style=args.citation_style,
        export_bib=args.export_bib, prisma=args.prisma, rank=args.rank,
        keywords=args.keywords, obsidian=args.obsidian, zotero=args.zotero,
        lang=args.lang)


if __name__ == "__main__":
    main()
