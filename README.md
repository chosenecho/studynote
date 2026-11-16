# studynote

操作系统概论、计算机组成原理、计算机网络技术和多媒体技术的章节笔记与交互练习，使用 MkDocs Material 发布。

网站：https://studynote.chosenecho.top/ · 仓库：https://github.com/chosenecho/studynote

课程资料唯一取自 OCR 仓库的“成书”，按校验过的私有快照写作，来源规则见 [内容贡献规则](handbook/content-policy.md)。

公开内容以大纲为索引，提供原创讲解、练习和概念图；第三方资源保持原许可。当前修订版的范围与历史副本的处理边界见许可说明。

- [操作系统概论](docs/courses/operating-systems/index.md)
- [计算机组成原理](docs/courses/computer-organization/index.md)
- [计算机网络技术](docs/courses/computer-networks/index.md)
- [多媒体技术及应用（第三版）](docs/courses/multimedia-technology/index.md)：九章学习草稿，来源 OCR 尚未终校。
- [易错点](docs/reference/pitfalls.md) · [术语表](docs/reference/glossary.md)

## 本地运行

需要 Python 3.12（由 `.python-version` 固定）与 Node.js 22+；Python 依赖由 uv 管理，清单在 `pyproject.toml`，锁定在 `uv.lock`。在仓库根目录执行：

```sh
npm run uv:sync
npm ci
npm run dev
```

`npm run uv:sync` 经本地代理下载依赖，默认代理为 `http://127.0.0.1:10808`，改端口见 [tools/dev/uv.ps1](tools/dev/uv.ps1)；直连时用 `npm run uv:sync:direct`。打开 http://127.0.0.1:8000/。仅构建站点可直接执行 `npm run build`，产物写入 `dist/`。

## 目录

```text
docs/                    MkDocs 直接读取的站点源文件
  courses/               课程 index.md、chapter-NN.md 与随文 figures/
  reference/             易错点与术语表
  labs/                  交互练习页面
  assets/
    javascripts/         阅读交互与 labs/ 实验模块
    stylesheets/         阅读与实验样式
    images/              站点图标
    vendor/              保留原发行文件的 KaTeX
config/                  课程注册、大纲映射、引文登记、权利清单及 ESA 域名规则
theme/                   Material 模板覆盖
tools/
  mkdocs/                内容处理、许可分发与产物处理钩子
  checks/                结构、笔记、修订、权利与链接检查
  deploy/                ECS 发布、Nginx 配置与 ESA 规则同步
tests/                   单元测试与浏览器测试
handbook/                开发、部署与第三方资源维护说明
archive/                 可公开的内容整理与发布记录
LICENSES/                第三方声明、许可原文与对应源码
```

首页为 `docs/index.md`，课程入口为各课程的 `index.md`。源码文件名与网址一致，例如 `docs/courses/operating-systems/chapter-01.md` 对应 `/courses/operating-systems/chapter-01/`。构建直接处理源页面，许可下载通过 MkDocs 虚拟文件提供。

根目录保留 `mkdocs.yml`、依赖清单与许可入口。生产使用 ESA 加速与 ECS 静态托管，配置位于 `config/ecs-site.json` 和 `config/esa-site.json`。`local/` 用于私有教材和独立归档，`artifacts/` 用于报告与截图；它们和 `dist/` 均不提交。

## 检查与维护

```sh
npm run check
npx playwright install chromium
npm run test:browser
```

CI 执行同一套检查，其中包括 `npm run check:rights`，核验记录位于 [config/content-rights.json](config/content-rights.json)。普通构建和测试不会授予内容传播权限。

- [开发约定](handbook/development.md)
- [构建与部署](handbook/deployment.md)
- [KaTeX 维护](handbook/vendor/katex.md)
- [许可与版权](LICENSING.md)：代码采用 Apache-2.0，已核验的原创学习文字采用 CC BY 4.0；第三方资源与引文按来源分别处理。
- [第三方资源说明](THIRD_PARTY_NOTICES.md)
- [内容贡献规则](handbook/content-policy.md) · [整理记录](archive/README.md)
