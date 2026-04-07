"""Tool module for PersonAgent.

Components:
- decision: ToolDecision model for LLM output
- executor: Secure tool execution (bash, codegen, glob, grep)
- utils: JSON handling, string truncation, pagination, retry
- batch: BatchLLMRouter for concurrent LLM calls
- async_io: AsyncWorkspaceIO for non-blocking file operations
- loop_detection: Loop detection service to prevent infinite loops
- security: Bash command security checking
"""

from agentsociety2.agent.tool.async_io import AsyncWorkspaceIO
from agentsociety2.agent.tool.batch import BatchLLMRouter, BatchLLMRouterSingleton
from agentsociety2.agent.tool.decision import ToolDecision
from agentsociety2.agent.tool.executor import ToolExecutor
from agentsociety2.agent.tool.loop_detection import (
    LoopDetectionConfig,
    LoopDetectionService,
)
from agentsociety2.agent.tool.security import (
    BLOCKED_PATTERNS,
    BLOCKED_TOKENS,
    BashSecurityChecker,
)
from agentsociety2.agent.tool.utils import (
    async_retry_on_transient,
    json_dumps,
    json_dumps_tool_result_for_thread,
    json_parse,
    jr_dumps,
    jr_parse,
    paginate,
    pagination_from_args,
    slice_text_page,
    trunc_str,
    truncate,
)

__all__ = [
    "ToolDecision",
    "ToolExecutor",
    "truncate",
    "trunc_str",
    "json_dumps",
    "json_parse",
    "jr_dumps",
    "jr_parse",
    "paginate",
    "pagination_from_args",
    "slice_text_page",
    "json_dumps_tool_result_for_thread",
    "async_retry_on_transient",
    "BatchLLMRouter",
    "BatchLLMRouterSingleton",
    "AsyncWorkspaceIO",
    "LoopDetectionService",
    "LoopDetectionConfig",
    "BLOCKED_TOKENS",
    "BLOCKED_PATTERNS",
    "BashSecurityChecker",
]
