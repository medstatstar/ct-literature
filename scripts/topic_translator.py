#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
topic_translator.py — 检索词 中文→英文 翻译（离线词典，零外部依赖、零网络）

数据源（references/，均为 中文key → 英文value 方向）：
  - term_map.json       中文医学通用术语 → 英文（~180 条，含肺癌/间质性肺病/免疫治疗等）
  - drug_name_map.json  中文药物名 → 英文 INN/通用名（~470 条，奥希替尼→osimertinib 等）

策略：贪心最长匹配（长词优先，避免"肺癌"吃掉"非小细胞肺癌"）；未命中的中文片段
     保留原样。只做词典查表，不做任何外部翻译 API / 网络请求。

输出 dict：
  topic_zh       原始中文检索词
  topic_en       翻译后的英文检索词（未命中中文片段保留）
  translated     bool：是否发生翻译（有中文字符即视为尝试翻译）
  hits           [(zh, en), ...]：命中的术语替换对（去重、按首次出现顺序）
  untranslated   [str, ...]：替换后残留的中文片段（未命中词典）

用法：
  from topic_translator import translate_topic
  info = translate_topic("奥希替尼 间质性肺病")
  # info["topic_en"] -> "osimertinib interstitial lung disease (ILD)"
"""

import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_REF = os.path.join(_HERE, "..", "references")
_HAN = re.compile(r"[\u4e00-\u9fff]+")

_CACHE = None


def load_dict():
    """合并 term_map.json + drug_name_map.json 的中→英条目（懒加载 + 缓存）。"""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    mapping = {}
    # (文件名, 值是否 list 取第一个)
    for fname, take_first in (("term_map.json", False), ("drug_name_map.json", True)):
        p = os.path.join(_REF, fname)
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        for k, v in data.items():
            if k == "_meta" or not k or not isinstance(k, str):
                continue
            # 只收中文 key（term_map 有少数英文 key 反向条目，跳过以免误替换英文检索词）
            if not _HAN.search(k):
                continue
            if isinstance(v, list):
                v = v[0] if v else None
            if isinstance(v, str) and v.strip():
                mapping[k] = v.strip()
    _CACHE = mapping
    return mapping


def translate_topic(topic):
    """翻译检索词（离线词典）。无中文字符 → 原样返回 translated=False。"""
    topic = (topic or "").strip()
    if not _HAN.search(topic):
        return {"topic_zh": topic, "topic_en": topic, "translated": False,
                "hits": [], "untranslated": []}

    mapping = load_dict()
    keys = sorted(mapping, key=len, reverse=True)  # 最长匹配优先
    hits = []

    def _repl(m):
        zh = m.group(0)
        en = mapping[zh]
        if (zh, en) not in hits:
            hits.append((zh, en))
        return en

    if keys:
        pattern = re.compile("|".join(re.escape(k) for k in keys))
        query = pattern.sub(_repl, topic)
    else:
        query = topic
    untranslated = sorted(set(_HAN.findall(query)))
    return {"topic_zh": topic, "topic_en": query, "translated": True,
            "hits": hits, "untranslated": untranslated}


if __name__ == "__main__":
    import sys
    for t in sys.argv[1:] or ["奥希替尼 间质性肺病", "肺癌 免疫治疗 不良反应",
                              "osimertinib interstitial lung disease"]:
        r = translate_topic(t)
        print("IN :", r["topic_zh"])
        print("OUT:", r["topic_en"], "| translated:", r["translated"])
        if r["hits"]:
            print("HITS:", r["hits"])
        if r["untranslated"]:
            print("UNTRANSLATED:", r["untranslated"])
        print("-" * 40)
