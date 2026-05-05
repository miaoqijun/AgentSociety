# Stage 3 - Release Gate

The release gate decides whether the current draft is ready for
serious human review (M1's release definition; this is **not**
"ready for submission").

Minimum criteria (all required):

1. `paper_meta.yaml` is present and validated
2. `storyline_map.json` exists with non-empty `current_angle` and
   `contribution_statement`
3. `claim_ledger.json` exists with no claims whose
   `evidence_support == []` and `unsupported_gaps != []`
4. `figure_argument_map.json` exists; every figure linked to a claim
   has either `panels` populated or `status == 'final'`
5. At least one closed review round (`reviews/review_round_NNN.yaml`
   with `completed_at` set) exists with `unresolved_fatal == []`
6. All open `human_gates.yaml` entries have `user_decision != null`
7. The latest `compile` run produced a valid `paper.pdf` (`>= 10KB`)

Use `subagent-prompts/release-gate-judge.md` to dispatch a fresh judge
that re-reads every artifact and returns the verdict. The judge has no
write privileges; it only emits the envelope.

## Verdict Outcomes

| Envelope status | Action |
|-----------------|--------|
| `DONE` with `severity=info` | Mark `paper_state.release_status = ready`; report PDF path to the user |
| `DONE_WITH_CONCERNS` | Surface concerns to the user; let them decide whether to ship as-is or run another round |
| `BLOCKED` with `severity=fatal` | Route the named issue back to the appropriate phase via the revision-router |
| `PIVOT_RECOMMENDED` | Open a human gate (this is intentionally restrictive) |
| `HUMAN_GATE_REQUIRED` | Open a human gate listing the missing criteria |

## Phase 3 Scope

Phase 3 may set `release_status = draft` after a successful compile;
the full gate logic is exercised in Phase 4 once the review loop is
wired up. In M1 smoke runs we still call `paper-orchestrator compile`
and report its envelope, but criterion 5 may legitimately be unmet.
