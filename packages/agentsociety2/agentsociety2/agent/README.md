# Agent Module

PersonAgent 是仿真人Agent的核心实现，支持Skills系统、Workspace管理和Token计数优化。

## 目录结构

```
agent/
├── person.py          # PersonAgent主类
├── base.py            # Agent基类
├── context.py         # 上下文管理、Token计数
├── context_config.py  # 配置参数
├── init_utils.py      # 初始化工具（新增）
├── tool/              # 工具模块
│   ├── utils.py       # JSON处理、分页工具
│   ├── decision.py    # ToolDecision模型
│   ├── executor.py    # 工具执行器
│   ├── loop_detection.py  # 循环检测（新增）
│   ├── async_io.py    # 异步文件IO
│   └── batch.py       # LLM批处理
├── skills/            # Skills系统
│   ├── __init__.py    # SkillRegistry, SkillInfo
│   ├── runtime.py     # AgentSkillRuntime
│   ├── needs/         # 需求管理
│   ├── cognition/     # 情绪和意图（含Mood层）
│   ├── plan/          # 计划执行
│   ├── memory/        # 长期记忆
│   ├── observation/   # 环境观察
│   ├── thought/       # 内心独白
│   ├── relationship/  # 社会关系
│   ├── belief/        # 信念系统
│   └── personality/   # 人格特质
└── tests/             # 单元测试
```

## 快速开始

### 基本创建

```python
from agentsociety2.agent import PersonAgent

agent = PersonAgent(
    id=1,
    profile={"name": "Alice", "age": 25},
)
await agent.init(env)
await agent.step(tick=300, t=datetime.now())
```

### 使用初始化工具（推荐）

```python
from agentsociety2.agent.init_utils import (
    create_person_agent, PersonInitConfig, discover_skill_schemas
)

# 1. 查看可用技能及其输出文件
schemas = discover_skill_schemas()
# {"needs": ["needs.json"], "cognition": ["emotion.json", "intention.json"], ...}

# 2. 动态创建 Agent（自动发现技能）
config = PersonInitConfig(
    agent_id=1,
    name="Alice",
    profile={"age": 25, "occupation": "Engineer"},
)

# 链式设置技能状态（只设置可用的技能）
config.set_state("needs", "needs.json", {
    "satiety": 0.3, "energy": 0.2, "safety": 0.8, "social": 0.5
}).set_state("cognition", "emotion.json", {
    "primary": "Distress", "valence": -0.3
})

# 自定义技能同样支持
config.set_state("my_game_skill", "game_state.json", {"score": 100, "level": 3})

agent = create_person_agent(config)
```

### 便捷函数

```python
from agentsociety2.agent.init_utils import (
    init_needs_state, init_personality_state, init_emotion_state,
    create_agent_with_needs, create_agent_with_personality,
)

# 生成标准格式状态
needs = init_needs_state(satiety=0.2, energy=0.1)  # 自动计算 current_need
personality = init_personality_state(extraversion=0.9, neuroticism=0.2)
emotion = init_emotion_state(primary="Distress", valence=-0.4)

# 预设模板（动态发现技能）
hungry_agent = create_agent_with_needs(1, satiety=0.1, energy=0.1)
outgoing_agent = create_agent_with_personality(2, extraversion=0.9, neuroticism=0.2)
```

### 动态技能发现

初始化工具**不硬编码**技能列表，而是运行时动态发现：

```python
# 检查技能是否可用
schemas = discover_skill_schemas()
if "my_custom_skill" in schemas:
    config.set_state("my_custom_skill", "my_state.json", {...})
```

这确保了：
- 内置技能可选：不需要时不会写入
- 自定义技能透明：与内置技能统一处理
- 向前兼容：新增技能自动可用

## 核心概念

### Skills系统

Skills是Agent能力的模块化单元：
- `SKILL.md`: 元数据和执行指南
- `outputs`: 输出文件列表
- `priority`: 优先级 (0-100)
- `requires`: 依赖的其他skills

### Workspace管理

Agent的workspace按功能分区：
- `state/{skill_name}/`: Skill状态文件
- `memory/`: 长期记忆
- `input/`: 外部输入
- `logs/`: 执行日志

### 情绪系统（三层模型）

| 层次 | 时长 | 文件 | 说明 |
|------|------|------|------|
| Emotion | 秒-分钟 | emotion.json | 短期情绪，事件驱动 |
| Mood | 小时-天 | emotion.json (mood字段) | 中期心境，累积效应 |
| Personality | 长期 | personality.json | 人格特质，稳定不变 |

### 循环检测

自动检测三种循环：
- 工具调用循环：相同工具+参数连续5次
- 内容循环：相同内容连续10次
- 错误重复：相同错误连续3次

### Token计数

统一使用 `cl100k_base` 编码：
- LiteLLM精确计数优先
- tiktoken近似计数回退
- 字符启发式兜底

### 上下文压缩

多级压缩阈值：
- 60%: 发出警告
- 70%: 触发压缩
- 85%: 强制压缩
- 95%: 硬停止

## 测试

```bash
# 运行单元测试
pytest agentsociety2/agent/tests/

# 收集测试
pytest agentsociety2/agent/tests/ --collect-only
```
