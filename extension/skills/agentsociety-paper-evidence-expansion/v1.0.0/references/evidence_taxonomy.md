# Evidence Taxonomy

This reference defines the categories of evidence gaps the
evidence-expansion producer must consider when auditing claim-evidence
alignment.

## Gap Categories

### 1. Missing Analysis

The claim requires a statistical or computational analysis that has not
been performed.

**Typical gaps:**
- No significance test for a pattern claim
- No comparison to baseline for a method claim
- No effect-size calculation for a difference claim
- No sensitivity analysis for a parameter-dependent claim

**How to flag:** `gap_type: "missing_analysis"`, specify the analysis
method needed.

---

### 2. Missing Control

The claim could be explained by a confound that has not been controlled
for.

**Typical gaps:**
- No control group for a causal claim
- No ablation study for a mechanism claim
- No placebo/sham condition for an intervention claim
- No time-reversed control for a temporal claim

**How to flag:** `gap_type: "missing_control"`, specify the confound
and the control needed.

---

### 3. Missing Robustness Check

The claim depends on a specific parameter, dataset, or condition, and
has not been tested under variation.

**Typical gaps:**
- Only one dataset supports the claim
- Only one parameter setting produces the result
- Only one time window shows the pattern
- No cross-validation or held-out test

**How to flag:** `gap_type: "missing_robustness"`, specify the
dimension of variation to test.

---

### 4. Missing Figure

The claim would be stronger with a visual argument that does not exist.

**Typical gaps:**
- No figure showing the pattern (pattern figure gap)
- No figure isolating the mechanism (mechanism figure gap)
- No figure demonstrating robustness (robustness figure gap)
- No figure marking the boundary (qualification figure gap)

**How to flag:** `gap_type: "missing_figure"`, specify the figure role
from `paper-architecture/references/figure_role_taxonomy.md` and the
claim it should support.

---

### 5. Missing Experiment

The claim requires an experiment that has not been conducted.

**Typical gaps:**
- No intervention experiment for a causal claim
- No replication across conditions for a generality claim
- No longitudinal data for a temporal claim

**How to flag:** `gap_type: "missing_experiment"`, specify the
experiment design needed.

---

### 6. Missing Alternative Explanation Test

A rival explanation for the observed result has not been tested or
ruled out.

**Typical gaps:**
- Alternative mechanism not tested
- Confound not ruled out
- Selection bias not addressed
- Simpson's paradox not checked

**How to flag:** `gap_type: "missing_alternative"`, specify the
alternative explanation and what test would address it.

---

### 7. Missing Literature

The claim overlaps with prior work that has not been cited or
distinguished.

**Typical gaps:**
- Known result presented as novel
- Prior method not compared
- Existing measure not cited

**How to flag:** `gap_type: "missing_literature"`, specify the known
work or search query needed.

## Priority Levels

| Priority | Criteria | Auto-executable? |
|----------|----------|-----------------|
| `high` | Claim is central AND evidence gap is fatal or major | Case-by-case |
| `medium` | Claim is supporting AND gap weakens but does not invalidate | Usually yes |
| `low` | Claim is qualifying AND gap affects scope | Usually yes |

## Auto-Execution Decision Matrix

| Gap type | Auto-executable? | Tool |
|----------|-----------------|------|
| Missing analysis | Usually yes | `agentsociety-analysis` |
| Missing control | Usually no | Human gate |
| Missing robustness | Usually yes | `agentsociety-analysis` |
| Missing figure | Yes (if data exists) | `agentsociety-analysis` |
| Missing experiment | No | Human gate |
| Missing alternative | Case-by-case | `agentsociety-analysis` or human gate |
| Missing literature | Yes | `agentsociety-literature-search` |

## Evidence Strength Levels

| Level | Criteria |
|-------|----------|
| `strong` | Direct evidence, controlled, robustness tested |
| `moderate` | Direct evidence, partially controlled, limited robustness |
| `weak` | Indirect evidence, uncontrolled, or single-observation |
| `absent` | No evidence; claim is unsupported |

The producer must downgrade claim wording strength when evidence is
`weak` or `absent`.
