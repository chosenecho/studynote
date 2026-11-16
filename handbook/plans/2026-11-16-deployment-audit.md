**部署调查与安全加固计划 · 2026-11-16（v2 精简版）**

状态：A、B 两阶段已于 2026-11-16 执行完毕，结论见第 3 节；C、D 待 `.env.local` 的实例 ID。基线：`main@201a381`。相对初版：阶段从 5 个压到 4 个、任务固定 12 个、安全项从"顺带核对"升为独立的 D 阶段。

执行注记：本次 A、B 期间同一工作树有另一条并行改动（`package.json` 的 check 链新增 `check:content` 等脚本、`tools/checks/` 新增若干检查器、`docs/courses/operating-systems/exam/01.md` 有措辞改动）。A1 的结论按当时状态记录；`package.json` 的 check 链变化后需在合并完成时复跑一次全链。

**1. 复杂度控制原则**

1. 每个阶段最多 3 个任务，一个任务一次验收，做完再进下一个。
2. 只读在前、变更在后：A/B/C 全部只读，D 才动线上，且每项单独提、单独回退。
3. 无凭据也能推进 A、B 两阶段；C、D 卡在同一个前置条件上，不拆成更多分支。

**2. 四阶段总览**

| 阶段 | 目标 | 任务 | 条件 | 产出 |
| --- | --- | --- | --- | --- |
| A 本地基线 | 确认当前代码能复现线上产物 | 3 | 无 | 构建与检查结果、依赖清单 |
| B 线上只读体检 | 确认线上版本、头、证书与仓库声明一致 | 3 | 无 | 差异清单 |
| C 源站核查 | 确认 ECS 侧配置、暴露面与续期 | 3 | `.env.local` | 源站事实表 |
| D 安全加固 | 把已确认的弱点按优先级修掉 | 4 | C 完成 | 变更记录 + 复测 |

**3. 逐阶段任务**

**A 本地基线**（已完成 2026-11-16）

| 任务 | 实测结果 |
| --- | --- |
| A1 可复现构建 | `npm ci` 装入 289 包；`mkdocs build --strict` 通过（3.17s，`dist/` 生成）；structure、notes（30 章 / 225 节 / 186 题 / 22 图 / 30 页）、revisions（72 处区分 + 80 项多媒体核算）、test:unit（31 项 Python + 7 组 Node）、links（0 broken / 0 anchor）、seo（91 页 0 错 0 警）全部通过。 |
| A1 附：权利记录修复 | `check:rights` 起初失败，三处不一致：`docs/courses/operating-systems/exam/01.md`（记录 `ed53f5…`，实际 `c8eae0…`）、`handbook/content-policy.md`（记录 `ec098e…`，实际 `a6b12f…`）、两个 `handbook/plans/` 新文件无条目。逐条核验改动内容（措辞改写、取源位置说明，均无第三方材料）后更新 4 条记录，现为 183 files 通过。 |
| A2 供应链核对 | `npm audit`（官方 registry）0 漏洞；`pip-audit` 因镜像缺 `pymdown-extensions==11.0.1` 且 `pypi.org` 超时未能跑通，改用 OSV 逐包查询：mkdocs 1.6.1、mkdocs-material 9.7.7、pymdown-extensions 11.0.1 均无已知漏洞。CI 仍为 `permissions: contents: read`。 |
| A3 敏感信息扫描 | 私钥与 token 零命中；IP 命中全部为教学示例地址（10.x、172.18.x、192.168.x）；`.env.local` 从未进入 Git 历史；`.gitignore` 覆盖 `.env.local`、`artifacts/`、`local/`、`dist/`、`node_modules/`。 |

**B 线上只读体检**（已完成 2026-11-16）

| 任务 | 实测结果 |
| --- | --- |
| B1 版本一致性 | 线上 `20261110T102858Z-201a38143ddc` = 本地 HEAD `201a381` = CI 最新成功运行 `42798934266`。`workingTreeModified: true`，与 11-10 发布时工作树带未提交改动一致，不是漂移。 |
| B2 响应头与缓存 | 安全头 7 项齐全；指纹资源 `immutable` 一年、`labs.css` 300s；404 与 403 均 `no-store`；HTML 无外部资源引用、无 RUM 或统计脚本注入；sitemap 88 条域名正确。两处待处理：CSP 含 `script-src 'unsafe-inline'`（首页 7 个内联脚本，收紧需逐个加 hash）；ESA 注入的 `Set-Cookie` 缺 `Secure` 与 `SameSite`。 |
| B3 证书与 TLS | 两个域名各自 Let's Encrypt 证书，至 2027-02-02，TLSv1.3，剩余 78 天。 |

**C 源站核查**（需 `.env.local` 的 `STUDY_ECS_INSTANCE_ID`，全部只读）

- **C1 实例与 Nginx**：`workbench exec` 跑 `nginx -t`、`systemctl is-active nginx`、`readlink -f /var/www/studynote/current`、`ls -1 releases | tail`、`du -sh releases`。验收：`current` 指向 `20261110T102858Z-201a38143ddc` 同类目录，`nginx -t` 通过，历史版本数量与磁盘占用有数。
- **C2 暴露面与回源校验**：确认安全组只放行 443（与 ESA 回源端口）、源站不接受无 `X-Studynote-Origin` 的请求、`/etc/nginx/conf.d/10-studynote-auth.conf` 权限为 `600`。验收：直连源站 IP 被拒；无多余开放端口。
- **C3 证书续期与日志**：`certbot certificates`、`systemctl is-active certbot.timer`、`tail` 错误日志。验收：证书覆盖两个域名、剩余 >30 天、`certbot.timer` active、错误日志无 5xx 聚集。

**D 安全加固**（逐项单独提，每项独立回退）

- **D1 源站 IP 收敛（最高优先）**：`handbook/deployment.md` 已记录 `CreateOriginProtection` 返回 `FunctionArgError`、白名单未启用，当前源站只靠随机头保护。做法：重试 ESA 回源 IP 收敛，失败则在安全组按 ESA 回源段收敛，保留现有校验头作为第二道。验收：非 ESA 来源直连源站失败，站点正常。
- **D2 CSP 收紧**：去掉 `script-src 'unsafe-inline'`，改为对 Material 内联脚本列 hash 或 nonce；同时把 HSTS 从 `max-age=2592000` 提到一年。验收：控制台无 CSP 报错、搜索与主题切换正常、`npm run test:browser` 通过。
- **D3 速率规则与 Cookie**：ESA 速率规则从观察改为拦截（先小阈值观察一周再放开）；确认 `Set-Cookie` 缺 `Secure`/`SameSite` 是否 ESA 平台注入、能否在控制台补属性。验收：压测触发拦截且正常用户不受影响；Cookie 属性有明确结论。
- **D4 入口与历史清理**：确认旧 `os-study-notes` Pages 项目与新建 `studynote` Pages 项目是否仍可访问、是否绑定域名；清理云端超期 releases（保留 `current` 与最近两版，含旧材料的版本不重新上线）。验收：正式域名只有一条入口链路；历史目录清单与保留策略一致。

**4. 安全项优先级**

| 级别 | 项 | 依据 | 成本 |
| --- | --- | --- | --- |
| P0 | D1 源站 IP 收敛 | 源站仅靠随机头，头一旦泄漏可被直连 | 中，需控制台 |
| P1 | D2 CSP 去 `unsafe-inline` | 实测 CSP 放行内联脚本，XSS 防护打折 | 中，需改模板或加 hash |
| P1 | D3 速率规则转拦截 | 现为观察模式，不构成流量与费用上限 | 低，控制台 |
| P1 | A2 依赖漏洞 | 三个 Python 包 + 两个 npm 包未做过漏洞核对 | 低 |
| P2 | D2 HSTS 升一年 | 30 天偏短，回滚窗口小但保护弱 | 低 |
| P2 | D3 Cookie 属性 | 实测缺 `Secure`/`SameSite`，来源待确认 | 低，先确认 |
| P2 | D4 历史与旧入口 | 陈旧内容与旁路入口风险 | 低 |

**5. 验收与回退**

- 每个任务只认一个验收口径，写进本节对应行；未通过不进下一阶段。
- D 阶段每项改动前记录现状（命令与输出），改动后复测同一命令；失败即回退到记录值。
- 回退只用已校验的 ECS 发布目录 + `nginx -t` + reload + ESA 缓存刷新，不重新绑定旧 Pages 项目。

**6. 前置条件**

- C、D 依赖 `.env.local` 的 `STUDY_ECS_INSTANCE_ID`，当前不存在；`tools/deploy/ecs.mjs` 第 12 行会直接抛错。
- 边缘证书 78 天后到期；若 C3 发现源站续期异常，须在到期前处理，不依赖 ESA 自动证书兜底。
- 任何阶段都不改 DNS、不改证书私钥、不改内容权利记录；安全改动与内容改动分开提。
