#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
normalize.py — multi-source literature normalization & merge.

Merges OpenAlex + Europe PMC + Semantic Scholar payloads into one unified, de-duplicated
work list. Dedupe key: DOI (preferred) else normalized title. Each merged record keeps a
`sources` list so the report can show provenance. Pure local computation, no network.

Cross-run (living review) layer — `merge_with_history()` unions the current run's works
with a PREVIOUS run's local JSON, stamping `first_seen` / `last_seen` on every record.
Also pure local: the history file is read from disk only, never fetched.
"""
import argparse
import datetime
import json
import re
from difflib import SequenceMatcher

# Source priority (lower = higher priority).
# OpenAlex / EuropePMC / bioRxiv / medRxiv are primary biomedical sources (rank 0);
# SemanticScholar and arXiv are low-priority supplementary sources (rank 1) — S2's key
# requires a manual form review and is often absent, and arXiv is mostly methodology
# breadth rather than core trial/safety evidence.
_SOURCE_PRIORITY = {
    "OpenAlex": 0, "EuropePMC": 0, "bioRxiv": 0, "medRxiv": 0,
    "SemanticScholar": 1, "arXiv": 1,
}

# 小写 source → 规范显示名（Coze 端节点统一输出小写，本地 fetch_* 输出大写；
# merge 时一律归一为规范名，保证 EuropePMC 优先覆盖逻辑与 Excel 分组不被大小写撕裂）
_SOURCE_CANON = {
    "openalex": "OpenAlex",
    "europepmc": "EuropePMC",
    "biorxiv": "bioRxiv",
    "medrxiv": "medRxiv",
    "semantic_scholar": "SemanticScholar",
    "arxiv": "arXiv",
}


def _canon_source(s):
    """source 归一为规范显示名（大小写不敏感；未知源原样返回）。"""
    if not s:
        return s
    return _SOURCE_CANON.get(str(s).strip().lower(), s)


def _norm_title(t):
    if not t:
        return ""
    t = t.lower()
    t = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", t)
    return " ".join(t.split())


def _bare_doi(v):
    """DOI 字段兜底归一：剥掉 https://doi.org/ 等 URL 前缀 → 裸 DOI。
    2026-09-06 实测：OpenAlex 等源的 doi 字段为完整 URL，若不归一，下游
    coze/EPMC `DOI:"https://…"` 查询与 BibTeX/RIS 导出全部失真。"""
    if not v:
        return v
    s = str(v).strip()
    low = s.lower()
    for p in ("https://doi.org/", "http://doi.org/",
              "https://dx.doi.org/", "http://dx.doi.org/"):
        if low.startswith(p):
            return s[len(p):]
    return s


def _norm_doi(d):
    if not d:
        return None
    d = _bare_doi(d).strip().lower()
    m = re.search(r"10\.\d{4,9}/[^\s]+", d)
    if not m:
        return d
    # strip a trailing terminal punctuation a source may have appended to the DOI
    # (e.g. "10.1056/NEJMoa2403614.") so the bare DOI resolves / links cleanly.
    return m.group(0).rstrip(".,;:)]")


def _dedupe_preprint_published(works, title_threshold=0.85, author_threshold=0.3):
    """检测预印本-发表版配对，保留发表版（策略 A）。

    一篇预印本（type=preprint）若在结果集中存在正式发表版本（type!=preprint），
    且归一化标题相似度 >= title_threshold、第一作者重叠 >= author_threshold，
    则视为同一研究。此时：
      - 预印本记录被移除（superseded）。
      - 发表版记录回填 preprint_doi（预印本 DOI）并加 has_preprint=True。

    参数：
      title_threshold: 归一化标题相似度阈值（0-1），默认 0.85。
      author_threshold: 第一作者重叠比例阈值（0-1），默认 0.3（≥1/3 作者相同）。

    注意：仅在同一函数调用内配对，不引入外部 API（CrossRef/OpenAlex relation）；
    对标题改动大或作者群大幅变动的发表版可能漏匹配，此时两版均保留。
    """
    preprints = [w for w in works if w.get("type") == "preprint"]
    if not preprints:
        return works

    superseded_dois = set()
    for p in preprints:
        pt = _norm_title(p.get("title"))
        if not pt:
            continue
        pa = [a.strip() for a in (p.get("authors") or []) if a and a.strip()]
        pa_set = set(a.lower() for a in pa)
        for w in works:
            if w.get("type") == "preprint":
                continue
            jt = _norm_title(w.get("title"))
            if not jt:
                continue
            sim = SequenceMatcher(None, pt, jt).ratio()
            if sim < title_threshold:
                continue
            ja = [a.strip() for a in (w.get("authors") or []) if a and a.strip()]
            ja_set = set(a.lower() for a in ja)
            overlap = len(pa_set & ja_set) / max(len(pa_set), 1)
            if overlap < author_threshold:
                continue
            # 配对成功 → 保留发表版 w，移除预印本 p
            if not w.get("preprint_doi"):
                w["preprint_doi"] = p.get("doi")
            w["has_preprint"] = True
            # 发表版缺失的字段从预印本回填
            for fld in ("abstract_snippet", "mesh", "keywords"):
                if not w.get(fld) and p.get(fld):
                    w[fld] = p.get(fld)
            superseded_dois.add(p.get("doi"))
            break  # 一个预印本只配对一个发表版

    if superseded_dois:
        works = [w for w in works if w.get("doi") not in superseded_dois]
    return works


# ── abstract placeholder detection ───────────────────────────────────────────
_ABSTRACT_PLACEHOLDERS = {
    "how to cite", "how to cite.", "[abstract unavailable]",
    "abstract not available", "no abstract available", "[no abstract]",
    "abstract:", "summary:", "abstract available", "unavailable",
    "abstract not provided", "not available", "n/a"
}

def _is_valid_abstract(text):
    """Check if abstract text is valid (not a placeholder or too short).
    OpenAlex and Europe PMC sometimes return placeholder strings like
    "How to cite" or empty abstracts for guidelines / editorials."""
    if not text:
        return False
    s = text.strip()
    if len(s) < 20:
        return False
    if s.lower() in _ABSTRACT_PLACEHOLDERS:
        return False
    return True


# Europe PMC 优先字段：这些字段在 Europe PMC 命中时更可靠（直链 PDF、PMID 等），
# 即使先命中 OpenAlex，后命中 Europe PMC 也应覆盖。
_EUROPE_PMC_PREFERRED = {
    "open_access_url", "pmid", "pmcid", "abstract_snippet", "mesh",
    "journal_iso", "publication", "authors", "publication_date",
    "volume", "issue", "page"
}

def _evidence_level(w):
    """Assign an evidence-level tag based on study_type / type.
    U4 (tooluniverse-drug-research inspired): every work gets an explicit
    evidence grade so reports can show the evidence pyramid at a glance."""
    st = (w.get("study_type") or "").lower()
    if st in ("systematic-review", "meta-analysis", "scoping-review"):
        return "systematic-review"
    if st == "rct":
        return "rct"
    if st == "cohort":
        return "cohort"
    if st == "case-report":
        return "case-report"
    if st == "case-series":
        return "case-series"
    if st == "preprint" or (w.get("type") or "").lower() == "preprint":
        return "preprint"
    if st == "review":
        return "narrative-review"
    return "other"


def merge(payloads):
    """payloads: list of {source, query, works:[...]} dicts (or None).

    兼容 Coze 端返回的 ``projects`` 键：若 payload 含 ``projects`` 但缺 ``works``，
    自动重命名后参与合并（本地 fetch 仍用 ``works``，Coze 端统一用 ``projects``）。
    """
    # 按源优先级重排 payload：Europe PMC 优先于 OpenAlex，确保其字段覆盖 OpenAlex
    source_order = {"EuropePMC": 0, "OpenAlex": 1, "bioRxiv": 0, "medRxiv": 0, "SemanticScholar": 2,
                    "openalex": 1, "europepmc": 0, "biorxiv": 0, "medrxiv": 0, "semantic_scholar": 2, "arxiv": 1}
    payloads = sorted(
        [p for p in payloads if p],
        key=lambda p: source_order.get(p.get("source", ""), 1)
    )

    by_key = {}
    order = []

    for p in payloads:
        # 兼容 Coze 端返回格式（projects → works）
        if "works" not in p and "projects" in p:
            p["works"] = p.pop("projects")
        for w in p.get("works", []):
            # 就地归一 DOI（剥 URL 前缀）：fetch 端已各源修复，此处兜底历史/混合源
            if w.get("doi"):
                w["doi"] = _bare_doi(w["doi"])
            # source 大小写归一（Coze 端小写 → 规范显示名；保证 EuropePMC 优先覆盖与分组稳定）
            if w.get("source"):
                w["source"] = _canon_source(w["source"])
            doi = _norm_doi(w.get("doi"))
            title = _norm_title(w.get("title"))
            key = doi or ("t:" + title)
            if not key or key == "t:":
                continue
            if key in by_key:
                rec = by_key[key]
                src = w["source"]
                if src not in rec["sources"]:
                    rec["sources"].append(src)
                # 字段合并策略：
                # - Europe PMC 优先字段：Europe PMC 的值覆盖已有值
                # - 其余字段："有则不覆盖"（保留先命中的）
                for fld in ("abstract_snippet", "mesh", "concepts", "keywords", "funders",
                            "publication", "year", "publication_date", "volume", "issue", "page",
                            "authors", "affiliations", "pmid", "pmcid",
                            "open_access_url", "journal_iso", "language", "oa_status"):
                    cur = rec.get(fld)
                    new = w.get(fld)
                    if not new:
                        continue
                    if fld in _EUROPE_PMC_PREFERRED and src == "EuropePMC":
                        # Europe PMC 优先字段：Europe PMC 有值就覆盖
                        rec[fld] = new
                    elif not cur:
                        # 非优先字段：只有当前值缺失时才填入
                        rec[fld] = new
                # pub_types: publisher self-labels (e.g. ["Review"], ["Systematic Review"]).
                # Union-merge so a review tagged in ANY source is preserved through merge.
                if w.get("pub_types"):
                    rec_types = list(rec.get("pub_types") or [])
                    for t in w["pub_types"]:
                        if t not in rec_types:
                            rec_types.append(t)
                    rec["pub_types"] = rec_types
                # is_oa: OR semantics — any source saying the work is OA wins
                if w.get("is_oa") and not rec.get("is_oa"):
                    rec["is_oa"] = True
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
                # U4: recompute evidence_level after study_type merge
                rec["evidence_level"] = _evidence_level(rec)
            else:
                w["sources"] = [w["source"]]
                # U4: attach evidence level to every record at birth
                if "evidence_level" not in w:
                    w["evidence_level"] = _evidence_level(w)
                by_key[key] = w
                order.append(key)

    works = [by_key[k] for k in order]
    works = _dedupe_preprint_published(works)
    # Source-priority demotion: pure SemanticScholar works sink to the bottom;
    # OpenAlex / EuropePMC and multi-source hits rank first.
    # Within the same priority, still sort by citation count descending.
    def _src_rank(w):
        srcs = w.get("sources") or [w.get("source")]
        return min(_SOURCE_PRIORITY.get(s, 1) for s in srcs)

    works.sort(key=lambda x: (_src_rank(x), -(x.get("cited_by_count") or 0)))
    return works


def merge_with_stats(payloads):
    """Like merge() but also returns de-duplication statistics.

    Returns ``(works, stats)`` where ``stats`` records how many records were
    collapsed during cross-source / intra-source de-duplication:

        stats = {
            "raw_count":          # works carrying a usable key (DOI or title)
            "duplicates_removed": # raw_count - len(works)
        }

    This feeds PRISMA 2020's "Records removed before screening: duplicates
    removed (n = …)" box. ``merge()`` remains a thin wrapper so existing callers
    are unaffected.
    """
    raw_valid = 0
    for p in payloads:
        if not p:
            continue
        # 兼容 Coze 端返回格式（projects → works）
        if "works" not in p and "projects" in p:
            p["works"] = p.pop("projects")
        for w in p.get("works", []):
            # 就地归一 DOI（剥 URL 前缀）：fetch 端已各源修复，此处兜底历史/混合源
            if w.get("doi"):
                w["doi"] = _bare_doi(w["doi"])
            # source 大小写归一（Coze 端小写 → 规范显示名；保证 EuropePMC 优先覆盖与分组稳定）
            if w.get("source"):
                w["source"] = _canon_source(w["source"])
            doi = _norm_doi(w.get("doi"))
            title = _norm_title(w.get("title"))
            key = doi or ("t:" + title)
            if key and key != "t:":
                raw_valid += 1
    works = merge(payloads)
    return works, {
        "raw_count": raw_valid,
        "duplicates_removed": raw_valid - len(works),
    }


# ── cross-run / living-review layer ────────────────────────────────────────────
# Fields copied from a historical record into a current record ONLY when the current
# record has no value (same "enrich, never overwrite" rule as merge()). `sources` is
# deliberately EXCLUDED: the historical source names belong to a previous run and would
# pollute this run's "By Source" distribution in the report.
_BACKFILL_FIELDS = ("abstract_snippet", "mesh", "funders", "publication", "year",
                    "publication_date", "volume", "issue", "page", "authors",
                    "affiliations", "pmid", "pmcid", "open_access_url",
                    "journal_iso", "language", "oa_status", "preprint", "pub_types")


def dedupe_key(w):
    """Public helper: the same key merge() uses (DOI else normalized title)."""
    if not isinstance(w, dict):
        return None
    doi = _norm_doi(w.get("doi"))
    title = _norm_title(w.get("title"))
    key = doi or ("t:" + title)
    if not key or key == "t:":
        return None
    return key


def _backfill(rec, other):
    """Fill empty fields on `rec` from `other`; append-union concepts/keywords."""
    if not other:
        return rec
    for fld in _BACKFILL_FIELDS:
        if not rec.get(fld) and other.get(fld):
            rec[fld] = other[fld]
    for fld in ("concepts", "keywords"):
        extra = other.get(fld) or []
        if not extra:
            continue
        cur = list(rec.get(fld) or [])
        for x in extra:
            if x not in cur:
                cur.append(x)
        rec[fld] = cur
    return rec


def _min_date(a, b):
    vals = [x for x in (a, b) if x]
    return min(vals) if vals else None


def _max_date(a, b):
    vals = [x for x in (a, b) if x]
    return max(vals) if vals else None


def history_works(history):
    """Accept a path / dict payload / list of records -> list of work dicts.

    Pure local: a path is read from disk. Unreadable input degrades to [] with a
    warning instead of aborting the pipeline.
    """
    if not history:
        return []
    if isinstance(history, list):
        return [w for w in history if isinstance(w, dict)]
    if isinstance(history, dict):
        return [w for w in (history.get("works") or []) if isinstance(w, dict)]
    try:
        with open(history, encoding="utf-8") as f:
            return history_works(json.load(f))
    except Exception as e:
        print("[WARN] cannot read --merge-existing %s: %s" % (history, e))
        return []


def merge_with_history(works, history, today=None, keep_history_only=True):
    """Union this run's works with a previous run's local JSON (living review).

    Args:
        works:            merged works of the CURRENT run (usually normalize.merge(...)).
        history:          previous `.merged.json` path / payload dict / list of records.
        today:            stamp for this run (default: today, YYYY-MM-DD).
        keep_history_only: keep records that were in history but NOT seen this run.
                           They keep their old `last_seen` (never refreshed) and are
                           flagged `seen_this_run=False`, so an evidence base can only
                           grow across runs — a paper must not silently vanish just
                           because it fell outside the current query window.

    Stamp semantics:
        first_seen  earliest date the record was ever seen (from history, else today)
        last_seen   latest date the record was seen (refreshed ONLY when seen this run)

    Old history files without these keys are fine — `.get()` yields None and the
    stamp is used; no other field is touched.

    Returns (works, stats).
    """
    stamp = today or datetime.date.today().isoformat()
    h_idx, h_order = {}, []
    for w in history_works(history):
        k = dedupe_key(w)
        if not k:
            continue
        if k in h_idx:
            prev = h_idx[k]
            _backfill(prev, w)
            prev["first_seen"] = _min_date(prev.get("first_seen"), w.get("first_seen"))
            prev["last_seen"] = _max_date(prev.get("last_seen"), w.get("last_seen"))
            continue
        rec = dict(w)
        h_idx[k] = rec
        h_order.append(k)

    out, seen_keys = [], set()
    n_new = n_carry = 0
    for w in works:
        if not isinstance(w, dict):
            out.append(w)
            continue
        k = dedupe_key(w)
        h = h_idx.get(k) if k else None
        if h:
            first = h.get("first_seen") or h.get("last_seen") or stamp
            n_carry += 1
        else:
            first = w.get("first_seen") or stamp
            n_new += 1
        w["first_seen"] = first
        w["last_seen"] = stamp
        w["seen_this_run"] = True
        if k:
            seen_keys.add(k)
        _backfill(w, h)
        out.append(w)

    n_retained = 0
    if keep_history_only:
        for k in h_order:
            if k in seen_keys:
                continue
            h = dict(h_idx[k])
            # NOT seen this run: last_seen is left exactly as history recorded it
            # (None when unknown) — never back-stamped with today's date, otherwise
            # the report would claim a sighting that did not happen.
            h["first_seen"] = h.get("first_seen") or h.get("last_seen")
            h["last_seen"] = h.get("last_seen")
            h["seen_this_run"] = False
            h["retained_from_history"] = True
            out.append(h)
            n_retained += 1

    stats = {"stamp": stamp, "history_total": len(h_idx), "new": n_new,
             "carryover": n_carry, "retained_only": n_retained, "total": len(out)}
    return out, stats


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
