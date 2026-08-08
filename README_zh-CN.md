# 临床试验文献检索专家（ct-literature）

[🇨🇳 中文 (当前)](./README_zh-CN.md) | [🇺🇸 English](./README.md)

<div align="center">
<img src="assets/icon.svg" width="240" height="240" alt="ct-literature 图标"/>
</div>

> **`ct-` 技能库中的 B 档公开情报技能：检索某药物 / 疾病 / 方法已发表的学术文献，将多个公开文献源归一化为统一去重的证据库，并提取证据格局与 CSM（累积安全性监测）定性子集。**

> 💡 **默认无 key 也能跑，但免费 key 能大幅提额：** OpenAlex 自 2026-02-13 起强制要求 key；无 key 时处于 keyless 池（100 credits/天，标注 *not suitable for production*）。免费 key 可提到 100k/天。申请约 30 秒 —— 见 §4 及技能在检测不到 key 时自动打印的申请提示。

> 不需要命令，也不需要手册。你只要在对话里用**自然语言**说清想查什么：技能从 OpenAlex（主源）加可选的 Europe PMC / Semantic Scholar 取数，然后写出 Markdown + Excel 报告。B 档：计算完全本地，仅对外公开检索。**注意：你的主题词会发往下方公开文献 API —— 出站说明见 §4。**

---

## 适用人群

`ct-*` 临床试验技能家族专用于解决临床试验全生命周期的各类需求，主要面向三类人群：

- **各制药企业的临床试验从业者** —— 申办方、CRO，以及医学 / 统计 / 注册等角色；
- **在医疗机构中设计、管理临床试验项目，或参与临床试验研究实务的医护人员**；
- **希望系统学习临床试验知识的医学专业学生**。

## 数据源

| 源 | 密钥 | 角色 |
|---|---|---|
| OpenAlex | 推荐 key（免费 100k/天，技能 `.env` 自动加载）；无 key 限 100/天（2026-02-13 起） | **主源** — 覆盖广、含引用数 |
| Europe PMC | 无需 | 可选 `--with-europepmc` — MEDLINE/MeSH 生物医学精准 |
| Semantic Scholar | 无需（易 429） | 可选 `--with-semantic-scholar` — 引用排序；**无 key / 429 时自动跳过** |

## 1. 如何在对话里使用（核心）

ct-literature 是一个**对话式技能**：你只要把想查的内容告诉助手即可 —— 无需命令、无需记参数名。安装为 WorkBuddy 技能后，你在对话里通过 Skill 工具调用它即可，无需额外配置；但它只在你主动调用时激活。

下面给出 7 个由简到繁的真实对话示例，每个都含**「你这样说」**与**「助手会这样回（示意）」**，并说明报告如何产出。

### 示例 1 · 简单文献检索（直接作答）
**你这样说：**
检索奥希替尼在 NSCLC 的已发表文献，2018–2025。

**助手会这样回（示意）：**
正在路由到 OpenAlex（主源）。这是归一化后的证据库 —— 论文数量、高被引文献、年度趋势，外加一个 CSM 子集。报告已写入 `lit_report.md` / `lit_report.xlsx`。

**📌 无需 key** —— OpenAlex keyless 池足以覆盖小规模检索；技能直接取数并写报告。

### 示例 2 · 加安全性 / CSM 子集
**你这样说：**
同一主题，但聚焦不良事件 / 上市后安全性。

**助手会这样回（示意）：**
加上 `--safety` —— 报告现含一个定性 CSM 子集（已发表病例报告 / 药物警戒文章），与 `ct-safety` 的结构化 FAERS 信号分析分开标注。二者是明确不同的数据类型；文献补充而非替代 FAERS。

### 示例 3 · 更广覆盖（Europe PMC + Semantic Scholar）
**你这样说：**
也用 Europe PMC 拉 MEDLINE，并用 Semantic Scholar 做引用排序。

**助手会这样回（示意）：**
加上 `--with-europepmc`（MeSH 精准）与 `--with-semantic-scholar`（引用排序）。S2 在无 key 或 429 时自动跳过 —— OpenAlex + Europe PMC 仍正常产出。

### 示例 4 · 配置 OpenAlex key（自行配置）
**你这样说：**
大规模检索怎么突破 100/天的限额？

**助手会这样回（示意）：**
在 <https://openalex.org/settings/api> 申请免费 key（约 30 秒），然后自行配置即可——技能**绝不要求你把 key 粘进对话**。三种方式任选其一：(a) 在 `ct-literature/.env` 加一行 `OPENALEX_API_KEY=<key>`；(b) 设为环境变量 `OPENALEX_API_KEY`；(c) 命令行传 `--openalex-key <key>`。key 仅本地存储，只通过 HTTPS 发往官方 OpenAlex API。

### 示例 5 · 拿 Excel 交付物
**你这样说：**
能给我 Excel 文件，而不只是 Markdown 吗？

**助手会这样回（示意）：**
可以 —— `--run` 自动产出 `lit_report.xlsx`（学术绿主题，4 页：说明 → 概览 → 文献总表 → 安全性相关；`is_safety` 行高亮）。用 `--no-xlsx` 可跳过。

### 示例 6 · 复杂请求 → 弹出确认菜单
**你这样说：**
我想查一下糖尿病治疗相关的文献。

**助手会这样回（示意）：**
识别到主题 = 糖尿病，但类型 / 年份 / 来源尚待确认，于是弹出编号确认菜单（详见 `references/search_menu.md` §4.1–§4.3）：
📚 文献检索 — 准备就绪
已识别：主题：糖尿病 · 类型：全部 · 年份：未指定
待确认：1) 文献类型 2) 年份区间 3) 安全性偏置 4) 数据源
回复数字选择，或说"默认"采用推荐配置。

### 示例 7 · 模糊请求 → 追问澄清（grill-me 风格）
**你这样说：**
帮我找一下那个新药，治癌症的。

**助手会这样回（示意）：**
主题模糊，于是反向追问（最多 2 轮，之后回退默认 + 预览提示，见 search_menu.md §6）：
"具体是哪个药？例如奥希替尼、帕博利珠单抗，或某个靶点如 PD-1？"
你点名后，锁定主题并进入预览确认。

---

## 2. 你能做些什么 —— 场景索引

技能覆盖临床试验全生命周期的已发表证据检索。每行给出典型**场景**与可直接照抄的**「试试这样说」**。

### ① 已发表证据检索（OpenAlex，主源）
| 场景 | 试试这样说 |
|:---|:---|
| 某药 / 病 / 方法的证据 | "找奥希替尼在 NSCLC 的 system review" |
| 带年份过滤的近期文献 | "2020 年以来 CAR-T 在淋巴瘤的论文" |
| 带安全性角度的主题 | "药物 X 的上市后安全性文献" |

### ② 更广 / 更深覆盖（可选源）
| 场景 | 试试这样说 |
|:---|:---|
| MEDLINE / MeSH 生物医学精准 | "这个主题也搜一下 Europe PMC" |
| 按引用量排序 | "用 Semantic Scholar 按引用量排这些文献" |

### ③ 输出格式
| 场景 | 试试这样说 |
|:---|:---|
| Excel 交付物 | "把文献导出成 Excel 文件" |
| 仅 Markdown 报告 | "只给我 Markdown 报告，跳过 Excel" |

### ④ Key / 配置
| 场景 | 试试这样说 |
|:---|:---|
| 突破 OpenAlex 限额 | "怎么提高速率限制？" |
| 查看当前配置 | "技能现在识别到哪些 key？" |

> 底层兄弟技能各有自己的 README；普通用户只需用自然语言说想做的事 —— 技能会路由正确的数据源并写出报告。

---

## 3. 首次使用常见问题 FAQ

**Q：跑起来需要 key 吗？** A：不需要。OpenAlex keyless 池 = 100 credits/天（小规模检索够用）；免费 key 提到 100k/天。Europe PMC 与 Semantic Scholar 均无需 key。

**Q：我的查询发到哪里？** A：你的主题词与筛选条件会发往公开文献 API —— OpenAlex、Europe PMC、Semantic Scholar（仅你启用的源）。绝不发送任何保密或申办方数据。

**Q：和 `ct-safety` 有什么区别？** A：`ct-literature` = 已发表的*定性*证据（论文 / 综述 / 病例报告）；`ct-safety` = 结构化 FAERS 信号检测（PRR / ROR / IC）。二者是明确不同的数据类型 —— 文献补充而非替代 FAERS。

**Q：中文系统下输出是中文吗？** A：是。输出语言默认跟随系统（中文系统→中文，其他→英文），随时一句话强制切换（如"用中文回复" / "switch to English"）。

**Q：Semantic Scholar 老是失败 / 被跳过？** A：S2 的 key 需填表人工审核、非自动发放，申请后需等待，短期内通常无 key。未配置 key 时本源被**直接跳过**（不发起网络请求），而非尝试后降级。若需要引用排序，之后配置即可。

---

## 4. 安全与隐私

### 安全预览（本地计算）
- **本地运行**：归一化 / 报告 / Excel 渲染全部在本机完成 —— 除随技能发布的脚本外，不在任何远程服务器执行代码。
- **可溯源、不编造**：报告中每条事实性断言都带来源标注（每篇文献的 `sources` 列表）或 `⚠️ 官方核实` 标记；绝不用流畅措辞填补证据空白。
- 输出仅供参考；申报 / 决策前请对照官方原文核实。

### 出站与隐私（仅公开检索）
- **唯一出站路径 = 三个公开文献 API**：运行检索时，你的主题词与筛选条件会发往 **OpenAlex**（`api.openalex.org`）、**Europe PMC**（`ebi.ac.uk/europepmc`）、**Semantic Scholar**（`api.semanticscholar.org`）—— 仅你启用的源。**无其他出站路径，也绝不发送任何保密 / 申办方数据**。
- **密钥留在你本机**：若配置了 OpenAlex / S2 key，从你本地的 `ct-literature/.env` 读取，**绝不随包分发** —— `.env` 已被 `.gitignore`（GitHub）/ `.clawhubignore`（ClawHub）排除，SkillHub 窄白名单也不含它；随包发布的只有 `.env.example` 模板。重新安装后需你自己再次填入 key。
- **不自动代申请**：技能不会自动搬运或代申请 key；检测不到 key 时仅打印申请提示并以 keyless 模式运行。

---

## 5. 进阶参考（开发者）

CLI 助手、运行要求、架构树与统一工作模式 schema 已移到此处，普通用户无需阅读。规范级内容与版本历史见 [`SKILL.md`](SKILL.md) 与 [`CHANGELOG.md`](CHANGELOG.md)。

### 运行时与要求
| 项目 | 要求 |
|---|---|
| 运行时 | Python 3.11+（CPython）。流水线仅用标准库 + `requests` 发 HTTP。 |
| Key（可选） | OpenAlex 免费 key（规模化推荐）；Semantic Scholar key 可选（放宽 ~1 req/s 限制）。均经 `.env` / 环境变量 / `--openalex-key`。 |
| 兄弟技能 | `ct-registry`（试验注册）、`ct-safety`（FAERS）、`ct-pipeline`（情报简报）—— ct-literature 既供给主题也被供给；均从 GitHub 安装。 |

### 架构
```
ct-literature/
├── SKILL.md              # agent-facing 规范（英文正文）
├── scripts/
│   ├── ct_literature.py  # 编排入口：fetch → normalize → report
│   ├── fetch_openalex.py # 主源
│   ├── fetch_europepmc.py# 可选 MEDLINE/MeSH
│   ├── fetch_semantic_scholar.py # 可选引用排序（低优先级、可跳过）
│   ├── normalize.py      # 多源合并 + 去重
│   ├── report.py         # Markdown 报告
│   ├── export_xlsx.py    # Excel 交付物（ct-base excel_style）
│   ├── export_html.py    # 可选 HTML
│   ├── http_utils.py     # 共享重试 / 请求头 / key 加载
│   └── i18n.py           # 双语唯一真源
├── references/           # SOP、key 配置、检索菜单、多库方法
└── assets/icon.svg       # B 档 logo
```

### CLI 示例（开发者）
```bash
# 主源（OpenAlex；无 key）
python scripts/ct_literature.py --topic "osimertinib" \
    --review-type systematic-review --year-from 2018 --safety --run --out-dir ./out

# 叠加 Europe PMC（MeSH）+ Semantic Scholar（引用排序）
python scripts/ct_literature.py --topic "osimertinib" \
    --with-europepmc --with-semantic-scholar --run --out-dir ./out

# 推荐（开箱即用）：把 key 放进技能目录 .env，之后无需任何额外参数
cp .env.example .env          # 编辑 .env 填入 OPENALEX_API_KEY=你的key
python scripts/ct_literature.py --topic "osimertinib" --safety --run --out-dir ./out
```

### 统一工作模式（输出 schema）
```
{
  source, id, title, authors, year, publication_date, publication, journal_iso,
  type, study_type, cited_by_count, url, open_access_url,
  pmid, pmcid, doi,
  abstract_snippet,                           # 完整文本，不截断
  mesh, concepts, keywords, funders,
  language, is_retracted, is_safety,
  volume, issue, page,
  affiliations,                               # 仅 Europe PMC
  sources                                     # 贡献来源列表
}
```

---

**版本**：v0.5.3 | **许可证**：MIT | **作者**：medstatstar, phoe-zip

如有功能改进建议、Bug 报告或其他反馈，欢迎直接联系作者：medstatstar@gmail.com（张文彤 / Wintone Zhang）。

---

## 保密声明

> CT 全系列技能由 16 余个技能构成，完整覆盖新药临床试验（Clinical Trial）全流程的各方面需求。然而，由于大量技能涉及药企需要严格保密的临床试验数据、内部资讯等敏感内容，仅有不涉密的 A、B 级别技能会在 GitHub 上公开发布；涉及保密的 C、D 级别技能（如 ct-analysis 等）均设定为企业内部使用。

> 若您对这些涉密技能确有实际需求，欢迎与作者联系，定制并安装相关技能。

> 📧 联系方式：medstatstar@gmail.com，张文彤（Wintone Zhang）
