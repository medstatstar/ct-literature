#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_cases.py — ct-literature 离线回归/场景测试 harness（无需联网）

设计要点
========
ct_literature.run() 内部硬编码 run=True，CLI 缺 --run 时只打印计划、不进流水线；
因此「纯 CLI PREVIEW」无法覆盖 report/xlsx/html/normalize 的真实崩溃点。

本 harness 采用 **mock http_utils.get_json** 的方式：喂入真实形状的 API 夹具 JSON，
让 run() 跑完整真实流水线（fetch._extract → normalize.merge → report.render →
export_xlsx → export_html），但零网络、零 key 消耗。这样能在 PREVIEW/不联网前提下，
真正触发下游渲染分支（safety 块、MeSH、dedupe、中文、None 年份、retracted 等）。

两阶段 / 每案例
===============
  A) CLI PREVIEW：以该案例参数构造 sys.argv（不带 --run）调用 main()，校验
     argparse 接受度 + 预览打印，不触发任何网络/流水线。
  B) Mocked 完整运行：直接调用 run()，所有源走 mock；校验 md/xlsx/html 产物存在且非空。

用法
====
  python tests/run_cases.py            # 跑全部 10 例
  python tests/run_cases.py --case 3   # 只跑第 3 例
  python tests/run_cases.py --quiet    # 仅汇总表

退出码：0 = 全部通过；1 = 有失败。
"""
import argparse
import copy
import io
import os
import sys
import traceback
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL_ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import http_utils  # noqa: E402  (必须在 patch 前导入)

# ───────────────────────────────────────────────────────────────────────────
# 真实形状的 API 夹具（mock 掉 http_utils.get_json 后返回）
# ───────────────────────────────────────────────────────────────────────────
OPENALEX_FIXTURE = {
    "meta": {"count": 6},
    "results": [
        {  # 1) 字段最全：abstract/概念/关键词/资助/biblio/oa_pdf/ids
            "id": "https://openalex.org/W1", "doi": "https://doi.org/10.1000/oa1",
            "title": "Osimertinib in EGFR-mutated NSCLC: a phase III trial",
            "publication_year": 2021, "publication_date": "2021-06-01", "type": "article",
            "cited_by_count": 342,
            "primary_location": {"source": {"display_name": "Nature Medicine"},
                                 "landing_page_url": "https://nature.com/oa1"},
            "authorships": [{"author": {"display_name": "A. Smith"}},
                            {"author": {"display_name": "B. Lee"}},
                            {"author": {"display_name": "C. Wang"}}],
            "abstract_inverted_index": {"osimertinib": [0, 5], "improves": [1],
                                        "survival": [2], "in": [3], "nsclc": [4]},
            "ids": {"pubmed": "33012345", "pmcid": "PMC8012345", "openalex": "W1"},
            "concepts": [{"display_name": "Lung cancer", "score": 0.9},
                         {"display_name": "EGFR", "score": 0.7}],
            "keywords": [{"display_name": "osimertinib"}, {"display_name": "NSCLC"}],
            "funders": [{"display_name": "NIH"}, {"display_name": "AstraZeneca"}],
            "best_oa_location": {"pdf_url": "https://oa.org/oa1.pdf",
                                 "landing_page_url": "https://oa.org/oa1"},
            "biblio": {"volume": "12", "issue": "3", "first_page": "234"},
            "language": "en", "is_retracted": False,
        },
        {  # 2) 无摘要、review 类型
            "id": "https://openalex.org/W2", "doi": "https://doi.org/10.1000/oa2",
            "title": "Systematic review of EGFR inhibitors",
            "publication_year": 2020, "publication_date": "2020-02-10", "type": "review",
            "cited_by_count": 88,
            "primary_location": {"source": {"display_name": "Cochrane"}},
            "authorships": [{"author": {"display_name": "D. Kim"}}],
            "abstract_inverted_index": None, "ids": {"openalex": "W2"},
            "concepts": [], "keywords": [], "funders": [],
            "best_oa_location": {}, "biblio": {}, "language": "en", "is_retracted": False,
        },
        {  # 3) safety 词、无 doi、retracted
            "id": "https://openalex.org/W3", "doi": None,
            "title": "Adverse event of osimertinib: a case report of toxicity",
            "publication_year": 2022, "publication_date": "2022-04-15", "type": "article",
            "cited_by_count": 12,
            "primary_location": {"source": {"display_name": "BMJ Case Reports"}},
            "authorships": [{"author": {"display_name": "E. Chen"}},
                            {"author": {"display_name": "F. Garcia"}}],
            "abstract_inverted_index": {"case": [0], "report": [1], "toxicity": [2]},
            "ids": {"openalex": "W3"}, "concepts": [], "keywords": [], "funders": [],
            "best_oa_location": {}, "biblio": {}, "language": "en", "is_retracted": True,
        },
        {  # 4) 中文标题、无摘要、2023
            "id": "https://openalex.org/W4", "doi": "https://doi.org/10.1000/oa4",
            "title": "奥希替尼治疗非小细胞肺癌的荟萃分析",
            "publication_year": 2023, "publication_date": "2023-09-01", "type": "article",
            "cited_by_count": 5,
            "primary_location": {"source": {"display_name": "中华肿瘤杂志"}},
            "authorships": [{"author": {"display_name": "张伟"}},
                            {"author": {"display_name": "李娜"}}],
            "abstract_inverted_index": None, "ids": {"openalex": "W4"},
            "concepts": [], "keywords": [], "funders": [],
            "best_oa_location": {}, "biblio": {}, "language": "zh", "is_retracted": False,
        },
        {  # 5) 与 EPMC 夹具共享 DOI → 触发去重合并
            "id": "https://openalex.org/W5", "doi": "https://doi.org/10.1000/shared",
            "title": "Shared-DOI work (OpenAlex primary)",
            "publication_year": 2021, "type": "article", "cited_by_count": 50,
            "primary_location": {"source": {"display_name": "Journal A"}},
            "authorships": [{"author": {"display_name": "G. Park"}}],
            "abstract_inverted_index": {"shared": [0]}, "ids": {"openalex": "W5"},
            "concepts": [], "keywords": [], "funders": [],
            "best_oa_location": {}, "biblio": {}, "language": "en", "is_retracted": False,
        },
        {  # 6) 缺失年份(year=None)、空作者
            "id": "https://openalex.org/W6", "doi": "https://doi.org/10.1000/oa6",
            "title": "Unnamed early preclinical study",
            "publication_year": None, "type": "article", "cited_by_count": 1,
            "primary_location": {"source": {"display_name": "Preprint Server"}},
            "authorships": [], "abstract_inverted_index": None, "ids": {"openalex": "W6"},
            "concepts": [], "keywords": [], "funders": [],
            "best_oa_location": {}, "biblio": {}, "language": "en", "is_retracted": False,
        },
    ],
}

EPMC_FIXTURE = {
    "hitCount": 3,
    "resultList": {"result": [
        {  # 与 OA W5 共享 DOI → 去重；含 MeSH/affiliation/biblio/oa
            "id": "PMC1", "pmid": "31000001", "pmcid": "PMC7000001", "doi": "10.1000/shared",
            "title": "Shared-DOI work (Europe PMC enriched)",
            "authorList": {"author": [
                {"fullName": "G. Park"},
                {"fullName": "H. Yamada",
                 "authorAffiliationDetailsList": {"authorAffiliation": [
                     {"affiliation": "University of X"}]}}]},
            "pubYear": "2021",
            "journalInfo": {"journal": {"title": "Journal A", "isoabbreviation": "J A"},
                            "volume": "5", "issue": "2"},
            "citedByCount": 60,
            "meshHeadingList": {"meshHeading": [
                {"descriptorName": "Lung Neoplasms"},
                {"descriptorName": "Protein Kinase Inhibitors"}]},
            "abstractText": "This study examines the shared-DOI work in detail.",
            "fullTextUrlList": {"fullTextUrl": [
                {"url": "https://europepmc.org/pdf1", "documentStyle": "pdf"}]},
        },
        {  # 无 MeSH、无 doi、2019
            "id": "PMC2", "pmid": "30000002", "pmcid": "PMC6000002", "doi": None,
            "title": "Older observational study without identifiers",
            "authorList": {"author": [{"fullName": "I. Novak"}]},
            "pubYear": "2019", "journalInfo": {"journal": {"title": "Old Journal"}},
            "citedByCount": 20, "abstractText": "Old abstract text.",
        },
        {  # 标题含 safety
            "id": "PMC3", "pmid": "32000003", "pmcid": "PMC6500003", "doi": "10.1000/epmc3",
            "title": "Safety of immunotherapy: adverse events review",
            "authorList": {"author": [{"fullName": "J. Brown"}]},
            "pubYear": "2022", "journalInfo": {"journal": {"title": "Safety Journal"}},
            "citedByCount": 30,
            "meshHeadingList": {"meshHeading": [{"descriptorName": "Immunotherapy"}]},
            "abstractText": "Safety review abstract.",
            "fullTextUrlList": {"fullTextUrl": [
                {"url": "https://europepmc.org/pdf3", "documentStyle": "pdf"}]},
        },
    ]},
}

S2_FIXTURE = {
    "total": 3,
    "data": [
        {"paperId": "S1", "title": "Semantic Scholar work one",
         "authors": [{"name": "K. Ali"}, {"name": "L. Liu"}], "year": 2021,
         "venue": "Conf A", "externalIds": {"DOI": "10.1000/s1", "PubMed": "33000004"},
         "citationCount": 40, "abstract": "Semantic abstract one.",
         "publicationDate": "2021-03-03",
         "openAccessPdf": {"url": "https://s2.org/s1.pdf"}},
        {"paperId": "S2", "title": "Semantic work with missing year",
         "authors": [{"name": "M. Roy"}], "year": None, "venue": "Conf B",
         "externalIds": {"DOI": None, "PubMed": None}, "citationCount": 0,
         "abstract": None, "publicationDate": None, "openAccessPdf": None},
        {"paperId": "S3", "title": "Safety signals in rare disease: adverse event mining",
         "authors": [{"name": "N. Patel"}], "year": 2020, "venue": "Conf C",
         "externalIds": {"DOI": "10.1000/s3"}, "citationCount": 10,
         "abstract": "Safety mining abstract.", "publicationDate": "2020-01-01",
         "openAccessPdf": None},
    ],
}


def _fake_get_json(url, headers=None, timeout=45, max_retries=4, backoff=2.0):
    """Mock：按 URL host 路由到对应夹具（深拷贝，避免被测代码改动夹具）。"""
    if "openalex.org" in url:
        return copy.deepcopy(OPENALEX_FIXTURE)
    if "europepmc" in url:
        return copy.deepcopy(EPMC_FIXTURE)
    if "semanticscholar" in url:
        return copy.deepcopy(S2_FIXTURE)
    # 意外 URL：返回空结构，不触发网络
    return {"results": [], "resultList": {"result": []}, "data": []}


# ───────────────────────────────────────────────────────────────────────────
# 10 个由简到繁的场景案例
# ───────────────────────────────────────────────────────────────────────────
CASES = [
    # 1 最简：单源 OpenAlex，默认全类型
    {"id": 1, "desc": "最简·OpenAlex 默认",
     "topic": "aspirin", "review_type": "all", "safety": False,
     "with_europepmc": False, "with_semantic_scholar": False, "max_results": 30},
    # 2 安全偏向
    {"id": 2, "desc": "安全偏向·osimertinib --safety",
     "topic": "osimertinib", "review_type": "all", "safety": True,
     "with_europepmc": False, "with_semantic_scholar": False, "max_results": 30},
    # 3 review-type 过滤
    {"id": 3, "desc": "综述类型·metformin systematic-review",
     "topic": "metformin", "review_type": "systematic-review", "safety": False,
     "with_europepmc": False, "with_semantic_scholar": False, "max_results": 30},
    # 4 年份区间
    {"id": 4, "desc": "年份区间·warfarin 2018–2022",
     "topic": "warfarin", "review_type": "all", "safety": False,
     "year_from": 2018, "year_to": 2022,
     "with_europepmc": False, "with_semantic_scholar": False, "max_results": 30},
    # 5 叠加 Europe PMC（MeSH）
    {"id": 5, "desc": "叠加 EuropePMC·pembrolizumab",
     "topic": "pembrolizumab", "review_type": "all", "safety": False,
     "with_europepmc": True, "with_semantic_scholar": False, "max_results": 30},
    # 6 叠加 Semantic Scholar（引用）
    {"id": 6, "desc": "叠加 SemanticScholar·nivolumab",
     "topic": "nivolumab", "review_type": "all", "safety": False,
     "with_europepmc": False, "with_semantic_scholar": True, "max_results": 30},
    # 7 三源 + safety（去重/MeSH/资助/safety 全触发）
    {"id": 7, "desc": "三源+safety·bevacizumab",
     "topic": "bevacizumab", "review_type": "all", "safety": True,
     "with_europepmc": True, "with_semantic_scholar": True, "max_results": 30},
    # 8 中文检索词
    {"id": 8, "desc": "中文主题·奥希替尼",
     "topic": "奥希替尼", "review_type": "all", "safety": False,
     "with_europepmc": True, "with_semantic_scholar": False, "max_results": 30},
    # 9 大 max（分页边界）
    {"id": 9, "desc": "大 max=200 分页边界·cancer immunotherapy",
     "topic": "cancer immunotherapy", "review_type": "all", "safety": False,
     "with_europepmc": True, "with_semantic_scholar": True, "max_results": 200},
    # 10 全标志窄主题（case-report + safety + 三源 + 年份）
    {"id": 10, "desc": "全标志窄主题·rare disease gene therapy",
     "topic": "rare disease gene therapy", "review_type": "case-report",
     "safety": True, "year_from": 2020, "year_to": 2024,
     "with_europepmc": True, "with_semantic_scholar": True, "max_results": 50},
]


def _cli_args(case):
    a = ["ct_literature.py", "--topic", case["topic"],
         "--review-type", case["review_type"], "--max", str(case["max_results"])]
    if case.get("year_from"):
        a += ["--year-from", str(case["year_from"])]
    if case.get("year_to"):
        a += ["--year-to", str(case["year_to"])]
    if case.get("safety"):
        a += ["--safety"]
    if case.get("with_europepmc"):
        a += ["--with-europepmc"]
    if case.get("with_semantic_scholar"):
        a += ["--with-semantic-scholar"]
    return a  # 不带 --run → PREVIEW


def run_case(case, out_base, quiet=False):
    import ct_literature  # 延迟导入，确保 patch 已生效

    cid = case["id"]
    out_dir = os.path.join(out_base, "case%02d" % cid)
    os.makedirs(out_dir, exist_ok=True)
    rec = {"id": cid, "desc": case["desc"], "preview_ok": None,
           "run_ok": None, "outputs": {}, "warn": [], "error": None}

    # ── 阶段 A：CLI PREVIEW（argparse + 预览打印，不进流水线）──
    buf = io.StringIO()
    old_argv, old_stdout = sys.argv, sys.stdout
    sys.argv = _cli_args(case)
    try:
        sys.stdout = buf
        ct_literature.main()
        out = buf.getvalue()
        rec["preview_ok"] = ("[PREVIEW]" in out)
    except Exception as e:
        rec["preview_ok"] = False
        rec["error"] = "PREVIEW: " + traceback.format_exc()
    finally:
        sys.stdout = old_stdout
        sys.argv = old_argv

    # ── 阶段 B：Mocked 完整流水线 ──
    buf2 = io.StringIO()
    try:
        sys.stdout = buf2
        ct_literature.run(
            topic=case["topic"], review_type=case["review_type"],
            year_from=case.get("year_from"), year_to=case.get("year_to"),
            safety=case.get("safety", False), max_results=case["max_results"],
            with_europepmc=case.get("with_europepmc", False),
            with_semantic_scholar=case.get("with_semantic_scholar", False),
            out_dir=out_dir, make_xlsx=True, make_html=True, openalex_key=None)
        log = buf2.getvalue()
        for line in log.splitlines():
            if "[WARN]" in line or "Warning" in line:
                rec["warn"].append(line.strip())
        # 产物校验
        for fn in ("lit_report.md", "lit_report.xlsx", "lit_report.html"):
            p = os.path.join(out_dir, fn)
            rec["outputs"][fn] = (os.path.exists(p) and os.path.getsize(p) > 0)
        rec["run_ok"] = all(rec["outputs"].values())
    except Exception as e:
        rec["run_ok"] = False
        rec["error"] = (rec.get("error") or "") + "RUN: " + traceback.format_exc()
    finally:
        sys.stdout = old_stdout

    # xlsx 有效性（openpyxl 可用时）
    xlsx_path = os.path.join(out_dir, "lit_report.xlsx")
    if rec["outputs"].get("lit_report.xlsx"):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(xlsx_path)
            rec["xlsx_sheets"] = wb.sheetnames
        except Exception as e:
            rec["xlsx_sheets"] = "LOAD_ERR: %s" % e

    if not quiet:
        flag = "OK " if (rec["preview_ok"] and rec["run_ok"]) else "FAIL"
        print("[%s] case %2d %-44s preview=%s run=%s warn=%d"
              % (flag, cid, case["desc"], rec["preview_ok"], rec["run_ok"],
                 len(rec["warn"])))
    return rec


def main():
    ap = argparse.ArgumentParser(description="ct-literature offline scenario harness")
    ap.add_argument("--case", type=int, help="只跑指定案例 id (1-10)")
    ap.add_argument("--quiet", action="store_true", help="仅打印汇总表")
    args = ap.parse_args()

    # 安装 mock（必须在导入 ct_literature 相关 fetch 之后、run 之前）
    http_utils.get_json = _fake_get_json

    out_base = os.path.join(HERE, "out")
    os.makedirs(out_base, exist_ok=True)

    cases = [c for c in CASES if (args.case is None or c["id"] == args.case)]
    results = [run_case(c, out_base, quiet=args.quiet) for c in cases]

    # ── 汇总 ──
    print("\n" + "=" * 78)
    print("ct-literature 场景回归汇总  %s" % datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 78)
    hdr = "%-4s %-44s %-7s %-7s %-6s" % ("ID", "场景", "PREV", "RUN", "WARN")
    print(hdr)
    print("-" * 78)
    fails = 0
    for r in results:
        prev = "Y" if r["preview_ok"] else "N"
        rn = "Y" if r["run_ok"] else "N"
        if not (r["preview_ok"] and r["run_ok"]):
            fails += 1
        print("%-4d %-44s %-7s %-7s %-6d" % (r["id"], r["desc"][:44], prev, rn, len(r["warn"])))
        if r["error"]:
            print("      ↳ ERROR:\n%s" % "\n".join("        " + ln for ln in r["error"].splitlines()[-12:]))
        if r.get("xlsx_sheets"):
            print("      xlsx sheets: %s" % r["xlsx_sheets"])
    print("-" * 78)
    print("总计 %d 例，失败 %d 例，warning 合计 %d 条"
          % (len(results), fails, sum(len(r["warn"]) for r in results)))
    # 写出结果 JSON（便于后续比对/CI）
    with open(os.path.join(out_base, "results.json"), "w", encoding="utf-8") as f:
        import json
        json.dump({"generated": datetime.now().isoformat(), "results": results},
                  f, ensure_ascii=False, indent=2)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
