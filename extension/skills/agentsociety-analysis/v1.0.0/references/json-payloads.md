# JSON Payloads (LLM-authored)

CLI accepts `--payload` as a **JSON object** or path to a `.json` file. Malformed JSON is repaired via `json-repair` before validation — fix semantics, not escaping.

## analysis_plan (`write-plan`)

```json
{
  "research_question": "Does treatment X increase metric Y by step 10?",
  "primary_metrics": ["Y", "treatment_flag"],
  "target_tables": ["agent_metrics", "run_summary"],
  "confirmatory_claims": [
    "Mean Y is higher under treatment than control after step 10"
  ],
  "exploratory_notes": "Optional side comparisons on subgroups",
  "simulation_limitations": "Single seed; not calibrated to real city",
  "eda_profile": "quick-stats",
  "table_checks": [
    {"table": "agent_metrics", "min_rows": 10, "columns": ["step", "Y"]}
  ],
  "synthesis_scope_hypothesis_ids": ["1"]
}
```

## claim (`record-claim`)

```json
{
  "claim_id": "c1",
  "statement": "Treatment arm shows higher mean Y after step 10",
  "mode": "confirmatory",
  "evidence": "agent_metrics: filter step>=10; compare mean(Y) by treatment_flag",
  "needs_chart": true
}
```

## phase attestation (`record-attestation`)

See `phase-attestation.md` for rubric keys. Minimal example:

```json
{
  "phase": "explore",
  "status": "DONE",
  "key_findings": [
    "agent_metrics has 1200 rows; treatment_flag balanced"
  ],
  "artifacts_written": [
    "presentation/hypothesis_1/data/eda_quick_stats.md"
  ],
  "rubric": {
    "tables_inspected": ["agent_metrics"],
    "data_limitations": "No demographic table; 12% missing Y in early steps",
    "eda_takeaway": "Distributions overlap but treatment tail is heavier"
  }
}
```

## report_outline.json (written to presentation dir)

```json
{
  "hypothesis_id": "1",
  "sections": [
    {"id": "overview", "title": "Experiment overview"},
    {"id": "data", "title": "Data and measures"},
    {"id": "findings", "title": "Findings"},
    {"id": "conclusions", "title": "Conclusions"},
    {"id": "appendix", "title": "Artifacts"}
  ],
  "figures": [
    {
      "asset": "chart_01_treatment_compare.png",
      "caption": "Mean Y by treatment after step 10",
      "finding_number": 1
    }
  ]
}
```

## evidence_index.json (`build-report-context`)

Auto-generated. Each source maps to a report section (`data`, `findings`, …).

```json
{
  "hypothesis_id": "1",
  "sources": [
    {
      "path": "presentation/hypothesis_1/data/eda_quick_stats.md",
      "kind": "eda",
      "phase": "explore",
      "report_section": "data",
      "label": "eda_quick_stats.md",
      "excerpt": "..."
    }
  ],
  "section_map": {
    "data": ["presentation/hypothesis_1/data/eda_quick_stats.md"],
    "findings": ["presentation/hypothesis_1/charts/chart_01_compare.png"]
  }
}
```

Also writes `data/report_context.md` (grouped digest for LLM).

## analysis_summary.json

```json
{
  "summary": "Treatment raises mean Y post step 10; effect modest.",
  "key_findings": ["Confirmatory claim c1 supported with caveats"],
  "limitations": "Single simulation run; not external validation",
  "evidence_index_path": "data/evidence_index.json"
}
```

## synthesis_brief.json

```json
{
  "synthesis_question": "What is consistent across hypotheses 1 and 2?",
  "scope_hypothesis_ids": ["1", "2"],
  "source_artifacts": [
    "presentation/hypothesis_1/report_zh.md",
    "presentation/hypothesis_2/data/analysis_summary.json"
  ],
  "comparison_mode": "cross_hypothesis"
}
```

## figure contract (`record-contract`)

```json
{
  "contract_id": "fc1",
  "claim_id": "c1",
  "core_finding": "Treatment mean Y higher after step 10",
  "output_files": ["charts/chart_01_treatment_compare.png"]
}
```
