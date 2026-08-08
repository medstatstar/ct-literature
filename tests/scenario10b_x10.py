#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scenario10b_x10.py - 对抗案例集（scenario10b）N 轮真实重复执行。

复用 scenario10b 的 10 个对抗案例，每轮独立产物目录 tests/scenario10b_run/r{NN}，
汇总「案例 x 轮次」稳定性矩阵，专捕间歇性失败（外网抖动 / 429 / 空结果）。

用法：  C:/Tools/anaconda3/python.exe tests/scenario10b_x10.py [--rounds 10]
结果：  tests/results/scenario10b_x10_<date>.json + 每轮 .log
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
RUNS = os.path.join(HERE, "scenario10b_run")
DATE = datetime.date.today().isoformat()

sys.path.insert(0, HERE)
import scenario10b as S  # noqa: E402

os.makedirs(RESULTS, exist_ok=True)
os.makedirs(RUNS, exist_ok=True)


def run_round(idx, total):
    rdir = os.path.join(RUNS, f"r{idx:02d}")
    os.makedirs(rdir, exist_ok=True)
    log = os.path.join(RESULTS, f"scenario10b_x10_{DATE}_r{idx:02d}.log")
    recs = []
    t0 = time.time()
    with open(log, "w", encoding="utf-8") as lf:
        lf.write(f"=== round {idx}/{total} | {DATE} ===\n")
        for num, name, fn in S.CASES:
            out = os.path.join(rdir, f"b{num:02d}")
            os.makedirs(out, exist_ok=True)
            rec = {"case": num, "name": name, "status": None, "detail": None}
            try:
                ok, det = fn(out)
                rec["status"] = "PASS" if ok else "FAIL"
                rec["detail"] = det
            except Exception as e:
                rec["status"] = "FAIL"
                rec["detail"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}"
            line = f"[r{idx:02d}/B{num:02d}] {rec['status']:4s} {name} :: {rec['detail']}"
            print(line, flush=True)
            lf.write(line + "\n")
            lf.flush()
            recs.append(rec)
    dt = time.time() - t0
    npass = sum(1 for r in recs if r["status"] == "PASS")
    print(f"--- round {idx}/{total}: PASS={npass}/{len(recs)} elapsed={dt:.1f}s ---",
          flush=True)
    return recs, dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=10)
    args = ap.parse_args()

    rounds_detail = []
    per_case = {num: [] for num, _, _ in S.CASES}
    t_all = time.time()
    for i in range(1, args.rounds + 1):
        recs, dt = run_round(i, args.rounds)
        rounds_detail.append({"round": i, "elapsed_s": round(dt, 1), "cases": recs})
        for r in recs:
            per_case[r["case"]].append(r["status"])

    by_case = []
    intermittent = []
    for num, name, _ in S.CASES:
        st = per_case[num]
        npass = st.count("PASS")
        stable = npass == len(st)
        inter = 0 < npass < len(st)
        if inter:
            intermittent.append(num)
        by_case.append({"case": num, "name": name, "pass": npass,
                        "fail": len(st) - npass, "total": len(st),
                        "stable": stable, "intermittent": inter,
                        "statuses": st})
    total_runs = sum(len(v) for v in per_case.values())
    total_pass = sum(v.count("PASS") for v in per_case.values())
    summary = {
        "date": DATE, "suite": "scenario10b_x10", "rounds": args.rounds,
        "total_runs": total_runs, "total_pass": total_pass,
        "total_fail": total_runs - total_pass,
        "intermittent_cases": intermittent,
        "elapsed_total_s": round(time.time() - t_all, 1),
        "by_case": by_case, "rounds_detail": rounds_detail,
    }
    p = os.path.join(RESULTS, f"scenario10b_x10_{DATE}.json")
    json.dump(summary, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n=== SCENARIO10B x{args.rounds}: PASS={total_pass}/{total_runs} "
          f"intermittent={intermittent} ===")
    print("results ->", p)
    if total_pass != total_runs:
        sys.exit(1)


if __name__ == "__main__":
    main()
