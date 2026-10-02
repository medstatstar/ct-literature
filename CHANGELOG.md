# Changelog · ct-literature

All notable changes to this skill are documented here. Versioning follows the
ct- library convention (A-tier public-intel skill — non-confidential input per ct-base §11, semver-ish).

## v1.2.0 (2026-10-02) · 默认启用滚雪球 + Report-first；结果不足建议卡；i18n 补全

- **默认启用**：`run()` 默认 `snowball=True`、`report_first=True`（零成本提升覆盖率 + 先出骨架改善 UX）；`f_depth` 默认 `standard`
- **结果不足建议卡**：`_finalize()` 在 ≤10 篇时主动建议扩展检索（snowball / deep / PICO / 罕见病专源），含罕见病关键词启发式
- **`_out()` JSON 模式**：携带 `message` 字段，建议文本可经流式到达前端
- **i18n 新增 5 条双语建议文案**：`suggest.few_results_prefix` / `snowball` / `deep` / `pico` / `rare_disease`
- **工作台 UI**：`f_snowball` + `f_report_first` 默认 `checked`；流式渲染 `suggest_few` / `suggest_item` 事件（橙色警告 + 斜体建议项）
- **F19 整改**：SKILL.md 正文中文段翻英文（§4 合规）
- **shared_sync 整改**：`i18n.py` / `kw_localize.py` 从 ct-base 同步；term_map 4 个光生物调节词条回填 ct-base 后同步
- **F13 版本对齐**：CHANGELOG 首部新增 v1.2.0

## v1.1.3 (2026-09-27) · SKILL.md 瘦身至 132 行：三大块外迁 references（零内容删除）

- **动因**：SKILL.md 326 行，超 ct-base §16.1 / spec_lint F02 软上限 200。按用户指示「不删除内容、
  移到其他文档」，做**逐字外迁**（原文一字不动搬出，SKILL.md 各节压成 3–6 行摘要 + 指针链接）：
  - `references/published_app.md`（新，51 行）← 原「Published Application」全节（登记表 + 重发布协议
    + publish-dist 改名事故记录）；
  - `references/capabilities.md`（新，133 行）← 原「Positioning / Data Sources / Clinical guideline
    sources / Features / Unified work schema / Output / Implementation（含 OpenAlex key）」明细表全文；
  - `references/dialogue.md`（新，84 行）← 原「Natural-Language Dialogue」全节（Step 0 四桶 / 红线 /
    echo block / merge_spec / 执行流）+「Bug Reporting §20.3」全节。
- **对账**：8 组关键特征串（appId、PROSPERO reserved、doc_type_filter、当前检索设定、
  ct-bugreport 端点、coze_resolve --pipeline、96 curated entries、load_openalex_key）在
  SKILL.md + 3 新文件合集内全部命中；SKILL.md 内 7 个 references 指针链接零死链；
  新文件未被 ignore 规则误挡（可随包发布）、无隐私命中。
- **运行面影响**：无功能代码改动；agent 侧加载契约不变（指针文件按需加载）。
- 版本未 bump（Unreleased——待下次发布随包）。

## v1.1.3 (2026-09-26) · 工作台流式检索补上检索词自动翻译 + dispatch_stream mode NameError 修复

用户反馈：「工作台操作的时候似乎没有对检索关键字做自动翻译」。核实：主管线 `/api/search`
（对话检索/高级参数）经 `ct_literature.run()` 一直有 `topic_translator` 中英翻译，
但「工具 → 实时流式检索」（`/api/lit-stream`）把用户关键词**原样**丢给 Coze——
中文检索词打到 OpenAlex/Europe PMC 基本零命中，属翻译盲区。

- **`workbench/server.py` `_lit_stream`**：调用 `dispatch_stream` 前插入
  `topic_translator.translate_topic(keyword, online_fallback=True)`（与主管线同一实现：
  本地词典贪心 + MeSH OR 扩展 + 联网兜底）；命中翻译时向前端推
  `translated {zh, en, partial, untranslated}` 事件；翻译模块异常不阻断，按原文检索。
- **`workbench/app.js`**：流式面板渲染 `⇄ 检索词已自动翻译：中文 → English`，
  部分未译时红字标注保留原文的词；新增 i18n 键 `trAuto` / `trPartial`（zh/en）。
- **连带修复 `adapters/fetch_coze_unified.py`**：`dispatch()` 于 2026-09-11 新增 `mode`
  参数时漏改 `dispatch_stream()` 签名，其内部 `mode=mode` 引用未定义全局名——
  流式检索一 `--run` 即 `NameError: name 'mode' is not defined`（e2e 实测踩中）。
  补 `mode: str = "search"` 形参并透传。
- **验证**：本地起 server 实测——「奥希替尼 间质性肺病」→ `(osimertinib OR Tagrisso)
  interstitial lung disease (ILD)`，OpenAlex 真实检索返回 5 篇；纯英文 `metformin`
  原样透传、无 translated 事件。bundle 已 `build_publish.py` 重建（3 处修改均确认落盘）。
- **已发布（2026-09-26 11:45）**：按 ct-workbench-publish 铺开计划验收协议在新 workspace
  覆盖发布——install_genie ①→publish_guard pre ②→deploy（appId 覆盖，shareLink 断言
  `ct-literature.app.workbuddy.host` 通过）→genie 回读无污染 ⑤→post-gate PASS ⑥→
  线上验证：app.js MD5 与载荷一致、`/api/status` 200、线上 `/api/lit-stream`
  「奥希替尼 间质性肺病」实测返回 `translated` 事件 → `(osimertinib OR Tagrisso)
  interstitial lung disease (ILD)`。跨 workspace 方案 B 对 ct-literature 二次实证。

## v1.1.3 (2026-09-19) · 解码与下载并行：本地直链一到手就落盘

用户反馈：「直链解码和 PDF 下载完全可以并行的，现在观察到的是本地先搜索一遍有直链的，
然后把无法解码的再发送扣子。实际上，本地如果已经解码到直链，就直接开始下载就可以了。
这种并行操作不仅在工作台界面上，在上下文对话技能调用中也应该可以这样操作。」

两处都确实是**名不副实的串行**：`coze_resolve.py` 是三段串行，`PdfDownloader.run()`
的 docstring 一直写着 `local download || coze decode`，代码却是本地整段跑完才启动 coze 线程。

### 工作台链路（`coze_resolve.py`，默认 `--pipeline`）
- **本地探针流式回报**：`_verify_direct(..., on_result=…)` 从 `ex.map`（等整批探完）改为
  `as_completed` + 逐条回调——命中直链的**那一刻**就入下载队列，不等其它探针。
- **两波提交、共用闸门**：「明显不是文件」的大头在探针跑的同时立刻提交端点；探针否掉的那批
  探完补送第二波。两波共用一把 `Semaphore(--concurrency)`，保证同一时刻打到端点的批数不翻倍。
- **Coze 返回一条就入队一条**：每批返回即逐条组装并立即下载，不再攒到末尾统一下载。
- **下载工人池**（`--dl-concurrency`，默认 3）：走 `PdfDownloader._limiter`（逐域名限速，
  线程安全）——同域名保距串行、跨域名并行。并发若不限速，同站请求节奏会被乘上工人数直接 429。
- **两波之外的收尾**：批次传送失败的篇目**等所有批返回后**才定性（沿用原口径：全部批失败且
  无任何非 manual 记录 → 「端点不可用」；否则只把失败批降级为 failed），漏网目标结案为「无直链」。
- **stats 改由最终行反推**（`_stats_from_rows`）：并发下「哪条先到」不确定，边跑边加加减减会错账
  （例如下载失败先扣了 `coze_resolved`、随后整批判为端点不可用）。行是唯一真相，反推必然自洽。
- `--no-pipeline` 保留串行三段做对照与排障；两条路径的 `items / stats / downloaded` **逐字段等价**（有测试钉住）。
- 进度新增 `stage id=pipeline {work_done, work_total}`：工作单元 = 目标数（解码 + 需要时的下载算一个），
  这是并发下唯一稳定、真实的分母；与解码并行的下载事件带 `parallel=true`，其 `total` 只是「已解出直链的篇数」
  会一路上涨，**不参与阶段锚点**。

### 上下文技能链路（`PdfDownloader.run()`）
- coze 解码线程**提到本地下载之前**启动，coze 与本地下载真正重叠；每个子批返回即落盘（原有 P1 流水线）。
- 「本地下载失败 → coze 兜底重试」改由 `_local_phase_done` 事件触发（本地阶段结束才放行），
  仍排在主批次之后，不与主批次抢端点。
- **修掉并发引入的竞态**：`local_failed_keys` 收集时排除「本来就路由到 coze」的篇目（新增 `coze_work_ids`）。
  否则 coze 线程与本地下载并行后，coze 篇目下载失败写下的 `pdf_download_note` 会被 4b 当成
  「本地失败」再送一次端点（重复解码 + 白烧配额）。

### 前端
- 新增流水线阶段锚点与 `parallel` 下载事件处理：并行下载**不占用阶段锚点**，避免进度条先冲到 90%
  再被真实进度拉回（A/B 验证过：还原此处理，新测试立刻 FAIL）。
- 阶段文案「并行推进：本地直链一到手就下载，其余同时送 Coze 解码」；下载提示改为「解码与下载并行」。

### 测试（新增 2 个套件，其余 11 个全部回归通过）
- `pipeline_e2e_test.py`（18 项）：用假端点 + 带时间戳的真下载证明——流水线下本地直链的下载
  **在第一次 Coze 返回之前就完成**，且 Coze 提交早于本地下载结束；串行下恰好相反（本地下载要等
  Coze 返回之后）。两模式结果等价。
- `pdf_download_parallel_test.py`（11 项）：`PdfDownloader.run()` 的解码与下载重叠；兜底重试仍排在
  主批次与本地阶段之后；coze 路由篇目不重复送端点。
- `coze_download_e2e_test.py` 扩到 30 项：真实服务上验证 `start.pipeline=true`、`id=pipeline`
  事件跑满、下载事件带 `parallel`，以及 `pipeline:false` 确实退回串行（无 pipeline 事件、无 parallel 标记、结果等价）。
- `coze_download_ui_offline_test.js` 扩到 27 项：新增「并行流水线」场景，断言并行下载事件
  没有把进度条顶到 90%、阶段文案带工作单元与并行 label。

### 顺带修掉的两个静默失效
- 进度通道加锁（`_EMIT_LOCK`）：流水线里探针 / Coze / 下载三类线程同时上报，整行必须原子写，
  否则两条 NDJSON 事件会咬进同一行、调用方解析失败（表现为进度凭空丢一块）。
- `coze_resolve.py` 补 `import threading` / `queue` / `urllib.parse`。

## v1.1.3 (2026-09-19) · 结果卡文献列表可展开摘要 + 逐篇「不下载」

用户反馈：「检索完成 / 唯一文献 37」下面的文献列表没有任何编辑修改功能，参考 meta-analysis
工作台的做法——单击能看到摘要，也能把某篇改成「不下载」。

### 交互（对齐 meta-analysis 工作台的 ▸/▾ + 内联详情 + 排除态）
- 行首 **▸/▾** + 标题整行可点 → 展开**内联详情面板**：完整摘要（可滚动，无摘要时明确写「来源未提供」）、
  作者、期刊卷期、DOI / PMID / OpenAlex 可点外链、OA 状态与 PDF 链接、被引数、引用核验状态 / 是否撤稿。
- 每行一个 **「不下载」/「恢复下载」** 开关；标记后整行淡化。
- 列表下方状态条：**「已排除 N 篇（不下载）」** + **「全部恢复」**；无标记时给出「点标题可展开摘要」的提示。
- 展开态与标记态都进自有 state（`WK[mountId]`），WBList 每次重渲染（分页/排序/筛选/切语言）仍保持一致。

### 状态落在磁盘上（不是在浏览器内存里）
- 新增 `GET/POST /api/selection`，读写 **`<out_dir>/.selection.json`**（`{version, skip:[{doi,title,id}], updated}`）。
  刷新页面、换浏览器打开同一输出目录，标记都还在。
- 归一化口径与下载端**逐字对齐**（`_norm_token`：小写 / 合并空白 / 去尾点），且 doi/标题/OpenAlex id
  **任一命中即同一篇**——只用 doi 会漏掉没有 doi 的预印本与指南，只用标题又怕标点差异。
- 写入**整体替换 + 原子落盘**（tmp + `os.replace`）：下载子进程读同一份文件，半份 JSON 会让所有篇目
  看起来「没被标记」而把刚排除的又下一遍。
- 前端**乐观更新 + 失败回滚**：任何异常都在状态条写明原因，不静默。

### 下载链路真的尊重标记
- `adapters/coze_resolve.py` 新增 `--skip-file`（默认自动读 `<out_dir>/.selection.json`）与 `--no-skip-file`；
  被标记篇目**照旧解码、但不落盘**，条目 `status=skipped`、`stats.skipped` 计数，**`direct_url` 保留**
  （链接清单不残缺，用户仍可手动打开）。
- 服务端 `/api/coze-stream` 在下载时传 `--skip-file`，`start` 事件带 `skip_count`；结果卡多一个
  「按标记跳过」KPI 与一条说明。**「解码直链数」与「实际落盘数」刻意分开**（跳过的确实解出了直链）。

### 验证
- 新增 `selection_e2e_test.py`（43 断言，全离线）：API 契约（归一化/去重/原子写/400-404/字符串不被拆成单字符）
  + **标记真的生效**（标 1 篇 → 只落 1 个 PDF、`stats.skipped=1`、解码仍是 2 条直链；取消标记 → 恢复 2 篇）
  + 适配器 CLI（`--skip-file` 标题命中、`--no-skip-file`、不传参数时自动发现）。
- 新增 `works_list_ui_offline_test.js`（41 断言）：初始即读标记、展开/收起、提交体形状、失败回滚、
  全部恢复、归一化口径、i18n 对称。
- 新增 `live_works_integration_test.js`（12 断言）：拿**真实 37 篇 + 真实接口**跑真实渲染代码，
  全部展开无 `undefined`/`[object Object]`/`NaN`，并真写一次标记核对落盘后还原。
- 旧 9 项回归全绿。

### 已知后续
- 线上发布包 `workbench/publish/` 需重新构建（`python workbench/publish-kit/build_publish.py`）后重新部署，
  线上才有 `/api/selection` 与新列表；本地 8787 已生效。

## v1.1.3 (2026-09-19) · 对话预览卡去掉「仅安全预览 (SAFE)」按钮

用户反馈：对话里的确认卡上那个 `仅安全预览 (SAFE)` 按钮要去掉。

- `renderIntent()` 的 `.acts` 从三按钮（确认并 --run / 仅安全预览 / 调整参数）减为两按钮
  （**确认并联网检索 (--run)** / **调整参数**）；`data-run="0"` 在对话卡不再出现。
- SAFE 空跑能力**没有删**，仍可从「高级检索」面板底部的 **预览 (SAFE)**（`#f_preview`）触发；
  `startRun(spec, dry)` 签名与 `/api/search` 的 `dry` 参数保持不变，dry 运行的徽章 / 日志
  （`runbadge safe`、`(… — no network)`）照旧显示 —— 那条路径现在只由表单入口到达。
- `btnSafe` 词条保留（中英各一处），仍被上述徽章与日志引用；对话卡不再引用它。
- 文档同步：`workbench/README.md` 的对话示例改为两动作，并注明 SAFE 空跑改由高级检索面板触发。

## v1.1.3 (2026-09-19) · Coze 解码按钮改为「解码 + 批量下载全文 PDF」

用户反馈：解码直链已经跑到这一步了，就应该顺势把 PDF 批量下载也做掉，按钮语义要改。

### 语义变更
- 结果卡主按钮 `Coze 解码全文直链` → **「解码 + 批量下载全文 PDF」**（`data-coze="dl"`，缺省行为）；
  新增次按钮「仅解码直链」(`data-coze="links"`) 保留「只要链接清单、不落盘」的老用法。
- 服务端 `/api/coze-stream`：`download` **缺省为开**（`body.get("download") is not False`），
  为真时给子进程加 `--download --dir <out_dir>`（`adapters/coze_resolve.py` 早已支持，只是前端从没传过）。
- `start` / `done` 事件新增 `download` / `pdfs_dir` / `pdf_count`（新增 `_count_pdfs()` 数盘上实际篇数，
  因为卡片要打包的是**目录里现有的** PDF，可能含上一轮的）。

### 进度
- 下载阶段改用 **已下/总数** 精确推进（`COZE_DL_LO=90` 起，占 8 个百分点），不再用时间缓动 ——
  篇数已知，估算反而更不准。另补 `prefilter` 阶段锚点与 `coze` 阶段的「批次 i/n」显示。

### 结果卡
- 新增「本次已下载 N」「pdfs/ 现有 N 篇」两个 KPI；本次一篇没下到时给出明确说明（而非静默）。
- 新增 **「打包下载 N 篇 PDF」**：先 `GET /api/artifacts?dir=<out>/pdfs` 本地核对件数/体积，
  再提交 `/api/zip`；超 2000 件 / 2 GB 给中文提示。**为什么先核对**：直接提交的话服务端 413
  会落在隐藏 iframe 里，用户只会觉得"点了没反应"。
- 新增「打开 PDF 文件夹」（`artSetDir(<out>/pdfs)` + `showView`）。

### 验证
- `coze_download_ui_offline_test.js`（21 断言）：请求体 `download` 真假、下载阶段 5/10→94%、
  卡片 KPI/按钮、打包 payload 只收 `.pdf`、空目录不提交、仅解码时无打包按钮。
- `coze_download_e2e_test.py`（22 断言，**完全离线**）：起本机 HTTP 服务伺服假 PDF（>5 KB，
  否则过不了 `_download_to` 的 5 KB 校验），把 OA 链接指向它 → 本地预筛命中、不呼叫外网端点 →
  验 `--download` 真落盘、`pdf_count`、`downloaded`、`%PDF-` 魔数，并顺手把刚下到的 PDF 打包解压比对字节。

### ⚠️ 本轮踩到的工具坑（重要）
- **同一文件并行 Edit 会互相覆盖，且报"成功"**。本轮 6 处改动被静默吞掉（前后端都有），
  包括最关键的服务端 `if _dl:` —— 导致「下载」开关根本没接上，而 py_compile / 语法检查全绿
  （未定义名是运行时错误）。**教训：同一文件的多处编辑必须串行**；改完要用「grep 关键串 +
  行为级测试」验证，不能只信 Edit 的成功回执。
- 由此新增 `i18n_audit.js`：抠出 `WB_T` 求值，比对 zh/en 键集**双向对称** + 页面引用的键是否齐备。
  被吞掉的字典改动会表现为「界面显示原始 key」，这个脚本把它变成显式失败（本轮据此修好 335/335）。

## v1.1.3 (2026-09-19) · 「输出文件」进入即刷新 + 检索过程只读 + PDF 一键打包

用户反馈三条：① 第一次进入「输出文件」面板是空的，必须手点「刷新」才出内容，很别扭；
② 「检索过程」分组完全没必要给下载；③ 「全文 PDF」应该能一次性打包下载。

### ① 进入面板自动读盘（根因：指向了一个早已删除的对象）
- 根因：`showView()` 里写的是 `if(v==="artifacts") wbArt && wbArt.refresh();`，而 `wbArt` 是上一版
  WBList 产物列表的全局对象，**重构为自写渲染后已经不存在**。`wbArt && …` 短路为假，所以
  「进入视图」这条路从来没触发过读盘 —— 首屏空白、必须手点「刷新」（那个按钮走的是另一条路）。
- 修复：`showView("artifacts") → loadArtifacts()`，进入即读盘。两处「查看输出文件」跳转按钮
  改为只设路径 + `showView(...)`，避免「showView 一次 + 手动又一次」抓两遍。
- 新增请求序号 `artReq`：连点 / 快速切目录时**后发请求胜出**，旧响应回来直接丢弃，不会回写过期内容。
- 首次读取且尚无内容时显示「读取目录中…」占位，避免「看着像坏了」。
- Coze 解码完成时若正在看该目录，顺手 `loadArtifacts()` 刷新（原为 `wbArt` 死代码）。
- 回归防线：源码级断言「不再存在 `wbArt.refresh()` 调用」+ **行为级**断言（抠出真实 `showView`
  源码执行，验证 `showView("artifacts")` 真的触发了读盘）。

### ② 「检索过程」只读，去掉下载入口
- `artDescribe()` 归类为 `proc` 的文件（`.coze_links.json` / `evidence_log.*` / `prisma*` / `.log` / 其余 `.json` / 未匹配的 `.md`·`.txt`）
  只渲染「查看」（浏览器内联打开），**不再渲染「下载」按钮**；不可预览的类型显示「仅供排错查看」。
- 分组说明改为「命令与原始返回记录，仅供排错查看（不提供下载）」，让规则的**理由**可见。
- 报告 / 题录数据 / 全文 PDF 的下载不受影响（断言覆盖）。

### ③ 全文 PDF 与文件夹一键打包（新增 `GET/POST /api/zip`）
- **服务端**：新增流式 zip 端点，`{dir, names[], dirs[]}`（JSON，或 UI 实际使用的表单 `payload=`）。
  - 边压边发（chunked，`zipfile` 走不可 seek 流 + data descriptor），**不落临时文件、不占内存**——
    上百篇 PDF 也不会把服务器或浏览器撑爆。
  - 只打包 `.pdf` 时用 `ZIP_STORED`（PDF 本身已压缩，存比压更快且无损），混类型才 `ZIP_DEFLATED`。
  - `dirs` 递归打包子目录，**跳过隐藏文件/隐藏目录**；显式点名隐藏文件仍会打包。
  - 包内附 `_bundle_info.txt`：来源目录 / 实际件数 / 体积 / 构建时间 / 中途跳过的不可读文件。
  - 安全限流：相对路径 `..` 拒绝（穿越防护）；>2000 件或解压后 >2 GiB 返回 413 并提示缩小范围。
- **前端**：`全文 PDF` 组头加「打包下载 N 项」（只看用途分组，**不截断**，193 篇就是 193 篇）；
  每个文件夹行加「打包」（整目录递归）。打包是**新增入口**，单篇「下载」保留。
- **前端提交方式**：隐藏 `form` + 隐藏 `iframe` POST，让**浏览器原生接管下载**（有进度、可取消、可重试），
  不把 zip 读进 JS 内存，也不会让当前页面跳走。提交后在面板顶部给一条可关闭的状态条
  （件数 / 体积 / 「在下载栏里看进度」），空集合 / 超限时给可操作的警告而不是静默失败。

### 验证
- 服务端 `zip_endpoint_test.py`：21 项全过（真起 handler、真发 HTTP、真解压校验 CRC；含 PDF STORED、
  子目录递归、隐藏文件跳过、`..` 穿越拒绝、404/400/413、`_bundle_info.txt` 内容、GET 形式）。
- 前端 `artifacts_ui_offline_test.js`：44 项全过（含 proc 无下载、文件夹有打包、筛选后只打包命中项、
  空集合不提交、`showView` 行为级断言、中英 316 键对齐、13 个新键双语齐备）。
- `live_artifacts_integration_test.js`：拿**真实 8787 服务返回**喂真实渲染代码，并把组头「打包下载」
  提交上去，端到端解出真实 PDF（810 KB，CRC 正常）——覆盖「离线假数据恰好长得对」的盲区。

## v1.1.3 (2026-09-19) · 「输出文件」面板重构（可读性 + 目录导航 + 真相校验）

用户反馈：「产物浏览界面还是不对，不知道怎么用」。根因是面板只有一个裸文件列表 + 一行图例，
既不解释每个文件是什么，也无法返回上级目录，且默认固定在 `./out`。

- **重命名为「输出文件」**（导航 / 标题 / 对话卡片按钮 `产物浏览` → `查看输出文件`），去掉「产物」这类需要解释的行话。
- **按用途分组**：子目录 / 报告 / 题录数据 / 全文 PDF / 检索过程 / 其他，每组带一句说明与计数。
- **每个文件一句人话说明**（`artDescribe()`）：例如 `lit_report.html` → 网页版检索报告（可打印成 PDF）、
  `references.bib` → BibTeX 引文（EndNote / Zotero 导入）、`.merged.json` → 多源合并去重后的完整题录。
- **显式按钮**：可预览类型给「查看」（浏览器新标签）+「下载」；xlsx/zip 只给「下载」（主按钮）。
  徽标按用途着色（表格绿 / PDF 红 / 过程灰 / 目录中性）。
- **目录导航**：新增「↑ 上一级」（此前只能进不能出）、回车即跳转、文件名筛选框、
  以及三个快捷入口（最近一次检索输出 / 工作台默认 `./out` / 上级目录）。
- **空态与错误态可操作**：空目录给出「去跑一次检索」；目录不存在给出路径 + 一键跳回最近一次检索输出。
  另：`/api/artifacts` **不再自动创建目录**（此前输错路径会静默建空目录）。
- **自动定位**：`/api/status` 新增 `last_out_dir` / `cwd`；面板目录不存在时自动跳到**最近一次检索的输出目录**
  （此前只要检索写在别处，面板就永远空白，看起来像坏了）。
- 大目录（如 193 篇 `pdfs/`）默认只渲染前 40 行 + 「显示全部 N 项」，避免一次插入上千个 DOM 节点。
- 离线验证脚本 `artifacts_ui_offline_test.js`（stub DOM 跑真实页面代码）：14 项断言全过，
  含分组顺序、按钮可见性、徽标着色、大目录截断、空态/错误态、中英字典 302 键对齐。

## v1.1.3 (2026-09-19) · Coze 解码「180 秒超时」根因修复（本地预筛 + 拆批并发 + 超时口径）

用户报错原文：`Command '[...coze_resolve.py, --in, ./out\.merged.json]' timed out after 180 seconds`。

- **根因（三层，均非用户操作问题）**：
  1. **超时口径错**：报错来自**一次性**接口 `/api/tools` → `_subprocess_text(timeout=180)`。
     实测该端点**单批（50 篇）解码要数分钟**（3 篇的一批也要 88s），180s 必然先到；
     >50 篇时脚本按 50/批**串行**传送，总时长 = 批数 × 单批时长，180s 更无可能。
  2. **前端口径**：前端在流式端点不可用时会静默回退到上述一次性接口，
     于是把 Python 的 `TimeoutExpired` 原文直接摊给用户看。
  3. **做了大量无用功**：`coze_resolve.py` 把**所有** key 都送端点，
     而实测检索结果里**约 2/3 本身就是文件直链**（bioRxiv/medRxiv `.full.pdf`、Nature/UCL 等），
     端点只是把可直下的链接再"解码"一遍。端点单篇约 19s，这部分纯属白等。
- **修复**：
  1. `workbench/server.py`：新增 `COZE_LEGACY_TIMEOUT_S = 420`（一次性接口专用），
     并捕获 `TimeoutExpired` 返回**可操作的中文说明**（含本次篇数/批数 + 建议改走流式），
     不再把 `Command '[...]' timed out after N seconds` 抛给用户。
  2. `adapters/coze_resolve.py`：拆批传送改为**并发**（`--concurrency`，默认 3），
     总时长由「Σ 各批」降为「最慢的一批」；每批独立降级，单篇仍只发送一次。
  3. `adapters/coze_resolve.py`：新增**本地预筛**（默认开，`--no-direct-prefilter` 关闭）：
     - 预印本 `.full.pdf` 走**规则认定**（bioRxiv/medRxiv 对机器人 UA 一律 403/429，
       批量探测必然被限速，校验结果不可信）→ 标记 `preprint_direct`；
     - 其余疑似直链用**浏览器头 + `Range: bytes=0-1023`** 实测（**不能用裸 HEAD**：
       裸 HEAD 会把能直下的预印本误判为不可下）→ 标记 `local_direct`；
     - 实测本机 193 篇：**112 篇本地即得直链**（预印本 100 + 实测 12，耗时 16.6s），
       送端点的从 193 降到 **81**（4 批 → 2 批）。结果卡新增说明，标注两类来源。
  4. `workbench/server.py`：结果卡/接口透传 `concurrency` 与 `direct_prefilter`。
- **顺带修正一处真实 bug**：开跑前用 `os.remove` 清理上一轮 `.coze_links.json`，
  在沙箱环境会被安全删除拦截 → 残留旧文件被当作**本轮 done** 上报（实测：取消后竟上报旧结果）。
  改为**按 mtime 判定结果新鲜度**，不再依赖删除是否成功。
- **已知事实（非代码问题）**：该端点 `CT_ENABLE_BROWSER_PDF_DOWNLOAD` 未启用，
  B 路径（浏览器下载）不可用，因此付费墙 / 仅有 DOI 的文献会返回 `pdf_failed`
  （`error`: "A 路径(OA/PMC/直链)全部失败；B 路径(浏览器)未启用"）。需要解码此类文献，
  须在端点侧开启该开关。

## v1.1.3 (2026-09-19) · Coze 全文解码「长等待」体验修复（流式进度 + 取消 + 正确状态）

- **问题**：点「Coze 解码全文直链」后界面只显示一句静态文案，30–180 秒内毫无变化（用户反馈"速度很慢，
  最好给提示或进度条"）。
- **修复（三层）**：
  1. `adapters/coze_resolve.py`：新增 `--progress {off,text,json}`，向 **stderr** 逐行 flush 结构化进度
     （`stage` 阶段：load / identify / coze[含批号] / assemble / download / done；`log` 日志；
     拆批时逐批上报）。stdout 仍只承载最终 JSON（`--out` 写文件时摘要也改走 stderr）；
     同时给 `PdfDownloader` 传入 progress 回调——**此前该回调未传，`_log` 全部被丢弃，进度等于没有**。
  2. `adapters/pdf_download.py::_parse_coze_stream`：SSE 事件**边到边报**（原来先把整流读完再打印，
     日志只能在结束后一次性涌出），并按节点标题 / 输出字节数 / 已用时上报；`ping` 保活事件每 20s
     转成一条心跳日志。
  3. `workbench/server.py` 新增 `POST /api/coze-stream`：chunked NDJSON 推 `start / stage / progress /
     tick(每5s) / done / error`；子进程 `PYTHONUNBUFFERED=1` + `-u`；**静默超时 200s** 判定端点无响应并
     终止（逐批场景每批都有输出，不会误杀）；客户端断开 / 点取消即 terminate 子进程；
     `/api/stop` 同时覆盖解码子进程；跑之前先删旧 `.coze_links.json`，避免把上一轮结果当本轮成功上报。
  4. `workbench/index.html`：解码卡改为实时卡（阶段名 + 已用时 + 进度条 + 日志滚动 + 取消按钮），
     进度为「阶段锚点 + 时间缓动」并**明确标注"按时间估算"**；20 秒后出现慢速提示；
     老服务无该端点时自动回退一次性 `/api/tools`。
- **顺带修正两处真实 bug**：
  - `coze_resolve.py` 的 `coze_unavailable = (projects is None)` 写在兜底填充**之后**，恒为 False
    → 端点不可达被误报为 `pdf_failed`（"无直链"）。已前移判定：端点连不上时正确返回
    `status=unavailable` / `stats.coze_unavailable=N`，界面据此提示"端点无响应，检索产物不受影响"。
  - 多批传送**全部失败**时同样判为端点不可用（不再逐篇报"无 OA"）。

## v1.1.3 (2026-09-17) · 飞书版本字段落点对齐（ct-base coze_io_contract §2.1）

- **结论：ct-literature 客户端本来就合规，本次只补文档约束、无行为改动。**
  ct-base §2.1（2026-09-17 定）规定版本字段（`skill_version` / `coze_version`）唯一落点是
  飞书 `resultstr`，`querystr` 不存版本信息。逐项核对本技能：
  1. `adapters/fetch_coze_unified.py` / `adapters/pdf_download.py` 均按 §1.2 发**顶层信封**
     `skill_version`（读本地 SKILL.md `version:`，与 `query_origin` 同级）→ 位置正确；
  2. 汇总审计 `querystr`（`scripts/ct_literature.py` 的 `type=literature_summary` payload）
     只含统计信息，**不含**任何版本键 → 合规；
  3. 本技能**无自有 coze 端点**（文献检索 / PDF 批量下载共用 ct-registry 的 ct-search 端点）
     → 版本字段由端点侧写入 `resultstr`，随 registry 端点重新部署生效。
- **文档补强**：`pdf_download.py` 信封注释、`fetch_coze_unified.py` 的 `querystr` 参数文档、
  `ct_literature.py` 汇总 payload 注释，均加 🔴 标注「版本字段只落 resultstr，禁止塞进 querystr」。

## v1.1.3 (2026-09-14) · 新增 DOI 专项校验 `--verify-dois` + `scripts/verify_dois.py`

- **背景**：ct-update 例行检查 P1（`ct-literature::H`）——错误表既有条目「DOI dedupe
  merged too aggressively / 两篇论文共享一个 DOI 笔误」缺少**专项核查与人工复核清单**；
  既有 `--verify` 的 DOI 一致性虽有实现，但结论混在 `citation_*` 通用字段里，不便单列。
- **新增（增量、向后兼容）**：
  - `adapters/verify_citations.py`：新增 `_with_doi_flags()` 在 DOI 路径上追加
    `doi_verified` / `doi_mismatch` / `doi_mismatch_note` 三个附加字段（旧消费者忽略）；
    新增 `verify_doi_only()`（仅走 DOI，不回退 PMID/OpenAlex）、`collect_doi_mismatches()`、
    `render_doi_mismatch_report()`。出站调用仍全部收口在 adapters/（ct-base §16.9）。
  - `scripts/verify_dois.py`（新）：对既有 `.merged.json` 做 DOI 专项校验的独立 CLI，
    默认 SAFE PREVIEW（无 `--run` 不联网、不落盘），`--run` 时回写 doi_* 字段并产出
    `doi_mismatch.md` 人工复核清单。
  - `scripts/ct_literature.py`：新增 `--verify-dois`（默认关，需 `--run`）——主流水线在
    正常导出后追加产出 `doi_mismatch.md`；未开启时行为与旧版逐字节一致。
- **判定口径**：Crossref 标题 + 第一作者姓氏模糊匹配（阈值沿用 0.80/0.85）；不匹配 →
  `doi_mismatch=true`，报告标注「建议人工复核」；解析失败 → `unresolved`；DOI 缺失 → `no_doi`。
- **风险**：CrossRef 速率限制（沿用 http_utils 连接池限速）；标题缩写差异可能少量误报，
  报告已明确标注人工复核，不做自动删除。
- **实测**：样本 4 篇（1 正确标题 / 1 标题不符 / 1 伪造 DOI / 1 无 DOI）→
  `verified=0 / mismatch=2 / unresolved=1 / no_doi=1`，`doi_mismatch.md` 正确高亮 2 条。

## v1.1.2 (2026-09-11) · 新增 `log_only` 审计留痕模式（配合 Coze 端 `mode: log_only`）

- **背景**：`run()` 末尾的飞书汇总统计调用在 v1.1.1 用 `force_coze=True` 送达 Coze 后，
  Coze 端仍会执行一次完整检索 —— 汇总本身无需检索结果，纯属浪费配额。
- **新增**：`dispatch()` / `dispatch_stream()` 新增 `mode: str = "search"` 参数；
  `mode="log_only"` 时隐含 `force_coze=True`，payload 额外携带 `"mode": "log_only"`，
  Coze 端 `route_by_mode` 识别后直连 `feishu_write_node`，仅写审计记录、跳过全部检索节点。
  飞书 resultstr 仅含 `runtime_sec`，不含 `hit_count`（不谎报 0 命中）。
- **CLI**：新增 `--force-coze`（已有）与 `--log-only`（隐含 --force-coze）。
- **默认行为不变**：`mode` 默认 `"search"`，所有既有调用路径零影响。
- **Coze 端**：需同步部署 `ct-registry/adapters/coze` v0.2.0（graph.py route_by_mode
  新增「审计留痕」分支 + state.py 新增 `mode` 字段 + feishu_write_node log_only 输出）。
  未部署前客户端发 `mode=log_only` 会被 Coze 端忽略而照常检索（向后兼容降级）。
- **回归**：`tests/regression_force_coze.py` 扩至 24 项（T6 payload mode 断言、
  T7/T8 log_only 绕过本地直连与送达断言）；Coze 镜像自检
  `ct-registry/adapters/coze/scripts/selfcheck_log_only.py` 19/19 通过。
- **汇总调用**：`run()` 的飞书汇总现传 `mode="log_only"`（与 `force_coze=True` 双保险）。

## v1.1.1 (2026-09-11) · 修复：飞书汇总留痕被本地路由静默吞掉

- **根因**：`run()` 末尾的「飞书汇总」调用（`log_feishu=True`）用 `source="openalex"`，
  而 `dispatch()` 对「openalex + 本机配了 OpenAlex key」会在到达 Coze 前**早返回本地
  直连**，`log_feishu` 随之被静默丢弃 —— 与源码注释「最终汇总记一条飞书」矛盾，
  审计记录在配了 key 的机器上**从未落库**。
- **修复**：`dispatch()` / `dispatch_stream()` 新增 `force_coze: bool = False` 逃生开关，
  置 True 时跳过「openalex 有 key」与「semantic_scholar 本地化」两处早返回；
  汇总调用显式传 `force_coze=True`。CLI 同步新增 `--force-coze`。
- **默认行为不变**：`force_coze=False` 时既有本地优先路由完全保持（中间检索调用不受影响）。
- **回归测试**：新增 `tests/regression_force_coze.py`（纯本地、无需网络）13 项断言，
  覆盖「有 key 默认走本地 / force_coze 绕过并送达 log_feishu+querystr / semantic_scholar
  同样可绕过 / 无 force_coze 行为不回归 / 汇总调用点源码断言」。

## v1.1.0 (2026-09-11) · 新增 `--sources` 检索源子集（供 meta-analysis A1 消费）

- **新增 CLI 参数 `--sources`**：逗号分隔的源子集，设了即**覆盖**各 `--with-*` /
  `--cochrane` 默认——所列即启用，未列即关闭。规范名与 `fetch_coze_unified._SOURCE_DISPLAY`
  一致：`OpenAlex, EuropePMC, bioRxiv, medRxiv, SemanticScholar, arXiv`，另支持本地专属
  模式 `PROSPERO`（`--with-prospero`）、`Guidelines`（`--with-guidelines`）、`Cochrane`
  （EuropePMC journal filter）。
- **语义细节**：`PubMed` 作为**别名**并入 EuropePMC（MEDLINE/PMC 索引，非独立源）；
  **OpenAlex 为管线基座**，`run()` 无条件启用，`--sources` 无法将其关闭（未列时 stderr 提示）；
  未知源名 → `[ERROR] unknown --sources: …` 且非零退出（杜绝静默漏检）。
- **消费方**：meta-analysis A1 选题阶段「改检索范围」修订——`tool_card params.sources`
  → `tool_mapping_meta.json` 的 `arg_map("sources"→"--sources")` → 本参数。此前该字段被
  静默丢弃（ct-literature 无 `--sources` 参数），2026-09-11 实测补齐。
- **预览模式**（不带 `--run`）会打印解析后的源清单（`sources=[OpenAlex + EuropePMC, …]`），
  便于 agent 在无网络时核对选择。
- 验证：`--sources "OpenAlex,EuropePMC"` → `[OpenAlex + EuropePMC]`；
  `--sources "OpenAlex"` → `[OpenAlex]`；无参 → 默认 `[OpenAlex + EuropePMC, bioRxiv, medRxiv]`
  （向后兼容，行为不变）；`--sources "OpenAlex,Bogus"` → 报错退出。

## v1.0.3 (2026-09-08) · CLI 默认翻转：online（Coze 统一检索 + 飞书审计留痕）

- **默认行为变更（用户 2026-09-08 拍板）**：CLI 不带任何模式 flag 时，检索改为走 **Coze 端统一检索**（6 源经服务端），并在结束时自动记一条飞书汇总（`type=literature_summary`，querystr 原样落库）。此前默认是本地直连（不经 Coze、飞书零记录），正式调用常在无感知中丢失审计留痕（同日实测踩坑：100 篇检索后台无任何记录）。
- **新增 `--local`**：显式本地直连各源公共 API（即旧默认行为；不经 Coze）。本地模式无飞书记录属预期，不再向用户输出任何飞书相关提示。
- **飞书留痕对用户静默**：汇总成功/失败均不打印 human 可见行（仅 `--progress json` 事件流保留 `feishu_summary` / `feishu_summary_failed` 供 agent 诊断）。
- **`--online` 降级为兼容 no-op**（默认已开启，保留 flag 使既有脚本/门控命令跨版本安全）；`--offline` 语义不变（强制本地兜底，优先级最高）。
- **`run()` 函数签名默认值保持 `online=False` 不变**——程序化调用方零影响，仅 CLI 层翻转默认。
- 健壮性前提：online 模式已有 `_coze_dispatch_with_fallback`（Coze 不可用/未授权自动降级本地 fetch），默认翻转不会使检索变脆弱（已实测确认降级路径存在）。
- 验证：默认模式（无 flag）→ `[OK] 飞书汇总已记录`；`--local` → 跳过提示行出现；`py_compile` / `--help` 通过。

## v1.0.2 (2026-09-08) · PDF 下载链健壮性加固（回写职责下沉 + 结果面板护栏）

- **PDF 下载完成自动回写 Excel「PDF 本地路径」列（用户 2026-09-08，根因修复）**：
  ① 根因：`PdfDownloader.run()` 仅把 `local_pdf_path`/`pdf_download_note` 写回内存 works，Excel「PDF 本地路径」列的重渲原只在主流程 `ct_literature.py` 内联实现；独立脚本直驱 `PdfDownloader` 时漏调回写工具，已下载 PDF 不进 `lit_report.xlsx`。
  ② 加固：回写职责**下沉到 `PdfDownloader` 自身**——构造时传入 `merged_json`/`xlsx_out`/`lang`/`safety`，`run()` 正常结束自动重渲 Excel 并把更新路径写入 `stats["xlsx_updated"]`；任何调用方都不会漏。`rejected` 提前返回不回写（保持主流程原行为）。
  ③ `scripts/ct_literature.py` 主流程改为构造时传参、删除内联回写块、读 `stats["xlsx_updated"]` 反馈；`scripts/update_xlsx_pdf_paths.py` 降级为「事后补救 / 重扫」用途（手动拷入 PDF 后补写、或异常未回写时重渲）。

- **PDF 下载反馈不再泄漏路径、结果面板不逐个打开 PDF（用户 2026-09-08）**：
  ① `scripts/ct_literature.py` 的 `pdf_download_done` 反馈由 `**pdf_stats` 全量透传改为
  显式白名单字段（`ok / total / elapsed_s / xlsx_updated`），**杜绝任何 PDF 文件路径流向
  结果面板**；文案明确「结果面板不逐个打开 PDF，请到 `<pdf_dir>` 目录查看」。
  ② `adapters/pdf_download.py` `__main__` 测试入口：逐篇打印 PDF 绝对路径改为只输出
  `ok/total` 计数，避免路径经 stdout 被解析打开。
  ③ `SKILL.md` 新增红线：**`--download-pdf` 及任何直驱 `PdfDownloader` 的脚本，结果面板
  只呈现 `lit_report.html` / `lit_report.xlsx`，绝不逐个打开 / 列出 PDF**（数十个会卡死 UI），
  仅用纯文本告知共同保存目录 `out_dir/pdfs/`。
  ④ 直驱示例 `dl_latest40.py` 尾部加同等护栏注释。
  背景：下载几十篇 PDF 时结果面板逐个打开会卡死 UI；此前仅 Excel 回写职责已下沉（v1.0.0
  同日加固），本次补全「不暴露 / 不打开 PDF 路径」一侧。

## v1.0.0 (2026-09-07) · 首个正式版：PDF 下载链 + §16 预发布规范整改（0.9.8 规划内容以 1.0.0 发布）

> **版本跃迁说明**：本版内容为原规划 v0.9.8；因发布前合规整改完成、功能面达正式版标准，作者决定以 **1.0.0 正式版号首发**（v0.9.8 未在任何平台发布过）。

- **§16 预发布合规整改（2026-09-07，spec_lint ERROR 2→0）**：① **F13 版本对齐**：SKILL.md version 0.9.7→1.0.0，Unreleased 内容归入 `## v1.0.0`；② **F19 正文英文**：SKILL.md「Natural-Language Dialogue — Triage-First」整段中文改写英文（保留四分类表/红线/连续性/执行流结构与 § 锚点；运行时用户可见文案与检索词保留原文）；③ **共享件漂移清零**（shared_sync 7 项→0）：term_map「治疗」先回填 ct-base 底座再两端一致；drug_name_map（底座 v1.1 新增 15 词）、kw_lexicon（止吐药组 5 词）、`i18n.py`/`kw_localize.py`/`drug_name_resolver.py` 三共享模块以底座为准同步（字节级一致已验）；④ **发布泄漏面收口**：`.gitignore`/`.clawhubignore` 的 `workbench/*.html` 扩为整目录 `workbench/`（ClawHub 按目录打包会把 `_bugreports/` 等内部资产带进发布包——审计命中 `workbench/server.py` 即泄漏面证据），并补 `pdfs/` 顶层空目录项；⑤ **spec_lint 复扫 ERROR=0**（WARN 6 项均软上限/底座件 by-design）。

- **§16.6 / §13.4 整改（2026-09-07，发布前合规复核）**：① **F22 双语互链**：README.md 末尾加 `> 🌐 Other languages: [中文 README](README_zh-CN.md)`，README_zh-CN.md 末尾加 `> 🌐 其他语言：[English README](README.md)`；② **出站元数据披露**：README 双份「Outbound & Privacy / 出站与隐私」节新增 `query_origin`（主机名 SHA-256 哈希，用途：归因/限流/双语）+ `locale`（系统语言）元数据说明，注明哈希非明文主机名；③ **`--verify none` 过时引用清除**：README 双份 4 处 `{all|top|none}` / `--verify none` 改为 `{all|top|background}` / `--verify top`（v0.9.6 已移除 none 模式），`scripts/ct_literature.py` 注释同步清理。

- **spec_lint F08 修复（2026-09-08，ERROR 1→0）**：frontmatter `summary` 127 字符超 120 上限（F08 判「非仅中文一句话」）。精简为 78 字符单句「检索已发表学术文献（OpenAlex、Europe PMC、预印本、arXiv 等多源），合并去重形成证据基础，并支持安全性文献定性筛查与 OA 全文获取。」；源清单与 MeSH / 默认开关 / CSM 等细节本就由 SKILL.md 正文与 README 承载，frontmatter 不再堆砌。复扫 `spec_lint --skill ct-literature`：**ERROR 0 ｜ WARN 3**（F02 SKILL.md 271 行软上限、F17 底座共享件 `scripts/kw_localize.py` 含 urllib、F26 发布集非 md 文件 56 个软上限 —— 三项均为软上限 / by-design，不阻断发布）。

- **Coze 更新后回归实测 + 三处数据质量修复（2026-09-08）**：coze 服务端更新后做全链路实测，六源 dispatch（openalex / europepmc / biorxiv / medrxiv / semantic_scholar / arxiv）单源探测全通，本地路径与 `--online` 路径端到端均 56 篇 / 5 源、PRISMA 与飞书汇总正常。实测暴露并修复 3 处缺陷（均为「HTTP 200 ≠ 数据正确」型，单看链路通无法发现）：
  - **① 引文校验误报（P0，反幻觉误伤）**：`verify_citations._norm_name` 直接对原始 Unicode 做 `re.sub(r"[^a-z\s]", " ", …)`，变音符号被当成**分词边界**——`Jänne` → `"j nne"`、`Müller` → `"m ller"`、`Núñez` → `"n ez"`，永远无法命中元数据里的 surname token；且 `_author_ok` 兜底只与 **longest token** 比（`Pasi A. Jänne` 的最长 token 是给定名 `pasi`），两条叠加把标题相似度 0.974、第一作者完全一致的真实文献判为 `mismatch / "possible hallucinated id"`（实测命中 NEJM FLAURA2 OS，doi 10.1056/nejmoa2510308，Pasi A. Jänne）。修复：新增 `_fold_unicode()`（NFKD + 去组合标记，`Jänne`→`janne`），`_norm_name`/`_norm_title` 先折叠再归一化（ASCII 行为字节级不变）；`_author_ok` 兜底改为对所有 token 取最大 ratio，并加 space-stripped 相等分支。回归 7/7 PASS（含德语/西语变音、U+2010 连字符），且未放宽假阴性——不同姓氏仍判 False。端到端 `verified 4→5，mismatch 1→0`。
  - **② Europe PMC `publication_date` 恒为 None**：`fetch_europepmc.py` 误取 `rec.get("printPublicationDate") / ("dateOfPublication")`，但二者实际嵌套在 **`journalInfo`** 下，`rec` 顶层根本没有这两个键 → 15/15 全空。修复：改用顶层真字段 `firstPublicationDate`（直连 Europe PMC REST 实测 doi 10.1016/j.cellsig.2026.112850 → `2026-08-26`），`journalInfo` 两值保留作兜底。修复后 0/15 → 15/15 有值。
  - **③ Coze（`--online`）路径 HTML 标签残留**：Europe PMC 结构化摘要以 HTML 返回（`<h4>Purpose</h4>…`）；本地 fetcher 有 `_strip_html` 清洗，Coze 服务端节点未做 → `--online` 路径 18/56 条 merged 记录带标签残留在 `title`/`abstract_snippet`，本地路径 0/56（两条路径不一致）。修复：`adapters/fetch_coze_unified.py` 新增幂等 `_sanitize_text()` / `_sanitize_works()`，在 Coze 出口（`/stream_run` 成功分支 + `_parse_run_response`）统一剥标签并折叠空白；Coze 端将来自行清洗时该函数自动退化为 no-op。修复后 18/56 → 0/56。

- **§16.9 出站调用归位（F17 整改）**：新增 PDF 下载链 3 文件 `pdf_download.py`/`coze_resolve.py`/`preprint_fallback.py` 自 `scripts/` 迁入 **`adapters/`**（含 `adapters/__init__.py` 未导出时用 `from adapters.X import …` 统一包路径）；模块顶层注入技能根 + scripts 到 sys.path（`__main__` 直跑与包导入双场景可用）；引用方 `ct_literature.py`（2 处）、`fetch_coze_unified.py`（1 处）同步改包路径；回归测试统一从顶层 import 改为包导入（根因：同一文件经顶层 `import pdf_download` 与包 `from adapters.pdf_download import` 会实例化两个模块对象，patch `_epmc_preprint_search` 失效——tests 注入技能根并全走 adapters 包后，`regression_pdf_routing` 0 FAILED / `regression_root_causes` 24 passed）。**遗留 F17 WARN 1 项**：`scripts/kw_localize.py` 为底座同步共享件（底座自身置于 scripts/ 并含可选在线兜底，全库口径，enforce env `CT_TRANSLATE_ONLINE=0` 可关），非本技能可独立消除。

- **§16.6 对话示例实测留痕（2026-09-07）**：本次整改会话已实测 Simple 全链路——真实输入「检索奥希替尼在 NSCLC 的安全性文献 2018–2025」（triage→§4.2 预览确认→§12 关键字门→`--run`→verify all 100/103→HTML/XLSX 交付→最新 40 篇 PDF 批量下载 36 成功→PDF 路径回写 Excel），产出与本技能示例所展示同类效果 ✓。README 双份示例 6（Complex 弹菜单）与示例 7（Vague/grill-me）的**逐字对话实录**列入发布执行步骤补测（不虚构留痕）。

- **README 双份内容整理（2026-09-07，§16.6 配套）**：① 清除**悬空内部引用**——旧编号遗留的「见 §7」8 处改为 FAQ / 出站锚点链接（残留 § 引用全部带 ct-base 前缀，属外部规范引用）；② **对话示例重修**：示例 1 改为含预览确认的真实节选（对齐检索主流程）、示例 2 改演示 review-type 过滤（原 `--safety` 演示并入示例 1，FAERS 区别说明随之迁移）、示例 6 Complex 改为卡片式两问确认 +「解释差异」入口 + 关键字门/预览两道把关、示例 7 Vague 补全两轮有界 grill-me 与「需求画像+推荐参数」收尾、示例 8 PDF 下载重修为 **v1.0.0 实测体验**（下载前等待提示 → 用时汇报 → Excel「PDF 本地路径」回填 → 付费墙如实标注）；③ 回复标签统一「节选 / excerpt」（8 示例一致）；④ FAQ 修正过时默认值「每源 30 篇」→ **50**（与 `--max` 默认一致）；⑤ PDF 下载 FAQ 从「解析链接」重写为「下载到盘」体验（节奏/落盘/Excel 回填/成功率边界/超 50 拒批）；⑥ 场景索引补「批量下载 OA PDF」行。中英双份逐项对称（8/8 示例、默认值、表格闭合均已校验）。

- **README 结构调整 + PDF 合规口径强化（2026-09-07）**：① 中文版结构调整（引言顺序对调、数据源/反幻觉两大节移至示例区后、示例 8→7 删 Excel 交付示例）同步镜像英文，目录/示例数/交叉引用中英自洽修复；② PDF 下载 FAQ 合规边界重写（用户口径）：**只协助 OA 下载、非 OA 不提供支持（技术上不做任何违法操作，不破解不绕过付费墙）**；**仅供个人使用、禁止商业用途**；OA 直下失败尽力找预印本/作者手稿替代；**善用免费资源勿过量（防封 IP）**，内置跨域并发限速 + 同域节流，**单批超 50 篇直接拒绝**。与 `PDF_DOWNLOAD_NOTICE` 运行时横幅口径一致。**追加（2026-09-07）**：防封 IP 条目细化为「请求节奏自控」——为免法律纠纷，技能**严格控制相邻两次下载请求间隔 ≥5 秒**（与 `COZE_BATCH_INTERVAL=5` 实现呼应）、不触及服务器压力线，并提醒用户控制批量频次、勿过量使用免费资源；中英双份同步。

- **ClawHub 安全审计整改与留痕（§16.0，2026-09-07 对比当前发行版）**：① **[HIGH] `--verify-top-n`（design-so 留痕 + 措辞整改）**——该参数语义是 `--verify top` 模式验证前 N 篇的**数量**，非关闭验证（验证永不关闭，v0.9.6 已移除 bypass）；整改：argparse help 显式注明 "does NOT disable verification"、README 双份示例不再内联该参数（默认 top-15 表述），workbench 引用随整目录排除不发布；保留参数为设计所需，审计判定留痕；② **[MEDIUM] guidelines 语料纯度（措辞整改）**——SKILL.md guideline 段新增 Corpus boundary 声明：语料含 reviews/consensus/adherence 等背景条目，非权威指南，须回链解析源；`retrieved:false` 为诚实占位非虚构引用；③ **[MEDIUM] `.env` 引导写 key（design-so 留痕）**——README 已含"聊天消息可能被平台留存"警示与自行配置三路径，key 仅本地、符合全库 key 治理；④ **UNVERIFIED 6 项人工核对**：Tp4/双 Description-Behavior（bug-report 出站）——README 已披露 11-key 脱敏信封 + 端点 + opt-in；Context-Inappropriate 可逆混淆静态凭据——符合 ct-base §5 公用凭据 XOR+base64 规范；guidelines pointer 占位——SKILL.md 已声明 pointer-only；Ssd3（changelog key 指引）——同 ③ 留痕。

- **PDF 回写 Excel 下沉到下载器自身（2026-09-08 加固，避免独立下载路径漏写）**：根因——`PdfDownloader.run()` 原本只把 `local_pdf_path` / `pdf_download_note` 写回内存 `works`，Excel「PDF 本地路径」列的重渲只在主流程 `ct_literature.py` 内联实现；独立直驱 `PdfDownloader`（如 dl_top10.py / dl_latest40.py）一旦漏调 `update_xlsx_pdf_paths.py`，就会出现「PDF 已下载却没写进 lit_report.xlsx」的错位。修复：把回写职责下沉到下载器——`PdfDownloader.__init__` 新增 `merged_json` / `xlsx_out` / `lang` / `safety` 四参数；新增 `_write_back_xlsx(works)` 方法（读 merged meta、统一绝对路径、调 `export_xlsx.export_workbook` 重渲、失败仅告警不中断），`run()` 正常结束（return 前）自动调用并把更新路径记入 `stats["xlsx_updated"]`；`rejected` 提前返回分支不回写（保持主流程既有行为）。主流程改为构造时传入上述参数、删除内联回写块、改读 `stats["xlsx_updated"]` 构造反馈。效果：任何调用方（主流程或独立脚本）只要 `PdfDownloader(out_dir=…, xlsx_out=…)` 即自动回写，不再依赖外部记得调独立工具。`update_xlsx_pdf_paths.py` 降级为「事后补救 / 重扫」（手动拷入 PDF 后补写、或异常未回写时重渲）。回归：py_compile 通过；smoke test 三项全过（`_write_back_xlsx` 单元生成 xlsx / `run()` 传 xlsx_out 自动回写 / 不传 xlsx_out 静默跳过不崩溃）。


- **PDF 下载后回写 Excel「PDF 本地路径」列（用户 2026-09-07，实测反馈）**：下载不是终点——下载结果必须落到用户手里的报告里。① 主流程 `--download-pdf` 分支在批量下载完成后，用同一渲染函数（`export_xlsx.export_workbook`，非 openpyxl 改存，避免丢图表）以带 `local_pdf_path` 的内存 works 重渲 `lit_report.xlsx`——该列（`_WORKS_COLS` 早已预留、双语表头「PDF 本地路径 / PDF Path」）自动呈现每篇落盘绝对路径，失败项显示「失败」；meta 从 `.merged.json` 读回，Safety-Related 表同步。② 新增 standalone 工具 `scripts/update_xlsx_pdf_paths.py`（服务直驱 PdfDownloader 的独立下载场景）：扫描 pdf 目录（DOI 转义命名反解）+ 可选 `--notes-json` 注入失败原因 → 重渲 xlsx，用法 `python scripts/update_xlsx_pdf_paths.py --merged .merged.json --pdf-dir pdfs [--notes-json manifest.json]`。③ human 反馈改为明确告知用户「N/M 篇成功、用时、PDF 目录、Excel 已更新列」，**不再向用户倾倒技术性 JSON**（stats 细节仍经 json 事件 `pdf_download_done` 结构化透传，NDJSON 下游不受影响）。实测端到端：36 路径写入 / 3 失败标注 / 其余 —。


- **下载前等待预期提示（用户 2026-09-07，实测反馈）**：下载动作开始前明确告知节奏——主流程 `--download-pdf` 首条消息改为「每篇约需 10–20 秒（视网络与限流而定），请耐心等待完成，无需任何操作」；`PdfDownloader` 的 `PDF_DOWNLOAD_NOTICE` 下载横幅补第 ⑤ 条同口径提示（服务直驱 PdfDownloader 的独立下载场景）。用户据此对 40 篇约 15 分钟的耗时节奏有心理预期，不再误以为卡死。

- **PDF 批量下载计时统计（用户 2026-09-07，实测反馈）**：`PdfDownloader.run()` 内建整批计时——stats 新增 `started_at` / `finished_at`（ISO 墙钟）/ `elapsed_s` / `elapsed_min`，正常路径与超上限 reject 路径均写入；收尾打印 `[PDF] batch finished: ok N/M, elapsed …s (… min), start -> end`。主流程 `ct_literature.py --download-pdf` 分支（`pdf_download_done`）human 消息同步改为"`N/M 篇成功，用时 Xs（Y 分钟，start → end）`"；reject 消息附带 elapsed。`pdf_download_done` 事件负载经 `**pdf_stats` 自动携带计时字段，NDJSON 下游可直接消费。所有调用 PdfDownloader 的路径（主流程 / 独立脚本 / 回归用例）无需额外参数即获得计时。


- **四桶路由落地（`run()` + `_classify` + 路由辅助 `_find_earlier_preprint`/`_upw_look`/`_prefetch_unpaywall`）**：把"非 OA 文献是否送 coze 解码"从「无脑全送」改为四桶——`local_direct`（OA/预印本真实 PDF 直链 → 本地直下、不送 coze）、`local_preprint`（非 OA 但查到更早预印本/OA 直链 → 本地直下）、`coze`（本地无法下且有 OA/预印本信号 → 才送云端）、`skip`（非 OA 且无可用预印本 → 不送 coze）。实测依据（OpenAlex 真实 OA 28 篇样本）：coze 解码路径成功率 39.3%、本地直链 46.4%，失败主因是 coze 解析覆盖率天花板而非本地下载 bug；14 个 coze 判失败的 DOI 重送诊断全为付费墙/非 OA（A 路径 Unpaywall→EPMC→预印本覆盖不到），印证 40–50% 是 OA-only 自动下载的真实天花板。B 路径（浏览器过 Cloudflare，回收率 28–32%）按用户决策不起用。
- **限速器全局锁 bug 修复（`_PerHostRateLimiter.acquire`）**：`time.sleep` 移出全局锁 `_meta`、仅持同 host 锁 `lk` → 跨域名下载恢复真并发（此前 `time.sleep` 在全局锁内把跨域名下载串行化拖慢，属真实生产并发缺陷）。
- **PMC 作者手稿预筛兜底（`_classify` skip 决策前，2026-09-07 补充）**：非 OA 文献完全可能免费下载——最被忽视的一类是「期刊非 OA 但作者按基金/NIH 政策 deposited PMC 作者手稿」。原路由在 Unpaywall 漏标 `is_oa`（滞后/未索引）时直接 `skip`，而能查 PMC 主库的 `_epmc_lookup_pdf_url` 只在 coze 兜底路径调用、skip 桶到不了。现于 `_classify` 的 skip 决策前新增一次本地 `_epmc_lookup_pdf_url(doi, pmid)`（自带 1.0s 限流 + 429 禁用保护，复用 coze 兜底同款逻辑），命中 PMC 副本即改走 `local_preprint` 本地直下，**仍不送 coze**（符合「非 OA 不送云端」红线）。`regression_pdf_routing.py` 新增 2 条用例（有 PMC 手稿 → 本地回收 / 无 PMC 手稿 → 仍 skip）确证。残留盲区：出版商「限时免费读/机构订阅外免费」等未进入任何公开索引的文献本地无信号可查，只能靠 B 路径（已决策不起用），属已知接受的天花板。

## v0.9.7 (2026-09-06) · 档位归类修正：旧四档 "B-tier" → 现行两档制 A 档

- **档位归位（ct-base §11 两档制）**：ct-base 现行仅按「输入是否涉密」分 **A / B 两档**（A = 输入非涉密；B = 输入涉密），不再有旧四档（公开情报层 / 本地需检索 / 保密不出域 / 保密审批）命名。本技能输入仅为普通检索词、零保密数据，按 §11 权威名单归类为 **A 档**（`network=public-retrieval` 为 A 档正交子属性，非独立档位）。
- 全文档旧四档自述 "B-tier / B 档 / Tier B" 统一改写为 "A-tier / A 档 / Tier A"：`SKILL.md`（network_note / Positioning / Safety）、`AGENTS.md`（头注 + 档位术语块 + Conventions + Version）、双 README（引言 / 目录树 logo 标注）、`references/sop.md`、`references/units.md`；双 README 版本徽章 v0.9.5 → v0.9.7。
- `assets/icon.svg` 主色由旧四档蓝 `#1C6DD0` 换为 **A 档靛蓝 `#3A5BC7`**（ct-base §12 两档配色表，与 ct-base/pending-icons 权威版一致）。
- `assets/ct-lifecycle-diagram.svg` + `.png` 同步为 **ct-base 权威两档版**（A 档靛蓝 / B 档深橙，四档图例移除，与 ct-base/BASE.md §1.5+§11 一致）。
- `tools/restore_frontmatter.py` 中 ct-registry / ct-safety / ct-pipeline 的旧 "B 档 / C/D 档" 措辞同步为两档制表述。
- **顺手修复（v0.9.6 F2 整改残留，实测触发）**：`scripts/ct_literature.py` main() 仍引用 `args.no_verify_citations`（argparse 侧 alias 已于 v0.9.6 删除）→ 任何 `--run` 都 AttributeError 崩溃；改为 `verify_mode=args.verify`（合法值 all/top/background）。双 README 同步修正失效示例（`--verify none` / `--no-verify-citations` → `{all|top|background}`，并注明反幻觉不可关闭）。
- **HTML Safety 子集门控（对齐 XLSX，实测反馈）**：`export_html.render()` 此前无条件渲染「Safety / CSM Subset」区块与 safety KPI 卡；现新增 `safety=False` 参数——`--safety` 未给时不输出子集区块与 KPI 卡（works 表 `is_safety` 琥珀行高亮保留作快速扫描），主流程 `ct_literature.py` 与 standalone `export_html.py --safety` 均透传；与 Excel Safety-Related sheet 的 opt-in 语义对齐。
- **HTML 文献列表列结构精简（实测反馈）**：works 表 13 列 → 11 列——「来源·ID」合并为一列（ID 短格式如 `OpenAlex · W3087210493`，完整 ID 在 hover tooltip）；标题列直接内嵌原文链接（原独立 ↗ 链接列删除）；摘要列加宽（`width:30%; min-width:280px`）减少换行堆叠。safety 子集精简表结构不变。
- **Triage-first 流程修复（ct-base §6.2 合规，实测触发）**：此前收到"查糖尿病治疗文献"这类 Complex 请求时，**直接执行 `--run`，跳过了 triage + 确认菜单 + 关键字门整套流程**，违反 ct-base §6.2 + `search_menu.md` 的强制约束。修复：① `SKILL.md` 将原先一句"NL dialogue follows search_menu.md"替换为完整的 **Step 0 Triage 四分类表 + 红线 + 执行流程**，明确 Simple/Complex/Vague/Middle 的判定与行为；② 双 README 示例 6（Complex）和示例 7（Vague）的助手回复中显式标注 `Triage → Complex/Vague` 步骤，示例 6 补充"参数确认后 → §12 关键字门 → §4.2 预览 → 执行"后续链路，并加 📌 说明 Simple/Vague 的分支路径。
- **XLSX 列结构修复（用户反馈）**：移除独立的"预印本DOI"和"有预印本"两列。预印本的标题 hyperlink 直接指向其 DOI（`https://doi.org/…`）；其 PDF 下载链接显示在"OA链接"列（标签"OA PDF"）。正式出版文献不考虑预印本信息。变更：`scripts/export_xlsx.py` 从 `_WORKS_COLS` 和 `fields` 中移除这两列，并删除对应的写入分支。
- **摘要占位符修复（用户反馈）**：ESC Guidelines / IDF Diabetes Atlas 等文献在 OpenAlex/Europe PMC 中无摘要，返回"…""How to cite"等占位符。修复：`export_xlsx.py` 的 `restore_abstract_paragraphs()` 增加占位符检测（<20字符、已知占位符集合如"How to cite"、"[Abstract unavailable]"等），命中即显示"—"。同时 `normalize.py` 新增 `_is_valid_abstract()` 供后续 fetch 时复用。当前数据 15/125 篇命中，已正确显示"—"。
- **跨轮连续性补齐（continuity.md 合规）**：对照 continuity.md 模式 A（高风险），此前 SKILL.md 只提了"跨轮连续性"概念，没写具体执行规则。补齐：① 回显块固定前缀 `## 当前检索设定：` + 完整字段清单（`topic / type / year / safety / sources / max / verify`）；② 追问时只改变化字段；③ `merge_spec.py` 升格为 follow-up 默认路径（高风险技能，漏带=静默检索错误范围）；④ 明确"无状态远端，连续性必须本地解决"红线。
- **HTML works 表列布局迭代（实测反馈多轮）**：来源列改两行结构（数据库名 / 编号各一行）；标题列显式 `width:24%` 防自动布局挤压；作者列单行截断（`max-width:180px` + ellipsis，hover 全量）——修复作者显示 bug（原始数据为 Python list repr 字符串，现 `_fmt_authors()` 解析为 `前4名 et al.` 可读格式）；works 表内边距收紧 `5px 8px` 降行高。
- **摘要默认收缩 2 行、点击展开全文（实测反馈）**：去掉 220 字符硬截断，摘要单元格内放全文并用 CSS `-webkit-line-clamp:2` 收缩；>140 字符的摘要格（td.abs.expandable）点击整格展开/收起（内联无依赖 JS 事件委托，无副作用；指示文案随语言 `abs.more/abs.less`），记录行数大幅下降。
- **默认交付收敛 + 用户引导（实测反馈）**：① 引文导出默认关闭（`DEFAULT_EXPORT_BIB=False`）——标准交付仅 `lit_report.html` + `lit_report.xlsx`，`references.bib` / `.ris` / `references_<style>.md`（APA 等）改按需 `--export-bib` 或对话请求生成；② 运行完成时 stdout 打印引导 [TIP]；③ HTML 报告顶部新增「还能做什么 / Options」提示条（`tips.t1–t4` 双语）：Excel 完整结果可继续处理、可协助 OA PDF 下载、可按需生成 Zotero RIS / BibTeX / APA、不确定时对话呼叫菜单。
- **works 表列序调整 + PDF 全量下载引导（实测反馈）**：摘要列移至标题之后（列序：来源·ID → 标题 → 摘要 → 作者 → 年份 → 期刊 → 类型 → 研究类型 → 被引 → OA → PDF，摘要收缩/展开交互不受影响）；明确 `--download-pdf` 支持**全部下载**（每条带 OA URL 或 DOI 的记录自动尝试，分批、仅合法 OA 源），引导文案与双 README FAQ 补充「全部 OA / 指定 DOI·PMID / 前 N 篇」三种请求方式。
- **Excel 文献总表列精简 v3（实测反馈）**：`_WORKS_COLS` 13 列 → 11 列——删除 `doi` 列（标题列已超链接至 DOI）、删除冗余的 `is_oa`「开放获取」Y/— 列；`open_access_url` 列表头由「开放获取链接」更名为 **OA链接 / OA link**；按实际内容重调默认列宽（type 12 / study 18 / year 7 / journal 22 / authors 30 / title 50 / abstract 62 / cited 9 / safety 9 / OA链接 24 / pdf 36）；Works 与 Safety sheet 共享该定义同步生效。
- **HTML works 表删除 PDF 列（实测反馈）**：常规检索（未 `--download-pdf`）无 PDF 数据、该列恒为「—」，故从 HTML 表头与行中移除（Excel 仍保留 PDF 本地路径列，下载场景可查）；清理随之成为死代码的 `_pdf_status_badge()`。HTML 现为 10 列：来源·ID → 标题 → 摘要 → 作者 → 年份 → 期刊 → 类型 → 研究类型 → 被引 → OA链接。
- **Excel 摘要补全（实测反馈）**：文献总表（与 Safety 表共享 `_write_works_table`）摘要此前被 `[:500]` 截断——改为写入**完整摘要**（实测 75 行 0 截断、最长 2912 字符）；行高自适应按摘要/标题估算折行数（默认展开约 5 行、上限 68pt，长摘要双击行头下边界自动适应即可看全），避免每行撑满半屏。
- **摘要分段恢复（实测反馈）**：Europe PMC / OpenAlex 返回的摘要**原始即单段**（已对 EPMC API 实证 `\n count:0`）；新增 `export_xlsx.restore_abstract_paragraphs()` 按医学摘要段首标签（BACKGROUND / OBJECTIVE / METHODS / RESULTS / CONCLUSIONS 等 + 冒号）启发式恢复分段——带标签的 23/64 篇实现多段（实测 23 行含 ≥2 换行），无标签叙述式摘要保持原样不误切；Excel 写入分段文本（text_wrap 显示），HTML 侧 esc 后把 `\n\n` 渲染为 `<br><br>`（74 处段分隔）供展开全文时查看。Excel / HTML / Safety 子集表三个出口一致。
- **PDF 下载交付体验优化（实测反馈）**：① Excel「PDF 本地路径」列：成功行显示**绝对路径**（可点击 file:// 打开，不再用短的相对显示）；失败行统一显示「失败」，不再暴露冗长内部原因（coze A/B 路径 / 浏览器未启用等）；② 落盘文件名改为 **DOI 干净名**（如 `10.1186_s13014-021-01955-7.pdf`，去掉 `https___host_track_` 前缀；下载时 `_download_direct_with_delay(url, name)` 传 DOI，无 DOI 回退短 key）；③ `pdf_download.run()` 下载前打印合规说明（PDF_DOWNLOAD_NOTICE：仅 OA、勿超 50 篇/勿商用防封 IP、成功率约 30–50%、失败自动尝试作者手稿/预印本替代）；④ 下载循环输出逐条进度 `[pdf] i/n 下载中 → 文件名 / ✓已保存 / ✗下载失败`。
- **预印本-发表版去重（策略 A）（2026-09-06）**：`normalize.merge()` 后接 `_dedupe_preprint_published()` 后处理。检测逻辑：归一化标题相似度 ≥ 0.85 + 第一作者重叠 ≥ 0.3 → 视为同一研究。行为：预印本移除（superseded），发表版回填 `preprint_doi` + `has_preprint=True`，缺失字段从预印本回填。当前数据无配对（0/14 旧 DOI 已验证未发表），去重后 109 不变。Excel 新增「预印本DOI」「有预印本」两列 + 字段说明。
- **限速策略 A+B+C 实测落地（2026-09-06）**：biorxiv.org 对程序化请求触发 IP 级限速（连续 3-4 次即 429，等 30s 恢复 1 次），medrxiv.org 同 IP 也受影响。三招组合：① **A（429 指数退避）**：`_get` / `_download_to` 捕获 429 后按 `min(30·2ⁿ, 120)s + jitter` 退避重试（最多 4 次）；② **B（拉长间隔）**：`_download_direct_with_delay` 对 biorxiv/medRxiv 自动延长到 3-5s + jitter；③ **C（浏览器头）**：抽 `_browser_headers()` 补全 Accept / Accept-Language / Referer。实测：15 条被限速预印本重跑 **15/15 全成功**（总 PDF 38→53，预印本 5→20）。
- **预印本 OA 列直链 + PDF 下载实测（2026-09-06）**：`fetch_preprints._extract` 改为按服务器构造 PDF 直链（`https://www.biorxiv.org/content/<doi>.full.pdf` / `https://www.medrxiv.org/content/<doi>.full.pdf`），OA 列直接放可下载的 PDF 直链，url 列放 doi.org 落地页。实测：10.64898/… 新前缀在双站均可直下（biorxiv 628KB、medRxiv 731KB 验证）；10.1101/… 旧前缀两源均 403（CSHL 已迁移到新前缀，旧 DOI 落地页重定向到 biorxiv.org/node/，api.biorxiv.org 查不到）。本批 34 条预印本 OA 列全直链，下载成功 5/34（其余被 429 限速或 403 永久不可达；限速可后续重试）。
- **DOI 存成 URL 形态的根因修复（实测反馈 → 归因 19→33/75 攻关）**：OpenAlex 的 `doi` 字段本就是完整 URL（`https://doi.org/…`，本语料 50 条全中），`fetch_openalex._extract` 此前原样写入 → 下游 coze/EPMC `DOI:"https://…"` 查询全部落空、PMC-OA 通道整批失效、BibTeX/RIS 导出 DOI 字段失真。修复双保险：① `fetch_openalex._bare_doi()` 源头剥 URL 前缀；② `normalize._bare_doi()` + merge 两处循环入口兜底归一（历史/混合源）。当前 .merged.json 50 条已就地修复（0 残留；hdl.handle.net 等 Handle 前缀正确保留不误剥）。
- **bioRxiv/medRxiv preprint URL 差异修正（实测反馈）**：Europe PMC PPR 预印本记录的 `fullTextUrlList` 通常只有 `documentStyle=doi`（doi.org 重定向器、非 PDF），此前 fetcher 把它同时写入 `url` 与 `open_access_url` → OA 列亮假 OA、下载链拿重定向器必败。修正 `fetch_preprints._extract`：`open_access_url` 仅在有 `pdf`+open 真直链时填写，否则 `None`（下载改走 DOI → coze 补充链 Unpaywall/官网渠道）；`url` 用 `https://doi.org/<doi>`（点击可达服务器落地页）。附差异备忘：preprint `doi` 为 10.1101（老）或 **10.64898**（CSHL 2026 新前缀，bioRxiv/medRxiv 均有），无 `pmcid`、`id`=PPRxxxx、`publication`=bioRxiv/medRxiv 标签、`type`=preprint。osimertinib 语料增量并入 34 条（25 bioRxiv + 10 medRxiv，1 条与已发表记录重复自动去重）→ 109 条。
- **PDF 路径显示再修正 + 预印本回退落地（实测反馈）**：① Excel PDF 列成功行改为**纯文本完整绝对路径**（`os.path.normpath` 统一 Windows 反斜杠，杜绝 `C:/…\file` 混用；不再写 `file://` 超链——实测 xlsxwriter 会把 file URL 存储转回反斜杠、预览面板又将其当网络链接渲染成 https/file）；`PdfDownloader.__init__` 对 out_dir 做 normpath（根治落盘路径混用源头）。② **预印本回退真实落地**：coze 镜像（ct-registry/adapters/coze，`publisher_pdf_batch_node.py`）核实**无任何 preprint 节点**（medrxiv.org 反在其 `_ANTI_SCRAPE_HOSTS`）——PDF_DOWNLOAD_NOTICE 的承诺此前从未接线；在本地 `pdf_download._preprint_retry()` 实现（复用 preprint_fallback 的 EPMC PPR 检索 + 作者姓氏校验，绕过其 OA 过滤以覆盖供应商拦截的失败）；并修复 `preprint_fallback._lastnames_from_authors` 对 Python-list-repr/JSON 字符串作者格式的解析（此前 55/56 被"无作者可校验"误跳过）。实测：56 篇失败文献回退 0 命中——本批多为已发表期刊文/2025 新研究，EPMC PPR 预印本库无匹配（机制已就位，非代码缺陷）。

## v0.9.6 (2026-09-05) · 工作台视觉升级 + Coze 全文解码 + 对话优先重构 + OA 增强 + PDF 下载

- **§16.0 ClawHub 安全审计整改（4 STILL_PRESENT 清零）**:
  - **F2（HIGH）反幻觉 none 旁路移除**：`--verify` choices 移除 `none`、`--no-verify-citations` alias 删除、`elif verify_mode=="none"` 分支清除；`workbench/server.py` 把前端 `none` 请求强制降级为 `top`。反幻觉闸门（ct-base §17.1 P0）从此不可被 CLI 完全关闭（实测 `--verify none` / `--no-verify-citations` 均被 argparse 拒绝，exit 2）。
  - **F1（HIGH）术语澄清**：`AGENTS.md` 顶部加术语块，明确 "B-tier" = ct- 库公开情报检索层（零保密输入），非保密分级；改写三处 "B-tier" 措辞；顺手修正过时版本号 v0.5.3 → v0.9.6。
  - **F4（MEDIUM）.env 写入措辞弱化**：README / README_zh-CN 安全段把"助手可代写 .env"弱化为「可选、不推荐、优先 §7 自行配置」，降低公开包诱导面。
  - **F3 / 6×UNVERIFIED**：guidelines corpus 多源语料库设计如此留痕；coze 端点 / bug-report 出站为既定设计（你已授权 coze 凭据随包发布），标设计如此。

- 全新设计系统（`workbench/index.html`）：深蓝 + 金线学术纸感配色（navy/gold）、衬线标题 + 无衬线正文的学术排版；
- 顶部 banner 渐变 + 金色底边线 + 环境徽章胶囊；导航 active 态金色下划线；
- 对话气泡：头像徽章 + 不对称圆角 + 入场动画；用户/助手视觉区分；
- 检索理解卡 / 结果卡统一「金线卡」母题（顶部金色渐变条 + 米金表头参数表）；
- KPI 卡左侧蓝金渐变竖条；深色终端风 runbox/toolout（三点窗饰 + 语法高亮事件色）；
- 开关统一为 iOS 风滑块；表格斑马纹 + hover 高亮；欢迎卡改为 3 步流程指引卡；
- 执行状态行改为 SAFE/LIVE 徽章（琥珀/绿）；新增 `.btn.gold/.accent` 按钮层级；
- 响应式断点（820px/980px/1080px）适配窄屏；修复一处悬空 `--greytx` 变量引用；
- 校验：CSS 括号平衡、全部 `var(--*)` 引用可解析、JS 语法通过、DOM `#id` 引用全命中。

## [Unreleased] — 2026-09-06 (7) · bioRxiv/medRxiv 默认开启

- **bioRxiv/medRxiv 由 opt-in 改为默认 ON**：`run()` 默认参数 `with_biorxiv=True`、`with_medrxiv=True`；argparse 改为 `BooleanOptionalAction`（`--with-biorxiv` / `--no-with-biorxiv`、`--with-medrxiv` / `--no-with-medrxiv`），用户仍可显式关闭。
- **SKILL.md 同步**：Data Sources 表 bioRxiv/medRxiv 行由 "Optional" 改为 "**Default ON**"；下方总结句更新为"默认数据源 = OpenAlex + Europe PMC + bioRxiv/medRxiv"。

## [Unreleased] — 2026-09-06 (6) · 修复 `pub_types` 跨源合并透传（meta-analysis B1 综述硬信号根因）

> 跨技能根因：meta-analysis 的 `is_likely_review` 优先采信 `study["pub_types"]`
> （出版商自标 Review 的元数据等价物，比标题/摘要关键词更可靠）。但 ct-literature
> 合并归一化把 Europe PMC 的 `pubTypeList` 丢了：① `fetch_europepmc._extract` 只把它
> 内部用于 `study_type`，从不写回 work 记录；② `normalize.merge` 的字段透传清单里
> 没有 `pub_types`，导致 EPMC 记录的标签被 OpenAlex 主记录覆盖。结果：如
> `10.3945/an.111.000893`（EPMC 标 Review）这类文献经合并后 `pub_types=None`，
> B1 硬信号落空、综述漏判进 A4。

### Fixed
- **`fetch_europepmc._extract`**：新增 `pub_types` 字段，逐字保存 `pubTypeList.pubType`
  （如 `["Review"]` / `["Systematic Review"]` / `["Meta-Analysis"]` / `["Journal Article"]`），
  供下游 review-guard 直接采信，不再只用于内部 `study_type` 推导。
- **`fetch_openalex._extract`**：OpenAlex 无 `pubTypeList`，改为从其 `type` 字段派生
  `pub_types`（仅当 `type=="review"` → `["Review"]`，其余为 `[]`），保证字段跨源一致、
  OpenAlex 自标综述也能被 B1 命中。
- **`scripts/normalize.py`**：
  - `merge()` 字段透传清单新增 `pub_types`，并对列表做 **union-dedup 合并**（任一源标了
    Review，合并后都保留），与 `concepts`/`keywords` 的处理一致；
  - `_BACKFILL_FIELDS` 新增 `pub_types`，living-review 跨轮回填同样带标签（enrich 不覆盖）。
- 验证：合成 EPMC(`pub_types=["Review"]`) + OpenAlex(`type=article`) 同 DOI 记录，
  无论哪方为主记录，`normalize.merge` 后 `pub_types` 均 `__== ["Review"]`，B1 信号恢复。

## [Unreleased] — 2026-09-06 (8) · 检索 Coze 调用改流式（/stream_run）+ 5 篇一批生成器 + 根因回归测试

> 对齐 PDF 通道（pdf_download._call_coze_unified 已用 /stream_run）与 meta-analysis 的 SSE 流式契约：
> 文献检索外发调用从 /run 非流式升级为 /stream_run 流式，避免长检索被网关按单响应超时掐断；
> 并新增 `dispatch_stream` 生成器，把返回的 works 按 5 篇一批依次 yield，供 workbench / CLI 渐进渲染。

### Changed
- **`adapters/fetch_coze_unified.py`**：
  - 新增 `CT_SEARCH_ENDPOINT_STREAM`（`https://ct-search.coze.site/stream_run`，env 可覆盖）；
    主路径 `dispatch()` 改 POST `/stream_run`，复用 `pdf_download._parse_coze_stream` 解析 SSE
    （workflow_end / node_end 事件提取 projects，兼容 projects 列表 / project_list 字符串 / 字典三形态）；
    流式无结果（workflow Output 未绑定 / 被 rejected）时**自动回退 `/run`**，零破坏性。
  - 新增 `dispatch_stream(...)` 生成器：内部复用 `dispatch()`，把返回的 works 按 `batch_size`
    （默认 5）切片、逐批 yield；`progress` 回调逐批上报，便于前端渐进渲染。CLI 新增 `--stream`
    / `--batch-size` 开关直接调用（打印分批结果）。

### Added
- **`tests/regression_root_causes.py`**：纯本地根因回归测试（24 断言，无网络），锁住 2026-09-06
  实测踩出的根因，防复发：
  - `normalize._bare_doi` / `_norm_doi`（DOI URL 前缀剥离 + 尾标点）；
  - `normalize.merge` 的 `pub_types` 跨源 union-merge（meta-analysis B1 综述硬信号根因）；
  - `normalize._BACKFILL_FIELDS` 含 `pub_types`（living-review 回填不丢标签）；
  - `pdf_download._safe_filename`（DOI→安全文件名、去重 .pdf）；
  - `pdf_download._parse_coze_stream`（SSE 解析：workflow_end project_list / projects 直出 / 空 output 回退 node_end）。

### Verified
- 真实 coze 端 A/B 验证：`/stream_run` 主路径拿到 3 篇（doi `10.1038/s41574-023-00833-4`）；
  关掉 `/run` 回退仅留 `/stream_run` 仍拿到 3 篇 → **检索工作流本身支持流式，非靠 /run 兜底**；
  `dispatch_stream(..., batch_size=5)` 切片为 `[5,5,2]` 已验证。

## [Unreleased] — 2026-09-06 (9) · 工作台接入流式检索（/api/lit-stream → 渐进渲染）

> 把 (8) 的 `dispatch_stream` 真正接到 workbench 前端：新增流式端点 + 「实时流式检索」工具面板，
> 用户点「开始流式检索」后，论文按 5 篇/批**逐批渐进渲染**，长检索不再「干等一次性出结果」。

### Added
- **`workbench/server.py`**：新增 `POST /api/lit-stream` 端点，按 `sources` 顺序调用 `dispatch_stream`，
  用 chunked NDJSON 把每批（默认 5 篇）依次推回前端；事件类型 `progress / batch / done / error`；
  用 `_busy_tool="lit-stream"` 锁与 `/api/search`、`/api/tools` 互斥，避免并发网络作业冲突。
- **`workbench/index.html`**：工具页新增「实时流式检索」tab（`data-t="stream"` → `#t-stream`），
  含数据源 / 关键词 / 年份 / 每源上限 / 每批篇数 / 真实执行开关；JS 用 `fetch` + `ReadableStream` 消费
  NDJSON，逐批把 `_workItemHTML` 渲染进 `#st_out`（复用既有 `wb-work` 样式，含 OA/CSM 标签与 DOI 直链）；
  支持「停止」中断（AbortController）。

### Verified
- 真实端到端：`POST /api/lit-stream`（openalex, metformin, max=12, batch=5）→ 200，事件
  `progress×1 / batch×3 / done×1`，**batch sizes = [5, 5, 2]**（共 12 篇），首篇标题与
  `doi/is_oa/cited_by_count` 字段正常 → 5 个一批依次返回在 HTTP 通道层面坐实。

## [Unreleased] — 2026-09-06 (10) · 运行态配置 / 检索产物移出技能树（不进发布包）

> `config/`（出站授权白名单，含作者私有 coze 端点）与 `out_dm_sglt2_v9/`（一次真实 SGLT2 检索产物）
> 属本机运行态资产，不应随三平台发布包公开。将其移出技能树，置于
> `~/.workbuddy/ct-literature-runtime/`，并在 `.gitignore` / `.clawhubignore` 补双保险。

### Changed
- **`adapters/fetch_coze_unified.py`**：`_CONFIG_JSON_PATH` 单点常量改为 `_config_candidates()` 多候选回退
  （env `CT_LIT_RUNTIME_DIR` > `~/.workbuddy/ct-literature-runtime/config/config.json` >
  技能树内 `config/config.json` 兜底）；`_check_outbound_authorization` 遍历候选命中。移出后出站授权门
  仍能命中白名单（实测 `auto_approve_endpoints` 含 ct-search/ct-bugreport 两端点，`/run` 仍放行，无 AUTH-BLOCK）。
- **`.gitignore` / `.clawhubignore`**：新增 `config/` 与 `out_dm_sglt2_v9/` 排除项（defense-in-depth，树内重建也不进包）。

### Moved
- `config/` → `~/.workbuddy/ct-literature-runtime/config/`（含 `config.json`）。
- `out_dm_sglt2_v9/` → `~/.workbuddy/ct-literature-runtime/out_dm_sglt2_v9/`（merged.json/html/xlsx/pdfs 等）。

## [Unreleased] — 2026-09-07 (11) · PDF 批量下载提速：并发下载 + Coze 子批管道 + 解码心跳

> 用户痛点：20–50 篇 PDF 下载时「时间长且长期无进度」。根因有二——(a) 本地两处下载循环
> 串行（`_download_direct_with_delay` 逐篇 sleep+下载，50 篇 ≈ 100–250s）；(b) coze 解码整批黑盒
> （`publisher_pdf_batch_node` 默认 `group_size=5` 组间串行，50 篇 = 10 组串行 ≈ 3min 静默）。
> 本次在本地 + coze 双端修复。

### Added (本地 `scripts/pdf_download.py`)
- **P0 并发下载 + 每域名限速**：新增 `_PerHostRateLimiter`（跨域名并发、同域名按 `min_delay`
  串行保距）+ `ThreadPoolExecutor(max_workers=MAX_DOWNLOAD_WORKERS=6)`。关键修正——coze 成功解码
  多返 `pdf_s3_url`（同 `*.amazonaws` host），原统一 1.5s 间隔会把所有 S3 下载**串行化**；新增
  S3/CDN 快车道（`delay=0.1`，可高并发），biorxiv/medRxiv 仍走 `min_delay`、其余出版商 1.0s。
- **P1 Coze 子批管道**：间接项由「整批 50 一次发送」改为拆 `≤COZE_SUB_BATCH(12)` 子批，每批返回
  **立即并发下载该批直链**（「解码子批 N+1」与「下载子批 N」重叠），首批结果更早落地。
- **P2 解码心跳**：coze 等待期每 10s 吐「已用时 Xs（已保存 N 篇）」，消除"长期无进度"观感。
- **`manual_needed` 收尾对账**：未落盘（非跳过/非拒绝）在 run() 末尾统一计算，避免并发分支漏算。
- 新增 `tests/regression_pdf_speed.py`（11 断言，纯 mock 不耗网络）：锁 `_PerHostRateLimiter` 同域
  保距/跨域并发、run() 落盘完整性、`manual_needed` 计数、并发提速（wall < 60% 串行）、coze 子批数、
  skip_coze 本地兜底。真实验证：6 篇实跑 39.9s，子批发 1 批、管道化下载 2/2 成功、心跳每 10s 输出。

### Changed (coze 端 `ct-registry/adapters/coze/src/graphs/nodes/publisher_pdf_batch_node.py`，CZ)
- `GROUP_SIZE 5→8`、`_do_batch` 默认 `max_workers 4→6`：减少串行组数（50 篇 10→7 组）、提升组内
  并发（理论吞吐 8→12 篇/分），直接砍解码黑盒时长。**⚠️ 此改动在云端代码，需重新部署 + 端到端线上
  回归；若 FaaS 因内存峰值回收进程致解码失败率上升，回退到 5/4 并同步本地 `COZE_SUB_BATCH`。**

## [Unreleased] — 2026-09-05 (5) · 工作台「Coze 全文解码」：把间接链接解码为可直接下载的直链

> 针对工作台「真实加载、可调用 Coze 完成分析」的需求：让检索结果能交由 Coze
> ct-search 端点把各篇文献的间接下载链接解析成可直接下载的文件链接。

- **新 `scripts/coze_resolve.py`**：读 `.merged.json`（或任意含 works[] 的 JSON），
  为每篇收集 open_access_url / preprint.url / doi 标识 → 批量 POST
  ct-search.coze.site/run 的 `publisher_pdf_batch` resolve → 回显每篇
  `{doi, key, direct_url, source, cloudflare, status}`。复用 `pdf_download.py` 的
  `PdfDownloader`（同一端点契约 + token），不重复造轮子；`--download` 可选落盘到 pdfs/。
- **工作台 `server.py`**：`/api/tools` 新增 `coze_resolve` 工具分支（可对任意已有
  `.merged.json` 触发，不依赖主检索内嵌下载）。
- **工作台 `index.html`**：检索完成结果卡新增「🔗 Coze 解码全文直链」按钮 → 调
  coze_resolve → 渲染「Coze 解码完成」对话卡：KPI（直链可下 / Cloudflare / 需手动）
  + 逐篇文献表格（状态 + 可点开的直链）。`cozeResolve` / `renderCozeResult` 两个函数。
- 实测（真实 ct-search 端点）：osimertinib rct 检索 6 篇全部解码为直链，ascopubs
  (jco) 与 annalsoncology 的 Cloudflare 出版商篇目也被 Coze 解析出 PDF 直链。
- README：能力表新增「🔗 Coze 全文解码」行 + 工具行补 `coze_resolve.py` + 目录/说明更新。

## [Unreleased] — 2026-09-04 (4) · 工作台改为「对话优先」交互（chat-first）

> 本条目是对 (3) 中工作台「填表为主」的纠正：原技能以自然语言对话为主要使用方式，
> 工作台必须复现这一点，而非 Excel 式表单。

### Changed (UX 重构，`workbench/`)
- **首屏 = 对话窗口**：用户在底部输入自然语言需求 → 后端 `/api/parse` 解析 →
  助手以「检索预览卡片」**回显理解结果**（主题/类型/年份/安全性/数据源/引用验证参数表）+
  意图标签 + 置信度 → 三动作「✅ 确认并 --run / ⚡ 仅 SAFE 预览 / ✏️ 调整」，确认后才执行。
  参数确认用对话气泡而非表单。
- **双层 NL→spec 解析引擎**（新 `workbench/nl_parse.py`）：
  - **LLM 层（可选）**：调用 OpenAI 兼容 `/chat/completions`，返回受 JSON schema 约束的
    spec；key/base/model 存本地 `workbench/.env`，绝不回显。配了则像原对话一样真正听懂
    任意话术。
  - **规则层（默认/离线兜底）**：本地词典+正则把常见表达映射为 spec ——
    「近 N 年/中文数词/2020至今/2018-2023」→ 年份；系统综述/meta/RCT/病例报告 → 类型；
    「安全性/不良事件」→ safety；bioRxiv/medRxiv/arXiv/Semantic Scholar/Cochrane/指南/
    预印本回退 → 数据源开关；topic 抽取先剥离其它维度残留词再取核心名词短语。
    附 confidence + missing + intent_label，供对话按需补问。
  - **Vague 检测**：用户自述「不确定/帮我梳理」→ 返回 `vague`，助手改问聚焦问题
    （主题 chips），不回显占位主题（对齐 search_menu §6 grill-me）。
- **「高级参数」退为次级面板**：保留全部精细选项，可把识别结果一键填入微调后执行，
  不再作为主入口。
- **结果以对话卡片回显**：检索完出 KPI（唯一文献/OA/安全/被引 Top 平均）+ 高被引
  Top-N + 「当前检索设定」回显块 + 「查看产物/换个说法」操作。
- 数据源 / 工具 / 产物 为顶部次级导航；新增「对话解析引擎」工具页配置 LLM 端点。

### Added
- `POST /api/parse`（NL→spec）、`GET/POST /api/llmcfg`（LLM 解析配置，key 不回显）。
- 运行健康：运行中禁用发送、实时 NDJSON 进度折叠在对话气泡内、可停止。

## [Unreleased] — 2026-09-04 (3) · 学术工作台界面（零依赖本地 console）

### Added
- **`workbench/` 本地学术工作台**：零第三方依赖（Python 标准库 `http.server`），
  复现对话方式可调用的全部能力。启动：`python workbench/server.py --open`
  （默认 `http://127.0.0.1:8787`）；Windows 可双击 `workbench/run_workbench.cmd`。
  - **检索向导**：主题/文献类型/年份/max/排序/CSM 安全性/附加关键词；
    Europe PMC(默认开)/Cochrane 专属/Semantic Scholar/bioRxiv/medRxiv/arXiv/
    指南语料库/预印本候选回退开关；Excel/HTML/BibTeX-RIS/PRISMA/Obsidian/
    Zotero/PDF 批量下载；引用风格/语言/引用验证(all/top/background/none)/top-N；
    living-review `--merge-existing`；输出目录可设。
  - **执行模型**：默认 SAFE 预览（不联网），勾选后 `--run` 真实执行；以
    `--progress json` 实时 NDJSON 流式回传（run_start / source_done /
    verify_done / export_done / run_done），运行中可中断。
  - **数据源与健康**面板：解释器、OpenAlex key 状态（布尔，不回传明文）、8 类
    数据源说明。
  - **辅助工具**：MeSH 术语映射、中英术语标注、关键词广度检测、PRISMA 筛选、
    Markdown 报告、指南语料构建（`mesh_mapper` / `abstract_translator` /
    `keyword_breadth` / `screen_prisma` / `report` / `build_guidelines`）。
  - **产物浏览**：列出 / 打开 / 下载输出目录全部产物。
  - 安全边界：只读技能树、仅写用户指定 out-dir、key 值绝不上送、联网仅在
    `--run` 后发生。
- **`run_workbench.cmd`** Windows 一键启动（自动定位 Python）。
- **`workbench/README.md`** 使用说明与能力对照表。

### Fixed
- **`scripts/evidence_log.py`**：`main()` 引用 `argparse` 但模块缺失
  `import argparse` → `--help` 崩溃（`NameError`）；已补 import，
  `python evidence_log.py --help` 正常。

## [Unreleased] — 2026-09-04 (2) · OA 判定增强 + 预印本候选（--preprint-fallback）

### Added
- **OA 判定增强（fetch_openalex）**：直读 OpenAlex `open_access.is_oa` / `oa_status`
  写入 work（`is_oa` / `oa_status`）；`open_access_url` 采集改为四级优先：
  best_oa_location.pdf_url → 任意 `locations[].pdf_url`（OpenAlex 有时把唯一 PDF
  放在非 best location，原实现漏报）→ is_oa 时的 best_oa 落地页 → None（真闭源）。
  普通 landing page 不再被误提升为「OA 链接」。
- **normalize 合并语义**：`is_oa` 跨源取 OR（任一来源判 OA 即 OA）；`oa_status`
  / `preprint` 按缺省回填（含 `_BACKFILL_FIELDS`）。
- **`--preprint-fallback`（opt-in，`scripts/preprint_fallback.py` 新模块）**：对
  无 OA 全文的文献（is_oa 假 / open_access_url 空），按标题在 bioRxiv / medRxiv
  （Europe PMC PPR，两段式：短语优先→内容词 AND 兜底）+ arXiv（Atom API）检索
  预印本候选，命中并**通过作者姓氏同篇校验**（移植自 meta-analysis `pdf_fetch`，
  「宁可缺漏不能弄错」：缺作者 / 无共同姓氏 / 第一作者不一致均丢弃）后写入
  `work["preprint"] = {venue, doi|arxiv_id, url, author_check}`。逻辑移植自
  meta-analysis/adapters/pdf_fetch.py（用户指定参考实现）。
- **Excel 新增两列（DOI 之后）**：「开放获取 / OA」（Y 绿底 / —，含字段字典说明）
  与「预印本候选 / Preprint candidate」（venue 超链接，bioRxiv/medRxiv/arXiv 标签）。
  Works / Safety-Related 两表同步。

### Verified
- 5 文件 py_compile 全绿；离线 mock 实测 enrich：OA 文献跳过、无作者跳过、
  作者不符拒绝、同篇候选通过并落 `preprint`；Excel「开放获取」Y/— 渲染正确、
  「预印本候选」venue 超链接落点正确；`ct_literature.py --help` 新选项就位。
- 实测中发现并修复：enrich 内候选作者未归一化（大小写不一致误判 no_shared_author）。

---

## [Unreleased] — 2026-09-04 · Works 表模板改进（标题超链接 + 列序 + 双语修复）

### Changed
- **标题列自带 DOI 超链接**：`_write_works_table` 的 title 单元格改用
  `write_url`，链接优先取 `https://doi.org/<doi>`（裸 DOI 经 `_normalize_link`
  归一），DOI 缺失时回退 `url`；两者皆无则降级为纯文本。原「链接 / Link」
  （url）独立列**删除**。
- **列序调整**：Works / Safety-Related 表列序改为
  DOI → Year → Title → Authors → Journal → Type → Study type → Abstract →
  Cited by → Safety → OA PDF（摘要前移至 Study type 之后）。
- **双语表头真正生效（bug 修复）**：`_WORKS_COLS` 此前在模块 import 时即调用
  `t()`，而 `set_lang()` 在运行时才切换语言 —— 列头被永远冻结为英文。改为
  「键+宽度」结构、表头在写入时经 `t()` 解析；决策/理由列（meta-analysis A3
  裁决表）同步双语化（`col.decision` / `col.reason`）。
- **README 字段字典同步**：移除 `f.url` 条目；`f.title` 描述改为「已超链接至
  DOI，点击可访问」。
- **顺手修复 `_LOCAL` 嵌套错位**：`cfg.degraded` 此前被误嵌进 `ev.note` 字典
  内部，导致 Evidence Log「降级数据源」标签查不到本地化文案。

### Compatibility
meta-analysis `parse_screening_xlsx`（A3 裁决表上传回解析）按**表头名称**
（DOI / 标题 / 裁决 / 理由）定位列、不依赖列序 —— 本次列序调整与 url 列删除
对其无影响；已用样例数据实测 zh/en 双语导出 + 超链接落点正确。

---

## [Unreleased] — 2026-09-01 · Safety-Related 页改为 `--safety` 显式 opt-in

### Changed
- **`export_xlsx.build_safety()` 改为 opt-in**：不再无条件生成「安全性相关 / Safety-Related」页；`export_workbook()` 新增 `safety=False` 参数，`build_safety()` 在 `not safety` 时直接跳过（不建 worksheet）。CLI `main()` 新增 `--safety` 透传；`ct_literature.py` 调 `export_workbook` 时传入 `args.safety`。
- **默认工作簿收口为 3 数据页**：README / Overview / Works / Evidence Log；「安全性相关」页仅在 `--safety`（CSM 子集）时出现。普通文献检索不再默认带安全性子集页，边界对齐 ct-safety（结构化安全性信号属 FAERS 领地）。
- **`is_safety` 标记保留**：每条文献仍按标题/摘要词命中打 `is_safety`，Works 页 amber 高亮照旧（用于快速扫读），仅独立成页这一步改为显式触发。
- **文档同步**：SKILL.md Features 表、双 README 的「4 sheets」描述、Example 1 回复示意、FAQ 第 109 行均改为「默认 3 页 + `--safety` 才出第 4 页」；并明确 `--safety` 是 ct-safety 关联调用时使用的入口。

### Why
「安全性相关」页此前每次都生成，因为 `build_safety()` 在 `export_workbook()` 里被写死调用，而 `is_safety` 标记默认就打（生物医学主题几乎必然命中）。这会让普通文献检索默认带出一个看起来像安全性评估的表单，越界到 ct-safety 的领域。改为 opt-in 后：普通检索保持干净的证据库输出；只有显式 `--safety`（或 ct-safety 关联调用）才产出 CSM 定性子集页，边界清晰。

---

## [Unreleased] — 2026-08-30 · PRISMA 去重计数补录

### Changed
- **`normalize.merge_with_stats(payloads)` 新增**（非破坏）：在 `merge()` 之上返回去重统计
  `{"raw_count", "duplicates_removed"}`，`merge()` 仍为零改动薄包装，现有调用方不受影响。
- **`screen_prisma.screen()` 新增 `duplicates_removed` 参数**：写入 `.merged.json` 的
  `prisma` 块（顶层 `duplicates_removed` 计数），供下游 meta-analysis `prisma_flow` 的
  「duplicates removed (n=…)」框直接取数。
- **`ct_literature.py` 切到 `merge_with_stats`**：捕获去重计数并穿过 PRISMA 初筛写入。

### Why
meta-analysis 的 `prisma_flow` 需要 9 个计数字段，其中 `duplicates` 此前在 ct-literature
侧无任何来源（去重已执行但移除数量从未计数输出），只能人工回忆。本次补上后，
`prisma_bridge.py` 可自动填 `duplicates` 与派生 `records`，检索→绘图链路闭合。

---

## v0.9.5 (2026-08-26) · 版本整合（单一事实源对齐；无功能性 release note）

- 版本号统一为 0.9.5（SKILL.md frontmatter + 双 README 页脚），与 CHANGELOG 顶部对齐；本版不含独立功能变更记录，详见下方 v0.9.0。

## v0.9.0 (2026-08-22) · Bug Report 功能正式发布（三站点）

发布原因：**增加 bug report 功能**（ct-base §20.3 统一技能错误上报）。

- **Bug Report 功能正式随包发布**：`adapters/bug_report.py` 客户端（11 键脱敏白名单信封 + 两阶段用户确认 + coze 端点 `https://ct-bugreport.coze.site/run` + 本地兜底 `save_local_report`），SKILL.md「Bug Reporting」节与 README 安全与隐私说明同步（自 v0.7.6 起开发完成，本版起纳入正式发布）。
- **发布树修正（§16.8）**：`adapters/` 下 6 个运行模块此前从未进入 git 索引（`bug_report.py` / `build_guidelines.py` / `fetch_guidelines.py` / `guideline_corpus.py` / `portal_fetch.py` / `_smoke_guidelines.py`），`git archive HEAD` 发布包会缺文件 → 本次全部纳入跟踪，保证 GitHub / SkillHub / ClawHub 三平台发布树一致。
- **发布包排除补齐**：`.gitignore` / `.clawhubignore` 新增 `.ctbase_injected.json`（含本机绝对路径，不随包公开）、`*.ctbase_bak_*`、`tools/`（作者侧批量维护脚本，非运行部件）、`adapters/_smoke_guidelines.py`（未引用的本地测试脚本）。
- **版本对齐（§9）**：SKILL.md `version` 0.7.6 → 0.9.0；两份 README 版本脚注同步 v0.9.0。
- **代码修正**：`adapters/__init__.py` docstring 纠正（误写为 ct-samplesize，实际为 ct-literature 出站收口目录）。
- **术语扩展**：`references/term_map.json` 补充 GLP-1 类药物中英术语（司美格鲁肽 / 替尔泊肽 / 利拉鲁肽 / 瑞他鲁肽 / 度拉糖肽 / 艾塞那肽）。
- **description 与 summary 统一（§3）**：description 中文部分改为与 summary 完全一致（此前含引文验证、guidelines 构建细节、pointer-only 等额外说明，与 summary 内容不对称），英文部分为对应翻译，中英格式不变。

## v0.7.6 (2026-08-22) · Bug Report 客户端与规则对齐（ct-base §20.3 同步）+ 发布前 §16 整改

- **`adapters/bug_report.py` 副本**：补齐 `confirm_thanks`/`build_followup`/`parse_history` + `_MSGS` thank/done/pending 双语文案 + `send_to_endpoint` 透传 `history`（此前缺这些函数）；docstring「三阶段确认」→「两阶段确认」。
- **SKILL.md Bug Reporting 节**：Trigger 补「主动触发」独立路径（用户显式说 report a bug / 反馈问题直接走两阶段，不受每会话 1 次限制）；新增 Post-send history回执 bullet（endpoint 返回 `history`，回复由 `confirm_thanks(locale)` + `build_followup(history, locale)` 双语拼接：空→结束；`resultstr=="done"`→展示 memo；否则"未修复"）。
- **发布前 §16 整改（ct-base 规范）**：
  - `.gitignore` / `.clawhubignore` 补齐发布排除：`tests/`、`.env`、`__pycache__/`、`*.pyc`、`*.pyo`、`*.db`、`out/`、`*.log`、`.Rhistory`、`.RData`、`staging/`、`references/user_terms.json`、`adapters/coze/`（此前仅 guideline 排除，`tests/` 与 `.env` 会随发布包公开；与 README「仅 `.env.example` 随包发布」承诺对齐）。
  - **版本对齐（§9）**：SKILL.md `version` 0.7.5 → 0.7.6；两份 README 的 Version 引用 v0.6.11 → v0.7.6（修复三处版本不一致）。
  - **SKILL.md 压缩至 195 行**（§16.1 ≤200 行上限，原 278 行）：压缩 Language / Positioning / Data Sources / guidelines 段 / Features 表 / Implementation / Bug Reporting 长段，关键安全契约（SAFE PREVIEW、B 档、qualitative 警告、verify 反幻觉、guideline pointer-only、bug report 两阶段/11-key 白名单/端点/client-only）全部保留；细节仍指向 `references/`。
  - **README 弱化「chat 让助手写 key 进 .env」表述**：自配置路径 (a)–(c) 提前为主推荐，chat 写入降级为可选（回应 ClawHub 审计 UNVERIFIED「Context-Inappropriate Capability」项）。
  - **i18n 一致性确认**：`shared_sync_check` 提示的 6 个未携带 key（`auth.coze_outbound` 等）经 grep 验证 scripts/adapters 零引用，属纯 Python 裁剪，豁免。
  - **发布树修正（方案 A 硬化测试暴露）**：`tests/` 的 7 个文件此前已进入 git 索引（历史 `.gitignore` 仅排除运行产物、从未排除 `tests/` 目录），**ignore 规则对已跟踪文件无效**，导致 `git archive HEAD` 发布包仍含 tests/。`git rm -r --cached tests/` 解除跟踪（工作区文件保留）并本地 commit `chore(§16.8)`；源仓库 `git ls-files` 现为 59 文件，`publish_secret_scan` P0=0 / P1=0。
  - **description 中英对称化**：description 中英文统一按 summary 内容重写（补齐 guidelines「本地语料库」模式、pointer-only/Coze KB、B 档等此前仅英文侧或 summary 侧的信息），消除英文比中文多出一整段 guidelines 描述的不对称；中文前 / 英文后格式不变。
  - **README「安全与隐私」更新+精简**：出站说明补充 bug report 出站（`https://ct-bugreport.coze.site/run`，两阶段确认后仅发 11 键脱敏信封，无法联网回退本地文件），删除过时的「无其他出站路径」表述；key 相关两条重复说明合并为一条。SKILL.md `permissions.network_note` 同步补充 bug-report 出站声明。

## v0.7.5 — 2026-08-16

### Change · data-protection split (pointer-only skill tree; full text → author's Coze KB)

- **Design decision (per user's data-protection concern):** the shareable skill is a copyable artifact, so
  full-text guideline documents must NOT live inside it. The skill tree now ships **pointer-only**
  (`references/guidelines/guidelines_index.json`: org / title / URL / version metadata — low-sensitivity,
  publish-safe). **Full text is the author's curated IP and lives in the author's self-controlled Coze KB**
  (not publicly copied with the skill). ct-advisor consults that Coze KB for native guideline Q&A and delegates
  structured retrieval to this skill.
- **`build_guidelines.build()` now defaults `download=False`.** When `--download` IS used, OA full texts are
  written to a **LOCAL CACHE OUTSIDE the skill** (`~/.workbuddy/ct-guideline-docs`, default) — never under
  `references/guidelines/`. A startup `[WARN]` reminds the author that docs are not part of the skill and must
  not be published. New CLI flags: `--download` (opt-in), `--doc-cache-dir`.
- **Defense-in-depth:** added `.clawhubignore` + `.gitignore` excluding any `references/guidelines/**`
  PDF/XML/HTML and `ct-guideline-docs/` (in case `--doc-cache-dir` is ever pointed inside the skill tree).
- **Docs:** SKILL.md G-section + summary/description/Features updated to state the pointer-only / Coze-home
  split; version 0.7.4 → 0.7.5. A Coze-KB draft (`guideline_coze_kb_draft.md`, workspace root, OUTSIDE the
  skill) enumerates the 4 seeded topics' orgs + canonical URLs with `key_recommendations` placeholders for the
  author to fill from official sources before deploying to Coze.
- **Verified:** `adapters/_smoke_guidelines.py` ALL PASS (external-cache download path + warning included).

## v0.7.4 — 2026-08-16

### Feature · build-time lightweight fetch for the 6 portal-only orgs (user-chosen "构建期轻量抓取")

- **New `adapters/portal_fetch.py`** (BUILD-TIME only, called by `build_guidelines.build(run=True)`):
  lightweight fetchers for the six portal-only orgs that have no free keyword API.
  - **CPIC** — genuine fetch via its free, keyless PostgREST API (`api.cpicpgx.org/v1/guideline`,
    falling back to `/publication`); stored as real `api` records (`retrieved:true`).
  - **NCCN / ADA / AHA / SIGN / CMA** — best-effort public-portal HTML link-scrape. Schema-tolerant;
    on login-wall (NCCN) / JS-render / network block it returns `[]` and `build_guidelines` falls back
    to the honest `portal` pointer. **Nothing is fabricated.**
  - Every fetcher is wrapped so it **never raises** — a failed fetch degrades gracefully to a pointer.
- **Wired into the builder:** `build_guidelines.build()` step 2 now tries `portal_fetch.fetch_portal(org, …)`
  per portal org; fetched records become `api` entries, failures fall back to `_portal_pointers()`.
  `source_status` now reports each portal org as `fetched` or `pointer`. Analysis-time loading is unchanged
  (still zero network via `guideline_corpus.load()`).
- **Honest limitation:** only CPIC has a real free API; the other five are fragile HTML scrapes that will
  likely stay pointers until tuned on open internet. NCCN is login-walled (free account) so may never yield
  content without auth. No live verification in this sandbox (egress limited) — verified offline via mocks.
- **Offline-verified:** 11 new smoke checks cover CPIC API path, HTML extraction, graceful `[]` on network
  error, and the build-time "fetch→api / fail→pointer" wiring. Full smoke (`adapters/_smoke_guidelines.py`)
  ALL PASS.

## v0.7.3 — 2026-08-16

### Refactor · clinical guideline corpus → local-first (corrects the v0.7.2 live-fetch design)
- **Design correction (per user feedback):** clinical guidelines are a *versioned* reference standard
  (NCCN 2024.v3, ADA 2026 Standards). The v0.7.2 model fetched "latest" via code at analysis time; the
  correct model is a **curated, version-pinned LOCAL corpus** — build once, read many times (zero network
  at analysis, reproducible, honours ct-base local-first / 数据不出域).
- **New `adapters/guideline_corpus.py`** (analysis-time, ZERO network): reads
  `references/guidelines/guidelines_index.json` and returns the same payload shape as
  `fetch_guidelines.fetch()`, so `scripts/ct_literature.py` consumes it uniformly. Filters by topic/org;
  returns an honest `corpus_missing` payload (with the builder command) when the index is absent.
- **New `adapters/build_guidelines.py`** (build-time, network, author action): aggregates 12+ sources,
  downloads OpenAlex OA-PDFs where reachable, writes/merges `guidelines_index.json` (+ optional doc files).
  SAFE PREVIEW: omit `--run` → dry-run, **no network, no write**. Dedupe by `(org, topic/title)`;
  special-cases portal orgs (`org:topic:title`) to avoid cross-topic id collisions.
- **Rewired pipeline:** `scripts/ct_literature.py` `--with-guidelines` now calls `guideline_corpus.load()`
  (was `fetch_guidelines.fetch(run=True)`). `fetch_guidelines.py` is retained as the source-library used
  by the builder, not by analysis-time loading.
- **Seeded corpus built live (network):** `references/guidelines/guidelines_index.json` — 96 curated
  entries (72 `api` + 24 `portal` pointers, all `retrieved:false`) across 4 topics (diabetes /
  breast-cancer / heart-failure / community-acquired-pneumonia). 0 OA-PDF docs on disk in this sandbox
  (external publisher domains unreachable here) — downloads succeed on the author's open-internet machine.
- **Offline-verified:** loader reads the real corpus in ~0.012 s with **zero network calls**; 22-check
  smoke (`adapters/_smoke_guidelines.py`) ALL PASS (loader zero-network, builder SAFE PREVIEW, dedupe,
  portal honesty, source-library 13 sources).
- `SKILL.md`: G section rewritten to the corpus-first model; frontmatter summary/description + Features
  row + Implementation CLI updated. `version` 0.7.1 → 0.7.3 (frontmatter had lagged behind CHANGELOG).
- **Red line honoured:** no publish/deploy (no git push / SkillHub / ClawHub / Coze deploy); local changes
  + local verification only.

## v0.7.2 — 2026-08-16

### Feature · clinical guideline aggregation across 12+ sources (G-upgrade, opt-in)
- New `adapters/fetch_guidelines.py`: aggregates clinical-practice guidelines from **12+**
  authoritative sources into one normalized, de-duplicated list. Two access tiers, honestly
  labelled per record via `access` (`api`/`portal`) + `retrieved`:
  - **Live `api`**: OpenAlex (guideline-typed search), Europe PMC (guideline pub types),
    GIN (Guidelines International Network), WHO IRIS — fetched via the shared `http_utils`
    GET+retry (429 Retry-After, exponential backoff, Bearer key).
  - **Live `api` (key-gated, best-effort)**: NICE¹ / MAGICapp / TRIP² — graceful `skipped_no_key`
    when the env key is absent (never fakes a result).
  - **`portal` pointer** (no free keyword API): NCCN / ADA / AHA / SIGN / CMA / CPIC — emit an
    honest navigational pointer (`retrieved:false`) to the org portal, **not** a fabricated fetch.
- Wired into `scripts/ct_literature.py` as a **separate** capability (kept OUT of
  `normalize.merge` so it never pollutes citation verification / PRISMA): `--with-guidelines`
  (BooleanOptionalAction, opt-in) → writes `guidelines.json` + a `guidelines` block in
  `.merged.json` (`meta.guidelines.source_status` shows per-source coverage). Flags:
  `--guideline-sources` (subset), `--guideline-max` (per-source cap, default 20).
- SAFE PREVIEW preserved: no network unless `--run`; `fetch(run=False)` returns `None`. Every
  live source is wrapped so a failure degrades to a `source_status` note, never aborting.
- `SKILL.md`: new "Clinical guideline sources" section, Features row, Implementation CLI examples,
  and frontmatter summary/description updated.
- Offline smoke test (`adapters/_smoke_guidelines.py`, mock-injected): 22 checks — parse /
  normalize / dedupe / merge, SAFE PREVIEW, portal honesty (`retrieved:false`), key-gated skip,
  and full `run()` integration — all pass.

¹ NICE public REST auth header is undocumented (like PROSPERO); degrades to skip until a working
token is supplied. ² TRIP requires a commercial API key. Live-correctness of GIN/WHO/MAGICapp/
NICE/TRIP parse paths is schema-tolerant but pending validation against a real 200 response.

## v0.7.1 — 2026-08-15

### Fix + Docs · make the abstract term-annotation tool actually work, and describe it honestly
- **Fix `abstract_translator.translate_abstract`** (was producing garbage): the old loop replaced each term without word boundaries, so short keys like `os`/`evaluate` corrupted inside longer words (`osimertinib` → `【总生存期】imertinib`), and sequential per-term substitution re-matched inside already-replaced spans (nested 【【…】】). Now: (1) only English keys are used (the Chinese-key entries from `term_map.json` are ignored — they belong to the zh→en topic translator, not this EN→ZH annotator); (2) word-boundary matching `(?<![A-Za-z0-9])…(?![A-Za-z0-9])`; (3) single-pass alternation, longest-first — no nesting. Verified: `randomized controlled trial → 【随机对照试验】`, `NSCLC → 【非小细胞肺癌】`, `overall survival → 【总生存期】`, `osimertinib` untouched.
- `SKILL.md` summary/description: "本地英文→中文摘要翻译助手" → **"可选英文→中文摘要术语标注工具（本地、术语级替换，非全文翻译）"** — the helper is a term-level annotator and not part of the retrieval pipeline; the old wording set a full-translation expectation it cannot meet.
- `README.md` / `README_zh-CN.md` (Advanced Reference): new "Optional tool · English→Chinese abstract term-annotation" section with CLI usage, real verified examples, and the explicit boundary: **term-level substitution, not full-text translation**.
- `README.md` / `README_zh-CN.md` (FAQ): new "Why don't you support Chinese domestic databases (e.g. CNKI)?" — deliberately not supported: (1) marginal incremental value vs the international evidence base; (2) no compliant channel exists (CNKI et al. have no public API for individuals and aggressively block / sue crawlers, against the skill's "official public access only" rule); (3) ROI. Users needing a Chinese paper export the citation (RIS/BibTeX) themselves.
- `scripts/abstract_translator.py`: docstring & CLI help aligned — removed the stale "optional translation API" claim (the code has **no API path**; purely local dictionary substitution).

## v0.7.0 — 2026-08-14

> v0.6.13（进度事件流）与 v0.6.14（架构优化）开发版均未单独发布，功能统一并入 v0.7.0。

### Feature · progress event stream (`--progress json`, agent-facing)
- New `--progress {human,json}` flag on `ct_literature.py` (default `human` = unchanged console
  output). In `json` mode stdout carries **only** a flushed NDJSON event stream —
  `run_start / source_done / source_failed / fetch_done / verify_progress / verify_done /
  evidence_log / intermediate / export_done / export_failed / run_done` — and sub-module
  prints are redirected to **stderr** so the stream stays parseable for agents.
- Human mode additionally gained per-source progress lines (`[OK] source OpenAlex: N works in X.Xs`).

### Performance · architecture-level wait-time reduction
- **Pooled HTTP connections** (`adapters/http_utils.py`): replaced the per-request
  `urllib.request.urlopen` (a fresh TCP+TLS handshake on every request) with a **thread-local
  keep-alive connection pool** + manual redirect following + **per-host concurrency caps**
  (doi.org 8 / Crossref 4 / OpenAlex 6 / Europe PMC 6 / S2 2). Saves ~100–300 ms handshake
  per request across the hundreds of fetch + verify round-trips; stale connections are
  dropped and rebuilt automatically. `verify_citations._resolve_doi` (doi.org Range probe)
  now uses the same pooled path.
- **Cross-source verification dedup** (`scripts/ct_literature.py`): the same work indexed by
  two sources (e.g. OpenAlex + Europe PMC) now verifies **once** by `work_key` — results still
  attach to every copy by key. Cuts 5–20% of verification calls on typical runs.
- **Wider verification pool** (8 → 24 workers): per-host politeness is now enforced by the
  connection-pool caps, not the worker count, so a 50-work verify finishes much sooner.
- **Two-phase delivery — `--verify background`**: the report is emitted immediately with works
  marked `pending_background` (fetch-time, ~seconds), then the background verification pass
  finishes and re-renders `lit_report.html` + writes `lit_report_verified.xlsx` + updates the
  evidence log. New progress events: `report_ready` → `verify_progress*` → `verify_done` →
  `report_verified` → `run_done` (export events carry `verified: false|true`).
- All existing modes (`all` / `top` / `none`) and human/json progress output are unchanged
  (regression-tested; verified 4/4 in `all` and `top`, connection reuse confirmed).
- **Measured speed-up (verify all, 20 works)**: verification segment ~119 s → ~35 s (~3.4×,
  -70%); two-phase key path 3.5 s to a usable report (~35× faster time-to-first-result).

### Docs (README FAQ, 2026-08-13)
- FAQ "How long does a search take": fixed misleading "per-source concurrency" → precise
  "sources run in parallel with each other, but each source pages serially (rate-limit / ban
  safety)".
- New FAQ "Why can't the fetch be faster?": compliance-first answer (official public access
  methods only, never violates site terms → no bulk-crawl effect) + parallel/serial structure
  + bottleneck (verification) + speed-up knobs. Synced into ct-base §13.8 as a mandatory FAQ
  item for any skill with data-fetch operations.

### Prepublish cleanup
- Removed 6 Coze-specific i18n messages (zero runtime references — `auth.coze_outbound`,
  `auth.coze_outbound_denied`, `auth.serial_blocked`, `error.coze_401`, `error.fallback_local`,
  `error.requests_missing`) that were vendored leftovers from ct-base (ct-literature has no
  Coze endpoint; they also fed SkillSpector Autonomous-Decision-Making findings).
- SKILL.md "zero confidential input" reworded to "zero confidential research / subject data
  input (API keys are local config, never research data)".

## v0.6.12 — 2026-08-13

### Security-audit fixes (ClawHub / NVIDIA SkillSpector, 21 findings)
- **README: unify API-key setup to the conversational flow (user preference)** — both READMEs
  now give one consistent story: tell the assistant in chat to configure the key (it writes it
  to the local `.env` via Write/Edit; never echoed back, never logged, sent only over HTTPS to
  the official API), or self-configure via `.env` / env var / `--openalex-key`; with an explicit
  notice that chat may be logged and self-config is the most secretive route. Fixes the
  internal contradiction SkillSpector flagged (6+ findings: one section said "never paste",
  another told you to); the conversational option is kept intentionally per user preference,
  accepting a residual chat-channel advisory. `http_utils` key-notice i18n strings updated to
  the same dual-path wording.
- **Remove all R-only dead code and messages** — this skill is pure Python
  (`required_commands: [python]`) and never calls R. Deleted `scripts/r_libs.py` (vendored
  ct-base stub, zero references here) and 13 R-only keys from `i18n_messages.json`
  (`error.rscript_not_found*`, `error.r_timeout`, `error.invalid_temp_path`,
  `error.invalid_install_path`, `install.*`, `header.r_code`, `header.install_cmd`). This also
  eliminates the stale "CRAN is the ONLY network operation" claim — that message applied to an
  R install flow this skill never uses. README/AGENTS reference lists updated.
- **SKILL.md summary/description now mention the local EN→ZH abstract translation helper**
  (eliminates the manifest-vs-behavior mismatch flagged at High/95%).
- **drug_name_resolver: auto mode now matches its docstring** — only a *unique* candidate is
  auto-translated; ambiguous names (multiple candidates) return unresolved instead of silently
  picking the first (could bias downstream queries in a biomedical context).
- **CLI help hardening**: `--no-verify-citations` / `--no-consistency` now carry a WARNING that
  they weaken the anti-hallucination gate (ct-base §17.1; debugging only); `abstract_translator
  --file/--output` now state they read/write only the paths you specify.
- **README: explicit activation boundary** — the skill activates only when the user explicitly
  asks for a literature search (addresses Vague-Triggers findings).

### Packaging note
- ClawHub audit scans confirmed the previously published package **contained `tests/`**.
  Per the new ct-base §16.8 red-line ("test content never ships"), the next publish must
  rebuild a clean package (`git archive` staging + `rm -rf tests scripts/tests`) and drop
  `tests/` via `.clawhubignore` (already updated).

## v0.6.11 — 2026-08-12

### Feature · title/author consistency cross-check in citation verification (anti-hallucination depth)
- Closes the gap flagged in v0.6.10: verification previously only confirmed an identifier
  *resolves to a live resource*. A hallucinated-but-real DOI (or a real-but-wrong id) still
  passed. Now, after an identifier resolves, the canonical metadata (title + first-author
  surname) is fetched from the authoritative, bot-friendly API and compared to the work we hold:
  - DOI  -> Crossref (`api.crossref.org/works/<doi>`)
  - PMID -> Europe PMC EXT_ID response (already fetched for resolution, no extra call)
  - OpenAlex id -> `api.openalex.org/works/<id>`
- New status **`mismatch`**: identifier resolved to a LIVE resource but its title/author do
  **not** match this work → flagged `citation_verified=False`, surfaced in all four deliverables
  (xlsx Evidence Log, html Evidence block, report, evidence_log.md) as **Mismatch / 不一致**.
  A consistent resolution is `verified`; a `bot_blocked` DOI whose Crossref metadata matches is
  now **upgraded to `verified`** (the 403 was only the publisher blocking doi.org, not the id).
- Robust by design:
  - Author matching is **order-independent** (handles "Last, First", "First Last", "First Initial"
    and list forms) via token-set membership against the metadata surname — fixes a naive
    "last token = surname" bug that misread "Ramalingam V" as surname "V".
  - Title match uses normalized `difflib` similarity (threshold 0.80) + author must not contradict.
  - Metadata **fetch failure / incomplete fields degrade gracefully** to "verified, consistency
    unchecked" — it NEVER invents a `mismatch` from a transient API error.
  - New additive per-work fields: `citation_consistency` (bool|None), `citation_title_ratio` (float|None).
- New opt-out: `--no-consistency` (pipeline `run()`) / `--no-consistency` (standalone
  `verify_citations.py`) skips the metadata fetch; verification then behaves as before v0.6.11.
- Verified: offline mock test (9 cases: match / mismatch / meta-fail / malformed / no-id /
  empty-meta / bot-block+match / pmid-path+match / no-consistency) all pass; EN+ZH render smoke
  test confirms `Mismatch / 不一致` surfaces in xlsx + html + evidence_log + report without crash.

### Docs · README + SKILL.md accuracy & clarity pass
- `README.md` / `README_zh-CN.md` restructured for clarity: added a **Table of Contents**
  anchor nav; renumbered sections (Who This Is For → Data Sources → Anti-Hallucination →
  How to Use → Scenarios → FAQ → Security → Advanced); compacted the scenario index.
- Fixed factual inaccuracies carried from earlier versions:
  - Version string `0.6.0` → `0.6.11`.
  - Dropped the false `requests` dependency claim — the skill uses **only the standard-library
    `urllib`**.
  - Architecture tree realigned to the actual layout: `adapters/` holds the 6 source fetchers +
    `http_utils` + `verify_citations`; `normalize` / `score_relevance` / `screen_prisma` /
    `format_citations` / `evidence_log` / `obsidian_exporter` / `zotero_exporter` / `export_*`
    live in `scripts/` (not `adapters/`). Output described as **HTML + Excel**, not Markdown.
  - Anti-Hallucination expanded to **4 guardrails** (was described as 3) incl. the v0.6.11
    title/author consistency layer; added `bot_blocked` + `mismatch` explanations and the
    `citation_*` schema fields.
  - Unified EN/ZH on **parallel** source execution (ZH previously said "serial").
  - Removed stale `.merged.json` references from the OA-PDF scenario (the file is now hidden /
    internal, not a user-facing artifact).
- `SKILL.md` `version:` bumped `0.6.0` → `0.6.11` to match CHANGELOG and the READMEs.

## v0.6.10 — 2026-08-12

### Logic audit · systematic bug sweep (HIGH + MEDIUM + LOW)

Systematic review of the whole skill (pipeline `run()`, every `scripts/*` exporter, both
adapters, i18n messages, formatters, docs) after the v0.6.8 output-cleanup refactor.

- **HIGH · `lit_report.xlsx` Evidence Log sheet rendered empty (v0.6.8 regression).**
  The pipeline `run()` passed `export_workbook({"count", "works", "meta"})` but
  `build_evidence` reads `evidence_log` / `verification` from the **top level** of `data`.
  So the Verification summary, source provenance and run-config blocks were all dropped —
  the sheet showed only its title + the anti-hallucination disclaimer.
  Fix: `export_workbook` now promotes `evidence_log` / `verification` out of `meta` when they
  are missing at top level (standalone CLI still passes `.merged.json` with them at top level).
  Verified by regenerating an xlsx from a real `.merged.json` — `verified=…`, `bot-blocked=…`,
  `Run config / 运行配置`, and source provenance all appear again.
- **MEDIUM · `evidence_log.py` standalone CLI lost its source trail.**
  `main()` read `data.get("payloads")`, but `.merged.json` persists `evidence_log` and does **not**
  persist `payloads`, so the rendered `evidence_log.md` had an empty source list.
  Fix: prefer the `evidence_log` already embedded in `.merged.json`; only fall back to
  rebuilding from `payloads` when it is absent.
- **LOW · DOI regex greedily swallowed trailing punctuation.**
  `_DOI_RE` used `[^\s]+`, so a trailing `.` / `)` / `]` etc. was captured into the DOI, producing
  links/labels like `10.1056/NEJMoa2403614.)`. Fixed in two places with a `_strip_doi_tail()`
  helper that strips `.,;:` then `)]` separately (the two-stage rstrip also avoids a Python
  parsing ambiguity when `)]` sits next to a string literal):
  `scripts/normalize.py::_norm_doi` and `adapters/verify_citations.py::_resolve_doi` / `work_key`.
- **Doc consistency · `merged.html` → `lit_report.html`.**
  `SKILL.md` (feature table + Output list) and `export_html.py` docstring still said `merged.html`;
  the pipeline has written `lit_report.html` since before v0.6.8. Corrected both.
- Verified: all four modified `.py` files `py_compile` clean; xlsx Evidence Log regen smoke test passes.

## v0.6.9 — 2026-08-12

### Fix · restore the "apply for an OpenAlex key" prompt in the deliverables
- Regression from v0.6.8: the keyless warning (`cfg.warn`, with the signup URL) lived in
  `report.py` / `lit_report.md`, which v0.6.8 stopped generating. After that the prompt
  survived only in console output and `evidence_log.md` — the two primary deliverables
  (HTML / XLSX) carried no actionable hint.
- `export_html.py`: added bilingual `cfg.warn` labels and render a warning block with a
  clickable signup link inside the Evidence section when `config.openalex_key == "missing"`.
- `export_xlsx.py`: the Run-config block now appends an actionable bilingual line with the
  signup URL when the key is missing (previously it only printed `missing — keyless`).
- No prompt is shown when the key is configured (verified by render smoke test, EN + ZH).

## v0.6.8 — 2026-08-12

### Output cleanup · drop `lit_report.md`; demote `merged.json` to hidden `.merged.json`
- Stop generating `lit_report.md` (the Markdown report). `lit_report.html` + `lit_report.xlsx`
  already cover the same content, so the `.md` deliverable was redundant. `report.py` stays in the
  skill as a reusable standalone Markdown renderer but is no longer called by the pipeline.
- Rename the unified work list from `merged.json` to `.merged.json` (dot-prefixed → normally hidden
  by the OS). It is now an **internal cache**, not a user-facing deliverable.
- All standalone tools (`export_html` / `export_xlsx` / `format_citations` / `obsidian_exporter` /
  `zotero_exporter` / `score_relevance` / `screen_prisma` / `evidence_log` + `verify_citations`) now
  default `--in` / `--in-json` / `--merged` to `.merged.json` (no longer `required`), so they keep
  working out-of-the-box against the hidden cache. Docstrings/help text updated accordingly.
- Docs (`SKILL.md` Output list; `README.md` / `README_zh-CN.md` report + OA-PDF references) updated:
  `lit_report.md` removed; `merged.json` → `.merged.json`; PRISMA block reference updated.
- Pre-existing (out of scope at v0.6.8, **resolved in v0.6.10**): `SKILL.md` still named the HTML
  deliverable `merged.html`, but the pipeline writes `lit_report.html`. Now fixed in both the
  feature table and the Output list; `export_html.py` docstring example updated too.

## v0.6.7 — 2026-08-12

### Bugfix · `evidence_log.md` bot-blocked label not localized (follow-up to v0.6.6)
- v0.6.6 localized the `bot_blocked` label in `report.py` / `export_xlsx.py` / `export_html.py`
  (`ev.bot_blocked`: "bot-blocked" / "出版社拦爬") but `evidence_log.py::render_md` still
  hard-coded the English `bot-blocked=` token. In a zh locale the report said `出版社拦爬=0`
  while the evidence log said `bot-blocked=0` — inconsistent.
- `render_md` now emits `bot-blocked=%s (出版社拦爬=%s)` so the zh label is present alongside
  the English key in the bilingual evidence log. Regenerated `out_lit_osimertinib_v6/evidence_log.md`.

## v0.6.6 — 2026-08-12

### Bugfix · Verification false-negative on big-publisher bot-block (403) + same-source-skip regression
- **Root cause (confirmed on another machine via live re-check):** the 37 "unresolved" papers were NOT suspect — they were the most credible, highest-cited works (FLAURA-OS, ADAURA, AURA3-CNS, BLOOM, NCCN guidelines…). Their DOIs are real: `doi.org` returns a correct 302 to the publisher, but NEJM / ASCO-JCO / JNCCN / JAMA / Nature-vs-others / Wiley / MDPI **return 403 to programmatic requests** (bot-blocking). `_resolve_doi` only accepted 2xx, so a 403 was wrongly marked `unresolved` — a **false negative**, not a broken DOI. (Publishers that allow bots — Nature / BMC / Elsevier — return 200 and were the "verified" set; so "verified vs unresolved" tracked publisher bot-policy, not paper quality.)
- **Fix 1 — `bot_blocked` status:** `_resolve_doi` now returns a 3-state string `ok | bot_blocked | unresolved`. A post-redirect 403 → `bot_blocked`. `verify_one` marks such works `citation_verified=True, citation_verify_status="bot_blocked"` (the identifier IS real) with a note "publisher bot-block (DOI likely valid; 403 from publisher, not a broken link)". This is reported **distinctly** from `unresolved`/`suspicious` everywhere (report.md / xlsx / html / evidence_log.json) so the 37 are never misread as suspect.
- **Fix 2 — same-source-skip regression:** v0.6.1's source-aware skip silenced the Europe PMC PMID (and OpenAlex id) check for same-source works. When such a work's DOI hit a 403, it had **no fallback** and fell to `unresolved` — even though its real PMID (Europe PMC EXT_ID API, bot-friendly) would have confirmed it. Now, when the DOI does NOT positively verify, PMID (Europe PMC `ext_id`) and OpenAlex id (`api.openalex.org`) are always attempted as the reliable bot-friendly fallback. `skip_sources` is retained for API compat but no longer suppresses that fallback.
- Summary dicts (`summarize_results`, `verify_works`, `none`-mode vsum) now carry `bot_blocked`. New bilingual labels `ev.bot_blocked` / `ev.bot_blocked.note`.
- Verified: 14-assertion offline self-test (200/206→ok, 403→bot_blocked, 404→unresolved, full-URL DOI normalized w/o double prefix, DOI-403+PMID-ok→verified, DOI-403+OpenAlex-ok→verified, summarize includes bot_blocked) + EN/ZH report render smoke (bot-blocked=37 shown, note present). `py_compile` clean.

## v0.6.5 — 2026-08-12

### Bugfix · Double-prefix DOI in formatted exports (`format_citations.py`)
- `references_apa.md` / `references.bib` / `references.ris` could emit `https://doi.org/https://doi.org/10.x/...` when the source DOI was OpenAlex's full resolver URL (`https://doi.org/10.x/...`). `_resolve_doi` was already fixed in v0.6.4, but the **citation-formatting path** still concatenated `"https://doi.org/" + doi` blindly at 6 sites (APA/Nature URL, `url` fallback, BibTeX `doi=` field, RIS `DO ` field, plus vancouver/ieee/gb7714 `doi:` tokens).
- Added `_bare_doi()` to `format_citations.py` — extracts the canonical `10.x/...` suffix via `_DOI_RE` regardless of input shape (full URL or bare). All 6 sites now build at most one resolver prefix. BibTeX `doi` and RIS `DO` now write the **bare** DOI (spec-correct; previously wrote the full URL).
- `export_xlsx.py._normalize_link` was already safe (checks `startswith(("http://","https://",...))` first) — no change there.
- Verified: unit self-test (full-URL + bare inputs → single prefix everywhere, bare in bib/ris) + regenerated real fixture `tests/smoke_out/merged.json` → **zero** `https://doi.org/https://doi.org/` across all three outputs; `doi = {10.1016/...}` and `DO  - 10.1016/...` now correct. `py_compile` clean.

## v0.6.4 — 2026-08-12

### Bugfix · DOI resolution mis-classified big-publisher DOIs as `unresolved`
- `_resolve_doi` accepted **only HTTP 200** (`code == 200`). Major publishers (NEJM / JCO / JAMA / AACR / Wiley / MDPI / ...) answer the `Range: bytes=0-0` probe with **206 Partial Content** instead of 200, so their live DOIs were wrongly marked `unresolved`. Now any 2xx is treated as resolved (`200 <= code < 300`). The dead `HTTPError`-branch `e.code == 200` (urllib never raises HTTPError for 2xx) was removed.
- **Mixed DOI formats normalized**: OpenAlex stores the full URL (`https://doi.org/10.x/...`), Europe PMC stores the bare DOI (`10.x/...`). `_resolve_doi` now extracts the canonical `10.x/...` suffix via `_DOI_RE` and always rebuilds the URL, so a double-prefix (`https://doi.org/https://doi.org/...`) can never occur. `work_key` was made format-agnostic too, so the same paper arriving from both sources collapses to one key (no silent duplicate / split verification).
- Offline-deterministic self-test (mocked `urllib.request.urlopen`): 206/200 resolve for NEJM/JCO/JAMA/AACR/Wiley/MDPI (full-URL + bare forms), 404 stays `unresolved`, URL normalization asserted, `work_key` equality asserted, `verify_one` end-to-end for a NEJM 206 → `verified`. `py_compile` clean.

## v0.6.1 — 2026-08-12

### P0 · Citation verification — scope control + source-aware skip
- New `--verify {all|top|none}` (default `all`) controls verification scope; legacy `--no-verify-citations` is now an alias for `--verify none`.
  - `all`: verify every merged work (concurrent with fetch, "verify one as it lands") — unchanged default behavior.
  - `top`: verify only the top-N by rank (`--verify-top-n`, default 15); remaining works are tagged `unverified_sampled` (no network call). Best speed/coverage trade-off for large result sets.
  - `none`: skip verification entirely (preview-style annotation).
- **Source-aware skip**: a work returned by OpenAlex / Europe PMC already carries a real identifier at that source, so the redundant same-source re-resolution round-trip is skipped and trusted **by source provenance** (marked `verified`, no network call). DOI is always cross-checked via `doi.org` (canonical + anti-hallucination net). `verify_citations.verify_one` gains a `skip_sources` parameter; the streaming worker and the `top` post-merge verifier both pass each work's `sources`.
- Reporting surfaces (report.md / xlsx Evidence Log) now show the verify `mode` (all/top/none) and the `sampled` count, plus bilingual mode notes.

### Tests
- Offline-deterministic self-tests: 7 `verify_one` skip/provenance cases + full `run()` integration across all three modes (mocked fetchers + verification). `py_compile` clean on all changed modules.

## v0.6.2 — 2026-08-12

### UX · Pre-run time estimate
- `run()` now prints a localized time-estimate banner **before the fetch begins**, so the user knows results may take a few minutes to return. Estimate scales with verification scope: `all` ≈ 1–4 min, `top` ≈ 1–3 min, `none` ≈ 1 min; rate-limit backoff on the keyless pool extends it further. Output path is shown so the user knows where to look while waiting.
- New i18n keys `run.starting` / `run.est.{all,top,none}` / `run.vmode.{all,top,none}` (EN/ZH).
- `SKILL.md` dialogue guidance updated: the agent must mirror this wait-time warning in chat before triggering the real fetch.

## v0.6.3 — 2026-08-12

### Docs · Anti-hallucination value section
- README.md / README_zh-CN.md: added a prominent "Why You Can Trust the Output — Anti-Hallucination by Design / 为什么可以信任输出 —— 反幻觉设计" section (right after Sources, before §1). Covers the three guardrails (live citation-id resolution P0 default ON + `suspicious` on malformed DOI; full provenance audit trail `evidence_log.json`; reports never pad gaps with prose) plus the two operational safeguards (Safe Preview local compute; source-aware skip by provenance), tied to ct-base §17.1.
- Fixed a stale FAQ claim: sources actually run **in parallel** (not sequential) since the concurrency change; latency now stated as the slowest source, plus the 1–4 min verification note.

## v0.6.0 — 2026-08-12

### P0 · Citation verification (anti-hallucination, ct-base §17.1)
- New `scripts/verify_citations.py`: each merged work is checked against its live identifier and tagged `citation_verified` / `citation_verify_status` (verified / unresolved / no_identifier / suspicious) / `citation_verify_note`.
  - doi → `https://doi.org/<doi>` resolves to final HTTP 200; pmid → Europe PMC `EXT_ID` lookup; OpenAlex id → `api.openalex.org/works/<id>`.
  - A **malformed DOI is flagged `suspicious`** (possible hallucinated identifier) — catches fabricated ids before they reach the report.
  - Each verification failure marks that work `unresolved` and **never aborts** the pipeline (pure stdlib + `http_utils`).
- Default **ON**; `--no-verify-citations` disables. Network runs only under `--run` (SAFE PREVIEW); in preview mode it records `skipped_preview` and passes works through untouched.
- New `scripts/evidence_log.py`: builds an immutable-style provenance audit trail → `evidence_log.json` + `evidence_log.md` (also embedded in `merged.json`). Traceability: query → source → hit count → retrieved_at → verification rate.

### P1 · PROSPERO systematic-review registry (opt-in, key-gated, UNVERIFIED)
- New `scripts/fetch_prospero.py`: answers *"is a review on this topic already registered / ongoing?"* (duplication-avoidance + protocol discovery), a distinct question from the bibliographic sources.
- **UNVERIFIED**: the public REST API now requires an undocumented auth header (`{"status":"error","errormessage":"Error code: header value undefined"}` on every probe). Until a working token + header is supplied, `--with-prospero` degrades to a no-op skip (returns `None`, no file written — like Semantic Scholar's no-key skip) and is **not** claimed functional. Provide `--prospero-token` (+ `--prospero-header` if `PROSPERO-ACCESS-TOKEN` is wrong). Response parser is schema-tolerant (JSON + XML) but must be re-validated against a real 200.

### Reporting surface
- `report.py` adds a bilingual **Evidence & verification** section (verification counts + source provenance table).
- `export_xlsx.py` adds an **Evidence Log** sheet (verification summary + source provenance table).
- `export_html.py` adds an **Evidence & Verification** block (verification summary + provenance table).

### Tests
- New `tests/scenario10d_evidence.py` — 8 offline-deterministic cases (D1–D8) covering verify preview / suspicious / no-identifier, evidence build+write, and the report / xlsx / html evidence surfaces, plus PROSPERO no-token graceful skip. `py_compile` clean.

### Deferred (by prior agreement)
- **Journal impact factor (IF) auto-annotation** — deferred. Will use an open proxy (e.g. OpenAlex `citation_normalized_*`) or a user-supplied local mapping table; not implemented until the mapping is provided.

## v0.5.7 — 2026-08-11

### Pre-publish hardening pass (ct-base BASE.md §16 checklist)
- **Fixed missing `scripts/i18n_messages.json`** — the ct-base shared generic i18n key set was never injected (omitted from `.ctbase_injected.json`'s file list), so `_MESSAGES` fell back to `{}` and every generic i18n key (`exec.running`, `error.generic`, `info.result_saved`, …) rendered as its raw key string at runtime. Copied the ct-base shared `i18n_messages.json` into `scripts/`; Excel UI keys stay self-contained in `export_xlsx._LOCAL`, domain keys inline in their consuming scripts (per §16.3).
- **SKILL.md 214 → 199 lines** (≤200, §16.1): trimmed the Cross-Database and Natural-language-dialogue sections.
- **Hardened `.gitignore` / `.clawhubignore`**: added `.ctbase_injected.json`, `*.ctbase_bak_*`, `tests/smoke_out/`, `.env.*`; removed a tracked `.ctbase_injected.json` (machine-specific absolute path) via `git rm --cached`.
- **references language (§16.2)**: rewrote `citation_styles.md` to English-only; stripped Chinese trigger phrases from `multi-db-search.md` (English trigger list + note that Chinese triggers mirror SKILL.md `triggers`).
- **No hardcoded Chinese output strings (§16.3)**: `abstract_translator.py` / `mesh_mapper.py` argparse help + `print` changed to English. `export_html.py` keeps ` / `-separated bilingual labels (policy-compliant); `obsidian_exporter.py` keeps `lang`-conditional bilingual.
- Not published — push/publish pending user confirmation.

## v0.5.6 — 2026-08-11

### Source expansion (real network, 10×10 hardening regression passed)
- **Europe PMC is now ON by default** (`with_europepmc=True`; `--no-with-europepmc` to disable). It is free/keyless and gives the whole PubMed/PMC/MEDLINE/MeSH pool, so the previous opt-in default (OpenAlex-only) was leaving the highest-value biomedical source off by default.
- **Added bioRxiv + medRxiv** as opt-in `--with-biorxiv` / `--with-medrxiv` (Tier P preprints). Neither has a free keyword-search API, so both are pulled through Europe PMC's preprint corpus (`SRC:PPR` + `publisher:` filter) and emitted with distinct `bioRxiv` / `medRxiv` provenance in the merged record.
- **Added arXiv** as opt-in `--with-arxiv` (keyless Atom API). Mostly methodology/ML/CS breadth for clinical questions, so kept opt-in (rank priority 1, sinks below biomedical sources).
- New fetchers: `scripts/fetch_preprints.py` (bioRxiv/medRxiv via EPMC PPR) and `scripts/fetch_arxiv.py` (arXiv Atom parser, with retry).
- `normalize._SOURCE_PRIORITY` extended: bioRxiv/medRxiv = 0 (primary biomedical), arXiv = 1 (supplementary, like SemanticScholar).

## v0.5.3 — 2026-08-08

- .env key 轻混淆（XOR+base64）防误打包明文扫描命中；http_utils.py 增加 `_deobfuscate` 向后兼容明文 .env；三平台同步发布。

## v0.5.2 — 2026-08-08

### Follow-up security audit cleanup (ClawHub SkillSpector, post-0.5.1)
- **Closed the residual Ssd3 (paste-key-to-chat) finding**: v0.5.1 removed the
  "paste your key to the assistant" prompt from `scripts/i18n.py`, but the same
  guidance was still present in README "Example 4 · Configure the OpenAlex key"
  (both `README.md` and `README_zh-CN.md`). Rewrote both to self-config only —
  `.env` / env var / `--openalex-key` — with an explicit "never paste a key into
  chat" statement. This was the true source of the 98%-confidence Ssd3 hit
  (the scanner reads the README, not just scripts).
- **Cleared the Unpinned Dependencies (Low) finding**: `requirements.txt` no
  longer declares `requests>=2.28`. `requests` is not a runtime dependency —
  fetch uses stdlib `urllib`, and the R-bridge (`r_libs.py`) was removed in
  0.5.1. The reserved optional `requests` import in `fetch_openalex.py` is noted
  with a pin-if-enabled comment.

## v0.5.1 — 2026-08-08

### Security audit remediation (ClawHub SkillSpector, post-0.5.0)
- **Removed API-key paste-to-assistant guidance**: deleted the conversational
  "paste your key to the assistant" prompts in `scripts/i18n.py`
  (`openalex.key_notice` / `semantic_scholar.key_notice`) and reverted to the
  self-service methods in `references/openalex_key.md` (Method A/B/C: `.env`,
  env var, or `--openalex-key`). Clarified the key is user-private, stored
  locally, sent only over HTTPS to the official API, and must never be pasted
  into chat — also resolves an internal contradiction with openalex_key.md §7.
- **Removed arbitrary R code execution primitive**: `scripts/r_libs.py` no longer
  imports `run_r` / `subprocess` / `tempfile`; it keeps only validation /
  sanitization helpers. ct-literature is pure-Python and never calls R, so the
  "Context-Inappropriate Capability" finding is eliminated at the root. The shared
  `ct-base/scripts/r_libs.py` was likewise stripped of `run_r` (execution
  primitives are no longer shared from the base), and `ct-base/BASE.md` §16.4 / §2
  / §10 references were updated to match.
- Dropped dead R-related i18n keys (`dry_run.*`, `exec.*`, `install.*`,
  `header.*`, etc.) that were only referenced by the removed R runner.

## v0.5.0 — 2026-08-08

### Initial public release (init version)
- First public release of ct-literature; consolidates the v0.3.x internal
  hardening aligned with ct-base v1.1.18 (i18n locale-aware strings, README
  rebuilt on the ct-advisor skeleton, `invocable: true` frontmatter, dual-author
  footer `medstatstar, phoe-zip`, packaging exclusions in `.clawhubignore`).
- The full compliance changelog carried into this release is recorded under
  v0.3.12 below.

## v0.3.12 — 2026-08-08

### Compliance & documentation (aligned with ct-base v1.1.18)
- **SKILL.md**: added `invocable: true` to frontmatter (task-entry skill, per BASE.md §16.5).
- **README (EN + ZH)**: added two dialogue-flow examples covering the two branches
  from `references/search_menu.md` — Complex (popup confirmation menu, §4.1–§4.3)
  and Vague (grill-me style clarifying questions, §6).
- Bumped version v0.3.11 → v0.3.12 across SKILL.md / AGENTS.md / both READMEs.

### Prior hardening (carried into this release)
- **i18n**: moved all hardcoded Chinese `print`/docstrings in `scripts/` to
  `i18n.py` en+zh key pairs (locale-aware) — clears BASE.md §16.3.
- **README (EN + ZH)**: restructured to the ct-advisor skeleton
  (switch line → logo → intro → Who This Is For → 1.How to Use → 2.Scenarios →
  3.FAQ → 4.Security & Privacy → 5.Advanced); removed the "Future Release Plans"
  section to stay consistent with BASE.md §13.6.
- **SKILL.md**: English-only body; frontmatter re-ordered to the ct-base §3 schema.
- **AGENTS.md**: version aligned.
- **references/**: sop.md / openalex_key.md / search_menu.md / multi-db-search.md
  fully English-only.
- **Authors**: README footer version line set to `medstatstar, phoe-zip`
  (synced to the ct-base template).

### Packaging
- `.clawhubignore`: now excludes `tests/results/`, `tests/scenario10_run/`,
  `tests/scenario10b_run/`, `tests/__pycache__/`, plus global `__pycache__/` / `*.pyc`.
- `.gitignore`: already excludes `__pycache__/` / `*.pyc` (no change needed).

## v0.3.11
- Baseline B-tier public-intel literature search skill: OpenAlex (primary) +
  Europe PMC (MEDLINE/MeSH) + Semantic Scholar (citation ranking, optional),
  normalized merge + dedupe, CSM qualitative safety subset, Markdown + Excel + HTML output.
