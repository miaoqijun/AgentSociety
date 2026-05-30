# AgentSociety: 社会中的 LLM 智能体

<p align="center">
  <a href="./README.md">English</a> · <a href="./README_zh.md">中文</a>
</p>

AgentSociety 是用于构建 LLM 驱动智能体仿真、城市环境实验与科研工作流的开源框架。本仓库同时维护推荐使用的 **AgentSociety 2** 与旧版 **AgentSociety 1.x**。

论文见 [arXiv](https://arxiv.org/abs/2502.08691)。

## 包结构

### AgentSociety 2（推荐）

AgentSociety 2 是现代化的 LLM 原生智能体仿真与科研平台，重点支持：

- 基于 `PersonAgent` 的 skills-first 人物智能体
- 模块化环境与 `CodeGenRouter`
- SQLite replay 与 agent workspace 双路径记录
- 文献、假设、实验配置、运行、分析，以及论文工作流（通过外部 `paper-toolkit` 插件）
- FastAPI 后端、VS Code 扩展与 React 前端

安装：

```bash
pip install agentsociety2
```

文档：

- [AgentSociety 2 文档](https://agentsociety2.readthedocs.io/)
- [包内 README](./packages/agentsociety2/README_zh.md)
- [源码](./packages/agentsociety2/)

### AgentSociety 1.x（旧版）

AgentSociety 1.x 是原始的城市仿真框架，包含 gRPC 环境集成、城市移动/经济/社会模块和分布式仿真能力。

```bash
pip install agentsociety
```

文档：[agentsociety.readthedocs.io](https://agentsociety.readthedocs.io/)

## 其他包

以下 legacy 包仍保留在 monorepo 中，但**不在活跃开发、CI 或安全扫描范围内**：

- **[agentsociety-community](./packages/agentsociety-community/)**：社区贡献的自定义 agent 与 block（legacy）
- **[agentsociety-benchmark](./packages/agentsociety-benchmark/)**：智能体评测基准工具（legacy）

当前活跃维护范围：`packages/agentsociety2/`、`extension/`、`frontend/`。详见 [`.github/agentsociety2-scope.yml`](./.github/agentsociety2-scope.yml)。

## 发版

AgentSociety 2 使用语义化版本，Git 标签格式：

```text
agentsociety2-v{major}.{minor}.{patch}
```

例如 `agentsociety2-v2.5.2` 会发布：

- **PyPI**：`agentsociety2==2.5.2`
- **VS Code 扩展**：`ai-social-scientist`（版本见 `extension/package.json`）
- **GitHub Release**：wheel、sdist 与 `.vsix`

变更记录：[CHANGELOG.md](./CHANGELOG.md)

## 仓库目录

```text
AgentSociety/
├── packages/
│   ├── agentsociety2/      # v2.x，当前推荐包
│   ├── agentsociety/       # v1.x，旧版城市仿真
│   ├── agentsociety-community/
│   └── agentsociety-benchmark/
├── frontend/               # React 前端
├── extension/              # VS Code 扩展
├── docs_v1/                # v1 文档
└── examples/               # 示例实验
```

## AgentSociety 2 快速示例

运行示例前请先配置 LLM 环境变量，例如：

```bash
export AGENTSOCIETY_LLM_API_KEY="your-api-key"
export AGENTSOCIETY_LLM_API_BASE="https://api.openai.com/v1"
export AGENTSOCIETY_LLM_MODEL="gpt-5.5"
```

最小示例：

```python
import asyncio
from datetime import datetime

from agentsociety2 import PersonAgent
from agentsociety2.contrib.env import SimpleSocialSpace
from agentsociety2.env import CodeGenRouter
from agentsociety2.society import AgentSociety


async def main():
    agent = PersonAgent(
        id=1,
        profile={"name": "Alice", "personality": "friendly and curious"},
    )
    env = CodeGenRouter(
        env_modules=[SimpleSocialSpace(agent_id_name_pairs=[(agent.id, agent.name)])]
    )
    society = AgentSociety(agents=[agent], env_router=env, start_t=datetime.now())
    await society.init()
    print(await society.ask("What's your name?"))
    await society.close()


asyncio.run(main())
```

## 开发

```bash
uv sync
uv run pytest packages/agentsociety2
uv run ruff check packages/agentsociety2
```

前端：

```bash
cd frontend
npm install
npm run dev
```

VS Code 扩展：

```bash
cd extension
npm install
npm run build
```

## 联系方式

- **Issues**：[GitHub Issues](https://github.com/tsinghua-fib-lab/agentsociety/issues)
- **安全报告**：见 [SECURITY.md](./SECURITY.md)
- **Discussions**：[GitHub Discussions](https://github.com/tsinghua-fib-lab/agentsociety/discussions)
- **贡献指南**：[CONTRIBUTING.md](./CONTRIBUTING.md)
- **Agent 指南**（Cursor / 编码 Agent）：[AGENTS.md](./AGENTS.md)
- **邮箱**：agentsociety.fiblab2025@gmail.com

## 许可证

AgentSociety 采用 Apache License 2.0，`packages/agentsociety/commercial` 目录除外。详见 [LICENSE](./LICENSE)。

## 引用

```bibtex
@article{piao2025agentsociety,
  title={AgentSociety: Large-Scale Simulation of LLM-Driven Generative Agents Advances Understanding of Human Behaviors and Society},
  author={Piao, Jinghua and Yan, Yuwei and Zhang, Jun and Li, Nian and Yan, Junbo and Lan, Xiaochong and Lu, Zhihong and Zheng, Zhiheng and Wang, Jing Yi and Zhou, Di and others},
  journal={arXiv preprint arXiv:2502.08691},
  year={2025}
}
```
