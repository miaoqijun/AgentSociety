"""
Replay scheduler — faithful mode.

Reads a recorded JSONL file, reconstructs the per-step/per-phase/per-agent
request topology, and replays them against an sglang (or any OpenAI-compatible)
backend while preserving the original concurrency structure.

Usage::

    import json
    from agentsociety.record.replay import load_records, replay, build_prompt

    records = load_records("path/to/records.jsonl")
    metrics = await replay(
        records,
        base_url="http://localhost:30000/v1",
        api_key="sk-noop",
        model="default",
    )
    print(json.dumps(metrics, indent=2))
"""

import asyncio
import json
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from openai import AsyncOpenAI


# ── Data structures ───────────────────────────────────────────────────────


@dataclass
class Step:
    """Reconstructed step with phase → agent_id → request-list mapping."""
    pre_dispatch: dict[int, list[dict]] = field(default_factory=lambda: defaultdict(list))
    main: dict[int, list[dict]] = field(default_factory=lambda: defaultdict(list))
    post_intercept: dict[int, list[dict]] = field(default_factory=lambda: defaultdict(list))


@dataclass
class RequestMetrics:
    """Metrics for a single replayed request."""
    seq: int
    step: int
    phase: str
    agent_id: int
    send_time: float           # monotonic clock
    first_token_time: float    # monotonic clock (or send_time if unknown)
    complete_time: float       # monotonic clock
    prompt_tokens: int = 0
    completion_tokens: int = 0
    status: int = 200
    error: str = ""


@dataclass
class ReplayMetrics:
    """Aggregate replay metrics."""
    total_requests: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    wall_time_s: float = 0.0
    throughput_req_s: float = 0.0
    throughput_tok_s: float = 0.0
    ttft_p50_ms: float = 0.0
    ttft_p99_ms: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p99_ms: float = 0.0
    request_metrics: list[RequestMetrics] = field(default_factory=list)
    errors: int = 0

    def to_dict(self) -> dict:
        """Serialise to a plain dict for JSON output."""
        return {
            "total_requests": self.total_requests,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "wall_time_s": round(self.wall_time_s, 3),
            "throughput_req_s": round(self.throughput_req_s, 1),
            "throughput_tok_s": round(self.throughput_tok_s, 1),
            "ttft_p50_ms": round(self.ttft_p50_ms, 1),
            "ttft_p99_ms": round(self.ttft_p99_ms, 1),
            "latency_p50_ms": round(self.latency_p50_ms, 1),
            "latency_p99_ms": round(self.latency_p99_ms, 1),
            "errors": self.errors,
        }


# ── Load records ──────────────────────────────────────────────────────────


def resolve_record_path(path: str) -> str:
    """Resolve a JSONL record path, accepting a record directory as input."""
    path = os.path.abspath(os.path.expanduser(path))
    if os.path.isdir(path):
        candidates = [
            os.path.join(path, name)
            for name in os.listdir(path)
            if name.endswith(".jsonl")
        ]
        if not candidates:
            raise FileNotFoundError(f"No JSONL record file found in: {path}")
        return max(candidates, key=os.path.getmtime)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Record file does not exist: {path}")
    return path


def load_records(path: str) -> list[Step]:
    """Load a JSONL record file and organise records into Step objects.

    Args:
        path: Path to a JSONL file or a directory containing JSONL records.

    Returns:
        A list of ``Step`` objects, one per simulation step.
    """
    path = resolve_record_path(path)
    records: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    # Group by step, then phase, then agent_id
    by_step: dict[int, Step] = {}
    for r in records:
        step_idx = r.get("step", 0)
        if step_idx not in by_step:
            by_step[step_idx] = Step()
        step = by_step[step_idx]

        phase = r.get("phase", "main")
        agent_id = r.get("agent_id", -1)
        target = getattr(step, phase, step.main)

        # Ensure the per-agent list exists
        if agent_id not in target:
            target[agent_id] = []
        target[agent_id].append(r)

    # Sort each agent's list by seq
    for step in by_step.values():
        for phase_dict in (step.pre_dispatch, step.main, step.post_intercept):
            for agent_id in phase_dict:
                phase_dict[agent_id].sort(key=lambda r: r.get("seq", 0))

    return [by_step[i] for i in sorted(by_step.keys())]


def load_meta(path: str) -> dict:
    """Load meta.json from the same directory as a JSONL file.

    If *path* is a JSONL file, this looks for ``meta.json`` in its parent
    directory.  If *path* is a directory, it looks for ``meta.json`` inside it.
    """
    import os
    if os.path.isdir(path):
        meta_path = os.path.join(path, "meta.json")
    else:
        meta_path = os.path.join(os.path.dirname(path), "meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# ── Build prompt from record ──────────────────────────────────────────────


def build_prompt(record: dict) -> dict:
    """Reconstruct an OpenAI-compatible request dict from a record.

    Args:
        record: A single record dict from a JSONL file.

    Returns:
        A dict suitable for ``client.chat.completions.create(**result)``.
    """
    messages = []
    for m in record.get("messages", []):
        content = "".join(seg.get("text", "") for seg in m.get("segments", []))
        messages.append({"role": m.get("role", "user"), "content": content})

    req = record.get("request", {})
    result = {
        "messages": messages,
        "temperature": req.get("temperature", 1.0),
        "max_tokens": req.get("max_tokens", 512),
    }

    response_format = req.get("response_format")
    if response_format is not None:
        result["response_format"] = response_format

    tools = req.get("tools")
    if tools is not None:
        result["tools"] = tools

    tool_choice = req.get("tool_choice")
    if tool_choice is not None:
        result["tool_choice"] = tool_choice

    return result


# ── Replay scheduler ──────────────────────────────────────────────────────


async def replay(
    steps: list[Step],
    base_url: str = "http://localhost:30000/v1",
    api_key: str = "sk-noop",
    model: str = "",
    mode: str = "faithful",
    max_concurrency: int = 0,
    unlimited: bool = False,
) -> ReplayMetrics:
    """Replay a recorded simulation against an LLM backend.

    Args:
        steps: List of ``Step`` objects (from ``load_records``).
        base_url: OpenAI-compatible API base URL.
        api_key: API key.
        model: Model name to send in requests.  If empty, uses the recorded
            ``model_hint`` if available, otherwise ``"default"``.
        mode: ``"faithful"`` (preserves agent-internal serial order) or
            ``"aggressive"`` (allows Phase-A per-receiver concurrency).
        max_concurrency: Max in-flight requests.  If 0, no explicit limit
            (but the client's default connection limit applies).
        unlimited: If True, no semaphore at all (stress-test mode).

    Returns:
        ``ReplayMetrics`` with aggregate results.
    """
    if mode not in {"faithful", "aggressive"}:
        raise ValueError(f"Unsupported replay mode: {mode}")

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    sem: Optional[asyncio.Semaphore] = None
    if not unlimited and max_concurrency > 0:
        sem = asyncio.Semaphore(max_concurrency)
    elif not unlimited:
        sem = asyncio.Semaphore(200)  # sensible default

    metrics_list: list[RequestMetrics] = []
    start_wall = time.monotonic()

    async def fire(record: dict) -> RequestMetrics:
        """Send one request and collect metrics."""
        nonlocal sem
        prompt = build_prompt(record)
        prompt["model"] = model or record.get("request", {}).get("model_hint", "default")

        m = RequestMetrics(
            seq=record.get("seq", 0),
            step=record.get("step", 0),
            phase=record.get("phase", "main"),
            agent_id=record.get("agent_id", -1),
            send_time=time.monotonic(),
            first_token_time=time.monotonic(),
            complete_time=time.monotonic(),
        )

        # Apply semaphore if configured
        if sem is not None:
            async with sem:
                m.send_time = time.monotonic()
                try:
                    response = await client.chat.completions.create(**prompt)
                    m.complete_time = time.monotonic()
                    if response.usage:
                        m.prompt_tokens = response.usage.prompt_tokens or 0
                        m.completion_tokens = response.usage.completion_tokens or 0
                    m.status = 200
                except Exception as e:
                    m.complete_time = time.monotonic()
                    m.status = 0
                    m.error = str(e)
        else:
            m.send_time = time.monotonic()
            try:
                response = await client.chat.completions.create(**prompt)
                m.complete_time = time.monotonic()
                if response.usage:
                    m.prompt_tokens = response.usage.prompt_tokens or 0
                    m.completion_tokens = response.usage.completion_tokens or 0
                m.status = 200
            except Exception as e:
                m.complete_time = time.monotonic()
                m.status = 0
                m.error = str(e)

        return m

    async def fire_agent_chain(reqs: list[dict]) -> list[RequestMetrics]:
        """Fire a single agent's chain of requests sequentially (faithful mode)."""
        results = []
        for r in reqs:
            m = await fire(r)
            results.append(m)
        return results

    # ── Main loop over steps ───────────────────────────────────────────
    for step_idx, step in enumerate(steps):
        # Phase A: pre_dispatch — per-agent serial chains, agents run concurrently
        if mode == "aggressive":
            phase_a_tasks = [
                fire(record)
                for reqs in step.pre_dispatch.values()
                for record in reqs
            ]
            metrics_list.extend(await asyncio.gather(*phase_a_tasks))
        else:
            phase_a_tasks = [
                fire_agent_chain(reqs)
                for reqs in step.pre_dispatch.values()
            ]
            for result_list in await asyncio.gather(*phase_a_tasks):
                metrics_list.extend(result_list)

        # Phase B: main — per-agent serial chains, agents run concurrently
        phase_b_tasks = [
            fire_agent_chain(reqs)
            for reqs in step.main.values()
        ]
        for result_list in await asyncio.gather(*phase_b_tasks):
            metrics_list.extend(result_list)

        # Phase C: post_intercept — serial per agent (sequential gather)
        for reqs in step.post_intercept.values():
            result_list = await fire_agent_chain(reqs)
            metrics_list.extend(result_list)

    end_wall = time.monotonic()

    # ── Compute aggregate metrics ──────────────────────────────────────
    await client.close()

    wall_time = end_wall - start_wall
    total_req = len(metrics_list)
    total_prompt = sum(m.prompt_tokens for m in metrics_list)
    total_completion = sum(m.completion_tokens for m in metrics_list)
    errors = sum(1 for m in metrics_list if m.status != 200)

    # Latency = complete_time - send_time per request
    latencies = [
        (m.complete_time - m.send_time) * 1000
        for m in metrics_list
        if m.send_time > 0
    ]
    latencies_sorted = sorted(latencies)

    # TTFT — in this simple version we use the same latency as approximation
    # since OpenAI doesn't expose TTFT in standard mode.
    ttft_sorted = latencies_sorted[:]  # same data for now

    def percentile(data: list[float], p: float) -> float:
        if not data:
            return 0.0
        idx = max(0, min(len(data) - 1, int(len(data) * p / 100)))
        return data[idx]

    metrics = ReplayMetrics(
        total_requests=total_req,
        total_prompt_tokens=total_prompt,
        total_completion_tokens=total_completion,
        wall_time_s=wall_time,
        throughput_req_s=total_req / wall_time if wall_time > 0 else 0.0,
        throughput_tok_s=(total_prompt + total_completion) / wall_time if wall_time > 0 else 0.0,
        ttft_p50_ms=percentile(ttft_sorted, 50),
        ttft_p99_ms=percentile(ttft_sorted, 99),
        latency_p50_ms=percentile(latencies_sorted, 50),
        latency_p99_ms=percentile(latencies_sorted, 99),
        request_metrics=metrics_list,
        errors=errors,
    )
    return metrics
