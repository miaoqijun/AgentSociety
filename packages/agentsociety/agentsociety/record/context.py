"""
Record ContextVars and sequencing.

Uses Python `contextvars.ContextVar` to propagate record metadata (step, phase,
agent_id, agent_class, block_name) across async task boundaries.  These are set
by monkey-patched hooks and read by the LLM-request record hook.

Because `asyncio.gather` inherits parent-context automatically, a single
`current_phase.set("main")` before the gather call is visible to all child
tasks — and each child task's own `.set()` is isolated from its siblings.
"""

from contextvars import ContextVar
from collections import defaultdict
from typing import Optional


# ── ContextVars (one per metadata dimension) ──────────────────────────────

current_step: ContextVar[int] = ContextVar("record_step", default=-1)
"""Simulation step number, starting from 0."""

current_phase: ContextVar[str] = ContextVar("record_phase", default="main")
"""Phase name: "pre_dispatch" | "main" | "post_intercept" """

current_agent_id: ContextVar[int] = ContextVar("record_agent_id", default=-1)
"""Agent ID that initiated the LLM call."""

current_agent_class: ContextVar[str] = ContextVar("record_agent_class", default="")
"""Agent class name (e.g. "SocietyAgent", "AgreeAgent")."""

current_block_name: ContextVar[Optional[str]] = ContextVar(
    "record_block_name", default=None
)
"""Block name or sub-component label (e.g. "needs", "plan", "do_chat.should_respond")."""


# ── Pending segments (set by FormatPrompt hook, consumed by LLM hook) ─────

_pending_segments: ContextVar[Optional[tuple]] = ContextVar(
    "_pending_segments", default=None
)
"""
Temporarily stores ``(segments, formatted_string)`` for the most recent
FormatPrompt.format() call.  Reset to None after the segments are consumed
by the LLM hook (or after a non-LLM format call whose output is never sent
to the LLM).
"""


def get_and_clear_pending_segments() -> Optional[tuple[list, str]]:
    """Return ``(segments, formatted_string)`` and clear the contextvar."""
    val = _pending_segments.get()
    _pending_segments.set(None)
    return val


def set_pending_segments(segments: list, formatted_string: str) -> None:
    """Set the pending ``(segments, formatted_string)`` contextvar."""
    _pending_segments.set((segments, formatted_string))


# ── Sequence counter ──────────────────────────────────────────────────────
# Counts LLM invocations per (step, phase, agent_id) tuple.
# This is a plain dict (not ContextVar) because sequencing is global — we want
# a single counter per triple that is shared across all coroutines, regardless
# of parent-child task relationships.
#
# Lock-free design: within the same (step, phase, agent_id) triple, LLM calls
# happen sequentially because:
#   - Phase A: per-receiver serial for-await (one agent_id at a time)
#   - Phase B: per-agent serial forward chain (one agent_id at a time)
#   - Phase C: serial (single supervisor)
# This means no concurrent mutations on the same dict key, so no lock needed.

_seq_counters: dict[tuple, int] = defaultdict(int)
"""Key = (step, phase, agent_id), value = next seq number to assign."""


def next_seq(step: int, phase: str, agent_id: int) -> int:
    """Atomically increment and return the sequence counter for the triple."""
    key = (step, phase, agent_id)
    seq = _seq_counters[key]
    _seq_counters[key] += 1
    return seq


def clear_seq_counters() -> None:
    """Clear all sequence counters (called at the start of each step)."""
    _seq_counters.clear()
