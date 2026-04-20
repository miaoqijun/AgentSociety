# Stage 5: Cross-Experiment Synthesis

Goal: compare reports across experiments or hypotheses when the user explicitly requests it.

## Steps

1. Read prior outputs from `presentation/`, preferring existing `report_zh.md` files, then `report_en.md`, and only using `report.md` as a backward-compatible fallback before loading missing context with `$PYTHON_PATH .agentsociety/bin/ags.py analysis load-context`.
2. Compare experiment goals, design differences, result patterns, and important conflicts.
3. Propose synthesis findings in text before generating any new chart.
4. Generate synthesis charts only when the comparison genuinely needs them, and cap them at 3 unless the user approves a trade-off.
5. Write synthesis outputs only under the dedicated `synthesis/` root directory.
6. Write `synthesis/synthesis_report_zh.md` and `synthesis/synthesis_report_en.md` unless the user explicitly narrows the deliverable.

## Exit Conditions

- The comparison findings are approved, and the synthesis report is accepted by the user.
