# Persistence Patterns

Use this reference when the custom environment is stateful. The goal is to make
replay data explicit instead of leaving it implicit in the code.

State persistence is **replay-only**: declare snapshot columns, let the framework
auto-register the replay tables, and write rows via the `_write_*` helpers. If your
module needs in-memory state, it is reconstructed from the constructor kwargs +
replay data on each run.

## The Persistence API on `EnvBase`

`agentsociety2.env.base.EnvBase` owns:

| Member | Purpose |
|--------|---------|
| `_agent_state_columns: ClassVar[list[ColumnDef]]` | Per-agent snapshot columns (keyed by `agent_id + step`). Declare on the class. |
| `_env_state_columns: ClassVar[list[ColumnDef]]` | Per-step env snapshot columns (keyed by `step`). Declare on the class. |
| `set_replay_writer(writer)` | Called by the framework; triggers lazy table registration when columns are declared. |
| `_register_state_tables()` | Auto-builds `{prefix}_agent_state` / `{prefix}_env_state` tables from the column declarations (called lazily on first write). |
| `await _write_agent_state(agent_id, step, t, **data)` | Write one per-agent snapshot row. |
| `await _write_agent_state_batch(step, t, records)` | Write many per-agent rows in one call. |
| `await _write_env_state(step, t, **data)` | Write one env-level snapshot row. |

`ColumnDef` / `TableSchema` / `ReplayDatasetSpec` come from `agentsociety2.storage`.
The framework auto-adds `agent_id` / `step` / `t` columns; you only declare your
module-specific fields. Table-name prefix is derived from the class name
(PascalCase → snake_case).

## Read These Runtime Examples

- `agentsociety2.env.base`
  Source of truth for `_agent_state_columns`, `_env_state_columns`,
  `set_replay_writer`, `_register_state_tables`, `_write_agent_state`,
  `_write_agent_state_batch`, `_write_env_state`.
- `agentsociety2.contrib.env.economy_space`
  Reference for combined per-agent + env-level replay (declares both column lists,
  writes snapshots in `step()`).
- `agentsociety2.contrib.env.simple_social_space`
  Reference for env-level replay only (`_env_state_columns` + `_write_env_state`).
- `agentsociety2.contrib.env.mobility_space.environment`
  Reference for per-agent replay of richer person state (position, etc.).

## Make The Design Decision Explicit

For every meaningful piece of mutable state, classify it before generating code:

- **Replay (per-agent)**: queryable per-agent snapshots keyed by `agent_id + step`
  → declare in `_agent_state_columns`, write via `_write_agent_state` /
  `_write_agent_state_batch`.
- **Replay (env-level)**: queryable env-wide snapshots keyed by `step`
  → declare in `_env_state_columns`, write via `_write_env_state`.
- **In-memory only**: derived / cached values that you can recompute from kwargs +
  replay data → keep as instance attributes, do NOT persist. They are rebuilt on
  each run by the constructor + replay.

Do not leave this undecided in prose. Put the result into the design spec's
`persistence` section.

## Map Design To Code

Declare columns as class-level `ClassVar[list[ColumnDef]]`:

```python
from typing import ClassVar
from agentsociety2.storage import ColumnDef

class MyEnv(EnvBase):
    _agent_state_columns: ClassVar[list[ColumnDef]] = [
        ColumnDef("balance", "REAL", description="Agent's current balance."),
        ColumnDef("status", "TEXT", description="Agent status string."),
    ]
    _env_state_columns: ClassVar[list[ColumnDef]] = [
        ColumnDef("total_messages", "INTEGER", description="Cumulative message count."),
        ColumnDef("market_rate", "REAL", description="Current market rate."),
    ]
```

Typical per-agent (`_agent_state_columns`) fields:

- balances, income, consumption
- lng/lat or other per-agent position snapshots (the framework auto-detects
  `lng` + `lat` and tags the dataset with `geo_point` / `trajectory` capabilities)
- per-agent scores or status values

Typical env-level (`_env_state_columns`) fields:

- aggregate counters
- market rates
- total message counts
- group counts

## Write At Canonical Boundaries

Prefer replay writes at deterministic boundaries:

- `step()` for periodic snapshots
- a single canonical mutation path if state changes outside `step()`

If multiple agents are written every step, use `_write_agent_state_batch(step, t, records)`
instead of many single-row `_write_agent_state` calls.

```python
async def step(self, tick: int, t: datetime) -> None:
    self._step_index += 1
    # Env-level snapshot
    await self._write_env_state(
        self._step_index, t,
        total_messages=self._msg_count,
        market_rate=self._rate,
    )
    # Per-agent batch snapshot
    records = [
        {"agent_id": aid, "balance": bal, "status": st}
        for aid, (bal, st) in self._agent_state.items()
    ]
    await self._write_agent_state_batch(self._step_index, t, records)
```

## Step Semantics: Do Not Confuse `tick` With Replay Step

In AgentSociety, `step(self, tick, t)` receives:

- `tick`: the duration of one simulation step, for example `1`, `60`, or `3600`
- `t`: the wall-clock simulation time after advancing by that duration

For replay tables keyed by `step`, you need a monotonic step index like `1, 2, 3, ...`,
not the duration value in `tick`.

Correct pattern:

- keep an internal counter such as `self._step_index`
- increment it once per `step()` call
- pass that internal counter as the `step` argument to `_write_agent_state_batch` /
  `_write_env_state`
- use the same counter for step-keyed decay windows or queued event timestamps

Typical bug to avoid:

- writing replay rows with `step=tick`
- with `tick=1`, tests may appear to pass by accident
- with `tick=60` or repeated same-duration runs, every replay write lands on the same
  primary key and later rows overwrite earlier ones

Minimum persistence review for step-keyed modules:

- after a 3-step smoke run, do step-keyed replay tables contain rows for steps
  `1, 2, 3` instead of only one surviving step?
- do decay windows compare against the internal step counter rather than the duration
  argument?

## Common Failure Modes

- Declaring replay columns but never writing them
- Writing replay rows whose keys do not match declared columns
- Reusing `tick` as the replay step primary key, causing multi-step runs to overwrite
  earlier rows
- Writing `**data` keys that don't match the declared `ColumnDef` names

## Minimum Review Questions

- Can replay consumers query the intended per-agent and env snapshots without reading
  opaque blobs?
- Are all declared replay columns actually written?
- Are all write points stable and deterministic?
- Is the internal step counter passed as `step` (not `tick`)?
