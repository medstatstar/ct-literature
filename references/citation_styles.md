# Citation Styles / 引文样式说明

`ct-literature` 支持五种引文样式（`--citation-style`），由 `scripts/format_citations.py`
读取 `merged.json` 并复用既有字段（title / authors / year / publication / volume /
issue / page / doi / url）拼装。导出 `references.bib`（BibTeX）+ `references.ris`（RIS）。

> 报告头与 `references_<style>.md` 顶部都会标注所用样式，便于溯源。

## 1. APA (7th) — 默认
```
Author, A. A., & Author, B. B. (Year). Title of article. *Journal Name*, *Vol*(Issue), Pages. https://doi.org/DOI
```
- 作者：姓, 名首字母.，多人用 `, &` 连接。
- 期刊名斜体；卷斜体，期用括号。

## 2. Nature
```
Author1 AB, Author2 CD. Title of article. Journal Name Vol, Pages (Year). https://doi.org/DOI
```
- 名在前缩写为首字母（无点），姓在后；逗号分隔。
- 编号式期刊的内联写法；年份置于末尾括号。

## 3. Vancouver（顺序编码制）
```
Author1 AB, Author2 CD. Title of article. Journal Name. Year;Vol(Issue):Pages. doi:DOI
```
- 作者不超过 6 人全列，超过则以「et al.」收尾（本实现全列，便于 Bib/RIS 互转）。
- 年份后接 `;卷(期):页`。

## 4. IEEE
```
Author1, "Title of article," Journal Name, vol. Vol, no. Issue, pp. Pages, Year. doi: DOI.
```
- 文章题名用双引号；`vol.` / `no.` / `pp.` 显式标注。

## 5. GB/T 7714（中华人民共和国国家标准）
```
作者. 题名[J]. 刊名, 年, 卷(期):页码. DOI:DOI.
```
- **中文分支**：标点全为中文全角（。、[J]、，、：），作者间用中文逗号「，」分隔。
- 与英文样式（apa/nature/vancouver/ieee）混排时，按 `style == 'gb7714'` 分支，
  避免中文标点被英文模板吞掉。

## 字段映射（merged.json → 引文）
| 引文要素 | merged.json 字段 |
|---|---|
| 作者 | `authors`（list，容忍字符串/None） |
| 年份 | `year` |
| 题名 | `title` |
| 期刊 | `publication` |
| 卷 / 期 / 页 | `volume` / `issue` / `page` |
| DOI / 链接 | `doi` / `url` |

## 注意事项
- 纯本地生成，不改动抓取层；样式仅为排版模板，非正式排版校验。
- 作者名解析对「姓, 名」与「名 姓」均兼容，中文姓名整体保留。
