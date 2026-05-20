# Changelog

## [2.4.1] - 2026-05-20

本版本在 `2.4.0` 基础上合并分析 Harness、扩展与技能包的一轮大更新；Python 包版本 `agentsociety2==2.4.1`，VS Code 扩展 `ai-social-scientist` **1.4.1**。

### Added

#### 分析 Harness（`agentsociety2` + `agentsociety-analysis` 技能）

- **五阶段假设分析流水线**（`frame` → `explore` → `claims` → `refine` → `produce`），状态与计划写入 `.agentsociety/analysis/hypothesis_{id}/`（`state.yaml`、`analysis_plan.yaml`、`claims.json`），与 `presentation/hypothesis_{id}/` 用户可见产物分离。
- **结构性校验 + 阶段 attestation 双层门禁**：`validate-<phase>`、`record-attestation`、`gate-status`；前置阶段未 `gate_pass` 时后续阶段阻断（`prior_phase_gate_issues`）。
- **`refine` 整体验证**：`validate-refine` 检查 figure contract 与 `charts/` 落盘；`validate-chart` 校验作图脚本命名与安全约束。
- **`produce` 发布校验**：`validate-release` 要求四份报告（`report_zh/en.md` + `report_zh/en.html`）、`report_outline.json`、`artifact_manifest.json`、`data/analysis_summary.json`；校验报告内 `assets/` 引用与磁盘一致，禁止正文引用 `charts/`；发布前自动 `sync-report-assets`（从 `charts/` 补齐 `assets/`）。
- **报告质量与独立评审**：`validate-report-quality`（篇幅、图表说明、主张对齐等机械检查）；`record-report-review` / `record-synthesis-review` + `validate_report_review`，未通过或指纹过期则 `validate-release` / `validate-synthesis` 阻断。
- **综合阶段（Stage 6）**：`synthesis_brief.json`、双语综合报告（MD+HTML）、`validate-synthesis`；支持 `synthesis/charts/` 与 `synthesis/assets/`。
- **CLI / `ags.py analysis` 子命令**：`intake`、`write-plan`、`build-report-context`、`sync-report-assets`、`record-claim`、`record-contract`、`record-phase-artifacts`、`advance`、`run-loop` 等；技能内 `scripts/analysis.py` 与 harness 对齐。
- **HTML 报告规范**：LLM 按 `assets/report-shell.reference.html` 原生撰写双语 HTML（非 Markdown 机械转换）；`support/frontend-design` 随分析技能同步到工作区。
- **测试**：`tests/test_analysis_harness.py`（门禁、release、图表同步、前置阶段阻断等）。

#### VS Code 扩展 `ai-social-scientist` 1.4.1

- **分析进度树**：假设下展示五阶段进度（`analysisHarnessStatusViewer`）；点击可查看 harness 状态与校验摘要。
- **报告节点**：固定展示四份必交报告；缺失显示「必交 · 未生成」；Markdown 预览、HTML 经 `aiSocialScientist.openHtmlReport` 走 Live Preview（失败回退编辑器）。
- **产物目录**：`分析数据`；`报告图表`（`assets/`）；`charts/` 仅在含脚本或未同步图片时显示，避免与 `assets/` 重复列表。
- **综合报告树**：与假设分析相同的四报告位 + `x/4 份报告` 计数；支持 `charts/` / `assets/` / `data/`。
- **Claude Code 配置**（高级配置 Tab）：读写 `ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_BASE_URL`；预设网关含 **DeepSeek**（`api.deepseek.com/anthropic`）与 **火山方舟**（`ark.cn-beijing.volces.com/api/plan`）分列；自定义预设不再默认填入 Anthropic 官方 URL。

#### 后端与其它

- **`path_security`**：工作区路径解析与越界访问防护，接入 custom / experiments / prefill_params / replay 等路由。
- **`env_benchmark.py`**：`CodeGenRouter` 统一 `code_format` 参数，便于对比各 env router。
- **文献检索**：扩展侧文献能力改为 MCP 调用路径（配合技能与后端调整）。

### Changed

- **`agentsociety-analysis` v1.0.0**：技能文档拆分为 `stages/`、`references/`（`harness-contract`、`html-export`、`report-embeddings`、`phase-attestation` 等）、`subagent-prompts/`（report/synthesis producer & reviewer）；`output-conventions` 明确禁止 `presentation/.../analysis/` 旧布局。
- **扩展配置页**：原独立 Claude Code Webview 并入主配置页「高级配置」；删除冗余 HELP 静态页，说明迁入 walkthrough / README。
- **Walkthrough**：API 配置与 Claude Code 章节更新（第三方 Base URL、Token 变量名）。

### Fixed

- **Claude Code**：修复误用 `ANTHROPIC_API_KEY` 的问题，与官方环境变量 `ANTHROPIC_AUTH_TOKEN` 一致。
- **CodeQL**：修复路径拼接、SQL 与相关静态分析问题（`b345d34f`）。
- **CI**：修复 analysis harness / 后端等文件的 ruff 未使用导入与 `ValidationResult` 类型注解（`F821`/`F401`）。

### 升级提示

- 已有工作区若仍含 `presentation/hypothesis_*/analysis/`，运行 `ags.py analysis intake` 可迁移 harness 状态至 `.agentsociety/analysis/`。
- 发版标签：`agentsociety2-v2.4.1`（GitLab `generate-changelog` / `create-release` 流水线依赖该命名）。

## [2.2.0] - 2026-04-18

### Added
- **VS Code 扩展 `ai-social-scientist` 1.0.0**：技能市场（GitHub 源）、Agent / Claude 分栏技能管理、项目结构增强、实验状态概览、预填充参数与国际化/用户向文案等（详见扩展发版说明与 `extension/README.md`）。

### Changed
- **Python 包 `agentsociety2` 2.1.5 → 2.2.0**：与当前主分支能力对齐发版；若从 PyPI/私有源安装，请使用 `pip install agentsociety2==2.2.0`（或贵司实际发布渠道）。

### Fixed
- N/A

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
