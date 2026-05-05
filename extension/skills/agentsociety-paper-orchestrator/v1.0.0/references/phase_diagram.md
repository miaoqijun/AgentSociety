# Phase Diagram

```text
                       ┌──────────┐
                       │  intake  │  paper_meta.yaml + paper_state.yaml
                       └────┬─────┘
                            │  build-pack (paper-adapter)
                            ▼
                       ┌──────────┐
                       │ framing  │  storyline_map.{md,json}
                       └────┬─────┘
                            │  framing producer + critic + auditor
                            ▼
                  ┌────────────────────┐
                  │   evidence-audit   │  claim_ledger.{md,json}
                  └─────────┬──────────┘
                            │  evidence-expansion producer
                            ▼
                  ┌────────────────────┐
                  │   expansion-plan   │  evidence_backlog.{md,json}
                  └─────────┬──────────┘
                            │  optional: auto-execute high-priority gaps
                            ▼
                  ┌────────────────────┐
                  │ manuscript-build   │  figure_argument_map +
                  │                    │  manuscript/{abstract,main,results,discussion}.md
                  └─────────┬──────────┘
                            │  architecture producer + figure-logic-reviewer
                            ▼
                  ┌────────────────────┐
                  │ skeptical-review   │  reviews/review_round_NNN.yaml
                  └─────────┬──────────┘
                            │  significance / precision / evidence reviewers
                            ▼
                  ┌────────────────────┐
                  │ revision-router    │  decide local | structural | pivot | gate
                  └─────────┬──────────┘
                            │  optional loop back to framing/evidence/architecture
                            ▼
                  ┌────────────────────┐
                  │   release-gate     │  paper.pdf delivered
                  └────────────────────┘
```

## Phase Transitions (CLI)

| From | To | Trigger |
|------|----|---------|
| `intake` | `framing` | `build-pack` completes successfully |
| `framing` | `evidence-audit` | `framing` persist (storyline_map saved) |
| `evidence-audit` | `expansion-plan` | `evidence` persist (evidence_backlog saved) |
| `expansion-plan` | `manuscript-build` | `architecture --artifact claim_ledger` saved |
| `manuscript-build` | `skeptical-review` | manuscript markdown drafted; orchestrator advances explicitly |
| `skeptical-review` | `revision-router` | review round closed |
| `revision-router` | `framing` / `manuscript-build` / `skeptical-review` | router decision |
| `revision-router` | `release-gate` | `unresolved_fatal == []` AND no pending human gates |
| `release-gate` | (terminal) | gate judge returns `DONE` with `severity=info` |

## Backwards Transitions

`PaperState.advance_phase` rejects backward jumps. Use
`reset_phase` (orchestrator-internal only) when the revision router
reroutes to an earlier layer. `reset_phase` does not bump the round
counter; `begin_round` does.

## Round Lifecycle

`begin_round()` increments `paper_state.round` and resets per-round
counters (`figure_regenerations`, `citation_augmentations`). A new
review round file is opened lazily on first `append_review`.

## Release-Status Lifecycle

```
not-started -> draft -> in-review -> ready -> released
                  │
                  └────> blocked  (any phase can transition here on fatal)
```

`release_status` is independent of `current_phase`: a paper can be
`in-review` while the phase is `manuscript-build` (architecture
producer iterating with reviewer feedback in flight).
