# Contributing

Thanks for contributing to AgentSociety.

## Quick start

- **Bug report / feature request**: [GitHub Issues](https://github.com/tsinghua-fib-lab/AgentSociety/issues)
- **Code changes**: open a Pull Request with a clear summary and test plan
- **Questions**: [GitHub Discussions](https://github.com/tsinghua-fib-lab/AgentSociety/discussions)

## Active scope

CI, security scanning, and dependency bots focus on **AgentSociety 2** only:

- `packages/agentsociety2/`
- `extension/`
- `frontend/`

Legacy packages (`packages/agentsociety`, `agentsociety-community`, `agentsociety-benchmark`, `docs_v1`) are out of active CI scope. See [`.github/agentsociety2-scope.yml`](./.github/agentsociety2-scope.yml).

## Development setup

- **Python**: 3.11+
- **Package manager**: [uv](https://docs.astral.sh/uv/)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

# Workspace root (optional: set UV_INDEX_URL to your preferred PyPI mirror)
uv sync

cd packages/agentsociety2
uv sync --extra dev
```

### Extension

```bash
cd extension
npm ci
npm run dev          # watch TypeScript + webview
npm run lint
npm run build
npm audit --audit-level=high
```

### Frontend

```bash
cd frontend
npm ci
npm run lint
npm run build
npm audit --audit-level=high
```

## Pull request checklist

- **Scope**: keep changes focused; avoid unrelated refactors
- **Docs**: update README / CHANGELOG / CONTRIBUTING when behavior or workflow changes
- **Tests**: add or update tests for behavior changes
- **Telemetry**: set `MEM0_TELEMETRY=False` and `ANONYMIZED_TELEMETRY=False` in test environments
- **Lockfiles**: run `uv lock` when changing Python dependencies

## Commit conventions

Use [Conventional Commits](https://www.conventionalcommits.org/):

```text
type(scope): description
```

- **Types**: `feat`, `fix`, `perf`, `refactor`, `docs`, `test`, `chore`, `ci`
- **Scopes**: `agent`, `env`, `extension`, `frontend`, `backend`, `cli`, etc.

PR descriptions should include **Summary**, **Test plan**, and **Breaking changes** (if any).

## Changelog

[CHANGELOG.md](./CHANGELOG.md) follows [Keep a Changelog](https://keepachangelog.com/). Release notes are generated with [git-cliff](https://git-cliff.org/):

```bash
git-cliff --unreleased
git-cliff --latest
git-cliff -o CHANGELOG.md
```

## Release process

1. Create `release/X.Y.Z` from `main`
2. Bump versions in `packages/agentsociety2/pyproject.toml` and `extension/package.json`
3. Update `CHANGELOG.md`
4. Merge to `main`
5. Tag on `main` and push the tag:

   ```bash
   git tag agentsociety2-vX.Y.Z
   git push origin agentsociety2-vX.Y.Z
   ```

6. The `agentsociety2-publish` workflow publishes to PyPI, builds the VSIX, and creates a GitHub Release

## CI overview

| Check             | Workflow                      |
| ----------------- | ----------------------------- |
| Python lint/test  | `ci.yml`                      |
| Extension         | `extension-ci.yml`            |
| Frontend          | `frontend-ci.yml`             |
| CodeQL            | `codeql.yml` (scoped paths)   |
| Dependency review | `dependency-review.yml` (PRs) |
| Publish on tag    | `agentsociety2-publish.yml`   |

Local checks before pushing:

```bash
cd packages/agentsociety2 && uv run ruff check . && uv run pytest -q
cd extension && npm run lint && npm run build
cd frontend && npm run lint && npm run build
```

## Code style

```bash
cd packages/agentsociety2
uv run ruff check .
uv run ruff format .
uv run mypy tests/ --follow-imports=skip
```

Pre-commit hooks (optional): `pre-commit install` — `ruff` is scoped to `packages/agentsociety2/`.
