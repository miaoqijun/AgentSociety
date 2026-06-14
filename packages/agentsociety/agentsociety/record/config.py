"""
Record and Replay configuration classes.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RecordConfig:
    """Configuration for the record phase.

    Attributes:
        output_dir: Directory to write JSONL log files and meta.json into.
        scenario: Scenario name (e.g. "polarization.echo_chamber").
        n_agents: Number of agents in the simulation.
        n_steps: Number of simulation steps.
        rng_seed: RNG seed used by the scenario. Zero means unknown or not set.
        agentsociety_commit: Git commit hash of the AgentSociety codebase.
        record_concurrency: Semaphore config used during record.
        record_llm_provider: LLM provider used during record.
        record_llm_model: Model name used during record.
        extra_meta: Any other metadata to include in meta.json.
    """
    output_dir: str = "/tmp/agentociety_records"
    scenario: str = "unknown"
    n_agents: int = 0
    n_steps: int = 0
    rng_seed: int = 0
    agentsociety_commit: str = ""
    record_concurrency: dict = field(default_factory=lambda: {
        "n_llm_configs": 1,
        "concurrency_per_config": 200,
        "n_actors": 8,
    })
    record_llm_provider: str = ""
    record_llm_model: str = ""
    extra_meta: dict = field(default_factory=dict)

    @property
    def filepath(self) -> str:
        """Get the JSONL file path based on metadata."""
        return (
            f"{self.output_dir}/{self.scenario}"
            f"_{self.n_agents}_{self.n_steps}_{self.rng_seed}.jsonl"
        )

    @property
    def meta_filepath(self) -> str:
        """Get the meta.json file path."""
        return f"{self.output_dir}/meta.json"


@dataclass
class ReplayConfig:
    """Configuration for the replay phase.

    Attributes:
        record_path: Path to the JSONL record file or a directory containing
            JSONL files. If a directory, the most recently modified JSONL is used.
        mode: Replay concurrency mode — "faithful" (preserves agent-internal
            serial order) or "aggressive" (relaxes Phase-A serial constraints).
        sglang_base_url: sglang server base URL (e.g. "http://localhost:30000/v1").
        sglang_api_key: API key for sglang (default "sk-noop").
        sglang_model: Model name to send in requests.
        max_concurrency: Max concurrent in-flight requests. If 0, replay uses
            its default limit of 200.
        unlimited: If True, no semaphore limit at all (for stress-testing).
    """
    record_path: str = ""
    mode: str = "faithful"
    sglang_base_url: str = "http://localhost:30000/v1"
    sglang_api_key: str = "sk-noop"
    sglang_model: str = ""
    max_concurrency: int = 0
    unlimited: bool = False
