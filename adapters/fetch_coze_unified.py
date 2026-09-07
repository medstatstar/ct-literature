#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_coze_unified.py — 文献检索统一 Coze 客户端（ct-literature 所有文献检索的外发出口）

WHY / 设计动机
─────────────
把 ct-literature 的「本地文献检索」动作外发到 Coze 服务端（轻本地端策略）：
  - OpenAlex / Europe PMC / bioRxiv / medRxiv / Semantic Scholar / arXiv
  - 6 个 source 共用同一端点 ct-search.coze.site/run
  - 服务端用 requests 直连各公共 API，回传结构化检索结果
  - 本地侧（ct_literature.py）做合并去重（normalize.py 保留本地）

向后兼容（100% 保证）：
  - 新增 source 全部是"增量追加"，不修改 Coze 端已有逻辑
  - 本地端 CLI 接口不变，输出格式不变
  - fetch_*.py 完整保留，作为 --offline 兜底
  - Coze 不可用时自动降级到本地 fetch（老版本行为）

飞书日志开关：
  - 中间调用（6 个 source 并行检索）传 log_feishu=False → 不记飞书
  - 最终汇总调用传 log_feishu=True → 只记一条汇总
  - 老版本终端不传此字段 → 默认 True → 行为不变

用法：
  python adapters/fetch_coze_unified.py --source openalex --keyword "osimertinib" --run
  python adapters/fetch_coze_unified.py --source europepmc --keyword "diabetes" --year-from 2020 --run
  python adapters/fetch_coze_unified.py --source biorxiv --keyword "covid" --offline  # 本地兜底
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

# ── 路径设置 ──────────────────────────────────────────────────────────────
_ADAPTERS_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_ROOT = os.path.dirname(_ADAPTERS_DIR)
_CT_REGISTRY_SKILL = os.path.expanduser("~/.workbuddy/skills/ct-registry")

# 确保 ct-registry/adapters 在 sys.path，以便复用 endpoint_token.py
if os.path.isdir(os.path.join(_CT_REGISTRY_SKILL, "adapters")):
    sys.path.insert(0, os.path.join(_CT_REGISTRY_SKILL, "adapters"))

# 本技能 scripts/ 也入路径：本地兜底模块（fetch_semantic_scholar 等）内部会
# 延迟 `from i18n import t`（i18n.py 在 scripts/ 下）——不经 ct_literature 主流程
# 单独调用 dispatch 时若无此路径即 ModuleNotFoundError（2026-09-06 实测）
_scripts = os.path.join(_SKILL_ROOT, "scripts")
if os.path.isdir(_scripts) and _scripts not in sys.path:
    sys.path.insert(0, _scripts)

# ── 复用 ct-registry 的凭据单一真相源 ─────────────────────────────────────
def _resolve_token() -> str:
    """token 优先级：CLI --token > env CT_REGISTRY_COZE_TOKEN > 内嵌公开 blob。

    复用 ct-registry 的 endpoint_token.py（ct-base §5.236），不重复造轮子。
    """
    # 1) CLI --token（由 argparse 注入）
    cli_tok = getattr(_resolve_token, "_cli_token", None)
    if cli_tok:
        return cli_tok
    # 2) env
    env_tok = os.environ.get("CT_REGISTRY_COZE_TOKEN") or os.environ.get("ICTRP_WORKFLOW_TOKEN")
    if env_tok:
        return env_tok
    # 3) 内嵌公开 blob
    try:
        from endpoint_token import get_token as _gt
        return _gt() or ""
    except Exception:
        return ""


def _has_openalex_key() -> bool:
    """本地是否配置 OpenAlex API key（env OPENALEX_API_KEY / 技能根 .env）。

    有 key → dispatch 把 openalex 路由到本地直连（keyed pool 100k credits/天）；
    无 key → 仍走 Coze 匿名池（openalex 匿名可用，非 S2 那种必 429，无需跳过）。
    复用 http_utils.load_openalex_key 保证与 fetch_openalex 离线路径 key 一致。
    """
    try:
        sys.path.insert(0, _ADAPTERS_DIR)
        from adapters import http_utils
        return bool(http_utils.load_openalex_key())
    except Exception:
        return bool(os.environ.get("OPENALEX_API_KEY"))


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    tok = _resolve_token()
    if tok:
        h["Authorization"] = "Bearer " + tok
    return h


def _query_origin() -> str:
    """稳定机器标识（sha256 哈希，不可逆）。"""
    return "sha256:" + hashlib.sha256(os.environ.get("COMPUTERNAME", "unknown").encode()).hexdigest()


# ── 端点 ──────────────────────────────────────────────────────────────────
# 主路径 /stream_run（SSE 流式）：2026-09-06 改流式，与 PDF 通道同源 SSE 架构，
# 避免长检索被网关按单响应超时掐断；流式无结果自动回退 /run（CT_SEARCH_ENDPOINT）。
CT_SEARCH_ENDPOINT_STREAM = os.environ.get("CT_SEARCH_ENDPOINT_STREAM", "https://ct-search.coze.site/stream_run")
# 回退路径 /run（非流式，旧默认）：仅当 /stream_run 无结果或被拒时启用。
CT_SEARCH_ENDPOINT = os.environ.get("CT_SEARCH_ENDPOINT", "https://ct-search.coze.site/run")

# 支持的 source 集合（与 Coze 端 sources.py 同步）
DISPATCHABLE_SOURCES = frozenset({
    "openalex",
    "europepmc",
    "biorxiv",
    "medrxiv",
    "semantic_scholar",
    "arxiv",
})

# Coze 端小写 source → 本地规范显示名（与 fetch_*.py 返回的 source 一致；
# 保证下游 normalize / hit_count 等按 source 判断的逻辑不受大小写影响）
_SOURCE_DISPLAY = {
    "openalex": "OpenAlex",
    "europepmc": "EuropePMC",
    "biorxiv": "bioRxiv",
    "medrxiv": "medRxiv",
    "semantic_scholar": "SemanticScholar",
    "arxiv": "arXiv",
}


def _display_source(source: str) -> str:
    """Coze 小写 source → 本地规范显示名（未知源原样返回）。"""
    return _SOURCE_DISPLAY.get(source, source)

# 技能版本号回退常量
_SKILL_VERSION_FALLBACK = "0.9.7"


def _skill_version() -> str:
    """技能版本号：优先读技能根 SKILL.md frontmatter 的 `version:`（单一事实来源）。"""
    try:
        skill_md = os.path.join(_SKILL_ROOT, "SKILL.md")
        with open(skill_md, encoding="utf-8") as f:
            head = f.read(4000)
        m = re.search(r"^version:\s*([0-9][\w.\-]*)", head, re.M)
        if m:
            return m.group(1)
    except Exception:
        pass
    return _SKILL_VERSION_FALLBACK


def _resolve_locale() -> str:
    """界面 / 输出语言（zh/en）—— 顶层信封 `locale` 字段。"""
    try:
        sys.path.insert(0, os.path.join(_SKILL_ROOT, "scripts"))
        import i18n as _i18n
        lang = (_i18n._current_lang() or "").lower()
        if lang.startswith("zh"):
            return "zh"
        if lang.startswith("en"):
            return "en"
    except Exception:
        pass
    return "zh"


# ── 出站授权门（ct-base §5.212）──────────────────────────────────────────
# config.json 存放「出站授权白名单」，含作者私有 coze 端点（ct-search /
# ct-bugreport），属本机运行态配置，不随技能发布包公开。2026-09-06 起移出
# 技能树，置于 ~/.workbuddy/ct-literature-runtime/。解析优先级：
#   1) env CT_LIT_RUNTIME_DIR 指定目录
#   2) 默认 ~/.workbuddy/ct-literature-runtime/config/config.json
#   3) 技能树内 config/config.json（兜底，兼容旧布局 / 包内默认）
_SESSION_AUTHORIZED = set()
_RUNTIME_DIR = os.environ.get("CT_LIT_RUNTIME_DIR") or os.path.join(
    os.path.expanduser("~"), ".workbuddy", "ct-literature-runtime")


def _config_candidates():
    cands = []
    if os.environ.get("CT_LIT_RUNTIME_DIR"):
        cands.append(os.path.join(os.environ["CT_LIT_RUNTIME_DIR"], "config", "config.json"))
    cands.append(os.path.join(_RUNTIME_DIR, "config", "config.json"))
    cands.append(os.path.join(_SKILL_ROOT, "config", "config.json"))  # 兜底
    return cands


def _check_outbound_authorization(endpoint: str) -> bool:
    """出站授权检查：已授权 → True；未授权 → 返回 False（由调用方提示用户）。

    脚本只发 [AUTH-BLOCK] 信号，绝不自行修改 config.json。config 解析按
    _config_candidates() 多候选回退，确保移出技能树后仍能在运行态目录命中。
    """
    if endpoint in _SESSION_AUTHORIZED:
        return True
    for path in _config_candidates():
        try:
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    cfg = json.load(f)
                if endpoint in cfg.get("auto_approve_endpoints", []):
                    _SESSION_AUTHORIZED.add(endpoint)
                    return True
        except Exception:
            continue
    return False


# ── 本地兜底（--offline / Coze 不可用）──────────────────────────────────
def _offline_fallback(source: str, keyword: str, year_from: int = None,
                      year_to: int = None, max_results: int = 50) -> Optional[Dict]:
    """Coze 不可用时的本地兜底：调用原有的 fetch_*.py 模块。

    返回格式与 Coze 端一致：{"total_count": N, "projects": [...]}
    本地 fetch 模块返回 {"source": "...", "works": [...], "count": N}，
    需转换为 Coze 格式。
    """
    try:
        result = None
        if source == "openalex":
            from adapters import fetch_openalex
            result = fetch_openalex.fetch(keyword, year_from=year_from, max_results=max_results, run=True)
        elif source == "europepmc":
            from adapters import fetch_europepmc
            result = fetch_europepmc.fetch(keyword, year_from=year_from, max_results=max_results, run=True)
        elif source in ("biorxiv", "medrxiv"):
            from adapters import fetch_preprints
            server = "medrxiv" if source == "medrxiv" else "biorxiv"
            result = fetch_preprints.fetch(keyword, server=server, year_from=year_from, max_results=max_results, run=True)
        elif source == "semantic_scholar":
            from adapters import fetch_semantic_scholar
            result = fetch_semantic_scholar.fetch(keyword, year_from=year_from, max_results=max_results, run=True)
        elif source == "arxiv":
            from adapters import fetch_arxiv
            result = fetch_arxiv.fetch(keyword, year_from=year_from, max_results=max_results, run=True)
        
        if result is None:
            return None

        # 统一为本地格式（与 Coze 成功路径一致）：{"source": 规范名, "count", "works"}
        # source 用规范大写；本地 fetch 模块本就返回规范名，此处 display 映射兜底。
        works = result.get("works", [])
        return {
            "source": _display_source(result.get("source") or source),
            "count": result.get("count", len(works)),
            "works": works,
            "total_count": result.get("count", len(works)),
        }
    except Exception as e:
        print(f"[offline_fallback] {source} 本地兜底失败: {e}", file=sys.stderr)
    return None


# ── SSE 流式解析（与 PDF 通道同源）──────────────────────────────────────────
def _silent_log(msg):
    """流式解析用的静默日志（dispatch 主路径不需要逐事件打屏）。"""
    return


def _parse_stream(resp, log_fn=_silent_log):
    """解析 Coze stream_run 的 SSE 流，提取检索结果 projects 列表。

    优先复用 scripts/pdf_download.py 的 _parse_coze_stream（PDF 通道已验证的同源实现）；
    导入异常时降级到本模块内置最小解析器。返回 projects(list[dict]) 或 None。
    """
    try:
        if _SKILL_ROOT not in sys.path:
            sys.path.insert(0, _SKILL_ROOT)
        from adapters.pdf_download import _parse_coze_stream
        return _parse_coze_stream(resp, log_fn)
    except Exception:
        return _parse_stream_local(resp, log_fn)


def _parse_stream_local(resp, log_fn=_silent_log):
    """最小 SSE 解析兜底（仅当无法复用 pdf_download 时启用）。"""
    events = []
    buf = b""
    for chunk in resp:
        buf += chunk
        while b"\n" in buf:
            line_b, buf = buf.split(b"\n", 1)
            line = line_b.decode("utf-8", "ignore").rstrip("\r")
            if line.startswith("data:"):
                ds = line[len("data:"):].lstrip()
                if ds and ds != "[DONE]":
                    try:
                        events.append(json.loads(ds))
                    except Exception:
                        pass
    if not events:
        try:
            events.append(json.loads(buf.decode("utf-8", "ignore")))
        except Exception:
            return None
    final = None
    for evt in events:
        if not isinstance(evt, dict):
            continue
        inner = evt.get("data")
        node = inner if (isinstance(inner, dict) and inner.get("type")) else evt
        etype = node.get("type") or evt.get("type")
        if etype == "workflow_end":
            out = node.get("output")
            if out is None and isinstance(node.get("data"), dict):
                out = node["data"].get("output")
            if out is not None:
                final = out
    if final is None:
        for evt in reversed(events):
            if isinstance(evt, dict) and ("projects" in evt or "project_list" in evt):
                final = evt
                break
    if final is None:
        return None
    if isinstance(final, str):
        try:
            final = json.loads(final)
        except Exception:
            return None
    if not isinstance(final, dict):
        return None
    projects = final.get("projects")
    if isinstance(projects, list):
        return projects
    pl = final.get("project_list")
    if pl is not None:
        if isinstance(pl, str):
            try:
                pl = json.loads(pl)
            except Exception:
                return None
        if isinstance(pl, dict):
            p = pl.get("projects")
            if isinstance(p, list):
                return p
    return None


def _parse_run_response(data, source):
    """解析 /run（非流式）返回体 → 本地统一格式 {"source","works","count","total_count"}。"""
    if isinstance(data.get("project_list"), str):
        try:
            pl = json.loads(data["project_list"])
            works = pl.get("projects", [])
            return {
                "source": _display_source(source),
                "count": pl.get("total_count", len(works)),
                "works": works,
                "total_count": pl.get("total_count", len(works)),
            }
        except (json.JSONDecodeError, TypeError):
            pass
    if "projects" in data and "works" not in data:
        data["works"] = data.pop("projects")
        data["count"] = data.get("total_count", len(data["works"]))
    data["source"] = _display_source(source)
    return data


def _coze_stream_once(body, timeout):
    """单次 /stream_run 请求 + SSE 解析；返回 projects(list) 或 None（无结果/被拒），异常上抛。"""
    req = urllib.request.Request(CT_SEARCH_ENDPOINT_STREAM, data=body, headers=_headers(), method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return _parse_stream(resp, _silent_log)


# ── 统一外发检索 ──────────────────────────────────────────────────────────
def dispatch(source: str, keyword: str, year_from: int = None, year_to: int = None,
             max_results: int = 50, run: bool = False, log_feishu: bool = True,
             timeout: int = 300, offline: bool = False,
             querystr: str = None, skillname: str = None) -> Optional[Dict]:
    """统一外发检索，返回结构化结果。

    Args:
        source: 数据源（openalex/europepmc/biorxiv/medrxiv/semantic_scholar/arxiv）
        keyword: 检索词（英文）
        year_from: 起始年份
        year_to: 截止年份
        max_results: 每源最大返回数
        run: 是否实际执行网络请求（False = 仅预览 payload）
        log_feishu: 是否记飞书（中间调用=False，最终汇总=True）
        timeout: HTTP 超时秒数
        offline: 强制本地兜底（不调 Coze）
        querystr: 审计 querystr JSON 字符串（透传飞书 querystr 列；None 则不携带）
        skillname: 飞书审计 skillname 覆盖（None=Coze 端按 source 推导）

    Returns:
        {"source": 规范名, "works": [...], "count": N, "total_count": N} 或 None（预览模式）
    """
    if source not in DISPATCHABLE_SOURCES:
        raise ValueError(f"unsupported source: {source}. Must be one of {sorted(DISPATCHABLE_SOURCES)}")

    # Semantic Scholar 本地化（用户决策 2026-09-06）：有 key 用户走本地直连，
    # 不经过 Coze——私人 key 零传递最安全，本地 fetch_semantic_scholar.py 本就支持
    # key（1 RPS 专属）；无 key 本地模块自行跳过（与老版本一致）。Coze 端
    # semantic_scholar_node 仅服务无本地检索能力的调用方（无 key 时跳过）。
    if source == "semantic_scholar":
        if not run:
            print(json.dumps({
                "source": source, "mode": "local", "note": "semantic_scholar 本地直连（有 key 用户，不经 Coze）",
                "keyword": keyword, "max_results": max_results}, ensure_ascii=False, indent=2))
            return None
        return _offline_fallback(source, keyword, year_from, year_to, max_results)

    # OpenAlex 本地化（用户决策 2026-09-06，方案 B 同 S2 原则）：有 key 用户本地直连
    # 不经过 Coze——key 零传递 + 进 keyed pool（100k credits/天，无 429），本地
    # fetch_openalex.py 经 build_openalex_headers 带 mailto polite-pool + Bearer key。
    # 无 key 仍走 Coze（openalex_node 匿名池可用，与 S2"无 key 必 429"不同，不需跳过）。
    if source == "openalex" and _has_openalex_key():
        if not run:
            print(json.dumps({
                "source": source, "mode": "local", "note": "openalex 本地直连（有 key 用户，keyed pool，不经 Coze）",
                "keyword": keyword, "max_results": max_results}, ensure_ascii=False, indent=2))
            return None
        return _offline_fallback(source, keyword, year_from, year_to, max_results)

    # 本地兜底
    if offline:
        return _offline_fallback(source, keyword, year_from, year_to, max_results)

    # 构造 payload
    payload = {
        "source": source,
        "mode": "search",
        "keyword": keyword,
        "max_results": max_results,
        "log_feishu": log_feishu,
        "query_origin": _query_origin(),
        "skill_version": _skill_version(),
        "locale": _resolve_locale(),
        "params": {"user_language": _resolve_locale()},
    }
    if year_from:
        payload["year_from"] = year_from
    if year_to:
        payload["year_to"] = year_to
    # 审计透传：汇总/标记类调用把统计信息放进 querystr，Coze 端飞书节点原样落库
    if querystr:
        payload["querystr"] = querystr
    if skillname:
        payload["skillname"] = skillname

    if not run:
        # 预览模式：只打印 payload，不执行网络请求
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return None

    # 出站授权检查
    if not _check_outbound_authorization(CT_SEARCH_ENDPOINT):
        print(f"[AUTH-BLOCK] endpoint not authorized: {CT_SEARCH_ENDPOINT}", file=sys.stderr)
        print("Run with --run after authorizing, or use --offline for local fallback.", file=sys.stderr)
        return {"error": "AUTH-BLOCK", "endpoint": CT_SEARCH_ENDPOINT}

    # HTTP POST to Coze —— 主路径 /stream_run（SSE 流式），回退 /run（见下方 except）
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        projects = _coze_stream_once(body, timeout)
        if projects is not None:
            # 流式成功：projects 已是从 workflow_end/output 提取的列表（兼容 projects
            # 列表 / project_list 字符串 / 字典三种形态）。total_count 取实际返回条数
            # （检索受 max_results 截断，与 Coze 端 total_count 语义一致）。
            return {
                "source": _display_source(source),
                "count": len(projects),
                "works": projects,
                "total_count": len(projects),
            }
        # 流式无结果（workflow Output 未绑定 / 被 rejected）→ 回退 /run
        print("[coze] /stream_run 无结果，回退 /run", file=sys.stderr)
    except urllib.error.HTTPError as e:
        print(f"[Coze] /stream_run HTTP {e.code}，回退 /run: "
              f"{(e.read().decode('utf-8', errors='replace') if e.fp else '')[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"[Coze] /stream_run 失败({type(e).__name__})，回退 /run: {e}", file=sys.stderr)
    # 回退 /run（非流式）
    try:
        req2 = urllib.request.Request(CT_SEARCH_ENDPOINT, data=body, headers=_headers(), method="POST")
        with urllib.request.urlopen(req2, timeout=timeout) as resp2:
            data = json.loads(resp2.read().decode("utf-8"))
        return _parse_run_response(data, source)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        print(f"[Coze] HTTP {e.code}: {err_body[:500]}", file=sys.stderr)
        # 401/403 → 明确警告
        if e.code in (401, 403):
            print("[Coze] Token 无效或已过期，请通过 --token 或 env CT_REGISTRY_COZE_TOKEN 重新设置", file=sys.stderr)
        return {"error": f"HTTP {e.code}", "message": err_body[:500]}
    except Exception as e:
        print(f"[Coze] 请求失败: {type(e).__name__}: {e}", file=sys.stderr)
        return {"error": f"{type(e).__name__}: {e}"}


# ── 流式检索生成器 ──────────────────────────────────────────────────────────
def dispatch_stream(source: str, keyword: str, year_from: int = None, year_to: int = None,
                    max_results: int = 50, run: bool = False, log_feishu: bool = True,
                    timeout: int = 300, offline: bool = False, querystr: str = None,
                    skillname: str = None, batch_size: int = 5, progress=None) -> "Generator[List[Dict], None, None]":
    """流式检索生成器：把 Coze 返回的 works 按 batch_size 切片，依次 yield 给调用方。

    设计（对应「对 coze 的调用改为流式调用，5 个一批依次返回」）：
      - 内部复用 dispatch()：dispatch 已改 /stream_run（SSE）+ /run 回退，coze 调用本身是流式的；
      - 检索工作流在 workflow_end 一次性返回全部结果（非节点级增量），故切片在流结束后分批吐出；
        若 coze 端未来支持节点级增量返回，吐批点可自然前移，无需改调用方；
      - 每批最多 batch_size 篇（默认 5），最后一批可能不足。progress 回调逐批上报进度，
        便于 workbench / CLI 渐进渲染，避免长检索「干等」。

    Args:
        batch_size: 每批返回篇数（默认 5）。
        progress: 可选 fn(msg) 进度回调。

    Yields:
        List[dict] —— 每批 work（本地统一格式，含 doi/title/source 等）。
    """
    if batch_size < 1:
        batch_size = 1
    result = dispatch(source, keyword, year_from, year_to, max_results,
                      run=run, log_feishu=log_feishu, timeout=timeout, offline=offline,
                      querystr=querystr, skillname=skillname)
    if result is None or result.get("error"):
        msg = f"[coze] 检索失败: {result.get('error') if result else 'None'}"
        if progress:
            progress(msg)
        else:
            print(msg, file=sys.stderr)
        return
    works = result.get("works", [])
    total = len(works)
    if progress:
        progress(f"[coze] 检索完成，共 {total} 篇，按 {batch_size} 篇/批返回")
    for i in range(0, total, batch_size):
        batch = works[i:i + batch_size]
        if progress:
            progress(f"[coze] 返回第 {i // batch_size + 1} 批（{len(batch)} 篇）")
        yield batch


# ── CLI ──────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="文献检索统一 Coze 客户端（ct-literature 外发出口）")
    ap.add_argument("--source", required=True, choices=sorted(DISPATCHABLE_SOURCES),
                    help="数据源")
    ap.add_argument("--keyword", required=True, help="检索词（英文）")
    ap.add_argument("--year-from", type=int, default=None, help="起始年份")
    ap.add_argument("--year-to", type=int, default=None, help="截止年份")
    ap.add_argument("--max-results", type=int, default=50, help="每源最大返回数（默认 50）")
    ap.add_argument("--run", action="store_true", help="实际执行网络请求（默认仅预览 payload）")
    ap.add_argument("--log-feishu", type=lambda x: x.lower() in ("true", "1", "yes"),
                    default=True, help="是否记飞书（默认 True，中间调用设 False）")
    ap.add_argument("--timeout", type=int, default=300, help="HTTP 超时秒数（默认 300）")
    ap.add_argument("--offline", action="store_true", help="强制本地兜底（不调 Coze）")
    ap.add_argument("--token", default=None, help="Coze Bearer token（优先级最高）")
    ap.add_argument("--stream", action="store_true",
                    help="流式返回：works 按 --batch-size 切片逐批输出（默认 5 篇/批）")
    ap.add_argument("--batch-size", type=int, default=5,
                    help="--stream 时每批篇数（默认 5）")
    args = ap.parse_args()

    # 注入 CLI token
    if args.token:
        _resolve_token._cli_token = args.token

    if args.stream:
        n_batches = 0
        for batch in dispatch_stream(
            source=args.source,
            keyword=args.keyword,
            year_from=args.year_from,
            year_to=args.year_to,
            max_results=args.max_results,
            run=args.run,
            log_feishu=args.log_feishu,
            timeout=args.timeout,
            offline=args.offline,
            batch_size=args.batch_size,
        ):
            n_batches += 1
            print(f"--- batch {n_batches} ({len(batch)} works) ---")
            print(json.dumps(batch, ensure_ascii=False, indent=2))
        print(f"[done] {n_batches} batches")
        return 0

    result = dispatch(
        source=args.source,
        keyword=args.keyword,
        year_from=args.year_from,
        year_to=args.year_to,
        max_results=args.max_results,
        run=args.run,
        log_feishu=args.log_feishu,
        timeout=args.timeout,
        offline=args.offline,
    )

    if result is not None:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
