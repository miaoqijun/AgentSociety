"""Agent模块 - 提供智能体核心类和基础设施。

核心组件
========

**AgentBase**
    智能体抽象基类，定义基本接口。

**PersonAgent**  
    技能优先型Agent实现，支持独立工作区和渐进式技能发现。

配置管理
========

**AgentConfig**
    统一配置管理，整合模型、循环、上下文、持久化、并发等所有配置。

    >>> from agentsociety2.agent import AgentConfig
    >>> config = AgentConfig()  # 使用默认值
    >>> config.model.context_window  # 200000

属性与状态
==========

**AgentAttributes / AgentState**
    属性与状态分离设计，区分静态特征和动态变化。

    >>> from agentsociety2.agent import PersonAttributes, PersonState
    >>> attrs = PersonAttributes(name="Alice", extraversion=0.8)
    >>> state = PersonState(primary_emotion="happy")

持久化
======

**Checkpoint** - 检查点管理，支持崩溃恢复
**WriteAheadLog** - 预写日志，确保精确恢复
**WorkspaceCleaner** - 工作区清理
**SessionRecovery** - 会话恢复上下文构建

并发控制
========

**ParallelExecutor** - 并行工具执行器
**RateLimiter** - 令牌桶限流器
**TaskManager** - 后台任务管理器
"""

from .base import AgentBase
from .person import PersonAgent
from .config import (
    AgentConfig,
    ModelConfig,
    LoopConfig,
    ContextConfig,
    PersistenceConfig,
    ConcurrencyConfig,
    LoopDetectionConfig,
    ALLOWED_ENV_VARS,
)
from .attributes import (
    AgentAttributes,
    AgentState,
    PersonAttributes,
    PersonState,
    StateManager,
)
from .prompt_builder import PromptBuilder, ToolTableBuilder
from .persistence import (
    Checkpoint,
    WriteAheadLog,
    WorkspaceCleaner,
    SessionRecovery,
    IntentStatus,
)
from .concurrent import (
    ParallelExecutor,
    RateLimiter,
    TaskManager,
    get_executor,
    get_limiter,
    get_task_manager,
)

__all__ = [
    # 核心类
    "AgentBase",
    "PersonAgent",
    # 配置
    "AgentConfig",
    "ModelConfig",
    "LoopConfig",
    "ContextConfig",
    "PersistenceConfig",
    "ConcurrencyConfig",
    "LoopDetectionConfig",
    "ALLOWED_ENV_VARS",
    # 属性与状态
    "AgentAttributes",
    "AgentState",
    "PersonAttributes",
    "PersonState",
    "StateManager",
    # Prompt
    "PromptBuilder",
    "ToolTableBuilder",
    # 持久化
    "Checkpoint",
    "WriteAheadLog",
    "WorkspaceCleaner",
    "SessionRecovery",
    "IntentStatus",
    # 并发
    "ParallelExecutor",
    "RateLimiter",
    "TaskManager",
    "get_executor",
    "get_limiter",
    "get_task_manager",
]
