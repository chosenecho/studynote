**上线与加固执行计划 · 2026-11-16**

状态：计划。承接[部署调查计划](2026-11-16-deployment-audit.md)（A、B 已完成）与[内容评估计划](2026-11-16-content-evaluation.md)（并行工作流执行中）。本计划只排顺序与验收，不重复调查结论。

**1. 现状**

| 项 | 状态 |
| --- | --- |
| 仓库 | `main@201a381` + 未提交改动：uv 迁移、性能优化、部署调查文档、并行工作流的内容与检查器 |
| 线上 | `20261110T102858Z-201a38143ddc`，比仓库落后一轮 |
| 已改未部署 | 页面 TTL 3600s、json 边缘缓存、ServeStale、发布后预热、搜索索引裁剪 |
| 阻塞 | `.env.local` 无 `STUDY_ECS_INSTANCE_ID`；ESA 规则需 `esa login` |
| 已知红灯 | 无。全链 `npm run check` 当前 exit 0 |

**2. 阶段与依赖**

```text
P0 发布前校验 ──> P1 边缘配置 ──┐
                    │            ├──> P3 安全加固 ──> P4 架构决策
                    └──> P2 源站上线 ┘
```

P1 与 P2 改的是两套系统，可并行；两者都要求 P0 先绿。P3 依赖 P2 拿到源站事实。P4 只出评估，不改动。

**3. P0 发布前校验**（半天，无需凭据）

| 任务 | 命令 | 验收 |
| --- | --- | --- |
| P0.1 全链检查 | `npm run check` | exit 0；184 条权利记录、91 页 SEO 0 错、0 断链 |
| P0.2 产物核对 | 检查 `dist/` | 199 文件；`search/search_index.json` 约 790 KB；无 `*.map` |
| P0.3 权利记录 | `npm run check:rights` | 并行工作流的内容改动全部登记 |

阻塞条件：并行工作流仍在改 `docs/courses/multimedia-technology/`，每改一次权利摘要就失效。P0.1 必须在它收工后跑，否则绿灯是假的。

**4. P1 边缘配置**（半天，需 `npx esa login`）

| 任务 | 命令 | 验收 |
| --- | --- | --- |
| P1.1 预览 | `npm run esa:configure` | 输出 `Would create: study-search-index`、`Would update: study-edge-static` |
| P1.2 差异核对 | 人工比对输出 | 只出现上述两条；无其他规则被动 |
| P1.3 应用 | `npm run esa:configure -- --apply` | 读回复核通过，输出 `ESA site rules verified.` |
| P1.4 生效验证 | 连续两次 `curl -I /search/search_index.json` | 第二次 `X-Site-Cache-Status: HIT` 且有 `Age` |

回退：`--apply` 前先 `git stash` 保存 `config/esa-site.json` 原件；失败时恢复文件并重跑 `--apply` 写回旧规则。

**P1 执行结果（2026-11-16）**

- 预览时发现第三条变动：`study-hotlink-no-store` 在云端比仓库多两条路径（`computer-networks/figures/`、`multimedia-technology/figures/`）。云端是手动补的，仓库没同步。直接 `--apply` 会把它覆盖回两条，丢掉两门课的防盗链。已先把云端值写回 `config/esa-site.json`，再重新预览，该规则变为 `Unchanged`。
- 首次 `--apply` 因 `EdgeCacheMode: "cache_ttl"` 报 `InvalidParameter.ArgValue`。查 [CreateCacheRule 文档](https://help.aliyun.com/zh/edge-security-acceleration/esa/api-esa-2024-09-10-createcacherule)，合法值为 `follow_origin`、`no_cache`、`override_origin`、`follow_origin_bypass`、`follow_origin_override`，没有 `cache_ttl`。改用 `override_origin` + `EdgeCacheTtl: "3600"` 后成功。
- 应用结果：`create: study-search-index`、`update: study-edge-static`，读回复核通过。
- **P1.4 未通过**：`/search/search_index.json` 连续请求仍为 `MISS`，无 `Age`，`Content-Length` 为 2,140,058。规则本身已确认生效（`RuleEnable: on`、`EdgeCacheMode: override_origin`、`EdgeCacheTtl: 3600`、站点 `VersionManagement: false`）。判断是源站当前索引 2.04 MB 超过单文件缓存上限，待 P2 部署后索引降到 790 KB 再复验。规则保留，不回退。

**P2 执行结果（2026-11-16）**

- P2.1：`workbench list --region cn-beijing` 找到唯一实例，写入 `.env.local`（已被 Git 忽略）。
- P2.2：`nginx -t` 通过；`current` 指向 `20261110T102858Z-201a38143ddc`；历史发布 42 个、323 MB；磁盘 40 G 用 15 G；`studynote` 证书覆盖两个域名、剩 77 天；`certbot.timer` active；错误日志只有一条目录列表 403。
- **又一处配置漂移**：服务器 `/etc/nginx/conf.d/20-studynote.conf` 的 figures 缓存规则包含四门课，仓库 `nginx-http.conf` 只有两门。直接上传会丢掉 `computer-networks` 与 `multimedia-technology` 的按日缓存。已先把服务器值写回仓库，再上传。
- P2.3：`npm run deploy` 成功，release `20261116T074319Z-201a38143ddc`，199 文件，`rightsCheckPassed: true`，`workingTreeModified: true`（工作树本就带未提交改动）。nginx 配置单独用 `workbench upload` 同步到 `20-studynote.conf`，`nginx -t` 通过后 reload，备份留在 `/root/20-studynote.conf.bak-*`。
- P2.4：页面 `Cache-Control: max-age=3600` 且 `HIT`，`Age` 有值。`search_index.json` 仍是 `MISS`——索引已降到 790 KB，规则依然不生效，说明 ESA 基础版不缓存这个 json，与体积无关。预热首次只有 1/92：Node fetch 并发报 `TypeError: fetch failed`，串行报 `ENOTFOUND`；改成 curl 每十页一批后 92/92，用时 28 秒，`warm.json` 已按实测重写。

**P3 执行结果（2026-11-16）**

- **P3.1 未完成，基础版不支持。** `CreateOriginProtection` 用四种参数组合（含 `OriginConverge: on/off`）全部返回 `FunctionArgError`；`UpdateOriginProtection` 返回 `OriginProtectionNotExist`（站点未配置源站防护时不能修改）。`GetOriginProtection` 的 `OriginProtection` 为空、`RegionalLatestIPWhitelist` 为空对象。结论：拿不到 ESA 回源 CIDR，安全组收敛无法自动化。
- **P3.1 附带发现**：安全组入方向实测四条规则——443、80、22、ICMP 全部对 `0.0.0.0/0` 开放。22 端口对全网开放比 443 更直接，workbench 走阿里云内部通道，收 22 不影响它，但会影响直接用 SSH 登录的人，需要先确认管理 IP。
- **P3.2 评估后不做。** 94 页共 656 个内联脚本、108 个唯一 sha256。全量 hash 的 CSP 头 5.9 KB，而响应头不压缩，等于每个请求多传 5.9 KB；且 hash 随内容变化，每次发布都要重新 apply。站点是纯静态、无用户输入、`default-src 'self'` 已挡住外部脚本，`'unsafe-inline'` 的实际风险很低。收益不抵成本。
- **P3.3 与计划描述不符。** `ListWafRules` 的 `http_custom` 阶段只有两条规则，都是 `deny`：`study-block-scanners`、`study-asset-hotlink`。没有速率规则可"从观察改为拦截"，要新建。新建 WAF 速率规则容易误伤正常访问，需要先定阈值并观察。
- **P3.4 完成。** 发布目录从 43 个清理到 3 个（当前版 + 最近两版），磁盘 323 MB → 44 MB，`current` 指向不变，首页、`__release.json`、章节页均返回 200。

**5. P2 源站上线**（一天，需实例 ID）

| 任务 | 命令 | 验收 |
| --- | --- | --- |
| P2.1 补凭据 | 复制 `.env.example` 为 `.env.local`，填 `STUDY_ECS_INSTANCE_ID` | `npm run deploy` 不再在第 12 行抛错 |
| P2.2 源站只读核查 | `workbench exec` 跑 `nginx -t`、`readlink -f current`、`certbot certificates` | `current` 指向上一版；证书剩余 >30 天 |
| P2.3 部署 | `npm run deploy` | 权利检查通过；新 release 目录生成；`__release.json` 与本地 HEAD 一致 |
| P2.4 验证 | 读 `artifacts/releases/<release>/warm.json`；抽查页面头 | `warmed` 等于页面数；页面 `Cache-Control: max-age=3600`；边缘 `HIT` |

回退：`current` 切回上一版目录 → `nginx -t` → reload → 刷新两个域名缓存。发布脚本不删历史版本，回退目标一定存在。

风险：TTL 从 300 秒提到 3600 秒后，若 `purgeSite` 失败，用户最多看到一小时旧内容。P2.4 必须确认 purge 结果，不能只看 `__release.json`。

**6. P3 安全加固**（两天，需控制台）

| 任务 | 优先级 | 验收 |
| --- | --- | --- |
| P3.1 源站 IP 收敛 | P0 | 非 ESA 来源直连源站失败；站点正常 |
| P3.2 CSP 去 `unsafe-inline` | P1 | 首页 7 个内联脚本逐个加 hash；控制台无 CSP 报错；`npm run test:browser` 通过 |
| P3.3 速率规则转拦截 | P1 | 小阈值观察一周后改拦截；正常用户不受影响 |
| P3.4 历史清理与旧入口 | P2 | 保留 `current` 与最近两版；旧 Pages 项目无域名绑定 |

P3.1 是唯一 P0 项：当前源站只靠 `X-Studynote-Origin` 随机值挡着，值泄漏即可绕过 ESA 直连。

**7. P4 架构决策**（只评估，不改动）

实测事实：`InternetChargeType` 是 `PayByBandwidth`，`InternetMaxBandwidthOut` 是 **3** Mbps（不是一直说的 5），`ChargeType` 是 `PrePaid`。源站 nginx 日志 11 天累计 215 MB、约 13,500 次请求，折合每月约 0.6 GB 回源流量。

| 选项 | 结论 | 依据 |
| --- | --- | --- |
| ECS 改按流量计费 | **建议做** | 3 Mbps 固定带宽预付费约 70 元/月；按流量 0.8 元/GB × 0.6 GB 不到 1 元/月，峰值还能开到 100 Mbps。成本降两个数量级，同时解除突发时的硬顶 |
| OSS 静态托管 + ESA 回源 OSS | **不建议** | 月回源 0.6 GB，3 Mbps 在正常情况下根本用不满；迁移要重写发布流程和源站校验，收益不抵成本 |
| HTTP/3 | **可选，优先级低** | ALPN 现在协商到 h2，没有 `alt-svc`。弱网下少一个握手 RTT，但站点流量小，收益有限，且需确认基础版是否开放 |

判断依据：3 Mbps 不是日常瓶颈，是**突发瓶颈**。TTL 3600 秒加预热之后，回源只在发布后和缓存过期时发生，那时 3 Mbps 会瞬间打满。按流量计费正好对上这个形状——平时几乎不花钱，突发时自动放开。

**8. 完成标准**

- P0–P2 完成：线上 release 与仓库 HEAD 一致，页面 TTL 3600 秒，搜索索引边缘命中，预热记录齐全。
- P3 完成：直连源站被拒，CSP 无 `unsafe-inline`，速率规则生效。
- P4 完成：三个选项各有一页结论，不需要动线上。
