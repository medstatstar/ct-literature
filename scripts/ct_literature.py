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
from adapters.fetch_coze_unified import dispatch as coze_dispatch, DISPATCHABLE_SOURCES
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
from adapters import guideline_corpus  # G: curated LOCAL guideline corpus (build-time: build_guidelines.py)
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
# Export default = OFF: HTML + Excel are the standard deliverables; bib / ris /
# references_<style>.md are generated on demand (--export-bib or a chat request).
DEFAULT_EXPORT_BIB = False
DEFAULT_PRISMA = True
DEFAULT_RANK = "cited"  # keep legacy cited-by ordering unless --rank relevance


def _empty_payload(source_display: str) -> dict:
    """空结果 payload（本地格式：source=规范名, works=[]），Coze/离线双路径失败时返回，
    保证 normalize.merge 拿到统一结构、不因缺键报错。"""
    return {"source": source_display, "count": 0, "works": [], "total_count": 0}


def _coze_dispatch_with_fallback(source, keyword, year_from, year_to, max_results, offline, name):
    """Coze 统一检索 + 本地兜底。

    --offline 或 Coze 不可用时自动降级本地 fetch（返回格式已归一化为本地格式：
    {"source": 规范名, "works": [...], "count": N}）。
    中间调用 log_feishu=False（不记飞书），最终汇总由 run() 末尾单独记一条。
    """
    if offline:
        # 强制本地兜底
        result = coze_dispatch(source, keyword, year_from, year_to, max_results,
                               run=True, log_feishu=False, offline=True)
        if result and not result.get("error"):
            return result
        return result or _empty_payload(name)

    # 先尝试 Coze
    try:
        result = coze_dispatch(source, keyword, year_from, year_to, max_results,
                               run=True, log_feishu=False)
        if result and not result.get("error"):
            return result
        # Coze 返回 error → 降级
        _out(f"[WARN] {name} Coze 失败({result.get('error') if result else 'None'})，降级本地 fetch",
             "coze_fallback", source=name)
    except Exception as e:
        _out(f"[WARN] {name} Coze 异常: {e}，降级本地 fetch",
             "coze_fallback", source=name, error=str(e))

    # 本地兜底（失败时记飞书一条，暴露降级）
    result = coze_dispatch(source, keyword, year_from, year_to, max_results,
                           run=True, log_feishu=True, offline=True)
    return result or _empty_payload(name)


def run(topic, review_type="all", year_from=None, year_to=None, safety=False,
        max_results=50, with_europepmc=True, with_semantic_scholar=False,
        with_biorxiv=True, with_medrxiv=True, with_arxiv=False,
        with_prospero=False, prospero_token=None, prospero_header="PROSPERO-ACCESS-TOKEN",
        with_guidelines=False, guideline_sources=None, guideline_max=20,
        verify_mode="all", verify_top_n=15, verify_consistency=True,
        out_dir="./out", make_xlsx=True, make_html=True, openalex_key=None,
        citation_style=DEFAULT_CITATION_STYLE, export_bib=DEFAULT_EXPORT_BIB,
        prisma=DEFAULT_PRISMA, rank=DEFAULT_RANK, keywords=None,
        obsidian=False, zotero=False, lang="auto", cochrane=False,
        merge_existing=None, stamp_date=None, preprint_fallback=False,
        download_pdf=False, include_reviews=True, online=False, offline=False):
    """merge_existing: path to a PREVIOUS run's .merged.json (or a payload dict /
    list of records). When set, this run's works are unioned with that history and
    every record is stamped first_seen / last_seen (living review / surveillance).
    Read from disk only — no network. Default None => behaviour unchanged.
    download_pdf: 是否在检索完成后进入 PDF 批量下载流程（opt-in）。
    online: 使用 Coze 端统一检索（6 个文献源走 Coze 服务端），中间调用不记飞书。
    offline: 强制本地兜底（不调 Coze），与老版本行为完全一致。"""
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
    # Semantic Scholar key 提示（无条件触发，与是否启用该源无关——即使默认关闭，
    # 也应在首次使用/未配置时告知申请路径、不外发承诺与提速收益）
    http_utils.notify_s2_key_if_missing()
    oa_json = os.path.join(out_dir, "openalex.json")
    epmc_json = os.path.join(out_dir, "europepmc.json")
    s2_json = os.path.join(out_dir, "semantic_scholar.json")
    biorxiv_json = os.path.join(out_dir, "biorxiv.json")
    medrxiv_json = os.path.join(out_dir, "medrxiv.json")
    arxiv_json = os.path.join(out_dir, "arxiv.json")
    prospero_json = os.path.join(out_dir, "prospero.json")
    merged_json = os.path.join(out_dir, ".merged.json")

    # ---- fetch all enabled sources in PARALLEL (per-source concurrency) ----
    # Each source is independent; running them concurrently turns summed per-source
    # latency into the latency of the SLOWEST source.
    #
    # --online 模式：6 个文献源走 Coze 服务端（中间调用 log_feishu=False），
    #   Coze 不可用时自动降级本地 fetch（与老版本行为一致）。
    # --offline 模式：强制本地兜底（不调 Coze）。
    # 默认（无 --online/--offline）：保持老版本行为（本地 fetch），100% 向后兼容。
    jobs = []
    if online:
        # Coze 统一检索：6 个文献源走服务端，中间调用不记飞书
        _coze_sources = [
            ("OpenAlex", "openalex"),
            ("EuropePMC", "europepmc"),
            ("bioRxiv", "biorxiv"),
            ("medRxiv", "medrxiv"),
            ("SemanticScholar", "semantic_scholar"),
            ("arXiv", "arxiv"),
        ]
        for _name, _src in _coze_sources:
            if _src == "europepmc" and not with_europepmc:
                continue
            if _src == "semantic_scholar" and not with_semantic_scholar:
                continue
            if _src == "biorxiv" and not with_biorxiv:
                continue
            if _src == "medrxiv" and not with_medrxiv:
                continue
            if _src == "arxiv" and not with_arxiv:
                continue
            # 闭包捕获 _src/_name
            jobs.append((_name, lambda s=_src, n=_name: _coze_dispatch_with_fallback(
                s, topic, year_from, year_to, max_results, offline, n)))
        # PROSPERO 不走 Coze（独立 token-gated），保持本地调用
        if with_prospero:
            jobs.append(("PROSPERO", lambda: fetch_prospero.fetch(
                topic, review_type, year_from, year_to, safety, max_results,
                run=True, out=prospero_json, token=prospero_token, header_name=prospero_header)))
    else:
        # 老版本行为（本地 fetch），100% 向后兼容
        jobs.append(("OpenAlex", lambda: fetch_openalex.fetch(
            topic, review_type, year_from, year_to, safety, max_results,
            run=True, out=oa_json, api_key=openalex_key,
            include_reviews=include_reviews)))
        if with_europepmc:
            jobs.append(("EuropePMC", lambda: fetch_europepmc.fetch(
                topic, review_type, year_from, year_to, safety, max_results,
                run=True, out=epmc_json, cochrane=cochrane,
                include_reviews=include_reviews)))
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
    # In `top` mode we verify after ranking (only the top-N).
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

    works, dedup_stats = normalize.merge_with_stats(payloads)

    # ---- cross-run incremental merge (living review / surveillance) ----
    # Opt-in via --merge-existing: union this run's works with a PREVIOUS run's local
    # .merged.json and stamp first_seen / last_seen. Pure local file read. When
    # merge_existing is None this block is a no-op and the pipeline is byte-identical
    # to before. Runs BEFORE the Cochrane filter so retained records are filtered too.
    merge_stats = None
    if merge_existing:
        works, merge_stats = normalize.merge_with_history(
            works, merge_existing, today=stamp_date)
        _out("[merge-existing] +%d new / %d carryover / %d retained-from-history "
             "= %d works (stamp %s)"
             % (merge_stats["new"], merge_stats["carryover"],
                merge_stats["retained_only"], merge_stats["total"],
                merge_stats["stamp"]),
             "merge_existing", **merge_stats)

    # ---- preprint candidates for non-OA works (opt-in via --preprint-fallback) ----
    # For works with no OA full text (is_oa false / open_access_url empty), search
    # bioRxiv / medRxiv (Europe PMC PPR) + arXiv by title and attach an author-verified
    # candidate to work["preprint"] (ported from meta-analysis pdf_fetch: "prefer
    # missing over wrong" — any author-check failure drops the candidate).
    preprint_stats = None
    if preprint_fallback:
        from adapters import preprint_fallback as _pf
        preprint_stats = _pf.enrich(works, progress=lambda m: _out(m, "preprint"))
        _out("[preprint-fallback] scanned=%d candidates=%d rejected=%d no-authors=%d "
             "servers=%s" % (preprint_stats["scanned"], preprint_stats["candidates"],
                             preprint_stats["rejected"], preprint_stats["skipped_no_authors"],
                             ",".join(preprint_stats["servers"])),
             "preprint_fallback", **preprint_stats)

    # Full API total for the Cochrane journal-filtered Europe PMC query — captured
    # from the fetcher's `hit_count` (independent of --max), so it reports the true
    # Cochrane count rather than just the capped sample we fetched for reading.
    _epmc_payload = next((p for p in payloads if p.get("source") == "EuropePMC"), None)
    _epmc_hit = (_epmc_payload or {}).get("hit_count")

    # ---- Cochrane-only focus (--cochrane): keep only works whose publication is
    # the Cochrane Database of Systematic Reviews. The Europe PMC leg is already
    # journal-filtered; this also drops any non-Cochrane OpenAlex/other hits so
    # the merged set is a clean Cochrane set. Uses the unified `publication`
    # field (present in every source's normalized record). ----
    if cochrane:
        _before = len(works)
        works = [w for w in works
                 if "cochrane" in (w.get("publication") or "").lower()]
        cochrane_count = len(works)          # sample kept for reading / reporting
        cochrane_total = _epmc_hit           # full API total (independent of --max)
        _out("[cochrane] kept %d Cochrane work(s) from %d merged; "
             "full Cochrane total (Europe PMC) = %s"
             % (len(works), _before, cochrane_total), "cochrane_filter",
             kept=len(works), total=_before, full_total=cochrane_total)
    else:
        cochrane_count = None
        cochrane_total = None

    # ---- P0-C: relevance scoring (annotates merged works, incremental) ----
    works = score_relevance.score_works(works, topic=topic, keywords=keywords)

    # ---- P0-B: deterministic PRISMA title/abstract screen (no LLM) ----
    prisma_block = None
    if prisma:
        sp = screen_prisma.screen(works, topic=topic, review_type=review_type,
                                  safety=safety,
                                  duplicates_removed=dedup_stats["duplicates_removed"])
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
    else:  # verify_mode == "background" — handled by the two-phase block below
        pass

    # ---- G: curated LOCAL guideline corpus (build-time populated by build_guidelines.py) ----
    # Independent of the literature works: kept OUT of normalize.merge so it does not
    # pollute citation verification / PRISMA. Reads a PINNED local corpus (references/
    # guidelines/guidelines_index.json) — ZERO network at analysis time. Emitted as
    # guidelines.json + a `guidelines` block in the merged state. To refresh/extend the
    # corpus, the author runs: python adapters/build_guidelines.py --topic <topic> --run
    guidelines_payload = None
    if with_guidelines:
        try:
            _gl_json = os.path.join(out_dir, "guidelines.json")
            guidelines_payload = guideline_corpus.load(
                _topic_zh, review_type=review_type,
                sources=(guideline_sources.strip() if guideline_sources else None),
                max_results=guideline_max, out=_gl_json)
            if guidelines_payload.get("corpus_missing"):
                _out("[WARN] guideline corpus not built yet — run build_guidelines.py first",
                     "guidelines_missing",
                     note="python adapters/build_guidelines.py --topic %s --run" % _topic_zh)
            else:
                _out("[OK] guideline corpus loaded: %d records"
                     % guidelines_payload.get("count", 0),
                     "guidelines_done", count=guidelines_payload.get("count", 0),
                     source_status=guidelines_payload.get("source_status", {}))
        except Exception as _ge:
            _out("[WARN] guideline corpus load failed: %s" % _ge, "guidelines_failed",
                 error=str(_ge))

    # ---- build meta / evidence / exports (shared by all verify modes) ----
    def _finalize(works, vsum, suffix="", guidelines=None):
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
                "cochrane": cochrane,
                "cochrane_count": cochrane_count,
                "cochrane_total": cochrane_total,
                "source_notes": source_notes,
                "merge_existing": merge_stats}   # living-review delta (None when off)
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
        if guidelines is not None:
            out_data["guidelines"] = guidelines
            meta["guidelines"] = {
                "count": guidelines.get("count", 0),
                "total_sources": guidelines.get("total_sources"),
                "api_sources": guidelines.get("api_sources"),
                "portal_sources": guidelines.get("portal_sources"),
                "source_status": guidelines.get("source_status", {}),
            }
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
                    xlsx_out, lang=lang, safety=safety)
                _out("[OK] xlsx  -> %s" % xlsx_out, "export_done", kind="xlsx",
                     path=xlsx_out, **_ver)
                primary = primary or xlsx_out
            except Exception as _xe:
                _out("[WARN] xlsx export failed: %s" % _xe,
                     "export_failed", kind="xlsx", error=str(_xe), **_ver)
        if make_html:
            html_out = os.path.join(out_dir, "lit_report.html")
            try:
                html_text = export_html.render(out_data, lang, safety=safety)
                with open(html_out, "w", encoding="utf-8") as f:
                    f.write(html_text)
                _out("[OK] html  -> %s" % html_out, "export_done", kind="html",
                     path=html_out, **_ver)
                primary = html_out
            except Exception as _he:
                _out("[WARN] html export failed: %s" % _he,
                     "export_failed", kind="html", error=str(_he), **_ver)
        # end-user guidance on optional add-ons (surfaced to the chat after the run)
        _out("[TIP] Excel 报告是完整结果，可在此基础上继续筛选 / 透视等进一步处理。", "tip", **_ver)
        if not export_bib:
            _out("[TIP] 如需 Zotero(RIS) / BibTeX / APA 等引文格式下载、或协助对 OA 文献下载 PDF，告诉我即可按需生成（也可用 --export-bib / --download-pdf）。附加功能不清楚时，对话中输入「菜单」让我列选。", "tip", **_ver)
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
        primary = _finalize(works, vsum_bg, suffix="", guidelines=guidelines_payload)
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
        primary_v = _finalize(works, vsum, suffix="_verified", guidelines=guidelines_payload)
        _out("[OK] report verified -> %s" % primary_v,
             "report_verified", primary=primary_v or "")
        primary = primary_v or primary
    else:
        primary = _finalize(works, vsum, suffix="", guidelines=guidelines_payload)

    # ---- PDF 批量下载（opt-in via --download-pdf）----
    if download_pdf:
        try:
            from adapters.pdf_download import PdfDownloader
            pdf_dir = os.path.join(out_dir, "pdfs")
            dl = PdfDownloader(out_dir=pdf_dir, progress=lambda m: _out(m, "pdf_download"))
            _out(f"[PDF] 开始批量下载 {len(works)} 篇文献的 PDF：每篇约需 10–20 秒"
                 f"（视网络与限流而定），请耐心等待完成，无需任何操作。")
            pdf_stats = dl.run(works)
            if pdf_stats.get("rejected"):
                # 总量超上限被拒：提示缩小范围（用户 2026-09-06：>50 直接拒绝避免超时）
                _out(f"[PDF] 拒绝下载 (elapsed {pdf_stats.get('elapsed_s', 0)}s): "
                     f"{pdf_stats.get('rejected_reason', '')}",
                     "pdf_download_rejected", reason=pdf_stats.get("rejected_reason", ""))
            else:
                # 耗时统计反馈（用户 2026-09-07：每次 PDF 下载都要报用时）
                _ok, _tot = pdf_stats.get("ok", 0), pdf_stats.get("total", 0)
                # 下载完成后把 PDF 本地路径回写进 Excel（用户 2026-09-07）：
                # run() 已把 local_pdf_path / pdf_download_note 写到内存 works 上，
                # 用同一渲染函数重渲 lit_report.xlsx ——「PDF 本地路径」列（导出器
                # _WORKS_COLS 早已预留）即真实呈现；不用 openpyxl 改存以免丢图表。
                _xlsx_updated = ""
                if make_xlsx:
                    try:
                        with open(merged_json, encoding="utf-8") as _f:
                            _meta = (json.load(_f) or {}).get("meta") or {}
                        # PdfDownloader 落盘路径可能相对 out_dir → 统一绝对路径再写入
                        for _w in works:
                            if _w.get("local_pdf_path"):
                                _w["local_pdf_path"] = os.path.abspath(_w["local_pdf_path"])
                        export_xlsx.export_workbook(
                            {"count": len(works), "works": works, "meta": _meta},
                            os.path.join(out_dir, "lit_report.xlsx"),
                            lang=lang, safety=safety)
                        _xlsx_updated = os.path.join(out_dir, "lit_report.xlsx")
                        _out("[OK] xlsx 已更新：PDF 本地路径已写入报告 -> %s"
                             % _xlsx_updated, "xlsx_updated",
                             path=_xlsx_updated, kind="xlsx_pdf_paths")
                    except Exception as _xe:
                        _out("[WARN] xlsx 回写 PDF 路径失败（不影响已下载的 PDF）: %s"
                             % _xe, "pdf_xlsx_update_failed", error=str(_xe))
                # 用户可读反馈：不倾倒技术性 JSON（stats 细节仅经 json 事件透传）
                _el = pdf_stats.get("elapsed_s")
                _base = f"[PDF] 下载完成: {_ok}/{_tot} 篇成功"
                if _el is not None:
                    _base += f"，用时 {_el}s（{pdf_stats.get('elapsed_min', 0)} 分钟）"
                if _xlsx_updated:
                    _out(f"{_base}。PDF 已保存至 {pdf_dir}，Excel 报告已更新「PDF 本地路径」列。",
                         "pdf_download_done", **pdf_stats)
                elif _ok > 0:
                    _out(f"{_base}。PDF 已保存至 {pdf_dir}。",
                         "pdf_download_done", **pdf_stats)
                else:
                    _out(f"{_base}。未下载到可用 PDF（多为付费墙 / 无 OA 直链）。",
                         "pdf_download_done", **pdf_stats)
        except Exception as e:
            _out(f"[PDF] 批量下载失败: {type(e).__name__}: {e}", "pdf_download_failed", error=str(e))

    if online:
        # 最终汇总记一条飞书（log_feishu=True）：统计信息经 querystr 透传，
        # Coze 端飞书节点原样落 querystr 列，供审计追踪整次多源检索的汇总。
        try:
            _summary_payload = {
                "type": "literature_summary",
                "topic": _topic_zh,
                "query": topic,
                "sources_ok": len([p for p in payloads if p and not p.get("error")]),
                "sources_fail": len([p for p in payloads if p and p.get("error")]),
                "hits_merged": len(works),
            }
            coze_dispatch("openalex", topic, year_from, year_to, max_results,
                          run=True, log_feishu=True,
                          querystr=json.dumps(_summary_payload, ensure_ascii=False),
                          skillname="literature")
            _out("[OK] 飞书汇总已记录 (log_feishu=True)", "feishu_summary")
        except Exception as e:
            _out(f"[WARN] 飞书汇总记录失败（不影响主流程）: {e}", "feishu_summary_failed", error=str(e))

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
    ap.add_argument("--max", type=int, default=50, help="max works per source")
    ap.add_argument("--with-europepmc", action=argparse.BooleanOptionalAction, default=True,
                    help="search Europe PMC (MEDLINE/MeSH, biomedical precision); default ON; "
                         "use --no-with-europepmc to disable")
    ap.add_argument("--with-semantic-scholar", action="store_true",
                    help="(low-priority supplementary source) search via Semantic Scholar "
                         "(citation-ranked); its API key requires a manual form review and is "
                         "not auto-issued, so it auto-skips when absent and never affects the "
                         "OpenAlex / Europe PMC primary output")
    ap.add_argument("--with-biorxiv", action=argparse.BooleanOptionalAction, default=True,
                    help="include bioRxiv preprints (biomedical preprints, via Europe PMC PPR index); "
                         "default ON; use --no-with-biorxiv to disable")
    ap.add_argument("--with-medrxiv", action=argparse.BooleanOptionalAction, default=True,
                    help="include medRxiv preprints (medical/clinical preprints, via Europe PMC PPR index); "
                         "default ON; use --no-with-medrxiv to disable")
    ap.add_argument("--with-arxiv", action="store_true",
                    help="include arXiv (physics/CS/ML methodology breadth; opt-in supplementary)")
    ap.add_argument("--preprint-fallback", action="store_true",
                    help="for non-OA works, look up bioRxiv/medRxiv/arXiv preprint "
                         "candidates (title search + author-surname verification, "
                         "'prefer missing over wrong'); attaches work['preprint'] "
                         "shown in the XLSX/HTML 'Preprint candidate' column")
    ap.add_argument("--cochrane", action="store_true",
                    help="(focus) restrict the Europe PMC leg to the Cochrane Database of "
                         "Systematic Reviews via a verified journal filter, then keep only "
                         "Cochrane works after merge — a clean Cochrane-only retrieval. "
                         "Pairs with meta-analysis's in-skill dedup probe (same filter string).")
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
    # ---- G: curated LOCAL guideline corpus (build-time populated by build_guidelines.py) ----
    ap.add_argument("--with-guidelines", action=argparse.BooleanOptionalAction,
                    default=False,
                    help="(G) load the CURATED LOCAL guideline corpus (references/guidelines/"
                         "guidelines_index.json) — ZERO network at analysis time. The corpus is "
                         "built/refreshed by the author via: python adapters/build_guidelines.py "
                         "--topic <topic> --run. Emits guidelines.json + a `guidelines` block in "
                         ".merged.json. Opt-in (use --no-with-guidelines to disable).")
    ap.add_argument("--guideline-sources", default=None,
                    help="comma-separated subset of guideline sources (default: all 12+)")
    ap.add_argument("--guideline-max", type=int, default=20,
                    help="max records per live api source (default 20)")
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
                    help="export references.bib / references.ris / references_<style>.md "
                         "(default: off — HTML + Excel are the standard deliverables; "
                         "enable for Zotero RIS / BibTeX / APA downloads)")
    ap.add_argument("--prisma", action=argparse.BooleanOptionalAction,
                    default=DEFAULT_PRISMA,
                    help="run deterministic PRISMA title/abstract screen + funnel "
                         "(default: on; use --no-prisma to disable)")
    ap.add_argument("--rank", default=DEFAULT_RANK, choices=["cited", "relevance"],
                    help="order works by cited_by_count (default) or relevance_score")
    ap.add_argument("--keywords", default=None,
                    help="comma-separated extra keywords for relevance scoring")
    # ---- P0: citation verification scope (anti-hallucination, ct-base §17.1) ----
    # NOTE: `none` was removed on purpose — the verification gate is a hard P0 control and
    # must never be fully disabled from the CLI. Lowest selectable scope is `top`.
    ap.add_argument("--verify", default="all", choices=["all", "top", "background"],
                    help="citation verification scope (anti-hallucination, ct-base §17.1 — "
                         "cannot be fully disabled): all = verify every work (default); "
                         "top = verify only the top-N by rank (fastest, good for large result "
                         "sets); background = two-phase: emit an unverified report immediately, "
                         "then re-render with verification results when the background pass "
                         "finishes. All modes skip re-resolution of identifiers already trusted "
                         "by provenance.")
    ap.add_argument("--verify-top-n", type=int, default=15,
                    help="N for --verify top (default 15): how many top-ranked works get the "
                         "full check. This does NOT disable verification — it only sizes the "
                         "top-N sample under --verify top; identifier resolution still runs.")
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
    # ---- G: cross-run incremental merge (living review / surveillance) ----
    ap.add_argument("--merge-existing", default=None, metavar="MERGED_JSON",
                    help="(living review) path to a PREVIOUS run's .merged.json: this "
                         "run's works are UNIONed with that history and every record is "
                         "stamped first_seen / last_seen. Records seen before keep their "
                         "earliest first_seen and get a refreshed last_seen; records only "
                         "in history are retained (last_seen NOT refreshed, "
                         "seen_this_run=false) so the evidence base can only grow. "
                         "Reads the local file only — ZERO network. Off by default.")
    ap.add_argument("--stamp-date", default=None, metavar="YYYY-MM-DD",
                    help="date stamp for --merge-existing first_seen / last_seen "
                         "(default: today). Useful for backfilling a historical run.")
    ap.add_argument("--download-pdf", action="store_true",
                    help="(opt-in) 检索完成后进入 PDF 批量下载流程：OA 直链/预印本直接下载，"
                         "其余经 coze 批量下载节点处理（直下探测→浏览器+S3，支持二次重试）")
    ap.add_argument("--include-reviews", action=argparse.BooleanOptionalAction,
                    default=True,
                    help="include review-type publications in results (default: on; "
                         "use --no-include-reviews to exclude at the source and save quota)")
    ap.add_argument("--online", action="store_true",
                    help="(opt-in) 使用 Coze 端统一检索（6 个文献源走 Coze 服务端），"
                         "中间调用不记飞书、最终汇总记一条；Coze 不可用时自动降级本地 fetch")
    ap.add_argument("--offline", action="store_true",
                    help="(opt-in) 强制本地兜底（不调 Coze），与老版本行为完全一致")
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
        if args.cochrane:
            extra.append("Cochrane(EPMC journal filter)")
        if args.with_guidelines:
            extra.append("Guidelines(12+)")
        if args.merge_existing:
            extra.append("merge-existing(%s)" % args.merge_existing)
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
        with_guidelines=args.with_guidelines,
        guideline_sources=args.guideline_sources,
        guideline_max=args.guideline_max,
        verify_mode=args.verify,
        verify_top_n=args.verify_top_n,
        verify_consistency=not args.no_consistency,
        out_dir=args.out_dir,
        make_xlsx=not args.no_xlsx, make_html=not args.no_html,
        openalex_key=args.openalex_key, citation_style=args.citation_style,
        export_bib=args.export_bib, prisma=args.prisma, rank=args.rank,
        keywords=args.keywords, obsidian=args.obsidian, zotero=args.zotero,
        lang=args.lang, cochrane=args.cochrane,
        merge_existing=args.merge_existing, stamp_date=args.stamp_date,
        preprint_fallback=args.preprint_fallback,
        download_pdf=args.download_pdf,
        include_reviews=args.include_reviews,
        online=args.online, offline=args.offline)


if __name__ == "__main__":
    main()
