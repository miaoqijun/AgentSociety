"""智能体子系统：基类、PersonAgent、配置、提示词、持久化与并发原语。

导出 :class:`~agentsociety2.agent.base.AgentBase`、:class:`~agentsociety2.agent.person.PersonAgent`、
:class:`~agentsociety2.agent.config.AgentConfig`，以及检查点、WAL、并行执行与限流等类型。

Example:
    >>> from agentsociety2.agent import AgentConfig
    >>> isinstance(AgentConfig().model.declared_context_window, int)
    True
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
    StateConfig,
    ALLOWED_ENV_VARS,
)
from .prompt_builder import PromptBuilder, PromptCacheManager, ToolTableBuilder
from .persistence import (
    Checkpoint,
    WriteAheadLog,
    WorkspaceCleaner,
    SessionRecovery,
    IntentStatus,
)
from .concurrent import (
    Priority,
    PrioritizedTask,
    PriorityScheduler,
    ParallelExecutor,
    RateLimiter,
    TaskManager,
    DeadlockDetector,
)
from .context import AgentMemory

__all__ = [
    "AgentBase",
    "PersonAgent",
    "AgentConfig",
    "ModelConfig",
    "LoopConfig",
    "ContextConfig",
    "PersistenceConfig",
    "ConcurrencyConfig",
    "LoopDetectionConfig",
    "StateConfig",
    "ALLOWED_ENV_VARS",
    "PromptBuilder",
    "PromptCacheManager",
    "ToolTableBuilder",
    "Checkpoint",
    "WriteAheadLog",
    "WorkspaceCleaner",
    "SessionRecovery",
    "IntentStatus",
    "Priority",
    "PrioritizedTask",
    "PriorityScheduler",
    "ParallelExecutor",
    "RateLimiter",
    "TaskManager",
    "DeadlockDetector",
    "AgentMemory",
]
