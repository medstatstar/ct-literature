# 临床试验文献检索专家（ct-literature）

[🇨🇳 中文 (当前)](./README_zh-CN.md) | [🇺🇸 English](./README.md)

<div align="center">
<img src="assets/icon.svg" width="240" height="240" alt="ct-literature 图标"/>
</div>

> **`ct-` 技能库中的 A 档公开情报技能（输入非涉密，ct-base §11）：检索某药物 / 疾病 / 方法已发表的学术文献，将多个公开文献源归一化为统一去重的证据库，并提取证据格局与 CSM（累积安全性监测）定性子集。**

> 不需要命令，也不需要手册。你只要在对话里用**自然语言**说清想查什么：技能从 **OpenAlex（主源）+ Europe PMC（默认开启）+ bioRxiv/medRxiv（默认开启）** 取数，然后写出自包含的 **HTML + Excel** 报告。（Semantic Scholar 与 arXiv 是经 flag 显式开启的可选源，不纳入默认检索组合）。**注意：你的主题词会发往下方公开文献 API —— 出站说明见 [安全与隐私 · 出站](#出站与隐私)。** 技能**仅在你明确发起文献检索时激活**，不会在不相关对话中自行联网检索。

> 💡 **默认无 key 也能跑，但免费 key 能大幅提额：** OpenAlex 自 2026-02-13 起强制要求 key；无 key 时处于 keyless 池（100 credits/天，标注 *not suitable for production*）。免费 key 可提到 100k/天。申请约 30 秒 —— 配置方法见下方 [首次使用 FAQ](#首次使用常见问题-faq) 与技能在检测不到 key 时自动打印的申请提示。

## 目录
- [适用人群](#适用人群)
- [如何在对话里使用](#如何在对话里使用)
- [数据源](#数据源)
- [为什么可以信任输出 —— 反幻觉设计](#为什么可以信任输出--反幻觉设计)
- [你能做些什么 —— 场景索引](#你能做些什么--场景索引)
- [首次使用常见问题 FAQ](#首次使用常见问题-faq)
- [安全与隐私](#安全与隐私)
- [进阶参考（开发者）](#进阶参考开发者)

---

## 适用人群

`ct-*` 临床试验技能家族专用于解决临床试验全生命周期的各类需求，主要面向三类人群：

- **各制药企业的临床试验从业者** —— 申办方、CRO，以及医学 / 统计 / 注册等角色；
- **在医疗机构中设计、管理临床试验项目，或参与临床试验研究实务的医护人员**；
- **希望系统学习临床试验知识的医学专业学生**。

## 如何在对话里使用

ct-literature 是一个**对话式技能**：你只要把想查的内容告诉助手即可 —— 无需命令、无需记参数名。安装为 WorkBuddy 技能后，你在对话里通过 Skill 工具调用它即可，无需额外配置；但它只在你主动调用时激活。

下面给出 7 个由简到繁的真实对话示例，每个都含**「你这样说」**与**「助手会这样回」**，并说明报告如何产出。助手回复是真实交互的**关键节选**（压缩了进度行与细节）；需要你拍板时，技能会把选项**列在界面上供点击确认**，或要求你说"默认/直接执行"。主交付物是自包含的 **`lit_report.html`**（离线、可打印）与 **`lit_report.xlsx`**。默认工作簿含 **3 个数据页：概览 → 文献总表 → 证据溯源**（另含一张说明封面）。**安全性相关**页为显式可选 —— 仅当你加 `--safety`（CSM 定性子集）时才出现，因为安全性 / CSM 文献子集属于安全性导向的诉求，并非每次普通文献检索的默认交付。

### 示例 1 · 简单文献检索（含预览确认）
**你这样说：**
检索奥希替尼在 NSCLC 的已发表文献，2018–2025，聚焦不良事件 / 上市后安全性。

**助手会这样回（节选）：**
你的请求已识别为**简单检索**（主题 + 年份 + 安全性角度都明确）→ 直接给出预览让你确认：
| 参数 | 值 |
|---|---|
| 主题 | osimertinib + NSCLC（同义词族 AZD9291 / Tagrisso / 奥希替尼 自动并入） |
| 年份 | 2018–2025 · 安全性聚焦 ✅ |
| 数据源 | OpenAlex + Europe PMC + 预印本（默认三源）· 每源 50 篇 |
| 引文验证 | all（防幻觉，默认开） |

确认执行 → 关键字清单过目 → 开始检索（约 30–60 秒）：
> 检索完成：**103 篇**去重后唯一文献（3 源）；其中安全性相关 **81 篇**。引文验证 100/103 通过。报告已写入 `lit_report.html` 与 `lit_report.xlsx`（文献总表 + 安全性相关页）。

**📌 无需 key** —— OpenAlex keyless 池足以覆盖小规模检索；技能直接取数并写报告。

### 示例 2 · 只看证据汇总层（系统综述 / Meta 分析）
**你这样说：**
同一主题，只保留系统综述和 Meta 分析 —— 我想看证据汇总结论，不看单篇试验。

**助手会这样回（节选）：**
限定 `--review-type systematic-review/meta-analysis` 重新检索。**本主题命中 3 篇系统综述**（跨源去重后），已单独列出；每篇保留完整摘要与引文验证。若某类型零命中，会明确告知"无此类型文献"而非用相近类型凑数。

**📌 安全性子集与 FAERS 是两回事**：`--safety`（CSM 定性子集 = 已发表病例报告 / 药物警戒文献）与 `ct-safety`（结构化 FAERS 信号检测 PRR / ROR / IC）是**明确不同的数据类型** —— 文献补充而非替代 FAERS。

### 示例 3 · 更广覆盖（Europe PMC + Semantic Scholar）
**你这样说：**
也用 Europe PMC 拉 MEDLINE，并用 Semantic Scholar 做引用排序。

**助手会这样回（节选）：**
加上 `--with-europepmc`（MeSH 精准）与 `--with-semantic-scholar`（引用排序）。S2 在无 key 或 429 时自动跳过 —— OpenAlex + Europe PMC 仍正常产出。

### 示例 4 · 配置 OpenAlex key（自行配置）
**你这样说：**
大规模检索怎么突破 100/天的限额？

**助手会这样回（节选）：**
在 <https://openalex.org/settings/api> 申请免费 key（约 30 秒）。然后自行配置：(a) 在 `ct-literature/.env` 加一行 `OPENALEX_API_KEY=<key>`，(b) 设为环境变量 `OPENALEX_API_KEY`，(c) 命令行传 `--openalex-key <key>`。**注意**：聊天消息可能被平台记录留存——如需最高隐秘性，请走自配置 (a)–(c)。如你愿意，也可以让助手帮你把 key 写进 `ct-literature/.env`（key 仅本地存储、绝不回显、绝不写日志，只经 HTTPS 发往官方 OpenAlex API）。

**配置 key 后检索会快很多、且 key 不外发**：有 key 时 OpenAlex 进入 keyed pool（约 10 万 credits/天、不易 429），OpenAlex / Semantic Scholar 两个源改为**本机本地直连检索，不经过云端**——你的 key 只在本机内存中用于请求官方 API，绝不上传任何第三方服务。仅未配置 key 的用户走云端通道（OpenAlex 匿名池，Semantic Scholar 自动跳过）。

### 示例 5 · 复杂请求 → 参数确认（菜单/卡片式）
**你这样说：**
我想查一下糖尿病治疗相关的文献。

**助手会这样回（节选）：**
Triage → **Complex**（主题 = 糖尿病已明确，但**文献类型 / 年份 / 来源**等关键参数缺失）→ 技能不替你拍板，先列出现有识别并请你在界面上确认两件事：

> 已识别：主题 `糖尿病 treatment` ｜ 待确认：① **文献类型**（全部类型 [推荐] / 仅系统综述+Meta / 系统综述+RCT…）② **是否现在执行**（✅ 直接执行 / ✏️ 修改参数 / ❌ 取消）
> 拿不准差异？说「详细解释这些选择之间的差异」——会先讲清各类型的临床与统计含义再让你决定。

参数确认后，还有两道把关才真正执行：**① 关键字确认门** —— 把扩展词清单（如 `diabetes mellitus`、`diabetes treatment` 的同义/中英词族）列给你过目；**② 预览确认** —— 一张与示例 1 相同的参数表，你点头后才联网取数。

**📌 说明：** 简单请求（topic + ≥2 参数明确）**跳过**确认菜单，直接预览（见示例 1）；模糊请求走 grill-me 追问（见示例 6）。

### 示例 6 · 模糊请求 → 有界追问澄清（grill-me 风格）
**你这样说：**
帮我找一下那个新药，治癌症的。

**助手会这样回（节选）：**
Triage → **Vague**（"那个新药"无法定位）→ 反向追问，**最多 2 轮**，每轮给出推荐默认，理不清就回退默认 + 预览提示：

> **第 1 轮：** "想不起药名没关系——是**哪一类**？第三代 EGFR-TKI（如奥希替尼）、免疫检查点抑制剂（如帕博利珠单抗），还是某个靶点（PD-1 / EGFR）？或把商品名 / 适应症发我，我来反查。"
> 你：奥希替尼，治肺癌那个。
> **第 2 轮（收敛范围）：** "锁定奥希替尼。癌种要限定 **NSCLC** 吗？（默认限定）年份与安全性角度有偏好吗？（无 → 近 5 年全类型）"

两轮后技能给出**需求画像 + 推荐参数**让你确认："主题 osimertinib + NSCLC ｜ 近 5 年 ｜ 全类型 ｜ 默认三源"——确认即转预览执行；若仍说不清则按默认配置执行并在预览里提醒。

### 示例 7 · 按需批量下载合法开放获取 PDF
**你这样说：**
把报告里最新发表的 40 篇的 PDF 都下载下来，记录一下用时。

**助手会这样回（节选）：**
先从 103 篇合并库中**按发表时间倒序取最新 40 篇**，然后开始批量下载 —— 下载**开始前**会先给你节奏预期：

> 开始批量下载 40 篇文献的 PDF：**每篇约需 10–20 秒**（视网络与限流而定），请耐心等待完成，无需任何操作。

下载全程自动路由：**OA / 预印本本地直连优先**（Frontiers、MDPI、PMC 作者手稿等），本地失败且存在 OA/预印本信号时才走云端补充链解码；付费墙且无合法副本的不硬来。完成后如实汇报：

> 下载完成: **36/40** 篇成功，用时 **853 秒（14.2 分钟）**。PDF 已保存至 `pdfs_latest40/`，**Excel 报告已更新「PDF 本地路径」列**（36 条绝对路径 + 3 条"失败"标注）。
> ⚠️ 4 篇未下载均为付费墙（NEJM / JCO / BMJ），需机构订阅或联系作者 —— 技能不绕过付费墙。

**⏱ 节奏**：每篇约 10–20 秒（含限流退避与云端解析），40 篇整批约 10–15 分钟 —— 属正常等待，不是卡死；单篇直连（Frontiers 类）通常 3–5 秒即完成。

## 数据源

| 源 | 密钥 | 角色 |
|---|---|---|
| OpenAlex | 推荐 key（免费 100k/天，技能 `.env` 自动加载）；无 key 限 100/天（2026-02-13 起） | **主源** — 覆盖广、含引用数 |
| Europe PMC | 无需 | **默认开启**（`--no-with-europepmc` 关闭） — MEDLINE/MeSH 生物医学精准 |
| Semantic Scholar | 推荐 key（需填表人工审核） | **仅显式可选** `--with-semantic-scholar` — 引用排序；**不属默认数据源**，须显式开启且配置 key 才会检索 |
| bioRxiv | 无需（经 Europe PMC PPR） | **默认开启**（`--no-with-biorxiv` 关闭） — 生物医学预印本 |
| medRxiv | 无需（经 Europe PMC PPR） | **默认开启**（`--no-with-medrxiv` 关闭） — 医学/临床预印本 |
| arXiv | 无需 | 可选 `--with-arxiv` — 物理/CS/ML 方法学广度 |
| PROSPERO | 需 token（认证头未公开） | 可选 `--with-prospero` — 系统评价注册库 / 方案发现；**保留接口**，未提供可用 token+header 前自动降级为空跳过 |

### 各来源如何配合

默认组合 —— **OpenAlex（主源）+ Europe PMC（默认开启）+ bioRxiv/medRxiv（默认开启）** —— 其实已经覆盖到了几乎整个已发表文献版图：通过这三个入口，你就能拿到 PubMed / PMC、bioRxiv / medRxiv / arXiv 预印本，以及 Crossref、Semantic Scholar、CORE、Unpaywall 的记录（其中 Semantic Scholar 的记录经由 OpenAlex 的关联即已带入，无需单独查 S2）。其它来源做成可选，不是因为这对组合不完整，而是出于两个现实考量：

- **预印本时效** —— **bioRxiv / medRxiv 现已默认开启**，直接从源头拉取预印本，不必等它慢慢同步进 Europe PMC 的 PPR 供稿。
- **抗限流** —— 若 Europe PMC 偶尔被限流（HTTP 429），独立的预印本入口让你可以绕开单一瓶颈、继续拓宽覆盖。（Semantic Scholar 是另一项需 `--with-semantic-scholar` + key 的显式可选源，不属默认检索组合。）

## 为什么可以信任输出 —— 反幻觉设计

由 LLM 驱动的文献工具，最容易翻车的一点就是**编造根本不存在的论文** —— 伪造的 DOI、写错的 PMID、看似合理实则虚构的引文。ct-literature 从设计上就让这种事不可能发生：四道独立防线 + 两项运行保障。

1. **每条引文都回源核验（P0，默认开启）。** 一篇文献进入报告之前，它的标识符会先去真实的文献 API 跑一遍：DOI → `doi.org`（必须返回 HTTP 2xx）、PMID → Europe PMC 的 `EXT_ID`、OpenAlex id → `api.openalex.org/works/<id>`。每篇文献都会被打上 `citation_verified` 标签和状态：`verified` / `bot_blocked` / `unresolved` / `no_identifier` / `suspicious`。**格式错误的 DOI 会被标为 `suspicious`** —— 等于在「疑似幻觉标识符」进入报告之前就把它拦下来。可用 `--verify {all|top|none}` 调节范围；默认 `all` 会对每篇都核验。
   - **`bot_blocked`**：部分出版社（NEJM、JAMA、Wiley、MDPI 等）对程序化访问回 **403**，但 DOI 本身是真实的。技能把这种情况单独标出 —— 它**不是**断链，且文献仍记为 `verified=True`。
2. **标题/作者一致性深度校验（v0.6.11）。** 标识符一旦解析到存活资源，技能会再去拉该资源的权威元数据（标题 + 第一作者姓氏）：DOI 走 **Crossref**（即便出版社拦 `doi.org` 它也 bot-friendly）、PMID 走 **Europe PMC**、OpenAlex id 走 **OpenAlex**，并与你手上的这篇文献比对。解析到**另一篇**文献则标为 **`mismatch`**（而非 `verified`）；`bot_blocked` 的 DOI 若 Crossref 元数据吻合则**升级为 `verified`**。于是即便一个「幻觉出的但真实存在的 DOI」也能被抓出来。元数据抓取失败会优雅降级为"verified，一致性未核验"——绝不因瞬时 API 错误捏造 mismatch。可用 `--no-consistency` 关闭该层。
3. **完整溯源，而非被摘要掉。** 每一篇归一化后的文献都保留 `sources` 列表（来自哪个 API），`evidence_log.json` 还会存一条不可变风格的审计轨迹：查询 → 来源 → 命中数 → 取数时间 → 核验率。任何一条结论都能回溯到产出它的那次具体 API 调用。
4. **报告绝不用流畅文字补窟窿。** 报告里每一句事实都带来源标注，或明确的 `⚠️ 需官方核实` 标记。技能**不会**为了填满空缺而编出看似合理的证据 —— 某个来源失败了、或某篇未核验，它会明说，而不是藏着。

两项运行保障进一步加固这一点：**安全预览（Safe Preview）** 把归一化 / 报告生成都留在你本机（不执行任何远端代码）；**源感知跳过** 避免冗余重复核验，同时仍按「来源可信」信任每个标识符（OpenAlex 返回的论文本来就带真实 OpenAlex id，所以不再回去查一遍）。以上均遵循 ct-base 反幻觉规范（§17.1）。

**结论：** 本技能给你的参考文献是真实存在、可追溯、可核验的 —— 放进幻灯片、方案或 CSR 附录都稳妥，但任何监管提交前仍请对照官方来源复核（见 [首次使用 FAQ](#首次使用常见问题-faq)）。

---

## 你能做些什么 —— 场景索引

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

### ③ 输出格式与导出
| 场景 | 试试这样说 |
|:---|:---|
| Excel 交付物 | "把文献导出成 Excel 文件" |
| 仅自包含 HTML 报告 | "只给我 HTML 报告，跳过 Excel" |
| 导入 **Zotero**（文献管理插件） | "导出 Zotero 格式" — 得到 `zotero.ris` / `zotero.csv`，用 Zotero 桌面版或浏览器插件导入 |
| 用 **Obsidian** 做文献图谱 | "导出到 Obsidian" — 每篇文献一篇 Markdown 笔记 + `Literature MOC.md` 索引，把文件夹作为 vault 打开即可图谱化浏览 |
| **批量下载 OA PDF**（v1.0.0） | "下载最新 40 篇的 PDF 并记录用时" — 下载到本地 `pdfs*/`（DOI 命名），Excel 同步回填「PDF 本地路径」列，失败项如实标注 |

### ④ 证据验证与溯源（P0，默认开启）
| 场景 | 试试这样说 |
|:---|:---|
| 验证每条 DOI/PMID 真实存在（反幻觉） | "报告前先核实引文是不是真的" |
| 进一步确认标题/作者与论文吻合（v0.6.11） | "确保这个 DOI 指向的确实是这篇论文" |
| 追溯每条命中的来源 | "给我看证据溯源 / 来源日志" |
| 只验证 top-N 条（大结果集更快） | "这次只验证前 15 条引文" |
| 跳过验证（更快、仅预览） | "这次先不验证引文" |

### ⑤ Key / 配置
| 场景 | 试试这样说 |
|:---|:---|
| 突破 OpenAlex 限额 | "怎么提高速率限制？" |
| 查看当前配置 | "技能现在识别到哪些 key？" |

> 底层兄弟技能各有自己的 README；普通用户只需用自然语言说想做的事 —— 技能会路由正确的数据源并写出报告。

---

## 首次使用常见问题 FAQ

**Q：跑起来需要 key 吗？** A：不需要。OpenAlex keyless 池 = 100 credits/天（小规模检索够用）；免费 key 提到 100k/天。Europe PMC 与 Semantic Scholar 均无需 key。

**Q：我的查询发到哪里？** A：你的主题词与筛选条件会发往公开文献 API —— OpenAlex、Europe PMC、Semantic Scholar（仅你启用的源）。绝不发送任何保密或申办方数据。

**Q：和 `ct-safety` 有什么区别？** A：`ct-literature` = 已发表的*定性*证据（论文 / 综述 / 病例报告）；`ct-safety` = 结构化 FAERS 信号检测（PRR / ROR / IC）。二者是明确不同的数据类型 —— 文献补充而非替代 FAERS。

**Q：中文系统下输出是中文吗？** A：是。**对话答案与报告**（HTML / Excel）的语言默认跟随系统（中文系统→中文，其他→英文），也可随时一句话强制切换（如"用中文回复" / "switch to English"）。**控制台进度日志**（下载/取数的过程提示）为中文辅助输出，属运行噪音，不影响答案与交付物的语言。

**Q：Semantic Scholar 老是失败 / 被跳过？** A：S2 的 key 需填表人工审核、非自动发放，申请后需等待，短期内通常无 key。未配置 key 时本源被**直接跳过**（不发起网络请求），而非尝试后降级。若需要引用排序，之后配置即可。

**Q：一次检索要跑多久？有限额吗？** A：
- **典型耗时**：各启用源**相互并行**（每个源一个并发任务），但**同一源内部按页链式串行**——源内请求逐个依次发出，因为源内并行翻页会提高限流 / 封号风险（如 OpenAlex 无 key 池）。Europe PMC ~1秒/页，OpenAlex ~2秒/页，所以墙钟时间是*最慢的那个源*，而非各源之和。拉取约 50 篇文献的 3 源合并通常 **10–30 秒**完成（开启全量引文验证时再多 ~1–4 分钟——见运行前的耗时预估）。加预印本（bioRxiv/medRxiv/arXiv）再多数秒。
- **结果上限**：默认 `max_results` 为**每源 50 篇**；无硬性上限（调大允许），但耗时与 API 用量线性增长。**2026-08-14 实测**（双源、"奥希替尼 间质性肺病"）：`--max 100` → 抓取+合并**约 20 秒**、全量验证**约 78 秒**（跨源去重后约 0.64 秒/篇；双源去重后保留约 **62%**）。**按 5 分钟总耗时建议：双源每源 ≤300、三源每源 ≤250**（两种配置合并去重后均约 370–380 篇；去重是自动的，3×250 并不等于报告里 750 篇）。超出后总耗时近似线性增长——大批量需求请配置 OpenAlex key 并改用 `--verify top 15`，而非一味调大 `max_results`。
- **速率限制：**
  - **OpenAlex（无 key）：** 100 credits/天（2026-02-13 起）。一次多页检索可用 5–20 credits。免费 key 可提到 **100k/天**。
  - **Europe PMC：** 无严格 key 限制，但请合理控制请求频率（不要高频循环调用）。
  - **Semantic Scholar（无 key）：** 极易触发 HTTP 429；未配置 key 时技能会直接跳过本源。
- **建议**：先用默认源（OpenAlex + Europe PMC）+ 适中 `max_results` 起步；仅在确实需要更广覆盖时再加装额外源。

**Q：为什么文献抓取速度不能更快一些？** A：因为技能**只使用各网站官方提供的公开抓取方式**（其公开 API / 接口），**不违反任何网站的规定**——按源、按页依次礼貌抓取，因此无法做到"短时间内大批量爬取数据"那种激进爬虫的效果。具体来说：(1) **不同源之间已经并行**（每个源一个并发任务）——再增加跨源并行度也不会更快。(2) **同一源内部必须链式串行**——公开文献 API（OpenAlex 无 key 池、Europe PMC 礼貌池）会对并发请求过多的客户端限流甚至封号；串行翻页正是为了不触发风控。(3) 如果某次运行觉得慢，通常瓶颈是**全量引文验证**（默认开启，每篇 1 次或多次 HTTP 查询）——改用 `--verify top 15` 或 `--verify none` 可省约 1–4 分钟。(4) 保持 `max_results` 适中——耗时与 API 用量随它线性增长。批量抓取 PDF 是另一项每篇数秒的操作（每次请求都要走重定向链）。

**Q：支持中文检索吗？** A：部分支持——技能会用**内置离线词典**（约 900 条：医学术语 + 药物 INN 名 + 商品名如 泰瑞沙→Tagrisso/osimertinib + MeSH 同义词；无需联网）把中文检索词自动翻译成英文后再查询各 API，报告头部会显示「原文 → 英文翻译」。等价名称会自动做布尔 OR 扩展以提升召回（如 `osimertinib OR Tagrisso`、`lung cancer OR pulmonary neoplasm`）。词典未收录的词会原样保留（召回可能受影响）并提示哪些未识别——你也可以**自行扩充词典**：在 `references/user_terms.json` 加条目（格式同 term_map：`{中文: "英文"}`，值可为同义词列表；该文件被 gitignore，你的扩充不会随发布公开）。为获得最佳召回，建议使用英文检索词——尤其是罕见病或新化合物。

**Q：为什么不支持检索知网等国内文献库？** A：刻意不支持，三个原因。（1）**价值有限**——本技能面向公开可检索的国际文献证据库（OpenAlex / Europe PMC 等），国内文献库的增量覆盖很小，且大量内容与国际库重叠或已被国际库收录。（2）**没有合规通道**——知网等国内数据库**不向个人提供公开 API**（仅对签约付费单位开放），同时对网络爬虫严厉封禁、甚至起诉；自动检索既没有合法的接口，也有法律风险，违背本技能"只用官方公开方式、不违反网站规定"的原则。（3）**不划算**——为这点增量覆盖承担合规与法律风险，不值得。需要某篇中文文献时，请在知网自行检索并导出题录（RIS / BibTeX）留档即可。

**Q：能下载全文 PDF 吗？** A：可以，但**仅限开放获取（OA）文献**，分两种方式。（1）Excel 与 HTML 报告始终包含**「开放获取链接」**列——当论文有免费 OA 副本时直接给出链接（通常覆盖 60–80% 的近期文献），**非 OA 的付费墙论文显示「—」，不提供支持**。（2）v1.0.0 起可让技能把 OA 文献**批量下载到本地**。合规边界先说清楚：
- **只协助 OA 下载，非 OA 不提供支持**：技能只从合法 OA 渠道取数（出版社 OA 直链、Europe PMC、PMC 作者手稿、开放预印本），**技术上不做任何违法操作**——不破解、不绕过、不触碰任何付费墙；付费墙论文（NEJM / JCO / BMJ 等）如实标注"失败"，请走机构订阅 / 文献传递 / 联系作者获取。
- **仅供个人使用，请勿用于商业用途**：本功能是为方便个人获取 OA 副本而设；请勿将下载内容用于商业用途。
- **OA 直下失败 → 尽力找预印本替代**：正文的 OA 直链拉不到时，会自动检索更早的预印本版本或作者手稿（bioRxiv / medRxiv / PMC）作为替代；仍无可用副本才标注失败。
- **善用免费资源、控制请求节奏（防封 IP）**：OA 供应商普遍拦截程序化高频下载——为避免法律纠纷，本技能**严格控制相邻两次下载请求的间隔在 5 秒以上**、不触及服务器压力线；同时也请你在批量请求时注意控制频次，**不要过量使用免费资源**以免 IP 被封。技能内置跨域并发限速与同域节流，**单批超过 50 篇会直接拒绝**，请分批（指定前 N 篇 / 单源）请求。

体验细节：下载开始前会先告知节奏（每篇约 **10–20 秒**，40 篇整批约 10–15 分钟）；完成后逐篇落盘到 `pdfs*/`（DOI 命名）并汇报用时（"N/M 篇成功，用时 X 秒"），**Excel 报告同步更新「PDF 本地路径」列**（成功项为绝对路径、失败项标"失败"）。无 key 纯自动渠道真实成功率约 **70–90%**（受 OA 覆盖率与出版商拦截影响）。如何请求：直接说"下载全部 OA PDF"、"下载最新 40 篇并记录用时"，或给具体 DOI/PMID 列表。

**Q: 发现结果有误怎么办？怎么上报？**
A: 本技能遵循 ct-base §20.3 错误报告流程。若您怀疑结果有误（或引擎报错），直接说 **"上报问题" / "report a bug" / "提交错误报告"**。技能在检测到疑似缺陷时（如引擎报错、重试仍失败）也会**主动询问**是否上报——**每会话最多 1 次**，您可随时拒绝。无论哪种方式，助手都会：
1. **生成一份脱敏报告**（11 键白名单：skill / skill_version / test / error_type / error_code / engine_status / description / locale / query_origin / session_hash / attempts——**不含您的原始输入值或个人数据**，仅 `description` 字段由您把关披露，如所用算法/函数、错误消息原文）；
2. **展示报告全文供您检视**——可补充问题描述或更正任何内容后再确认；
3. **经您明确确认后发送**——本会话有 coze 调用则发往统一端点 `https://ct-bugreport.coze.site/run`；纯本地则保存脱敏报告 + 提示邮件联系作者（数据不出域）；
4. **收到回执**——包括您此前从同一来源提交的报告是否已被修复（含修复说明）或仍在处理中。

整个过程您完全可控：报告在**发送前**先展示给您，未经您明确说「发送」绝不传输任何内容。

---

## 安全与隐私

### 安全预览（本地计算）
- **本地运行**：归一化 / 报告 / Excel 渲染全部在本机完成 —— 除随技能发布的脚本外，不在任何远程服务器执行代码。
- **可溯源、不编造**：报告中每条事实性断言都带来源标注（每篇文献的 `sources` 列表）或 `⚠️ 官方核实` 标记；绝不用流畅措辞填补证据空白。
- 输出仅供参考；申报 / 决策前请对照官方原文核实。

### 出站与隐私
- **文献检索（仅公开 API）**：主题词与筛选发往 **OpenAlex** / **Europe PMC** / **Semantic Scholar**（仅你启用的源），引文验证时额外访问 **doi.org** 与 **Crossref**；绝不发送保密 / 申办方数据。
- **Bug 报告（可选，需你确认）**：`adapters/bug_report.py` 仅在**两阶段确认后**才向 `https://ct-bugreport.coze.site/run` 发送 **11 键脱敏信封**（skill / version / error_type / description 等，不含原始数据与受试者信息）；无法联网时回退为本地文件。
- **密钥留在本机**：key 从本地 `ct-literature/.env` 读取，绝不随包分发（仅 `.env.example` 随包）。OpenAlex 免费 key 请自行到 <https://openalex.org/settings/api> 申请，并按下方 [首次使用 FAQ](#首次使用常见问题-faq) 自行配置（`.env` / 环境变量 / `--openalex-key`）；切勿把 `.env` 提交进仓库。（可选、不推荐：可贴出 key 让助手在本地代写——仅存于本机、绝不回显或写日志；更推荐自行配置。）

---

## 进阶参考（开发者）

CLI 助手、运行要求、架构树与统一工作模式 schema 已移到此处，普通用户无需阅读。规范级内容与版本历史见 [`SKILL.md`](SKILL.md) 与 [`CHANGELOG.md`](CHANGELOG.md)。

### 运行时与要求
| 项目 | 要求 |
|---|---|
| 运行时 | Python 3.11+（CPython）。流水线**仅用 Python 标准库**（`urllib`）发 HTTP —— **无需任何第三方依赖**。 |
| Key（可选） | OpenAlex 免费 key（规模化推荐）；Semantic Scholar key 可选（放宽 ~1 req/s 限制）。均经 `.env` / 环境变量 / `--openalex-key`。 |
| 兄弟技能 | `ct-registry`（试验注册）、`ct-safety`（FAERS）、`ct-pipeline`（情报简报）—— ct-literature 既供给主题也被供给；均从 GitHub 安装。 |

### 可选工具 · 英文→中文摘要术语标注（`abstract_translator.py`）

一个独立的轻量 CLI：对英文文本命中词典的医学术语做**中文标注**（`术语级替换`，非全文翻译——未命中词保留英文）。它**不属于检索流水线**，按需对文本或文件运行：

```bash
# 标注一段文本
python scripts/abstract_translator.py --text "Osimertinib is a third-generation EGFR-TKI used in NSCLC."
# 标注文件（如摘要），输出 ASCII 或 JSON
python scripts/abstract_translator.py --file abstract.txt --format ascii
python scripts/abstract_translator.py --file abstract.txt --format json --output out.json
```

输出展示原文与标注版（如 `randomized controlled trial` → 【随机对照试验】、`NSCLC` → 【非小细胞肺癌】、`overall survival` → 【总生存期】）。词典为内置离线英→中医学术语表（约 130 条：研究类型 / 试验设计 / 统计术语）+ 共享 `term_map.json` 的英文条目，无网络调用。需要通顺整句翻译时，请改用通用翻译服务。


### 架构
```
ct-literature/
├── SKILL.md                 # agent-facing 规范（英文正文）
├── CHANGELOG.md             # 版本历史
├── adapters/                # 每个公开 API 一个抓取器 + 验证器
│   ├── fetch_openalex.py    # 主源
│   ├── fetch_europepmc.py   # MEDLINE/MeSH（默认开启）
│   ├── fetch_semantic_scholar.py  # 可选引用排序（可跳过）
│   ├── fetch_preprints.py   # bioRxiv / medRxiv
│   ├── fetch_arxiv.py       # arXiv
│   ├── fetch_prospero.py    # PROSPERO（保留接口，未设 token 前空跳过）
│   ├── http_utils.py        # 共享重试 / 请求头 / key 加载
│   └── verify_citations.py  # P0 引文验证 + 标题/作者一致性
├── scripts/
│   ├── ct_literature.py     # 编排入口：fetch → normalize → verify → report/export
│   ├── normalize.py         # 多源合并 + 去重
│   ├── score_relevance.py   # 相关性打分
│   ├── screen_prisma.py     # 确定性 PRISMA 标题/摘要筛选
│   ├── export_xlsx.py       # Excel 交付物（ct-base excel_style）
│   ├── export_html.py       # 自包含 HTML 报告
│   ├── format_citations.py  # APA/Nature/Vancouver/IEEE/GB7714 + BibTeX/RIS
│   ├── evidence_log.py      # 溯源审计轨迹（evidence_log.json/.md）
│   ├── obsidian_exporter.py # Obsidian 笔记 + MOC
│   ├── zotero_exporter.py   # Zotero RIS/CSV
│   ├── i18n.py              # 双语唯一真源
│   └── excel_style.py 等              # 共享样式（ct-base vendor）
├── references/              # SOP、key 配置、检索菜单、多库方法
└── assets/icon.svg          # A 档 logo
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

# P0 · 引文验证（默认开启，mode=background）+ 证据日志在 --run 下自动产出；
# 用 --verify {all|top|background} 控制范围；源感知跳过会避免「同源再回源」的冗余往返
# （来自 OpenAlex / Europe PMC 的论文直接按来源可信，不再回源核验）。
# 验证是反幻觉闸门（ct-base §17.1 P0）：不可完全关闭——"none" 不是合法模式（v0.9.6 已移除 CLI 旁路）。
python scripts/ct_literature.py --topic "osimertinib" --run --out-dir ./out
# 大结果集的最佳速度/覆盖折中：仅验证按排序取的前 N 条（默认 15；--verify-top-n 调 N——验证永不关闭）
python scripts/ct_literature.py --topic "osimertinib" --run --verify top --out-dir ./out
# 非阻塞默认：background 模式后台流式核验，不拖延报告产出
python scripts/ct_literature.py --topic "osimertinib" --run --verify background --out-dir ./out
# v0.6.11 · 跳过标题/作者一致性层（验证仍会解析标识符）
python scripts/ct_literature.py --topic "osimertinib" --run --no-consistency --out-dir ./out
# v0.7.0 · 进度以 NDJSON 事件流输出到 stdout（面向 agent：--progress json 会把子模块
# print 重定向到 stderr，保证 stdout 可解析；事件含 run_start / source_done / source_failed /
# fetch_done / verify_progress / verify_done / evidence_log / export_done / export_failed /
# run_done，每行一个 JSON 对象、实时 flush）
python scripts/ct_literature.py --topic "osimertinib" --run --progress json --out-dir ./out
# v0.7.0 · 两阶段交付：报告数秒即出（未验证版），验证结果后台回填后自动重渲染
python scripts/ct_literature.py --topic "osimertinib" --run --verify background --out-dir ./out

# P1 · PROSPERO 系统评价注册库（可选，保留接口，未提供 token 前自动空跳过）
python scripts/ct_literature.py --topic "osimertinib" \
    --with-prospero --prospero-token "$PROSPERO_API_TOKEN" --run --out-dir ./out
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
  sources,                                    # 贡献来源列表
  # --- P0 验证阶段附加（verify_citations.py）---
  citation_verified,                          # bool
  citation_verify_status,                     # verified | bot_blocked | mismatch |
                                              #   unresolved | no_identifier | suspicious | unverified_sampled
  citation_verify_note,                       # 人类可读详情
  citation_consistency,                       # bool | None  （v0.6.11）
  citation_title_ratio                       # float | None  （归一化标题相似度）
}
```

---

**版本**：v0.9.7 | **许可证**：MIT | **作者**：medstatstar, phoe-zip

如有功能改进建议、Bug 报告或其他反馈，欢迎直接联系作者：medstatstar@gmail.com（张文彤 / Wintone Zhang）。

---

## 保密声明

> CT 全系列技能由 20+ 个技能构成，按「输入是否涉密」分为 **A、B 两档**（network / egress / publish 为独立正交属性，详见 ct-base §11），完整覆盖新药临床试验（Clinical Trial）全流程的各方面需求。
>
> - **A 档（输入非涉密）**：输入为普通数据，可完全本地运行（`network=off`）或对外公开检索（`network=public-retrieval`，如 ct-registry / ct-advisor 等）；不涉及任何保密信息。A 档技能均在 GitHub 公开发布。
> - **B 档（输入涉密）**：输入含药企需严格保密的临床试验数据 / 方案 / CRF（如 ct-analysis、ct-sdtm、ct-protocol、ct-eligibility 等）；B 档**既能本地处理**（`egress=none`，数据不出域）**也能对外公开检索**（`network=public-retrieval`，如 ct-protocol 调 ct-registry / ct-literature 抓取公开试验设计与文献作参考——仅公开查询词出域）；或需审批出站（`egress=approval-req`，如 ct-eligibility）。但**均不对外公开发布**；涉密输入绝不随包 / 出站；若有定制 / 本地部署需求，欢迎与作者联系。
>
> 📧 联系方式：medstatstar@gmail.com，张文彤（Wintone Zhang）
