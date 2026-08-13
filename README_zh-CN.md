# 临床试验文献检索专家（ct-literature）

[🇨🇳 中文 (当前)](./README_zh-CN.md) | [🇺🇸 English](./README.md)

<div align="center">
<img src="assets/icon.svg" width="240" height="240" alt="ct-literature 图标"/>
</div>

> **`ct-` 技能库中的 B 档公开情报技能：检索某药物 / 疾病 / 方法已发表的学术文献，将多个公开文献源归一化为统一去重的证据库，并提取证据格局与 CSM（累积安全性监测）定性子集。**

> 💡 **默认无 key 也能跑，但免费 key 能大幅提额：** OpenAlex 自 2026-02-13 起强制要求 key；无 key 时处于 keyless 池（100 credits/天，标注 *not suitable for production*）。免费 key 可提到 100k/天。申请约 30 秒 —— 见 §7 及技能在检测不到 key 时自动打印的申请提示。

> 不需要命令，也不需要手册。你只要在对话里用**自然语言**说清想查什么：技能从 OpenAlex（主源）加可选的 Europe PMC / Semantic Scholar 取数，然后写出自包含的 **HTML + Excel** 报告。B 档：计算完全本地，仅对外公开检索。**注意：你的主题词会发往下方公开文献 API —— 出站说明见 §7。** 技能**仅在你明确发起文献检索时激活**，不会在不相关对话中自行联网检索。

## 目录
- [适用人群](#适用人群)
- [数据源](#数据源)
- [为什么可以信任输出 —— 反幻觉设计](#为什么可以信任输出--反幻觉设计)
- [如何在对话里使用](#如何在对话里使用)
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

## 数据源

| 源 | 密钥 | 角色 |
|---|---|---|
| OpenAlex | 推荐 key（免费 100k/天，技能 `.env` 自动加载）；无 key 限 100/天（2026-02-13 起） | **主源** — 覆盖广、含引用数 |
| Europe PMC | 无需 | **默认开启**（`--no-with-europepmc` 关闭） — MEDLINE/MeSH 生物医学精准 |
| Semantic Scholar | 无需（易 429） | 可选 `--with-semantic-scholar` — 引用排序；**无 key / 429 时自动跳过** |
| bioRxiv | 无需（经 Europe PMC PPR） | 可选 `--with-biorxiv` — 生物医学预印本 |
| medRxiv | 无需（经 Europe PMC PPR） | 可选 `--with-medrxiv` — 医学/临床预印本 |
| arXiv | 无需 | 可选 `--with-arxiv` — 物理/CS/ML 方法学广度 |
| PROSPERO | 需 token（认证头未公开） | 可选 `--with-prospero` — 系统评价注册库 / 方案发现；**保留接口**，未提供可用 token+header 前自动降级为空跳过 |

### 各来源如何配合

默认组合 —— **OpenAlex（主源）+ Europe PMC（默认开启）** —— 其实已经覆盖到了几乎整个已发表文献版图：通过这两个入口，你就能拿到 PubMed / PMC、bioRxiv / medRxiv / arXiv 预印本，以及 Crossref、Semantic Scholar、CORE、Unpaywall 的记录。其它来源做成可选，不是因为这对组合不完整，而是出于两个现实考量：

- **抗限流** —— Europe PMC 偶尔会被限流（HTTP 429）。一旦如此，独立的各入口（Semantic Scholar、各家预印本服务器）让你可以绕开单一瓶颈、继续拓宽覆盖。
- **预印本时效** —— 当你要追预印本的新鲜度时，才需要打开 **bioRxiv / medRxiv 的直接检索**：直接从源头拉取，而不必等它慢慢同步进 Europe PMC 的 PPR 供稿。

## 为什么可以信任输出 —— 反幻觉设计

由 LLM 驱动的文献工具，最容易翻车的一点就是**编造根本不存在的论文** —— 伪造的 DOI、写错的 PMID、看似合理实则虚构的引文。ct-literature 从设计上就让这种事不可能发生：四道独立防线 + 两项运行保障。

1. **每条引文都回源核验（P0，默认开启）。** 一篇文献进入报告之前，它的标识符会先去真实的文献 API 跑一遍：DOI → `doi.org`（必须返回 HTTP 2xx）、PMID → Europe PMC 的 `EXT_ID`、OpenAlex id → `api.openalex.org/works/<id>`。每篇文献都会被打上 `citation_verified` 标签和状态：`verified` / `bot_blocked` / `unresolved` / `no_identifier` / `suspicious`。**格式错误的 DOI 会被标为 `suspicious`** —— 等于在「疑似幻觉标识符」进入报告之前就把它拦下来。可用 `--verify {all|top|none}` 调节范围；默认 `all` 会对每篇都核验。
   - **`bot_blocked`**：部分出版社（NEJM、JAMA、Wiley、MDPI 等）对程序化访问回 **403**，但 DOI 本身是真实的。技能把这种情况单独标出 —— 它**不是**断链，且文献仍记为 `verified=True`。
2. **标题/作者一致性深度校验（v0.6.11）。** 标识符一旦解析到存活资源，技能会再去拉该资源的权威元数据（标题 + 第一作者姓氏）：DOI 走 **Crossref**（即便出版社拦 `doi.org` 它也 bot-friendly）、PMID 走 **Europe PMC**、OpenAlex id 走 **OpenAlex**，并与你手上的这篇文献比对。解析到**另一篇**文献则标为 **`mismatch`**（而非 `verified`）；`bot_blocked` 的 DOI 若 Crossref 元数据吻合则**升级为 `verified`**。于是即便一个「幻觉出的但真实存在的 DOI」也能被抓出来。元数据抓取失败会优雅降级为"verified，一致性未核验"——绝不因瞬时 API 错误捏造 mismatch。可用 `--no-consistency` 关闭该层。
3. **完整溯源，而非被摘要掉。** 每一篇归一化后的文献都保留 `sources` 列表（来自哪个 API），`evidence_log.json` 还会存一条不可变风格的审计轨迹：查询 → 来源 → 命中数 → 取数时间 → 核验率。任何一条结论都能回溯到产出它的那次具体 API 调用。
4. **报告绝不用流畅文字补窟窿。** 报告里每一句事实都带来源标注，或明确的 `⚠️ 需官方核实` 标记。技能**不会**为了填满空缺而编出看似合理的证据 —— 某个来源失败了、或某篇未核验，它会明说，而不是藏着。

两项运行保障进一步加固这一点：**安全预览（Safe Preview）** 把归一化 / 报告生成都留在你本机（不执行任何远端代码）；**源感知跳过** 避免冗余重复核验，同时仍按「来源可信」信任每个标识符（OpenAlex 返回的论文本来就带真实 OpenAlex id，所以不再回去查一遍）。以上均遵循 ct-base 反幻觉规范（§17.1）。

**结论：** 本技能给你的参考文献是真实存在、可追溯、可核验的 —— 放进幻灯片、方案或 CSR 附录都稳妥，但任何监管提交前仍请对照官方来源复核（见 §7）。

## 如何在对话里使用

ct-literature 是一个**对话式技能**：你只要把想查的内容告诉助手即可 —— 无需命令、无需记参数名。安装为 WorkBuddy 技能后，你在对话里通过 Skill 工具调用它即可，无需额外配置；但它只在你主动调用时激活。

下面给出 8 个由简到繁的真实对话示例，每个都含**「你这样说」**与**「助手会这样回（示意）」**，并说明报告如何产出。主交付物是自包含的 **`lit_report.html`**（离线、可打印）与 **`lit_report.xlsx`**（4 页：概览 → 文献总表 → 安全性相关 → 证据溯源）。

### 示例 1 · 简单文献检索（直接作答）
**你这样说：**
检索奥希替尼在 NSCLC 的已发表文献，2018–2025。

**助手会这样回（示意）：**
正在路由到 OpenAlex（主源）。这是归一化后的证据库 —— 论文数量、高被引文献、年度趋势，外加一个 CSM 子集。报告已写入 `lit_report.xlsx`（以及 `lit_report.html`）。

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
在 <https://openalex.org/settings/api> 申请免费 key（约 30 秒）。然后按你习惯的方式配置即可——**在对话里告诉助手你想配置 key**（它用 Write/Edit 把 `OPENALEX_API_KEY=<key>` 写进 `ct-literature/.env`；key 仅本地存储、绝不回显、绝不写日志，只经 HTTPS 发往官方 OpenAlex API）；或自行配置：(a) 在 `ct-literature/.env` 加一行 `OPENALEX_API_KEY=<key>`，(b) 设为环境变量 `OPENALEX_API_KEY`，(c) 命令行传 `--openalex-key <key>`。**注意**：聊天消息可能被平台记录留存——如需最高隐秘性，请走自配置 (a)–(c)。

### 示例 5 · 拿 Excel 交付物
**你这样说：**
能同时给我 Excel 文件吗？

**助手会这样回（示意）：**
可以 —— `--run` 总会一并产出 `lit_report.xlsx`（学术绿主题，4 页：概览 → 文献总表 → 安全性相关含 KPI 卡与图表；`is_safety` 行高亮）与 `lit_report.html`。用 `--no-xlsx` 跳过表格，或用 `--no-html` 跳过网页。

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

### 示例 8 · 按需抓取合法开放获取 PDF
**你这样说：**
从你刚生成的报告里，尝试为被引前 10 的文献获取合法开放获取 PDF。

**助手会这样回（示意）：**
从报告中的这 10 篇取出 DOI/PMID，再逐一向合法 OA 来源（Unpaywall、Europe PMC、PubMed Central）解析。它会明确告知哪些解析成功、哪些没有 —— 例如"10 篇中 7 篇已解析；3 篇无合法 OA 副本（付费墙——请走机构图书馆 / 文献传递 / 联系通讯作者）"。解析到的链接写入 `lit_report_oa_pdfs.md`（或追加进报告）。这一步按需触发，**不**绕过任何付费墙。

**⏱ 耗费提示** —— 10 篇批量约增 20–40 秒及少量 API 用量；50 篇批量约增 1–3 分钟。

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

**Q：中文系统下输出是中文吗？** A：是。输出语言默认跟随系统（中文系统→中文，其他→英文），随时一句话强制切换（如"用中文回复" / "switch to English"）。

**Q：Semantic Scholar 老是失败 / 被跳过？** A：S2 的 key 需填表人工审核、非自动发放，申请后需等待，短期内通常无 key。未配置 key 时本源被**直接跳过**（不发起网络请求），而非尝试后降级。若需要引用排序，之后配置即可。

**Q：一次检索要跑多久？有限额吗？** A：
- **典型耗时**：各启用源**相互并行**（每个源一个并发任务），但**同一源内部按页链式串行**——源内请求逐个依次发出，因为源内并行翻页会提高限流 / 封号风险（如 OpenAlex 无 key 池）。Europe PMC ~1秒/页，OpenAlex ~2秒/页，所以墙钟时间是*最慢的那个源*，而非各源之和。拉取约 50 篇文献的 3 源合并通常 **10–30 秒**完成（开启全量引文验证时再多 ~1–4 分钟——见运行前的耗时预估）。加预印本（bioRxiv/medRxiv/arXiv）再多数秒。
- **结果上限**：默认 `max_results` 控制每次合并的最大文献数；调高会线性增加耗时与 API 用量。
- **速率限制：**
  - **OpenAlex（无 key）：** 100 credits/天（2026-02-13 起）。一次多页检索可用 5–20 credits。免费 key 可提到 **100k/天**。
  - **Europe PMC：** 无严格 key 限制，但请合理控制请求频率（不要高频循环调用）。
  - **Semantic Scholar（无 key）：** 极易触发 HTTP 429；未配置 key 时技能会直接跳过本源。
- **建议**：先用默认源（OpenAlex + Europe PMC）+ 适中 `max_results` 起步；仅在确实需要更广覆盖时再加装额外源。

**Q：为什么文献抓取速度不能更快一些？** A：现有结构已经是各 API 允许的速度上限了。(1) **不同源之间已经并行**（每个源一个并发任务）——再增加跨源并行度也不会更快。(2) **同一源内部必须链式串行**——公开文献 API（OpenAlex 无 key 池、Europe PMC 礼貌池）会对并发请求过多的客户端限流甚至封号；串行翻页正是为了不触发风控。(3) 如果某次运行觉得慢，通常瓶颈是**全量引文验证**（默认开启，每篇 1 次或多次 HTTP 查询）——改用 `--verify top 15` 或 `--verify none` 可省约 1–4 分钟。(4) 保持 `max_results` 适中——耗时与 API 用量随它线性增长。批量抓取 PDF 是另一项每篇数秒的操作（每次请求都要走重定向链）。

**Q：能下载全文 PDF 吗？** A：可以，分两种方式。（1）Excel 与 HTML 报告始终包含**「开放获取链接」**列，当论文在出版社或存储库有免费 PDF 时直接给出链接（通常覆盖 60–80% 的近期文献）；付费墙论文显示「—」。本技能**不**绕过付费墙、不下载受版权保护的内容——付费墙论文请通过所在机构图书馆、文献传递或直接联系通讯作者获取。（2）按需还可由技能主动为你抓取指定文献的合法开放获取 PDF：
- **能做什么：** 给定 DOI 或 PMID，尝试从合法来源（Unpaywall、Europe PMC、PubMed Central 等）解析开放获取 PDF 链接。
- **耗费警告**：每次请求至少涉及 1 次 HTTP 查询 + 到 PDF 的重定向链。50 篇文献的批量会增加 **1–3 分钟**额外时间，并消耗额外的 API 额度（OpenAlex/Europe PMC）。
- **不保证成功**：许多论文没有合法开放获取副本。技能会明确告知哪些解析成功、哪些没有。
- **如何请求**：提供具体的 DOI/PMID 列表（如从报告中筛选），并说"尝试为这些文献获取合法 OA PDF"。

---

## 安全与隐私

### 安全预览（本地计算）
- **本地运行**：归一化 / 报告 / Excel 渲染全部在本机完成 —— 除随技能发布的脚本外，不在任何远程服务器执行代码。
- **可溯源、不编造**：报告中每条事实性断言都带来源标注（每篇文献的 `sources` 列表）或 `⚠️ 官方核实` 标记；绝不用流畅措辞填补证据空白。
- 输出仅供参考；申报 / 决策前请对照官方原文核实。

### 出站与隐私（仅公开检索）
- **唯一出站路径 = 公开文献 API**：运行检索时，你的主题词与筛选条件会发往 **OpenAlex**（`api.openalex.org`）、**Europe PMC**（`ebi.ac.uk/europepmc`）、**Semantic Scholar**（`api.semanticscholar.org`）—— 仅你启用的源。引文验证（默认开启）期间，技能还会额外访问 **`doi.org`**（DOI 解析）与 **Crossref**（`api.crossref.org`，用于标题/作者一致性校验）。**无其他出站路径，也绝不发送任何保密 / 申办方数据**。
- **密钥留在你本机**：若配置了 OpenAlex / S2 key，从你本地的 `ct-literature/.env` 读取，**绝不随包分发** —— `.env` 已被 `.gitignore`（GitHub）/ `.clawhubignore`（ClawHub）排除，SkillHub 窄白名单也不含它；随包发布的只有 `.env.example` 模板。重新安装后需你自己再次填入 key。
- **key 必须由你自行申请——技能不代发、也不内置任何 key**：OpenAlex 免费 key 请自行到 <https://openalex.org/settings/api> 申请（约 30 秒）。配置方式按你习惯：**在对话里告诉助手你想配置 key**（它用 Write/Edit 把 key 写进 `ct-literature/.env`；key 仅本地存储、绝不回显、绝不写日志，只经 HTTPS 发往官方 OpenAlex API），或按 §7 自行配置（`.env` / 环境变量 / `--openalex-key`）。**提醒**：聊天消息可能被平台记录留存——如需最高隐秘性，优先走 §7 自配置。切勿从他人 `.env` 复制 key，切勿把 `.env` 提交进仓库。

---

## 进阶参考（开发者）

CLI 助手、运行要求、架构树与统一工作模式 schema 已移到此处，普通用户无需阅读。规范级内容与版本历史见 [`SKILL.md`](SKILL.md) 与 [`CHANGELOG.md`](CHANGELOG.md)。

### 运行时与要求
| 项目 | 要求 |
|---|---|
| 运行时 | Python 3.11+（CPython）。流水线**仅用 Python 标准库**（`urllib`）发 HTTP —— **无需任何第三方依赖**。 |
| Key（可选） | OpenAlex 免费 key（规模化推荐）；Semantic Scholar key 可选（放宽 ~1 req/s 限制）。均经 `.env` / 环境变量 / `--openalex-key`。 |
| 兄弟技能 | `ct-registry`（试验注册）、`ct-safety`（FAERS）、`ct-pipeline`（情报简报）—— ct-literature 既供给主题也被供给；均从 GitHub 安装。 |

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
└── assets/icon.svg          # B 档 logo
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

# P0 · 引文验证（默认开启）+ 证据日志在 --run 下自动产出；
# 用 --verify {all|top|none} 控制范围；源感知跳过会避免「同源再回源」的冗余往返
# （来自 OpenAlex / Europe PMC 的论文直接按来源可信，不再回源核验）。
python scripts/ct_literature.py --topic "osimertinib" --run --out-dir ./out
# 大结果集的最佳速度/覆盖折中：仅验证按排序取的前 20 条
python scripts/ct_literature.py --topic "osimertinib" --run --verify top --verify-top-n 20 --out-dir ./out
# 用 --no-verify-citations（== --verify none）可显式关闭验证。
python scripts/ct_literature.py --topic "osimertinib" --run --verify none --out-dir ./out
# v0.6.11 · 跳过标题/作者一致性层（验证仍会解析标识符）
python scripts/ct_literature.py --topic "osimertinib" --run --no-consistency --out-dir ./out

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

**版本**：v0.6.11 | **许可证**：MIT | **作者**：medstatstar, phoe-zip

如有功能改进建议、Bug 报告或其他反馈，欢迎直接联系作者：medstatstar@gmail.com（张文彤 / Wintone Zhang）。

---

## 保密声明

> CT 全系列技能由 20+ 个技能构成，完整覆盖新药临床试验（Clinical Trial）全流程的各方面需求。然而，由于大量技能涉及药企需要严格保密的临床试验数据、内部资讯等敏感内容，仅有不涉密的 A、B 级别技能会在 GitHub 上公开发布；涉及保密的 C、D 级别技能（如 ct-analysis 等）均设定为企业内部使用。

> 若您对这些涉密技能确有实际需求，欢迎与作者联系，定制并安装相关技能。

> 📧 联系方式：medstatstar@gmail.com，张文彤（Wintone Zhang）
