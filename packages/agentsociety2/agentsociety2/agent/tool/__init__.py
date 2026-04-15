"""Tool module for PersonAgent.

Components:
- decision: ToolDecision model for LLM output
- utils: JSON handling, string truncation, pagination, retry
- loop_detection: Loop detection service to prevent infinite loops
- security: Bash command security checking
- sandbox: Lightweight workspace isolation and resource limits
"""

from agentsociety2.agent.tool.decision import ToolDecision, VALID_TOOL_NAMES
from agentsociety2.agent.tool.loop_detection import (
    LoopDetectionConfig,
    LoopDetectionService,
)
from agentsociety2.agent.tool.sandbox import (
    SecurityError,
    WorkspaceSandbox,
    get_safe_env,
    set_process_limits,
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
    "VALID_TOOL_NAMES",
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
    "LoopDetectionService",
    "LoopDetectionConfig",
    "BLOCKED_TOKENS",
    "BLOCKED_PATTERNS",
    "BashSecurityChecker",
    # Sandbox
    "WorkspaceSandbox",
    "SecurityError",
    "set_process_limits",
    "get_safe_env",
]
