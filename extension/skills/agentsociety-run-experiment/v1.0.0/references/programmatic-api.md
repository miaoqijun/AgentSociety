# Programmatic API Reference

For advanced usage, import the runner functions directly.

## Available Functions

```python
import asyncio
from agentsociety2.skills.experiment.runner import (
    start_experiment,
    stop_experiment,
    get_experiment_status,
    list_experiments,
)
```

## Start Experiment

```python
async def run():
    await start_experiment(
        workspace_path="/path/to/workspace",
        hypothesis_id=1,
        experiment_id=1,
        run_id="run",  # optional, default="run"
    )
```

## Check Status

```python
status = await get_experiment_status(
    workspace_path="/path/to/workspace",
    hypothesis_id=1,
    experiment_id=1,
    run_id="run",
)
```

## Stop Experiment

```python
await stop_experiment(
    workspace_path="/path/to/workspace",
    hypothesis_id=1,
    experiment_id=1,
    run_id="run",
)
```

## List Experiments

```python
experiments = await list_experiments(
    workspace_path="/path/to/workspace",
    hypothesis_id=1,  # optional
)
```

## Status Values

| Status | Description |
|--------|-------------|
| `running` | Experiment is currently executing |
| `completed` | Experiment finished successfully |
| `failed` | Experiment terminated with errors |
| `terminated` | Experiment was stopped via signal |
