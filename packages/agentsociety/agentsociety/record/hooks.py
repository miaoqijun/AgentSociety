"""
Monkey-patching hooks for Record-Replay.

Call ``enable_recording(config)`` to install all hooks and start recording.
Call ``disable_recording()`` to remove them, flush, and close the writer.

Hooks installed:
1. **FormatPrompt.format** — captures template → segment parsing.
2. **LLM.atext_request**  — assembles the full record and writes it.
3. **Agent.run**           — injects agent_id/agent_class context.
4. **Block.forward**       — injects block_name context.
5. **SimulationEngine.step** — injects phase context and manages step
   boundaries.
6. **MessageInterceptor.forward** — injects post_intercept phase context.
"""

import asyncio
import time
from typing import Any, Optional

from openai import NOT_GIVEN

from ..agent.prompt import FormatPrompt
from ..llm.llm import LLM
from ..agent.agent_base import Agent
from ..agent.block import Block

from .config import RecordConfig
from .context import (
    current_step,
    current_phase,
    current_agent_id,
    current_agent_class,
    current_block_name,
    next_seq,
    clear_seq_counters,
    get_and_clear_pending_segments,
    set_pending_segments,
)
from .segments import (
    parse_template_to_segments,
    lookup_template_id,
    _discover_template_constants,
)
from .writer import RecordWriter


# ── Global state ──────────────────────────────────────────────────────────

_writer: Optional[RecordWriter] = None
"""The active RecordWriter instance (None if recording is disabled)."""

_config: Optional[RecordConfig] = None
"""The active RecordConfig."""

_original_methods: dict[str, Any] = {}
"""Stores references to original methods for clean restoration."""

_recording_enabled: bool = False

# ── Per-step tracking ─────────────────────────────────────────────────────
# Tracks which agent_class we've already seen for a given (step, agent_id)
# to avoid re-looking up the class name every LLM call.

_agent_class_cache: dict[int, str] = {}


# ── Public API ────────────────────────────────────────────────────────────


def enable_recording(config: RecordConfig) -> None:
    """Install all recording hooks.

    Must be called *before* SimulationEngine is created (or at least before
    its first step).  If called after the engine is initialised, the hooks
    will still apply to subsequent steps.

    Args:
        config: Record configuration.
    """
    global _recording_enabled, _writer, _config, _original_methods

    if _recording_enabled:
        return

    _config = config
    _writer = RecordWriter(config)
    _writer.open_sync()  # create the output file synchronously

    # Build template registry
    _discover_template_constants()

    # Install all patches
    _original_methods["FormatPrompt.format"] = FormatPrompt.format
    _original_methods["LLM.atext_request"] = LLM.atext_request
    _original_methods["Agent.run"] = Agent.run
    _original_methods["Block.forward"] = Block.forward

    FormatPrompt.format = _patched_format  # type: ignore[assignment]
    LLM.atext_request = _patched_atext_request  # type: ignore[assignment]
    Agent.run = _patched_agent_run  # type: ignore[assignment]
    Block.forward = _patched_block_forward  # type: ignore[assignment]

    _recording_enabled = True


def disable_recording() -> None:
    """Remove all recording hooks, flush, and close the writer."""
    global _recording_enabled, _writer

    if not _recording_enabled:
        return

    # Restore original methods
    if "FormatPrompt.format" in _original_methods:
        FormatPrompt.format = _original_methods["FormatPrompt.format"]
    if "LLM.atext_request" in _original_methods:
        LLM.atext_request = _original_methods["LLM.atext_request"]
    if "Agent.run" in _original_methods:
        Agent.run = _original_methods["Agent.run"]
    if "Block.forward" in _original_methods:
        Block.forward = _original_methods["Block.forward"]

    _original_methods.clear()
    _agent_class_cache.clear()

    # Close writer — write meta.json and close the file handle
    if _writer is not None:
        try:
            # Drain the queue synchronously by writing remaining items directly
            import json
            while not _writer._queue.empty():
                item = _writer._queue.get_nowait()
                if item is not None and _writer._file is not None:
                    _writer._file.write(json.dumps(item, ensure_ascii=False) + "\n")
                    _writer._file.flush()
                _writer._queue.task_done()
        except Exception:
            pass
        try:
            # Write meta.json (synchronously)
            _writer._write_meta_sync()
        except Exception:
            pass
        try:
            if _writer._file is not None:
                _writer._file.close()
        except Exception:
            pass
        _writer = None

    _recording_enabled = False


def is_recording_enabled() -> bool:
    return _recording_enabled


def get_writer() -> Optional[RecordWriter]:
    return _writer


# ── Patch 1: FormatPrompt.format ──────────────────────────────────────────

async def _patched_format(self: FormatPrompt, context: Optional[dict] = None, **kwargs) -> str:
    """Wraps FormatPrompt.format to capture segment structure and template_id."""
    result = await _original_methods["FormatPrompt.format"](self, context=context, **kwargs)

    try:
        segments = await parse_template_to_segments(
            template=self.template,
            kwargs=kwargs,
            context=context,
            memory_status=self.memory.status if self.memory else None,
        )
        tid = lookup_template_id(self.template)
        set_pending_segments(segments, result, tid)
    except Exception:
        pass

    return result


# ── Patch 2: LLM.atext_request ────────────────────────────────────────────

async def _patched_atext_request(
    self: LLM,
    dialog: list,
    response_format=NOT_GIVEN,
    temperature: float = 1,
    max_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
    presence_penalty: Optional[float] = None,
    timeout: int = 300,
    retries: int = 10,
    tools=NOT_GIVEN,
    tool_choice=NOT_GIVEN,
):
    """Wraps LLM.atext_request to record the invocation."""
    from . import context as ctx_module
    from openai.types.chat import completion_create_params

    global _agent_class_cache

    # Get current context
    step = current_step.get()
    phase = current_phase.get()
    agent_id = current_agent_id.get()
    agent_class = current_agent_class.get()
    block_name = current_block_name.get()

    # Caching agent_class by agent_id
    if agent_id >= 0 and agent_class:
        _agent_class_cache[agent_id] = agent_class
    elif agent_id >= 0 and agent_id in _agent_class_cache:
        agent_class = _agent_class_cache[agent_id]

    # Compute seq
    seq = next_seq(step, phase, agent_id)

    # Consume pending segments from FormatPrompt hook.
    # The contextvar holds a list of (segments, formatted_string, template_id)
    # tuples — one per FormatPrompt.format() call.  We match each tuple
    # against dialog messages by comparing the rendered string.
    pending_list = get_and_clear_pending_segments() or []

    # ── Build the record ──

    record: dict[str, Any] = {
        "step": step,
        "phase": phase,
        "agent_id": agent_id,
        "agent_class": agent_class,
        "seq": seq,
        "cause": None,
        "block_name": block_name,
        "messages": [],
        "request": {},
        "response": {},
        "wall_clock_ms": int(time.time() * 1000),
    }

    # Build structured messages
    for i, msg in enumerate(dialog):
        role = msg.get("role", "user")
        content: str = msg.get("content", "") or ""

        message_entry: dict = {
            "role": role,
            "template_id": None,
            "segments": [],
        }

        # Walk pending_list and match by formatted content.
        matched_idx = None
        for pi, (segs, fmt_str, tid) in enumerate(pending_list):
            if fmt_str and (content == fmt_str or fmt_str in content):
                message_entry["segments"] = segs
                message_entry["template_id"] = tid
                matched_idx = pi
                break
        if matched_idx is not None:
            pending_list.pop(matched_idx)

        if not message_entry["segments"]:
            # Fallback: treat as LLM-generated or free-form
            source = "llm_generated" if role == "assistant" else "format_kwarg"
            message_entry["segments"] = [
                {"kind": "var", "source": source, "text": str(content) if content else ""}
            ]

        record["messages"].append(message_entry)

    # Build request params
    req: dict = {}
    if response_format is not None and response_format is not NOT_GIVEN:
        if hasattr(response_format, "model_dump"):
            req["response_format"] = response_format.model_dump()
        elif isinstance(response_format, dict):
            req["response_format"] = response_format
        else:
            req["response_format"] = response_format
    if tools is not None and tools is not NOT_GIVEN:
        req["tools"] = tools
    if tool_choice is not None and tool_choice is not NOT_GIVEN:
        req["tool_choice"] = tool_choice
    if temperature is not None:
        req["temperature"] = temperature
    if max_tokens is not None:
        req["max_tokens"] = max_tokens
    req["model_hint"] = self.configs[0].model if self.configs else ""

    record["request"] = req

    # ── Call the original method ──
    try:
        start = time.perf_counter()
        result = await _original_methods["LLM.atext_request"](
            self, dialog,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            timeout=timeout,
            retries=retries,
            tools=tools,
            tool_choice=tool_choice,
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        # Read back the log entry that the original appended to self._log_list
        input_tokens = 0
        output_tokens = 0
        if self._log_list:
            last_log = self._log_list[-1]
            input_tokens = last_log.get("input_tokens", 0)
            output_tokens = last_log.get("output_tokens", 0)

        # Build response info
        response_text = ""
        if isinstance(result, str):
            response_text = result
        elif isinstance(result, tuple) and len(result) > 0:
            if isinstance(result[0], str):
                response_text = result[0]
            else:
                response_text = str(result[0])

        record["response"] = {
            "text": response_text,
            "tokens": {"prompt": input_tokens, "completion": output_tokens},
            "latency_ms": elapsed_ms,
            "finish_reason": "stop",
        }
    except Exception as exc:
        record["response"] = {
            "text": "",
            "tokens": {"prompt": 0, "completion": 0},
            "latency_ms": 0,
            "finish_reason": f"error: {exc}",
        }
        raise
    finally:
        # Write the record via the writer's public API
        if _writer is not None:
            try:
                await _writer.write(record)
            except Exception:
                pass

    return result


# ── Patch 3: Agent.run ────────────────────────────────────────────────────

async def _patched_agent_run(self: Agent):
    """Wraps Agent.run to inject agent contextvars."""
    # Set agent context
    current_agent_id.set(self.id)
    current_agent_class.set(type(self).__name__)
    current_block_name.set(None)

    # Call original
    return await _original_methods["Agent.run"](self)


# ── Patch 4: Block.forward ────────────────────────────────────────────────

async def _patched_block_forward(self: Block, **kwargs):
    """Wraps Block.forward to inject block_name contextvar."""
    # Determine block name
    name = getattr(self, "name", "") or type(self).__name__
    current_block_name.set(name)

    return await _original_methods["Block.forward"](self, **kwargs)


# ── Step trampoline for SimulationEngine ──────────────────────────────────
# Rather than patching SimulationEngine.step (which is complex and fragile),
# we install wrapper functions around _message_dispatch, the agent run gather,
# and _message_interceptor.forward that set the phase contextvar.
#
# These are set on the *instance* after the engine is created, via a helper.


def instrument_engine(engine) -> None:
    """Install phase-context injection into a SimulationEngine instance.

    Wraps the engine's ``step`` and ``_message_dispatch`` methods to set
    the ``current_step`` and ``current_phase`` contextvars.  The actual
    work is delegated to the original methods — no logic is duplicated.

    Must be called *after* ``engine.init()`` but *before* the first step.

    Usage::

        from agentsociety.record import enable_recording, instrument_engine

        enable_recording(config)
        engine = SimulationEngine(...)
        await engine.init()
        instrument_engine(engine)
        await engine.run()
    """
    # ── Wrap _message_dispatch ──────────────────────────────────────────
    _orig_dispatch = engine._message_dispatch

    async def _patched_dispatch():
        current_phase.set("pre_dispatch")
        await _orig_dispatch()
        current_phase.set("main")  # restore so Phase B gather inherits "main"

    engine._message_dispatch = _patched_dispatch

    # ── Wrap step ───────────────────────────────────────────────────────
    # Use an independent counter rather than reading engine internals,
    # whose attribute name we can't verify statically.
    _step_counter: list[int] = [0]

    _orig_step = engine.step

    async def _patched_step(num_environment_ticks: int = 1):
        step_num = _step_counter[0]
        _step_counter[0] += 1
        current_step.set(step_num)
        clear_seq_counters()

        # Phase A — _message_dispatch now sets "pre_dispatch" via its wrapper
        # Phase B — set "main" before the agent run gather
        current_phase.set("main")

        # Run the original step logic (which includes _message_dispatch,
        # agent.run gather, gather_queries, save, forward messages, etc.)
        result = await _orig_step(num_environment_ticks)

        # Record step boundary for the writer (after step completes)
        if _writer is not None:
            await _writer.step_boundary(step_num)

        return result

    engine.step = _patched_step  # type: ignore[assignment]

    # ── Wrap MessageInterceptor.forward (if present) ────────────────────
    if engine._message_interceptor is not None:
        _orig_interceptor_forward = engine._message_interceptor.forward

        async def _patched_interceptor_forward(messages):
            current_phase.set("post_intercept")
            return await _orig_interceptor_forward(messages)

        engine._message_interceptor.forward = _patched_interceptor_forward
