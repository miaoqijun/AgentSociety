# AgentSociety 2

<p align="center">
  <a href="./README.md">English</a> · <a href="./README_zh.md">中文</a>
</p>

AgentSociety 2 是面向计算社会科学的现代化、LLM 原生智能体仿真与科研平台。它把智能体、环境模块、实验运行、replay 存储和研究技能组织在一个统一的 Python 包中，并可通过 CLI、FastAPI 后端和 VS Code 扩展使用。

## 安装

```bash
pip install agentsociety2
```

要求：

- Python >= 3.11
- 一个 LiteLLM 支持的 LLM API Key

## 快速开始

运行示例前请先配置 LLM 环境变量。`agentsociety2` 会在导入时校验这些变量：

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
        profile={
            "name": "Alice",
            "age": 28,
            "personality": "friendly and curious",
        },
    )
    social_env = SimpleSocialSpace(agent_id_name_pairs=[(agent.id, agent.name)])
    env_router = CodeGenRouter(env_modules=[social_env])
    society = AgentSociety(
        agents=[agent],
        env_router=env_router,
        start_t=datetime.now(),
    )

    await society.init()
    print(await society.ask("What's your favorite activity?"))
    await society.close()


asyncio.run(main())
```

## 核心概念

- **PersonAgent**：默认人物智能体。采用 metadata-first 的 skill 选择模型，每个 step 通过工具循环按需激活技能。
- **Agent Skills**：内置 `observation`、`cognition`、`plan`、`memory`，自定义技能放在 `custom/skills/`。
- **Environment Modules**：继承 `EnvBase`，通过 `@tool` 暴露可观察、统计和读写工具。
- **CodeGenRouter**：推荐的环境路由器，将自然语言环境指令转换为可执行工具调用。
- **ReplayWriter**：SQLite replay dataset 写入器。新实验使用 catalog-driven dataset，不再写旧的 `agent_profile` / `agent_status` / `agent_dialog` 表。
- **Agent Workspace**：每个 `PersonAgent` 在 `run/agents/agent_xxxx/` 下维护本地状态、线程日志和工具调用记录。

## 配置

必需：

```bash
export AGENTSOCIETY_LLM_API_KEY="your-api-key"
export AGENTSOCIETY_LLM_API_BASE="https://api.openai.com/v1"
export AGENTSOCIETY_LLM_MODEL="gpt-5.5"
```

可选：

```bash
export AGENTSOCIETY_CODER_LLM_MODEL="gpt-5.5"
export AGENTSOCIETY_NANO_LLM_MODEL="gpt-5.5"
export AGENTSOCIETY_EMBEDDING_MODEL="text-embedding-3-large"
export AGENTSOCIETY_EMBEDDING_DIMS="1024"
export AGENTSOCIETY_HOME_DIR="./agentsociety_data"
```

源码仓库中也可以从根目录复制 `.env.example`：

```bash
cp .env.example .env
```

## CLI 运行实验

```bash
python -m agentsociety2.society.cli \
  --config my_experiment/init/init_config.json \
  --steps my_experiment/init/steps.yaml \
  --run-dir my_experiment/run \
  --log-level INFO \
  --log-file my_experiment/run/output.log
```

后台运行时请务必指定 `--log-file`。

## 后端服务

```bash
python -m agentsociety2.backend.run
```

默认地址：

- API: http://localhost:8001
- Swagger: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc

## 文档与开发

- 在线文档（英文）：https://agentsociety2.readthedocs.io/
- 在线文档（中文）：https://agentsociety2.readthedocs.io/zh_CN/latest/
- 仓库根目录中文说明：[../../README_zh.md](../../README_zh.md)
- 开发指南：[docs/development.rst](./docs/development.rst)
- 贡献指南：[../../CONTRIBUTING.md](../../CONTRIBUTING.md)
- 安全政策：[../../SECURITY.md](../../SECURITY.md)

开发常用命令：

```bash
uv sync
uv run pytest packages/agentsociety2
uv run ruff check packages/agentsociety2
uv run ruff format packages/agentsociety2
```

## 许可证

Apache License 2.0，详见 [LICENSE](./LICENSE)。
