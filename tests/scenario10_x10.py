#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scenario10_x10.py - ct-literature 真实联网稳定性回归（N 轮 × 10 案例）。

复用 scenario10.py 的 10 个案例函数（c01..c10），每轮重新真实联网执行，
独立产物目录 tests/scenario10_run/r{NN}/c{MM}，最终汇总"案例×轮次"稳定性矩阵，
专门捕获间歇性失败（同一案例某些轮 PASS、某些轮 FAIL）。

数据源均为真实外部 API：OpenAlex（key 走 .env）+ Europe PMC + Semantic Scholar。
注意：ct-literature 当前无 coze 端点（coze 在 ct-registry 技能），故不含 coze 调用。

用法：  C:/Tools/anaconda3/python.exe tests/scenario10_x10.py [--rounds 10]
结果：  tests/results/scenario10_x10_<date>.json
        tests/results/scenario10_x10_<date>_r{NN}.log （每轮明细）
"""
import argparse
import datetime
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
RUNS = os.path.join(HERE, "scenario10_run")
DATE = datetime.date.today().isoformat()

# 复用 scenario10 的 10 案例定义与底层工具
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "adapters"))
from scenario10 import CASES, works_of, rec_count  # noqa: E402

os.makedirs(RESULTS, exist_ok=True)
os.makedirs(RUNS, exist_ok=True)


def run_round(round_idx, rounds_total):
    """执行一轮（10 案例），返回该轮结果列表 + 每案例 merged 条数。"""
    rdir = os.path.join(RUNS, f"r{round_idx:02d}")
    os.makedirs(rdir, exist_ok=True)
    log = os.path.join(RESULTS, f"scenario10_x10_{DATE}_r{round_idx:02d}.log")
    recs = []
    t0 = time.time()
    with open(log, "w", encoding="utf-8") as lf:
        lf.write(f"=== round {round_idx}/{rounds_total} | {DATE} ===\n")
        for num, name, fn in CASES:
            out = os.path.join(rdir, f"c{num:02d}")
            rec = {"case": num, "name": name, "status": None, "detail": None,
                   "merged": None}
            try:
                ok, det = fn(out)
                rec["status"] = "PASS" if ok else "FAIL"
                rec["detail"] = det
                rec["merged"] = rec_count(out)
            except Exception as e:
                rec["status"] = "FAIL"
                rec["detail"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}"
                rec["merged"] = rec_count(out)
            line = f"[r{round_idx:02d}/c{num:02d}] {rec['status']:4s} {name} :: {rec['detail']}"
            print(line)
            lf.write(line + "\n")
            lf.flush()
            recs.append(rec)
    dt = time.time() - t0
    npass = sum(1 for r in recs if r["status"] == "PASS")
    print(f"--- round {round_idx}/{rounds_total} done: PASS={npass}/{len(recs)} "
          f"elapsed={dt:.1f}s ---")
    return recs, dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=10, help="重复轮数（默认 10）")
    args = ap.parse_args()
    ROUNDS = args.rounds

    all_rounds = []
    per_case_status = {num: [] for num, _, _ in CASES}
    per_case_merged = {num: [] for num, _, _ in CASES}
    t_total = time.time()

    for ri in range(1, ROUNDS + 1):
        recs, dt = run_round(ri, ROUNDS)
        all_rounds.append({"round": ri, "elapsed_s": round(dt, 1), "cases": recs})
        for r in recs:
            per_case_status[r["case"]].append(r["status"])
            per_case_merged[r["case"]].append(r["merged"])

    # ---- 稳定性汇总 ----
    case_reports = []
    for num, name, _ in CASES:
        statuses = per_case_status[num]
        merged = per_case_merged[num]
        n_pass = statuses.count("PASS")
        intermittent = n_pass > 0 and n_pass < len(statuses)
        case_reports.append({
            "case": num, "name": name,
            "pass": n_pass, "fail": len(statuses) - n_pass,
            "total": len(statuses),
            "stable": (n_pass == len(statuses)),
            "intermittent": intermittent,
            "merged_counts": merged,
            "merged_min": min(m for m in merged if m is not None) if merged else None,
            "merged_max": max(m for m in merged if m is not None) if merged else None,
        })

    total_runs = ROUNDS * len(CASES)
    total_pass = sum(cr["pass"] for cr in case_reports)
    total_fail = total_runs - total_pass
    intermittent_cases = [cr["case"] for cr in case_reports if cr["intermittent"]]
    unstable_cases = [cr["case"] for cr in case_reports if not cr["stable"]]

    summary = {
        "date": DATE,
        "suite": "scenario10_x10",
        "rounds": ROUNDS,
        "total_runs": total_runs,
        "total_pass": total_pass,
        "total_fail": total_fail,
        "intermittent_cases": intermittent_cases,
        "unstable_cases": unstable_cases,
        "elapsed_total_s": round(time.time() - t_total, 1),
        "by_case": case_reports,
        "rounds_detail": all_rounds,
    }
    out_path = os.path.join(RESULTS, f"scenario10_x10_{DATE}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n=== SCENARIO10_x10 {DATE}: rounds={ROUNDS} "
          f"runs={total_runs} PASS={total_pass} FAIL={total_fail} ===")
    print(f"intermittent_cases={intermittent_cases} unstable_cases={unstable_cases}")
    print(f"results -> {out_path}")
    # 有不稳定/失败则非零退出，便于 CI 捕获
    sys.exit(1 if (total_fail or intermittent_cases) else 0)


if __name__ == "__main__":
    main()
