"""
Example: Using the Record-Replay Module
=========================================

This script demonstrates the end-to-end workflow of the AgentSociety
Record-Replay benchmark module.

Prerequisites:
    pip install agentsociety  # (or pip install -e packages/agentsociety)
    pip install openai httpx   # for replay

Usage:
    # Record an existing AgentSociety scenario against a local backend:
    python -m agentsociety.record.example_usage --mode record \
        --script examples/polarization/control.py \
        --map-file /path/to/map.pb \
        --output /tmp/records \
        --base-url http://localhost:30000/v1 \
        --model Qwen/Qwen2.5-7B-Instruct

    # Replay mode (requires a running sglang server):
    python -m agentsociety.record.example_usage --mode replay \
        --input /tmp/records \
        --base-url http://localhost:30000/v1 \
        --model Qwen/Qwen2.5-7B-Instruct

    # Analysis mode (standalone, from recorded JSONL):
    python -m agentsociety.record.example_usage --mode analyze --input /tmp/records
"""

import argparse
import asyncio
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


# ── Record Example ────────────────────────────────────────────────────────


def _load_scenario_config(script: str):
    """Load the top-level ``config`` object from an AgentSociety scenario."""
    script_path = Path(script).expanduser().resolve()
    if not script_path.is_file():
        raise FileNotFoundError(f"Scenario script does not exist: {script_path}")

    sys.path.insert(0, str(script_path.parent))
    try:
        spec = importlib.util.spec_from_file_location(
            f"_agentsociety_record_{script_path.stem}", script_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot import scenario script: {script_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)

    if not hasattr(module, "config"):
        raise AttributeError(
            f"{script_path} must expose a top-level AgentSociety `config` object"
        )
    return module.config, script_path


def _count_agents(config: Any) -> int:
    total = 0
    for group in ("citizens", "firms", "banks", "nbs", "governments"):
        total += sum(item.number for item in getattr(config.agents, group, []))
    supervisor = getattr(config.agents, "supervisor", None)
    if supervisor is not None:
        total += supervisor.number
    return total


def _git_commit(script_path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(script_path.parent), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


async def run_record_demo(args: argparse.Namespace) -> None:
    """Run and record an existing scenario using a local LLM backend."""
    from agentsociety.configs import LLMConfig
    from agentsociety.llm import LLMProviderType
    from agentsociety.record import (
        enable_recording,
        disable_recording,
        instrument_engine,
        RecordConfig,
    )
    from agentsociety.simulation import AgentSociety

    simulation_config, script_path = _load_scenario_config(args.script)
    if args.map_file:
        simulation_config.map.file_path = str(Path(args.map_file).expanduser().resolve())

    base_urls = args.base_url or ["http://localhost:30000/v1"]
    simulation_config.llm = [
        LLMConfig(
            provider=LLMProviderType.VLLM,
            base_url=base_url,
            api_key=args.api_key,
            model=args.model,
            concurrency=args.concurrency,
            timeout=args.timeout,
        )
        for base_url in base_urls
    ]

    scenario = args.scenario or simulation_config.exp.name
    record_config = RecordConfig(
        output_dir=args.output,
        scenario=scenario,
        n_agents=args.n_agents if args.n_agents is not None else _count_agents(simulation_config),
        n_steps=args.n_steps,
        rng_seed=args.rng_seed,
        agentsociety_commit=_git_commit(script_path),
        record_concurrency={
            "n_llm_configs": len(simulation_config.llm),
            "concurrency_per_config": args.concurrency,
            "n_actors": min(os.cpu_count() or 1, 8),
        },
        record_llm_provider=LLMProviderType.VLLM.value,
        record_llm_model=args.model,
        extra_meta={
            "scenario_script": str(script_path),
            "record_llm_base_urls": base_urls,
        },
    )

    print(f"[Record] Scenario script: {script_path}")
    print(f"[Record] Local backend(s): {', '.join(base_urls)}")
    print(f"[Record] Model: {args.model}")
    print(f"[Record] Output: {record_config.filepath}")

    enable_recording(record_config)
    engine = None
    try:
        engine = AgentSociety.create(simulation_config)
        await engine.init()
        instrument_engine(engine)
        await engine.run()
    finally:
        try:
            if engine is not None:
                await engine.close()
        finally:
            disable_recording()

    size = os.path.getsize(record_config.filepath)
    print(f"[Record] Records written: {record_config.filepath} ({size} bytes)")
    print(f"[Record] Metadata written: {record_config.meta_filepath}")


# ── Replay Example ────────────────────────────────────────────────────────


async def run_replay_demo(args: argparse.Namespace) -> None:
    """Demonstrate replaying recorded LLM calls against an sglang backend.

    Args:
        args: Parsed command-line arguments.
    """
    from agentsociety.record.replay import load_records, replay, resolve_record_path

    record_path = resolve_record_path(args.input)
    print(f"[Replay] Loading records from {record_path}...")
    steps = load_records(record_path)

    total_requests = sum(
        len(reqs)
        for step in steps
        for phase_dict in (step.pre_dispatch, step.main, step.post_intercept)
        for reqs in phase_dict.values()
    )
    print(f"[Replay] Loaded {len(steps)} step(s) with {total_requests} total request(s).")

    base_url = (args.base_url or ["http://localhost:30000/v1"])[0]
    print(f"[Replay] Starting replay against {base_url}...")
    metrics = await replay(
        steps,
        base_url=base_url,
        api_key=args.api_key,
        model=args.model,
        mode=args.replay_mode,
        max_concurrency=args.max_concurrency,
        unlimited=args.unlimited,
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
    from agentsociety.record.replay import resolve_record_path
    from agentsociety.record.analysis import (
        load_jsonl,
        template_inventory,
        estimate_cache_hit_rate,
        step_llm_count_curve,
        agent_chain_summary,
        segment_cardinality,
    )

    record_path = resolve_record_path(record_path)
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
                        help="Input JSONL file or record directory for replay/analysis")
    parser.add_argument("--script", help="Scenario script exposing a top-level `config`")
    parser.add_argument("--map-file", help="Override the scenario map file")
    parser.add_argument("--base-url", action="append",
                        help="Local OpenAI-compatible base URL; repeat in record mode for multiple backends")
    parser.add_argument("--api-key", default="sk-noop", help="Local backend API key")
    parser.add_argument("--model", default="", help="Model name served by the local backend")
    parser.add_argument("--concurrency", type=int, default=200,
                        help="Concurrency per local backend in record mode")
    parser.add_argument("--timeout", type=float, default=60,
                        help="LLM client timeout in record mode (1-60 seconds)")
    parser.add_argument("--scenario", default="", help="Override scenario name in metadata")
    parser.add_argument("--n-agents", type=int, help="Override agent count in metadata")
    parser.add_argument("--n-steps", type=int, default=0,
                        help="Expected simulation step count to store in metadata")
    parser.add_argument("--rng-seed", type=int, default=0,
                        help="Seed already used by the scenario, stored as metadata only; 0 means unknown")
    parser.add_argument("--replay-mode", choices=["faithful", "aggressive"],
                        default="faithful", help="Replay scheduling mode")
    parser.add_argument("--max-concurrency", type=int, default=200,
                        help="Maximum in-flight replay requests")
    parser.add_argument("--unlimited", action="store_true",
                        help="Disable the replay concurrency limit")
    args = parser.parse_args()

    if args.mode == "record":
        if not args.script or not args.model:
            parser.error("record mode requires --script and --model")
        asyncio.run(run_record_demo(args))
    elif args.mode == "replay":
        if not args.input:
            parser.error("--input is required for replay mode")
        asyncio.run(run_replay_demo(args))
    elif args.mode == "analyze":
        if not args.input:
            parser.error("--input is required for analyze mode")
        run_analysis_demo(args.input)


if __name__ == "__main__":
    main()
