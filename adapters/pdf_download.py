#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pdf_download.py — 文献 PDF 批量下载（本地端，与 ct-literature 共用）

架构（2026-09-05 重构：统一输入 + 单次 coze 传送 + 真实直链下载）：
  - 统一输入：本地为每篇 work 生成「单一规范标识」（open_access_url 优先，否则 doi），
    整批一次性发 coze（publisher_pdf_batch 统一契约），不再区分 DOI / OA 两种模式。
  - 解码上移 coze：coze 端对每条标识执行 A(解码+直下探测验证真实 PDF)
    → 若 A 失败则 B(浏览器+S3)，仅返回经探测/上传验证过的真实直链
    （pdf_url / pdf_s3_url）；拿不到真实直链只返 pdf_failed，绝不返回伪直链。
  - 本地只负责「下载 coze 返回的真实直链」。下载失败 → 标记 manual，不重发
    （符合「只做一次 coze 传送」；coze 端 A→B 已联合尝试，无需本地二次传送）。
  - 兜底：coze 不可用 / --skip-coze 时，本地复用 _epmc_lookup_pdf_url 自行解码
    （仅 Europe PMC 非 Cloudflare 副本可直下；付费墙/重定向器本地无浏览器只能标 manual）。

出站信封（ct-base references/coze_io_contract.md 全库统一契约）：
  - skill_version（§1.2）：顶层信封字段，读本地 SKILL.md frontmatter `version:`
  - locale（§1.1）：界面 / 输出语言（zh/en），顶层信封输出开关
  - params.user_language（§1.1）：输入语言提示，规范承载位是请求 params（顶层不双写）
  - coze 端据此把 runtime_sec（处理持续秒数，§2.2）写入飞书 resultstr 列（只进日志不出参）

单批上限（用户 2026-09-05 指定）：coze 端 MAX_BATCH_ITEMS=50，超限直接 rejected；
本地按同一上限自动拆批，每批一次传送。

总量上限（用户 2026-09-06 追加）：一次 PDF 下载请求超过 MAX_TOTAL_ITEMS=50 篇
直接拒绝（不再拆批）——多批串行传送 + 逐篇下载的总耗时远超单请求网关/用户可接受
窗口，必然超时；须提示用户缩小范围（按引用排序取 top-N / 单源 / 分次下载）后重试。

传输（2026-09-05 改流式）：PDF 批量下载耗时较长，coze 端口改用 stream_run（SSE 流式）
调用——实时返回节点事件，避免长连接被网关按单响应超时掐断。本地 _call_coze_unified
解析 SSE 流，从 workflow_end / node_end 事件提取最终 projects（兼容 projects 列表、
project_list 字符串/字典、超长回参外置 S3 三种形态）。

流程（run）：
  1. 收集每篇规范标识（OA 优先，否则 DOI）
  2. 总量 > 50 → 直接拒绝（提示缩小范围），不拆批
  3. 按 50 上限拆批，每批一次性调用 coze（publisher_pdf_batch 统一契约）→ 拿回真实直链
  4. 本地 urllib 逐篇下载真实直链（间隔 1s、429 退避、拒绝挑战页）；失败标 manual，不重发
  5. 整批 coze 失败 → 该批走本地兜底解码（仅 epmc 副本可下）
"""

import hashlib
import json
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

# §16.9 出站归位：本模块自 adapters/ 运行，但同仓引用（adapters.preprint_fallback /
# scripts.i18n 等）依赖技能根与 scripts 在 sys.path——统一在此注入，__main__ 直跑与
# 包导入（from adapters.pdf_download import …）两种场景都可用。
_SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_SKILL_ROOT, os.path.join(_SKILL_ROOT, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# 并发下载线程池上限（P0，2026-09-06）：不同出版商域名之间并发下载，
# 同域名仍按该域名的 min_delay 串行保距（见 _PerHostRateLimiter），
# 既提速又不被 Cloudflare 1015 封。纯本地、标准库实现，不碰 coze 工作流。
MAX_DOWNLOAD_WORKERS = 6
# coze 子批篇数（P1，2026-09-06）：把 indirect_items 拆成 ≤12 的小批送 coze，
# 比一次性 50 更早返回首批结果，且「解码子批 N+1」与「下载子批 N」重叠 → 管道化提速。
COZE_SUB_BATCH = 12
# Unpaywall email（与 coze 端 publisher_pdf_batch_node._UPW_EMAIL 保持一致；
# Unpaywall 要求合法 email，本地用它取 OA 直链 / 更早预印本版本做「本地优先」路由）。
_UPW_EMAIL = "medstatstar@gmail.com"
# 本地预筛：每个 DOI 的 Unpaywall 查询并发上限（预取阶段用，避免触发限流）
_UPW_CONCURRENCY = 5

DEFAULT_EMAIL = "ct-literature@example.com"
# coze 流式接口（PDF 批量下载耗时较长，改用 stream_run SSE 实时返回节点事件，
# 避免长连接被网关按单响应超时掐断）。
# 宿主用 ct-search.coze.site：实测只有该宿主真正承载 publisher_pdf_batch 工作流
#（/run 返回真实直链；bp3886cvnd.coze.site 是 registry-search 工作流，不服务 PDF 下载）。
# 若 publisher_pdf_batch 已发布到其它流式宿主，可用环境变量 CT_SEARCH_ENDPOINT 覆盖。
# 注意：stream_run 返回 workflow_end.output 依赖 coze 工作流「Output」变量已绑定
# project_list；未绑定则 output 为 {}（已实测），需在工作流控制台配置后流式才生效。
CT_SEARCH_ENDPOINT = os.environ.get("CT_SEARCH_ENDPOINT", "https://ct-search.coze.site/stream_run")
CT_REGISTRY_SKILL = os.path.expanduser("~/.workbuddy/skills/ct-registry")

# Europe PMC 严格限速：两次查询之间至少间隔 1.0 秒（本地兜底用，单线程调用）。
_epmc_last_ts = 0.0
_EPMC_MIN_INTERVAL = 1.0


def _epmc_ratelimit():
    """两次 Europe PMC 查询之间至少间隔 1.0 秒（严格限速）。"""
    global _epmc_last_ts
    now = time.time()
    wait = _EPMC_MIN_INTERVAL - (now - _epmc_last_ts)
    if wait > 0:
        time.sleep(wait)
    _epmc_last_ts = time.time()


def _resolve_token() -> str:
    """token 优先级：env CT_SEARCH_COZE_TOKEN > 动态复用 ct-registry 内嵌公开 blob。"""
    tok = os.environ.get("CT_SEARCH_COZE_TOKEN")
    if tok:
        return tok
    try:
        sys.path.insert(0, os.path.join(CT_REGISTRY_SKILL, "adapters"))
        from endpoint_token import get_token as _gt
        return _gt() or ""
    except Exception:
        return ""


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    tok = _resolve_token()
    if tok:
        h["Authorization"] = "Bearer " + tok
    return h


def _query_origin() -> str:
    """稳定机器标识。"""
    return "sha256:" + hashlib.sha256(os.environ.get("COMPUTERNAME", "unknown").encode()).hexdigest()


# 单批篇数上限：必须与 coze 端 publisher_pdf_batch_node.MAX_BATCH_ITEMS 保持一致。
# coze 端超过该值直接返 status=rejected 拒绝执行；本地按此上限自动拆批，
# 每批一次传送（每篇仍只传送一次，下载失败不重发）。
MAX_BATCH_ITEMS = 50
# 单次下载总量上限（用户 2026-09-06 追加）：一次 run(works) 超过该篇数**直接拒绝**，
# 不拆批继续——多批串行（每批一次 coze 传送 + 逐篇下载间隔 1s）总耗时必然超时；
# 拒绝时提示用户缩小范围（top-N / 单源 / 分次）后重试。
MAX_TOTAL_ITEMS = 50
# sub-batch 发送间隔（秒）：避免 coze 端高频请求触发限流（2026-09-07 用户要求 ≥5 秒）
COZE_BATCH_INTERVAL = 5
# 技能版本号回退常量（SKILL.md 读取失败时使用；ct-base coze_io_contract §1.2）
_SKILL_VERSION_FALLBACK = "1.0.0"


def _skill_version() -> str:
    """技能版本号：优先读技能根 SKILL.md frontmatter 的 `version:`（单一事实来源），
    读取失败（文件缺失 / 格式异常）回退模块常量 —— 升级技能后无需同步改本文件。
    位置：coze 请求**顶层信封**字段（与 query_origin 同级，ct-base coze_io_contract §1.2）。
    """
    try:
        skill_md = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "SKILL.md")
        with open(skill_md, encoding="utf-8") as f:
            head = f.read(4000)
        m = re.search(r"^version:\s*([0-9][\w.\-]*)", head, re.M)
        if m:
            return m.group(1)
    except Exception:
        pass
    return _SKILL_VERSION_FALLBACK


def _resolve_locale() -> str:
    """界面 / 输出语言（zh/en）—— 顶层信封 `locale` 字段（ct-base coze_io_contract §1.1）。

    判定源：ct-literature 自带 i18n（系统 locale 检测）；失败回退 "zh"。
    """
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        import i18n as _i18n
        lang = (_i18n._current_lang() or "").lower()
        if lang.startswith("zh"):
            return "zh"
        if lang.startswith("en"):
            return "en"
    except Exception:
        pass
    return "zh"


def _resolve_user_language() -> str:
    """输入语言提示（zh/en）—— 承载位 `params.user_language`（ct-base coze_io_contract §1.1）。

    规范位置是请求 `params`（顶层不双写）；服务端读取顺序 params → 顶层 → 空。
    当前与界面语言同源（i18n 判定）；保留独立函数以便后续按「输入 query 文本内容」
    细分（§1.1 三级优先级：显式 override > 输入文本判定 > 系统 locale）。
    """
    return _resolve_locale()


PDF_DOWNLOAD_NOTICE = (
    "【下载说明】本功能仅为方便快速获取文档：① 仅下载无版权问题的 OA 文献，付费文献请自行下载；"
    "② 请勿用于超过 50 篇的批量下载或商业用途，否则可能导致服务被封锁 IP；"
    "③ OA 供应商普遍拦截代码自动下载，因此可能失败，成功率约 30–50%；"
    "④ 对无法直接下载的文献，系统会自动尝试公开提供的作者手稿或其它预印本渠道作为替代；"
    "⑤ 每篇下载约需 10–20 秒（含限流退避与云端解析），整批下载请耐心等待。"
)


def _safe_filename(doi: str, max_len: int = 120) -> str:
    """DOI / URL → 安全文件名。"""
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", doi)
    # 移除末尾已有的 .pdf 后缀，避免重复追加
    if safe.lower().endswith(".pdf"):
        safe = safe[:-4]
    if len(safe) > max_len:
        digest = hashlib.md5(doi.encode()).hexdigest()[:8]
        safe = safe[:max_len - 9] + "_" + digest
    return safe + ".pdf"


# 直链 PDF 判定：OA / 预印本真实 PDF 直链（本地可直接下载，无需送 coze 解码）。
# 注意：doi.org 解析页不算直链；预印本服务器域名（bioRxiv/medRxiv/arXiv/ChemRxiv/
# ResearchSquare/SSRN）即便 URL 形态不标准也视为可本地直下。
def _looks_like_direct_pdf(url: str) -> bool:
    u = (url or "").strip().lower()
    if not u or "doi.org" in u:
        return False
    # 预印本 / OA 直链域名（命中即视为可本地直下）
    if any(h in u for h in ("biorxiv.org", "medrxiv.org", "arxiv.org",
                            "chemrxiv.org", "researchsquare.com", "ssrn.com")):
        return True
    return (u.endswith(".pdf") or "pdf=render" in u
            or "article-pdf" in u or "pdfs/" in u
            or "full.pdf" in u or "document/" in u
            or "download" in u or "bitstream" in u)


def _looks_like_pdf_url(u: str) -> bool:
    """宽松判定：是否为 PDF 下载地址（用于本地预筛返回的候选直链）。"""
    u = (u or "").strip().lower()
    return bool(u) and (u.endswith(".pdf") or "pdf" in u)


class _PerHostRateLimiter:
    """每域名限速器（P0，2026-09-06）：不同出版商域名之间并发下载，同域名按 min_delay
    串行保距——既提速又不被 Cloudflare 1015 封。纯本地、标准库实现，不碰 coze 工作流。

    acquire(host, delay)：调用方在发起请求「前」调用。同一 host 的并发调用会顺序化——
    每位等待到「距上一位允许时刻 ≥ delay」才放行；不同 host 各持各锁、互不阻塞。
    下载动作在 acquire 返回之后进行（锁已释放），故同 host 的「间隔」计的是请求发起节奏，
    不计入下载耗时，最大化并发。
    """

    def __init__(self):
        self._host_locks: Dict[str, threading.Lock] = {}
        self._host_last: Dict[str, float] = {}
        self._meta = threading.Lock()

    def acquire(self, host: str, delay: float):
        with self._meta:
            lk = self._host_locks.get(host)
            if lk is None:
                lk = self._host_locks[host] = threading.Lock()
        lk.acquire()
        try:
            # 计算允许时刻需短暂持全局锁（仅读写 _host_last），但 sleep 必须释放全局锁——
            # 否则所有 host 的限速等待会互相阻塞，跨域名并发被全局锁串行化（致命性能 bug）。
            # 同 host 串行保距由 per-host 锁 lk 保证（sleep 期间仍持 lk）；跨 host 并发由
            # 释放全局锁后并行实现。
            now = time.time()
            with self._meta:
                allowed = max(now, self._host_last.get(host, 0.0) + delay)
                wait = allowed - now
                self._host_last[host] = allowed
            if wait > 0:
                time.sleep(wait)
        finally:
            lk.release()


def _browser_headers(host: str = "") -> dict:
    """浏览器级 headers（C：补全 Accept / Accept-Language / Referer 降低被识别为 bot 的概率）。"""
    h = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "Accept": "application/pdf,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    if "biorxiv.org" in host:
        h["Referer"] = "https://www.biorxiv.org/"
    elif "medrxiv.org" in host:
        h["Referer"] = "https://www.medrxiv.org/"
    return h


def _get(url: str, timeout: int = 60, retries: int = 2) -> bytes:
    """GET 带重试（A：429 指数退避）。"""
    import random as _rand
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=_browser_headers(url))
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                wait = min(30 * (2 ** attempt), 120) + _rand.uniform(0, 5)
                time.sleep(wait)
                last = "HTTP 429 (backoff %.0fs)" % wait
                continue
            if e.code in (403, 404):
                time.sleep(1)
                last = "HTTP %s" % e.code
                continue
            raise
        except Exception as e:
            last = "%s: %s" % (type(e).__name__, e)
            time.sleep(0.5)
    raise RuntimeError(str(last))


def _download_to(url: str, out_path: str, timeout: int = 120) -> bool:
    """下载 URL 到本地文件。返回是否成功（首字节须为 %PDF-）。

    对 Europe PMC / biorxiv / medRxiv 等 429 限流做指数退避重试（A）；对 Cloudflare /
    跳转 / 限流等 HTML 挑战页直接判失败（不落脏文件到目标路径），避免把网页当 PDF 存下。

    写盘策略：**先写到 out_path + '.part' 临时文件，校验通过后
    用 os.replace 原子替换到 out_path**。绝不在失败路径删除目标文件——WorkBuddy 的
    safe-delete 钩子会拦截对工作区文件的 os.remove（fail closed 抛异常），此前
    "先建目标文件、校验失败再 os.remove 清理" 会触发钩子并反复卡死。os.replace 是
    覆盖写入而非删除，不触发钩子，且天然幂等（可安全覆盖已存在文件）。
    """
    import random as _rand
    tmp_path = out_path + ".part"
    for attempt in range(4):  # A：4 次重试（3 次 429 退避 + 1 次最终尝试）
        try:
            req = urllib.request.Request(url, headers=_browser_headers(url))
            with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp_path, "wb") as f:
                head = r.read(5)
                f.write(head)
                ct = (r.headers.get("Content-Type") or "").lower()
                if head[:5] != b"%PDF-" or "html" in ct:
                    # 挑战页 / 跳转页 / 限流页 → 判失败。临时文件留在 .part 不删
                    # （不触发 safe-delete 钩子）；下次成功 os.replace 会覆盖。
                    if "html" in ct and attempt < 3:
                        time.sleep(3)
                        continue
                    return False
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
            if os.path.getsize(tmp_path) > 100:
                # 校验通过 → 原子覆盖到最终路径（os.replace 非删除，不触发钩子）
                os.replace(tmp_path, out_path)
                return True
            return False
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                wait = min(30 * (2 ** attempt), 120) + _rand.uniform(0, 5)
                time.sleep(wait)
                continue
            return False
        except Exception:
            return False
    return False


def _dig_output(node):
    """从单个流式事件对象（workflow_end / node_end）中提取最终 output。

    兼容多种嵌套形态：
      - {"type":"workflow_end", "output": <...>}
      - {"type":"workflow_end", "data": {"output": <...>}}
      - {"type":"workflow_end", "data": {"data": {"output": <...>}}}
    output 可能是 dict（已结构化）或 str（JSON 字符串，由调用方 json.loads）。
    """
    if not isinstance(node, dict):
        return None
    out = node.get("output")
    if out is None and isinstance(node.get("data"), dict):
        out = node["data"].get("output")
    if (out is None and isinstance(node.get("data"), dict)
            and isinstance(node["data"].get("data"), dict)):
        out = node["data"]["data"].get("output")
    return out


def _has_real_output(o: Any) -> bool:
    """判定某节点的输出是否携带「我们需要的」真实结果（而非空容器）。

    workflow_end.output 在 coze「Output 变量未绑定」时返回空字典 {}，
    此时必须回退到 node_end 输出——因此空 dict / 空 list 不算『有结果』。
    """
    if isinstance(o, dict):
        return any(k in o for k in ("projects", "project_list", "s3_url", "status", "total_count"))
    if isinstance(o, str):
        try:
            d = json.loads(o)
        except Exception:
            return bool(o) and "[DONE]" not in o
        return isinstance(d, dict) and any(
            k in d for k in ("projects", "project_list", "s3_url", "status", "total_count"))
    if isinstance(o, list):
        return len(o) > 0
    return False


def _parse_coze_stream(resp, log_fn) -> Optional[List[Dict[str, Any]]]:
    """解析 Coze stream_run 的 SSE 流，提取 publisher_pdf_batch 最终 projects 列表。

    返回 projects（list[dict]）或 None（无结果 / 执行失败 / 被拒绝）。

    流式事件类型（外层 data.type，与用户提供的六种完全一致）：
      - workflow_start : 工作流开始（记日志，忽略内容）
      - node_start     : 节点开始（记节点标题，实时进度）
      - node_end       : 节点结束，output 含该节点输出（流式真实结果常落此处）
      - workflow_end   : 工作流结束，output 为聚合结果（依赖 coze Output 变量绑定）
      - error          : 执行错误，直接返回 None
      - ping           : 保活心跳，忽略

    选择最终结果的优先级：
      workflow_end.output（非空）→ 否则取最后一个『含真实结果』的 node_end 输出
      → 否则取最后一个 node_end → 否则兜底整块 JSON。
    """
    events: List[dict] = []
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
    # 兜底：未解析到事件则尝试整块 JSON（应对非 SSE 返回）
    if not events:
        try:
            events.append(json.loads(buf.decode("utf-8", "ignore")))
        except Exception:
            log_fn("[coze] 流式响应无法解析为事件")
            return None

    workflow_end_out: Any = None
    node_outputs: List[Any] = []
    for evt in events:
        if not isinstance(evt, dict):
            continue
        etype = evt.get("type")
        inner = evt.get("data")
        if isinstance(inner, dict) and inner.get("type"):
            etype = inner.get("type")
            node = inner
        else:
            node = evt
        if etype == "workflow_start":
            log_fn("[coze:workflow_start] 工作流开始")
        elif etype == "node_start":
            nt = node.get("node_title") or node.get("title") or node.get("node_id") or ""
            log_fn("[coze:node_start] %s" % nt)
        elif etype == "node_end":
            nt = node.get("node_title") or node.get("node_id") or ""
            o = _dig_output(node)
            if o is not None:
                node_outputs.append(o)
                if nt:
                    try:
                        sz = len(json.dumps(o, ensure_ascii=False))
                    except Exception:
                        sz = 0
                    log_fn("[coze:node_end] %s -> %d 字节输出" % (nt, sz))
        elif etype == "workflow_end":
            workflow_end_out = _dig_output(node)
            log_fn("[coze:workflow_end] 工作流结束")
        elif etype == "error":
            log_fn("[coze] 流式返回 error: %s"
                   % json.dumps(evt.get("data") or evt, ensure_ascii=False)[:400])
            return None
        # ping 等其它类型：忽略

    # 选择最终结果：优先 workflow_end（非空），否则回退到『含真实结果的』node_end
    final: Any = None
    if _has_real_output(workflow_end_out):
        final = workflow_end_out
    else:
        for o in reversed(node_outputs):
            if _has_real_output(o):
                final = o
                break
        if final is None and node_outputs:
            final = node_outputs[-1]
    if final is None:
        # 兜底：非 SSE 整块 JSON 返回，取最后一个含 projects/project_list 的事件
        for evt in reversed(events):
            if isinstance(evt, dict) and ("projects" in evt or "project_list" in evt):
                final = evt
                break
    if final is None:
        return None
    # output 可能为 JSON 字符串（如 project_list 序列化体）
    if isinstance(final, str):
        try:
            final = json.loads(final)
        except Exception:
            log_fn("[coze] 最终结果非 JSON: %s" % final[:200])
            return None
    if not isinstance(final, dict):
        return None

    # 归一化 projects（兼容 projects 列表 / project_list 字符串或字典 / s3_url 外置）
    projects = final.get("projects")
    if isinstance(projects, list):
        if projects:
            return projects
        # 空列表：若带 s3_url 说明回参超长外置，去拉取真实数据；否则表示 0 篇结果
        s3 = final.get("s3_url")
        if s3:
            pl = None
            log_fn("[coze] 回参超长，从 S3 拉取结果: %s" % s3)
            try:
                raw_json = _get(s3, timeout=60)
                pl = json.loads(raw_json.decode("utf-8"))
            except Exception as e:
                log_fn("[coze] S3 结果拉取失败: %s" % e)
                return None
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
        return []
    pl = final.get("project_list")
    s3 = final.get("s3_url")
    if pl is None and s3:
        log_fn("[coze] 回参超长，从 S3 拉取结果: %s" % s3)
        try:
            raw_json = _get(s3, timeout=60)
            pl = json.loads(raw_json.decode("utf-8"))
        except Exception as e:
            log_fn("[coze] S3 结果拉取失败: %s" % e)
            return None
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


def _extract_doi_from_url(url: str) -> Optional[str]:
    """从 URL 提取 DOI（如 nejm.org/doi/pdf/10.1056/NEJMoa... → 10.1056/NEJMoa...）。"""
    if not url:
        return None
    m = re.search(r'/doi/(?:pdf/)?(10\.\d{4,}/[^\s?&]+)', url)
    if m:
        return m.group(1)
    m = re.search(r'[?&]doi=(10\.\d{4,}/[^\s?&]+)', url)
    if m:
        return m.group(1)
    # doi.org/10.xxxx/... 形式（最常见的官方 DOI 解析地址）
    m = re.search(r'doi\.org/(10\.\d{4,}/[^\s?&]+)', url)
    if m:
        return m.group(1)
    # 兜底：URL 中任意位置出现的裸 DOI
    m = re.search(r'(10\.\d{4,}/[^\s?&]+)', url)
    if m:
        return m.group(1)
    return None


class PdfDownloader:
    """文献 PDF 批量下载器。

    Args:
        out_dir: PDF 保存目录
        email: Unpaywall email（OA 解析用）
        progress: 进度回调 fn(msg)
    """

    def __init__(self, out_dir: str = "pdfs", email: str = DEFAULT_EMAIL,
                 progress=None, min_delay: float = 3.0):
        # normpath 归一路径分隔符（out_dir 常以正斜杠传入，join 会混用 \ /，
        # 导致落盘路径与 Excel 显示出现 C:/…\file 混用）
        self.out_dir = os.path.normpath(out_dir)
        self.email = email
        self.progress = progress or (lambda m: None)
        # biorxiv/medRxiv 逐篇下载间隔秒数（防 Cloudflare 1015 限流）。默认 3.0
        # （2026-09-06 实测安全）；批量调快可传更小值（如 1.2），失败会自动转
        # coze 兜底，不会卡死。
        self.min_delay = max(0.5, float(min_delay))
        os.makedirs(self.out_dir, exist_ok=True)
        # 整轮下载共用的每域名限速器（P0）：跨「直链下载 / coze 返直链下载」统一保距
        self._limiter = _PerHostRateLimiter()
        # 本地预筛（2026-09-07）：Unpaywall 查询结果缓存（按 DOI），整轮复用避免重复查询
        self._upw_cache: Dict[str, Any] = {}
        self._upw_email = _UPW_EMAIL

    def _log(self, msg: str):
        self.progress(msg)

    def _epmc_lookup_pdf_url(self, doi: str = "", pmcid: str = "", pmid: str = "") -> Optional[str]:
        """按 DOI/PMCID/PMID 解析 Europe PMC 的非 Cloudflare OA PDF 直链（本地兜底用）。

        返回 'https://europepmc.org/articles/{pmcid}?pdf=render' 或 None。
        限速：每次查询前走 _epmc_ratelimit()，严格 1.0 秒间隔（Europe PMC 官方限制 10 次/秒/IP，留足余量）。
        限流/过载处理：
          - 429：本次 session 剩余不再查（避免被封）。
          - 503/504：服务端过载，指数退避重试（最多 3 次），**不禁用整批**——
            避免把“瞬时限流”误判成“无副本”，导致批量回退到出版商直链而拉低回收率。
        """
        if getattr(self, "_epmc_disabled", False):
            return None
        if pmcid:
            return f"https://europepmc.org/articles/{pmcid}?pdf=render"
        if not doi and not pmid:
            return None
        for attempt in range(4):  # 1 次 + 503/504 重试 3 次
            if getattr(self, "_epmc_disabled", False):
                return None
            try:
                _epmc_ratelimit()
                q = f"DOI:{urllib.parse.quote(doi)}" if doi else f"PMID:{urllib.parse.quote(str(pmid))}"
                api = (f"https://www.ebi.ac.uk/europepmc/webservices/rest/search"
                       f"?query={q}&format=json&resultType=core")
                req = urllib.request.Request(api, headers={"User-Agent": "ct-literature-skill/1.0"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = json.loads(r.read().decode("utf-8"))
                for res in (data.get("resultList") or {}).get("result", [])[:3]:
                    pmcid2 = res.get("pmcid") or ""
                    ftl = res.get("fullTextUrlList") or {}
                    for u in ftl.get("fullTextUrl", []) or []:
                        if u.get("documentStyle") == "pdf" and u.get("availabilityCode") == "OA" and pmcid2:
                            return f"https://europepmc.org/articles/{pmcid2}?pdf=render"
                    # 退路：有 pmcid 且 hasPDF，仍给 render 链接
                    if pmcid2 and res.get("hasPDF"):
                        return f"https://europepmc.org/articles/{pmcid2}?pdf=render"
                return None  # 查到但无 OA 副本
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    self._epmc_disabled = True
                    self._log("[epmc] 被限流(429)，本次运行剩余文献不再查 Europe PMC")
                    return None
                elif e.code in (503, 504):
                    self._log(f"[epmc] 服务端过载 HTTP {e.code}，退避重试({attempt + 1}/3)")
                    import time as _t
                    _t.sleep(2 * (attempt + 1))
                    continue
                else:
                    self._log(f"[epmc] 查询失败 HTTP {e.code}")
                    return None
            except Exception as e:
                self._log(f"[epmc] 查询失败: {type(e).__name__}: {e}")
                return None
        return None

    def _download_direct(self, url: str, doi: str) -> Optional[str]:
        """直接下载（OA / 预印本 / Europe PMC），返回本地路径或 None。"""
        fname = _safe_filename(doi or url)
        out_path = os.path.join(self.out_dir, fname)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 100:
            return out_path
        if _download_to(url, out_path):
            return out_path
        return None

    def _download_direct_with_delay(self, url: str, doi: str, delay: float = 1.0) -> Optional[str]:
        """带间隔的直接下载（B：拉长间隔 + jitter 避免触发反爬）。

        biorxiv/medRxiv 限速较严 → 用 self.min_delay（默认 3-5s，可构造时调快）；
        其它源保持 2-3s。
        """
        import random as _rand
        if "biorxiv.org" in url or "medrxiv.org" in url:
            time.sleep(self.min_delay + _rand.uniform(0, 2.0))
        else:
            time.sleep(max(delay, 1.5) + _rand.uniform(0, 1.0))
        return self._download_direct(url, doi)

    # ── coze 统一传送（主路径，只做一次）──
    def _call_coze_unified(self, items: List[str]) -> Optional[List[Dict[str, Any]]]:
        """一次 coze 传送（统一契约）：输入统一标识列表（OA 直链或 DOI 混排），
        coze 端解码 + A→B 后，返回每篇记录（含 key / pdf_url / pdf_s3_url / status）。
        只传送一次；下载失败由 run() 标记 manual，不重发（符合「只做一次 coze 传送」）。
        请求失败 / 无结果返回 None（交由 _local_fallback）。
        """
        if not items:
            return []
        payload = {
            "source": "publisher_pdf_batch",
            "keyword": json.dumps(items, ensure_ascii=False),
            "mode": "search",
            "query_origin": _query_origin(),
            # ct-base coze_io_contract §1.2：技能版本号 = 顶层信封字段（与 query_origin 同级，禁止嵌套）
            "skill_version": _skill_version(),
            # ct-base coze_io_contract §1.1：locale = 界面/输出语言（顶层信封输出开关）
            "locale": _resolve_locale(),
            # ct-base coze_io_contract §1.1：user_language（输入语言提示）规范承载位 = 请求 params
            "params": {"user_language": _resolve_user_language()},
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(CT_SEARCH_ENDPOINT, data=body,
                                     headers=_headers(), method="POST")
        # 流式调用：stream_run 以 SSE 实时返回节点事件（workflow_start/node_end/workflow_end…），
        # 适合耗时较长的 PDF 批量下载——避免长连接被网关按单响应超时掐断。
        # 本地解析 SSE，从 workflow_end（或 node_end）事件提取最终 projects。
        try:
            with urllib.request.urlopen(req, timeout=1200) as r:
                projects = _parse_coze_stream(r, self._log)
        except Exception as e:
            self._log(f"[coze] 流式传送失败: {type(e).__name__}: {e}")
            return None
        if projects is None:
            self._log("[coze] 流式响应未解析到 projects（可能 rejected / 执行失败）")
            return None
        return projects

    # ── 本地兜底解码（coze 不可用 / skip_coze）──
    def _local_fallback(self, items: List[str],
                        work_by_key: Dict[str, Any]) -> List[Dict[str, Any]]:
        """coze 不可用时的本地兜底：仅能拿到 Europe PMC 非 Cloudflare 副本并直下；
        其余（付费墙/重定向器/Cloudflare 出版商）本地无浏览器，标记 manual。
        """
        out = []
        for key in items:
            w = work_by_key.get(key, {}) or {}
            doi = (w.get("doi") or "") or _extract_doi_from_url(key) or ""
            url = None
            if doi:
                epmc = self._epmc_lookup_pdf_url(doi, w.get("pmcid") or "", w.get("pmid") or "")
                if epmc:
                    url = epmc
            if url:
                out.append({"key": key, "doi": doi, "pdf_url": url, "pdf_s3_url": None,
                            "status": "ok", "via": "epmc_local"})
            else:
                out.append({"key": key, "doi": doi, "pdf_url": None, "pdf_s3_url": None,
                            "status": "manual",
                            "error": "本地无浏览器，且无 Europe PMC 副本"})
        return out

    # ── 本地预筛（2026-09-07）：coze 改为「本地逐项预筛后的最后手段」──
    # 路由规则（用户 2026-09-07）：
    #   ① 本地可直接处理/下载的预印本直链 → 本地下载，不送 coze；
    #   ② 非 OA 论文：本地查有无更早预印本，有则本地下载，否则也不送 coze；
    #   ③ 仅当「本地无法直接下载」且「有 OA 或预印本链接」时才送 coze。
    def _upw_look(self, doi: str) -> Optional[Dict[str, Any]]:
        """查 Unpaywall（按 DOI），返回解析后的 JSON dict；不可达/异常返回 None（未知）。

        返回 None 表示「查询未成功」（网络/超时/429），此时路由应保守地回退到 coze，
        而非判定为「无 OA」直接跳过——避免误杀可下载文献。
        命中 200（含 is_oa=false 的闭源论文）正常返回 dict；结果按 DOI 缓存整轮复用。
        """
        if not doi:
            return None
        if doi in self._upw_cache:
            return self._upw_cache[doi]
        try:
            u = "https://api.unpaywall.org/v2/%s?email=%s" % (
                urllib.parse.quote(doi), urllib.parse.quote(self._upw_email))
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (research audit)"})
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.loads(r.read().decode("utf-8"))
            self._upw_cache[doi] = d
            return d
        except Exception:
            self._upw_cache[doi] = None
            return None

    def _prefetch_unpaywall(self, works: List[Dict[str, Any]]):
        """并发预取所有可能需要 Unpaywall 信号的 DOI（受 _UPW_CONCURRENCY 限流）。"""
        import concurrent.futures as _cf
        dois = []
        for w in works:
            doi = (w.get("doi") or "").strip()
            if not doi or doi in self._upw_cache:
                continue
            oa = (w.get("open_access_url") or "").strip()
            pp = w.get("preprint")
            if oa and _looks_like_direct_pdf(oa):
                continue
            if isinstance(pp, dict) and pp.get("url") and _looks_like_direct_pdf(pp["url"]):
                continue
            dois.append(doi)
        if not dois:
            return
        sem = threading.Semaphore(_UPW_CONCURRENCY)

        def _one(d: str):
            with sem:
                self._upw_look(d)

        with _cf.ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(_one, dois))

    def _work_is_oa(self, w: Dict[str, Any]) -> bool:
        """work 是否带 OA 信号（直接字段，优先用上游已算好的 is_oa / oa_status）。"""
        if w.get("is_oa"):
            return True
        oa = w.get("oa_status")
        if isinstance(oa, str) and oa.lower() in ("gold", "green", "bronze", "hybrid"):
            return True
        return False

    def _find_earlier_preprint(self, doi: str, title: str):
        """本地查找「可下载的更早预印本 / OA 直链」。返回 (kind, url) 或 None。

        kind ∈ {"oa", "preprint"}：二者都直接可本地下载，区别仅用于统计/日志。
          - oa：Unpaywall 返回的 OA 直链（url_for_pdf），属「有 OA 但本地直下」；
          - preprint：Europe PMC PPR 索引按标题检索到的预印本 PDF（bioRxiv/medRxiv/arXiv 等）。
        仅做本地只读查询，不送 coze；查不到返回 None（交由路由决定 coze 或跳过）。
        """
        # 1) Unpaywall：OA 直链（url_for_pdf）优先
        d = self._upw_look(doi) if doi else None
        if d is not None and d.get("is_oa"):
            loc = d.get("best_oa_location") or {}
            u = loc.get("url_for_pdf") or loc.get("pdf_url")
            if u and _looks_like_pdf_url(u):
                return ("oa", u)
        # 2) Europe PMC PPR 按标题检索更早预印本（复用 preprint_fallback，避免重复实现）
        if title:
            try:
                from adapters.preprint_fallback import _epmc_preprint_search
                for cand in _epmc_preprint_search(title):
                    u = cand.get("pdf_url")
                    if u and _looks_like_pdf_url(u):
                        return ("preprint", u)
            except Exception:
                pass
        return None

    def _classify(self, w: Dict[str, Any], skip_coze: bool) -> Tuple[str, Optional[str]]:
        """单篇路由分类。返回 (kind, url_or_key)。

        kind ∈ {"local_direct", "local_preprint", "coze", "skip"}。
          - local_direct   : open_access_url 已是真实 PDF 直链 → 本地下载，不送 coze
          - local_preprint : 上游已富集预印本 / 本地查到更早预印本或 OA 直链 → 本地下载
          - coze           : 本地无法直接下，但有 OA 或预印本链接 → 送 coze 解码
          - skip           : 非 OA、无可用预印本、无 OA 链接 → 不送 coze（避免无效调用）
        """
        oa = (w.get("open_access_url") or "").strip()
        doi = (w.get("doi") or "").strip()
        pp = w.get("preprint")
        title = (w.get("title") or "").strip()
        is_oa = self._work_is_oa(w)

        # ① 直链 PDF（OA/预印本）→ 本地
        if oa and _looks_like_direct_pdf(oa):
            return ("local_direct", oa)
        # 上游已富集的预印本候选（--preprint-fallback）→ 本地
        if isinstance(pp, dict) and pp.get("url") and _looks_like_direct_pdf(pp["url"]):
            return ("local_preprint", pp["url"])

        # ② 本地解析：OA 直链 / 更早预印本（本地只读，非 coze）
        lp = self._find_earlier_preprint(doi, title)
        if lp:
            return ("local_preprint", lp[1])

        # ③ 有 OA 或预印本链接但本地无法直接下 → coze
        has_signal = bool(oa) or bool(pp) or is_oa
        if not has_signal and doi:
            d = self._upw_look(doi)
            # Unpaywall 可达且确认 is_oa → 有信号；不可达（None）→ 保守送 coze
            if d is not None and d.get("is_oa"):
                has_signal = True
            elif d is None:
                has_signal = True
        if has_signal:
            return ("coze", oa or doi)
        # ② 负向前兜底：非 OA 但可能已 deposited PMC 作者手稿（Unpaywall 漏标 is_oa 的盲区）。
        #    本地按 DOI/PMID 查 Europe PMC 主库（注意：非 _find_earlier_preprint 用的 PPR 预印本索引），
        #    命中 PMC 副本即本地下载，仍不送 coze（符合「非 OA 不送云端」红线）。
        #    复用 _epmc_lookup_pdf_url（自带 1.0s 限流 + 429 禁用保护），已 used in coze 兜底路径，行为一致。
        if doi or w.get("pmid"):
            epmc = self._epmc_lookup_pdf_url(doi=doi, pmid=(w.get("pmid") or ""))
            if epmc:
                return ("local_preprint", epmc)
        # ③ 负向：非 OA、无预印本、无 OA 链接、无 PMC 手稿 → 跳过 coze
        return ("skip", None)

    def run(self, works: List[Dict[str, Any]], skip_coze: bool = False) -> Dict[str, Any]:
        """Batch PDF download (four-bucket routing: local direct / local preprint / coze / skip).

        Routing rules (user 2026-09-07):
          - local-direct PDF (preprint / OA direct link via _looks_like_direct_pdf) -> local_direct, no coze
          - non-OA paper: first check local "earlier preprint / OA direct link" (_find_earlier_preprint);
            if found -> local_preprint local download; if not and no OA/preprint signal -> skip (no coze)
          - only when "cannot download locally" AND "has OA or preprint link" -> coze decode
        Speed arch (2026-09-06): local download || coze decode; coze sub-batch pipes download.
        """
        stats = {"total": len(works), "ok": 0, "coze_sent": 0,
                 "coze_ok": 0, "manual_needed": 0, "failed": 0,
                 "skipped_no_id": 0, "skipped_no_oa": 0, "batches": 0,
                 "local_direct": 0, "local_preprint": 0,
                 "local_fallback_coze_sent": 0, "local_fallback_coze_ok": 0}

        # 0) batch timing (user 2026-09-07: every PDF batch reports elapsed time)
        _t_wall = time.strftime("%Y-%m-%dT%H:%M:%S")
        _t_mono = time.monotonic()

        # 1) hard cap (user 2026-09-06): >MAX_TOTAL_ITEMS rejected, never split
        if len(works) > MAX_TOTAL_ITEMS:
            stats["rejected"] = True
            stats["rejected_reason"] = (
                f"download {len(works)} items exceeds single-run cap {MAX_TOTAL_ITEMS}; "
                f"splitting serially would always time out. Narrow scope: "
                f"top-{MAX_TOTAL_ITEMS} by citations / single source / multiple small batches.")
            self._log(f"[PDF] rejected: {len(works)} > cap {MAX_TOTAL_ITEMS}. {stats['rejected_reason']}")
            for w in works:
                w["local_pdf_path"] = None
                w["pdf_download_note"] = stats["rejected_reason"]
            stats["started_at"] = _t_wall
            stats["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            stats["elapsed_s"] = round(time.monotonic() - _t_mono, 1)
            stats["elapsed_min"] = round(stats["elapsed_s"] / 60.0, 2)
            return stats

        import threading as _th
        stats_lock = _th.Lock()

        # 2) prefetch Unpaywall (local prescreen; classify reuses cache)
        self._prefetch_unpaywall(works)

        # 3) classify into buckets (local-first prescreen)
        work_by_key: Dict[str, Any] = {}
        local_tasks = []      # (url, doi, work, label)
        coze_keys: List[str] = []
        for w in works:
            oa = (w.get("open_access_url") or "").strip()
            doi = (w.get("doi") or "").strip()
            key = oa or doi
            if not key:
                w["local_pdf_path"] = None
                w["pdf_download_note"] = "no DOI / OA, cannot download"
                stats["skipped_no_id"] += 1
                continue
            kind, val = self._classify(w, skip_coze)
            if kind == "local_direct":
                local_tasks.append((val, doi or val, w, "oa_direct_local"))
                w["pdf_via"] = "oa_direct_local"  # 预置，下载失败时 local_failed_keys 收集才能识别
                stats["local_direct"] += 1
            elif kind == "local_preprint":
                local_tasks.append((val, doi or val, w, "preprint_local"))
                w["pdf_via"] = "preprint_local"
                stats["local_preprint"] += 1
            elif kind == "coze":
                coze_keys.append(val)
                work_by_key[val] = w
            else:  # skip: non-OA and no preprint -> do NOT call coze
                w["local_pdf_path"] = None
                w["pdf_download_note"] = "non-OA and no usable preprint; skip cloud decode (per rule)"
                stats["skipped_no_oa"] += 1

        self._log(PDF_DOWNLOAD_NOTICE)
        self._log(f"[PDF] route: local_direct {stats['local_direct']} / local_preprint "
                  f"{stats['local_preprint']} / coze {len(coze_keys)} / "
                  f"skip(nonOA no preprint) {stats['skipped_no_oa']}")

        # ── download helpers ────────────────────────────────────────────────────
        def _download_one(url: str, doi: str, work: Dict[str, Any], label: str) -> bool:
            host = urlparse(url).netloc
            low = url.lower()
            if "biorxiv.org" in low or "medrxiv.org" in low:
                delay, jitter = self.min_delay, 0.5
            elif "amazonaws" in host or "s3" in host or "cloudfront" in host:
                delay, jitter = 0.1, 0.1
            else:
                delay, jitter = 1.0, 0.3
            self._limiter.acquire(host, delay + random.uniform(0, jitter))
            path = self._download_direct(url, doi)
            with stats_lock:
                if path:
                    work["local_pdf_path"] = path
                    work["pdf_via"] = label
                    work.pop("pdf_download_note", None)
                    stats["ok"] += 1
                    self._log(f"[pdf] OK {label} saved -> {_safe_filename(doi or url)}")
                    return True
                work["local_pdf_path"] = None
                work["pdf_download_note"] = "download failed (publisher block or network error)"
                self._log(f"[pdf] FAIL {label} -> {_safe_filename(doi or url)}")
                return False

        def _download_batch(recs: List[Dict[str, Any]], label: str):
            tasks = []
            for rec in recs:
                k = rec.get("key") or rec.get("doi") or ""
                w = work_by_key.get(k)
                if not w or w.get("local_pdf_path"):
                    continue
                url = rec.get("pdf_s3_url") or rec.get("pdf_url")
                if rec.get("status") == "ok" and url:
                    tasks.append((url, (w.get("doi") or "").strip() or k, w,
                                  rec.get("via") or label))
            if not tasks:
                return
            ok_n = 0
            with ThreadPoolExecutor(max_workers=MAX_DOWNLOAD_WORKERS) as ex:
                futs = [ex.submit(_download_one, u, d, w, v) for (u, d, w, v) in tasks]
                for f in as_completed(futs):
                    try:
                        if f.result():
                            ok_n += 1
                    except Exception:
                        pass
            self._log(f"[pdf] {label} concurrent download done: {ok_n}/{len(tasks)} ok")

        # 4) local tasks concurrent download (parallel with coze decode in bg)
        if local_tasks:
            self._log(f"[pdf] local direct/preprint concurrent download: {len(local_tasks)} "
                      f"(max workers {MAX_DOWNLOAD_WORKERS})")
            with ThreadPoolExecutor(max_workers=MAX_DOWNLOAD_WORKERS) as ex:
                futs = [ex.submit(_download_one, u, d, w, v) for (u, d, w, v) in local_tasks]
                for _ in as_completed(futs):
                    pass
            self._log("[pdf] local direct/preprint download done")

        # 4b) 收集本地下载失败的条目，送 coze 兜底重试（2026-09-07 新增）
        #    仅当本地下载失败、且该条目有 DOI 或 URL 可送 coze 时才重试。
        #    重试在主线 coze 批次完成后串行发送，避免并发限流。
        local_failed_keys: List[str] = []
        for w in works:
            if w.get("local_pdf_path"):
                continue
            # 只重试原本走 local_direct/local_preprint 的条目（原本就走 coze 的已在 coze_keys 里）
            via = w.get("pdf_via") or ""
            note = w.get("pdf_download_note") or ""
            if via in ("oa_direct_local", "preprint_local") or "download failed" in note:
                doi = (w.get("doi") or "").strip()
                oa = (w.get("open_access_url") or "").strip()
                key = oa or doi
                if key:
                    local_failed_keys.append(key)
                    work_by_key[key] = w
        if local_failed_keys:
            self._log(f"[pdf] local failed {len(local_failed_keys)} items -> coze fallback retry")

        # 5) coze decode (bg thread): coze_keys split into <=COZE_SUB_BATCH sub-batches,
        #    each returned batch pipes into concurrent download (P1 pipeline).
        coze_box: Dict[str, Any] = {"projects": None, "done": False}

        def _coze_worker():
            try:
                if skip_coze:
                    coze_box["projects"] = None
                    coze_box["done"] = True
                    return
                collected: List[Dict[str, Any]] = []
                # 主 coze 批次（有 coze_keys 时才执行）
                if coze_keys:
                    subs = [coze_keys[i:i + COZE_SUB_BATCH]
                            for i in range(0, len(coze_keys), COZE_SUB_BATCH)] or [[]]
                    stats["batches"] = len(subs)
                    self._log(f"[coze] bg decode {len(coze_keys)} items ({len(subs)} sub-batches, "
                              f"<= {COZE_SUB_BATCH} each, interval {COZE_BATCH_INTERVAL}s)...")
                    for ci, sub in enumerate(subs, 1):
                        if not sub:
                            continue
                        if ci > 1:
                            # sub-batch 之间强制间隔 ≥ COZE_BATCH_INTERVAL 秒，避免触发限流
                            self._log(f"[coze] waiting {COZE_BATCH_INTERVAL}s before sub-batch {ci}...")
                            time.sleep(COZE_BATCH_INTERVAL)
                        self._log(f"[coze] sub-batch {ci}/{len(subs)}: {len(sub)} items sent...")
                        part = self._call_coze_unified(sub)
                        if part is None:
                            self._log(f"[coze] sub-batch {ci}/{len(subs)} send failed, local fallback")
                            part = self._local_fallback(sub, work_by_key)
                        collected.extend(part)
                        ok_n = len([p for p in part if p.get("status") == "ok"])
                        self._log(f"[coze] sub-batch {ci}/{len(subs)} returned: {ok_n} links -> download now")
                        _download_batch(part, "coze")
                    stats["coze_sent"] = len(coze_keys)
                    self._log(f"[coze] decode done: {len(collected)} records")
                # ── 本地下载失败的条目，送 coze 兜底重试 ──
                if local_failed_keys and not skip_coze:
                    self._log(f"[coze] local-fallback retry: {len(local_failed_keys)} items sent...")
                    stats["local_fallback_coze_sent"] = len(local_failed_keys)
                    time.sleep(COZE_BATCH_INTERVAL)
                    fb_part = self._call_coze_unified(local_failed_keys)
                    if fb_part is None:
                        self._log("[coze] local-fallback retry send failed, local fallback")
                        fb_part = self._local_fallback(local_failed_keys, work_by_key)
                    fb_ok = len([p for p in fb_part if p.get("status") == "ok"])
                    stats["local_fallback_coze_ok"] = fb_ok
                    self._log(f"[coze] local-fallback retry returned: {fb_ok}/{len(local_failed_keys)} ok")
                    _download_batch(fb_part, "coze_local_fallback")
                    collected.extend(fb_part)
                # 汇总 ok 数
                coze_box["projects"] = collected
                stats["coze_ok"] = len([p for p in collected
                                        if p.get("status") == "ok"
                                        and (p.get("pdf_url") or p.get("pdf_s3_url"))])
                self._log(f"[coze] all done: {len(collected)} records, {stats['coze_ok']} links parsed")
            except Exception as _ce:
                self._log(f"[coze] bg decode error: {type(_ce).__name__}: {_ce}")
                coze_box["projects"] = None
            finally:
                coze_box["done"] = True

        _coze_thread = None
        if (coze_keys or local_failed_keys) and not skip_coze:
            _coze_thread = _th.Thread(target=_coze_worker, daemon=True, name="pdf-coze-decode")
            _coze_thread.start()
            self._log(f"[pdf] local download || coze decode: local {len(local_tasks)} / coze {len(coze_keys)}")

        # P2: heartbeat every 10s during coze decode wait
        _hb_stop = _th.Event()

        def _heartbeat():
            t0 = time.time()
            while not _hb_stop.is_set():
                if _coze_thread is None or not _coze_thread.is_alive():
                    break
                _hb_stop.wait(10)
                if _hb_stop.is_set():
                    break
                el = int(time.time() - t0)
                self._log(f"[pdf] decoding... elapsed {el}s (saved {stats['ok']} / coze decoding)")
        _hb = _th.Thread(target=_heartbeat, daemon=True, name="pdf-heartbeat")
        _hb.start()

        # 5b) wait for coze thread (local download already done; skip items never entered coze)
        if _coze_thread is not None and _coze_thread.is_alive():
            self._log("[coze] waiting for decode thread...")
            _coze_thread.join(timeout=1200)
        _hb_stop.set()
        _hb.join(timeout=2)

        projects = coze_box.get("projects")
        if projects:
            _download_batch(projects, "coze")
        # reconciliation: not-saved (non-reject/non-skip/non-noid) counts as manual_needed
        if not stats.get("rejected"):
            stats["manual_needed"] = max(
                0, stats["total"] - stats["ok"]
                - stats["skipped_no_id"] - stats["skipped_no_oa"])
        # batch-level timing (user 2026-09-07): surface elapsed for user feedback
        stats["started_at"] = _t_wall
        stats["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        stats["elapsed_s"] = round(time.monotonic() - _t_mono, 1)
        stats["elapsed_min"] = round(stats["elapsed_s"] / 60.0, 2)
        self._log(f"[PDF] batch finished: ok {stats['ok']}/{stats['total']}, "
                  f"elapsed {stats['elapsed_s']}s ({stats['elapsed_min']} min), "
                  f"{stats['started_at']} -> {stats['finished_at']}")
        return stats


if __name__ == "__main__":
    # 独立测试：从 stdin 读 DOI 列表
    if len(sys.argv) > 1:
        items = sys.argv[1:]
        works = [{"doi": d, "title": "test"} for d in items]
        dl = PdfDownloader(out_dir="pdfs")
        stats = dl.run(works)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        for w in works:
            print(f"  {w['doi']}: {w.get('local_pdf_path') or w.get('pdf_download_note')}")
