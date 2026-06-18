"""
Analysis tools for record log files.

Provides offline analysis of recorded LLM call logs:

- ``cache_hit_estimator`` — Estimate RadixAttention three-layer cache hit rate
  (shape / structure / byte).
- ``template_inventory`` — Count calls per template_id, compute avg token stats.
- ``segment_cardinality`` — Per (template_id, segment_index) distinct-value counts.
- ``call_graph_visualizer`` — Step-vs-LLM-count curves and agent-chain timelines.
"""

import json
import os
from collections import Counter, defaultdict
from typing import Any, Optional


def load_jsonl(path: str) -> list[dict]:
    """Load a JSONL file into a list of dicts."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ── 1. Cache Hit Estimator ────────────────────────────────────────────────


def _request_shape(record: dict) -> tuple:
    """Return the template_id sequence (shape) of a record's messages.

    Returns a tuple of (template_id or None for each message).
    """
    return tuple(
        msg.get("template_id") for msg in record.get("messages", [])
    )


def _structure_signature(record: dict) -> tuple:
    """Return the structure signature — template_id + segment (kind, source, key)
    for each message.

    This is a tuple of ((tid, ((k, s, key), ...)), ...)  per message.
    """
    sig = []
    for msg in record.get("messages", []):
        tid = msg.get("template_id")
        seg_sigs = tuple(
            (seg.get("kind"), seg.get("source"), seg.get("key"))
            for seg in msg.get("segments", [])
        )
        sig.append((tid, seg_sigs))
    return tuple(sig)


def _byte_signature(record: dict) -> tuple:
    """Return the byte-level signature — full concatenated text per message."""
    return tuple(
        "".join(seg.get("text", "") for seg in msg.get("segments", []))
        for msg in record.get("messages", [])
    )


def estimate_cache_hit_rate(
    records: list[dict],
    min_shape_overlap: int = 1,
) -> dict[str, Any]:
    """Estimate three-layer RadixAttention cache hit rates.

    For each step-and-phase group (the concurrency boundary in the original
    simulation), calculates:

    - **shape rate**: fraction of request pairs whose template_id sequences
      share a prefix of at least *min_shape_overlap* messages.
    - **structure rate**: fraction of request pairs whose (kind, source, key)
      structure aligns on the shared prefix.
    - **byte rate**: fraction of request pairs whose actual text matches
      on the shared prefix.

    Because exact pair comparison is O(N^2), this implementation compares each
    request in a group against a *reference* request (the first in the group)
    and reports what fraction match at each level.  This is a reasonable
    approximation of the actual cache benefit when requests are processed
    concurrently within a batch.

    Args:
        records: List of record dicts.
        min_shape_overlap: Minimum number of leading messages that must share
            template_id for a pair to be considered for structure/byte checks.

    Returns:
        Dict with keys ``shape_rate``, ``structure_rate``, ``byte_rate``,
        and ``total_pairs``.
    """
    # Group by (step, phase) — this is the concurrency group
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in records:
        groups[(r["step"], r["phase"])].append(r)

    shape_hits = 0
    structure_hits = 0
    byte_hits = 0
    total_pairs = 0

    for group_records in groups.values():
        if len(group_records) < 2:
            continue

        shapes = [_request_shape(r) for r in group_records]
        structs = [_structure_signature(r) for r in group_records]
        bytes_sigs = [_byte_signature(r) for r in group_records]

        # Compare first against all others (reference-based approximation)
        ref_shape = shapes[0]
        ref_struct = structs[0]
        ref_bytes = bytes_sigs[0]

        for i in range(1, len(group_records)):
            total_pairs += 1
            other_shape = shapes[i]

            # Count how many leading messages share template_id
            overlap = 0
            for a, b in zip(ref_shape, other_shape):
                if a == b:
                    overlap += 1
                else:
                    break

            if overlap >= min_shape_overlap:
                shape_hits += 1

                # Check structure alignment
                other_struct = structs[i]
                struct_match = (
                    len(ref_struct) >= overlap
                    and len(other_struct) >= overlap
                    and all(
                        ref_struct[j] == other_struct[j]
                        for j in range(overlap)
                    )
                )
                if struct_match:
                    structure_hits += 1

                    # Check byte match on the overlapping prefix
                    other_bytes = bytes_sigs[i]
                    byte_match = (
                        len(ref_bytes) >= overlap
                        and len(other_bytes) >= overlap
                        and all(
                            ref_bytes[j] == other_bytes[j]
                            for j in range(overlap)
                        )
                    )
                    if byte_match:
                        byte_hits += 1

    return {
        "shape_rate": round(shape_hits / total_pairs, 4) if total_pairs else 0.0,
        "structure_rate": round(structure_hits / total_pairs, 4) if total_pairs else 0.0,
        "byte_rate": round(byte_hits / total_pairs, 4) if total_pairs else 0.0,
        "total_pairs": total_pairs,
    }


# ── 2. Template Inventory ─────────────────────────────────────────────────


def template_inventory(records: list[dict]) -> dict[str, Any]:
    """Compute per-template_id statistics.

    Returns:
        Dict mapping template_id (or "<no_template>") to:
        - count: number of calls
        - avg_prompt_tokens: average prompt token count (from response)
        - avg_completion_tokens: average completion token count
        - agents: set of agent_classes that used this template
        - per_step_avg: average calls per step
    """
    inventory: dict[str, dict] = {}

    for r in records:
        # Determine the template_id from the messages
        tid = _best_template_id(r)

        if tid not in inventory:
            inventory[tid] = {
                "count": 0,
                "prompt_tokens": [],
                "completion_tokens": [],
                "agents": set(),
                "blocks": set(),
                "steps": set(),
            }

        inv = inventory[tid]
        inv["count"] += 1
        inv["agents"].add(r.get("agent_class", ""))
        inv["blocks"].add(r.get("block_name", "") or "")
        inv["steps"].add(r.get("step", -1))

        resp = r.get("response", {})
        tokens = resp.get("tokens", {})
        inv["prompt_tokens"].append(tokens.get("prompt", 0))
        inv["completion_tokens"].append(tokens.get("completion", 0))

    # Compute aggregates
    result = {}
    for tid, inv in sorted(inventory.items(), key=lambda x: -x[1]["count"]):
        pt = inv["prompt_tokens"]
        ct = inv["completion_tokens"]
        n_steps = len(inv["steps"])
        result[tid] = {
            "count": inv["count"],
            "avg_prompt_tokens": round(sum(pt) / len(pt), 1) if pt else 0,
            "avg_completion_tokens": round(sum(ct) / len(ct), 1) if ct else 0,
            "total_prompt_tokens": sum(pt),
            "agent_classes": sorted(inv["agents"]),
            "block_names": sorted(inv["blocks"]),
            "n_steps": n_steps,
            "avg_per_step": round(inv["count"] / n_steps, 1) if n_steps else 0,
        }

    return result


def _best_template_id(record: dict) -> str:
    """Return the best template_id for a record, or '<no_template>'."""
    for msg in record.get("messages", []):
        tid = msg.get("template_id")
        if tid is not None:
            return tid
    return "<no_template>"


# ── 3. Segment Cardinality ────────────────────────────────────────────────


def segment_cardinality(records: list[dict]) -> dict[str, Any]:
    """Compute distinct-value counts per (template_id, segment_index).

    Returns:
        Dict mapping template_id to a list of dicts, one per segment,
        with ``index``, ``distinct_values``, ``sample_values``, and
        ``source``.
    """
    # Collect values per (template_id, msg_index, seg_index)
    values: dict[tuple, set] = defaultdict(set)
    sources: dict[tuple, str] = {}

    for r in records:
        for mi, msg in enumerate(r.get("messages", [])):
            tid = msg.get("template_id")
            if tid is None:
                continue
            for si, seg in enumerate(msg.get("segments", [])):
                key = (tid, mi, si)
                values[key].add(seg.get("text", ""))
                if key not in sources:
                    sources[key] = seg.get("source", "unknown")

    # Aggregate per template_id
    result: dict[str, list[dict]] = defaultdict(list)
    for (tid, mi, si), vals in sorted(values.items()):
        sorted_vals = sorted(vals)
        result[tid].append({
            "msg_index": mi,
            "seg_index": si,
            "source": sources.get((tid, mi, si), "unknown"),
            "distinct_values": len(vals),
            "sample_values": sorted_vals[:5],
        })

    return dict(result)


# ── 4. Call Graph Visualizer (text-based) ────────────────────────────────


def step_llm_count_curve(records: list[dict]) -> dict[int, dict[str, int]]:
    """Compute LLM-call counts per step, broken down by phase.

    Returns:
        Dict mapping step_number -> {"pre_dispatch": N, "main": N, "post_intercept": N, "total": N}
    """
    counts: dict[int, dict[str, int]] = defaultdict(
        lambda: {"pre_dispatch": 0, "main": 0, "post_intercept": 0, "total": 0}
    )
    for r in records:
        step = r.get("step", 0)
        phase = r.get("phase", "main")
        counts[step][phase] += 1
        counts[step]["total"] += 1
    return dict(sorted(counts.items()))


def agent_chain_summary(records: list[dict]) -> dict[str, Any]:
    """Summarise per-agent LLM chain lengths.

    Returns dict with keys:
    - ``per_agent``: mapping of agent_id -> [chain_lengths_per_step]
    - ``avg_chain_length``: average chain length
    - ``max_chain_length``: maximum chain length
    - ``p90_chain_length``: 90th percentile chain length
    """
    # (step, agent_id) -> seq count (max seq + 1)
    chain_lengths: dict[tuple, int] = {}
    for r in records:
        key = (r.get("step", 0), r.get("agent_id", -1))
        seq = r.get("seq", 0)
        chain_lengths[key] = max(chain_lengths.get(key, 0), seq + 1)

    lengths = list(chain_lengths.values())
    lengths_sorted = sorted(lengths)

    # Per-agent
    per_agent: dict[int, list[int]] = defaultdict(list)
    for (step, aid), length in chain_lengths.items():
        per_agent[aid].append(length)

    return {
        "per_agent": {str(k): v for k, v in per_agent.items()},
        "avg_chain_length": round(sum(lengths) / len(lengths), 2) if lengths else 0,
        "max_chain_length": max(lengths) if lengths else 0,
        "p90_chain_length": (
            lengths_sorted[int(len(lengths_sorted) * 0.9)] if lengths else 0
        ),
        "total_chains": len(lengths),
    }
