# Generate

Generate a single-file environment module at `custom/envs/<module_name>.py`.

Before writing code:

- Run `$PYTHON_PATH .agentsociety/bin/ags.py create-env-module-resolve-sources` if the runtime file locations are not obvious.
- Read `references/runtime-sources.md`.
- Confirm the real contract in `EnvBase`, the bundled local validator, and registry helpers.
- Read at least one reference implementation that matches the desired complexity.
- If the module carries mutable state, replay data, or resume requirements, read `references/persistence-patterns.md`.
- Keep the implementation proportional to the simulation scale budget chosen during intake.

Generation rules:

- Keep the class definition in the target file itself.
- Inherit from `EnvBase`.
- Preserve `class_name` as the registry key.
- Include at least one legal `@tool`.
- Provide `step()`.
- Default to no-arg construction.
- If the module needs observation capability, provide it through one or more `@tool(readonly=True, kind="observe")` methods.
- Provide a short `description()` and useful `init_description()` for init kwargs.
- If per-agent state must be persisted to replay, declare `_agent_state_columns` and write through `_write_agent_state()` or `_write_agent_state_batch()`.
- If global environment state must be persisted to replay, declare `_env_state_columns` and write through `_write_env_state()`.
- Distinguish `tick` from replay `step`: in `EnvBase.step(self, tick, t)`, `tick` is the duration of one simulation step, not the monotonically increasing step index. Do not use `tick` directly as the primary-key step value for replay tables unless the design explicitly defines them to be the same.
- If the environment needs per-step replay snapshots, maintain an internal step counter such as `self._tick` / `self._step_index`, increment it once per `step()` call, and use that counter for `_write_agent_state_batch()` / `_write_env_state()` and other step-keyed state like `created_step`.
- If the module keeps mutable in-memory state, treat it as derived/cached: reconstruct it from the constructor kwargs + replay data on each run.
- Persist step counters, IDs, queues, maps, or other reconstruction-critical state by writing them to replay tables (declare the columns, write via `_write_*`), not via a dump channel.
- Do not add placeholder persistence hooks. Either implement the real replay-write path or keep the module intentionally stateless.

After writing code, keep lightweight notes only if they help later review:

- If traceability matters, write a concise `generation_input.json` or `generation_summary.md` into the current run directory.
- Include `module_path`, `class_name`, and the key generation decisions worth reviewing later.
