#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
i18n.py -- bilingual (EN/ZH) localization for ct-literature.

Provides:
  - is_chinese_os(): detect if the OS locale is Chinese
  - t(key, **kwargs): translate a message key to the current locale
  - set_lang(locale): manually override the locale (for testing)

Rules (per ~/.workbuddy/MEMORY.md "双语语言策略"):
  - Default: English
  - Auto-switch to Chinese when OS locale contains zh/CN
  - Code output is NOT affected by language policy

Usage:
  from i18n import t
  print(t("info.result_saved", path="/tmp/x.json"))

NOTE: ct-literature is a pure-Python literature-search skill and does NOT
execute R. All R-related message keys were removed; API-key configuration is
documented in references/openalex_key.md (self-config only -- never paste a
real key into chat; see its §7 Security notes).
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
    # ── Generic messages / 通用消息 ──
    "info.result_saved": {
        "en": "Result JSON saved to: {path}",
        "zh": "结果 JSON 已保存至：{path}",
    },
    "info.png_saved": {
        "en": "PNG saved to: {path}",
        "zh": "PNG 已保存至：{path}",
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
    # ── ct-literature: OpenAlex key notice / OpenAlex 密钥提示 ──
    "openalex.key_notice": {
        "en": (
            "[KEY] No OpenAlex API key found — running in keyless mode "
            "(capped at 100 credits/day since 2026-02-13).\n"
            "      Apply for a FREE key (~30s) at https://openalex.org/settings/api, then one of:\n"
            "        • cp .env.example .env  and set OPENALEX_API_KEY=your_key   (recommended, zero extra flags)\n"
            "        • export OPENALEX_API_KEY=your_key\n"
            "        • pass --openalex-key your_key\n"
            "      See references/openalex_key.md for details. "
            "Your key is for your own use only, stored locally in .env / env var, "
            "and sent solely to the official OpenAlex API over HTTPS — never to any third party. "
            "Do not paste a real key into chat (see §7 Security notes)."
        ),
        "zh": (
            "[密钥] 未检测到 OpenAlex API key —— 当前为无 key 模式"
            "（自 2026-02-13 起限 100 credits/天）。\n"
            "      请免费申请 key（约 30 秒）：https://openalex.org/settings/api ，随后三选一：\n"
            "        • cp .env.example .env 并填入 OPENALEX_API_KEY=你的key（推荐，零额外参数）\n"
            "        • 设置环境变量 export OPENALEX_API_KEY=你的key\n"
            "        • 传 --openalex-key 你的key\n"
            "      详见 references/openalex_key.md。key 仅你自用、本地存储于 .env / 环境变量，"
            "仅通过 HTTPS 发往官方 OpenAlex API，不会发给任何第三方。"
            "请勿在对话中粘贴真实 key（见 §7 安全说明）。"
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
            "(no network request). Configure via .env / env var / --openalex-key (see "
            "references/openalex_key.md). Your key is for your own use only, stored locally, "
            "and sent solely to the official Semantic Scholar API over HTTPS. "
            "Do not paste a real key into chat."
        ),
        "zh": (
            "[密钥] 未检测到 Semantic Scholar API Key，当前以无 key 模式运行"
            "（限流严格，易触发 429 并自动降级，不影响 OpenAlex / Europe PMC 主源产出）。\n"
            "      申请免费 key（填表，需人工审核、非自动发放，申请后请等待）："
            "https://www.semanticscholar.org/product/api#api-key-form\n"
            "      未配置 key 时本源自动跳过（不发起请求）；通过 .env / 环境变量 / "
            "--openalex-key 配置（详见 references/openalex_key.md）。key 仅你自用、本地存储，"
            "仅通过 HTTPS 发往官方 Semantic Scholar API。请勿在对话中粘贴真实 key。"
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
