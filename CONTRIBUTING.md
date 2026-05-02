# Contributing

Thanks for taking the time to contribute to AgentSociety.

## Quick start

- **Bug report / feature request**: use GitHub Issues (templates are provided).
- **Code changes**: open a Pull Request with a clear summary and test plan.

## Development setup

- **Python**: use Python 3.11+
- **Package manager**: use `uv` for dependency management

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies (from workspace root)
uv sync

# Install with dev dependencies
cd packages/agentsociety2
uv sync --extra dev
```

## Project structure (high level)

- `packages/agentsociety2/`: AgentSociety2 core Python package
- `extension/`: VS Code extension
- `frontend/`: web UI (if applicable)

## Pull request checklist

- **Scope**: keep PRs focused; avoid unrelated refactors.
- **Docs**: update README/docs when user-facing behavior changes.
- **Tests**: add or update tests when behavior changes; include a minimal reproduction for bug fixes.
- **Style**: follow existing conventions in the touched module; avoid redundant comments.
- **Telemetry**: ensure `MEM0_TELEMETRY=False` and `ANONYMIZED_TELEMETRY=False` are set in test environments.

## Commit & PR conventions

- Use clear, descriptive commit messages.
- In PR description, include:
  - **Summary** (1–3 bullets)
  - **Test plan** (commands or steps)
  - **Breaking changes** (if any)

## Code style

- Use `ruff` for linting: `uv run ruff check .`
- Use `ruff` for formatting: `uv run ruff format .`
- Use `mypy` for type checking: `uv run mypy tests/ --follow-imports=skip`

## Running tests

```bash
cd packages/agentsociety2
uv run pytest -v
```

