# Reports (MD + HTML)

**No MD→HTML converter.** Bilingual MD and HTML are both **required** gate deliverables — LLM-authored natively.

Primary shell: `assets/report-shell.reference.html`. Independent review: `references/report-review.md`.

## Produce workflow

```text
refine gate_pass
  → build-report-context
  → report-producer subagent
  → report-reviewer subagent (independent)
  → record-report-review (PASS)
  → sync-report-assets (charts→assets + embed-interactive-eda)
  → validate-release
  → record-attestation (produce)
```

Orchestrator only: user alignment, attestation wording, `advance`.

## build-report-context

```bash
$PYTHON_PATH .agentsociety/bin/ags.py analysis build-report-context \
  --workspace . --hypothesis-id $HYP_ID
```

Outputs `data/evidence_index.json` + `data/report_context.md` from phase artifacts, `data/`, `charts/`, claims, contracts.

## Section integration

| Section     | Content                                                                |
| ----------- | ---------------------------------------------------------------------- |
| overview    | Research question, experiment design                                   |
| data        | Synthesize EDA (bullets + summary table); iframe hub in HTML §数据 tab |
| findings    | One block per confirmatory claim + `assets/chart_*.png` + caption      |
| conclusions | Answer + simulation limitations                                        |
| appendix    | Artifact table + EDA links                                             |

Simulation template: setup → data → findings (per claim) → conclusions → appendix. See claim subsections with evidence table + figure + caveat.

## Embedding rules

Pipeline: `run-eda`/`run-code` → `sync-report-assets` → `assets/` only in report body.

| Asset type | Markdown                                                | HTML                                                                |
| ---------- | ------------------------------------------------------- | ------------------------------------------------------------------- |
| Chart      | `![caption](assets/chart_01_slug.png)` + one line below | `.figure-block` + img + takeaway                                    |
| Table      | pipe table or small HTML                                | `.table-wrap` + `.data-table`                                       |
| EDA        | bullets + summary table in §数据                        | tab **摘要** + iframe `data/eda_hub.html` (see `references/eda.md`) |

Never reference `charts/` in final report body. Numbers must trace to `sqlite.db` or registered artifacts.

## HTML blocks (from shell)

| Block             | Use                                     |
| ----------------- | --------------------------------------- |
| `.metrics`        | 2–4 KPIs with `.metric-source` footnote |
| `.report-toc`     | Sticky nav when ≥4 sections             |
| `.figure-block`   | Chart + caption + takeaway              |
| `.eda-panel`      | Short EDA summary before iframe         |
| `.mermaid-block`  | Claim chain / pipeline (≤12 nodes)      |
| `.limitations`    | Simulation external validity            |
| `.artifact-table` | Appendix inventory                      |

Keep `<!-- EDA_INTERACTIVE_BEGIN -->` … `<!-- EDA_INTERACTIVE_END -->` markers for mechanical re-embed.

## Mermaid (optional)

Templates: data flow, claim→evidence chain, agent loop, EDA→finding. ≤12 nodes; offline `mermaid.min.js` in shell.

## Canvas vs disk

| Layer  | Role                                               |
| ------ | -------------------------------------------------- |
| Canvas | IDE exploration, layout drafts — not gate artifact |
| Disk   | `report_*.md` / `report_*.html` under presentation |

Handoff: finalize narrative on disk; do not treat Canvas as substitute for `validate-release`.

## HTML polish checklist

| Element | Guidance                                                              |
| ------- | --------------------------------------------------------------------- |
| Header  | Brand lockup + `agentsociety_icon.svg`                                |
| Metrics | 3–4 KPIs from EDA/SQL                                                 |
| TOC     | Sticky when long                                                      |
| §数据   | Summary table + interactive EDA tab                                   |
| §发现   | Claim-led sections with figures                                       |
| Style   | Scientific tone; navy/slate shell — no emoji spam, no 5MB inline HTML |

Optional typography: `support/frontend-design/` (polish only, not content).

## Bilingual parity

Same `assets/` filenames, same figures/tables, translated prose only. `report_outline.json` captions match takeaways.

## Pre-review checklist

- [ ] `build-report-context` run
- [ ] `sync-report-assets` after final chart list
- [ ] All `assets/` paths resolve
- [ ] §数据 cites EDA from `evidence_index.json`
- [ ] report-reviewer PASS recorded
- [ ] `limitations` in `analysis_summary.json`

Quality bar: `references/analysis-quality.md` (Produce section).

## Synthesis (Stage 6)

Cross-hypothesis reports in `synthesis/` — integrate scoped `report_context.md` / final reports; compare findings, don't re-dump raw EDA. `synthesis_brief.json` lists every `source_artifacts` path used.
