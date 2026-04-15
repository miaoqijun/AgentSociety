# Agent Module

技能优先型智能体框架，专为Agent-Based Modeling (ABM)研究设计。

## 设计理念

### 核心原则

1. **技能优先 (Skill-First)**
   Agent能力通过Skill模块动态扩展，而非硬编码。用户可自定义Skill，系统自动发现并集成。

2. **统一配置管理**
   所有配置集中于`AgentConfig`，支持环境变量覆盖和运行时动态调整。

3. **长期运行支持**
   内置检查点、预写日志(WAL)、工作区清理机制，支持崩溃恢复和长时间仿真。

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                      PersonAgent                            │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ AgentConfig │  │ SkillRuntime │  │   PromptBuilder  │   │
│  │ (统一配置)   │  │ (技能执行)    │  │   (模块化Prompt) │   │
│  └─────────────┘  └──────────────┘  └──────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              持久化层 (Persistence)                  │   │
│  │  Checkpoint │ WriteAheadLog │ WorkspaceCleaner      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              并发控制 (Concurrency)                  │   │
│  │  ParallelExecutor │ RateLimiter │ TaskManager       │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 目录结构

```
agent/
├── person.py          # PersonAgent核心实现
├── base.py            # Agent抽象基类
├── config.py          # 统一配置管理
├── prompt_builder.py  # 模块化Prompt构建
├── persistence.py     # 检查点、WAL、清理
├── concurrent.py      # 并发控制
├── context.py         # 上下文管理、Token计数
├── init_utils.py      # 初始化工具
├── tool/              # 工具模块
│   ├── decision.py    # ToolDecision模型
│   ├── loop_detection.py  # 循环检测
│   ├── security.py    # Bash安全检查
│   └── utils.py       # 工具函数
├── skills/            # Skills系统
│   ├── __init__.py    # SkillRegistry
│   ├── runtime.py     # AgentSkillRuntime
│   ├── needs/         # 需求管理
│   ├── cognition/     # 情绪和意图
│   ├── plan/          # 计划执行
│   ├── memory/        # 长期记忆
│   └── ...
└── benchmark/         # 性能基准测试
```

## 核心组件

### 1. AgentConfig - 统一配置

所有配置的统一入口，支持环境变量和运行时覆盖。

```python
from agentsociety2.agent import AgentConfig

# 默认配置
config = AgentConfig()

# 从环境变量加载
config = AgentConfig.from_env()

# 从kwargs覆盖
config = AgentConfig.from_kwargs({
    "model": {"context_window": 128000},
    "loop": {"max_steps": 50},
})

# 访问子配置
config.model.context_window     # 模型上下文窗口
config.loop.max_steps           # 循环最大步数
config.context.thread_max_tokens # 线程最大Token
config.persistence.checkpoint_interval  # 检查点间隔
config.concurrency.max_parallel # 最大并行数
config.state.builtin_states     # 内置状态文件定义
```

#### 配置项说明

| 配置类 | 参数 | 默认值 | 说明 |
|--------|------|--------|------|
| ModelConfig | context_window | 200000 | 模型上下文窗口大小 |
| | output_reserve | 16000 | 输出预留tokens |
| LoopConfig | max_rounds | 24 | 工具循环最大轮数 |
| | step_timeout | 300 | 单步超时时间(秒) |
| ContextConfig | thread_max_tokens | 150000 | 线程最大Token |
| | compact_trigger_ratio | 0.75 | 压缩触发阈值 |
| | workspace_cache_max_entries | 50 | 工作区缓存最大条目 |
| | grep_max_files | 2000 | grep最大扫描文件数 |
| PersistenceConfig | checkpoint_interval | 10 | 检查点间隔(tick) |
| | wal_max_entries | 1000 | WAL最大条目数 |
| | enable_llm_history | False | 是否启用LLM历史记录 |
| ConcurrencyConfig | max_parallel_tools | 3 | 最大并行工具数 |
| | rate_limit_rps | 10 | 每秒请求数限制 |
| StateConfig | builtin_states | {...} | 内置状态文件定义 |
| | extra_states | {} | 扩展状态文件定义 |
| | auto_discover | True | 自动发现状态文件 |

### 2. Persistence - 持久化支持

```python
from agentsociety2.agent import Checkpoint, WriteAheadLog, WorkspaceCleaner

# 检查点
checkpoint = Checkpoint(workspace, config)
checkpoint.save(tick=100, state={"activated_skills": [...]})
latest = checkpoint.restore(checkpoint.latest_tick())

# 预写日志
wal = WriteAheadLog(workspace)
intent_id = wal.log_intent("workspace_write", {"path": "test.txt"}, tick=1)
wal.log_result(intent_id, {"ok": True})

# 工作区清理
cleaner = WorkspaceCleaner(workspace, config)
stats = await cleaner.cleanup()  # 清理旧文件
```

### 3. Concurrent - 并发控制

```python
from agentsociety2.agent import ParallelExecutor, RateLimiter, TaskManager

# 并行执行器
executor = ParallelExecutor(config)
results = await executor.execute(
    tools=[("workspace_read", {"path": "a.txt"}),
           ("glob", {"pattern": "**/*.py"})],
    executor=my_executor,
)

# 限流器
limiter = RateLimiter(rps=10, burst=20)
await limiter.acquire()

# 后台任务管理
task_mgr = TaskManager()
task_id = await task_mgr.spawn("task_1", my_coro())
await task_mgr.cancel("task_1")
```

### 3. PromptBuilder - 模块化Prompt

```python
from agentsociety2.agent import PromptBuilder, ToolTableBuilder

builder = PromptBuilder()
builder.add_identity("You are a helpful assistant.")
builder.add_tools(ToolTableBuilder.render())
builder.add_context("Current time: 2024-01-01")
builder.add_skills(["needs", "cognition"])

prompt = builder.build(base="System prompt base.")
```

## 快速开始

### 基本创建

```python
from agentsociety2.agent import PersonAgent, AgentConfig

agent = PersonAgent(
    id=1,
    profile={"name": "Alice", "age": 25},
    config=AgentConfig(),  # 使用默认配置
)
await agent.init(env)
await agent.step(tick=300, t=datetime.now())
```

### 使用初始化工具

```python
from agentsociety2.agent.init_utils import (
    create_person_agent, PersonInitConfig, discover_skill_schemas
)

# 动态发现可用技能
schemas = discover_skill_schemas()

# 配置Agent
config = PersonInitConfig(
    agent_id=1,
    name="Alice",
    profile={"age": 25, "occupation": "Engineer"},
)

# 链式设置技能状态
config.set_state("needs", "needs.json", {
    "satiety": 0.3, "energy": 0.2
}).set_state("cognition", "emotion.json", {
    "primary": "Distress", "valence": -0.3
})

agent = create_person_agent(config)
```

### 便捷函数

```python
from agentsociety2.agent.init_utils import (
    init_needs_state, init_emotion_state,
    create_agent_with_needs,
)

# 生成标准状态
needs = init_needs_state(satiety=0.2, energy=0.1)
emotion = init_emotion_state(primary="Distress", valence=-0.4)

# 预设模板
hungry_agent = create_agent_with_needs(1, satiety=0.1, energy=0.1)
```

## 核心概念

### Skills系统

Skills是Agent能力的模块化单元，通过`SKILL.md`定义：

```yaml
---
name: cognition
description: 生成情绪和意图状态
inputs:
  - state/observation.txt
  - state/needs.json
outputs:
  - state/emotion.json
  - state/intention.json
priority: 80
---
```

#### Skill元数据字段

| 字段 | 类型 | 说明 |
|------|------|------|
| name | str | Skill唯一标识 |
| description | str | 简短描述，用于catalog展示 |
| inputs | list[str] | 输入文件列表（依赖声明） |
| outputs | list[str] | 输出文件列表 |
| script | str | 可选的Python脚本路径 |
| requires | list[str] | 依赖的其他skill名称 |
| priority | int | 优先级（越高越重要） |

#### 内置Skills

| Skill | 功能 | 输入 | 输出 |
|-------|------|------|------|
| observation | 获取环境感知 | - | observation.txt |
| needs | 生理/社交需求 | observation.txt | needs.json |
| cognition | 情绪/意图生成 | observation.txt, needs.json | emotion.json, intention.json |
| plan | 执行动作 | intention.json, observation.txt | plan_state.json |
| memory | 长期记忆 | observation.txt, intention.json | memory.jsonl |
| thought | 内心独白 | observation.txt, needs.json | thought.txt |
| habit | 习惯管理 | observation.txt, needs.json | habits.json |

### Workspace结构

```
agent_0001/
├── state/              # Skill状态文件（动态发现）
│   ├── needs.json      # 需求状态
│   ├── emotion.json    # 情绪状态
│   ├── intention.json  # 意图状态
│   ├── plan_state.json # 计划状态
│   └── *.json          # 其他skill扩展状态
├── memory/             # 长期记忆
│   └── memory.jsonl    # 记忆日志
├── input/              # 外部输入
├── logs/               # 执行日志
│   ├── tool_calls.jsonl      # 工具调用日志
│   ├── thread_messages.jsonl # 线程消息
│   └── behavior_trace.jsonl  # 行为追踪
├── checkpoints/        # 检查点
├── wal/               # 预写日志
│   ├── wal.jsonl      # 日志条目
│   └── index.json     # 索引
├── AGENT_CONTEXT.md   # 动态上下文（类似CLAUDE.md）
└── AGENT_FILES.md     # 文件清单（自动生成）
```

### 状态文件动态发现

系统支持动态发现状态文件，无需硬编码：

```python
# 配置扩展状态文件
config.state.extra_states = {
    "my_custom": ("custom.json", "status"),
}

# 自动发现所有state/*.json文件
state_files = skill_runtime.workspace_list("state")
```

### 情绪系统

三层情绪模型：

| 层次 | 时长 | 文件 | 说明 |
|------|------|------|------|
| Emotion | 秒-分钟 | emotion.json | 短期情绪，事件驱动 |
| Mood | 小时-天 | emotion.json (mood字段) | 中期心境，累积效应 |
| Personality | 长期 | personality.json | 人格特质，稳定不变 |

### 循环检测

自动检测三种循环：
- **工具调用循环**：相同工具+参数连续5次
- **内容循环**：相同内容连续10次
- **错误重复**：相同错误连续3次

### 上下文压缩

多级压缩阈值：
- 60%: 发出警告
- 70%: 触发压缩
- 85%: 强制压缩
- 95%: 硬停止

## 设计亮点

### 1. 技能优先架构

- **动态发现**：运行时自动发现可用Skill
- **依赖管理**：自动解析Skill依赖关系
- **隔离执行**：每个Skill有独立的作用域和允许的工具集

### 2. 长期运行支持

- **检查点机制**：定期保存状态，支持崩溃恢复
- **预写日志(WAL)**：记录执行意图和结果，防止重复副作用
- **自动清理**：定期清理旧日志和检查点

### 3. ABM研究友好

- **属性/状态分离**：清晰区分静态特征和动态变化
- **状态快照**：支持历史状态追踪
- **可扩展性**：用户可自定义Skill扩展Agent能力

### 4. 高性能并发

- **并行工具执行**：自动识别可并行的读操作
- **令牌桶限流**：防止API过载
- **后台任务管理**：异步任务生命周期管理

## 环境变量

仅暴露用户可能需要调整的核心配置，其他参数使用合理的默认值：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| AGENT_MODEL | 模型名称 | "" |
| AGENT_CONTEXT_WINDOW | 模型上下文窗口 | 200000 |
| AGENT_MAX_TOOL_ROUNDS | 工具循环最大轮数 | 24 |
| AGENT_CHECKPOINT_INTERVAL | 检查点间隔(tick) | 10 |
| AGENT_STEP_TIMEOUT | 单步超时(秒) | 300 |

对于高级配置需求，可直接修改 `AgentConfig` 实例：

```python
from agentsociety2.agent import AgentConfig

config = AgentConfig()
config.context.workspace_cache_max_entries = 100  # 调整缓存大小
config.persistence.wal_max_entries = 2000          # 调整WAL大小
config.loop_detection.max_tool_repeats = 8         # 调整循环检测灵敏度
```

## 测试

```bash
# 运行单元测试
pytest agentsociety2/agent/tests/

# 运行性能基准测试
python -m agentsociety2.agent.benchmark.run_benchmark --test all

# 收集测试
pytest agentsociety2/agent/tests/ --collect-only
```
