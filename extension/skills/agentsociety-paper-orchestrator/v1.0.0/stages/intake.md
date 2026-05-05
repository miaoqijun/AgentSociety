# Stage 1 - Paper Meta Intake

Collect the user-facing identity for the manuscript before touching the
state machine. The output is a JSON object that the
`paper-orchestrator init-meta` CLI subcommand validates and persists at
`<workspace>/paper/paper_meta.yaml`.

## Required Fields

- **title** (string, non-empty) - draft is OK; the framing subagent may
  later rewrite it
- **authors** (list, non-empty) - each entry has:
  - `name` (string, non-empty)
  - `affils` (list of int) - references the affiliation IDs below
  - `email` (string, optional but recommended for the corresponding
    author)
  - `corresponding` (bool, default `false`) - if no author is flagged,
    the CLI auto-marks the last author corresponding
- **affils** (list, non-empty) - each entry has `id` (int) and `name`
  (string, non-empty)

## Optional Fields

- **data_availability_url** - string; goes into the LaTeX *Data
  availability* section
- **code_availability_url** - string; goes into the LaTeX *Code
  availability* section
- **target_journal** - free-form string (Nature / Science / NeurIPS /
  arXiv / ...); informs the framing subagent's significance calibration

## Interview Style

Ask the user only what is needed. Reuse anything already obvious from
the workspace (e.g. infer institution from `TOPIC.md` byline if present,
then confirm). Do **not** invent author names, titles or affiliations.

If the user's input is ambiguous (e.g. "me and my advisor" without
naming the advisor), ask one focused clarifying question rather than
guessing.

## Output Format

Build a single JSON blob that matches the schema above and pass it to
the CLI:

```bash
$PYTHON_PATH .agentsociety/bin/ags.py paper-orchestrator init-meta \
    --workspace . \
    --payload '{"title":"...","authors":[...],"affils":[...]}'
```

For long payloads, write the JSON to a temp file and pass its path:

```bash
$PYTHON_PATH .agentsociety/bin/ags.py paper-orchestrator init-meta \
    --workspace . --payload /tmp/paper_meta_intake.json
```

## After This Stage

Run `paper-orchestrator intake --workspace .` to initialize
`<workspace>/paper/state/paper_state.yaml`, then move on to
`stages/routing.md`.
