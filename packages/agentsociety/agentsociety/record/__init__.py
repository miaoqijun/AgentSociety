"""
AgentSociety Record-Replay Module

Implements a record-replay benchmarking architecture for sglang as described in
DESIGN.md. Records all LLM invocations during an AgentSociety simulation into
structured JSONL logs, then replays them against an sglang backend to measure
throughput, latency, and RadixAttention cache hit rates.

Usage:
    from agentsociety.record import enable_recording, disable_recording, RecordConfig

    config = RecordConfig(output_dir="/tmp/records")
    enable_recording(config)
    # ... run simulation ...
    disable_recording()
"""

from .config import RecordConfig, ReplayConfig
from .hooks import (
    enable_recording,
    disable_recording,
    is_recording_enabled,
    instrument_engine,
)
from .replay import replay, build_prompt, load_records, ReplayMetrics
from .analysis import (
    estimate_cache_hit_rate,
    template_inventory,
    segment_cardinality,
    step_llm_count_curve,
    agent_chain_summary,
)

__all__ = [
    "enable_recording",
    "disable_recording",
    "is_recording_enabled",
    "instrument_engine",
    "RecordConfig",
    "ReplayConfig",
    "replay",
    "build_prompt",
    "load_records",
    "ReplayMetrics",
    "estimate_cache_hit_rate",
    "template_inventory",
    "segment_cardinality",
    "step_llm_count_curve",
    "agent_chain_summary",
]
