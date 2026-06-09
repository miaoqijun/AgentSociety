# Changelog

本文件遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 格式，记录 **AgentSociety 2** 相关组件的可见变更。

| 组件         | 标识                    | 说明                                        |
| ------------ | ----------------------- | ------------------------------------------- |
| Python SDK   | `agentsociety2`         | `packages/agentsociety2`，PyPI / 私有源发版 |
| VS Code 扩展 | `ai-social-scientist`   | `extension/package.json` 中的版本号         |
| 分析技能     | `agentsociety-analysis` | 随扩展同步至工作区 `.claude/skills/`        |

Git 发版标签：`agentsociety2-v{major}.{minor}.{patch}`（见 `CONTRIBUTING.md`）。

---

## [Unreleased]

## [2.5.4] - 2026-06-09

- **agentsociety2** `2.5.4` · **extension** `1.5.4` · 标签 `agentsociety2-v2.5.4`

### Added

- **extension**：配置页支持通过 Casdoor Device Flow 从 AgentSociety Web 导入 LiteLLM、Claude Code 与 EasyPaper 配置，登录凭据缓存至用户目录 `~/.fiblab/`。
- **extension**：导入模型列表后，默认 LLM、专用模型、Embedding、Claude Code 与 EasyPaper 模型字段提供可编辑候选项。
- **extension**：EasyPaper 导入时自动配置 LLM 与 VLM 的模型、Base URL 和 API Key。

### Changed

- **extension**：Web 导入配置需用户确认后才填入表单，仍需手动保存。
- **extension**：Claude Code 导入保留 LiteLLM Base URL 原值，不再自动追加 `/anthropic`。

### Fixed

- **extension**：修复 Webview 配置页导入按钮 i18n key 直出问题。
- **extension**：修复 EasyPaper VLM 开关无法正常操作的问题。
- **extension**：修复 Device Flow 默认 client id 导致线上 Casdoor 返回 `Invalid client_id` 的问题。
- **agentsociety2**：同步包内 `agentsociety2.__version__` 到发布版本。

## [2.5.3] - 2026-05-30

- **agentsociety2** `2.5.3` · **extension** `1.5.3` · 标签 `agentsociety2-v2.5.3`

本版本在 [2.5.2] 基础上进行 **依赖升级**、**分析 harness 增强** 与 **扩展 UX/健壮性改进**。

### Added

- **analysis**：CLI 新增 `guidance`、`payload-template`、`chart-scaffold` 子命令，内置分析指引与 JSON 模板。
- **analysis**：交互式 EDA 嵌入报告（`report_eda_embed.py`），支持在 HTML 报告中嵌入可视化图表。
- **analysis**：经验记忆闭环（experience memory），跨分析会话积累反馈。
- **analysis**：更严格的 phase gate 与扩展的 skill references。
- **analysis**：新增 `chart_export.py`（817 行）、`harness/guidance.py`（473 行）等模块。
- **docs**：中文 README（根目录 `README_zh.md` 与 `packages/agentsociety2/README_zh.md`）。
- **docs**：`AGENTS.md` 从符号链接改为独立文档，适配 Cursor 等编辑器。
- **extension**：新增 3 个 analysis support skills（`interactive-viz`、`report-blocks`、`scientific-visualization`）。

### Changed

- **extension**：默认 LLM 模型对齐为 `gpt-5.5`。
- **extension**：`engines.vscode` 降至 `^1.95.0`，兼容 Cursor（基于 VS Code 1.105.x）。
- **extension**：工作区缺失目录/文件时自动修复，不再显示修复按钮和确认对话框。
- **extension**：缺少 `.env` 时自动创建模板并引导配置 API key。
- **extension**：`initProject` 去掉已存在时的确认对话框（`init()` 本身幂等）。
- **extension**：技能同步成功时不再弹窗，仅失败/异常时提示。
- **extension**：扫描自定义模块时去掉多余的"Scanning..."开始通知。
- **extension**：后端配置错误时按钮直接打开配置页（而非手动编辑 `.env` 文件）。
- **deps**：刷新根 `uv.lock`、`agentsociety-community/uv.lock`、`package-lock.json` 等全部 lock 文件。

### Fixed

- **extension**：`git clone` 操作现在检查返回状态码，失败时抛出明确错误。
- **extension**：`autoCommit` 的 git 操作改为返回 `boolean`，失败时提前终止并记录日志。
- **extension**：`autoCommit` 中 `git config user.name` 空字符串检测修复。
- **extension**：ZIP 导出本地文件时改为流式 `copyFile`，不再将整个 ZIP 读入内存。
- **extension**：ZIP 导出增加系统 `zip` 命令作为 Python 的后备方案。
- **extension**：导出扫描中的 `readdirSync` 增加 try-catch 保护。
- **extension**：孤立后端进程健康检查增加一次 2 秒延迟重试，避免误杀启动中的后端。
- **extension**：临时目录改用 `fs.mkdtempSync()`，消除竞态条件风险。

### Changed (from previous Unreleased)

- **docs**：新增根目录与 `packages/agentsociety2` 的中英文 README（`README_zh.md`），同步 Sphinx 贡献指南与 API 示例。
- **docs**：将 `AGENTS.md` 从 `CLAUDE.md` 软链拆为独立 Cursor Agent 入口；修正 `cliff.toml` 对 `docs(...)` commit 的匹配。
- **docs**：更新 `README.md`、`CONTRIBUTING.md`、`SECURITY.md`，补充发版流程与 CI 范围说明。
- **analysis**：分析 harness 增加经验记忆闭环（`draft-reflection` / `promote-reflection` / `memory-context`）及更严格的 phase 门禁。
- **analysis**：分析技能 stages 补充外部工具调用链（integrations.md）与 Stage 6 必做经验沉淀；support 包在 explore/refine/produce 阶段显式启用。
- **extension**：默认 LLM 模型对齐为 `gpt-5.5`。
- **ci**：收窄检查范围至 AgentSociety2（`packages/agentsociety2`、`extension`、`frontend`）；legacy 包不纳入活跃 CI / Dependabot / CodeQL 扫描。
- **ci**：修复 frontend 全量 ESLint 错误（类型化、`unused-vars` 清理、Workflow 分支逻辑）；CI 保留 lint + build + audit。
- **ci**：发版前增加 validate 门禁；GitHub Release 说明改用 git-cliff。
- **deps**：刷新根 `uv.lock`（`sphinx-intl`、`urllib3`、`pytest` 等）；extension 升级 `ajv`、`@types/vscode`；frontend 升级 `typescript-eslint`、`@types/react-plotly.js`；GitHub Actions 升级 `dependency-review-action` v5、`download-artifact` v8。

---

## [2.5.2] - 2026-05-29

- **agentsociety2** `2.5.2` · **extension** `1.5.2` · 标签 `agentsociety2-v2.5.2`

本版本在 [2.5.1] 基础上完成 **paper 技能外迁**、**安全加固** 与 **依赖漏洞修复**；Python 安装：`pip install agentsociety2==2.5.2`。

### Removed

- **agentsociety2**：内置 `paper` 研究技能套件（`agentsociety-paper-adapter` / `agentsociety-paper-architecture` / `agentsociety-paper-evidence-architect`），论文生成迁移至独立的 `paper-toolkit` plugin。
- **extension**：移除 legacy paper skill 注册条目；`ags.py` 中已无 paper 子命令入口。

### Changed

- **docs**：根 `CLAUDE.md`、`workspace/CLAUDE.md`、`workspace/AGENTS.md` 指引由 `agentsociety-paper-orchestrator` 更新为引用外部 `paper-toolkit` plugin（确定性 CLI + companion Claude Code 写作 / 审阅 skill）。

### Fixed

- **agentsociety2**：后端路径解析增加 `..` / 空字节校验，消除 CodeQL 路径注入告警（`path_security.py`）。
- **agentsociety2**：LLM Router 调试日志不再经含 API Key 的配置对象传递，避免敏感信息日志泄露。
- **extension**：`.env` 写入时对 API Key 等值做完整转义（`\`、`"`、换行、`$` 等）。
- **extension**：升级 `tmp`、`qs` 传递依赖，修复 `npm audit --audit-level=high` 失败。
- **frontend**：升级 `fast-uri`、`fast-xml-builder`，并通过 `path-to-regexp` override 修复高危 npm 审计项。
- **deps**：根 `uv.lock` 升级 `urllib3`、`idna`、`pytest`（仍使用清华 tuna 镜像源）。
- **ci**：新增 CodeQL 配置，排除 `frontend/public/monaco-editor` 第三方 vendor 扫描误报。

---

## [2.5.1] - 2026-05-21

- **agentsociety2** `2.5.1` · **extension** `1.5.1` · 标签 `agentsociety2-v2.5.1`

本版本在 [2.4.1] 基础上交付**自适应 LLM 并发控制**、**Agent 技能与认知增强**、**CodeGenRouter 安全加固**及 VS Code 扩展多项体验改进；Python 安装：`pip install agentsociety2==2.5.1`。

### Added

- **agentsociety2**：自适应 LLM 并发控制，优化大规模智能体仿真吞吐量。
- **agentsociety2**：Agent 技能（agent-skill）重构改善；认知（cognition）模块增强情绪与意图状态管理。
- **agentsociety2**：mobility_space 模块在地图文件缺失时给出下载提示。
- **extension**：Claude Code 权限模式配置页面；移除 Stop hook。
- **extension**：HYPOTHESIS.md 与 EXPERIMENT.md 作为树节点固定展示。
- **extension**：工作区文件变更时强制 git 追踪。
- **docker**：运行时依赖新增 `python-dotenv`。

### Changed

- **agentsociety2**：时间上下文移至 prompt 末尾以提升缓存命中率。
- **ci**：配置变更时始终构建 Docker 镜像并运行完整 CI；无 Python 代码变更时跳过 lint/test。

### Fixed

- **docker**：统一 `python3` 路径，修复 apt 拉入不同版本后命令不可用的问题；确保 `python` 命令指向系统 Python。
- **extension**：autoCommit 因缺少 git identity 静默失败的问题。
- **agentsociety2**：mobility_space 缺少 `json` 和 `Path` 导入。
- **agentsociety2**：CodeGenRouter 沙箱加固与安全基准测试。

---

## [2.4.1] - 2026-05-20

- **agentsociety2** `2.4.1` · **extension** `1.4.1` · 标签 `agentsociety2-v2.4.1`

本版本在 [2.4.0] 基础上交付**分阶段分析 Harness**、**双语报告（MD + HTML）门禁**及扩展侧配套体验；Python 安装：`pip install agentsociety2==2.4.1`（或贵司私有源等价版本）。

### Added

#### 分析 Harness（`agentsociety2` + `agentsociety-analysis`）

- 假设分析五阶段流水线：`frame` → `explore` → `claims` → `refine` → `produce`；机器状态位于 `.agentsociety/analysis/hypothesis_{id}/`，与用户可见目录 `presentation/hypothesis_{id}/` 分离。
- 结构性校验与 LLM 阶段 attestation 双层门禁；`validate-<phase>`、`record-attestation`、`gate-status`；未通过前置阶段时后续阶段阻断。
- `refine`：`validate-refine`、`validate-chart`；`produce`：`validate-release`（四份报告必交）、`validate-report-quality`、独立 `record-report-review`。
- 工作区综合阶段：`validate-synthesis`、`synthesis_brief.json`、双语综合报告；支持 `synthesis/charts/` 与 `synthesis/assets/`。
- CLI：`intake`、`build-report-context`、`sync-report-assets`、`advance`、`run-loop` 等；技能脚本 `ags.py analysis` 与 harness 对齐。
- 报告 HTML 由 LLM 按 `assets/report-shell.reference.html` 原生撰写；`support/frontend-design` 随分析技能同步至工作区。
- 测试套件 `tests/test_analysis_harness.py`。

#### VS Code 扩展

- 分析阶段进度树与 Harness 状态查看器（`analysisHarnessStatusViewer`）。
- 假设 / 综合报告树固定展示 MD、HTML 中英四件套；缺失项标记「必交 · 未生成」。
- HTML 报告经 `aiSocialScientist.openHtmlReport` 打开 Live Preview（不可用则回退编辑器）。
- 产物目录：`分析数据`；`报告图表`（`assets/`）；`charts/` 仅在含脚本或未同步图片时显示，避免与 `assets/` 重复列举。

#### 后端与其它

- `path_security`：工作区路径解析与越界访问防护，接入 custom、experiments、prefill_params、replay 等路由。
- `env_benchmark`：`CodeGenRouter` 统一 `code_format` 参数，便于对比各 env router。

### Changed

- **agentsociety-analysis**：技能文档重组为 `stages/`、`references/`（`harness-contract`、`html-export`、`report-embeddings` 等）、`subagent-prompts/`；禁止在 `presentation/` 下使用旧版 `analysis/` 布局。
- **extension**：Claude Code 配置迁入配置页「高级配置」；读写 `ANTHROPIC_AUTH_TOKEN` 与 `ANTHROPIC_BASE_URL`；第三方网关预设区分 **DeepSeek**（`https://api.deepseek.com/anthropic`）与 **火山方舟**（`https://ark.cn-beijing.volces.com/api/plan`）。
- **extension**：文献检索改为 MCP 调用；移除独立 Claude 配置 Webview 与冗余静态 HELP 页。
- **docs**：Walkthrough 中 API / Claude Code 说明与上述环境变量保持一致。

### Fixed

- **extension**：Claude Code 误用 `ANTHROPIC_API_KEY` 的问题。
- **agentsociety2**：CodeQL 静态分析问题；分析 harness 与后端相关 ruff 项。
- **extension / literature**：文献技能 lint 与 MCP 路径问题。

### 升级说明

- 若工作区仍存在 `presentation/hypothesis_*/analysis/`，执行 `ags.py analysis intake --workspace . --hypothesis-id <ID> --experiment-id <ID>` 可将 harness 状态迁移至 `.agentsociety/analysis/`。
- 报告插图仅使用 `assets/` 路径；作图后运行 `sync-report-assets` 或 `collect-assets`，再执行 `validate-release`。

---

## [2.4.0] - 2026-05-19

- **agentsociety2** `2.4.0` · **extension** `1.4.0`

### Added

- **agentsociety2**：`CodeGenRouterV2`；Codex 技能符号链接；论文编排与分析图表能力增强；用户指南与中英文档补全。
- **extension**：AI Chat 多提供商集成；Claude Code 独立配置页（后续版本已并入高级配置）。
- **agentsociety2**：工作区引导与 `create-agent` / `create-env-module` 技能加固。

### Changed

- **agentsociety2**：Read the Docs 在 monorepo 下的构建配置与文档结构更新。
- **extension**：CSV 表格可视化；实验状态总览与步骤配置体验优化；项目树图标与右键菜单修正。

### Fixed

- **extension**：技能启动器工作区默认值；VS Code `when` 子句取反语法。
- **agentsociety2**：Agent 运行兜底，降低实验异常中断影响。
- **ci**：npm audit 阈值调整为 `high`，恢复流水线通过。

---

## [2.3.0] - 2026-05-08

- **agentsociety2** `2.3.0` · **extension** `1.2.0`

### Added

- **agentsociety2**：LaTeX 论文编排流水线（替代 EasyPaper）；PersonAgent 技能扩展；后端 API 与实验目录布局完善。
- **extension**：技能市场（GitHub 源）、Agent / Claude 技能分栏管理；前端 Skills 管理页。
- **agentsociety2**：Sphinx 文档站、技能文档与英文 locale；GitHub / GitLab CI 与扩展 CI 流水线。

### Changed

- **extension**：HTML 分析报告预览交互修复。
- **repo**：根目录说明、`.gitignore` 与 Docker 构建清理。

### Fixed

- **paper / literature**：技能与流水线若干缺陷修复。
- **ci**：MR 与主分支流水线稳定性改进。

---

## [2.2.0] - 2026-04-19

- **agentsociety2** `2.2.0` · **extension** `1.0.0`

### Added

- **extension**：技能市场；项目结构树增强；实验状态概览；环境 / 智能体预填充参数；中英国际化与用户向文案（详见 `extension/README.md`）。
- **agentsociety2**：对话历史持久化相关能力；社区文档（行为准则、贡献指南、安全策略）。

### Changed

- **agentsociety2**：自 `2.1.5` 对齐主分支能力后正式发版；安装示例：`pip install agentsociety2==2.2.0`。
- **extension**：技能管理界面重构。

### Fixed

- **extension**：分析报告展示问题。
- **agentsociety2**：速率限制与 JSON 工具类重复定义等 Agent 层问题。

---

## [2.1.5] - 2026-04-15

- **agentsociety2** `2.1.5` · **extension**（持续迭代，见同期 commit）

### Added

- **extension**：PID 状态可视化；文献路径复制与 @ 提及；数据集技能与树节点集成。
- **agentsociety2**：问卷与回复流增强；文献搜索 API 切换至新服务端点。
- **extension**：MinerU 相关能力调整为官方 Claude Office 技能方案。

### Changed

- **extension**：国际化与可视化查看器；构建配置与文档对齐。
- **ci**：发布流水线与 ruff 策略调整，保障发版通过。

### Fixed

- **ci**：MR 流水线仅做构建验证，避免多余 registry 登录。

---

## [2.1.0] - 2026-03-20

- **agentsociety2** `2.1.0`

### Added

- **agentsociety2**：分析 / 综合报告中英双语输出。
- **extension**：文献检索后端地址写入配置页。
- **extension**：文献库层级目录；树视图拖放导入 PDF / 文件。

### Changed

- **extension**：PDF 自动解析模式与状态栏开关。

### Fixed

- **agentsociety2**：实验启动流程；自定义模块测试脚本缩进与错误回传；`agent.init()` 调用方式。

---

## [2.0.2] - 2026-03-06

- **agentsociety2** `2.0.2`

### Added

- **extension**：项目树拖放与相关 i18n。
- **docs**：中英双语文档初版；PDF 自动解析。

### Fixed

- **extension**：预填充参数树图标；自定义模块集成测试错误字段。

---

## [2.0.1] - 2026-03-05

- **agentsociety2** `2.0.1`

### Added

- **docs**：自定义模块文档；Read the Docs 配置拆分（v1 / AgentSociety 2）。

### Changed

- **docs**：站点样式与导航（含 V2 Beta 入口）。

### Fixed

- **agentsociety2**：线程与重试相关边缘问题。
- **docs**：RTD 依赖路径与构建配置。

---

## [2.0.0] - 2026-03-05

- **agentsociety2** `2.0.0` · **extension** `0.0.1`（初始集成）

### Added

- **agentsociety2**：面向二次开发的自定义模块（Custom Agent / Env）扫描、生成与后端集成。
- **extension**：AI Social Scientist 工作区、项目树与实验工作流初版。

---

## AgentSociety 1.x 及更早版本

以下条目为 **AgentSociety 1.x**（及更早标签）的逐版本记录，与 2.x 包 `agentsociety2` 产品线分离。2.x 用户通常只需阅读上文 **2.0.0** 及以上章节。

## [1.4.0a0] - 2025-05-12

### Added
- N/A

### Changed
- N/A

### Deprecated
- N/A

### Fixed
- N/A

## [1.3.7] - 2025-04-28

### Added
- N/A

### Changed
- Update wechat group QR code.

### Deprecated
- N/A

### Fixed
- N/A


## [1.3.6] - 2025-04-17

### Added
- N/A

### Changed
- N/A

### Deprecated
- N/A

### Fixed
- Refactor chat history gathering to handle grouped data structure across multiple files, ensuring consistent data format for agent interactions.
- Fix the `from pyparsing import deque` error.


## [1.3.5] - 2025-04-14

### Added
- Add automatic monitoring of LLM requests, if a request is stuck for a long time, it will be logged.
    - To use this feature, you need to set `logging_level` to `DEBUG` in `AdvancedConfig`.

### Changed
- N/A

### Deprecated
- N/A

### Fixed
- Fix bug in survey dispatching.
- Fix bug in inconsistent schema when writing survey results to SQL.

## [1.3.4] - 2025-04-14

### Added
- Add docs for `reset` method in `Agent` and `Block`.

### Changed
- Return 404 rather than 200 for empty delete/update.
- Move webui config into database.

### Deprecated
- N/A

### Fixed
- Solve the problem of not being able to exit.
- Fix raising error when from memory.
- Enhance lock_decorator with exception logging for better error tracking.
- Fix bug in `NeedsBlock`.

## [1.3.3] - 2025-04-07

### Added
- Add `input_tokens` and `output_tokens` to experiment info.
- Add S3 storage support.
- Web API to export experiment data including agent profiles, agent statuses, agent dialogs, agent surveys, and global prompts.
- Add `NEXT_ROUND` step type, support multiple rounds of simulation.
- Add abstract method `reset` for `Agent` and implement it for all city agents.

### Changed
- Hide sensitive experiment information in AVRO and PostgreSQL storage.
- UI details.
- Removed `total_tick` in `EnvironmentConfig` - always 24 hours.
- Support float days in `RUN` step, for example, `RUN: 1.5 days`.

### Deprecated
- `Tool` abstract class.

### Fixed
- Bug in avro saver.

## [1.3.2] - 2025-04-02

### Removed
- Remove useless files due to merge error

## [1.3.1] - 2025-04-02

### Changed
- Update Python version requirements and cibuildwheel skip list.

## [1.3.0] - 2025-04-02

See [Version 1.3](https://agentsociety.readthedocs.io/en/latest/02-version-1.3/01.v1.3.0.html) for more details.

## [1.2.10] - 2025-03-18

### Added
- N/A

### Changed
- Add retry for syncer connections.

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- Fix typo in `simulator.sence`

### Security
- N/A

## [1.2.9] - 2025-03-14

### Added
- N/A

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- Fixed bug for `update_environment` in `AgentGroup`.
- Bug for calling sequence of `agent.step` and `OnlyClientSidecar.step`.

### Security
- N/A

## [1.2.8] - 2025-03-14

### Added
- N/A

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- Fixed bug for `PlaceSelectionBlock.forward` when selecting POI.
- Bug for `OnlyClientSidecar` calling

### Security
- N/A

## [1.2.7] - 2025-03-14

### Added
- N/A

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- Fixed bug for `PlaceSelectionBlock.forward` when selecting POI.

### Security
- N/A

## [1.2.6] - 2025-03-12

### Added
- N/A

### Changed
- WeChat QR code.

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A
  
## [1.2.5] - 2025-03-07

### Added
- N/A

### Changed
- N/A

### Deprecated
- N/A

### Removed
- Remove `Agent._uuid`

### Fixed
- Fixed bug for `simulation.init_agents` when creating group parameters for agents.

### Security
- N/A



## [1.2.4] - 2025-03-04

### Added
- N/A

### Changed
- N/A

### Deprecated
- N/A

### Removed
- Remove `Agent._uuid`

### Fixed
- Fixed issue with `EconomyClient.update` when handling InstitutionAgent updates.
- Fixed bug for `MobilityBlock.MoveBlock.forward`.
- Added adjustment logic to ensure the sum of the returned employee counts exactly equals N in matching firms and employees.

### Security
- N/A


## [1.2.3] - 2025-03-03

### Added
- N/A

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- Fix typo in quick start docs.

### Security
- N/A



## [1.2.2] - 2025-03-02

### Added
- N/A

### Changed
- Change the download URL for `agentsociety-sim` to a publicly accessible address that does not require authentication in `setup.py`.

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- Missed match between the dictionary and `economyv2.Firm` as input arguments in the `EconomyClient.update` method.

### Security
- N/A



## [1.2.1] - 2025-03-01

### Added
- Add docker compose for china user (use huawei cloud docker registry)

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- Definition bug of `EconomyEntityType`

### Security
- N/A


## [1.2.0] - 2025-02-28

### Added
- N/A

### Changed
- Update `pycityproto` version to v2.2.8, splitting organization into bank, firm, government and statistical bureau.
- Adapt `environment.economy` to align with the new definitions of economic entities.

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A

## [1.1.5] - 2025-02-28

### Added
- N/A

### Changed
- Update doc at `05-custom-agents`.
- Add more comments in agentsociety.cityagent

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A



## [1.1.4] - 2025-02-27

### Added
- Add log of original LLM response during handling LLM calling error.

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A

## [1.1.3] - 2025-02-27

### Added
- N/A

### Changed
- The WeChat group chat QR code has been replaced to the second group. Welcome to join and participate in the discussions.

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- Add retry for `syncer` server connecting, providing enough time for start.

### Security
- N/A


## [1.1.2] - 2025-02-26

### Added
- N/A

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- Calling `syncer` that didn't have time to start causes the gRPC service to report an error.

### Security
- N/A

## [1.1.1] - 2025-02-25

### Added
- N/A

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- Inconsistency of python 3.12 and current pydantic version. 

### Security
- N/A


## [1.1.0] - 2025-02-21

### Added
- N/A

### Changed
- The simulator has been converted to a synchronous mode, controlled by `ExpConfig.SimulatorConfig.steps_per_simulation_step` and `ExpConfig.SimulatorConfig.steps_per_simulation_day` parameters that determine the number of seconds per step for advancing the urban environment time in each simulation step and day.

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A

## [1.0.13] - 2025-02-21

### Added
- N/A

### Changed
- N/A

### Deprecated
- N/A

### Removed
- Delete `enable_institution` in ExpConfig

### Fixed
- N/A

### Security
- N/A

## [1.0.12] - 2025-02-21

### Added
- N/A

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- Document typo on `agentsociety-ui` activation.

### Security
- N/A

## [1.0.11] - 2025-02-21

### Added
- N/A

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- Bug of inconsistent length of `agent_counts` and `agent_class` in `simulation.init_agents`.

### Security
- N/A

## [1.0.10] - 2024-02-21

### Added
- N/A

### Changed
- Example map data download link in the document.

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A

## [1.0.9] - 2024-02-20

### Added
- WeChat group QR code.

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A
  
## [1.0.8] - 2024-02-19

### Added
- N/A

### Changed
- Detailed document.

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A
 
## [1.0.7] - 2024-02-18

### Added
- N/A

### Changed
- Update agentsociety-ui to version v0.3.3.

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A
  
## [1.0.6] - 2024-02-18

### Added
- N/A

### Changed
- Detailed document.

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A
  
## [1.0.5] - 2024-02-15

### Added
- N/A

### Changed
- Set parent_id and lnglat of InstitutionAgent as NULL for pgsql

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A

## [1.0.4] - 2024-02-14

### Added
- N/A

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- Bug of incorrect experiment uid for MLflow tag.

### Security
- N/A

## [1.0.3] - 2024-02-13

### Added
- Social experiment use case document.

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- 

### Security
- N/A

## [1.0.2] - 2024-02-08

### Added
- Social experiment use case with our platform.

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A

## [1.0.1] - 2024-02-07

### Added
- Add `README.md`

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A

## [1.0.0] - 2024-02-06

### Added
- Initial commit.

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A
