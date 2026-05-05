# Stage: propose_gaps

After the evidence audit produces the initial backlog, this stage
handles the expansion-plan phase — deciding which gap items to address
before proceeding to manuscript-build.

## Mechanism

The evidence_backlog contains gap items with `priority` and
`auto_executable` flags. The orchestrator handles expansion-plan as
follows:

1. **Auto-executable items** (priority=`high`, auto_executable=`true`):
   The orchestrator may dispatch `agentsociety-analysis` or
   `agentsociety-literature-search` to address these automatically.
   - Cap: 2 analysis dispatches + 2 literature dispatches per round.
   - After dispatch, re-run the adapter (`build-pack`) to refresh the
     research_pack with new results.

2. **Human-gated items** (priority=`high`, auto_executable=`false`):
   Open a `human_gate` with the gap description and suggested approach.
   The orchestrator pauses until the human decides.

3. **Low-priority items** (priority=`low` or `medium`):
   Defer to manuscript-build. The evidence_backlog records them as
   `deferred` and the architecture producer receives them as context.

## Routing Table

| Condition | Action |
|-----------|--------|
| High-priority auto-executable analysis gap | Dispatch `agentsociety-analysis` (cap 2/round) |
| High-priority auto-executable literature gap | Dispatch `agentsociety-literature-search` (cap 2/round) |
| High-priority human-gated gap | Open `human_gate` |
| All high-priority gaps resolved or deferred | Advance to `manuscript-build` |

## Counter Enforcement

```yaml
# paper_state.yaml
counters:
  figure_regenerations: 0    # cap 2/round
  citation_augmentations: 0  # cap 2/round
```

Orchestrator increments `citation_augmentations` for each literature
dispatch and `figure_regenerations` for each analysis dispatch that
produces new figures. If the cap is reached, open a `human_gate`
instead of auto-dispatching.
