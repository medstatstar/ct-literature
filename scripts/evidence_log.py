#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""evidence_log.py — provenance audit trail (ct-base §17.1 anti-hallucination).

Builds an immutable-style provenance log from the fetch payloads + verification
summary, so every evidence item is traceable:

    query  ->  source  ->  hit count  ->  retrieved_at  ->  verification rate

Outputs:
  - evidence_log.json  (machine readable; also embedded into .merged.json)
  - evidence_log.md    (human readable, audit trail)
The same dict is consumed by export_xlsx.build_evidence() for the Excel sheet.

Pure stdlib; no network. Mirror the SAFE PREVIEW contract: only built when the
pipeline actually ran (payloads populated).
"""
import json
import os
from datetime import datetime


def build_log(payloads, topic, meta, verification_summary, config=None, degraded=None):
    """payloads: list of {source, query, works, ...} (or None).
    config: dict of run-time configuration recorded for audit, e.g.
        {"openalex_key": "configured" | "missing", "openalex_key_url": "https://..."}.
        Key presence is recorded as a STATUS STRING — the key value itself is
        NEVER logged (ct-base §5: no credentials in logs).
    degraded: list of per-source degradation notes (rate-limit / fetch failure), each
        {"source", "status", "message_zh", "message_en"} — surfaced so a failed source is
        documented, not silently swallowed.
    Returns the evidence-log dict (topic / generated_at / config / degraded / sources / verification)."""
    meta = meta or {}
    sources = []
    for p in payloads:
        if not p:
            continue
        cnt = p.get("count")
        if cnt is None:
            cnt = len(p.get("works") or [])
        sources.append({
            "source": p.get("source"),
            "query": p.get("query"),
            "review_type": p.get("review_type"),
            "year_from": p.get("year_from"),
            "year_to": p.get("year_to"),
            "safety": p.get("safety"),
            "count": cnt,
            "retrieved_at": datetime.now().isoformat(timespec="seconds"),
            "status": "ok" if cnt else "empty",
        })
    return {
        "topic": topic,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "config": config or {},
        "degraded": degraded or [],
        "sources": sources,
        "verification": verification_summary or {},
    }


def render_md(log):
    lines = []
    lines.append("# Evidence Log / 证据溯源日志\n")
    lines.append("- **Topic / 主题**: %s" % (log.get("topic") or "—"))
    lines.append("- **Generated / 生成时间**: %s" % (log.get("generated_at") or "—"))
    cfg = log.get("config") or {}
    if cfg:
        key_status = cfg.get("openalex_key", "")
        lines.append("- **OpenAlex key / 密钥**: %s" % (
            "configured ✓" if key_status == "configured"
            else "**missing — keyless mode (100 credits/day, rate-limited)**"))
        if key_status == "missing" and cfg.get("openalex_key_url"):
            lines.append("  > ⚠️ 未配置 OpenAlex API key：当前以 keyless 模式运行（限 100 次/天，易触发 HTTP 429）。"
                         "建议申请免费 key 后写入技能目录 `.env`（`OPENALEX_API_KEY=<key>`）：%s" % cfg["openalex_key_url"])
    deg = log.get("degraded") or []
    if deg:
        lines.append("")
        lines.append("## ⚠️ Degraded sources / 降级数据源")
        lines.append("> 以下数据源未能正常返回（限流或报错），本轮结果仅来自其余可用数据源。")
        for d in deg:
            lines.append("- **%s** (%s):" % (d.get("source"), d.get("status")))
            lines.append("  - 🇨🇳 %s" % d.get("message_zh"))
            lines.append("  - 🇬🇧 %s" % d.get("message_en"))
    v = log.get("verification") or {}
    if v:
        lines.append(
            "- **Verification / 引文验证**: total=%s · verified=%s · "
            "bot-blocked=%s (出版社拦爬=%s) · mismatch=%s (不一致=%s) · "
            "unresolved=%s · no_identifier=%s · suspicious=%s%s"
            % (v.get("total", 0), v.get("verified", 0), v.get("bot_blocked", 0),
               v.get("bot_blocked", 0), v.get("mismatch", 0), v.get("mismatch", 0),
               v.get("unresolved", 0), v.get("no_identifier", 0),
               v.get("suspicious", 0),
               " (preview-skip)" if v.get("skipped_preview") else ""))
        if v.get("bot_blocked"):
            lines.append(
                "  - ⚠️ bot-blocked / 出版社拦爬: %s 篇 DOI 真实有效，仅因出版社对自动化访问回 "
                "403 被拦（非断链）；如需可人工复核。" % v.get("bot_blocked", 0))
        if v.get("mismatch"):
            lines.append(
                "  - ⚠️ mismatch / 不一致: %s 篇标识符解析到存活资源，但标题/作者与该文献不符"
                "（可能为幻觉或错误 id），请人工复核。" % v.get("mismatch", 0))
    lines.append("")
    lines.append("| Source / 来源 | Query / 检索式 | Type | Year | Safety | Count | "
                 "Retrieved / 检索时间 | Status |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for s in log.get("sources", []):
        lines.append("| %s | %s | %s | %s–%s | %s | %s | %s | %s |" % (
            s.get("source"), (s.get("query") or "")[:80], s.get("review_type") or "all",
            s.get("year_from") or "", s.get("year_to") or "",
            "Y" if s.get("safety") else "—", s.get("count", 0),
            s.get("retrieved_at", ""), s.get("status", "")))
    lines.append("")
    lines.append("> Provenance audit trail (ct-base §17.1): every evidence item is traceable to "
                 "its source query and retrieval time. Verification status is advisory, not a "
                 "substitute for human review.")
    return "\n".join(lines)


def write_log(log, out_dir, lang="auto"):
    os.makedirs(out_dir, exist_ok=True)
    jpath = os.path.join(out_dir, "evidence_log.json")
    mpath = os.path.join(out_dir, "evidence_log.md")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    md = render_md(log)
    with open(mpath, "w", encoding="utf-8") as f:
        f.write(md)
    return {"json": jpath, "md": mpath}


def main():
    ap = argparse.ArgumentParser(description="Render an evidence log from a .merged.json + payloads.")
    ap.add_argument("--merged", default=".merged.json",
                    help=".merged.json (hidden intermediate; verification block)")
    ap.add_argument("--topic", default="—")
    ap.add_argument("--out-dir", default="./out")
    args = ap.parse_args()
    data = json.load(open(args.merged, encoding="utf-8"))
    # Prefer the evidence_log already embedded in .merged.json (full provenance);
    # only fall back to re-building from payloads when it is absent. (The pipeline
    # writes evidence_log into .merged.json, but payloads are NOT persisted there,
    # so reading `payloads` would silently yield an empty source trail.)
    if data.get("evidence_log"):
        log = data["evidence_log"]
    else:
        log = build_log(data.get("payloads") or [], args.topic,
                        data.get("meta") or {}, data.get("verification"))
    res = write_log(log, args.out_dir)
    print("[OK] evidence_log -> %s / %s" % (res["json"], res["md"]))


if __name__ == "__main__":
    main()
