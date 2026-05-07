# Stage: run_review_round

Dispatch the three specialist reviewers and aggregate their verdicts
into a single review round.

## Dispatch Order

The three reviewers are dispatched in sequence (not parallel) because
later reviewers may benefit from seeing earlier issues:

1. **significance-calibrator** — checks Layer 1 (argument/evidence)
2. **evidence-skeptic** — checks Layer 1 (evidence discipline in prose)
3. **precision-editor** — checks Layer 2 (word/paragraph/flow)

Layer 1 reviewers run first. If both Layer 1 reviewers accept, the
precision-editor runs. If Layer 1 finds fatal issues, the
precision-editor is skipped — polishing prose over a broken argument
wastes a round.

## Routing Table

| Condition | Dispatch | Persist |
|-----------|----------|---------|
| `phase=skeptical-review` AND manuscript blocks exist | significance-calibrator | — |
| significance-calibrator done | evidence-skeptic | — |
| evidence-skeptic done AND no fatal from Layer 1 | precision-editor | — |
| All reviewers done | Aggregate into ReviewRound | `paper-orchestrator review --payload <ReviewRound JSON> --round N` |
| Any reviewer verdict = fatal | Skip remaining, aggregate immediately | same |
| round_verdict != accept | Route to revision-router | n/a |
| round_verdict = accept | Check release_blockers checklist | n/a |
| release_blockers pass | Advance to release-gate | n/a |
| 3+ consecutive non-accept rounds | Open `human_gate` | n/a |

## Dispatch Instructions

### Significance-Calibrator

```json
{
  "workspace_path": "<absolute>",
  "manuscript_dir": "<ws>/paper/artifacts/manuscript",
  "storyline_path": "<ws>/paper/artifacts/storyline_map.json",
  "claim_ledger_path": "<ws>/paper/artifacts/claim_ledger.json",
  "research_pack_path": "<ws>/paper/state/research_pack.json",
  "round_num": 1
}
```

### Evidence-Skeptic

```json
{
  "workspace_path": "<absolute>",
  "manuscript_dir": "<ws>/paper/artifacts/manuscript",
  "claim_ledger_path": "<ws>/paper/artifacts/claim_ledger.json",
  "evidence_backlog_path": "<ws>/paper/artifacts/evidence_backlog.json",
  "research_pack_path": "<ws>/paper/state/research_pack.json",
  "round_num": 1
}
```

### Precision-Editor

```json
{
  "workspace_path": "<absolute>",
  "manuscript_dir": "<ws>/paper/artifacts/manuscript",
  "manuscript_structure_ref": "references/manuscript_structure.md",
  "prior_layer1_issues": [<issues from calibrator + skeptic>],
  "round_num": 1
}
```

## Aggregation Logic

```python
unresolved_fatal = [i for r in reviews for i in r.issues if i.severity == "fatal"]
unresolved_major = [i for r in reviews for i in r.issues if i.severity == "major"]
minor = [i for r in reviews for i in r.issues if i.severity == "minor"]

if unresolved_fatal:
    round_verdict = "fatal"
elif unresolved_major:
    round_verdict = "revise"
else:
    round_verdict = "accept"
```

## Release Blockers Checklist

After `round_verdict = accept`, check `checklists/release_blockers.md`:

1. No claim in claim_ledger has empty evidence_support AND non-empty
   unsupported_gaps
2. Every figure in figure_argument_map has at least one claim_supported
3. Abstract follows the pressure curve (framing_principles.md)
4. No inflation words without specific justification
5. Discussion is ambitious in implication but conservative in inference

If any blocker fails, route back to revision-router.
