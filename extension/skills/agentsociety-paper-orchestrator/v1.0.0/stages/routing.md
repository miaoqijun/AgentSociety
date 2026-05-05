# Stage 2 - Routing Loop

After intake the orchestrator enters a deterministic loop:

```text
read paper_state.yaml -> pick next dispatch -> run subagent -> persist
envelope -> update state -> repeat
```

The decision table below maps `current_phase` (and the latest review
verdict) to the next dispatch.

## Phase Routing Table

| current_phase | Pre-conditions | Dispatch target | CLI persist call |
|---------------|----------------|-----------------|------------------|
| `intake` | `paper_meta.yaml` exists | `paper-orchestrator build-pack` (no subagent needed; CLI runs adapter directly) | n/a |
| `framing` | `research_pack.json` exists | `agentsociety-paper-framing` producer + angle-critic + contribution-auditor | `paper-orchestrator framing --payload <storyline_map JSON>` |
| `evidence-audit` | `storyline_map.json` exists | `agentsociety-paper-evidence-expansion` producer + evidence-skeptic + alternative-explanation-reviewer | `paper-orchestrator evidence --payload <evidence_backlog JSON>` |
| `expansion-plan` | `evidence_backlog.json` reviewed | (Phase 4) optional auto-execution of high-priority `auto_executable=true` items via `agentsociety-analysis` / `-literature-search`; otherwise advance | n/a |
| `manuscript-build` | `evidence_backlog.json` exists | `agentsociety-paper-architecture` producer + figure-logic-reviewer (claim_tree, figure_argument, section_outline, draft_section) | `paper-orchestrator architecture --artifact claim_ledger --payload <JSON>` etc.; manuscript markdown written directly to `<ws>/paper/artifacts/manuscript/` |
| `skeptical-review` | manuscript markdown drafted | `agentsociety-paper-skeptical-review` (significance-calibrator + precision-editor + evidence-skeptic) | `paper-orchestrator review --payload <Review or ReviewRound JSON> --round N` |
| `revision-router` | review round closed with non-empty `unresolved_fatal` or non-`accept` verdicts | `subagent-prompts/revision-router.md` (this skill) | n/a (router updates state directly) |
| `release-gate` | review round closed with no unresolved fatal | `subagent-prompts/release-gate-judge.md` (this skill) | `paper-orchestrator compile` once gate passes |

## Dispatch Pattern

For every dispatch, do all of:

1. **Open a run** by calling the CLI with the relevant subcommand or
   reading `<ws>/paper/runs/` for the latest timestamp.
2. **Dispatch the Task subagent** with a prompt that:
   - Names the sub-skill and its subagent role
   - Provides the workspace path, the relevant artifact paths, and the
     research pack path
   - Instructs the subagent to read its skill's prompt files (`SKILL.md`,
     `references/*`, `subagent-prompts/<role>.md`)
   - Asks it to return its envelope JSON inline at the end of its
     response so this skill can parse it
3. **Persist** the returned artifact via the appropriate CLI subcommand
   (see the table above). Persistence is the only side effect this
   skill performs.
4. **Re-read** `paper_state.yaml`. The CLI advances the phase
   automatically when the right artifact lands; if not, advance with a
   subsequent dispatch.

## Error Handling

If a subagent envelope returns:

- `BLOCKED` with severity=fatal -> stop the loop, report to the user
- `NEEDS_CONTEXT` -> re-dispatch the same subagent with the missing
  context (do not change phase)
- `PIVOT_RECOMMENDED` -> route to the revision-router subagent
  (`subagent-prompts/revision-router.md`)
- `HUMAN_GATE_REQUIRED` -> open a human gate via
  `human_gates.yaml`; the orchestrator pauses until `decide()` is called
- `DONE_WITH_CONCERNS` -> proceed to the next phase but log the concern
  in `key_findings`
- `DONE` -> proceed normally

## Phase 3 Scope

Phase 3 only requires the path **intake -> framing -> manuscript-build
-> compile**. Evidence expansion, skeptical review, revision routing,
and human-gate handling land in Phase 4. The router still consults
`paper_state.yaml` correctly; phases past `manuscript-build` are
no-ops in M1's smoke path.
