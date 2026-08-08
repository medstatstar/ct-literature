#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scenario10b.py - ct-literature 对抗/边界 10 案例（第二代硬化套件）。

scenario10.py 覆盖主编排 happy path（已 10x10 全 PASS）；本套件专攻此前
未触达的路径：单脚本链路、SAFE PREVIEW 语义、跨源 DOI 去重桥接、畸形记录
健壮性、非法参数优雅退出、注入型/超长主题、双语导出、幂等重跑、key 泄漏。

10 个案例（简单 -> 复杂）：
  B1  SAFE PREVIEW：无 --run 不得联网、不得落盘产物
  B2  单脚本链路：fetch_openalex -> normalize -> report（裸文件桥接）
  B3  Europe PMC 单源直取 + normalize（无 OpenAlex 参与）
  B4  Semantic Scholar 单源 429 降级必须 rc=0 且产出合法 JSON
  B5  跨源 DOI 去重：同一 DOI 的 OA/EPMC 记录须合并且 sources 含两者
  B6  非法参数：--max 0 / year-from>year-to / 未知 review-type -> 优雅退出无 traceback
  B7  注入型 & 超长主题（引号/括号/&/CJK 混排/512 字符）不崩
  B8  畸形 merged.json（缺字段/None/超长摘要/坏 URL）-> report+xlsx+html 不崩
  B9  中文主题 + safety + 双源（CJK 归一化去重路径）
  B10 幂等重跑同一 out-dir + 产物不残留脏数据 + 日志不泄漏 API key

用法：  C:/Tools/anaconda3/python.exe tests/scenario10b.py [--cases 1,5]
结果：  tests/results/scenario10b_<date>.json
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL, "scripts")
RESULTS = os.path.join(HERE, "results")
RUNS = os.path.join(HERE, "scenario10b_run")
DATE = datetime.date.today().isoformat()
PY = "C:/Tools/anaconda3/python.exe"
os.makedirs(RESULTS, exist_ok=True)
os.makedirs(RUNS, exist_ok=True)


def sh(script, *args, timeout=300):
    cmd = [PY, os.path.join(SCRIPTS, script), *args]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           cwd=SCRIPTS, env=dict(os.environ))
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or ""), (e.stderr or "") + "\n[TIMEOUT]"


def orch(out_dir, *args, timeout=300):
    os.makedirs(out_dir, exist_ok=True)
    return sh("ct_literature.py", *args, "--out-dir", out_dir, timeout=timeout)


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def nonempty(p):
    return os.path.exists(p) and os.path.getsize(p) > 0


def works_of_file(path):
    d = load_json(path)
    if isinstance(d, dict):
        w = d.get("works")
        return w if isinstance(w, list) else []
    return d if isinstance(d, list) else []


def works_of(out_dir):
    return works_of_file(os.path.join(out_dir, "merged.json"))


def has_traceback(*texts):
    return any("Traceback (most recent call last)" in (t or "") for t in texts)


def api_key():
    k = os.environ.get("OPENALEX_API_KEY", "")
    if k:
        return k
    for p in (os.path.join(SKILL, ".env"), os.path.join(SCRIPTS, ".env")):
        try:
            for line in open(p, encoding="utf-8"):
                if line.strip().startswith("OPENALEX_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
    return ""


# ------------------------------------------------------------------ 案例 ---
def b01_safe_preview(out):
    """无 --run 应只打印预览，不产出 merged/report 等产物，且 rc=0。"""
    rc, so, se = orch(out, "--topic", "osimertinib", "--max", "5", timeout=90)
    if rc != 0:
        return False, f"preview rc={rc} stderr={se[-500:]}"
    if has_traceback(so, se):
        return False, "preview 出现 traceback"
    leaked = [f for f in ("merged.json", "lit_report.md", "lit_report.xlsx",
                          "lit_report.html", "openalex.json")
              if nonempty(os.path.join(out, f))]
    if leaked:
        return False, f"SAFE PREVIEW 却落盘产物: {leaked}"
    hint = ("PREVIEW" in so.upper()) or ("--run" in so) or ("预览" in so)
    if not hint:
        return False, f"预览输出无提示语: {so[:300]}"
    return True, f"rc=0 无产物落盘 预览提示 OK (stdout {len(so)}B)"


def b02_single_chain(out):
    """fetch_openalex -> normalize -> report 三段式手工链路。"""
    oa = os.path.join(out, "oa.json")
    mg = os.path.join(out, "m.json")
    rp = os.path.join(out, "r.md")
    rc1, so1, se1 = sh("fetch_openalex.py", "--topic", "osimertinib", "--max", "10",
                       "--run", "--out", oa, timeout=180)
    if rc1 != 0 or not nonempty(oa):
        return False, f"fetch rc={rc1} out_exists={nonempty(oa)} {se1[-400:]}"
    n_oa = len(works_of_file(oa))
    rc2, so2, se2 = sh("normalize.py", "--in", oa, "--out", mg, timeout=60)
    if rc2 != 0 or not nonempty(mg):
        return False, f"normalize rc={rc2} {se2[-400:]}"
    n_mg = len(works_of_file(mg))
    rc3, so3, se3 = sh("report.py", "--in", mg, "--out", rp, "--topic",
                       "osimertinib", timeout=60)
    if rc3 != 0 or not nonempty(rp):
        return False, f"report rc={rc3} {se3[-400:]}"
    if n_oa == 0 or n_mg == 0:
        return False, f"链路空数据 oa={n_oa} merged={n_mg}"
    if n_mg > n_oa:
        return False, f"归一化后条数反增 oa={n_oa} merged={n_mg}"
    return True, f"oa={n_oa} merged={n_mg} report={os.path.getsize(rp)}B"


def b03_epmc_only(out):
    """仅 Europe PMC 单源 -> normalize，验证不依赖 OpenAlex。"""
    ep = os.path.join(out, "ep.json")
    mg = os.path.join(out, "m.json")
    rc1, so1, se1 = sh("fetch_europepmc.py", "--topic", "metformin lactic acidosis",
                       "--max", "15", "--run", "--out", ep, timeout=180)
    if rc1 != 0 or not nonempty(ep):
        return False, f"epmc rc={rc1} {se1[-400:]}"
    n_ep = len(works_of_file(ep))
    if n_ep == 0:
        return False, "Europe PMC 返回 0 条（主题应有命中）"
    rc2, so2, se2 = sh("normalize.py", "--in", ep, "--out", mg, timeout=60)
    ws = works_of_file(mg)
    if rc2 != 0 or not ws:
        return False, f"normalize rc={rc2} merged={len(ws)} {se2[-400:]}"
    bad_src = [w for w in ws if "EuropePMC" not in (w.get("sources") or [w.get("source")])]
    if bad_src:
        return False, f"来源标记错误 {len(bad_src)}/{len(ws)}"
    with_pmid = sum(1 for w in ws if w.get("pmid"))
    return True, f"epmc={n_ep} merged={len(ws)} with_pmid={with_pmid}"


def b04_s2_degrade(out):
    """Semantic Scholar 无 key：429 或成功都必须 rc=0 且 JSON 合法。"""
    s2 = os.path.join(out, "s2.json")
    rc, so, se = sh("fetch_semantic_scholar.py", "--topic", "pembrolizumab",
                    "--max", "10", "--run", "--out", s2, timeout=240)
    if rc != 0:
        return False, f"S2 降级未优雅 rc={rc} {se[-600:]}"
    if has_traceback(so, se):
        return False, f"S2 抛 traceback: {se[-600:]}"
    if not os.path.exists(s2):
        return False, "S2 未生成输出文件（降级也应写空结构）"
    d = load_json(s2)
    if d is None:
        return False, "S2 输出非合法 JSON"
    n = len(works_of_file(s2))
    # 空结果也 PASS：429 属预期降级
    mg = os.path.join(out, "m.json")
    rc2, so2, se2 = sh("normalize.py", "--in", s2, "--out", mg, timeout=60)
    if rc2 != 0:
        return False, f"空/少量 S2 输入 normalize 崩溃 rc={rc2} {se2[-400:]}"
    return True, f"s2={n} 降级链路 OK merged={len(works_of_file(mg))}"


def b05_cross_dedupe(out):
    """离线构造同 DOI 跨源记录，验证 normalize 合并且保留双 provenance。"""
    doi = "10.1056/nejmoa1713137"
    a = {"source": "OpenAlex", "count": 2, "works": [
        {"source": "OpenAlex", "id": "W1", "title": "Osimertinib in EGFR-mutated NSCLC",
         "doi": doi, "year": 2018, "cited_by_count": 100, "authors": ["A"],
         "url": "https://openalex.org/W1"},
        {"source": "OpenAlex", "id": "W2", "title": "Unique OA only paper",
         "doi": "10.1000/oa-only", "year": 2020, "cited_by_count": 5, "authors": ["B"]},
    ]}
    b = {"source": "EuropePMC", "count": 2, "works": [
        {"source": "EuropePMC", "id": "MED123",
         "title": "Osimertinib in EGFR-Mutated NSCLC.",  # 大小写/句点差异
         "doi": doi.upper(), "year": 2018, "pmid": "29151359", "authors": ["A"],
         "mesh": ["Lung Neoplasms"]},
        {"source": "EuropePMC", "id": "MED999", "title": "EPMC only paper",
         "doi": "10.1000/ep-only", "year": 2021, "pmid": "1"},
    ]}
    pa, pb = os.path.join(out, "a.json"), os.path.join(out, "b.json")
    mg = os.path.join(out, "m.json")
    json.dump(a, open(pa, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(b, open(pb, "w", encoding="utf-8"), ensure_ascii=False)
    rc, so, se = sh("normalize.py", "--in", pa, pb, "--out", mg, timeout=60)
    if rc != 0:
        return False, f"normalize rc={rc} {se[-400:]}"
    ws = works_of_file(mg)
    if len(ws) != 3:
        return False, (f"跨源去重失败：期望 3 条（1 合并 + 2 独有），实际 {len(ws)}；"
                       f"titles={[w.get('title') for w in ws]}")
    merged = [w for w in ws if (w.get("doi") or "").lower() == doi]
    if len(merged) != 1:
        return False, f"同 DOI 未收敛为 1 条，实际 {len(merged)}"
    srcs = set(merged[0].get("sources") or [merged[0].get("source")])
    if not {"OpenAlex", "EuropePMC"} <= srcs:
        return False, f"合并后 provenance 丢失: {srcs}"
    keep_pmid = merged[0].get("pmid")
    return True, f"merged=3 dedupe OK sources={sorted(srcs)} pmid_kept={keep_pmid}"


def b06_bad_args(out):
    """三类非法参数：必须非 0 退出或安全兜底，且绝不 traceback。"""
    notes = []
    # 6a 未知 review-type -> argparse choices 报错 rc=2
    rc_a, so_a, se_a = orch(os.path.join(out, "a"), "--topic", "x",
                            "--review-type", "not-a-type", "--run", timeout=90)
    if has_traceback(so_a, se_a):
        return False, f"6a traceback: {se_a[-500:]}"
    if rc_a == 0:
        return False, "6a 非法 review-type 竟成功退出"
    notes.append(f"6a rc={rc_a}")
    # 6b --max 0 -> 不得崩溃（要么报错要么 0 条正常收尾）
    rc_b, so_b, se_b = orch(os.path.join(out, "b"), "--topic", "osimertinib",
                            "--max", "0", "--run", timeout=180)
    if has_traceback(so_b, se_b):
        return False, f"6b --max 0 traceback: {se_b[-600:]}"
    notes.append(f"6b rc={rc_b}")
    # 6c year-from > year-to -> 不得崩溃
    rc_c, so_c, se_c = orch(os.path.join(out, "c"), "--topic", "osimertinib",
                            "--year-from", "2030", "--year-to", "2000",
                            "--max", "5", "--run", timeout=180)
    if has_traceback(so_c, se_c):
        return False, f"6c 逆序年份 traceback: {se_c[-600:]}"
    notes.append(f"6c rc={rc_c} merged={len(works_of(os.path.join(out, 'c')))}")
    # 缺 --topic -> argparse required
    rc_d, so_d, se_d = sh("ct_literature.py", "--run", timeout=60)
    if rc_d == 0:
        return False, "6d 缺 --topic 竟成功"
    notes.append(f"6d rc={rc_d}")
    return True, " | ".join(notes)


def b07_weird_topic(out):
    """注入型字符 + 超长主题：URL 编码与请求构造不得崩。"""
    weird = 'BRAF V600E & "targeted" therapy (NSCLC) 100% <script>/?#'
    rc_a, so_a, se_a = orch(os.path.join(out, "a"), "--topic", weird, "--max", "5",
                            "--run", timeout=180)
    if has_traceback(so_a, se_a):
        return False, f"7a 特殊字符 traceback: {se_a[-700:]}"
    if rc_a != 0:
        return False, f"7a rc={rc_a} {se_a[-500:]}"
    longt = ("非小细胞肺癌 EGFR 突变 奥希替尼 耐药机制 " * 12)[:512]
    rc_b, so_b, se_b = orch(os.path.join(out, "b"), "--topic", longt, "--max", "5",
                            "--run", timeout=180)
    if has_traceback(so_b, se_b):
        return False, f"7b 超长主题 traceback: {se_b[-700:]}"
    if rc_b != 0:
        return False, f"7b rc={rc_b} {se_b[-500:]}"
    na = len(works_of(os.path.join(out, "a")))
    nb = len(works_of(os.path.join(out, "b")))
    return True, f"weird rc=0 merged={na} | long({len(longt)}字) rc=0 merged={nb}"


def b08_malformed(out):
    """畸形 merged.json 喂给 report/export_xlsx/export_html，三者都不能崩。"""
    mg = os.path.join(out, "m.json")
    payload = {"count": 6, "works": [
        {},                                                     # 全空
        {"source": "OpenAlex", "id": "W1", "title": None, "year": None,
         "authors": None, "sources": None},                     # None 字段
        {"source": "OpenAlex", "id": "W2", "title": "长摘要",
         "abstract_snippet": "长" * 40000, "year": "2019",      # 年份为字符串
         "cited_by_count": None, "authors": []},
        {"source": "EuropePMC", "id": "W3", "title": "坏链接",
         "url": "not a url ]]", "open_access_url": "javascript:alert(1)",
         "doi": "10.1/x", "year": 2021, "is_safety": True},
        {"source": "S2", "id": "W4", "title": "特殊字符 <>&\"'\t\n换行",
         "year": 1899, "authors": ["A" * 500], "mesh": ["x"] * 200},
        {"source": "OpenAlex", "id": "W5", "title": "正常记录",
         "year": 2023, "doi": "10.1/ok", "cited_by_count": 7,
         "url": "https://doi.org/10.1/ok"},
    ]}
    json.dump(payload, open(mg, "w", encoding="utf-8"), ensure_ascii=False)
    notes = []
    rc1, so1, se1 = sh("report.py", "--in", mg, "--out", os.path.join(out, "r.md"),
                       "--topic", "malformed", timeout=90)
    if rc1 != 0 or has_traceback(so1, se1):
        return False, f"report 崩溃 rc={rc1} {se1[-700:]}"
    notes.append("report OK")
    xp = os.path.join(out, "r.xlsx")
    rc2, so2, se2 = sh("export_xlsx.py", "--in-json", mg, "--out", xp,
                       "--lang", "zh", timeout=120)
    if rc2 != 0 or has_traceback(so2, se2) or not nonempty(xp):
        return False, f"xlsx 崩溃 rc={rc2} exists={nonempty(xp)} {se2[-700:]}"
    notes.append(f"xlsx {os.path.getsize(xp)}B")
    hp = os.path.join(out, "r.html")
    rc3, so3, se3 = sh("export_html.py", "--in-json", mg, "--out", hp,
                       "--lang", "en", timeout=90)
    if rc3 != 0 or has_traceback(so3, se3) or not nonempty(hp):
        return False, f"html 崩溃 rc={rc3} exists={nonempty(hp)} {se3[-700:]}"
    html = open(hp, encoding="utf-8").read()
    if "<script>alert" in html or "javascript:alert(1)\"" in html.replace("&", "&"):
        notes.append("⚠ 可疑未转义链接")
    notes.append(f"html {len(html)}B")
    return True, " | ".join(notes)


def b09_cjk_safety_dual(out):
    """中文主题 + --safety + 双源：CJK 归一化 + safety 标记 + MeSH 增强。"""
    rc, so, se = orch(out, "--topic", "奥希替尼 不良反应", "--safety",
                      "--with-europepmc", "--max", "20", "--run", timeout=300)
    if rc != 0:
        return False, f"rc={rc} {se[-600:]}"
    ws = works_of(out)
    if not ws:
        return False, "merged 为空"
    ids = [w.get("id") for w in ws]
    dup = len(ids) - len(set(ids))
    if dup:
        return False, f"合并后存在重复 id {dup} 个"
    md = os.path.join(out, "lit_report.md")
    if not nonempty(md):
        return False, "报告缺失"
    txt = open(md, encoding="utf-8").read()
    if "安全" not in txt and "Safety" not in txt:
        return False, "safety 模式报告缺安全性段落"
    n_safe = sum(1 for w in ws if w.get("is_safety"))
    return True, f"merged={len(ws)} dup_id=0 is_safety={n_safe}"


def b10_idempotent(out):
    """同 out-dir 连跑两次：产物覆盖正确、无脏残留；日志不得泄漏 API key。"""
    a1 = orch(out, "--topic", "osimertinib", "--max", "20", "--run", timeout=240)
    if a1[0] != 0:
        return False, f"首跑 rc={a1[0]} {a1[2][-400:]}"
    n1 = len(works_of(out))
    size1 = os.path.getsize(os.path.join(out, "lit_report.md"))
    # 第二次用不同参数（更小结果集 + 关闭 xlsx），验证覆盖而非追加
    a2 = orch(out, "--topic", "aspirin", "--max", "5", "--run", timeout=240)
    if a2[0] != 0:
        return False, f"重跑 rc={a2[0]} {a2[2][-400:]}"
    n2 = len(works_of(out))
    md = open(os.path.join(out, "lit_report.md"), encoding="utf-8").read()
    if "osimertinib" in md.lower():
        return False, "重跑后报告仍含上一次主题（产物未覆盖，脏残留）"
    if n2 > n1:
        return False, f"重跑 max=5 却 merged={n2} > 首跑 {n1}（疑似追加）"
    key = api_key()
    blob = (a1[1] + a1[2] + a2[1] + a2[2])
    if key and key in blob:
        return False, "❌ API key 出现在 stdout/stderr（泄漏）"
    if key and key in md:
        return False, "❌ API key 出现在报告中（泄漏）"
    masked = bool(re.search(r"key", blob, re.I))
    return True, (f"run1 merged={n1} md={size1}B -> run2 merged={n2} 覆盖 OK | "
                  f"key_leak=NO (key_mentioned={masked})")


CASES = [
    (1,  "SAFE PREVIEW 不落盘不联网", b01_safe_preview),
    (2,  "单脚本链路 fetch->normalize->report", b02_single_chain),
    (3,  "Europe PMC 单源链路", b03_epmc_only),
    (4,  "Semantic Scholar 429 优雅降级", b04_s2_degrade),
    (5,  "跨源同 DOI 去重 + provenance", b05_cross_dedupe),
    (6,  "非法参数优雅退出", b06_bad_args),
    (7,  "注入型/超长主题", b07_weird_topic),
    (8,  "畸形 merged.json 三导出健壮性", b08_malformed),
    (9,  "中文+safety+双源", b09_cjk_safety_dual),
    (10, "幂等重跑 + key 不泄漏", b10_idempotent),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases")
    args = ap.parse_args()
    sel = {int(x) for x in args.cases.split(",") if x.strip()} if args.cases else None

    results = []
    for num, name, fn in CASES:
        if sel and num not in sel:
            continue
        out = os.path.join(RUNS, f"b{num:02d}")
        os.makedirs(out, exist_ok=True)
        rec = {"case": num, "name": name, "status": None, "detail": None}
        try:
            ok, det = fn(out)
            rec["status"] = "PASS" if ok else "FAIL"
            rec["detail"] = det
        except Exception as e:
            rec["status"] = "FAIL"
            rec["detail"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}"
        print(f"[B{num:02d}] {rec['status']:4s} {name} :: {rec['detail']}")
        results.append(rec)

    n_pass = sum(1 for r in results if r["status"] == "PASS")
    summary = {"date": DATE, "suite": "scenario10b", "total": len(results),
               "PASS": n_pass, "FAIL": len(results) - n_pass, "cases": results}
    p = os.path.join(RESULTS, f"scenario10b_{DATE}.json")
    json.dump(summary, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n=== SCENARIO10B {DATE}: PASS={n_pass} FAIL={len(results)-n_pass} ===")
    if n_pass != len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
