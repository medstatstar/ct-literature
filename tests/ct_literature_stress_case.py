#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ct-literature · 性能/稳定性测试案例（独立可运行版）
==================================================

一个不依赖 scenario10.py 框架的最小自包含测试案例。
直接调用主编排 scripts/ct_literature.py，纯真实联网，
覆盖「宽主题 + safety + 三源」三重压力，守卫 C7 超时回归。

你（用户）自己运行即可：
    python tests/ct_literature_stress_case.py
    python tests/ct_literature_stress_case.py --topic "diabetes" --max 200
    python tests/ct_literature_stress_case.py --no-run     # 只打印将执行的命令，不真正运行

判定标准：
    [1] rc == 0              —— 不允许出现 124 外层超时（C7 回归直接暴露）
    [2] 20s < wall < 400s   —— 排除瞬崩空跑，也排除卡死逼近超时
    [3] merged >= 50        —— 有效产出，非空跑
    [4] OpenAlex + EuropePMC 双源必须成功
    [5] Semantic Scholar 允许 429 降级（s2=0 容错，不判 FAIL）

注：数据全部真实联网（OpenAlex / Europe PMC / Semantic Scholar），
   OpenAlex API key 由技能 .env 自动加载，无需手动传参。
   本脚本位于 <ct-literature>/tests/ 下即可自动定位主编排脚本。
"""

import os
import sys
import json
import time
import argparse
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL_ROOT, "scripts")
ORCH = os.path.join(SCRIPTS, "ct_literature.py")


def pick_python():
    """优先用 Anaconda python（技能约定），回退到当前解释器。"""
    for p in (r"C:\Tools\anaconda3\python.exe", sys.executable):
        if p and os.path.exists(p):
            return p
    return sys.executable


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def source_works(out_dir, name):
    """单源产物统一为 {'works': [...]} 结构；缺失或解析失败返回空列表。"""
    d = load_json(os.path.join(out_dir, name))
    if isinstance(d, dict):
        return d.get("works") or []
    if isinstance(d, list):
        return d
    return []


def build_cmd(topic, max_n, out_dir):
    return [pick_python(), ORCH,
            "--topic", topic, "--max", str(max_n),
            "--safety", "--with-europepmc", "--with-semantic-scholar",
            "--out-dir", out_dir, "--run"]


def main():
    ap = argparse.ArgumentParser(
        description="ct-literature 性能/稳定性测试案例（独立可运行）")
    ap.add_argument("--topic", default="cancer",
                    help="检索主题（默认 cancer，超宽主题）")
    ap.add_argument("--max", type=int, default=100,
                    help="最大结果数（默认 100）")
    ap.add_argument("--out-dir", default=None,
                    help="输出目录（默认 tests/_case_run）")
    ap.add_argument("--timeout", type=int, default=400,
                    help="外层超时秒数（默认 400）")
    ap.add_argument("--no-run", action="store_true",
                    help="只打印将执行的命令，不真正运行")
    args = ap.parse_args()

    out_dir = args.out_dir or os.path.join(HERE, "_case_run")
    cmd = build_cmd(args.topic, args.max, out_dir)

    if args.no_run:
        print("将执行以下命令（--no-run 模式，未真实运行）：")
        print("  " + " ".join(cmd))
        print(f"\n输出目录：{out_dir}")
        print("取消 --no-run 即可真实联网运行。")
        return

    if not os.path.exists(ORCH):
        print(f"[FATAL] 找不到主编排脚本：{ORCH}")
        print("请确认本脚本位于 <ct-literature>/tests/ 目录下。")
        sys.exit(2)

    os.makedirs(out_dir, exist_ok=True)

    print(">> 执行命令：")
    print("   " + " ".join(cmd))
    print()

    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=args.timeout, cwd=SCRIPTS)
        rc = p.returncode
        stderr = p.stderr
    except subprocess.TimeoutExpired as e:
        wall = time.time() - t0
        print(f"[TIMEOUT] 进程在 {args.timeout}s 后被杀（SIGTERM），rc 视为 124")
        rc, stderr, wall = 124, "[TIMEOUT]", wall
    else:
        wall = time.time() - t0

    # ---- 断言 ----
    checks = []

    # [1] rc == 0
    checks.append(("rc==0（无 124 外层超时）", rc == 0, f"rc={rc}"))

    # [2] 墙钟窗口
    in_window = 20 < wall < args.timeout
    checks.append(("耗时 20s<t<400s（非瞬崩/非卡死）", in_window, f"wall={wall:.1f}s"))

    # 读取产物
    merged = load_json(os.path.join(out_dir, "merged.json")) or {}
    mworks = merged.get("works") or []
    oa = source_works(out_dir, "openalex.json")
    ep = source_works(out_dir, "europepmc.json")
    s2 = source_works(out_dir, "semantic_scholar.json")

    # [3] merged >= 50
    checks.append(("merged>=50（有效产出）", len(mworks) >= 50, f"merged={len(mworks)}"))

    # [4] OA + EP 双源成功
    checks.append(("OpenAlex 源成功", len(oa) > 0, f"oa={len(oa)}"))
    checks.append(("EuropePMC 源成功", len(ep) > 0, f"ep={len(ep)}"))

    # [5] S2 容错（允许 0）
    checks.append(("Semantic Scholar 容错（允许 0）", True,
                   f"s2={len(s2)}（429 跳过属预期容错）"))

    # ---- 报告 ----
    print("=" * 60)
    print("ct-literature 性能/稳定性案例 · 结果")
    print("=" * 60)
    print(f"主题      : {args.topic}")
    print(f"最大结果  : {args.max}")
    print(f"耗时      : {wall:.1f}s")
    print(f"merged    : {len(mworks)}  (oa={len(oa)} ep={len(ep)} s2={len(s2)})")
    print("-" * 60)
    ok_all = True
    for name, ok, detail in checks:
        mark = "PASS" if ok else "FAIL"
        if not ok:
            ok_all = False
        print(f"  [{mark}] {name}  ::  {detail}")
    print("-" * 60)
    print(f"  总判定  : {'✅ 全部通过' if ok_all else '❌ 存在失败项'}")
    print("=" * 60)

    if not ok_all:
        if stderr:
            print("\n[stderr 尾部]\n" + stderr[-1500:])
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
