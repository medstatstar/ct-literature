#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
i18n.py -- bilingual (EN/ZH) localization for the ct- skill library (shared base layer)

Provides:
  - is_chinese_os(): detect if the OS locale is Chinese
  - t(key, **kwargs): translate a message key to the current locale
  - set_lang(locale): manually override the locale (for testing)

Rules (per ~/.workbuddy/MEMORY.md "双语语言策略"):
  - Default: English
  - Auto-switch to Chinese when OS locale contains zh/CN
  - Code output (R/Python) is NOT affected by language policy

Usage:
  from i18n import t
  print(t("error.rscript_not_found"))
  print(t("info.result_saved", path="/tmp/x.json"))
"""

import os
import sys


# ═══════════════════════════════════════════════════════════════════════════
# Locale detection / 系统语言检测
# ═══════════════════════════════════════════════════════════════════════════

_OVERRIDE_LANG = None


def set_lang(locale_code):
    """Manually override language (for testing). Pass None to reset to auto-detect."""
    global _OVERRIDE_LANG
    _OVERRIDE_LANG = locale_code


def is_chinese_os():
    """Detect if the OS is Chinese (zh-CN, zh-TW, zh-HK, etc.).

    Detection order:
      1. Environment variables: LANGUAGE / LC_ALL / LC_MESSAGES / LANG
      2. Windows API: GetLocaleInfoW + registry (LocaleName)
      3. Python locale module: getdefaultlocale()
    """
    global _OVERRIDE_LANG
    if _OVERRIDE_LANG is not None:
        return _OVERRIDE_LANG == "zh"

    # 1. Check environment variables
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var, "")
        if val.lower().startswith("zh"):
            return True

    # 2. Windows-specific detection
    if sys.platform == "win32":
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(85)
            ctypes.windll.kernel32.GetLocaleInfoW(0x0400, 0x00000005, buf, 85)
            if buf.value.lower().startswith("zh"):
                return True
        except Exception:
            pass

        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Control Panel\International"
            )
            locale_name = winreg.QueryValueEx(key, "LocaleName")[0]
            winreg.CloseKey(key)
            if locale_name.lower().startswith("zh"):
                return True
        except Exception:
            pass

    # 3. Python locale module fallback
    try:
        import locale
        loc = locale.getdefaultlocale()[0]
        if loc and loc.lower().startswith("zh"):
            return True
    except Exception:
        pass

    return False


def _current_lang():
    """Return 'zh' or 'en'."""
    return "zh" if is_chinese_os() else "en"


# ═══════════════════════════════════════════════════════════════════════════
# Message dictionary / 消息字典
# ═══════════════════════════════════════════════════════════════════════════

_MESSAGES = {
    # ── Generic messages shared by ALL ct- skills / 全库通用消息 ──
    "dry_run.not_executed": {
        "en": "[DRY RUN — code not executed. Remove --dry-run to execute.]",
        "zh": "[DRY RUN — 代码未执行。去掉 --dry-run 以执行。]",
    },
    "safe_preview.not_executed": {
        "en": "[SAFE PREVIEW] R code was NOT executed. Re-run with --yes to compute the result.",
        "zh": "[安全预览] R 代码未执行。追加 --yes 重新运行以计算结果。]",
    },
    "exec.running": {
        "en": "[EXECUTING R CODE...]",
        "zh": "[正在执行 R 代码...]",
    },
    "info.r_code_shown_default": {
        "en": "[INFO] R code is shown by default in preview mode. Re-run with --show-code while using --yes to also display it during execution.",
        "zh": "[提示] 预览模式默认展示 R 代码。执行时追加 --show-code 可同时查看代码。]",
    },
    "info.result_saved": {
        "en": "Result JSON saved to: {path}",
        "zh": "结果 JSON 已保存至：{path}",
    },
    "info.png_saved": {
        "en": "PNG saved to: {path}",
        "zh": "PNG 已保存至：{path}",
    },
    "error.rscript_not_found": {
        "en": "[ERROR] Rscript not found or invalid. Set RSCRIPT_PATH env or install R.",
        "zh": "[错误] 未找到 Rscript 或路径无效。请设置 RSCRIPT_PATH 环境变量或安装 R。",
    },
    "error.invalid_temp_path": {
        "en": "[ERROR] Invalid temp path; execution refused.",
        "zh": "[错误] 临时路径无效；执行已拒绝。]",
    },
    "error.r_timeout": {
        "en": "[ERROR] R execution timed out (300s limit)",
        "zh": "[错误] R 执行超时（300 秒限制）]",
    },
    "error.exec_failed": {
        "en": "[ERROR] Execution failed: {name}",
        "zh": "[错误] 执行失败：{name}",
    },
    "error.invalid_install_path": {
        "en": "[ERROR] Invalid install script path; execution refused.",
        "zh": "[错误] 安装脚本路径无效；执行已拒绝。]",
    },
    "error.rscript_not_found_install": {
        "en": "[ERROR] Rscript not found or invalid. Is R installed?",
        "zh": "[错误] 未找到 Rscript 或路径无效。是否已安装 R？]",
    },
    "error.generic": {
        "en": "ERROR: {msg}",
        "zh": "错误：{msg}",
    },
    "error.val_err": {
        "en": "ERROR: {msg}",
        "zh": "错误：{msg}",
    },
    "validation.failed": {
        "en": "Parameter validation failed:",
        "zh": "参数校验失败：",
    },
    "validation.range_error_gt": {
        "en": "--{label} must be > {bound} (got {val})",
        "zh": "--{label} 必须 > {bound}（当前值 {val}）",
    },
    "validation.range_error_lt": {
        "en": "--{label} must be < {bound} (got {val})",
        "zh": "--{label} 必须 < {bound}（当前值 {val}）",
    },
    "install.cmd_header": {
        "en": "[R package commands — for review only, NOT executed]",
        "zh": "[R 包安装命令 — 仅供审阅，未执行]",
    },
    "install.cran_warning": {
        "en": "This command will download and install {n} R packages from CRAN (the ONLY network operation in this skill).",
        "zh": "此命令会**从 CRAN 联网下载并安装** {n} 个 R 包（即本技能唯一会联网的操作）。",
    },
    "install.confirm_prompt": {
        "en": "If confirmed, re-run with --run-install to actually download:",
        "zh": "如确认无误，请重新运行并追加 --run-install 才会真正联网安装：",
    },
    "install.manual_alt": {
        "en": "Or paste the above command into an R console to install manually.",
        "zh": "或在 R 控制台中手动粘贴上述命令自行安装。",
    },
    "install.network_warning_en": {
        "en": "⚠️  NETWORK INSTALL: the following R code will download packages from CRAN",
        "zh": "⚠️  联网安装：以下 R 代码将从 CRAN 下载并安装 R 包（供应链风险由你知情触发）",
    },
    "install.code_header": {
        "en": "[R CODE — will be executed by Rscript]",
        "zh": "[R 代码 — 将由 Rscript 执行]",
    },
    "header.r_code": {
        "en": "[R CODE — generated for this analysis]",
        "zh": "[R 代码 — 本次分析生成]",
    },
    "header.install_cmd": {
        "en": "[R package commands — for review only, NOT executed]",
        "zh": "[R 包安装命令 — 仅供审阅，未执行]",
    },
    "openalex.key_notice": {
        "en": (
            "[KEY] No OpenAlex API key found — running in keyless mode "
            "(capped at 100 credits/day since 2026-02-13).\n"
            "      Apply for a FREE key (~30s) at https://openalex.org/settings/api, then one of:\n"
            "        • cp .env.example .env  and set OPENALEX_API_KEY=your_key   (recommended, zero extra flags)\n"
            "        • export OPENALEX_API_KEY=your_key\n"
            "        • pass --openalex-key your_key\n"
            "      See references/openalex_key.md for details.\n"
            "      Recommended (conversational): paste your key to the WorkBuddy assistant "
            "and it writes it into ct-literature/.env for you."
        ),
        "zh": (
            "[密钥] 未检测到 OpenAlex API key —— 当前为无 key 模式"
            "（自 2026-02-13 起限 100 credits/天）。\n"
            "      请免费申请 key（约 30 秒）：https://openalex.org/settings/api ，随后三选一：\n"
            "        • cp .env.example .env 并填入 OPENALEX_API_KEY=你的key（推荐，零额外参数）\n"
            "        • 设置环境变量 export OPENALEX_API_KEY=你的key\n"
            "        • 传 --openalex-key 你的key\n"
            "      详见 references/openalex_key.md。\n"
            "      配置方式（推荐·对话式）：把 key 直接发给 WorkBuddy 助手，它会写入 "
            "ct-literature/.env，你无需手动编辑文件。"
        ),
    },
    # ── ct-literature: Semantic Scholar key notice / S2 密钥提示 ──
    "semantic_scholar.key_notice": {
        "en": (
            "[KEY] Semantic Scholar API key not found — running keyless "
            "(strict ~1 req/s rate limit, prone to HTTP 429 and graceful degradation; "
            "OpenAlex + Europe PMC still produce results).\n"
            "      Apply for a FREE key (form-based, manually reviewed, NOT auto-issued; "
            "please wait after applying): "
            "https://www.semanticscholar.org/product/api#api-key-form\n"
            "      When no key is configured this source is skipped entirely "
            "(no network request); to configure (recommended, conversational): paste your "
            "key to the WorkBuddy assistant and it writes it into ct-literature/.env for you."
        ),
        "zh": (
            "[密钥] 未检测到 Semantic Scholar API Key，当前以无 key 模式运行"
            "（限流严格，易触发 429 并自动降级，不影响 OpenAlex / Europe PMC 主源产出）。\n"
            "      申请免费 key（填表，需人工审核、非自动发放，申请后请等待）："
            "https://www.semanticscholar.org/product/api#api-key-form\n"
            "      未配置 key 时本源自动跳过（不发起请求）；配置方式（推荐·对话式）："
            "把 key 直接发给 WorkBuddy 助手，它会写入 ct-literature/.env，你无需手动编辑文件。"
        ),
    },
    "semantic_scholar.skip_no_key": {
        "en": "[SKIP] Semantic Scholar skipped — no API key configured "
              "(form-based, manually reviewed, not auto-issued); no network request made.",
        "zh": "[跳过] Semantic Scholar 未配置 key（需填表人工审核、非自动发放）"
              " -> 跳过本源，不发起网络请求。",
    },
}


def t(key, **kwargs):
    """Translate a message key to the current locale.

    Args:
        key: message identifier in _MESSAGES
        **kwargs: format placeholders (e.g., path="/tmp/x.json")

    Returns:
        Localized string. Falls back to the key itself if not found.
    """
    lang = _current_lang()
    entry = _MESSAGES.get(key)
    if entry is None:
        return key
    text = entry.get(lang, entry.get("en", key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


# Back-compatible alias
_ = t
