# Persistence Layout - `<workspace>/paper/`

Single source of truth: every helper in
`agentsociety2.skills.paper.paths` derives from this layout.

```
<workspace>/paper/
  paper_meta.yaml                   # un-namespaced user identity (init-meta)
  state/
    research_pack.json              # paper-adapter output
    paper_state.yaml                # phase / round / counters / release_status
    human_gates.yaml                # pending + decided major-pivot gates
  artifacts/
    storyline_map.{md,json}         # paper-framing output
    claim_ledger.{md,json}          # paper-architecture (claim_tree)
    evidence_backlog.{md,json}      # paper-evidence-expansion
    figure_argument_map.{md,json}   # paper-architecture (figure_argument)
    manuscript/
      abstract.md                   # paper-architecture (draft_section)
      main.md
      results/
        01_<slug>.md                # one file per result subsection
        02_<slug>.md
      discussion.md
  reviews/
    review_round_001.yaml           # paper-skeptical-review (append-only)
    review_round_NNN.yaml
  runs/
    <YYYYMMDD_HHMMSS>/
      envelope.json                 # final envelope returned by this run
      dispatch_NNN.json             # one record per Task subagent
      compose/
        main.tex                    # rendered from main.tex.j2
        references.bib              # adapter/bib_writer output
        wlscirep.cls                # support files copied verbatim
        naturemag-doi.bst
        jabbrv.sty
        jabbrv-ltwa-{all,en}.ldf
        Figure/
          <id>.<png|pdf>            # copied panels
        out/
          paper.pdf                 # ← deliverable
          paper.log
```

## Pydantic Schemas (canonical)

Defined in `agentsociety2.skills.paper.models`:

- `PaperMeta` - identity block backing `paper_meta.yaml`
- `PaperState` - state machine backing `paper_state.yaml`; phases:
  `intake -> framing -> evidence-audit -> expansion-plan ->
  manuscript-build -> skeptical-review -> revision-router ->
  release-gate`
- `ResearchPack` - normalized workspace ingest; backs
  `research_pack.json`
- `StorylineMap` - main_question / core_tension / why_now /
  contribution_statement / current_angle / rejected_angles /
  kill_criteria / section_logic
- `ClaimLedger`, `Claim` - claim_id / claim_text / claim_type /
  evidence_support / linked_figures / unsupported_gaps /
  allowed_wording_strength (`weak|moderate|strong`) /
  reviewer_objections
- `EvidenceBacklog`, `EvidenceGap` - gap_id / description /
  category (`analysis|control|robustness|figure|experiment`) /
  priority (`high|medium|low`) / `auto_executable` / `human_gated` /
  `related_claim_ids`
- `FigureArgumentMap`, `FigureSpec` - figure_id / title /
  question_answered / claim_supported / target_section /
  status (`planned|drafted|rendered|final`) / `panels`
- `ReviewRound`, `Review` - reviewer_profile / verdict
  (`accept|revise_local|revise_structural|pivot_conceptual|
  pivot_major|fatal`) / severity / target_layer (`wording|paragraph|
  section|figure_plan|evidence|framing`) / issue_type /
  reroute_target / `human_gate_flag` / resolved_state /
  resolution_note
- `HumanGate` - gate_id / triggering_issue / proposed_pivot /
  severity / rationale / user_decision (`accept|reject|modify`) /
  accepted_version / decided_at
- `DispatchRecord` - dispatch_num / target_skill / target_subagent /
  envelope / status (`pending|running|completed|failed`)

## Init Sentinel

`<workspace>/paper/state/paper_state.yaml` is the canonical
"initialized" sentinel for the orchestrator. Its presence implies
`paper_meta.yaml` is also present (because `intake` requires it).

## Counter Caps (Phase 4)

`paper_state.yaml#counters`:

```yaml
counters:
  figure_regenerations: 0     # cap 2/round (analysis re-dispatch)
  citation_augmentations: 0   # cap 2/round (literature-search re-dispatch)
```

Hitting either cap on the same `target_artifact + issue_type` opens
a human gate.
