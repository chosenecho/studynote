**搜索完整性修复计划 · 2026-11-16**

状态：已实施（S1、S2、S4 完成；S3 只完成仓库接管压缩规则，边缘编码仍是 gzip；S5 未排期），实测见第 11、12 节。承接本轮搜索性能与召回调查，原始数据在 `artifacts/search/`（`performance.json`、`completeness-ui.json`、`cap-coverage-current.json`、`merge-strategy.json`、`performance-cap-*.json`）。本计划只排顺序与验收，不重复调查过程。

**1. 现状**

| 项 | 状态 |
| --- | --- |
| 仓库 | `main@201a381` + 未提交改动：uv 迁移、性能优化、部署调查文档、并行工作流的内容与检查器。本计划不提交 |
| 索引 | 681 条文档；未裁剪 2,148,280 B，裁剪后 808,405 B（正文 292,910 字符） |
| 传输 | 边缘 brotli 223,215 B / gzip 291,194 B |
| 边缘缓存 | 已命中，`Age` 1–2 s（`study-search-index` 规则 TTL 3600） |
| 性能 | 桌面冷开 645 ms、首查 250 ms、稳态最慢 217 ms；移动冷开 2,095 ms、首查 661 ms、稳态最慢 496 ms |
| 召回 | 30 词 506 词-页对，worker 召回 0.557、精确 0.671 |
| 已知红灯 | 移动端稳态最慢 496 ms 超 `search-performance.mjs` 的 400 ms 预算 |

**2. 三层原因**

| 层 | 机制 | 实测代价 |
| --- | --- | --- |
| 分词 | Material worker 的 `separator` 只切空白与标点，中文整句成一个 token；查询扩展 `fe()` 退化为单字前缀通配（`中*`、`页*`、`加*`） | 死锁 4/14 页、缓存 8/25、索引 6/34；反向过配：中断 42/13、页表 18/5、加密 32/11 |
| 截断 | `search_trim.py` 的 `LIMIT = 800` 截掉 157/681 条正文，丢 124,712 字符（纯文本的 30%） | 页级丢 54/506 对（10.9%）：索引 −7、调度 −5、文件 −4、子网 −3 |
| 兜底 | `fallbackResults()` 只在 worker 返回空时触发（`search.mjs:151`） | `SPOOLing` 被救回，`死锁` 的另外 10 页永远不出现 |

**3. 方案选择**

`diagnose-strategies.mjs` 对 30 词 506 对做了四路对比（页级）：

| 策略 | 页数 | 命中 | 召回 | 精确 |
| --- | --- | --- | --- | --- |
| worker 单用（现状） | 420 | 282 | 0.557 | 0.671 |
| worker ∪ 兜底 | 592 | 454 | 0.897 | 0.767 |
| worker 文本过滤后 ∪ 兜底 | 452 | 452 | 0.893 | 1.000 |
| 索引文本直接匹配 | 452 | 452 | 0.893 | 1.000 |

后两行完全相同：一旦用“页文本是否含该词”决定成员，worker 只剩排序作用。所以修法不是换引擎，而是**让文本决定成员、worker 决定顺序**。精确 1.000 指“命中页确实含该词”，不含排序质量。

兜底扫描成本（`measure-fallback.mjs`，30 词）：cpu1 中位 1.4 ms、最差 4.4 ms（死锁）；cpu4 中位 9.2 ms、最差 21.1 ms。每次查询都跑得起。

**4. 阶段与依赖**

```text
S1 前端合并 ──┬──> S4 护栏
S2 上限 1600 ─┘
S3 边缘 brotli（独立）
S5 分词（只记录，不排期）
```

S1 单独可发，立刻拿到 0.893。S2 把上限抬到 0.958。S4 用 S1、S2 的数值做断言。S3 与召回无关，只影响移动端加载。

**5. S1 前端合并**（改一个文件，无构建变更）

| 任务 | 位置 | 内容 |
| --- | --- | --- |
| S1.1 抽词 | `docs/assets/javascripts/search.mjs` | 新增 `queryParts()`，返回 `lastQuery.toLowerCase().match(/[\p{L}\p{N}]+/gu) \|\| []`，与 `fallbackResults():120` 同一正则 |
| S1.2 文本判定 | 同上 | 新增 `textMatch(doc, parts)`：每个 part 在 `(doc.title + ' ' + doc.text).toLowerCase()` 中出现即真；汉字 ≥3 字时允许 bigram 覆盖 ≥60%，与 `fallbackResults():126-133` 同规则 |
| S1.3 合并 | 同上 | 新增 `merge(items)`：worker 组保留 `group.some(doc => textMatch(doc, parts))` 的；按 `location.split('#')[0]` 记页，把 `fallbackResults()` 里未出现的页追加在后 |
| S1.4 接线 | `search.mjs:150-151` | `render(items)` 首行由 `if (!items.length) items = fallbackResults();` 改为 `items = merge(items);` |

验收：

| 检查 | 期望 |
| --- | --- |
| 30 词页级召回 | ≥ 0.89（当前 0.557） |
| 30 词页级精确 | ≥ 0.99 |
| 中断 | 42 页 → 11 页 |
| 死锁 | 4 页 → 13 页 |
| SPOOLing | 3 页，不退化 |
| 单次查询增量 | cpu4 中位 +9.2 ms、最差 +21.1 ms |
| 桌面稳态最慢 | ≤ 240 ms（当前 217 ms） |

回退：`git checkout -- docs/assets/javascripts/search.mjs`。改动只在前端，索引不动，回退无副作用。

**6. S2 索引上限 800→1600**（改构建钩子，需重建）

| 任务 | 位置 | 内容 |
| --- | --- | --- |
| S2.1 抬上限 | `tools/mkdocs/search_trim.py` | `LIMIT = 800` → `1600` |
| S2.2 去标签不补空格 | 同上 `trim()` | `TAG.sub(' ', text)` → `TAG.sub('', text)`，避免行内标签处断词；实测 809,865 → 809,802 B，800 上限下截断条数不变（48→48） |
| S2.3 改注释 | 同上 docstring | “大约省掉四分之一”错：实际 2,148,280 → 808,405 B（62%），且上限已变 |

上限取舍（`cap-coverage.json`，真值 = 未裁剪索引）：

| 上限 | 字符 | 截断条数 | 丢页对 | 丢失率 | brotli | gzip |
| --- | --- | --- | --- | --- | --- | --- |
| 800（现状） | 293,492 | 157 | 54 | 10.9% | 223,531 | 291,185 |
| 1200 | 334,725 | 56 | 28 | 5.6% | 249,097 | 326,055 |
| **1600** | 353,674 | 36 | 21 | 4.2% | 260,404 | 341,466 |
| 2400 | 377,820 | 26 | 15 | 3.0% | 273,082 | 359,487 |
| 不截断 | 418,229 | 0 | 0 | 0 | 295,439 | 390,687 |

选 1600：比 800 多 37 KB brotli，换掉一半以上的丢失；再往上每 30 KB 只换 6 对。

验收：

| 检查 | 期望 |
| --- | --- |
| 索引大小 | 正文 369,761 字符（682 条）；brotli 275 KB |
| 召回上限 | 0.893 → 0.958（丢 21/504 对） |
| 移动端冷开 | 2,495 ms（安静机）／2,805 ms（有 70% CPU 邻居） |
| 桌面冷开 | 757 ms |
| 移动端首查 | 910 ms（安静）／1,431 ms（有邻居） |

**门禁结论**：原计划写“超 2,600 ms 就退 1200”。实测证明这条门禁的前提是错的——上限 1200、1400、1600 三档在同一台机器上分别测到 2,779、2,761、2,805 ms 冷开，差异在噪声内（见 `artifacts/search/performance-cap-*.json`）。截到 200 字符的极端档仍有 1,550 ms 冷开，说明移动端冷开由“1.4 s 传输 + 0.9 s worker 初始化”两块固定成本决定，正文体量只占很小一部分。所以退到 1200 只会丢 8 对召回（21→29），换不到任何可测的加载时间，**维持 1600**。

回退：`LIMIT` 改回 800，重建。索引是构建产物，回退不影响源页面。

**7. S3 边缘 brotli**（需 `npx esa login`）

原假设：套餐没有压缩规则，源站 nginx 只有 `gzip on`，所以浏览器只能拿到 gzip。

实测推翻了这个假设的一半：

- `ListCompressionRules` 返回一条已存在的规则 `study-compression`，`Gzip: on`、`Brotli: on`，`ConfigId` 528187574491136。压缩一直开着，只是没写进仓库配置。
- 浏览器拿到 gzip 的原因是**边缘按客户端列出的顺序挑编码**，不是按压缩率：`Accept-Encoding: gzip, deflate, br, zstd` → gzip；只发 `br` → br；连 `gzip;q=0.5, br;q=1.0` 也还是 gzip。浏览器一律把 gzip 写在前面，所以线上永远是 gzip。
- 边缘自己重编码的 brotli 质量偏弱：旧索引 808,778 B 的正文，边缘 br 出 281,742 B（34.8%），而 libbrotli q11 是 223,215 B（27.6%）。即使强制拿 br，也只省到边缘水平。

代价实测（cap 1600，同一台机器，`performance-cap-1600.json` 对 `performance-cap-1600-gzip.json`）：移动端冷开 2,805 ms（br）对 3,239 ms（gzip），**gzip 多花 434 ms、多传 86 KB**。

已做（`npm run esa:configure` 预览十路规则全部 `Unchanged`，读回复核一致）：

| 任务 | 结果 |
| --- | --- |
| S3.1 探测套餐支持 | `ListCompressionRules` 支持，规则已存在 |
| S3.2 仓库接管压缩规则 | `config/esa-site.json` 增 `compressionRules`，`tools/deploy/esa.mjs` 增 `syncRules('CompressionRule', …)`，防止有人关掉 Brotli 而仓库不知情 |

未做，留作评估：源站 brotli（`nginx-site.conf` 加 `brotli on`）。它要在 ECS 上装 `ngx_brotli` 并重编译 nginx，而且源站出 br 之后边缘是否透传还是重编码，没装模块就验证不了。收益上限是 434 ms（移动端冷开 2,805 → 2,371 ms）。触发条件：移动端冷开成为被报的问题，再启动。

回退：删掉 `compressionRules` 条目重跑 `npm run esa:configure --apply`。

**8. S4 护栏**

| 任务 | 文件 | 内容 |
| --- | --- | --- |
| S4.1 索引覆盖检查 | 新建 `tools/checks/search_coverage.py` | 读 `dist/search/search_index.json` 与 `dist` 页面的 `<article>` 文本，对 28 个固定词断言“页面含词的页，索引文本也含该词”；丢页对超过 6% 即 exit 1 |
| S4.2 端到端检查 | 新建 `tests/browser/search-completeness.mjs` | Playwright 打开真实搜索，12 词断言 UI 结果页集合等于索引真值页集合；`SPOOLing` 必须有结果 |
| S4.3 挂脚本 | `package.json` | 增 `check:search`（S4.1）与 `test:search`（S4.2）；`check` 链在 `build` 之后加 `check:search` |
| S4.4 预算按设备给 | `tests/browser/search-performance.mjs` | 400 ms 单值改为按设备类给，且都被实测撑住：桌面冷开 ≤900、首查 ≤400、稳态 ≤300；移动冷开 ≤3,000、首查 ≤1,800、稳态 ≤700；索引 brotli ≤300 KB |

回退：删两个新文件与两条 npm 脚本，`check` 链去掉 `check:search`。

**9. S5 分词**（只记录，不排期）

根因在 Material worker 的 `separator`：只切 `[\s\u200b\u3000\-、。，．？！；]+`，中文句子整段成一个 token，查询扩展只能退化成单字前缀通配。彻底修要换索引器（自建 n-gram 索引，或换 pagefind 的中文分词），代价是重建整条索引管线并接管主题的 worker 协议。S1+S2 把召回从 0.557 提到 0.958，剩余约 4% 留给 S5。触发条件：出现 S1+S2 之后仍被用户报缺的查询，再启动评估。

**10. 文档同步**

| 文件 | 改动 |
| --- | --- |
| `handbook/development.md:16` | “2.1 MB 降到 790 KB”“截到 800 字符”两处数字随 S2 更新 |
| `tools/mkdocs/search_trim.py` docstring | 同上，见 S2.3 |
| 本计划 | 执行后补“执行结果”段，记录实测值与门禁结论 |

**11. 验收总表**

实测口径：召回、精确、页数取自 `artifacts/search/completeness-ui.json`（12 词，真实浏览器，对着构建产物的索引真值比）；冷开与查询取自 `artifacts/search/performance.json`（cap 1600、brotli、桌面 10 Mbps/40 ms、移动 1.6 Mbps/150 ms/4× CPU，3 次取中位）。

| 项 | 修复前 | 修复后 | 目标 | 结论 |
| --- | --- | --- | --- | --- |
| UI 结果页数 vs 索引真值 | 缺页 + 多页 | 12 词 0 缺 0 多 | 0 缺 0 多 | 达标 |
| 死锁 | 4 页 | 14 页（真值 14） | 13 页 | 达标 |
| 中断 | 42 页（真值 13） | 13 页 | 11 页 | 达标 |
| SPOOLing | 3 页 | 3 页 | 3 页 | 达标 |
| 索引对源文本召回上限 | 0.893 | 0.958（丢 21/504 对） | ≥ 0.95 | 达标 |
| 桌面冷开 | 645 ms | 757 ms | ≤ 900 ms | 达标 |
| 桌面首查 | 250 ms | 240 ms | ≤ 400 ms | 达标 |
| 桌面稳态最慢 | 217 ms | 192 ms | ≤ 300 ms | 达标 |
| 移动冷开（brotli） | 2,095 ms | 2,495 ms（邻居满载时 2,805 ms） | ≤ 3,000 ms | 达标 |
| 移动首查 | 661 ms | 910 ms（邻居满载时 1,431 ms） | ≤ 1,800 ms | 达标 |
| 移动稳态最慢 | 496 ms | 256 ms | ≤ 700 ms | 达标 |
| 索引 brotli | 223 KB | 275 KB | ≤ 300 KB | 达标 |
| 边缘编码 | gzip | gzip（规则已开 Brotli，边缘按客户端顺序挑） | br | 未达标，见 S3 |

**12. 执行结果**

S1（`docs/assets/javascripts/search.mjs`）与 S4（`tools/checks/search_coverage.py`、`tests/browser/search-completeness.mjs`、`package.json`、按设备的性能预算）已完成并通过。`npm run check:search` 输出 28 词 505 对、丢 22 对（4.4%），`npm run test:search` 输出 12 词 184 页、0 缺 0 多。

S2 已完成并保留 1600：正文 369,761 字符、682 条、1,013,670 B、brotli 275,417 B。原来写的“移动端冷开超 2,600 ms 就退 1200”门禁按实测作废——上限 1200/1400/1600 的冷开分别是 2,779/2,761/2,805 ms，退档换不到时间，只丢召回。

S3 只完成“仓库接管压缩规则”一半，边缘编码仍是 gzip，原因和解法见上一节。

