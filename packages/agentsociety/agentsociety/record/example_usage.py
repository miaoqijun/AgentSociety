"""
Example: Using the Record-Replay Module
=========================================

This script demonstrates the end-to-end workflow of the AgentSociety
Record-Replay benchmark module.

Prerequisites:
    pip install agentsociety  # (or pip install -e packages/agentsociety)
    pip install openai httpx   # for replay

Usage:
    # Record mode (requires a running AgentSociety simulation):
    python example_usage.py --mode record --output /tmp/records

    # Replay mode (requires a running sglang server):
    python example_usage.py --mode replay --input /tmp/records/records.jsonl

    # Analysis mode (standalone, from recorded JSONL):
    python example_usage.py --mode analyze --input /tmp/records/records.jsonl
"""

import argparse
import asyncio
import json
import os
import sys


# ── Record Example ────────────────────────────────────────────────────────


async def run_record_demo(output_dir: str) -> None:
    """Demonstrate recording hooks installed on AgentSociety classes.

    This is a simplified example — in a real scenario you would:

    1. Create a ``RecordConfig`` with your scenario metadata.
    2. Call ``enable_recording(config)``.
    3. Create and initialise your ``SimulationEngine``.
    4. Call ``instrument_engine(engine)`` (after ``engine.init()``).
    5. Run the simulation as normal — all LLM calls are recorded.
    6. Call ``disable_recording()`` to flush and finalise the logs.
    """
    from agentsociety.record import (
        enable_recording,
        disable_recording,
        instrument_engine,
        RecordConfig,
    )

    config = RecordConfig(
        output_dir=output_dir,
        scenario="example_demo",
        n_agents=10,
        n_steps=5,
        rng_seed=42,
        record_llm_provider="openai",
        record_llm_model="gpt-4o-mini",
        extra_meta={"description": "Example record-replay demo"},
    )

    print(f"[Record] Output directory: {output_dir}")
    print(f"[Record] Meta: scenario={config.scenario}, agents={config.n_agents}, "
          f"steps={config.n_steps}")

    # --- Step 1: Enable recording (installs monkey-patches) ---
    print("[Record] Enabling recording hooks...")
    enable_recording(config)

    # --- Step 2: Create & init engine ---
    # In your real code:
    #   engine = SimulationEngine(config)
    #   await engine.init()
    #   instrument_engine(engine)
    #   await engine.run()
    #
    # Here we just demonstrate that the hooks are active by showing
    # the FormatPrompt and LLM integration.

    from agentsociety.agent.prompt import FormatPrompt

    # This will be captured by the FormatPrompt hook
    prompt = FormatPrompt(
        template="Hello {name}! Today is ${context.current_time}.",
        memory=None,
    )
    formatted = await prompt.format(context={"current_time": "10:00"}, name="Alice")
    print(f"[Record] FormatPrompt test: {formatted}")

    # --- Step 3: Disable recording ---
    print("[Record] Disabling recording and finalising logs...")
    disable_recording()

    # --- Step 4: Check output ---
    if os.path.exists(config.filepath):
        size = os.path.getsize(config.filepath)
        print(f"[Record] Records written to {config.filepath} ({size} bytes)")
    if os.path.exists(config.meta_filepath):
        with open(config.meta_filepath) as f:
            meta = json.load(f)
        print(f"[Record] Meta: {json.dumps(meta, indent=2)}")


# ── Replay Example ────────────────────────────────────────────────────────


async def run_replay_demo(record_path: str, sglang_url: str) -> None:
    """Demonstrate replaying recorded LLM calls against an sglang backend.

    Args:
        record_path: Path to the JSONL record file.
        sglang_url: sglang server base URL (e.g. "http://localhost:30000/v1").
    """
    from agentsociety.record.replay import load_records, replay

    print(f"[Replay] Loading records from {record_path}...")
    steps = load_records(record_path)

    total_requests = sum(
        len(reqs)
        for step in steps
        for phase_dict in (step.pre_dispatch, step.main, step.post_intercept)
        for reqs in phase_dict.values()
    )
    print(f"[Replay] Loaded {len(steps)} step(s) with {total_requests} total request(s).")

    print(f"[Replay] Starting replay against {sglang_url}...")
    metrics = await replay(
        steps,
        base_url=sglang_url,
        api_key="sk-noop",
        model="default",
        mode="faithful",
    )

    print(f"[Replay] Results:")
    print(f"  Total requests:     {metrics.total_requests}")
    print(f"  Wall time:          {metrics.wall_time_s:.2f}s")
    print(f"  Throughput:         {metrics.throughput_req_s:.1f} req/s")
    print(f"  Token throughput:   {metrics.throughput_tok_s:.0f} tok/s")
    print(f"  Latency p50/p99:    {metrics.latency_p50_ms:.1f} / {metrics.latency_p99_ms:.1f} ms")
    print(f"  Errors:             {metrics.errors}")

    # Save metrics
    metrics_path = record_path + ".metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics.to_dict(), f, indent=2)
    print(f"[Replay] Metrics saved to {metrics_path}")


# ── Analysis Example ──────────────────────────────────────────────────────


def run_analysis_demo(record_path: str) -> None:
    """Demonstrate offline analysis of a record file."""
    import json
    from agentsociety.record.analysis import (
        load_jsonl,
        template_inventory,
        estimate_cache_hit_rate,
        step_llm_count_curve,
        agent_chain_summary,
        segment_cardinality,
    )

    print(f"[Analysis] Loading {record_path}...")
    records = load_jsonl(record_path)
    print(f"[Analysis] Loaded {len(records)} record(s).")

    # 1. Template inventory
    inv = template_inventory(records)
    print(f"\n[Analysis] Template Inventory ({len(inv)} templates):")
    for tid, data in list(inv.items())[:10]:
        print(f"  {tid}: count={data['count']}, "
              f"prompt_avg={data['avg_prompt_tokens']}, "
              f"completion_avg={data['avg_completion_tokens']}")

    # 2. Cache hit estimate
    cache = estimate_cache_hit_rate(records)
    print(f"\n[Analysis] Cache Hit Estimate ({cache['total_pairs']} pairs):")
    print(f"  Shape rate:     {cache['shape_rate']:.2%}")
    print(f"  Structure rate: {cache['structure_rate']:.2%}")
    print(f"  Byte rate:      {cache['byte_rate']:.2%}")

    # 3. Step-vs-LLM-count curve
    curve = step_llm_count_curve(records)
    print(f"\n[Analysis] Step-vs-LLM-Count Curve:")
    for step, counts in list(curve.items())[:20]:
        print(f"  Step {step}: total={counts['total']}, "
              f"A={counts['pre_dispatch']}, B={counts['main']}, C={counts['post_intercept']}")

    # 4. Agent chain summary
    chains = agent_chain_summary(records)
    print(f"\n[Analysis] Agent Chain Summary:")
    print(f"  Avg chain length: {chains['avg_chain_length']}")
    print(f"  Max chain length: {chains['max_chain_length']}")
    print(f"  P90 chain length: {chains['p90_chain_length']}")
    print(f"  Total chains:     {chains['total_chains']}")

    # 5. Segment cardinality
    card = segment_cardinality(records)
    print(f"\n[Analysis] Segment Cardinality ({len(card)} templates with segments):")
    for tid, segs in list(card.items())[:5]:
        for seg in segs[:3]:
            print(f"  {tid}[msg={seg['msg_index']},seg={seg['seg_index']}]: "
                  f"source={seg['source']}, distinct={seg['distinct_values']}")


# ── Main ──────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Record-Replay Demo")
    parser.add_argument("--mode", choices=["record", "replay", "analyze"],
                        default="analyze", help="Mode")
    parser.add_argument("--output", default="/tmp/agentociety_records",
                        help="Output directory for records")
    parser.add_argument("--input", default="",
                        help="Input JSONL file for replay/analysis")
    parser.add_argument("--sglang-url", default="http://localhost:30000/v1",
                        help="sglang server URL for replay")
    args = parser.parse_args()

    if args.mode == "record":
        asyncio.run(run_record_demo(args.output))
    elif args.mode == "replay":
        if not args.input:
            print("ERROR: --input is required for replay mode")
            sys.exit(1)
        asyncio.run(run_replay_demo(args.input, args.sglang_url))
    elif args.mode == "analyze":
        if not args.input:
            print("ERROR: --input is required for analyze mode")
            sys.exit(1)
        run_analysis_demo(args.input)


if __name__ == "__main__":
    main()
