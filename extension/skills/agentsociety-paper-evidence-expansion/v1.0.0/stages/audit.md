# Stage: audit

Audit claim-evidence alignment and produce the evidence_backlog.

## Routing Table

| Condition | Dispatch | Persist |
|-----------|----------|---------|
| `phase=evidence-audit` AND no `evidence_backlog.json` | producer | `paper-orchestrator evidence --payload <EvidenceBacklog JSON>` |
| `evidence_backlog.json` persisted | evidence-skeptic (read-only) | `paper-orchestrator review --payload <Review JSON> --round N` |
| after evidence-skeptic | alternative-explanation-reviewer (read-only) | same |
| reviewer verdict != `accept` AND `revise_*` | re-dispatch producer with reviewer notes | same |
| same-target retry count >= 2 | open `human_gate` | n/a |

## Dispatch Instructions

### Producer Dispatch

1. Build the producer input JSON:
   ```json
   {
     "workspace_path": "<absolute>",
     "research_pack_path": "<ws>/paper/state/research_pack.json",
     "storyline_path": "<ws>/paper/artifacts/storyline_map.json",
     "claim_ledger_path": "<ws>/paper/artifacts/claim_ledger.json",
     "evidence_backlog_path": null,
     "target_artifact": "evidence_backlog",
     "prior_review_findings": [],
     "round_constraints": []
   }
   ```
2. Open a Task subagent with prompt from `subagent-prompts/producer.md`.
3. Persist the `evidence_backlog` field via CLI.

### Evidence-Skeptic Dispatch (always after producer)

1. Build the reviewer input JSON:
   ```json
   {
     "workspace_path": "<absolute>",
     "claim_ledger_path": "<ws>/paper/artifacts/claim_ledger.json",
     "evidence_backlog_path": "<ws>/paper/artifacts/evidence_backlog.json",
     "research_pack_path": "<ws>/paper/state/research_pack.json",
     "storyline_path": "<ws>/paper/artifacts/storyline_map.json",
     "round_num": 1
   }
   ```
2. Open a Task subagent with prompt from `subagent-prompts/evidence-skeptic.md`.
3. Persist the Review envelope via CLI.

### Alternative-Explanation-Reviewer Dispatch (always after evidence-skeptic)

1. Build the reviewer input JSON (same shape as evidence-skeptic).
2. Open a Task subagent with prompt from
   `subagent-prompts/alternative-explanation-reviewer.md`.
3. Persist the Review envelope via CLI.
4. If reviewer flags missing alternative explanations, add gap items to
   the evidence_backlog and re-persist via CLI.
