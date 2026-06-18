# AgentSociety: 社会中的 LLM 智能体

<p align="center">
  <a href="./README.md">English</a> · <a href="./README_zh.md">中文</a>
</p>

AgentSociety 是用于构建 LLM 驱动智能体仿真、城市环境实验与科研工作流的开源框架。本仓库同时维护推荐使用的 **AgentSociety 2** 与旧版 **AgentSociety 1.x**。

论文见 [arXiv](https://arxiv.org/abs/2502.08691)。

## 包结构

### AgentSociety 2（推荐）

AgentSociety 2 是现代化的 LLM 原生智能体仿真与科研平台，重点支持：

- 基于 `AgentBase` / `PersonAgent` 的 workspace 绑定智能体（无状态 record，由 Ray Task 流式驱动）
- 模块化环境与 `CodeGenRouter`（含 ReAct / Plan-Execute / Two-Tier / Search 路由器）
- 经单一 `ServiceProxy` 注入 env / LLM clients / trace / replay 句柄
- JSONL replay（catalog-driven，DuckDB 读侧）+ 分布式 trace + agent workspace 多路径记录
- 文献、假设、实验配置、运行、分析和论文写作等研究技能
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
from pathlib import Path

from agentsociety2.contrib.env import SimpleSocialSpace
from agentsociety2.env import CodeGenRouter
from agentsociety2.society import AgentSociety


async def main():
    # 智能体以 spec 元数据声明；AgentSociety 在 init 时批量创建 workspace
    agent_specs = [{"id": 1, "profile": {"name": "Alice"}, "config": {}}]
    env = CodeGenRouter(
        env_modules=[SimpleSocialSpace(agent_id_name_pairs=[(1, "Alice")])]
    )
    society = AgentSociety(
        agent_specs=agent_specs,
        agent_class_name="PersonAgent",
        env_router=env,
        start_t=datetime.now(),
        run_dir=Path("run"),
    )
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
