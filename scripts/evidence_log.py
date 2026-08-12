#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""evidence_log.py — provenance audit trail (ct-base §17.1 anti-hallucination).

Builds an immutable-style provenance log from the fetch payloads + verification
summary, so every evidence item is traceable:

    query  ->  source  ->  hit count  ->  retrieved_at  ->  verification rate

Outputs:
  - evidence_log.json  (machine readable; also embedded into merged.json)
  - evidence_log.md    (human readable, audit trail)
The same dict is consumed by export_xlsx.build_evidence() for the Excel sheet.

Pure stdlib; no network. Mirror the SAFE PREVIEW contract: only built when the
pipeline actually ran (payloads populated).
"""
import json
import os
from datetime import datetime


def build_log(payloads, topic, meta, verification_summary):
    """payloads: list of {source, query, works, ...} (or None).
    Returns the evidence-log dict (topic / generated_at / sources / verification)."""
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
        "sources": sources,
        "verification": verification_summary or {},
    }


def render_md(log):
    lines = []
    lines.append("# Evidence Log / 证据溯源日志\n")
    lines.append("- **Topic / 主题**: %s" % (log.get("topic") or "—"))
    lines.append("- **Generated / 生成时间**: %s" % (log.get("generated_at") or "—"))
    v = log.get("verification") or {}
    if v:
        lines.append(
            "- **Verification / 引文验证**: total=%s · verified=%s · unresolved=%s · "
            "no_identifier=%s · suspicious=%s%s"
            % (v.get("total", 0), v.get("verified", 0), v.get("unresolved", 0),
               v.get("no_identifier", 0), v.get("suspicious", 0),
               " (preview-skip)" if v.get("skipped_preview") else ""))
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
    ap = argparse.ArgumentParser(description="Render an evidence log from a merged.json + payloads.")
    ap.add_argument("--merged", required=True, help="merged.json (for verification block)")
    ap.add_argument("--topic", default="—")
    ap.add_argument("--out-dir", default="./out")
    args = ap.parse_args()
    data = json.load(open(args.merged, encoding="utf-8"))
    log = build_log(data.get("payloads") or [], args.topic,
                    data.get("meta") or {}, data.get("verification"))
    res = write_log(log, args.out_dir)
    print("[OK] evidence_log -> %s / %s" % (res["json"], res["md"]))


if __name__ == "__main__":
    main()
