#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scenario10.py - ct-literature 真实联网 10 案例（从简单到复杂，覆盖各种场景）。

全部走主编排 ct_literature.py CLI（真实联网），验证各分支行为：
keyword/review-type/年份过滤、safety/CSM 子集、多源合并去重（OpenAlex + Europe PMC +
Semantic Scholar）、中文主题、大结果集、空结果边界、产物控制（--no-xlsx/--no-html）。

10 个案例（简单 -> 复杂）：
  C1  OpenAlex 最小冒烟（单源最简）
  C2  OpenAlex + review-type 过滤（systematic-review）
  C3  OpenAlex + 年份范围（--year-from/--year-to）
  C4  OpenAlex + safety/CSM 子集（--safety）
  C5  双源（+Europe PMC，MeSH/PMID）
  C6  三源（+Semantic Scholar，可能 429 容错跳过）
  C7  组合过滤（meta-analysis + year + safety）
  C8  中文主题（多语言检索）
  C9  大结果集（--max 100）
  C10 边界：空结果(0 条不崩) + 产物控制(--no-xlsx/--no-html)
  C11 性能/稳定性压测（cancer + safety + 三源 + max 100，守卫 C7 超时回归）

OpenAlex key：技能 .env 已配置（--openalex-key 默认自动加载，验证过 HTTP 200）。
用法：  C:/Tools/anaconda3/python.exe tests/scenario10.py [--cases 1,3,10]
结果：  tests/results/scenario10_<date>.json  +  每 case 日志 scenario10_<date>_cN.log
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))          # tests/
SKILL = os.path.dirname(HERE)                               # ct-literature/
SCRIPTS = os.path.join(SKILL, "scripts")
RESULTS = os.path.join(HERE, "results")
RUNS = os.path.join(HERE, "scenario10_run")
DATE = datetime.date.today().isoformat()
PY = "C:/Tools/anaconda3/python.exe"
os.makedirs(RESULTS, exist_ok=True)
os.makedirs(RUNS, exist_ok=True)


def run_case(out_dir, *args, timeout=300):
    """调用主编排 ct_literature.py；返回 (rc, stdout, stderr)。"""
    os.makedirs(out_dir, exist_ok=True)
    cmd = [PY, os.path.join(SCRIPTS, "ct_literature.py"), *args,
           "--out-dir", out_dir, "--run"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           cwd=SCRIPTS, env=dict(os.environ))
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or ""), (e.stderr or "") + "\n[TIMEOUT]"


def run_case_timed(out_dir, *args, timeout=300):
    """同 run_case，但额外返回墙钟耗时（秒），用于性能/稳定性案例。"""
    import time
    os.makedirs(out_dir, exist_ok=True)
    cmd = [PY, os.path.join(SCRIPTS, "ct_literature.py"), *args,
           "--out-dir", out_dir, "--run"]
    t0 = time.perf_counter()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           cwd=SCRIPTS, env=dict(os.environ))
        rc, so, se = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        rc, so, se = 124, (e.stdout or ""), (e.stderr or "") + "\n[TIMEOUT]"
    elapsed = time.perf_counter() - t0
    return rc, so, se, elapsed


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def exists_nonempty(path):
    return os.path.exists(path) and os.path.getsize(path) > 0


def works_of(out_dir):
    """merged.json 形如 {"count": N, "works": [...]}。"""
    d = load_json(os.path.join(out_dir, "merged.json"))
    if isinstance(d, dict):
        w = d.get("works")
        return w if isinstance(w, list) else []
    return d if isinstance(d, list) else []


def rec_count(out_dir):
    return len(works_of(out_dir))


def source_breakdown(out_dir):
    from collections import Counter
    ws = works_of(out_dir)
    def first_src(w):
        s = w.get("sources")
        if isinstance(s, list) and s:
            return s[0]
        return w.get("source") or "?"
    return dict(Counter(first_src(w) for w in ws))


def std_assert(out_dir, rc, se, label, expect_artifacts=("openalex.json", "merged.json",
                                                         "lit_report.md", "lit_report.xlsx",
                                                         "lit_report.html"),
               expect_nonempty=True):
    """公共断言：rc==0 + 产物齐全 + merged 非空。返回 (ok, detail)。"""
    if rc != 0:
        return False, f"rc={rc}\nSTDERR:\n{se[-1200:]}"
    missing = [f for f in expect_artifacts if not exists_nonempty(os.path.join(out_dir, f))]
    if missing:
        return False, f"产物缺失: {missing}"
    n = rec_count(out_dir)
    if expect_nonempty and n <= 0:
        return False, "merged.json 为空（0 条记录）"
    srcs = source_breakdown(out_dir)
    return True, f"merged={n} sources={srcs}"


# ---------------------------------------------------------------- 案例定义 ---
def c01_oa_min(out):
    rc, so, se = run_case(out, "--topic", "osimertinib", "--max", "5")
    ok, det = std_assert(out, rc, se, "C1")
    # 抽查：记录有 title + year + doi 关键字段
    ws = works_of(out)
    bad = [w for w in ws if not w.get("title") or not w.get("year")]
    return ok, det + f" | missing_title_or_year={len(bad)}"


def c02_review_type(out):
    rc, so, se = run_case(out, "--topic", "osimertinib", "--review-type",
                          "systematic-review")
    ok, det = std_assert(out, rc, se, "C2")
    return ok, det


def c03_year_range(out):
    rc, so, se = run_case(out, "--topic", "pembrolizumab", "--year-from", "2022",
                          "--year-to", "2024")
    ok, det = std_assert(out, rc, se, "C3")
    ws = works_of(out)
    bad = [w for w in ws if not (2022 <= (w.get("year") or 0) <= 2024)]
    extra = f" | out_of_range={len(bad)}"
    if bad:
        ok = False
    return ok, det + extra


def c04_safety(out):
    rc, so, se = run_case(out, "--topic", "osimertinib", "--safety")
    ok, det = std_assert(out, rc, se, "C4")
    ws = works_of(out)
    safety = [w for w in ws if w.get("is_safety")]
    extra = f" | is_safety={len(safety)}"
    # safety 子集可为 0（取决于检索命中），但报告必须含 safety 段落
    md = ""
    try:
        md = open(os.path.join(out, "lit_report.md"), encoding="utf-8").read()
    except Exception:
        pass
    if "Safety" not in md and "安全" not in md:
        ok, extra = False, extra + " | 报告缺 Safety/安全 段落"
    return ok, det + extra


def c05_dual_source(out):
    rc, so, se = run_case(out, "--topic", "osimertinib", "--with-europepmc")
    ok, det = std_assert(out, rc, se, "C5",
                         expect_artifacts=("openalex.json", "europepmc.json", "merged.json",
                                           "lit_report.md", "lit_report.xlsx", "lit_report.html"))
    epmc = load_json(os.path.join(out, "europepmc.json"))
    n_ep = len(epmc.get("works") or []) if isinstance(epmc, dict) else (len(epmc) if isinstance(epmc, list) else 0)
    # 抽查：Europe PMC 记录应带 mesh / pmid 增强字段
    ws = works_of(out)
    ep_recs = [w for w in ws if "EuropePMC" in (w.get("sources") or [])]
    with_mesh = sum(1 for w in ep_recs if w.get("mesh"))
    extra = f" | epmc_raw={n_ep} ep_merged={len(ep_recs)} with_mesh={with_mesh}"
    if n_ep > 0 and len(ep_recs) == 0:
        ok = False
    return ok, det + extra


def c06_three_source(out):
    rc, so, se = run_case(out, "--topic", "cancer immunotherapy",
                          "--with-europepmc", "--with-semantic-scholar")
    # Semantic Scholar 无 key 常 429 -> 技能优雅跳过，semantic_scholar.json 可能缺失；
    # 断言只强制 OA+EP 双源产物，S2 成功或降级均视为正常（不判 FAIL）。
    ok, det = std_assert(out, rc, se, "C6",
                         expect_artifacts=("openalex.json", "europepmc.json",
                                           "merged.json",
                                           "lit_report.md", "lit_report.xlsx", "lit_report.html"))
    ws = works_of(out)
    srcs = source_breakdown(out)
    n_oa = srcs.get("OpenAlex", 0)
    n_ep = srcs.get("EuropePMC", 0)
    s2 = load_json(os.path.join(out, "semantic_scholar.json"))
    n_s2 = len(s2.get("works") or []) if isinstance(s2, dict) else (len(s2) if isinstance(s2, list) else 0)
    extra = f" | oa={n_oa} ep={n_ep} s2={n_s2} (429 跳过属预期)"
    if n_oa == 0 or n_ep == 0:
        ok = False  # OA+EP 双源必须成功；S2 允许降级，但 OA/EP 不可缺一
    return ok, det + extra


def c07_combined(out):
    rc, so, se = run_case(out, "--topic", "metformin", "--review-type",
                          "meta-analysis", "--year-from", "2018", "--safety")
    ok, det = std_assert(out, rc, se, "C7")
    ws = works_of(out)
    bad = [w for w in ws if (w.get("year") or 0) < 2018]
    extra = f" | pre_2018={len(bad)}"
    if bad:
        ok = False
    return ok, det + extra


def c08_chinese(out):
    rc, so, se = run_case(out, "--topic", "肺癌", "--max", "10")
    ok, det = std_assert(out, rc, se, "C8")
    return ok, det


def c09_large(out):
    rc, so, se = run_case(out, "--topic", "cancer immunotherapy", "--max", "100",
                          timeout=420)
    ok, det = std_assert(out, rc, se, "C9")
    n = rec_count(out)
    extra = f" | got={n}"
    if n < 30:
        ok, extra = False, extra + " (期望 >=30)"
    return ok, det + extra


def c10_edge(out):
    """边界组合：空结果不崩 + 产物控制（--no-xlsx/--no-html）。"""
    notes = []
    # 10a: 空结果主题（几乎必然 0 条）-> rc=0 + 报告仍生成
    outa = os.path.join(out, "10a_empty")
    rc_a, so_a, se_a = run_case(outa, "--topic",
                                "zzzqqq_nonexistent_topic_xyz_2026", "--max", "5",
                                timeout=120)
    md_a = os.path.join(outa, "lit_report.md")
    n_a = rec_count(outa)
    notes.append(f"10a empty rc={rc_a} merged={n_a} report={exists_nonempty(md_a)}")
    if rc_a != 0:
        return False, f"10a 空结果应 rc=0 实际 rc={rc_a}\n{so_a[-600:]}{se_a[-600:]}"
    if not exists_nonempty(md_a):
        return False, "10a 空结果时 lit_report.md 未生成"

    # 10b: --no-xlsx --no-html -> 不产出这两个文件
    outb = os.path.join(out, "10b_no_export")
    rc_b, so_b, se_b = run_case(outb, "--topic", "osimertinib", "--max", "5",
                                "--no-xlsx", "--no-html", timeout=180)
    xlsx_b = exists_nonempty(os.path.join(outb, "lit_report.xlsx"))
    html_b = exists_nonempty(os.path.join(outb, "lit_report.html"))
    md_b = exists_nonempty(os.path.join(outb, "lit_report.md"))
    notes.append(f"10b no-export rc={rc_b} xlsx={xlsx_b} html={html_b} md={md_b}")
    if rc_b != 0:
        return False, f"10b --no-xlsx/--no-html 失败 rc={rc_b}\n{so_b[-600:]}{se_b[-600:]}"
    if xlsx_b or html_b:
        return False, f"10b 期望无 xlsx/html 但存在: xlsx={xlsx_b} html={html_b}"
    if not md_b:
        return False, "10b --no-xlsx/--no-html 后 lit_report.md 也未生成"
    return True, " | ".join(notes)


def c11_perf_stress(out):
    """性能/稳定性压测：宽查询 + safety + 三源 + 大结果集，验证不超时且产出有效。

    直接守卫上一轮修复的 C7 回归（重组合查询累计超时被 SIGTERM=124）。
    比 C9（单源大结果）更重：叠加 safety 子集 + 三源全开，制造真实压力。
    附带墙钟计时遥测，可用作 10 轮稳定性矩阵的 timing 数据源。
    """
    rc, so, se, elapsed = run_case_timed(
        out, "--topic", "cancer", "--max", "100", "--safety",
        "--with-europepmc", "--with-semantic-scholar", timeout=420)
    # 主判：必须优雅完成（不出现 rc=124 外层超时 / 非 0 错误）
    if rc != 0:
        return False, f"rc={rc} wall={elapsed:.1f}s (超时/错误)\nSTDERR:\n{se[-1200:]}"
    # 稳定性判：在合理墙钟区间（20s<t<400s），排除瞬崩与卡死逼近外层 420s
    if elapsed < 20:
        return False, f"wall={elapsed:.1f}s 异常偏短（疑似瞬崩/空跑）"
    if elapsed > 400:
        return False, f"wall={elapsed:.1f}s 逼近外层 420s 超时（稳定性风险）"
    # 产出判：merged 有效
    n = rec_count(out)
    if n < 50:
        return False, f"wall={elapsed:.1f}s merged={n} <50（产出不足）"
    # 源分解：OA+EP 必须成功；S2 允许 429 降级
    srcs = source_breakdown(out)
    n_oa = srcs.get("OpenAlex", 0)
    n_ep = srcs.get("EuropePMC", 0)
    s2 = load_json(os.path.join(out, "semantic_scholar.json"))
    n_s2 = len(s2.get("works") or []) if isinstance(s2, dict) else (len(s2) if isinstance(s2, list) else 0)
    extra = f" | wall={elapsed:.1f}s merged={n} oa={n_oa} ep={n_ep} s2={n_s2}"
    if n_oa == 0 or n_ep == 0:
        return False, extra + " | OA/EP 双源缺失"
    return True, extra + " (S2 429 跳过属预期容错)"


CASES = [
    (1,  "OpenAlex 最小冒烟", c01_oa_min),
    (2,  "OpenAlex + review-type 过滤", c02_review_type),
    (3,  "OpenAlex + 年份范围", c03_year_range),
    (4,  "OpenAlex + safety/CSM 子集", c04_safety),
    (5,  "双源（+Europe PMC MeSH/PMID）", c05_dual_source),
    (6,  "三源（+Semantic Scholar 429 容错）", c06_three_source),
    (7,  "组合过滤（meta-analysis+year+safety）", c07_combined),
    (8,  "中文主题", c08_chinese),
    (9,  "大结果集（--max 100）", c09_large),
    (10, "边界（空结果 + --no-xlsx/--no-html）", c10_edge),
    (11, "性能/稳定性压测（cancer+safety+三源+max100）", c11_perf_stress),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", help="comma-separated case numbers")
    args = ap.parse_args()
    sel = {int(x) for x in args.cases.split(",") if x.strip()} if args.cases else None

    results = []
    for num, name, fn in CASES:
        if sel and num not in sel:
            continue
        rec = {"case": num, "name": name, "status": None, "detail": None}
        out = os.path.join(RUNS, f"c{num:02d}")
        os.makedirs(out, exist_ok=True)
        log = os.path.join(RESULTS, f"scenario10_{DATE}_c{num:02d}.log")
        try:
            ok, det = fn(out)
            rec["status"] = "PASS" if ok else "FAIL"
            rec["detail"] = det
        except Exception as e:
            rec["status"] = "FAIL"
            rec["detail"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}"
        print(f"[case{num:02d}] {rec['status']:4s} {name} :: {rec['detail']}")
        results.append(rec)

    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    summary = {"date": DATE, "suite": "scenario10", "total": len(results),
               "PASS": n_pass, "FAIL": n_fail, "cases": results}
    out_path = os.path.join(RESULTS, f"scenario10_{DATE}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n=== SCENARIO10 {DATE}: PASS={n_pass} FAIL={n_fail} ===")
    print(f"results -> {out_path}")
    if n_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
