# 开发与内容约定

## 源文件与构建

MkDocs 直接读取 `docs/`。课程位于 `docs/courses/<slug>/`，入口为 `index.md`，章节为 `chapter-NN.md`；共用速查位于 `docs/reference/`，交互练习页面位于 `docs/labs/`。Markdown 使用相对路径，课程插图放在本课程的 `figures/` 中。

`config/syllabus.json` 关联大纲小节与章节练习；`config/quotations.json` 登记必要的第三方引文，当前为空。出题与引用规则见 [内容贡献规则](content-policy.md)。

`config/courses.json` 注册课程的 `id`、`slug`、`title` 和 `chapters`。源码路径直接决定网址；复习记录标识统一为 `<id>-<章号>`。

构建由 `mkdocs.yml` 注册的原生钩子处理：

- `tools/mkdocs/content.py`：通过 `on_page_markdown` 添加复习工具栏、进度标记、折叠答案和图片尺寸。课程入口的“资料与核对规则”“资料依据与使用边界”“原有笔记处理”章节仅保留在源码中。
- `tools/mkdocs/licenses.py`：通过 `on_files` 将根目录许可说明、`LICENSE`、`NOTICE`、`LICENSES/` 和权利清单作为虚拟文件提供给站点。
- `tools/mkdocs/assets.py`：处理构建产物，内联阅读样式、调用 `render-math.cjs` 将公式构建为 KaTeX HTML/MathML，清理未使用的搜索语言包与 source map。
- `tools/mkdocs/search_trim.py`：构建后去掉搜索索引的 HTML 标签并归一空白，保留完整正文，不再按 1600 字符截断。2026-11-17 整改实测为 685 条、442,964 字符，JSON 1,191,083 B、Brotli 312,265 B；相对同批旧裁剪产物增加 16.08%，换取固定 28 词的 507 个正文词—页面对全部保留。`check:search` 的总量与单词丢失预算均为 0。只改产物，不动源页面；实测与局限见 `plans/2026-11-17-site-remediation-results.md`。

钩子不写入 `docs/`。课程之间的链接保留原生 Markdown 路径，不再另设输出目录或改写章节文件名。

## Python 环境与依赖

Python 依赖以 `pyproject.toml` 为唯一来源，锁定在 `uv.lock`；`requirements.txt` 已移除。`.python-version` 固定 3.12，与 CI 一致。

```sh
npm run uv:sync          # 按 uv.lock 同步依赖（--locked，不改锁文件）
npm run uv:lock          # 改动依赖后重新解析并锁定
```

依赖通过 uv 管理，构建与检查一律 `uv run --locked`，锁文件与 `pyproject.toml` 不一致时直接失败，避免运行中悄悄改锁。代理是可选项：默认直连或沿用环境变量里的代理；本机需要固定代理时用 `tools/dev/uv.ps1 -Proxy http://127.0.0.1:10808` 显式传入，端口不写死。索引固定官方 PyPI，因为国内镜像缺 `pymdown-extensions` 11.0.1；`uv.toml` 的 `index-url` 会被环境变量 `UV_DEFAULT_INDEX`（或 `UV_INDEX_URL`）覆盖，而 `uv.lock` 是对官方索引锁定的，所以在设置了非官方镜像环境变量的机器上，跑 `--locked` 前须把 `UV_DEFAULT_INDEX` 设为 `https://pypi.org/simple` 或清除，否则报锁文件过期。`uv.toml` 只放索引与证书设置；代理只认 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY` 环境变量，由该脚本按需注入，不写进仓库配置。

升级依赖时改 `pyproject.toml` 的版本号，跑 `npm run uv:lock` 与 `npm run uv:sync`，再按[第三方资源说明](../THIRD_PARTY_NOTICES.md)复核实际分发文件。

## 前端与主题

`docs/assets/javascripts/reader.mjs` 负责复习记录、字号、图片预览、搜索和无障碍适配。`labs/loader.mjs` 按页面加载实验；调度页面使用 `labs/scheduler.mjs`，其模型为 `labs/scheduling.mjs`。其他实验与题库分别使用 `labs/labs.mjs`、`labs/labs-core.mjs` 和 `labs/quiz-bank.mjs`。单元测试直接导入页面使用的模型。

自测问题与选项的 ID 是永久标识，不能从数组位置重新生成。修正文案或增加干扰项保持原身份；改变题意或正确答案须增加单题 `revision`，并移除不再适用的 `legacyRevision`。版本 3 存储用选项身份保存答案，恢复时按单题版本核验；未知格式先另存备份，再启动新会话。

阅读和实验样式位于 `docs/assets/stylesheets/`；KaTeX 原发行文件位于 `docs/assets/vendor/katex/`，保留其 LICENSE。模板覆盖位于 `theme/`。

页面用 Material 自带的导航、页脚、配色、卡片和折叠组件，课程索引另外接上。新增页面先走 `mkdocs.yml` 和 Markdown 扩展，样式只在阅读、实验、打印和无障碍上补足。

课程首页与考点页面由 Markdown 与自有样式组成：`.chapter-grid`、`.chapter-card`、`.course-steps`。每门课拆成两套页面：`chapter-NN.md` 放学习导航、概念讲解与练习；`exam/NN.md` 放必背名词、必背清单、数字与公式、易混对照、简答模板与默写自测，`exam/index.md` 是考点总览。考点页文件名不得以 `chapter-` 开头，否则会与章节文件集校验冲突；章页用 `(exam/NN.md)` 链到考点页，考点页用 `(../chapter-NN.md)` 链回。

Material 9.7.7 的搜索分享会先保存旧链接再更新链接。`initSearchShareCopy()` 在点击捕获阶段同步复制属性，仍由上游 ClipboardJS 执行复制。主题升级后重新检查，确认上游修复后移除此适配。

## 修改与添加课程

1. 修改对应章节，保留首行标题、大纲定位、学习导航、应试导航与自编练习结构，并同步大纲小节与题目的映射；插图使用本课程的相对路径。
2. 新课程在 `config/courses.json` 注册，并添加 `index.md` 和连续编号的 `chapter-NN.md`。
3. 更新 `mkdocs.yml` 导航、`docs/index.md` 课程卡片及 `reader.mjs` 的课程进度配置；需要自测时补充题库。
4. 调整 `tools/checks/notes.py` 与 `tools/checks/revisions.py` 的检查范围，补充相应测试。
5. 完成内容权利核验记录后运行检查；涉及交互时运行浏览器测试。

## 内容权利

许可范围见 [LICENSING.md](../LICENSING.md)。新增或修改学习文字、插图后，在 `config/content-rights.json` 记录来源、核验结论和依据。只有确认具备相应授权后才设为 `cleared`，填写许可、核验日期和文件 SHA-256；文本按 LF 换行计算摘要，第三方二进制资源保持原字节。正文变化后须重新核验，不能只更新摘要。不能确认的材料保持 `pending`，或从发布内容中移除。

第三方许可、署名与 MPL 搜索语言包对应源码随站点分发。更新依赖时，重新核对实际分发文件，并更新 [第三方资源说明](../THIRD_PARTY_NOTICES.md)。

## 检查入口

| 命令 | 范围 |
| --- | --- |
| `npm run check:structure` | 课程注册、文件编号、源码链接与目录边界 |
| `npm run check:notes` | 笔记结构、图片引用与行文规则 |
| `npm run check:revisions` | 已核对技术修订 |
| `npm run check:exams` | 真题映射结构与章节落点（纯映射层，可无数据库运行） |
| `npm run test:unit` | 原生构建钩子、许可分发、权利检查、真题合并重建与练习模型 |
| `npm run build` | MkDocs 严格构建 |
| `npm run check:links` | 产物链接、锚点与图片 |
| `npm run test:browser` | 主题、搜索、阅读控制、实验、打印与窄屏 |
| `npm run test:search` | 搜索面板结果与产物索引一致（索引真值，不校验索引是否丢词） |
| `npm run check:search` | 产物索引对构建后页面正文的搜索完整性（原文真值，含丢失预算） |
| `npm run check:rights` | 发布内容的核验记录、摘要与未登记文件 |

`npm run check` 依次执行权利、结构、笔记结构、技术回归、大纲与练习覆盖、真题映射、单元测试、严格构建、搜索完整性与产物链接、SEO 检查。发布命令在上传前再次约束内容权利。

Playwright 为仓库锁定的开发依赖。浏览器证据默认写入 `artifacts/browser/labs/`；`STUDY_BASE_URL` 和 `STUDY_OUTPUT_DIR` 可指定站点与证据目录。

## 历史与私有材料

`archive/` 只保留当前可公开的维护记录。含旧题面、答案及截图的历史审计已移到本地对照副本。main 已改写为干净历史；GitHub PR 引用、缓存和外部副本的后续边界见 [历史清理记录](history-cleanup.md)。当前检查统一从 `package.json` 启动。

`local/` 整体忽略提交，其中的独立 Git 仓库保留内部结构。构建不读取私有教材、扫描件或历史审计记录。

## 公式与分享图片

构建需要 Node.js（与本仓库模型测试使用同一运行环境）；公式解析失败会终止构建，浏览器不再临时渲染 TeX。无需新增 KaTeX npm 依赖，使用已锁定许可的本地发行文件。

首页与课程分享 PNG 是已提交的 1200×630 原创图片。维护者需要重绘时安装 Pillow 并显式指定本机中文字体，例如 `python tools/seo/social.py --font C:/Windows/Fonts/msyh.ttc`；常规构建不依赖 Pillow 或系统字体。预览站图片 URL 随 `site_url` 生成，不能固定引用生产域名。
