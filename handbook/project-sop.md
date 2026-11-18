# studynote 项目标准作业程序（SOP）

适用于维护人、校对人和发布人。同一人兼任时，在记录中注明各项检查由谁完成。产品边界、验收指标和工作窗口见 [PDR](plans/2026-11-18-pdr.md) 与 [PDP](plans/2026-11-18-pdp.md)。

## 接单与复现

1. 记录页面、章节或题号、设备与浏览器、预期和实际结果。优先处理误导答题的内容、考生任务无法完成的问题和发布故障。
2. 明确负责人、改动范围、验收样本和证据位置。复现时记录提交号、工作树状态或公开发布号。
3. 将改动分成可独立复核的批次。登记结论为通过、超限、待核或延期，并注明下一次复查条件。

## 内容修订与校对

1. 按课程代码、教材版本和大纲条目查找依据。由校对人核对术语、算式、单位、适用条件和章节锚点。来源冲突记入勘误，结论保留适用范围。见 [内容政策](content-policy.md) 和 [勘误](../docs/errata.md)。
2. 同步复核学习页、考点页、练习答案和入口计数。无独立真题题号与有效样本范围的措辞采用「题型建议」。章节练习用自编题，真题只做映射与核验。
3. 复核内容权利后更新 [权利台账](../config/content-rights.json)。已有条目在复核依据仍适用时更新 SHA-256，新增条目补齐来源与许可。文本按校验器的 LF 口径计算摘要。运行 `npm run check:rights` 和 `npm run check:content`。涉及真题映射时用本地题库设置 `EXAM_DB` 后执行 `npm run check:exams`，记录实际通过或跳过状态。

## 性能变更与真人验收

1. 在同一环境串行测量改前与改后。先执行 `npm run build`，然后用以下命令分别保存每个候选版本的结果。默认每个设备三次冷上下文，比较中位数，同时保留单轮样本。线上对照另建文件，记录 `__release.json`、编码及边缘缓存条件。

   ```powershell
   npm run measure:performance -- dist artifacts/eval/reading.json /courses/operating-systems/chapter-02/ /courses/computer-organization/chapter-05/ /reference/glossary/
   npm run measure:search -- dist artifacts/eval/search.json
   npm run test:search
   ```

2. 阅读超限时记录 LCP 元素、资源瀑布与长任务调用栈。搜索超限时拆分索引传输、解析与 Worker 初始化，以及首次查询。每次实验只改一项，保留召回与排序回归结果。搜索性能读取 JSON 的 `verdict`，同时检查各指标值。
3. 对照 PDP 验收。阅读贴线例外记录成因、复测、影响和批准人。真人走查记录设备、任务结果、用时和求助情况，匿名保存。读屏记录操作序列、预期播报与实际播报。

## 发布、核验与回退

1. 确认发布候选提交及工作树状态。运行 `npm run check`、`npm run test:browser` 和 `npm run test:search`，核对远端 CI 对应的提交。记下 ECS 当前有效发布编号用于回退。
2. 按部署手册准备 Workbench、ESA 登录与本地配置，在明确的发布窗口执行 `npm run deploy`。保留 `artifacts/releases/<release>/` 的版本、摘要、激活、缓存刷新和预热证据。见 [部署手册](deployment.md)。
3. 核对 ECS `current` 与公网 `/__release.json`。抽查首页、学习和应试入口、练习与搜索，检查裸域重定向与证书期限。证书剩余不足 30 天登记为 P1。
4. 激活后核验失败时，先区分源站切换、ESA 缓存与公开访问故障。需要回退时，依部署手册切换为上次确认的发布，刷新 ESA 缓存，再核对版本与核心路径。记录影响范围、时间和恢复结果。
