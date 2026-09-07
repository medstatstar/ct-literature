#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""coze_resolve.py — 用 Coze ct-search 端点把「间接下载链接」解码为「可直接下载的文件链接」

ct-literature 工作台专用轻量工具：读取一份 .merged.json（或任意含 works[] 的 JSON），
对其中每一篇文献收集可下载标识（open_access_url 优先 → preprint.url → doi），
批量 POST 到 ct-search.coze.site/run 的 publisher_pdf_batch 统一契约（解码+A→B），
由 Coze 端把间接链接/DOI 解码为可直接下载的真实直链（pdf_url / pdf_s3_url），或 pdf_failed。

设计对齐 ct-base 的「解码上 Coze、下载在本地」：
  * 统一契约：Coze 对每条标识执行 A(解码+直下探测验证)→B(浏览器+S3)，只返回已验证真实直链；
  * 本地不做二次解析（避免越权/反爬），只下载 Coze 返回的真实直链；
  * --download 时把能拿到的直链保存到 <out_dir>/pdfs/，其余标记 manual。

复用 scripts/pdf_download.py 的 PdfDownloader（其 _call_coze_unified /
_headers / _resolve_token / _query_origin 已封装同一端点契约），不重复造轮子。

用法：
  python coze_resolve.py --in .merged.json                # 只解码，输出直链 JSON
  python coze_resolve.py --in .merged.json --download     # 解码并下载到 pdfs/
  python coze_resolve.py --in .merged.json --out r.json   # 结果写文件而非 stdout

安全：仅只读输入 JSON；联网仅发给既有的 ct-search 端点；token 从 ct-registry/ct-advisor
内嵌公开 blob 复用（见 pdf_download._resolve_token），绝不打印 token 明文（ct-base §5）。
"""
import argparse
import json
import os
import sys

# 技能根注入：使 `from adapters.pdf_download import …` 在 __main__ 直跑与包导入下均可解析
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _collect_identifiers(works):
    """为每篇 work 生成 (idx, key, doi, label, direct_candidate)。
    key 取 open_access_url 优先、否则 preprint.url、否则 doi —— 与 PdfDownloader.run 一致。
    """
    out = []
    for i, w in enumerate(works):
        oa = (w.get("open_access_url") or "").strip()
        pre = ((w.get("preprint") or {}).get("url") or "").strip()
        doi = (w.get("doi") or "").strip()
        # label: 简短展示用
        label = (w.get("title") or w.get("doi") or "untitled")[:80]
        # 需发 Coze 解码的：有 doi 或 OA 间接链接但没有可靠本地直链的篇目
        # （预印本直链通常可直接下，也一并过一遍 Coze，统一拿 Coze 判定）
        key = oa or pre or doi
        if not key:
            continue
        out.append({"idx": i, "key": key, "doi": doi, "label": label,
                    "oa": oa, "preprint_url": pre})
    return out


def main():
    ap = argparse.ArgumentParser(description="Coze resolve: decode indirect links -> direct file links")
    ap.add_argument("--in", dest="inp", required=True, help=".merged.json (or any JSON with works[])")
    ap.add_argument("--out", default="", help="write JSON result to this file (default stdout)")
    ap.add_argument("--download", action="store_true",
                    help="also download resolvable direct links into <dir>/pdfs/")
    ap.add_argument("--dir", dest="out_dir", default="",
                    help="output dir for pdfs/ when --download (default: same dir as --in)")
    ap.add_argument("--skip-coze", action="store_true",
                    help="local-only decode (no Coze); mainly for debugging")
    args = ap.parse_args()

    if not os.path.isfile(args.inp):
        sys.exit("[coze_resolve] missing input: %s" % args.inp)

    with open(args.inp, "r", encoding="utf-8") as f:
        data = json.load(f)
    works = data.get("works") if isinstance(data, dict) else data
    if not isinstance(works, list) or not works:
        sys.exit("[coze_resolve] no works[] found in %s" % args.inp)

    from adapters.pdf_download import PdfDownloader  # noqa: PLC0415  (deferred import keeps CLI fast)
    out_dir = args.out_dir or os.path.dirname(os.path.abspath(args.inp))
    dl = PdfDownloader(out_dir=os.path.join(out_dir, "pdfs"))

    # 1) 收集标识
    targets = _collect_identifiers(works)
    keys = [t["key"] for t in targets]
    if not keys:
        print(json.dumps({"ok": True, "total": 0, "items": [],
                          "note": "works 中无可用 DOI / OA / 预印本链接"}, ensure_ascii=False))
        return 0

    # 2) Coze 单次传送（统一契约：解码+A→B，返回真实直链或 pdf_failed）
    #    单批上限 MAX_BATCH_ITEMS（与 coze 端一致），超过需拆批逐批传送
    from adapters.pdf_download import MAX_BATCH_ITEMS
    projects = None
    if not args.skip_coze:
        if len(keys) <= MAX_BATCH_ITEMS:
            # 单批即可
            try:
                projects = dl._call_coze_unified(keys)
            except Exception as e:  # noqa: BLE001
                projects = None
                dl._log("[coze_resolve] Coze 调用异常: %s" % e)
        else:
            # 拆批传送（与 PdfDownloader.run 拆批逻辑一致）
            chunks = [keys[i:i + MAX_BATCH_ITEMS]
                      for i in range(0, len(keys), MAX_BATCH_ITEMS)]
            dl._log(f"[coze_resolve] {len(keys)} 篇超过单批上限 {MAX_BATCH_ITEMS}，"
                    f"自动拆为 {len(chunks)} 批")
            collected = []
            all_ok = True
            for ci, chunk in enumerate(chunks, 1):
                dl._log(f"[coze_resolve] 第 {ci}/{len(chunks)} 批：{len(chunk)} 篇 ...")
                try:
                    part = dl._call_coze_unified(chunk)
                except Exception as e:  # noqa: BLE001
                    part = None
                    dl._log(f"[coze_resolve] 第 {ci}/{len(chunks)} 批异常: {e}")
                if part is None:
                    all_ok = False
                    # 该批降级本地兜底（与 pdf_download 一致）
                    from adapters.pdf_download import _extract_doi_from_url
                    for k in chunk:
                        collected.append({"key": k, "doi": _extract_doi_from_url(k) or "",
                                          "pdf_url": None, "pdf_s3_url": None,
                                          "status": "manual",
                                          "error": "该批 coze 传送失败，降级本地兜底"})
                else:
                    collected.extend(part)
            projects = collected if collected else None if not all_ok else []
    if projects is None:
        # Coze 不可用 → 本地兜底（仅标记，不下载）
        by_key = {t["key"]: t for t in targets}
        projects = []
        for k in keys:
            t = by_key.get(k, {})
            projects.append({"key": k, "doi": t.get("doi") or "",
                             "pdf_url": None, "pdf_s3_url": None,
                             "status": "manual", "error": "Coze 不可用"})

    # 区分「coze 返回了结果（含 ok / pdf_failed）」vs「coze 真的不可用（异常/无响应）」
    coze_unavailable = (projects is None)
    if coze_unavailable:
        projects = []

    # key -> 记录（coze 可能返回原始 key 或从 URL 提取的 DOI，需双向匹配）
    rec_map: Dict[str, Dict] = {}
    for p in projects:
        k = p.get("key") or p.get("doi") or ""
        rec_map[k] = p
        # 同时以 doi 为键索引（coze 可能把 OA URL 解析为裸 DOI 返回）
        doi = p.get("doi") or ""
        if doi and doi != k:
            rec_map[doi] = p

    # 3) 组装每篇结果
    from adapters.pdf_download import _extract_doi_from_url
    items = []
    dl_stats = {"coze_resolved": 0, "coze_failed": 0, "coze_unavailable": 0, "manual": 0}
    if coze_unavailable:
        dl_stats["coze_unavailable"] = len(targets)

    for t in targets:
        # 先按原始 key 匹配；若不命中，尝试从 key(URL) 提取 DOI 后按 DOI 匹配
        rec = rec_map.get(t["key"], {})
        if not rec:
            extracted_doi = _extract_doi_from_url(t["key"])
            if extracted_doi:
                rec = rec_map.get(extracted_doi, {})
        url = rec.get("pdf_s3_url") or rec.get("pdf_url")
        has_url = bool(url) and rec.get("status") == "ok"

        if coze_unavailable:
            # coze 真的不可用（异常/无响应）
            row = {
                "idx": t["idx"],
                "title": t["label"],
                "doi": t["doi"] or "",
                "oa": t.get("oa") or "",
                "preprint_url": t.get("preprint_url") or "",
                "key": t["key"],
                "direct_url": "",
                "source": "unavailable",
                "cloudflare": False,
                "status": "unavailable",
                "error": "Coze 端点不可用（连接异常或超时）",
            }
        elif has_url:
            # coze 返回了真实直链
            row = {
                "idx": t["idx"],
                "title": t["label"],
                "doi": t["doi"] or "",
                "oa": t.get("oa") or "",
                "preprint_url": t.get("preprint_url") or "",
                "key": t["key"],
                "direct_url": url or "",
                "source": rec.get("via") or rec.get("source") or "coze",
                "cloudflare": bool(rec.get("cloudflare")),
                "status": "direct",
                "error": rec.get("error") or "",
            }
            dl_stats["coze_resolved"] += 1
        else:
            # coze 返回了 pdf_failed（A/B 路径都失败）
            row = {
                "idx": t["idx"],
                "title": t["label"],
                "doi": t["doi"] or "",
                "oa": t.get("oa") or "",
                "preprint_url": t.get("preprint_url") or "",
                "key": t["key"],
                "direct_url": "",
                "source": rec.get("via") or rec.get("source") or "coze_failed",
                "cloudflare": bool(rec.get("cloudflare")),
                "status": "failed",
                "error": rec.get("error") or "Coze 未返回可下载直链",
            }
            dl_stats["coze_failed"] += 1
        items.append(row)

    # 4) 可选下载
    downloaded = {}
    if args.download and not args.skip_coze:
        for row in items:
            if row["status"] != "direct" or not row["direct_url"]:
                continue
            try:
                path = dl._download_direct_with_delay(row["direct_url"], row["key"] or row["doi"], delay=0.5)
            except Exception:  # noqa: BLE001
                path = None
            if path:
                downloaded[row["key"]] = path
            else:
                # 下载失败 → 降级为 failed
                row["status"] = "failed"
                row["error"] = row.get("error", "") + "；本地下载失败"
                dl_stats["coze_resolved"] = max(0, dl_stats["coze_resolved"] - 1)
                dl_stats["coze_failed"] = dl_stats.get("coze_failed", 0) + 1

    result = {
        "ok": True,
        "total": len(items),
        "stats": dl_stats,
        "downloaded": downloaded,
        "items": items,
        "endpoint": "ct-search.coze.site/stream_run:publisher_pdf_batch(unified)",
    }
    # 当全部为 pdf_failed 且 error 含"B 路径未启用"时，附加说明 note
    failed_notes = [r.get("error", "") for r in items if r.get("status") == "failed"]
    if failed_notes and all("B 路径" in n or "未启用" in n for n in failed_notes if n):
        result["note"] = "Coze 端 B 路径（浏览器下载）未启用；仅靠 A 路径（OA/PMC/直链）无法覆盖付费墙文献。可在 coze 端设置 CT_ENABLE_BROWSER_PDF_DOWNLOAD=1 启用。"
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print("[coze_resolve] -> %s (%d works)" % (args.out, len(items)))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
