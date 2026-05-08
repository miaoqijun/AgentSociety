# Agent 模块

`agentsociety2.agent` 提供 Agent 的最小生命周期接口，以及面向人物仿真的默认实现 `PersonAgent`。如果只是想改变人物如何观察、记忆、思考或行动，通常优先写 Agent Skill；只有当生命周期、调度方式或与环境交互协议都需要改变时，才需要继承 `AgentBase` 编写新的 Agent。

## 设计理念

### 核心原则

1. **能力外置**
   Agent 的基础生命周期由代码实现，具体行为能力由 Skill 模块描述和扩展。用户可定义自定义 Skill，系统自动发现并集成。

2. **统一配置管理**
   所有配置集中于 `AgentConfig`，支持环境变量覆盖和运行时调整。

3. **长时间运行支持**
   内置检查点、预写日志（WAL）和工作区清理机制，支持崩溃恢复和长时间仿真。

4. **上下文窗口管理**
   通过简洁上下文、按需读取 Skill 正文和自动压缩，避免长时间仿真时上下文无限增长。

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                      PersonAgent                            │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ AgentConfig │  │ SkillRuntime │  │   PromptBuilder  │   │
│  │ (配置)       │  │ (技能执行)    │  │   (模块化Prompt) │   │
│  └─────────────┘  └──────────────┘  └──────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Persistence Layer                       │   │
│  │  Checkpoint │ WriteAheadLog │ WorkspaceCleaner      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Concurrency Control                     │   │
│  │  PriorityScheduler │ RateLimiter │ DeadlockDetector │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 目录结构

```
agent/
├── person.py          # PersonAgent 默认人物智能体
├── base.py            # AgentBase 抽象基类
├── config.py          # 统一配置
├── prompt_builder.py  # 模块化 Prompt 构建
├── persistence.py     # 检查点、WAL、清理
├── concurrent.py      # 优先级调度、限流
├── context.py         # 上下文管理、Token 计数
├── tool/              # 工具模块
│   ├── decision.py    # ToolDecision 模型
│   ├── loop_detection.py  # 循环检测
│   ├── security.py    # bash 命令安全检查（黑名单 token/模式/危险子串）
│   └── utils.py       # 工具函数
├── skills/            # 技能系统
│   ├── __init__.py    # SkillRegistry
│   ├── runtime.py     # AgentSkillRuntime
│   ├── observation/   # 环境观察
│   ├── cognition/     # 情绪评估与意图形成
│   ├── memory/        # 长期事件记忆
│   └── plan/          # 计划执行与环境行动
```

## 核心组件

### 1. AgentConfig - 统一配置

```python
from agentsociety2.agent import AgentConfig

config = AgentConfig()
config.model.context_window          # 200000
config.loop.max_rounds               # 24
config.persistence.checkpoint_interval  # 10
```

### 2. Persistence - ACID 保证

```python
from agentsociety2.agent import Checkpoint, WriteAheadLog

checkpoint = Checkpoint(workspace, config)
checkpoint.save(tick=100, state={"step_count": 42})

wal = WriteAheadLog(workspace)
intent_id = wal.log_intent("execute_skill", {"skill": "cognition"}, tick=1)
wal.log_result(intent_id, {"ok": True})
```

### 3. Concurrency - 优先级调度

```python
from agentsociety2.agent import PriorityScheduler, RateLimiter, DeadlockDetector

scheduler = PriorityScheduler(max_concurrent=5)
await scheduler.submit("task1", my_coro(), Priority.HIGH)

limiter = RateLimiter(rps=10, burst=20)
await limiter.acquire()

detector = DeadlockDetector(timeout=60.0)
detector.register("operation1")
```

### 4. Context Management - AGENT.md

`AGENT.md` 由运行时组件 `AgentSkillRuntime` 自动维护（包含 YAML frontmatter 与自动生成的文件索引区块）。
Agent 可通过 `workspace_read("AGENT.md")` 获取当前上下文与文件索引。

### 5. PersonAgent - 技能驱动的人物智能体

`PersonAgent` 在每个 `step()` 中运行一个工具循环：模型根据 profile、workspace 摘要、可用 skill catalog 和环境描述输出结构化 `ToolDecision`，运行时执行工具并把结果反馈给模型，直到调用 `done` 或达到轮数上限。

常见流程不是硬编码管线，但通常会自然形成：先用 `observation` 获取当前环境，再用 `cognition` 更新情绪和意图，随后用 `plan` 执行动作，最后在发生重要事件时用 `memory` 追加长期记忆。

## 内置技能

| 技能 | 功能 | 输入 | 输出 |
|-----|------|-----|------|
| observation | 环境观察 | - | state/observation.txt, state/observation_ctx.json |
| cognition | 情绪评估与意图形成 | state/observation.txt, state/memory.jsonl 等 | state/emotion.json, state/intention.json |
| plan | 计划执行与环境行动 | state/intention.json | state/plan_state.json |
| memory | 长期事件记忆 | 本步观察、计划结果、重要认知变化 | state/memory.jsonl |

### 技能元数据

```yaml
---
name: cognition
description: 核心认知技能，生成情绪、需求和意图。
script: scripts/update_cognition.py
---
```

`name` 与 `description` 会进入选择 catalog；`script` 可省略，省略时会自动探测 `scripts/<skill_name>.py`。输入、输出和依赖关系写在 Markdown 正文中，注册表不会解析 `inputs`、`outputs`、`requires` 等扩展字段。

## 工作区结构

```
agent_0001/
├── state/              # 技能状态文件
│   ├── observation.txt # 当前观察
│   ├── observation_ctx.json # 结构化观察上下文
│   ├── emotion.json    # 情绪状态
│   ├── intention.json  # 当前目标
│   ├── plan_state.json # 当前计划与执行状态
│   └── memory.jsonl    # 长期事件记忆
├── .runtime/logs/      # 执行日志
│   ├── tool_calls.jsonl
│   └── thread_messages.jsonl
├── checkpoints/        # 恢复快照
├── wal/               # 预写日志
│   ├── wal.jsonl
│   └── index.json
├── custom/skills/      # 当前 agent 可热加载的自定义 skills
└── AGENT.md            # 动态上下文与文件索引
```

## AGENT.md 设计

`AGENT.md` 是运行时维护的轻量上下文文件，用于保存当前焦点、状态摘要和 workspace 文件索引：

- **简洁**：不超过 2000 字符
- **结构化**：YAML frontmatter + Markdown 章节
- **活文档**：每 tick 更新
- **焦点优先**：当前任务醒目展示

示例：

```markdown
---
current_focus: 在咖啡馆吃午餐
tick: 42
location: downtown_cafe
energy: 0.65
mood: content
---

# Agent Context

## Current Focus
正在主街的咖啡馆吃午餐。

## Key Decisions
- 选择步行而非乘坐公交
- 点了今日特餐

## Patterns
- 1 公里内的距离偏好步行

## Known Issues
- 钱包现金不足
```

## 快速开始

```python
from agentsociety2.agent import PersonAgent, AgentConfig
from datetime import datetime

agent = PersonAgent(
    id=1,
    profile={"name": "Alice", "age": 25},
)
await agent.init(env)
result = await agent.step(tick=300, t=datetime.now())
```

## 环境变量

| 变量 | 默认值 | 说明 |
|-----|-------|------|
| AGENT_MODEL | "" | 模型名称 |
| AGENT_CONTEXT_WINDOW | 200000 | 上下文窗口大小 |
| AGENT_MAX_TOOL_ROUNDS | 24 | 最大工具循环轮数 |
| AGENT_CHECKPOINT_INTERVAL | 10 | 检查点间隔（ticks） |

## 测试

```bash
# 运行单元测试
pytest tests/test_agent_modules.py -v

# 运行覆盖率测试
pytest tests/ --cov=agentsociety2.agent
```
